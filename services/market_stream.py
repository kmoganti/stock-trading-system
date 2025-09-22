import asyncio
import logging
import struct
from typing import Dict, List, Optional, Set, Tuple

from .iifl_api import IIFLAPIService
from .screener import ScreenerService
from .data_fetcher import DataFetcher

logger = logging.getLogger(__name__)

try:
    from bridgePy import connector as iifl_connector
    HAS_BRIDGEPY = True
except ImportError:
    HAS_BRIDGEPY = False


class MarketStreamService:
    """
    Connects to the IIFL Market Data Stream to receive real-time events
    for building a dynamic intraday watchlist.
    """

    def __init__(self, iifl_service: IIFLAPIService, screener_service: ScreenerService):
        # Allow initialization without bridgePy for unit tests; enforce at connect time
        self.iifl_service = iifl_service
        self.screener_service = screener_service
        self.connection = iifl_connector.Connect() if HAS_BRIDGEPY else None
        self.is_connected = False
        self._watchlist_symbols: Set[str] = set()

        # In-memory live state per instrumentId (string)
        self._live_state: Dict[str, Dict] = {}
        self._symbol_to_id: Dict[str, str] = {}
        self._id_to_symbol: Dict[str, str] = {}
        self._market_open: bool = True
        self._lpp_bands: Dict[str, Tuple[float, float]] = {}

        # Register handlers
        if self.connection is not None:
            self.connection.on_error = self._handle_error
            self.connection.on_acknowledge_response = self._handle_ack
            self.connection.on_high_52_week_data_received = self._handle_52_week_high
            self.connection.on_low_52_week_data_received = self._handle_52_week_low
            self.connection.on_feed_data_received = self._handle_feed
            self.connection.on_market_status_data_received = self._handle_market_status
            self.connection.on_lpp_data_received = self._handle_lpp
            self.connection.on_upper_circuit_data_received = self._handle_upper_circuit
            self.connection.on_lower_circuit_data_received = self._handle_lower_circuit
            self.connection.on_open_interest_data_received = self._handle_oi

    def _handle_error(self, code: int, message: str):
        logger.error(f"Market Stream Error: Code {code} - {message}")
        self.is_connected = False

    def _handle_ack(self, response: str):
        logger.info(f"Market Stream Ack: {response}")

    def _handle_52_week_high(self, data: bytearray, topic: str):
        """
        Handles the 52-week high event. This is where we add the symbol to our watchlist.
        Packet Structure: instrumentId (UInt32), 52WeekHigh (UInt32), priceDivisor (Int32)
        """
        try:
            # Unpack the binary data according to the documentation
            instrument_id, _, _ = struct.unpack('<III', data)
            symbol = str(instrument_id)

            # Avoid reprocessing the same symbol within a short time
            if symbol in self._watchlist_symbols:
                return

            logger.info(f"EVENT: 52-Week High for Instrument ID: {symbol}. Adding to watchlist.")
            self._watchlist_symbols.add(symbol)

            # Use the ScreenerService to add this single symbol to the watchlist
            # We run this in a separate task to avoid blocking the event handler.
            asyncio.create_task(
                self.screener_service.watchlist_service.refresh_from_list(
                    symbols=[symbol],
                    category="day_trading",
                    deactivate_missing=False  # Don't deactivate others
                )
            )
        except Exception as e:
            logger.error(f"Error handling 52-week high event: {e}", exc_info=True)

    def _handle_52_week_low(self, data: bytearray, topic: str):
        """
        Handles the 52-week low event. Auto-add the symbol to short_sell watchlist category.
        Packet: instrumentId (UInt32), 52WeekLow (UInt32), priceDivisor (Int32)
        """
        try:
            instrument_id, _, _ = struct.unpack('<III', data)
            symbol = str(instrument_id)
            logger.info(f"EVENT: 52-Week Low for Instrument ID: {symbol}. Adding to short_sell.")
            asyncio.create_task(
                self.screener_service.watchlist_service.refresh_from_list(
                    symbols=[symbol],
                    category="short_sell",
                    deactivate_missing=False
                )
            )
        except Exception as e:
            logger.error(f"Error handling 52-week low event: {e}", exc_info=True)

    def _decode_feed(self, data: bytearray) -> Optional[Dict]:
        """Decode 188-byte Market Feed packet as per IIFL spec.

        Returns a dict with normalized numeric values (prices divided by priceDivisor).
        """
        try:
            # Unpack fixed header fields up to priceDivisor and lastTradedTime
            # Little-endian as per docs
            (
                ltp,
                lastTradedQuantity,
                tradedVolume,
                high,
                low,
                open_price,
                close,
                averageTradedPrice,
            ) = struct.unpack_from('<iIIIIIIi', data, 0)

            # Skip reserved (2 bytes), then best bid/ask and totals up to priceDivisor
            reserved = struct.unpack_from('<H', data, 32)[0]
            bestBidQuantity, bestBidPrice, bestAskQuantity, bestAskPrice, totalBidQuantity, totalAskQuantity, priceDivisor, lastTradedTime = struct.unpack_from(
                '<I i I i I I i i', data, 34
            )

            # Guard priceDivisor
            div = priceDivisor if priceDivisor and priceDivisor != 0 else 1

            def p(v: int) -> float:
                return float(v) / float(div)

            decoded = {
                "ltp": p(ltp),
                "lastTradedQuantity": int(lastTradedQuantity),
                "tradedVolume": int(tradedVolume),
                "high": p(high),
                "low": p(low),
                "open": p(open_price),
                "close": p(close),
                "averageTradedPrice": p(averageTradedPrice),
                "bestBidQuantity": int(bestBidQuantity),
                "bestBidPrice": p(bestBidPrice),
                "bestAskQuantity": int(bestAskQuantity),
                "bestAskPrice": p(bestAskPrice),
                "totalBidQuantity": int(totalBidQuantity),
                "totalAskQuantity": int(totalAskQuantity),
                "priceDivisor": int(div),
                "lastTradedTime": int(lastTradedTime),
            }
            return decoded
        except Exception as e:
            logger.error(f"Failed to decode market feed: {e}", exc_info=True)
            return None

    def _update_live_state(self, topic: str, payload: Dict) -> None:
        try:
            # topic format: nseeq/<instrumentId>
            parts = str(topic).split('/')
            if len(parts) != 2:
                return
            instrument_id = parts[1]
            self._live_state[instrument_id] = payload
        except Exception:
            return

    def _handle_feed(self, data: bytearray, topic: str):
        try:
            decoded = self._decode_feed(data)
            if not decoded:
                return
            # Compute derived metrics
            try:
                close = decoded.get("close") or 0.0
                ltp = decoded.get("ltp") or 0.0
                best_bid = decoded.get("bestBidPrice") or 0.0
                best_ask = decoded.get("bestAskPrice") or 0.0
                total_bid = float(decoded.get("totalBidQuantity") or 0)
                total_ask = float(decoded.get("totalAskQuantity") or 0)
                pct_change = ((ltp - close) / close * 100.0) if close else 0.0
                spread = ((best_ask - best_bid) / best_bid * 100.0) if best_bid > 0 else 0.0
                imbalance = ((total_bid - total_ask) / (total_bid + total_ask)) if (total_bid + total_ask) > 0 else 0.0
                decoded.update({
                    "pctChange": pct_change,
                    "spreadPct": spread,
                    "depthImbalance": imbalance,
                })
            except Exception:
                pass

            self._update_live_state(topic, decoded)
        except Exception as e:
            logger.error(f"Error handling feed event: {e}", exc_info=True)

    def _handle_market_status(self, data: bytearray, topic: str):
        try:
            (code,) = struct.unpack('<h', data)
            self._market_open = (code == 2)
        except Exception:
            return

    def _handle_lpp(self, data: bytearray, topic: str):
        try:
            lpp_high, lpp_low, divisor = struct.unpack('<IIi', data)
            div = divisor if divisor else 1
            parts = str(topic).split('/')
            if len(parts) != 2:
                return
            inst_id = parts[1]
            self._lpp_bands[inst_id] = (float(lpp_low) / div, float(lpp_high) / div)
        except Exception:
            return

    def _handle_upper_circuit(self, data: bytearray, topic: str):
        try:
            inst_id, upper, div = struct.unpack('<IIi', data)
            key = str(inst_id)
            state = self._live_state.get(key, {})
            state['upperCircuit'] = float(upper) / (div or 1)
            self._live_state[key] = state
        except Exception:
            return

    def _handle_lower_circuit(self, data: bytearray, topic: str):
        try:
            inst_id, lower, div = struct.unpack('<IIi', data)
            key = str(inst_id)
            state = self._live_state.get(key, {})
            state['lowerCircuit'] = float(lower) / (div or 1)
            self._live_state[key] = state
        except Exception:
            return

    def _handle_oi(self, data: bytearray, topic: str):
        try:
            open_interest, day_high_oi, day_low_oi, previous_oi = struct.unpack('<iiii', data)
            parts = str(topic).split('/')
            if len(parts) != 2:
                return
            inst_id = parts[1]
            state = self._live_state.get(inst_id, {})
            state['openInterest'] = int(open_interest)
            state['openInterestChangePct'] = ((open_interest - previous_oi) / previous_oi * 100.0) if previous_oi else 0.0
            self._live_state[inst_id] = state
        except Exception:
            return

    async def connect_and_subscribe(self):
        """
        Connects to the IIFL Bridge and subscribes to market-wide events.
        """
        if not HAS_BRIDGEPY or self.connection is None:
            raise ImportError("The 'bridgePy' package is required for market streaming. Please install it.")
        if self.is_connected:
            logger.info("Market stream is already connected.")
            return

        session_token = self.iifl_service.session_token
        if not session_token:
            logger.error("Cannot connect to market stream without a valid session token.")
            return

        try:
            conn_req = f'{"host": "bridge.iiflcapital.com", "port": 8883, "token": "{session_token}"}'
            self.connection.connect_host(conn_req)
            self.is_connected = True
            logger.info("Successfully connected to IIFL Market Stream.")

            # Give a moment for the connection to establish before subscribing
            await asyncio.sleep(1)

            # Subscribe to the 52-week high event for the NSE Equity segment
            # Other events like 'on_upper_circuit_data_received' can be added here too.
            sub_req = '{"subscriptionList": ["nseeq"]}'
            self.connection.subscribe_52_week_high(sub_req)
            self.connection.subscribe_52_week_low(sub_req)
            self.connection.subscribe_market_status(sub_req)
            logger.info("Subscribed to 52-week high/low and market status events for NSEEQ.")

            # Subscribe to market feed for active day_trading watchlist symbols
            try:
                symbols = await self.screener_service.watchlist_service.get_watchlist(active_only=True, category="day_trading")
                if not symbols:
                    logger.info("No symbols in day_trading watchlist; skipping feed subscription.")
                else:
                    fetcher = DataFetcher(self.iifl_service)
                    topics: List[str] = []
                    for sym in symbols:
                        try:
                            inst_id = await fetcher._resolve_instrument_id(sym)
                            if not inst_id:
                                continue
                            self._symbol_to_id[sym.upper()] = str(inst_id)
                            self._id_to_symbol[str(inst_id)] = sym.upper()
                            topics.append(f"nseeq/{inst_id}")
                        except Exception:
                            continue

                    if topics:
                        # Chunk subscriptions to <=1024 topics per request
                        chunk_size = 1000
                        for i in range(0, len(topics), chunk_size):
                            chunk = topics[i:i+chunk_size]
                            req = '{"subscriptionList": [' + ",".join([f'"{t}"' for t in chunk]) + ']}'
                            self.connection.subscribe_feed(req)
                            self.connection.subscribe_lpp(req)
                            self.connection.subscribe_open_interest(req)
                        logger.info(f"Subscribed to market feed for {len(topics)} instruments from watchlist.")
            except Exception as e:
                logger.warning(f"Failed to subscribe to watchlist feed: {e}")

        except Exception as e:
            logger.error(f"Failed to connect or subscribe to market stream: {e}", exc_info=True)
            self.is_connected = False

    async def disconnect(self):
        """Disconnects from the market stream."""
        if self.is_connected:
            self.connection.disconnect_host()
            self.is_connected = False
            logger.info("Disconnected from IIFL Market Stream.")

    def get_watchlist_snapshot(self) -> List[Dict]:
        """Return a snapshot list of live data for current watchlist subscriptions."""
        snapshot: List[Dict] = []
        try:
            for inst_id, state in self._live_state.items():
                symbol = self._id_to_symbol.get(inst_id) or inst_id
                row = {
                    "symbol": symbol,
                    "instrumentId": inst_id,
                    "exchange": "NSEEQ",
                    "ltp": state.get("ltp"),
                    "pctChange": state.get("pctChange"),
                    "averageTradedPrice": state.get("averageTradedPrice"),
                    "high": state.get("high"),
                    "low": state.get("low"),
                    "open": state.get("open"),
                    "close": state.get("close"),
                    "spreadPct": state.get("spreadPct"),
                    "depthImbalance": state.get("depthImbalance"),
                    "totalBidQuantity": state.get("totalBidQuantity"),
                    "totalAskQuantity": state.get("totalAskQuantity"),
                    "bestBidPrice": state.get("bestBidPrice"),
                    "bestAskPrice": state.get("bestAskPrice"),
                    "lastTradedTime": state.get("lastTradedTime"),
                    "upperCircuit": state.get("upperCircuit"),
                    "lowerCircuit": state.get("lowerCircuit"),
                    "openInterest": state.get("openInterest"),
                    "openInterestChangePct": state.get("openInterestChangePct"),
                    "marketOpen": self._market_open,
                }
                snapshot.append(row)
        except Exception:
            pass
        return snapshot
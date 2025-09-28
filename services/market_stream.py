import asyncio
import logging
import struct
import os
import time
from typing import Dict, List, Optional, Set

from .iifl_api import IIFLAPIService
from .screener import ScreenerService

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
        if not HAS_BRIDGEPY:
            raise ImportError("The 'bridgePy' package is required for market streaming. Please install it.")

        self.iifl_service = iifl_service
        self.screener_service = screener_service
        self.connection = iifl_connector.Connect()
        self.is_connected = False
        self._watchlist_symbols: Set[str] = set()
        # Debounce timestamps to avoid refreshing the same symbol too frequently
        self._recent_symbols_ts: Dict[str, float] = {}
        # Lock to guard concurrent watchlist updates
        self._lock = asyncio.Lock()

        # Register handlers
        self.connection.on_error = self._handle_error
        self.connection.on_acknowledge_response = self._handle_ack
        self.connection.on_high_52_week_data_received = self._handle_52_week_high

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
            # Basic sanity checks
            if not data or len(data) < 12:
                logger.warning("Received malformed 52-week data (too short).")
                return

            # Unpack the binary data: instrumentId (UInt32), 52WeekHigh (UInt32), priceDivisor (Int32 signed)
            instrument_id, _, price_divisor = struct.unpack('<IIi', data[:12])

            # Try resolving instrumentation id to a tradable symbol via IIFLAPIService if available
            symbol = None
            try:
                resolver = getattr(self.iifl_service, 'resolve_instrument_id', None)
                if callable(resolver):
                    symbol = resolver(instrument_id)
            except Exception:
                symbol = None

            if not symbol:
                symbol = str(instrument_id)

            # Debounce: ignore repeats within window (seconds)
            debounce_seconds = int(os.getenv('MARKET_STREAM_DEBOUNCE_S', '300'))
            now = time.time()
            last = self._recent_symbols_ts.get(symbol)
            if last and (now - last) < debounce_seconds:
                logger.debug("Ignoring duplicate 52-week event for %s (debounced).", symbol)
                return
            self._recent_symbols_ts[symbol] = now

            logger.info(f"EVENT: 52-Week High for Instrument ID: {instrument_id} (symbol: {symbol}). Queuing watchlist add.")

            async def _enqueue_refresh():
                # Guard against concurrent adds
                async with self._lock:
                    if symbol in self._watchlist_symbols:
                        logger.debug("Symbol %s already in internal watchlist set.", symbol)
                        return
                    self._watchlist_symbols.add(symbol)

                try:
                    await self.screener_service.watchlist_service.refresh_from_list(
                        symbols=[symbol],
                        category="day_trading",
                        deactivate_missing=False
                    )
                    logger.info("Added %s to watchlist from 52-week event.", symbol)
                except Exception as e:
                    logger.error("Failed to refresh watchlist for %s: %s", symbol, e, exc_info=True)

            asyncio.create_task(_enqueue_refresh())

        except Exception as e:
            logger.error(f"Error handling 52-week high event: {e}", exc_info=True)

    async def connect_and_subscribe(self):
        """
        Connects to the IIFL Bridge and subscribes to market-wide events.
        """
        if self.is_connected:
            logger.info("Market stream is already connected.")
            return

        session_token = self.iifl_service.session_token
        if not session_token:
            logger.error("Cannot connect to market stream without a valid session token.")
            return

        # Use environment variables for configuration
        bridge_host = os.getenv('IIFL_BRIDGE_HOST', 'bridge.iiflcapital.com')
        bridge_port = int(os.getenv('IIFL_BRIDGE_PORT', '8883'))
        use_tls = os.getenv('IIFL_BRIDGE_USE_TLS', '1') not in ('0', 'false', 'False')

        # Reconnection with exponential backoff
        max_retries = int(os.getenv('MARKET_STREAM_MAX_RETRIES', '5'))
        attempt = 0
        backoff = float(os.getenv('MARKET_STREAM_BACKOFF_S', '1'))

        while attempt < max_retries and not self.is_connected:
            attempt += 1
            try:
                conn_payload = {
                    'host': bridge_host,
                    'port': bridge_port,
                    'token': session_token
                }
                if use_tls:
                    conn_payload['ssl'] = True

                # Build the JSON-like connection string expected by bridgePy
                conn_req = str(conn_payload).replace("'", '"')
                self.connection.connect_host(conn_req)
                self.is_connected = True
                logger.info("Successfully connected to IIFL Market Stream (host=%s port=%s tls=%s).", bridge_host, bridge_port, use_tls)

                # Give a moment for the connection to establish before subscribing
                await asyncio.sleep(1)

                sub_req = '{"subscriptionList": ["nseeq"]}'
                self.connection.subscribe_52_week_high(sub_req)
                logger.info("Subscribed to 52-week high events for NSEEQ.")
                break

            except Exception as e:
                logger.error("Failed to connect/subscribe to market stream (attempt %d): %s", attempt, e, exc_info=True)
                self.is_connected = False
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

        if not self.is_connected:
            logger.error("Could not establish market stream connection after %d attempts.", max_retries)

    async def disconnect(self):
        """Disconnects from the market stream."""
        if self.is_connected:
            self.connection.disconnect_host()
            self.is_connected = False
            logger.info("Disconnected from IIFL Market Stream.")
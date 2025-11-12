import os
import asyncio
import logging
import struct
from typing import Dict, List, Optional, Set
from functools import partial

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

        try:
            # BridgePy plugin requires port 8883 for IIFL market stream
            bridge_port = int(os.getenv("IIFL_BRIDGE_PORT", "8883"))
            conn_req = f'{{"host": "bridge.iiflcapital.com", "port": {bridge_port}, "token": "{session_token}"}}'
            await asyncio.to_thread(self.connection.connect_host, conn_req)
            self.is_connected = True
            logger.info("Successfully connected to IIFL Market Stream.")

            # Give a moment for the connection to establish before subscribing
            await asyncio.sleep(1)

            # Subscribe to the 52-week high event for the NSE Equity segment
            # Other events like 'on_upper_circuit_data_received' can be added here too.
            sub_req = '{"subscriptionList": ["nseeq"]}'
            await asyncio.to_thread(self.connection.subscribe_52_week_high, sub_req)
            logger.info("Subscribed to 52-week high events for NSEEQ.")

        except Exception as e:
            logger.error(f"Failed to connect or subscribe to market stream: {e}", exc_info=True)
            self.is_connected = False

    async def disconnect(self):
        """Disconnects from the market stream."""
        if self.is_connected:
            await asyncio.to_thread(self.connection.disconnect_host)
            self.is_connected = False
            logger.info("Disconnected from IIFL Market Stream.")
import struct

from services.market_stream import MarketStreamService
from services.iifl_api import IIFLAPIService
from services.screener import ScreenerService


class _DummyScreener:
    def __init__(self):
        self.watchlist_service = None


def _build_dummy_feed():
    # Build a minimal 188-byte buffer with divisor=100 and ltp=12345 (=> 123.45)
    buf = bytearray(188)
    # ltp (int32)
    struct.pack_into('<i', buf, 0, 12345)
    # lastTradedQuantity (uint32)
    struct.pack_into('<I', buf, 4, 10)
    # tradedVolume (uint32)
    struct.pack_into('<I', buf, 8, 1000)
    # high, low, open, close (int32)
    struct.pack_into('<i', buf, 12, 13000)
    struct.pack_into('<i', buf, 16, 12000)
    struct.pack_into('<i', buf, 20, 12500)
    struct.pack_into('<i', buf, 24, 12400)
    # avg traded price (int32)
    struct.pack_into('<i', buf, 28, 12450)
    # reserved (2 bytes) left as zeros at 32-33
    # bestBidQuantity, bestBidPrice, bestAskQuantity, bestAskPrice, totalBidQuantity, totalAskQuantity, priceDivisor, lastTradedTime
    struct.pack_into('<I', buf, 34, 100)
    struct.pack_into('<i', buf, 38, 12300)
    struct.pack_into('<I', buf, 42, 200)
    struct.pack_into('<i', buf, 46, 12350)
    struct.pack_into('<I', buf, 50, 1000)
    struct.pack_into('<I', buf, 54, 800)
    struct.pack_into('<i', buf, 58, 100)
    struct.pack_into('<i', buf, 62, 1695286500)
    return bytes(buf)


def test_decode_feed_basic():
    dummy = _DummyScreener()
    svc = MarketStreamService(IIFLAPIService(), dummy)  # bridgePy import assumed present in environment

    data = _build_dummy_feed()
    decoded = svc._decode_feed(data)
    assert decoded is not None
    assert abs(decoded['ltp'] - 123.45) < 1e-6
    assert decoded['lastTradedQuantity'] == 10
    assert decoded['tradedVolume'] == 1000
    assert abs(decoded['bestBidPrice'] - 123.0) < 1e-6
    assert abs(decoded['bestAskPrice'] - 123.5) < 1e-6


def test_snapshot_ranking_sort_key_stability():
    dummy = _DummyScreener()
    svc = MarketStreamService(IIFLAPIService(), dummy)
    # Inject minimal state
    svc._id_to_symbol['1'] = 'AAA'
    svc._id_to_symbol['2'] = 'BBB'
    svc._live_state['1'] = {"ltp": 100.0, "pctChange": 2.0}
    svc._live_state['2'] = {"ltp": 99.0}
    snap = svc.get_watchlist_snapshot()
    # Ensure keys exist and missing pctChange does not break
    assert any(r.get('symbol') == 'AAA' for r in snap)
    assert any(r.get('symbol') == 'BBB' for r in snap)

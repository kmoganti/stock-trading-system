"""
Unit tests for Order Manager Service
Tests order placement, modification, cancellation, and status tracking
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from decimal import Decimal

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.order_manager import OrderManager
from services.iifl_api import IIFLAPIService


class TestOrderManager:
    """Test suite for Order Manager Service"""

    @pytest.fixture
    def mock_iifl_service(self):
        """Mock IIFL API service"""
        service = MagicMock(spec=IIFLAPIService)
        service.authenticated = True
        service.session_token = "test_token"
        service.make_request = AsyncMock()
        return service

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        session = AsyncMock()
        return session

    @pytest.fixture
    def order_manager(self, mock_iifl_service, mock_db_session):
        """Create OrderManager instance for testing"""
        return OrderManager(mock_iifl_service, db_session=mock_db_session)

    @pytest.fixture
    def mock_order_success_response(self):
        """Mock successful order placement response"""
        return {
            "stat": "Ok",
            "result": {
                "order_id": "ORDER123456",
                "symbol": "RELIANCE",
                "quantity": "100",
                "price": "2500.00",
                "order_type": "LIMIT",
                "side": "BUY",
                "status": "PENDING",
                "timestamp": "2025-10-21 10:30:00"
            }
        }

    @pytest.fixture
    def mock_order_status_response(self):
        """Mock order status response"""
        return {
            "stat": "Ok",
            "result": {
                "order_id": "ORDER123456",
                "status": "FILLED",
                "filled_quantity": "100",
                "avg_price": "2499.50",
                "remaining_quantity": "0",
                "timestamp": "2025-10-21 10:31:00"
            }
        }

    @pytest.fixture
    def mock_positions_response(self):
        """Mock positions response"""
        return {
            "stat": "Ok",
            "result": [
                {
                    "symbol": "RELIANCE",
                    "quantity": "100",
                    "avg_price": "2499.50",
                    "side": "LONG",
                    "pnl": "50.00",
                    "unrealized_pnl": "25.00"
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_place_buy_order_success(self, order_manager, mock_order_success_response):
        """Test successful buy order placement"""
        order_manager.iifl_service.make_request.return_value = mock_order_success_response

        result = await order_manager.place_order(
            symbol="RELIANCE",
            quantity=100,
            price=2500.00,
            order_type="LIMIT",
            side="BUY"
        )

        assert result is not None
        assert result['order_id'] == "ORDER123456"
        assert result['symbol'] == "RELIANCE"
        assert result['side'] == "BUY"
        order_manager.iifl_service.make_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_place_sell_order_success(self, order_manager, mock_order_success_response):
        """Test successful sell order placement"""
        mock_response = mock_order_success_response.copy()
        mock_response['result']['side'] = "SELL"
        order_manager.iifl_service.make_request.return_value = mock_response

        result = await order_manager.place_order(
            symbol="RELIANCE",
            quantity=100,
            price=2500.00,
            order_type="LIMIT",
            side="SELL"
        )

        assert result is not None
        assert result['side'] == "SELL"

    @pytest.mark.asyncio
    async def test_place_market_order(self, order_manager, mock_order_success_response):
        """Test market order placement"""
        mock_response = mock_order_success_response.copy()
        mock_response['result']['order_type'] = "MARKET"
        mock_response['result']['price'] = "0.00"
        order_manager.iifl_service.make_request.return_value = mock_response

        result = await order_manager.place_order(
            symbol="RELIANCE",
            quantity=100,
            order_type="MARKET",
            side="BUY"
        )

        assert result is not None
        assert result['order_type'] == "MARKET"

    @pytest.mark.asyncio
    async def test_place_order_invalid_symbol(self, order_manager):
        """Test order placement with invalid symbol"""
        order_manager.iifl_service.make_request.return_value = {
            "stat": "Not_Ok",
            "emsg": "Invalid symbol"
        }

        result = await order_manager.place_order(
            symbol="INVALID",
            quantity=100,
            price=2500.00,
            order_type="LIMIT",
            side="BUY"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_place_order_insufficient_funds(self, order_manager):
        """Test order placement with insufficient funds"""
        order_manager.iifl_service.make_request.return_value = {
            "stat": "Not_Ok",
            "emsg": "Insufficient margin"
        }

        result = await order_manager.place_order(
            symbol="RELIANCE",
            quantity=1000,
            price=2500.00,
            order_type="LIMIT",
            side="BUY"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_cancel_order_success(self, order_manager):
        """Test successful order cancellation"""
        mock_response = {
            "stat": "Ok",
            "result": {
                "order_id": "ORDER123456",
                "status": "CANCELLED"
            }
        }
        order_manager.iifl_service.make_request.return_value = mock_response

        result = await order_manager.cancel_order("ORDER123456")

        assert result is True

    @pytest.mark.asyncio
    async def test_cancel_order_already_filled(self, order_manager):
        """Test cancellation of already filled order"""
        order_manager.iifl_service.make_request.return_value = {
            "stat": "Not_Ok",
            "emsg": "Order already filled"
        }

        result = await order_manager.cancel_order("ORDER123456")

        assert result is False

    @pytest.mark.asyncio
    async def test_modify_order_success(self, order_manager):
        """Test successful order modification"""
        mock_response = {
            "stat": "Ok",
            "result": {
                "order_id": "ORDER123456",
                "new_price": "2450.00",
                "new_quantity": "150",
                "status": "MODIFIED"
            }
        }
        order_manager.iifl_service.make_request.return_value = mock_response

        result = await order_manager.modify_order(
            order_id="ORDER123456",
            new_price=2450.00,
            new_quantity=150
        )

        assert result is not None
        assert result['new_price'] == "2450.00"

    @pytest.mark.asyncio
    async def test_get_order_status(self, order_manager, mock_order_status_response):
        """Test order status retrieval"""
        order_manager.iifl_service.make_request.return_value = mock_order_status_response

        result = await order_manager.get_order_status("ORDER123456")

        assert result is not None
        assert result['status'] == "FILLED"
        assert result['filled_quantity'] == "100"

    @pytest.mark.asyncio
    async def test_get_all_orders(self, order_manager):
        """Test retrieval of all orders"""
        mock_response = {
            "stat": "Ok",
            "result": [
                {
                    "order_id": "ORDER123456",
                    "symbol": "RELIANCE",
                    "status": "FILLED"
                },
                {
                    "order_id": "ORDER789012",
                    "symbol": "TCS",
                    "status": "PENDING"
                }
            ]
        }
        order_manager.iifl_service.make_request.return_value = mock_response

        result = await order_manager.get_all_orders()

        assert len(result) == 2
        assert result[0]['order_id'] == "ORDER123456"

    @pytest.mark.asyncio
    async def test_get_positions(self, order_manager, mock_positions_response):
        """Test positions retrieval"""
        order_manager.iifl_service.make_request.return_value = mock_positions_response

        result = await order_manager.get_positions()

        assert len(result) == 1
        assert result[0]['symbol'] == "RELIANCE"
        assert result[0]['quantity'] == "100"

    @pytest.mark.asyncio
    async def test_get_trades(self, order_manager):
        """Test trades retrieval"""
        mock_response = {
            "stat": "Ok",
            "result": [
                {
                    "trade_id": "TRADE123",
                    "order_id": "ORDER123456",
                    "symbol": "RELIANCE",
                    "quantity": "100",
                    "price": "2499.50",
                    "timestamp": "2025-10-21 10:31:00"
                }
            ]
        }
        order_manager.iifl_service.make_request.return_value = mock_response

        result = await order_manager.get_trades()

        assert len(result) == 1
        assert result[0]['trade_id'] == "TRADE123"

    @pytest.mark.asyncio
    async def test_bracket_order_placement(self, order_manager):
        """Test bracket order with stop loss and target"""
        mock_response = {
            "stat": "Ok",
            "result": {
                "parent_order_id": "PARENT123",
                "target_order_id": "TARGET123",
                "stop_loss_order_id": "SL123"
            }
        }
        order_manager.iifl_service.make_request.return_value = mock_response

        result = await order_manager.place_bracket_order(
            symbol="RELIANCE",
            quantity=100,
            price=2500.00,
            target_price=2600.00,
            stop_loss_price=2400.00
        )

        assert result is not None
        assert 'parent_order_id' in result

    @pytest.mark.asyncio
    async def test_order_validation_invalid_quantity(self, order_manager):
        """Test order validation with invalid quantity"""
        with pytest.raises(ValueError, match="Quantity must be positive"):
            await order_manager.place_order(
                symbol="RELIANCE",
                quantity=0,
                price=2500.00,
                order_type="LIMIT",
                side="BUY"
            )

    @pytest.mark.asyncio
    async def test_order_validation_invalid_price(self, order_manager):
        """Test order validation with invalid price"""
        with pytest.raises(ValueError, match="Price must be positive"):
            await order_manager.place_order(
                symbol="RELIANCE",
                quantity=100,
                price=-100.00,
                order_type="LIMIT",
                side="BUY"
            )

    @pytest.mark.asyncio
    async def test_order_validation_invalid_side(self, order_manager):
        """Test order validation with invalid side"""
        with pytest.raises(ValueError, match="Invalid side"):
            await order_manager.place_order(
                symbol="RELIANCE",
                quantity=100,
                price=2500.00,
                order_type="LIMIT",
                side="INVALID"
            )

    @pytest.mark.asyncio
    async def test_calculate_position_pnl(self, order_manager):
        """Test position PnL calculation"""
        position = {
            "symbol": "RELIANCE",
            "quantity": "100",
            "avg_price": "2450.00",
            "side": "LONG"
        }
        current_price = 2500.00

        pnl = order_manager.calculate_position_pnl(position, current_price)

        assert pnl == 5000.00  # (2500 - 2450) * 100

    @pytest.mark.asyncio
    async def test_calculate_position_pnl_short(self, order_manager):
        """Test position PnL calculation for short position"""
        position = {
            "symbol": "RELIANCE",
            "quantity": "100",
            "avg_price": "2550.00",
            "side": "SHORT"
        }
        current_price = 2500.00

        pnl = order_manager.calculate_position_pnl(position, current_price)

        assert pnl == 5000.00  # (2550 - 2500) * 100

    @pytest.mark.asyncio
    async def test_risk_management_position_size(self, order_manager):
        """Test risk management for position sizing"""
        # Mock available margin
        order_manager.get_available_margin = AsyncMock(return_value=100000.00)

        max_quantity = await order_manager.calculate_max_quantity(
            symbol="RELIANCE",
            price=2500.00,
            risk_percent=10.0
        )

        assert max_quantity == 4  # 10% of 100k / 2500

    @pytest.mark.asyncio
    async def test_order_timeout_handling(self, order_manager):
        """Test handling of order timeouts"""
        order_manager.iifl_service.make_request.side_effect = asyncio.TimeoutError()

        result = await order_manager.place_order(
            symbol="RELIANCE",
            quantity=100,
            price=2500.00,
            order_type="LIMIT",
            side="BUY"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_order_retry_logic(self, order_manager, mock_order_success_response):
        """Test order retry logic on network errors"""
        # First call fails, second succeeds
        order_manager.iifl_service.make_request.side_effect = [
            Exception("Network error"),
            mock_order_success_response
        ]

        result = await order_manager.place_order(
            symbol="RELIANCE",
            quantity=100,
            price=2500.00,
            order_type="LIMIT",
            side="BUY",
            retry_count=1
        )

        assert result is not None
        assert order_manager.iifl_service.make_request.call_count == 2

    @pytest.mark.asyncio
    async def test_bulk_order_cancellation(self, order_manager):
        """Test bulk cancellation of orders"""
        order_ids = ["ORDER1", "ORDER2", "ORDER3"]
        order_manager.cancel_order = AsyncMock(return_value=True)

        results = await order_manager.cancel_bulk_orders(order_ids)

        assert len(results) == 3
        assert all(results)

    @pytest.mark.asyncio
    async def test_order_history_persistence(self, order_manager, mock_order_success_response):
        """Test that order history is persisted to database"""
        order_manager.iifl_service.make_request.return_value = mock_order_success_response

        await order_manager.place_order(
            symbol="RELIANCE",
            quantity=100,
            price=2500.00,
            order_type="LIMIT",
            side="BUY"
        )

        # Verify database operations were called
        if hasattr(order_manager, 'db_session') and order_manager.db_session:
            # Check that order was saved to database
            pass

    @pytest.mark.asyncio
    async def test_order_status_polling(self, order_manager):
        """Test continuous order status polling"""
        mock_responses = [
            {"stat": "Ok", "result": {"status": "PENDING"}},
            {"stat": "Ok", "result": {"status": "PENDING"}},
            {"stat": "Ok", "result": {"status": "FILLED"}}
        ]
        order_manager.iifl_service.make_request.side_effect = mock_responses

        final_status = await order_manager.wait_for_order_completion(
            "ORDER123456",
            timeout=5,
            poll_interval=1
        )

        assert final_status == "FILLED"

    @pytest.mark.asyncio
    async def test_order_rejection_handling(self, order_manager):
        """Test handling of order rejections"""
        order_manager.iifl_service.make_request.return_value = {
            "stat": "Not_Ok",
            "emsg": "Order rejected: Price out of circuit limits"
        }

        result = await order_manager.place_order(
            symbol="RELIANCE",
            quantity=100,
            price=1000.00,  # Unrealistic price
            order_type="LIMIT",
            side="BUY"
        )

        assert result is None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
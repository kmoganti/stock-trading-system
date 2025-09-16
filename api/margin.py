"""
Margin calculation API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, Literal
import logging

from services.data_fetcher import DataFetcher
from services.iifl_api import IIFLAPIService

logger = logging.getLogger(__name__)
router = APIRouter()

class MarginCalculationRequest(BaseModel):
    symbol: str
    quantity: int 
    transaction_type: Literal["BUY", "SELL"]
    price: Optional[float] = None
    product: Literal["NORMAL", "INTRADAY", "DELIVERY", "BNPL"] = "NORMAL"
    exchange: Literal["NSEEQ", "NSEFO", "BSEEQ"] = "NSEEQ"
    order_type: Literal["MARKET", "LIMIT", "SL", "SLM"] = "MARKET"

    @model_validator(mode='after')
    def price_required_for_limit_and_sl_orders(self):
        """Ensure price is provided for order types that require it."""
        if self.order_type in ("LIMIT", "SL") and self.price is None:
            raise ValueError("Price is required for LIMIT and SL order types.")
        if self.order_type == "MARKET" and self.price is not None:
            # This is a warning, not an error, as it's not critical but good to know.
            logger.warning("Price is provided for a MARKET order but will be ignored by the broker.")
        return self

    @field_validator('quantity')
    def quantity_must_be_positive(cls, v):
        """Ensure quantity is a positive integer."""
        if v <= 0:
            raise ValueError('Quantity must be a positive integer.')
        return v


async def get_data_fetcher():
    """Dependency to get DataFetcher instance"""
    iifl_service = IIFLAPIService()
    return DataFetcher(iifl_service)

@router.post("/calculate")
async def calculate_margin(
    request: MarginCalculationRequest,
    data_fetcher: DataFetcher = Depends(get_data_fetcher)
):
    """Calculate pre-order margin requirement for a trade"""
    try:
        margin_info = await data_fetcher.calculate_required_margin(
            symbol=request.symbol,
            quantity=request.quantity,
            transaction_type=request.transaction_type,
            price=request.price,
            product=request.product,
            exchange=request.exchange
        )
        
        if margin_info:
            return {
                "success": True,
                "data": margin_info
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="Failed to calculate margin. Check symbol and parameters."
            )
            
    except Exception as e:
        logger.error(f"Error in margin calculation endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/info")
async def get_margin_info(data_fetcher: DataFetcher = Depends(get_data_fetcher)):
    """Get current margin information"""
    try:
        margin_info = await data_fetcher.get_margin_info()
        
        if margin_info:
            return {
                "success": True,
                "data": margin_info
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="Failed to fetch margin information"
            )
            
    except Exception as e:
        logger.error(f"Error in margin info endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

"""
Margin calculation API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import logging

from services.data_fetcher import DataFetcher
from services.iifl_api import IIFLAPIService

logger = logging.getLogger(__name__)
router = APIRouter()

class MarginCalculationRequest(BaseModel):
    symbol: str
    quantity: int
    transaction_type: str  # BUY or SELL
    price: Optional[float] = None
    product: str = "NORMAL"  # NORMAL, INTRADAY, DELIVERY, BNPL
    exchange: str = "NSEEQ"  # NSEEQ, NSEFO, BSEEQ, etc.
    order_type: str = "MARKET"  # MARKET, LIMIT, SL, SLM

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

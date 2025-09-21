from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List
import logging
from datetime import date, datetime
import os
from models.database import get_db
from models.pnl_reports import PnLReport
from services.report import ReportService
from services.logging_service import trading_logger
from services.pnl import PnLService
from services.data_fetcher import DataFetcher
from services.iifl_api import IIFLAPIService
from config.settings import get_settings

router = APIRouter(prefix="/api/reports", tags=["reports"])
logger = logging.getLogger(__name__)

async def get_pnl_service(db: AsyncSession = Depends(get_db)) -> PnLService:
    """Dependency to get PnLService instance"""
    iifl = IIFLAPIService()
    data_fetcher = DataFetcher(iifl, db_session=db)
    return PnLService(data_fetcher, db)

async def get_report_service(db: AsyncSession = Depends(get_db)) -> ReportService:
    """Dependency to get ReportService instance"""
    iifl = IIFLAPIService()
    data_fetcher = DataFetcher(iifl, db_session=db)
    pnl_service = PnLService(data_fetcher, db)
    return ReportService(pnl_service, data_fetcher)

@router.get("/list")
async def list_generated_reports() -> List[Dict[str, str]]:
    """List recently generated PDF reports."""
    reports_dir = "reports"
    try:
        if not os.path.exists(reports_dir):
            return []
        
        # List files and sort by modification time to get the most recent first
        report_files = sorted(
            (os.path.join(reports_dir, f) for f in os.listdir(reports_dir) if f.endswith(".pdf")),
            key=os.path.getmtime,
            reverse=True
        )
        
        reports_list = []
        for file_path in report_files[:20]: # Limit to 20 most recent
            try:
                filename = os.path.basename(file_path)
                # Extract date from filename like daily_report_YYYYMMDD.pdf
                date_str = filename.replace("daily_report_", "").replace(".pdf", "")
                report_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
                reports_list.append({
                    "filename": filename,
                    "date": report_date,
                    "url": f"/reports/{filename}"
                })
            except (ValueError, IndexError):
                continue # Skip files with unexpected names
        return reports_list
    except Exception as e:
        logger.error(f"Error listing reports: {str(e)}")
        return []


@router.get("/pnl/daily")
async def get_daily_pnl(
    report_date: str = None,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get daily PnL report"""
    logger.info(f"Request for daily PnL report for date: {report_date or 'today'}")
    try:
        from sqlalchemy import select
        
        if report_date:
            target_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        else:
            target_date = date.today()
        
        stmt = select(PnLReport).where(PnLReport.date == target_date)
        result = await db.execute(stmt)
        report = result.scalar_one_or_none()
        
        if report:
            response = report.to_dict()
            logger.info(f"Found daily PnL report for {target_date}")
            return response
        else:
            response = {
                "date": target_date.isoformat(),
                "daily_pnl": 0.0,
                "cumulative_pnl": 0.0,
                "message": "No report found for this date"
            }
            logger.warning(f"No daily PnL report found for {target_date}")
            return response
        
    except Exception as e:
        logger.error(f"Error getting daily PnL: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pnl/summary")
async def get_pnl_summary(
    days: int = 30,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get PnL summary for specified period"""
    logger.info(f"Request for PnL summary for last {days} days.")
    try:
        from sqlalchemy import select, func
        from datetime import timedelta
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        stmt = select(PnLReport).where(
            PnLReport.date >= start_date,
            PnLReport.date <= end_date
        ).order_by(PnLReport.date.desc())
        
        result = await db.execute(stmt)
        reports = result.scalars().all()
        
        if not reports:
            response = {
                "period": f"{start_date} to {end_date}",
                "total_pnl": 0.0,
                "reports": []
            }
            logger.warning(f"No PnL reports found for the last {days} days.")
            return response
        
        total_pnl = sum(report.daily_pnl for report in reports)
        
        response = {
            "period": f"{start_date} to {end_date}",
            "total_pnl": total_pnl,
            "reports_count": len(reports),
            "reports": [report.to_dict() for report in reports]
        }
        logger.info(f"Returning PnL summary with {len(reports)} reports.")
        return response
        
    except Exception as e:
        logger.error(f"Error getting PnL summary: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/eod/{report_date}")
async def download_eod_report(
    report_date: str,
    report_service: ReportService = Depends(get_report_service)
) -> FileResponse:
    """Download end-of-day PDF report"""
    logger.info(f"Request to download EOD report for {report_date}")
    try:
        target_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        # Generate PDF report
        pdf_path = await report_service.generate_pdf_report(target_date)
        
        if not os.path.exists(pdf_path):
            raise HTTPException(status_code=404, detail="Report file not found")
        
        return FileResponse(
            path=pdf_path,
            filename=f"daily_report_{report_date}.pdf",
            media_type="application/pdf"
        )
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Error downloading EOD report: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/eod/generate")
async def generate_eod_report(
    report_date: str = None,
    db: AsyncSession = Depends(get_db),
    report_service: ReportService = Depends(get_report_service)
) -> Dict[str, Any]:
    """Generate end-of-day report on demand"""
    logger.info(f"Request to generate EOD report for {report_date or 'today'}")
    try:
        if report_date:
            target_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        else:
            target_date = date.today()
        
        # Generate comprehensive daily report
        trading_logger.main_logger.info(
            f"SYSTEM: Generating EOD report", 
        )
        report_data = await report_service.generate_daily_report(target_date)
        
        if "error" in report_data:
            err_msg = report_data["error"]
            trading_logger.log_error(
                component="reports",
                error=Exception(err_msg),
                context={"stage": "generate_daily_report", "target_date": target_date.isoformat()}
            )
            raise HTTPException(status_code=500, detail=err_msg)
        
        # Generate PDF report
        pdf_path = await report_service.generate_pdf_report(target_date)
        
        logger.info(f"EOD report generated for {target_date}: {pdf_path}")
        trading_logger.main_logger.info(
            f"SYSTEM: EOD report generated for {target_date} -> {pdf_path}"
        )
        
        return {
            "message": f"EOD report generated successfully for {target_date}",
            "status": "completed",
            "pdf_path": pdf_path,
            "report_data": report_data
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Error generating EOD report: {str(e)}", exc_info=True)
        try:
            trading_logger.log_error(
                component="reports",
                error=e,
                context={
                    "endpoint": "/api/reports/eod/generate",
                    "report_date": report_date,
                }
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/weekly")
async def get_weekly_summary(
    report_service: ReportService = Depends(get_report_service)
) -> Dict[str, Any]:
    """Get weekly performance summary"""
    logger.info("Request for weekly performance summary.")
    try:
        weekly_data = await report_service.generate_weekly_summary()
        
        if "error" in weekly_data:
            raise HTTPException(status_code=500, detail=weekly_data["error"])
        
        logger.info("Successfully generated weekly summary.")
        return weekly_data
        
    except Exception as e:
        logger.error(f"Error getting weekly summary: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/monthly")
async def get_monthly_analysis(
    report_service: ReportService = Depends(get_report_service)
) -> Dict[str, Any]:
    """Get comprehensive monthly analysis"""
    logger.info("Request for monthly analysis.")
    try:
        monthly_data = await report_service.generate_monthly_analysis()
        
        if "error" in monthly_data:
            raise HTTPException(status_code=500, detail=monthly_data["error"])
        
        logger.info("Successfully generated monthly analysis.")
        return monthly_data
        
    except Exception as e:
        logger.error(f"Error getting monthly analysis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance/metrics")
async def get_performance_metrics(
    days: int = 30,
    pnl_service: PnLService = Depends(get_pnl_service)
) -> Dict[str, Any]:
    """Get performance metrics for specified period"""
    logger.info(f"Request for performance metrics for last {days} days.")
    try:
        metrics = await pnl_service.calculate_performance_metrics(days)
        
        if "error" in metrics:
            raise HTTPException(status_code=500, detail=metrics["error"])
        
        response = {
            "period_days": days,
            "metrics": metrics,
            "generated_at": datetime.now().isoformat()
        }
        logger.info("Successfully calculated performance metrics.")
        return response
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

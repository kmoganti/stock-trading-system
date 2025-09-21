import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
import logging
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.piecharts import Pie
import io
import base64
import os

# Optional matplotlib import
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
from .pnl import PnLService
from .data_fetcher import DataFetcher

logger = logging.getLogger(__name__)

class ReportService:
    """Service for generating trading reports and analytics"""
    
    def __init__(self, pnl_service: PnLService, data_fetcher: DataFetcher):
        self.pnl_service = pnl_service
        self.data_fetcher = data_fetcher
        self.styles = getSampleStyleSheet()
    
    async def generate_daily_report(self, report_date: Optional[date] = None) -> Dict[str, Any]:
        """Generate comprehensive daily trading report"""
        if report_date is None:
            report_date = date.today()
        
        try:
            # Collect all data
            daily_pnl = await self.pnl_service.get_daily_report(report_date)
            portfolio_data = await self.data_fetcher.get_portfolio_data()
            performance_metrics = await self.pnl_service.calculate_performance_metrics(30)
            
            # Generate charts
            equity_chart = await self._generate_equity_chart()
            pnl_chart = await self._generate_pnl_chart()
            
            report_data = {
                "date": report_date.isoformat(),
                "daily_pnl": daily_pnl,
                "portfolio": portfolio_data,
                "performance_metrics": performance_metrics,
                "charts": {
                    "equity_curve": equity_chart,
                    "pnl_distribution": pnl_chart
                },
                "generated_at": datetime.now().isoformat()
            }
            
            return report_data
            
        except Exception as e:
            logger.error(f"Error generating daily report: {str(e)}")
            return {"error": str(e)}
    
    async def generate_pdf_report(self, report_date: Optional[date] = None, 
                                 output_path: Optional[str] = None) -> str:
        """Generate PDF report"""
        if report_date is None:
            report_date = date.today()
        
        if output_path is None:
            output_path = f"reports/daily_report_{report_date.strftime('%Y%m%d')}.pdf"
        
        try:
            # Ensure output directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # Get report data
            report_data = await self.generate_daily_report(report_date)
            
            if "error" in report_data:
                raise Exception(report_data["error"])
            
            # Create PDF
            doc = SimpleDocTemplate(output_path, pagesize=A4)
            story = []
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=self.styles['Heading1'],
                fontSize=24,
                spaceAfter=30,
                alignment=1  # Center alignment
            )
            
            story.append(Paragraph(f"Daily Trading Report - {report_date.strftime('%B %d, %Y')}", title_style))
            story.append(Spacer(1, 20))
            
            # Executive Summary
            story.append(Paragraph("Executive Summary", self.styles['Heading2']))
            
            daily_pnl_data = report_data.get("daily_pnl", {})
            summary_data = [
                ["Metric", "Value"],
                ["Daily P&L", f"₹{daily_pnl_data.get('daily_pnl', 0):,.2f}"],
                ["Cumulative P&L", f"₹{daily_pnl_data.get('cumulative_pnl', 0):,.2f}"],
                ["Total Trades", str(daily_pnl_data.get('total_trades', 0))],
                ["Win Rate", f"{daily_pnl_data.get('win_rate', 0):.1%}"],
                ["Max Drawdown", f"{daily_pnl_data.get('max_drawdown', 0):.2%}"]
            ]
            
            summary_table = Table(summary_data, colWidths=[2*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 14),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(summary_table)
            story.append(Spacer(1, 20))
            
            # Portfolio Positions
            story.append(Paragraph("Current Positions", self.styles['Heading2']))
            
            portfolio = report_data.get("portfolio", {})
            positions = portfolio.get("positions", [])
            
            if positions:
                position_data = [["Symbol", "Quantity", "P&L", "P&L %"]]
                
                for pos in positions[:10]:  # Limit to top 10 positions
                    position_data.append([
                        pos.get("symbol", "N/A"),
                        str(pos.get("quantity", 0)),
                        f"₹{pos.get('pnl', 0):,.2f}",
                        f"{pos.get('pnl_percent', 0):.2f}%"
                    ])
                
                position_table = Table(position_data, colWidths=[1.5*inch, 1*inch, 1.5*inch, 1*inch])
                position_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(position_table)
            else:
                story.append(Paragraph("No open positions", self.styles['Normal']))
            
            story.append(Spacer(1, 20))
            
            # Performance Metrics
            story.append(Paragraph("Performance Metrics (30 Days)", self.styles['Heading2']))
            
            metrics = report_data.get("performance_metrics", {})
            if not metrics.get("error"):
                metrics_data = [
                    ["Metric", "Value"],
                    ["Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0):.2f}"],
                    ["Sortino Ratio", f"{metrics.get('sortino_ratio', 0):.2f}"],
                    ["Calmar Ratio", f"{metrics.get('calmar_ratio', 0):.2f}"],
                    ["Volatility", f"{metrics.get('volatility', 0):.2%}"],
                    ["Profit Factor", f"{metrics.get('profit_factor', 0):.2f}"]
                ]
                
                metrics_table = Table(metrics_data, colWidths=[2*inch, 2*inch])
                metrics_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(metrics_table)
            else:
                story.append(Paragraph("Performance metrics unavailable", self.styles['Normal']))
            
            # Footer
            story.append(Spacer(1, 30))
            footer_style = ParagraphStyle(
                'Footer',
                parent=self.styles['Normal'],
                fontSize=10,
                alignment=1
            )
            story.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", footer_style))
            story.append(Paragraph("Stock Trading System - Automated Report", footer_style))
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"PDF report generated: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error generating PDF report: {str(e)}")
            raise
    
    async def _generate_equity_chart(self) -> str:
        """Generate equity curve chart as base64 image"""
        try:
            if not HAS_MATPLOTLIB:
                logger.warning("Matplotlib not available, skipping chart generation")
                return ""
            
            equity_data = await self.pnl_service.get_equity_curve(30)
            
            if not equity_data:
                return ""
            
            # Create matplotlib chart
            fig, ax = plt.subplots(figsize=(10, 6))
            
            dates = [datetime.fromisoformat(item["date"]) for item in equity_data]
            equity_values = [item["equity"] for item in equity_data]
            
            ax.plot(dates, equity_values, linewidth=2, color='#4F46E5')
            ax.set_title('Equity Curve (30 Days)', fontsize=16, fontweight='bold')
            ax.set_xlabel('Date', fontsize=12)
            ax.set_ylabel('Equity (₹)', fontsize=12)
            ax.grid(True, alpha=0.3)
            
            # Format dates on x-axis
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
            plt.xticks(rotation=45)
            
            # Format y-axis for currency
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'₹{x:,.0f}'))
            
            plt.tight_layout()
            
            # Convert to base64
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
            buffer.seek(0)
            
            chart_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
            
            return chart_base64
            
        except Exception as e:
            logger.error(f"Error generating equity chart: {str(e)}")
            return ""
    
    async def _generate_pnl_chart(self) -> str:
        """Generate P&L distribution chart as base64 image"""
        try:
            if not HAS_MATPLOTLIB:
                logger.warning("Matplotlib not available, skipping chart generation")
                return ""
            
            # Get recent P&L data
            end_date = date.today()
            start_date = end_date - timedelta(days=30)
            period_summary = await self.pnl_service.get_period_summary(start_date, end_date)
            
            reports = period_summary.get("reports", [])
            if not reports:
                return ""
            
            # Create histogram of daily P&L
            daily_pnls = [report["daily_pnl"] for report in reports]
            
            fig, ax = plt.subplots(figsize=(10, 6))
            
            ax.hist(daily_pnls, bins=20, alpha=0.7, color='#10B981', edgecolor='black')
            ax.set_title('Daily P&L Distribution (30 Days)', fontsize=16, fontweight='bold')
            ax.set_xlabel('Daily P&L (₹)', fontsize=12)
            ax.set_ylabel('Frequency', fontsize=12)
            ax.grid(True, alpha=0.3)
            
            # Add vertical line at zero
            ax.axvline(x=0, color='red', linestyle='--', alpha=0.7)
            
            # Format x-axis for currency
            ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'₹{x:,.0f}'))
            
            plt.tight_layout()
            
            # Convert to base64
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
            buffer.seek(0)
            
            chart_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
            
            return chart_base64
            
        except Exception as e:
            logger.error(f"Error generating P&L chart: {str(e)}")
            return ""
    
    async def generate_weekly_summary(self) -> Dict[str, Any]:
        """Generate weekly performance summary"""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=7)
            
            weekly_data = await self.pnl_service.get_period_summary(start_date, end_date)
            
            # Add additional weekly insights
            reports = weekly_data.get("reports", [])
            
            if reports:
                # Best and worst days
                best_day = max(reports, key=lambda x: x["daily_pnl"])
                worst_day = min(reports, key=lambda x: x["daily_pnl"])
                
                weekly_data.update({
                    "best_day": {
                        "date": best_day["date"],
                        "pnl": best_day["daily_pnl"]
                    },
                    "worst_day": {
                        "date": worst_day["date"],
                        "pnl": worst_day["daily_pnl"]
                    },
                    "consistency_score": self._calculate_consistency_score(reports)
                })
            
            return weekly_data
            
        except Exception as e:
            logger.error(f"Error generating weekly summary: {str(e)}")
            return {"error": str(e)}
    
    async def generate_monthly_analysis(self) -> Dict[str, Any]:
        """Generate comprehensive monthly analysis"""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=30)
            
            monthly_data = await self.pnl_service.get_period_summary(start_date, end_date)
            performance_metrics = await self.pnl_service.calculate_performance_metrics(30)
            
            # Combine data
            analysis = {
                **monthly_data,
                "performance_metrics": performance_metrics,
                "analysis_date": end_date.isoformat(),
                "recommendations": await self._generate_recommendations(monthly_data, performance_metrics)
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error generating monthly analysis: {str(e)}")
            return {"error": str(e)}
    
    def _calculate_consistency_score(self, reports: List[Dict]) -> float:
        """Calculate trading consistency score (0-100)"""
        try:
            if not reports:
                return 0
            
            daily_pnls = [report["daily_pnl"] for report in reports]
            
            # Calculate coefficient of variation (lower is more consistent)
            import numpy as np
            
            mean_pnl = np.mean(daily_pnls)
            std_pnl = np.std(daily_pnls)
            
            if mean_pnl == 0:
                return 0
            
            cv = abs(std_pnl / mean_pnl)
            
            # Convert to 0-100 score (lower CV = higher consistency)
            consistency_score = max(0, 100 - (cv * 100))
            
            return consistency_score
            
        except Exception as e:
            logger.error(f"Error calculating consistency score: {str(e)}")
            return 0
    
    async def _generate_recommendations(self, monthly_data: Dict, 
                                      performance_metrics: Dict) -> List[str]:
        """Generate trading recommendations based on performance"""
        recommendations = []
        
        try:
            # Win rate analysis
            win_rate = monthly_data.get("win_rate", 0)
            if win_rate < 0.5:
                recommendations.append("Consider reviewing entry criteria - win rate below 50%")
            elif win_rate > 0.7:
                recommendations.append("Excellent win rate - consider increasing position sizes")
            
            # Sharpe ratio analysis
            sharpe = performance_metrics.get("sharpe_ratio", 0)
            if sharpe < 1.0:
                recommendations.append("Risk-adjusted returns could be improved - review risk management")
            elif sharpe > 2.0:
                recommendations.append("Outstanding risk-adjusted returns - maintain current strategy")
            
            # Drawdown analysis
            max_dd = performance_metrics.get("max_drawdown", 0)
            if max_dd > 0.15:
                recommendations.append("High drawdown detected - consider tighter stop losses")
            
            # Trading frequency
            total_trades = monthly_data.get("total_trades", 0)
            if total_trades < 10:
                recommendations.append("Low trading frequency - consider expanding watchlist")
            elif total_trades > 100:
                recommendations.append("High trading frequency - ensure quality over quantity")
            
            # Profit factor
            profit_factor = performance_metrics.get("profit_factor", 0)
            if profit_factor < 1.5:
                recommendations.append("Profit factor could be improved - review exit strategies")
            
            if not recommendations:
                recommendations.append("Performance metrics look good - continue current approach")
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            recommendations.append("Unable to generate recommendations due to data issues")
        
        return recommendations

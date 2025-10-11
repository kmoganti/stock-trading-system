#!/usr/bin/env python3
"""
Log analyzer for trading system critical events and performance monitoring.
"""
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Any
import pandas as pd

class LogAnalyzer:
    """Analyzer for trading system logs with focus on critical events."""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.events = []
        
    def load_critical_events(self, hours_back: int = 24) -> List[Dict]:
        """Load critical events from the last N hours."""
        critical_log_file = self.log_dir / "critical_events.log"
        
        if not critical_log_file.exists():
            print(f"❌ Critical events log not found: {critical_log_file}")
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        events = []
        
        with open(critical_log_file, 'r') as f:
            for line_no, line in enumerate(f, 1):
                try:
                    event = json.loads(line.strip())
                    event_time = datetime.fromisoformat(event['timestamp'])
                    
                    if event_time >= cutoff_time:
                        event['line_number'] = line_no
                        events.append(event)
                        
                except (json.JSONDecodeError, ValueError, KeyError) as e:
                    print(f"⚠️  Skipping malformed log line {line_no}: {e}")
        
        self.events = sorted(events, key=lambda x: x['timestamp'])
        print(f"📊 Loaded {len(events)} events from last {hours_back} hours")
        return self.events
    
    def analyze_trading_performance(self) -> Dict[str, Any]:
        """Analyze trading performance from logged events."""
        analysis = {
            'summary': {},
            'orders': {},
            'signals': {},
            'pnl': {},
            'risks': {}
        }
        
        order_events = [e for e in self.events if e.get('event_type') == 'order_execution' or e.get('extra_data', {}).get('event_type') == 'order_execution']
        signal_events = [e for e in self.events if e.get('event_type') == 'signal_generation' or e.get('extra_data', {}).get('event_type') == 'signal_generation']
        pnl_events = [e for e in self.events if e.get('event_type') == 'pnl_update' or e.get('extra_data', {}).get('event_type') == 'pnl_update']
        risk_events = [e for e in self.events if e.get('event_type') == 'risk_violation' or e.get('extra_data', {}).get('event_type') == 'risk_violation']
        
        # Order Analysis
        if order_events:
            order_statuses = Counter([e.get('status') or e.get('extra_data', {}).get('status') for e in order_events if e.get('status') or e.get('extra_data', {}).get('status')])
            order_symbols = Counter([e.get('symbol') or e.get('extra_data', {}).get('symbol') for e in order_events if e.get('symbol') or e.get('extra_data', {}).get('symbol')])
            total_volume = sum([e.get('amount', 0) or e.get('extra_data', {}).get('amount', 0) for e in order_events])
            
            analysis['orders'] = {
                'total_orders': len(order_events),
                'order_statuses': dict(order_statuses),
                'top_symbols': dict(order_symbols.most_common(5)),
                'total_volume': total_volume,
                'avg_order_size': total_volume / len(order_events) if order_events else 0
            }
        
        # Signal Analysis  
        if signal_events:
            signal_types = Counter([e.get('signal_type') or e.get('extra_data', {}).get('signal_type') for e in signal_events if e.get('signal_type') or e.get('extra_data', {}).get('signal_type')])
            strategies = Counter([e.get('strategy') or e.get('extra_data', {}).get('strategy') for e in signal_events if e.get('strategy') or e.get('extra_data', {}).get('strategy')])
            confidences = [e.get('confidence') or e.get('extra_data', {}).get('confidence', 0) for e in signal_events if (e.get('confidence') is not None) or (e.get('extra_data', {}).get('confidence') is not None)]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            analysis['signals'] = {
                'total_signals': len(signal_events),
                'signal_types': dict(signal_types),
                'strategies': dict(strategies),
                'avg_confidence': avg_confidence
            }
        
        # P&L Analysis
        if pnl_events:
            latest_event = pnl_events[-1]
            latest_pnl = latest_event.get('extra_data') or latest_event
            daily_pnls = [e.get('daily_pnl') or e.get('extra_data', {}).get('daily_pnl', 0) for e in pnl_events]
            
            analysis['pnl'] = {
                'current_cumulative_pnl': latest_pnl.get('cumulative_pnl', 0),
                'latest_daily_pnl': latest_pnl.get('daily_pnl', 0),
                'total_trades': latest_pnl.get('total_trades', 0),
                'daily_pnl_trend': [x for x in daily_pnls[-7:] if x] if len(daily_pnls) >= 7 else [x for x in daily_pnls if x]
            }
        
        # Risk Analysis
        if risk_events:
            risk_types = Counter([e.get('violation_type') or e.get('extra_data', {}).get('violation_type') for e in risk_events if e.get('violation_type') or e.get('extra_data', {}).get('violation_type')])
            risk_severities = Counter([e.get('severity') or e.get('extra_data', {}).get('severity') for e in risk_events if e.get('severity') or e.get('extra_data', {}).get('severity')])
            
            analysis['risks'] = {
                'total_violations': len(risk_events),
                'violation_types': dict(risk_types),
                'severities': dict(risk_severities)
            }
        
        # Summary
        analysis['summary'] = {
            'total_events': len(self.events),
            'time_range': f"{self.events[0]['timestamp']} to {self.events[-1]['timestamp']}" if self.events else "No events",
            'orders_executed': len(order_events),
            'signals_generated': len(signal_events),
            'risk_violations': len(risk_events),
            'pnl_updates': len(pnl_events)
        }
        
        return analysis
    
    def analyze_system_performance(self) -> Dict[str, Any]:
        """Analyze system performance metrics from logs."""
        performance_events = [e for e in self.events 
                            if e.get('event_type') == 'performance_metric' or e.get('extra_data', {}).get('event_type') == 'performance_metric']
        operation_events = [e for e in self.events 
                          if e.get('event_type') in ['operation_start', 'operation_complete', 'operation_failed'] or
                          e.get('extra_data', {}).get('event_type') in ['operation_start', 'operation_complete', 'operation_failed']]
        
        analysis = {
            'operations': {},
            'metrics': {},
            'errors': {}
        }
        
        # Operation Performance
        operations = defaultdict(list)
        failed_operations = []
        
        for event in operation_events:
            data = event.get('extra_data') or event
            event_type = data.get('event_type')
            operation = data.get('operation')
            
            if event_type == 'operation_complete' and operation:
                duration = data.get('duration_seconds')
                if duration is not None:
                    operations[operation].append(duration)
            elif event_type == 'operation_failed' and operation:
                failed_operations.append({
                    'operation': operation,
                    'error': data.get('error', 'Unknown'),
                    'duration': data.get('duration_seconds', 0)
                })
        
        # Calculate operation stats
        operation_stats = {}
        for op, durations in operations.items():
            operation_stats[op] = {
                'count': len(durations),
                'avg_duration': sum(durations) / len(durations),
                'min_duration': min(durations),
                'max_duration': max(durations)
            }
        
        analysis['operations'] = {
            'stats': operation_stats,
            'failed_operations': failed_operations,
            'total_operations': sum(len(durations) for durations in operations.values()),
            'failure_rate': len(failed_operations) / (sum(len(durations) for durations in operations.values()) + len(failed_operations)) if operations or failed_operations else 0
        }
        
        # Performance Metrics
        metrics = defaultdict(list)
        for event in performance_events:
            data = event.get('extra_data') or event
            metric_name = data.get('metric_name')
            value = data.get('value')
            if metric_name and value is not None:
                metrics[metric_name].append(value)
        
        metric_stats = {}
        for metric, values in metrics.items():
            metric_stats[metric] = {
                'count': len(values),
                'avg': sum(values) / len(values),
                'min': min(values),
                'max': max(values),
                'latest': values[-1]
            }
        
        analysis['metrics'] = metric_stats
        
        return analysis
    
    def generate_report(self, hours_back: int = 24) -> str:
        """Generate comprehensive analysis report."""
        self.load_critical_events(hours_back)
        
        if not self.events:
            return "📋 No critical events found in the specified time period."
        
        trading_analysis = self.analyze_trading_performance()
        system_analysis = self.analyze_system_performance()
        
        report = []
        report.append("🔍 TRADING SYSTEM LOG ANALYSIS REPORT")
        report.append("=" * 50)
        report.append("")
        
        # Summary
        summary = trading_analysis['summary']
        report.append("📊 SUMMARY")
        report.append("-" * 20)
        report.append(f"Time Range: {summary['time_range']}")
        report.append(f"Total Events: {summary['total_events']}")
        report.append(f"Orders Executed: {summary['orders_executed']}")
        report.append(f"Signals Generated: {summary['signals_generated']}")
        report.append(f"Risk Violations: {summary['risk_violations']}")
        report.append("")
        
        # Trading Performance
        if trading_analysis['orders']:
            orders = trading_analysis['orders']
            report.append("📈 TRADING PERFORMANCE")
            report.append("-" * 25)
            report.append(f"Total Orders: {orders['total_orders']}")
            report.append(f"Total Volume: ₹{orders['total_volume']:,.2f}")
            report.append(f"Average Order Size: ₹{orders['avg_order_size']:,.2f}")
            report.append(f"Order Status Distribution: {orders['order_statuses']}")
            report.append(f"Top Trading Symbols: {orders['top_symbols']}")
            report.append("")
        
        # P&L Analysis
        if trading_analysis['pnl']:
            pnl = trading_analysis['pnl']
            report.append("💰 P&L ANALYSIS")
            report.append("-" * 18)
            report.append(f"Current Cumulative P&L: ₹{pnl['current_cumulative_pnl']:,.2f}")
            report.append(f"Latest Daily P&L: ₹{pnl['latest_daily_pnl']:,.2f}")
            report.append(f"Total Trades: {pnl['total_trades']}")
            report.append("")
        
        # Signal Analysis
        if trading_analysis['signals']:
            signals = trading_analysis['signals']
            report.append("🎯 SIGNAL ANALYSIS")
            report.append("-" * 20)
            report.append(f"Total Signals: {signals['total_signals']}")
            report.append(f"Average Confidence: {signals['avg_confidence']:.2f}")
            report.append(f"Signal Types: {signals['signal_types']}")
            report.append(f"Strategies Used: {signals['strategies']}")
            report.append("")
        
        # System Performance
        if system_analysis['operations']:
            ops = system_analysis['operations']
            report.append("⚡ SYSTEM PERFORMANCE")
            report.append("-" * 22)
            report.append(f"Total Operations: {ops['total_operations']}")
            report.append(f"Failure Rate: {ops['failure_rate']:.2%}")
            
            if ops['stats']:
                report.append("\nOperation Performance:")
                for op, stats in ops['stats'].items():
                    report.append(f"  {op}: {stats['count']} runs, avg {stats['avg_duration']:.3f}s")
            
            if ops['failed_operations']:
                report.append(f"\nRecent Failures: {len(ops['failed_operations'])}")
                for failure in ops['failed_operations'][-5:]:  # Last 5 failures
                    report.append(f"  {failure['operation']}: {failure['error']}")
            report.append("")
        
        # Risk Violations
        if trading_analysis['risks']:
            risks = trading_analysis['risks']
            report.append("⚠️  RISK VIOLATIONS")
            report.append("-" * 20)
            report.append(f"Total Violations: {risks['total_violations']}")
            report.append(f"Violation Types: {risks['violation_types']}")
            report.append(f"Severity Distribution: {risks['severities']}")
            report.append("")
        
        report.append("Generated at: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        return "\n".join(report)

def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description='Analyze trading system logs')
    parser.add_argument('--hours', type=int, default=24, help='Hours of logs to analyze')
    parser.add_argument('--log-dir', default='logs', help='Log directory path')
    parser.add_argument('--output', help='Output file for report')
    
    args = parser.parse_args()
    
    analyzer = LogAnalyzer(args.log_dir)
    report = analyzer.generate_report(args.hours)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"📄 Report saved to: {args.output}")
    else:
        print(report)

if __name__ == "__main__":
    main()
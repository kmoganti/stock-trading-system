"""
Security Configuration Validator

This module validates security settings and ensures proper configuration
for production deployment.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class SecurityCheckResult:
    """Result of a security check."""
    check_name: str
    passed: bool
    message: str
    severity: str = "INFO"  # INFO, WARNING, ERROR, CRITICAL

class SecurityValidator:
    """Validate security configuration for production deployment."""
    
    def __init__(self, env_file: str = ".env.production"):
        self.env_file = Path(env_file)
        self.config = {}
        self.results = []
        
        if self.env_file.exists():
            self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from environment file."""
        with open(self.env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    self.config[key] = value
    
    def validate_all(self) -> List[SecurityCheckResult]:
        """Run all security validation checks."""
        logger.info("🔍 Running comprehensive security validation...")
        
        checks = [
            self._check_secret_keys,
            self._check_debug_settings,
            self._check_database_security,
            self._check_api_security,
            self._check_cors_configuration,
            self._check_rate_limiting,
            self._check_logging_security,
            self._check_file_permissions,
            self._check_environment_settings
        ]
        
        for check in checks:
            try:
                result = check()
                if result:
                    if isinstance(result, list):
                        self.results.extend(result)
                    else:
                        self.results.append(result)
            except Exception as e:
                self.results.append(SecurityCheckResult(
                    check_name=check.__name__,
                    passed=False,
                    message=f"Check failed: {str(e)}",
                    severity="ERROR"
                ))
        
        return self.results
    
    def _check_secret_keys(self) -> List[SecurityCheckResult]:
        """Validate secret keys are properly configured."""
        results = []
        required_keys = ['SECRET_KEY', 'API_SECRET_KEY']
        
        for key in required_keys:
            if key not in self.config:
                results.append(SecurityCheckResult(
                    check_name="secret_keys",
                    passed=False,
                    message=f"Missing required secret key: {key}",
                    severity="CRITICAL"
                ))
            elif len(self.config[key]) < 32:
                results.append(SecurityCheckResult(
                    check_name="secret_keys",
                    passed=False,
                    message=f"Secret key {key} is too short (< 32 chars)",
                    severity="ERROR"
                ))
            else:
                results.append(SecurityCheckResult(
                    check_name="secret_keys",
                    passed=True,
                    message=f"Secret key {key} properly configured"
                ))
        
        return results
    
    def _check_debug_settings(self) -> SecurityCheckResult:
        """Check debug settings are disabled in production."""
        debug_enabled = self.config.get('DEBUG', 'false').lower() == 'true'
        
        return SecurityCheckResult(
            check_name="debug_settings",
            passed=not debug_enabled,
            message="Debug mode disabled" if not debug_enabled else "DEBUG=true in production!",
            severity="INFO" if not debug_enabled else "CRITICAL"
        )
    
    def _check_database_security(self) -> List[SecurityCheckResult]:
        """Validate database security configuration."""
        results = []
        
        db_url = self.config.get('DATABASE_URL', '')
        
        if 'sqlite' in db_url.lower():
            results.append(SecurityCheckResult(
                check_name="database_security",
                passed=True,
                message="SQLite database - ensure file permissions are secure",
                severity="WARNING"
            ))
        elif 'postgresql' in db_url.lower() and 'sslmode=require' not in db_url:
            results.append(SecurityCheckResult(
                check_name="database_security",
                passed=False,
                message="PostgreSQL connection should use SSL (sslmode=require)",
                severity="ERROR"
            ))
        else:
            results.append(SecurityCheckResult(
                check_name="database_security",
                passed=True,
                message="Database security configuration OK"
            ))
        
        return results
    
    def _check_api_security(self) -> List[SecurityCheckResult]:
        """Check API security settings."""
        results = []
        
        # Check API key configuration
        if 'API_SECRET_KEY' in self.config:
            results.append(SecurityCheckResult(
                check_name="api_security",
                passed=True,
                message="API secret key configured"
            ))
        
        # Check HTTPS settings
        https_only = self.config.get('SESSION_HTTPS_ONLY', 'true').lower() == 'true'
        results.append(SecurityCheckResult(
            check_name="api_security",
            passed=https_only,
            message="HTTPS enforced for sessions" if https_only else "Sessions not restricted to HTTPS",
            severity="INFO" if https_only else "WARNING"
        ))
        
        return results
    
    def _check_cors_configuration(self) -> SecurityCheckResult:
        """Validate CORS configuration."""
        allowed_origins = self.config.get('ALLOWED_ORIGINS', '')
        
        if not allowed_origins:
            return SecurityCheckResult(
                check_name="cors_config",
                passed=False,
                message="No CORS origins configured",
                severity="WARNING"
            )
        
        if '*' in allowed_origins:
            return SecurityCheckResult(
                check_name="cors_config",
                passed=False,
                message="Wildcard CORS origins detected - security risk!",
                severity="CRITICAL"
            )
        
        return SecurityCheckResult(
            check_name="cors_config",
            passed=True,
            message=f"CORS properly restricted to: {allowed_origins}"
        )
    
    def _check_rate_limiting(self) -> SecurityCheckResult:
        """Check rate limiting configuration."""
        rate_limit_enabled = self.config.get('RATE_LIMIT_ENABLED', 'false').lower() == 'true'
        
        return SecurityCheckResult(
            check_name="rate_limiting",
            passed=rate_limit_enabled,
            message="Rate limiting enabled" if rate_limit_enabled else "Rate limiting disabled",
            severity="INFO" if rate_limit_enabled else "WARNING"
        )
    
    def _check_logging_security(self) -> List[SecurityCheckResult]:
        """Validate logging security settings."""
        results = []
        
        # Check if sensitive logging is disabled
        console_logging = self.config.get('LOG_CONSOLE_ENABLED', 'true').lower() == 'true'
        if console_logging:
            results.append(SecurityCheckResult(
                check_name="logging_security",
                passed=False,
                message="Console logging enabled in production - may expose sensitive data",
                severity="WARNING"
            ))
        
        # Check log level
        log_level = self.config.get('LOG_LEVEL', 'DEBUG')
        if log_level == 'DEBUG':
            results.append(SecurityCheckResult(
                check_name="logging_security",
                passed=False,
                message="DEBUG logging enabled in production",
                severity="WARNING"
            ))
        
        return results
    
    def _check_file_permissions(self) -> List[SecurityCheckResult]:
        """Check file permissions for sensitive files."""
        results = []
        sensitive_files = ['.env.production', 'trading_system.db']
        
        for filename in sensitive_files:
            filepath = Path(filename)
            if filepath.exists():
                try:
                    stat_info = filepath.stat()
                    mode = oct(stat_info.st_mode)[-3:]
                    
                    # On Windows, check if file exists and is readable by owner
                    # Windows doesn't use Unix-style permissions
                    if os.name == 'nt':  # Windows
                        results.append(SecurityCheckResult(
                            check_name="file_permissions",
                            passed=True,
                            message=f"File {filename} exists (Windows permissions managed by NTFS)"
                        ))
                    else:  # Unix/Linux
                        if mode != '600':
                            results.append(SecurityCheckResult(
                                check_name="file_permissions",
                                passed=False,
                                message=f"File {filename} has insecure permissions: {mode} (should be 600)",
                                severity="ERROR"
                            ))
                        else:
                            results.append(SecurityCheckResult(
                                check_name="file_permissions",
                                passed=True,
                                message=f"File {filename} has secure permissions: {mode}"
                            ))
                except Exception as e:
                    results.append(SecurityCheckResult(
                        check_name="file_permissions",
                        passed=False,
                        message=f"Could not check permissions for {filename}: {str(e)}",
                        severity="WARNING"
                    ))
        
        return results
    
    def _check_environment_settings(self) -> SecurityCheckResult:
        """Check general environment settings."""
        environment = self.config.get('ENVIRONMENT', 'development')
        
        return SecurityCheckResult(
            check_name="environment",
            passed=environment == 'production',
            message=f"Environment set to: {environment}",
            severity="INFO" if environment == 'production' else "WARNING"
        )
    
    def generate_report(self) -> str:
        """Generate a comprehensive security validation report."""
        if not self.results:
            self.validate_all()
        
        report_lines = [
            "# 🔒 SECURITY VALIDATION REPORT",
            f"Generated: {datetime.now().isoformat()}",
            f"Configuration file: {self.env_file}",
            "",
            "## 📊 Summary",
        ]
        
        # Count results by severity
        critical_count = sum(1 for r in self.results if r.severity == "CRITICAL" and not r.passed)
        error_count = sum(1 for r in self.results if r.severity == "ERROR" and not r.passed)
        warning_count = sum(1 for r in self.results if r.severity == "WARNING" and not r.passed)
        passed_count = sum(1 for r in self.results if r.passed)
        
        report_lines.extend([
            f"- ✅ Passed: {passed_count}",
            f"- ⚠️ Warnings: {warning_count}",
            f"- ❌ Errors: {error_count}",
            f"- 🚨 Critical: {critical_count}",
            "",
            "## 🔍 Detailed Results",
            ""
        ])
        
        # Group results by severity
        for severity in ["CRITICAL", "ERROR", "WARNING", "INFO"]:
            severity_results = [r for r in self.results if r.severity == severity]
            if severity_results:
                icon = {"CRITICAL": "🚨", "ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️"}[severity]
                report_lines.append(f"### {icon} {severity}")
                
                for result in severity_results:
                    status_icon = "✅" if result.passed else "❌"
                    report_lines.append(f"- {status_icon} **{result.check_name}**: {result.message}")
                
                report_lines.append("")
        
        # Security recommendations
        if critical_count > 0 or error_count > 0:
            report_lines.extend([
                "## 🛡️ Security Recommendations",
                "",
                "### Immediate Actions Required:",
            ])
            
            for result in self.results:
                if not result.passed and result.severity in ["CRITICAL", "ERROR"]:
                    report_lines.append(f"- Fix: {result.message}")
            
            report_lines.append("")
        
        return "\n".join(report_lines)

if __name__ == "__main__":
    validator = SecurityValidator()
    results = validator.validate_all()
    
    print("🔒 Security Validation Results:")
    print("=" * 50)
    
    for result in results:
        icon = "✅" if result.passed else "❌"
        print(f"{icon} [{result.severity}] {result.check_name}: {result.message}")
    
    # Generate full report
    report = validator.generate_report()
    with open("security_validation_report.md", "w", encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n📄 Full report saved to: security_validation_report.md")

"""
Log Noise Filter Module
Filters out garbage logs, framework noise, and non-error information
"""

import re
from typing import Dict, List


class NoiseFilter:
    """Filter out garbage logs, framework noise, and non-error information"""
    
    # Log levels that should be filtered (not errors)
    NOISE_LOG_LEVELS = [
        r"(DEBUG|INFO|VERBOSE|TRACE|NOTICE)",  # Match anywhere in line
    ]
    
    # Retry and status message patterns (noise)
    RETRY_AND_STATUS_PATTERNS = [
        r"Retry attempt\s+\d+",  # Retry attempt messages
        r"Fallback response",  # Fallback messages
        r"Returning fallback",  # Returning fallback
        r"Skipping",  # Skipping operations
        r"Attempting to",  # Attempting messages
        r"Please check",  # Advisory messages
        r"Verify|verify",  # Verification messages
        r"Rolling back|Rollback initiated",  # Rollback messages
    ]
    
    # Framework-specific noise patterns
    FRAMEWORK_NOISE_PATTERNS = [
        # Spring Boot
        r"^.*Started \w+ in [\d.]+ seconds",
        r"^.*Tomcat started on port",
        r"^.*HikariPool.*initialized",
        r"^.*Connected to", r"^.*Connection pool",
        
        # Django
        r"^.*Django Version [\d.]+",
        r"^.*Starting development server",
        
        # Flask
        r"^.*Running on",
        r"^.*WARNING in app\.run\(\)",
        
        # Node.js
        r"^.*listening on port",
        r"^.*Server started",
        
        # ASP.NET
        r"^.*Application Started",
        r"^.*Connection string",
        
        # General framework patterns
        r"^.*\[INFO\].*Application",
        r"^.*\[DEBUG\].*Cache",
        r"^.*\[VERBOSE\].*Thread",
        r"^.*Starting up", r"^.*Shutting down",
        r"^.*Configuration", r"^.*Properties",
        r"^.*Loading", r"^.*Loaded",
        r"^.*Initializing", r"^.*Initialized",
    ]
    
    # HTTP access log patterns
    HTTP_LOG_PATTERNS = [
        r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\s+\S+\s+\S+\s+\[",  # Common log format
        r"^.*\"(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+\S+\s+HTTP/\d\.\d\"",
        r"^\d+-\d+-\d+\s+\d+:\d+:\d+.*\d{3}\s+\d+$",  # Access log with status
    ]
    
    # Repeated/redundant patterns
    REPEATED_PATTERNS = [
        r"^.*\.\.\.\s*\d+\s*more$",  # Java "... X more" pattern
        r"^.*caused by:.*caused by:",  # Duplicate caused by
    ]
    
    @staticmethod
    def compile_patterns() -> Dict[str, List[re.Pattern]]:
        """Pre-compile all noise filter patterns"""
        return {
            "log_levels": [re.compile(p, re.IGNORECASE) for p in NoiseFilter.NOISE_LOG_LEVELS],
            "retry_status": [re.compile(p, re.IGNORECASE) for p in NoiseFilter.RETRY_AND_STATUS_PATTERNS],
            "framework": [re.compile(p, re.IGNORECASE) for p in NoiseFilter.FRAMEWORK_NOISE_PATTERNS],
            "http": [re.compile(p, re.IGNORECASE) for p in NoiseFilter.HTTP_LOG_PATTERNS],
            "repeated": [re.compile(p, re.IGNORECASE) for p in NoiseFilter.REPEATED_PATTERNS],
        }
    
    @staticmethod
    def is_noise(line: str, compiled_patterns: Dict[str, List[re.Pattern]]) -> bool:
        """Check if line is noise and should be filtered"""
        line = line.strip()
        
        if not line:
            return True
        
        # Check if it's an actual error line (has ERROR, FATAL, CRITICAL, EXCEPTION, Traceback)
        error_keywords = ['ERROR', 'FATAL', 'CRITICAL', 'EXCEPTION', 'Traceback', 'Exception']
        has_error_keyword = any(keyword in line for keyword in error_keywords)
        
        if has_error_keyword:
            # For error lines, only filter out retry/status messages
            for pattern in compiled_patterns["retry_status"]:
                if pattern.search(line):
                    return True
            # Don't filter actual error lines
            return False
        
        # For non-error lines, check all noise patterns
        # Check log level noise
        for pattern in compiled_patterns["log_levels"]:
            if pattern.search(line):
                return True
        
        # Check framework noise
        for pattern in compiled_patterns["framework"]:
            if pattern.search(line):
                return True
        
        # Check HTTP access logs
        for pattern in compiled_patterns["http"]:
            if pattern.search(line):
                return True
        
        # Check repeated patterns
        for pattern in compiled_patterns["repeated"]:
            if pattern.search(line):
                return True
        
        return False
    
    @staticmethod
    def filter_logs(lines: List[str]) -> List[str]:
        """Remove noise from log lines, keeping only relevant error information and preserving empty lines"""
        compiled = NoiseFilter.compile_patterns()
        filtered = []
        
        for line in lines:
            # PRESERVE empty lines - they are needed for error segregation
            if not line.strip():
                filtered.append(line)
            elif not NoiseFilter.is_noise(line, compiled):
                filtered.append(line)
        
        return filtered

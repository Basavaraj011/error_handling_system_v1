"""
Dynamic Value Cleaner Module
Removes dynamic values from stack traces for better similarity matching
"""

import re
from typing import Dict, List


class DynamicValueCleaner:
    """Remove dynamic values from stack traces for better similarity matching"""
    
    # Patterns for various dynamic values
    DYNAMIC_PATTERNS = {
        "timestamps": [
            # ISO 8601 formats
            r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}[\.\,]\d{3,6}Z?",  # 2025-01-01T12:00:00.000Z or 2025-01-01 12:00:00.000
            r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}Z?",  # 2025-01-01T12:00:00Z or 2025-01-01 12:00:00
            
            # Common log format variations
            r"\d{2}/\w+/\d{4}\s+\d{2}:\d{2}:\d{2}[\.\,]\d{3,6}",  # 01/Jan/2025 12:00:00.000
            r"\d{2}/\w+/\d{4}\s+\d{2}:\d{2}:\d{2}",  # 01/Jan/2025 12:00:00
            r"\[\d{2}/\w+/\d{4}\s+\d{2}:\d{2}:\d{2}[\.\,]\d{3,6}\]",  # [01/Jan/2025 12:00:00.000]
            r"\[\d{2}/\w+/\d{4}\s+\d{2}:\d{2}:\d{2}\]",  # [01/Jan/2025 12:00:00]
            
            # DD-MMM-YYYY HH:MM:SS format
            r"\d{1,2}-\w+-\d{4}\s+\d{2}:\d{2}:\d{2}[\.\,]\d{3,6}",  # 01-Jan-2025 12:00:00.000
            r"\d{1,2}-\w+-\d{4}\s+\d{2}:\d{2}:\d{2}",  # 01-Jan-2025 12:00:00
            r"\[\d{1,2}-\w+-\d{4}\s+\d{2}:\d{2}:\d{2}\]",  # [01-Jan-2025 12:00:00]
            
            # Time-only formats
            r"^\d{1,2}:\d{2}:\d{2}[\.\,]\d{3,6}\s+",  # 12:00:00.000 prefix
            r"^\d{1,2}:\d{2}:\d{2}\s+",  # 12:00:00 prefix
            r"\[\d{1,2}:\d{2}:\d{2}[\.\,]\d{3,6}\]",  # [12:00:00.000]
            r"\[\d{1,2}:\d{2}:\d{2}\]",  # [12:00:00]
            r"\s\d{1,2}:\d{2}:\d{2}[\.\,]\d{3,6}\s",  # space 12:00:00.000 space
            r"\s\d{1,2}:\d{2}:\d{2}\s",  # space 12:00:00 space
            
            # Date-only formats
            r"\d{4}-\d{2}-\d{2}(?:[T\s]|$)",  # 2025-01-01 (with boundary)
            r"\d{2}/\d{2}/\d{4}(?:\s|$)",  # 01/01/2025
            r"\d{2}/\w+/\d{4}(?:\s|$)",  # 01/Jan/2025
            r"\d{1,2}-\w+-\d{4}(?:\s|$)",  # 01-Jan-2025
            r"\w+\s+\d{1,2},?\s+\d{4}(?:\s|$)",  # January 1, 2025 or January 1 2025
            r"\d{1,2}\s+\w+\s+\d{4}(?:\s|$)",  # 1 January 2025
            
            # Unix timestamps (10-13 digits)
            r"\b\d{10,13}\b",  # Unix timestamp
            
            # Syslog format
            r"^\w+\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}(?:\s|$)",  # Jan 01 12:00:00
            
            # Timestamp in brackets
            r"\[\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}[\.\,]?\d{0,6}Z?\]",  # [2025-01-01T12:00:00.000]
            
            # Timezone offsets
            r"[+-]\d{2}:\d{2}(?:\s|$)",  # +05:30 or -08:00
        ],
        "memory_addresses": [
            r"0x[0-9a-fA-F]+",  # Hex memory addresses
            r"@[0-9a-fA-F]+",  # Java-style @addresses
        ],
        "file_paths": [
            r"[A-Za-z]:\\[^\"'\s]*",  # Windows paths
            r"/[^\"'\s]*(?:\\.py|\\.java|\\.js|\\.cpp|\\.go|\\.rb|\\.php|\\.sql)",  # Unix paths with extensions
            r"\([^)]*(?:\\.py|\\.java|\\.js):\d+\)",  # File:line in parentheses
        ],
        "line_numbers": [
            r"line\s+\d+",
            r":\d+:",  # file:line:col format
            r"at\s+\d+",
        ],
        "ids_and_numbers": [
            r"(id|ID|Id)[\s:=]+['\"]?[0-9a-f]{8,}",  # ID values
            r"(request|Request|REQUEST)[\s:=]+['\"]?\d+",  # Request IDs
            r"(session|Session|SESSION)[\s:=]+['\"]?[0-9a-f]+",  # Session IDs
            r"(hash|Hash)[\s:=]+[0-9a-f]+",  # Hash values
            r"duration[\s:=]+[\d.]+\s*(ms|s|seconds|milliseconds)?",  # Duration values
        ],
        "process_info": [
            r"(pid|PID)[\s:=]+\d+",  # Process ID
            r"(thread|Thread)[\s:=]+\d+",  # Thread ID
            r"(task|Task)[\s:=]+\d+",  # Task ID
        ],
        "port_numbers": [
            r"port\s+\d{4,5}",
            r":\d{4,5}/",  # URL with port
        ],
    }
    
    @staticmethod
    def compile_patterns() -> Dict[str, List[re.Pattern]]:
        """Pre-compile all dynamic value patterns"""
        compiled = {}
        for category, patterns in DynamicValueCleaner.DYNAMIC_PATTERNS.items():
            compiled[category] = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in patterns]
        return compiled
    
    @staticmethod
    def remove_timestamp(line: str) -> str:
        """Remove all timestamps and dates from a line"""
        cleaned = line
        
        # Comprehensive timestamp patterns
        timestamp_patterns = [
            # ISO 8601 formats
            r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}[\.\,]\d{3,6}Z?",  # 2025-01-01T12:00:00.000Z
            r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}Z?",  # 2025-01-01T12:00:00 or 2025-01-01 12:00:00
            
            # Common log format
            r"\d{2}/\w+/\d{4}\s+\d{2}:\d{2}:\d{2}[\.\,]\d{3,6}",  # 01/Jan/2025 12:00:00.000
            r"\d{2}/\w+/\d{4}\s+\d{2}:\d{2}:\d{2}",  # 01/Jan/2025 12:00:00
            r"\[\d{2}/\w+/\d{4}\s+\d{2}:\d{2}:\d{2}[\.\,]?\d{0,6}\]",  # [01/Jan/2025 12:00:00]
            
            # DD-MMM-YYYY HH:MM:SS
            r"\d{1,2}-\w+-\d{4}\s+\d{2}:\d{2}:\d{2}[\.\,]\d{3,6}",  # 01-Jan-2025 12:00:00.000
            r"\d{1,2}-\w+-\d{4}\s+\d{2}:\d{2}:\d{2}",  # 01-Jan-2025 12:00:00
            
            # Time-only (with boundaries)
            r"\b\d{1,2}:\d{2}:\d{2}[\.\,]\d{3,6}\b",  # 12:00:00.000
            r"\b\d{1,2}:\d{2}:\d{2}\b",  # 12:00:00
            r"\[\d{1,2}:\d{2}:\d{2}[\.\,]\d{0,6}\]",  # [12:00:00.000]
            
            # Date-only formats
            r"\d{4}-\d{2}-\d{2}\b",  # 2025-01-01
            r"\d{2}/\d{2}/\d{4}\b",  # 01/01/2025
            r"\d{2}/\w+/\d{4}\b",  # 01/Jan/2025
            r"\d{1,2}-\w+-\d{4}\b",  # 01-Jan-2025
            
            # Unix/Epoch timestamps (10-13 digits on word boundary)
            r"\b\d{10,13}\b",  # Unix timestamp
            
            # Syslog format
            r"\b\w+\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\b",  # Jan 01 12:00:00
            
            # Full datetime in brackets
            r"\[\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}[\.\,]?\d{0,6}Z?\]",
            
            # Timezone info
            r"\s[+-]\d{2}:\d{2}\b",  # +05:30 or -08:00
        ]
        
        for pattern in timestamp_patterns:
            cleaned = re.sub(pattern, '', cleaned)
        
        # Clean up extra spaces left behind
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # Remove empty brackets left behind after timestamp removal
        cleaned = re.sub(r'\[\s*\]', '', cleaned)
        cleaned = re.sub(r'\(\s*\)', '', cleaned)
        
        return cleaned.strip()
    
    @staticmethod
    def clean_line(line: str, compiled_patterns: Dict[str, List[re.Pattern]]) -> str:
        """Remove dynamic values from a single line"""
        # First remove timestamps
        cleaned = DynamicValueCleaner.remove_timestamp(line)
        
        # Replace memory addresses with <MEMORY_ADDRESS>
        for pattern in compiled_patterns["memory_addresses"]:
            cleaned = pattern.sub("<MEMORY_ADDRESS>", cleaned)
        
        # Replace file paths with <FILE_PATH>
        for pattern in compiled_patterns["file_paths"]:
            cleaned = pattern.sub("<FILE_PATH>", cleaned)
        
        # Replace line numbers with <LINE_NUM>
        for pattern in compiled_patterns["line_numbers"]:
            cleaned = pattern.sub("<LINE_NUM>", cleaned)
        
        # Replace IDs and numbers with <ID>
        for pattern in compiled_patterns["ids_and_numbers"]:
            cleaned = pattern.sub("<ID>", cleaned)
        
        # Replace process info with <PROCESS_INFO>
        for pattern in compiled_patterns["process_info"]:
            cleaned = pattern.sub("<PROCESS_INFO>", cleaned)
        
        # Replace port numbers with <PORT>
        for pattern in compiled_patterns["port_numbers"]:
            cleaned = pattern.sub("<PORT>", cleaned)
        
        return cleaned
    
    @staticmethod
    def clean_stack_trace(stack_trace: List[str]) -> List[str]:
        """Clean entire stack trace by removing dynamic values, timestamps, and non-important lines"""
        compiled = DynamicValueCleaner.compile_patterns()
        cleaned_lines = [DynamicValueCleaner.clean_line(line, compiled) for line in stack_trace]
        
        # Filter out non-important lines (WARNING, DEBUG, INFO, VERBOSE, TRACE, NOTICE)
        # Keep only lines that contain actual error information
        filtered_lines = []
        non_important_prefixes = ['WARNING', 'DEBUG', 'INFO', 'VERBOSE', 'TRACE', 'NOTICE']
        
        for line in cleaned_lines:
            stripped = line.strip()
            if not stripped:
                continue
            
            # Check if line starts with a non-important prefix
            is_non_important = False
            for prefix in non_important_prefixes:
                # Match if line starts with [PREFIX] or PREFIX (case-insensitive)
                if re.match(rf'^[\[]?{re.escape(prefix)}[\]]?\s', stripped, re.IGNORECASE):
                    is_non_important = True
                    break
            
            # Include the line if it's important or contains error keywords
            if not is_non_important:
                filtered_lines.append(line)
            elif any(keyword in stripped for keyword in ['ERROR', 'FATAL', 'CRITICAL', 'Exception', 'Error', 'Traceback']):
                # Even if it starts with non-important prefix, keep it if it has error keywords
                filtered_lines.append(line)
        
        return filtered_lines

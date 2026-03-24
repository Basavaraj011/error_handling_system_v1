"""
Base Error Extractor Module
Comprehensive error extraction with noise reduction, deterministic error block detection,
and dynamic value cleaning for all tool types.

Features:
1. Noise Reduction: Filters DEBUG, INFO, WARNING, framework noise, HTTP logs, etc.
2. Deterministic Error Block Detection: Full error blocks as stack traces
3. Cleaned Stack Trace: Removes timestamps, IDs, memory addresses, file paths, etc.
"""

from dataclasses import dataclass, field
from importlib import import_module
from typing import List, Dict, Optional, Any, Set, Tuple
from pathlib import Path
import re
import glob
from enum import Enum
import os
import sys
import yaml


workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))

from config.settings import DATABASE_URL
from database.database_operations import insert_errors_into_db
from connections.database_connections import DatabaseManager
from src.core.error_detector import ErrorDetector
from src.core.log_filters import NoiseFilter
from src.core.value_cleaners import DynamicValueCleaner
# ============================================================================
# ERROR MARKERS & KNOWN PATTERNS
# ============================================================================


ERROR_MARKERS = {
    "CRITICAL": [
        # Python
        "Traceback", "SyntaxError", "IndentationError", "NameError", 
        "TypeError", "ValueError", "KeyError", "IndexError", "AttributeError",
        "ImportError", "ModuleNotFoundError", "ZeroDivisionError", 
        "RuntimeError", "NotImplementedError", "AssertionError",
        
        # Java
        "Exception", "Error", "Throwable", "NullPointerException", 
        "ClassNotFoundException", "IllegalArgumentException", "IOException",
        "SQLException", "ArrayIndexOutOfBoundsException", "ClassCastException",
        "OutOfMemoryError", "StackOverflowError", "RuntimeException",
        
        # JavaScript/Node.js
        "TypeError", "ReferenceError", "SyntaxError", "RangeError",
        "EvalError", "URIError", "Error", "UnhandledPromiseRejection",
        
        # C++
        "exception", "std::runtime_error", "std::logic_error", 
        "segmentation fault", "Segmentation Fault", "SIGSEGV",
        "access violation", "core dumped",
        
        # SQL
        "SQLError", "SQLException", "SQL Syntax", "Syntax error",
        "constraint violation", "primary key violation",
        
        # Go
        "panic", "fatal", "error", "panic:", "fatal:",
        
        # C#/.NET
        "Exception", "NullReferenceException", "InvalidOperationException",
        "NotImplementedException", "ArgumentException", "InvalidCastException",
        
        # Ruby
        "StandardError", "RuntimeError", "NoMethodError", "NameError",
        "ArgumentError", "IOError", "SyntaxError",
        
        # PHP
        "Fatal error", "Parse error", "Warning", "Notice", "Error",
        "Exception", "Deprecated",
    ],
    
    "MAJOR": [
        "ERROR", "FATAL", "CRITICAL", "SEVERE",
        "failed", "failure", "failed to", "unable to", "cannot",
        "could not", "crashed", "crash", "panic", "abort", "died",
    ],
    
    "STACK_TRACE_INDICATORS": [
        "Traceback", "Stack trace", "stack trace:",
        "at ", "caused by", "thrown by",
        "File ", "line ", "in ", "at line",
        "goroutine", "panic:", "fatal:",
    ],
    
    "FRAMEWORK_NOISE": [
        "DEBUG", "INFO", "VERBOSE", "TRACE",
        "Entering", "Exiting", "Starting", "Started", "Initialized",
        "Connected", "Connecting", "Disconnected", "Reconnecting",
        "Attempting", "Retrying", "Waiting", "Timeout",
        "Connection pool", "Thread pool", "cache", "Cache",
    ],
    
    "HTTP_PATTERNS": [
        "GET ", "POST ", "PUT ", "DELETE ", "PATCH ",
        "HTTP/", "status:", "status code", "response code",
        "404", "500", "403", "401", "502", "503",
    ],
}


# ============================================================================
# REFACTORED CLASSES
# ============================================================================
# Note: NoiseFilter and DynamicValueCleaner have been moved to separate modules:
# - src/core/log_filters.py (NoiseFilter class)
# - src/core/value_cleaners.py (DynamicValueCleaner class)
# They are imported at the top of this file for backward compatibility.

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class ExtractedError:
    """Represents an extracted error with cleaned and original data"""
    tool: str
    main_error: str
    stack_trace: List[str] = field(default_factory=list)
    cleaned_stack_trace: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format with stack traces as newline-separated strings"""
        return {
            "tool": self.tool,
            "main_error": self.main_error,
            "stack_trace": "\n".join(self.stack_trace) if self.stack_trace else "",
            "cleaned_stack_trace": "\n".join(self.cleaned_stack_trace) if self.cleaned_stack_trace else ""
        }


# ============================================================================
# BASE ERROR EXTRACTOR
# ============================================================================

class BaseErrorExtractor:
    """Main error extractor with noise reduction and dynamic value cleaning"""
    
    def __init__(self, max_stack_trace_lines: int = 50):
        self.max_stack_trace_lines = max_stack_trace_lines
        self.error_detector = ErrorDetector()
        self.dynamic_cleaner = DynamicValueCleaner()
    
    def extract_errors(self, lines: List[str]) -> List[ExtractedError]:
        """
        Extract errors from log lines with noise reduction and cleaning.
        
        Process:
        1. Filter noise (DEBUG, INFO, framework logs, HTTP access logs, retry/status messages)
        2. Group lines by EMPTY LINES ONLY (each group is one error block)
        3. For each group, find the MAIN error line
        4. Detect tool type
        5. Generate cleaned stack traces
        
        Returns:
            List of ExtractedError objects
        """
        # Step 1: Noise reduction
        filtered_lines = NoiseFilter.filter_logs(lines)
        
        if not filtered_lines:
            return []
        
        # Step 2: Group lines by empty lines ONLY (error separators)
        error_groups = []
        current_group = []
        
        for line in filtered_lines:
            if line.strip():  # Non-empty line
                current_group.append(line)
            else:  # Empty line - separator
                if current_group:
                    error_groups.append(current_group)
                    current_group = []
        
        # Add last group if exists
        if current_group:
            error_groups.append(current_group)
        
        # Step 3: Process each group as a potential error
        errors = []
        
        for group in error_groups:
            error = self._extract_error_from_group(group)
            if error:
                errors.append(error)
        
        return errors
    
    def _extract_error_from_group(self, group: List[str]) -> Optional[ExtractedError]:
        """Extract a single error from a group of lines (separated by empty lines)"""
        if not group:
            return None
        
        # Extract main error from the entire group (not just first line)
        main_error = self.error_detector.extract_main_error(group) 

        if not main_error:
            return None
        main_error= DynamicValueCleaner.remove_timestamp(main_error.strip())
        # Build stack trace: entire group with timestamps removed
        stack_trace = []
        for line in group:
            cleaned = DynamicValueCleaner.remove_timestamp(line.strip())
            if cleaned:
                stack_trace.append(cleaned)
        
        if not stack_trace:
            return None
        
        # Detect tool type
        tool = self.error_detector.detect_tool_type(stack_trace)
        
        # Generate cleaned stack trace
        cleaned_trace = self.dynamic_cleaner.clean_stack_trace(stack_trace)
        
        return ExtractedError(
            tool=tool,
            main_error=main_error,
            stack_trace=stack_trace,
            cleaned_stack_trace=cleaned_trace
        )
    
    @staticmethod
    def _looks_like_error_context(line: str) -> bool:
        """Check if line looks like it's part of error context"""
        line = line.strip()
        
        # Common stack trace and error context patterns
        context_patterns = [
            r'^\s+at\s+',
            r'^\s+File\s+"',
            r'^\s+in\s+\w+',
            r'^\s+->\s+',
            r'^\s+raised|raised by',
            r'^\s+caused\s+by',
            r'^\s+Caused\s+by',
            r'^\s+during\s+handling',
            r'^\s+Exception\s+in',
            r'^\s+\d+\s+\|',  # Stack with line number
            r'^\s+\[\d+\]',  # Stack frame
        ]
        
        for pattern in context_patterns:
            if re.search(pattern, line):
                return True
        
        return False


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def read_log_file(file_path: str) -> List[str]:
    """Read a log file and return lines (preserving empty lines for error segregation)"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return [line.rstrip('\n\r') for line in f]
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []


def read_log_directory(directory_path: str, pattern: str = "*.txt") -> Dict[str, List[str]]:
    """Read all log files from directory"""
    log_files = {}
    
    try:
        dir_path_obj = Path(directory_path)
        
        if not dir_path_obj.is_dir():
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        
        file_paths = sorted(dir_path_obj.glob(pattern))
        
        if not file_paths:
            print(f"Warning: No files matching pattern '{pattern}' found")
            return log_files
        
        for file_path in file_paths:
            lines = read_log_file(str(file_path))
            if lines:
                log_files[file_path.name] = lines
                print(f"✓ {file_path.name}: {len(lines)} lines")
        
        return log_files
    
    except Exception as e:
        print(f"Error: {e}")
        return {}


def get_errors_as_list(errors: List[ExtractedError], filename: str = "ErrorLogs1.txt") -> List[Dict[str, Any]]:
    """Convert extracted errors to a list of dictionaries"""
    errors_list = []
    
    for error_counter, error in enumerate(errors, 1):
        error_dict = error.to_dict()
        error_dict["error_id"] = error_counter
        error_dict["source_file"] = filename
        errors_list.append(error_dict)
    
    return errors_list


# ============================================================================
# USAGE EXAMPLE
# ============================================================================


def start_error_extractor():
    print("=" * 80)
    print("Base Error Extractor - Advanced Error Analysis")
    print("=" * 80)
    
    # Use Error Logs directory
    #error_logs_dir = r"C:\Users\kutkar01\OneDrive - dentsu\Documents\Self Heal\error_handling_system\Test_Error_Logs"
    
    base_path = os.path.dirname(__file__)

    error_logs_file = os.path.join(base_path, "..", "Test_Error_Logs", "ErrorLogs1.txt")

    try:
        # Read single log file
        print(f"Reading log file: {error_logs_file}\n")
        
        if not os.path.exists(error_logs_file):
            print(f"Error log file not found: {error_logs_file}")
            exit(1)
        
        lines = read_log_file(error_logs_file)
        print(f"Successfully read {len(lines)} lines\n")
        
        # Initialize extractor
        extractor = BaseErrorExtractor(max_stack_trace_lines=50)
        
        # Extract errors from the single file
        print("Extracting errors...\n")
        errors = extractor.extract_errors(lines)
        total_errors = len(errors)
        
        if errors:
            print(f"Found {total_errors} error(s)\n")
        else:
            print(f"No errors found\n")
        
        # Display results
        print("\n" + "=" * 80)
        print(f"EXTRACTION RESULTS - Total Errors: {total_errors}")
        print("=" * 80 + "\n")
        
        # Summary statistics
        print(f"\n\n{'=' * 80}")
        print("SUMMARY STATISTICS:")
        print(f"{'=' * 80}")
        print(f"Total Errors Found: {total_errors}")
        
        if total_errors > 0:
            tool_dist = {}
            for error in errors:
                tool_dist[error.tool] = tool_dist.get(error.tool, 0) + 1
            
            print(f"\nTools/Languages Distribution:")
            for tool, count in sorted(tool_dist.items(), key=lambda x: x[1], reverse=True):
                print(f"  {tool}: {count}")
        
        print(f"\n{'=' * 80}\n")
        
        # Create list of all errors as dictionaries
        print("=" * 80)
        print("ERRORS AS LIST OF DICTIONARIES:")
        print("=" * 80 + "\n")
        
        errors_list = get_errors_as_list(errors, "ErrorLogs1.txt")
        
        print(f"Total Errors: {len(errors_list)}\n")
        print("Format: [Error1, Error2, Error3, ...]\n")
        
        for error_dict in errors_list:
            print(f"\nError {error_dict['error_id']} (from {error_dict['source_file']}):")
            print(f"{{")
            print(f"    'tool': '{error_dict['tool']}',")
            print(f"    'main_error': '{error_dict['main_error'][:80]}{'...' if len(error_dict['main_error']) > 80 else ''}',")
            print(f"    'stack_trace': '{error_dict['stack_trace'][:100]}{'...' if len(error_dict['stack_trace']) > 100 else ''}',")
            print(f"    'cleaned_stack_trace': '{error_dict['cleaned_stack_trace'][:100]}{'...' if len(error_dict['cleaned_stack_trace']) > 100 else ''}'")
            print(f"}}")
        
        print(f"\n{'=' * 80}")
        print("ERROR DATA AVAILABLE AS:")
        print(f"{'=' * 80}")
        print(f"Total Records: {len(errors_list)}")
        print(f"Ready to pass to SQL database")
        print(f"{'=' * 80}\n")
        # Return errors_list for use in other parts of the application
        # This can be passed directly to SQL DB insert operations
        
        if errors_list:
            try:
                config_path = os.path.join(workspace_root, 'config', 'teams.yml')
                with open(config_path) as f:
                    data = yaml.safe_load(f)
                team_name = next(iter(data["teams"]))
                project_name = next(iter(data["projects"]))
                repo_name = next(iter(data["repo_names"]))
                print("Team Name:", team_name)
                print("Project Name:", project_name)
                print("Repo Name:", repo_name)
                db_manager = DatabaseManager(DATABASE_URL)
                insert_errors_into_db(errors_list, db_manager, team_name, project_name, repo_name)
            except Exception as e:
                print(f"Error inserting into database: {e}")
                import traceback
                traceback.print_exc()
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Starting Base Error Extractor...\n")
    start_error_extractor()
"""
Error Detector Module
Detects and classifies errors from log content.
Handles error type identification, tool/language detection, and main error extraction.
"""

from typing import List, Dict, Optional
import re
from enum import Enum


class ToolType(Enum):
    """Supported tool/language types"""
    PYTHON = "Python"
    JAVA = "Java"
    SQL = "SQL"
    JAVASCRIPT = "JavaScript"
    CPP = "C++"
    GO = "Go"
    CSHARP = "C#"
    RUBY = "Ruby"
    PHP = "PHP"
    NODEJS = "Node.js"
    DOTNET = ".NET"
    CSHARP_DOTNET = "C#/.NET"
    C = "C"
    KERNEL = "Kernel"
    RUBY_RAILS = "Ruby/Rails"
    UNKNOWN = "Unknown"


class ErrorDetector:
    """Detect error blocks and extract structured error information"""
    
    # Error markers from all tools
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
    
    # Specific error type keywords to prioritize as main errors
    SPECIFIC_ERROR_TYPES = [
        # Python - Exceptions
        "NameError", "IndexError", "TypeError", "ValueError", "KeyError", 
        "AttributeError", "ImportError", "ModuleNotFoundError", "ZeroDivisionError",
        "RuntimeError", "NotImplementedError", "AssertionError", "IOError",
        "UnboundLocalError", "FileNotFoundError", "PermissionError", "SyntaxError",
        "IndentationError", "OSError", "RecursionError", "UnicodeDecodeError",
        "ConnectionError", "ConnectionRefusedError", "ReadTimeout", "JSONDecodeError",
        "ssl.SSLCertVerificationError", "kafka.errors.KafkaTimeoutError",
        "OverflowError", "LookupError", "StopIteration", "GeneratorExit",
        "SystemExit", "KeyboardInterrupt", "EnvironmentError", "EOFError",
        "ArithmeticError", "FloatingPointError", "MemoryError",
        
        # Java - Exceptions
        "NullPointerException", "ClassNotFoundException", "IllegalArgumentException",
        "IOException", "SQLException", "ArrayIndexOutOfBoundsException",
        "ClassCastException", "OutOfMemoryError", "StackOverflowError",
        "IllegalStateException", "UnsupportedOperationException",
        "ConcurrentModificationException", "NoSuchElementException",
        "IllegalMonitorStateException", "InstantiationException",
        "InvocationTargetException", "ExceptionInInitializerError",
        "LinkageError", "VerifyError", "NoClassDefFoundError",
        
        # JavaScript/Node.js - Errors
        "ReferenceError", "RangeError", "EvalError", "URIError",
        "UnhandledPromiseRejection", "AggregateError", "SyntaxError",
        
        # C# - Exceptions
        "NullReferenceException", "InvalidOperationException", "NotImplementedException",
        "ArgumentException", "InvalidCastException", "FileNotFoundException",
        "NotSupportedException", "OperationCanceledException",
        "IndexOutOfRangeException", "ArgumentOutOfRangeException",
        "FormatException", "OverflowException",
        
        # SQL/PostgreSQL - Errors
        "SQLError", "SQLException", "ConstraintViolation",
        "DeadlockDetected", "Deadlock", "SyntaxError", "foreign key constraint",
        "integrity error", "constraint violation", "NOT NULL", "out of shared memory",
        "out of memory", "file unreadable", "out of range", "integer out of range",
        "division by zero", "database locked", "duplicate key", "database is locked",
        "Unique violation", "Check violation", "Exclusion violation",
        "Table does not exist", "Column does not exist", "Relation does not exist",
        "Deadlock avoided", "Lock timeout", "Recovery", "Recovery mode",
        "Vacuum", "Reindex", "Analyze", "Explain",
        
        # C/C++ - Errors and Signals
        "Segmentation fault", "segmentation fault", "SIGSEGV", "SIGABRT",
        "Bus error", "bus error", "SIGBUS", "core dumped", "Illegal instruction",
        "SIGILL", "Floating point exception", "SIGFPE", "Aborted",
        "std::bad_alloc", "std::runtime_error", "std::logic_error",
        "stack smashing detected", "buffer overflow", "undefined symbol",
        "permission denied", "operation not permitted", "resource deadlock",
        "Resource temporarily unavailable", "EAGAIN", "EPERM", "EDEADLK",
        "No such file or directory", "ENOENT", "Permission denied", "EACCES",
        "Interrupted system call", "EINTR", "Bad address", "EFAULT",
        "Device or resource busy", "EBUSY", "File exists", "EEXIST",
        "Is a directory", "EISDIR", "Cross-device link", "EXDEV",
        "Invalid argument", "EINVAL", "Too many open files", "EMFILE",
        "Pipe error", "Broken pipe", "EPIPE", "Value too large", "EOVERFLOW",
        "Function not implemented", "ENOSYS", "Read-only file system", "EROFS",
        "Name too long", "ENAMETOOLONG",
        
        # C - Compilation and Runtime
        "error:", "undeclared", "no match for", "invalid conversion",
        "permission denied", "Permission denied", "note:", "warning:",
        "compilation failed", "Make terminated", "Build failed",
        "Undefined reference", "Multiple definition", "Missing symbol",
        "Implicit declaration", "Incompatible pointer", "Type mismatch",
        
        # Ruby/Rails - Errors
        "LoadError", "NoMethodError", "StandardError", "Errno::ENOMEM",
        "Errno::EACCES", "Errno::ENOENT", "SocketError", "Timeout",
        "ExecJS::RuntimeError", "BCrypt::Errors::InvalidCost",
        "OpenSSL::SSL::SSLError", "PG::ConnectionBad", "PG::DuplicateColumn",
        "ActiveRecord::RecordInvalid", "Aws::S3::Errors::HttpTimeoutError",
        "Errno::EAGAIN", "Errno::EPERM", "Errno::EDEADLK", "Errno::EBUSY",
        "Errno::ENOTEMPTY", "Errno::EROFS", "RuntimeError", "ArgumentError",
        "IOError", "SystemCallError", "RangeError", "TypeError",
        
        # Go - Errors
        "panic:", "fatal:", "error:", "Error:",
        
        # Kernel/Linux - Errors
        "BUG:", "kernel NULL pointer", "Kernel panic", "kernel panic",
        "kernel NULL pointer dereference", "Tainted:", "RIP:", "Call Trace:",
        "double free", "Program received signal", "OOPS", "Machine check",
        "WARNING:", "BUG on unmap:", "kernel BUG", "lockdep:",
        "RCU stall", "CPU stall", "Watchdog", "Hard lockup", "Soft lockup",
        
        # Network/SSL/TLS - Errors
        "Connection refused", "Connection reset", "Broken pipe",
        "CERTIFICATE_VERIFY_FAILED", "certificate has expired",
        "certificate verify failed", "self signed certificate",
        "Temporary failure in name resolution", "getaddrinfo:",
        "DNS lookup", "timed out", "Timeout reached",
        "ECONNREFUSED", "ECONNRESET", "EPIPE", "ETIMEDOUT",
        "Network is unreachable", "ENETUNREACH", "Host is unreachable", "EHOSTUNREACH",
        "TLS handshake", "SSL handshake", "Certificate chain", "Cipher",
        
        # GPU/CUDA/Graphics - Errors
        "CUDA out of memory", "RuntimeError: CUDA", "gpu", "GPU OOM",
        "VK_ERROR", "Vulkan", "VK_ERROR_INCOMPATIBLE_DRIVER",
        "Invalid SPIR-V", "dlsym failed", "ABI mismatch",
        "vkCreateInstance", "Vulkan loader", "CUDA driver", "Device error",
        
        # Serialization/Pickle - Errors
        "pickle", "Pickle", "PickleError", "Can't get attribute",
        "BadPickleData", "AttributeError", "unpickling", "Unpickling",
        
        # Parser/Configuration - Errors
        "ScannerError", "scanner error", "YAML error", "yaml error",
        "mapping values are not allowed", "json", "JSON error",
        "ParserError", "TokenError", "ParseException", "Invalid JSON",
        "Invalid YAML", "Malformed", "Syntax",
        
        # Hardware/Disk - Errors
        "Input/output error", "No space left on device", "Disk full",
        "orphaned relation", "file corruption", "sector unreadable",
        "Hardware failure", "Hardware", "hardware error", "FPGA",
        "I/O error", "Read error", "Write error", "Seek error",
        "Media error", "CRC error", "Parity error",
        
        # Memory - Errors
        "stack overflow", "stack smashing", "double free", "use-after-free",
        "Memory corruption", "memory", "heap", "allocation", "allocate",
        "Heap overflow", "Heap underflow", "UAF", "OOM",
        
        # Process/Threading - Errors
        "Resource deadlock", "deadlock", "thread", "Thread", "stalled",
        "ulimit", "fork failed", "OOM killer", "out of resources",
        "Mutex", "Lock", "Semaphore", "Race condition",
        
        # Watchdog/Monitoring - Errors
        "Watchdog", "watchdog", "Main thread frozen", "Timeout", "Stalled",
        
        # Assembly/Low-Level - Errors
        "Instruction", "Opcode", "Register", "Memory access",
        "Invalid address", "Access violation", "Page fault", "Protection fault",
    ]
    
    def __init__(self):
        self.compiled_error_patterns = self._compile_error_patterns()
        self.compiled_specific_errors = self._compile_specific_errors()
    
    @staticmethod
    def _compile_error_patterns() -> Dict[str, List[re.Pattern]]:
        """Compile all error marker patterns"""
        patterns = {}
        
        for category, markers in ErrorDetector.ERROR_MARKERS.items():
            patterns[category] = [
                re.compile(rf'\b{re.escape(marker)}\b', re.IGNORECASE) 
                for marker in markers
            ]
        
        return patterns
    
    @staticmethod
    def _compile_specific_errors() -> List[re.Pattern]:
        """Compile specific error type patterns for prioritized matching"""
        return [
            re.compile(rf'\b{re.escape(error_type)}\b', re.IGNORECASE)
            for error_type in ErrorDetector.SPECIFIC_ERROR_TYPES
        ]
    
    def is_error_line(self, line: str) -> bool:
        """Check if line contains error indicators"""
        line = line.strip()
        
        # Check critical error markers
        for pattern in self.compiled_error_patterns["CRITICAL"]:
            if pattern.search(line):
                return True
        
        # Check major error keywords
        for pattern in self.compiled_error_patterns["MAJOR"]:
            if pattern.search(line):
                return True
        
        return False
    
    def is_stack_trace_line(self, line: str) -> bool:
        """Check if line is part of a stack trace"""
        line = line.strip()
        
        for pattern in self.compiled_error_patterns["STACK_TRACE_INDICATORS"]:
            if pattern.search(line):
                return True
        
        return False
    
    def detect_tool_type(self, error_lines: List[str]) -> str:
        """Detect the tool/language type from error content"""
        combined_text = '\n'.join(error_lines).lower()
        
        tool_scores = {
            "Python": 0,
            "Java": 0,
            "SQL": 0,
            "JavaScript": 0,
            "C++": 0,
            "Go": 0,
            "C#": 0,
            "Ruby": 0,
            "PHP": 0,
            "Node.js": 0,
            "C": 0,
            "Kernel": 0,
            "Ruby/Rails": 0,
            "Unknown": 1  # Default fallback
        }
        
        # Python detection
        if any(x in combined_text for x in ["traceback", ".py:", "python", "def ", "self."]):
            tool_scores["Python"] += 3
        if "traceback (most recent call last):" in combined_text:
            tool_scores["Python"] += 5
        if any(x in combined_text for x in ["unicodedecodeerror", "json.decoder", "redis.exceptions", "kafka.errors"]):
            tool_scores["Python"] += 3
        
        # Java detection
        if any(x in combined_text for x in ["at java.", "at com.", "at org.", "exception in thread"]):
            tool_scores["Java"] += 4
        if ".java:" in combined_text:
            tool_scores["Java"] += 2
        
        # SQL/PostgreSQL detection
        if any(x in combined_text for x in ["sql", "select ", "insert ", "from ", "sqlexception", "statement:"]):
            tool_scores["SQL"] += 3
        if any(x in combined_text for x in ["postgresql", "postgres", "pg::", "pgpl/"]):
            tool_scores["SQL"] += 3
        
        # JavaScript/Node.js detection
        if any(x in combined_text for x in [".js:", "typeerror", "referenceerror", "node.js"]):
            tool_scores["JavaScript"] += 3
        if "node.js" in combined_text:
            tool_scores["Node.js"] += 2
        
        # C++ detection (more comprehensive)
        if any(x in combined_text for x in [".cpp:", "segmentation fault", "core dumped", "std::"]):
            tool_scores["C++"] += 3
        if any(x in combined_text for x in ["sigabrt", "sigsegv", "sigbus", "sigill", "sigfpe"]):
            tool_scores["C++"] += 2
        if "backtrace:" in combined_text:
            tool_scores["C++"] += 1
        
        # C detection
        if any(x in combined_text for x in [".c:", "error:", "undeclared", "no match for"]):
            tool_scores["C"] += 3
        if "gcc" in combined_text or "make" in combined_text:
            tool_scores["C"] += 2
        
        # Kernel/Linux detection
        if any(x in combined_text for x in ["bug:", "kernel panic", "kernel null pointer", "tainted:", "rip:", "call trace:"]):
            tool_scores["Kernel"] += 5
        if "program received signal" in combined_text:
            tool_scores["Kernel"] += 2
        
        # Ruby/Rails detection
        if any(x in combined_text for x in [".rb:", "rails", "activerecord", "loaderror", "nomethoderror"]):
            tool_scores["Ruby/Rails"] += 3
        if any(x in combined_text for x in ["errno::", "pg::connectionbad", "activerecord"]):
            tool_scores["Ruby/Rails"] += 3
        
        # Go detection
        if any(x in combined_text for x in [".go:", "panic", "goroutine"]):
            tool_scores["Go"] += 3
        
        # C# detection
        if any(x in combined_text for x in [".csproj", ".cs:", "nullreferenceexception"]):
            tool_scores["C#"] += 3
        
        # PHP detection
        if any(x in combined_text for x in [".php:", "fatal error", "parse error"]):
            tool_scores["PHP"] += 3
        
        return max(tool_scores.items(), key=lambda x: x[1])[0]
    
    def extract_main_error(self, error_lines: List[str]) -> Optional[str]:
        """Extract the main error from a group of lines - prioritize specific error types"""
        # First, look for lines with specific error types (NameError, IndexError, etc.)
        specific_error_lines = []
        for line in error_lines:
            for pattern in self.compiled_specific_errors:
                if pattern.search(line):
                    specific_error_lines.append(line)
                    break
        
        # If we found specific error types, use those
        if specific_error_lines:
            # Find the most descriptive one (prefer lines with actual error message)
            main_error_line = specific_error_lines[0]
            for line in specific_error_lines:
                # Prefer lines that have more information (longer lines)
                if len(line) > len(main_error_line):
                    main_error_line = line
        else:
            # Fallback: Find all lines with general error indicators
            error_candidates = []
            
            for line in error_lines:
                # Check if this is actually an error line (not WARNING, DEBUG, INFO, etc.)
                error_keywords = ['error', 'fatal', 'critical', 'exception', 'traceback', 'throwable']
                if any(keyword.lower() in line.lower() for keyword in error_keywords):
                    # Skip retry and status messages
                    if not any(skip in line.lower() for skip in ['retry attempt', 'fallback', 'returning fallback', 
                                                                   'rollback', 'skipping', 'please check', 'verify']):
                        error_candidates.append(line)
            
            # If no candidates found, return None
            if not error_candidates:
                return None
            
            # Use the first non-status error
            main_error_line = error_candidates[0]
        
        # Remove log level markers
        line = re.sub(r'^\s*\[?(ERROR|FATAL|CRITICAL|EXCEPTION|Traceback|Exception)\]?\s*', '', main_error_line, flags=re.IGNORECASE)
        
        return line.strip() if line.strip() else None

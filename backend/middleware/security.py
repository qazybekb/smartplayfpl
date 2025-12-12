"""
Security middleware for SmartPlayFPL.

Implements critical security headers and protections following OWASP guidelines.
"""

import os
import re
import hashlib
import secrets
import logging
from typing import Optional, Set, Callable
from functools import wraps
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import Response, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("smartplayfpl.security")

# =============================================================================
# SECURITY CONFIGURATION
# =============================================================================

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Content Security Policy
CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "font-src 'self' data:; "
    "connect-src 'self' https://fantasy.premierleague.com https://api.anthropic.com; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self';"
)

# Allowed SPARQL query patterns (whitelist approach)
ALLOWED_SPARQL_PATTERNS = [
    r"^SELECT\s+\?",  # SELECT queries only
    r"^ASK\s+",       # ASK queries
    r"^DESCRIBE\s+",  # DESCRIBE queries
]

# Forbidden SPARQL keywords
FORBIDDEN_SPARQL_KEYWORDS = {
    "DELETE", "DROP", "INSERT", "UPDATE", "CLEAR", "CREATE",
    "LOAD", "COPY", "MOVE", "ADD", "WITH"
}


# =============================================================================
# SECURITY HEADERS MIDDLEWARE
# =============================================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all responses.

    Headers added:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    - Content-Security-Policy (in production)
    - Strict-Transport-Security (HSTS in production)
    - Permissions-Policy
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Always add these headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Production-only headers
        if not DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Content-Security-Policy"] = CSP_POLICY

        # Remove potentially dangerous headers
        if "Server" in response.headers:
            del response.headers["Server"]
        if "X-Powered-By" in response.headers:
            del response.headers["X-Powered-By"]

        return response


# =============================================================================
# SPARQL INJECTION PROTECTION
# =============================================================================

def validate_sparql_query(query: str) -> tuple[bool, str]:
    """
    Validate SPARQL query for injection attacks.

    Returns:
        (is_valid, error_message)
    """
    if not query:
        return False, "Query cannot be empty"

    # Normalize query
    query_upper = query.upper().strip()

    # Check for forbidden keywords
    for keyword in FORBIDDEN_SPARQL_KEYWORDS:
        # Use word boundary matching to avoid false positives
        if re.search(rf'\b{keyword}\b', query_upper):
            logger.warning(f"SPARQL injection attempt detected: {keyword}")
            return False, f"Forbidden keyword in query: {keyword}"

    # Check if query matches allowed patterns
    is_allowed = False
    for pattern in ALLOWED_SPARQL_PATTERNS:
        if re.match(pattern, query_upper):
            is_allowed = True
            break

    if not is_allowed:
        logger.warning(f"SPARQL query pattern not allowed: {query[:50]}...")
        return False, "Only SELECT, ASK, and DESCRIBE queries are allowed"

    # Additional validation: Check for suspicious patterns
    suspicious_patterns = [
        r"OPTIONAL\s*\{\s*OPTIONAL",  # Nested OPTIONAL DoS
        r"(SELECT|WHERE)\s*\{[^}]*\{[^}]*\{[^}]*\{",  # Deep nesting
        r"FILTER\s*\(\s*1\s*=\s*1\s*\)",  # Always-true filter
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, query_upper):
            logger.warning(f"Suspicious SPARQL pattern detected")
            return False, "Query contains suspicious patterns"

    # Limit query length
    if len(query) > 2000:
        return False, "Query exceeds maximum length (2000 characters)"

    return True, ""


class SPARQLQueryValidator:
    """
    Secure SPARQL query executor with validation.
    """

    def __init__(self, max_results: int = 1000):
        self.max_results = max_results

    def sanitize_query(self, query: str) -> str:
        """
        Sanitize SPARQL query by adding safety constraints.
        """
        query = query.strip()

        # Add LIMIT if not present
        if "LIMIT" not in query.upper():
            query = f"{query} LIMIT {self.max_results}"
        else:
            # Enforce maximum limit
            limit_match = re.search(r'LIMIT\s+(\d+)', query, re.IGNORECASE)
            if limit_match:
                current_limit = int(limit_match.group(1))
                if current_limit > self.max_results:
                    query = re.sub(
                        r'LIMIT\s+\d+',
                        f'LIMIT {self.max_results}',
                        query,
                        flags=re.IGNORECASE
                    )

        return query

    def validate_and_sanitize(self, query: str) -> tuple[str, Optional[str]]:
        """
        Validate and sanitize query.

        Returns:
            (sanitized_query, error_message)
            error_message is None if valid
        """
        is_valid, error = validate_sparql_query(query)
        if not is_valid:
            return "", error

        return self.sanitize_query(query), None


# =============================================================================
# JSON SCHEMA VALIDATION FOR AI RESPONSES
# =============================================================================

def validate_json_structure(data: dict, expected_keys: Set[str]) -> tuple[bool, str]:
    """
    Validate JSON structure from AI responses.

    Args:
        data: Parsed JSON data
        expected_keys: Set of expected top-level keys

    Returns:
        (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Response must be a JSON object"

    # Check for unexpected keys that might indicate injection
    actual_keys = set(data.keys())
    unexpected_keys = actual_keys - expected_keys - {"_metadata", "_version"}

    if len(unexpected_keys) > 5:  # Allow some flexibility
        logger.warning(f"Unexpected keys in AI response: {unexpected_keys}")

    return True, ""


def sanitize_ai_text(text: str) -> str:
    """
    Sanitize text from AI responses to prevent XSS.
    """
    if not text:
        return ""

    # Remove potential script tags
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)

    # Remove event handlers
    text = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', text, flags=re.IGNORECASE)

    # Escape basic HTML entities
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')

    return text


# =============================================================================
# SECURE DEBUG ENDPOINT
# =============================================================================

def require_debug_auth(func: Callable) -> Callable:
    """
    Decorator to require authentication for debug endpoints.
    Uses a simple secret token approach for development.
    """
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        if not DEBUG:
            raise HTTPException(
                status_code=404,
                detail="Not found"
            )

        # Check for debug auth token
        debug_token = os.getenv("DEBUG_AUTH_TOKEN")
        if debug_token:
            provided_token = request.headers.get("X-Debug-Token")
            if not provided_token or not secrets.compare_digest(provided_token, debug_token):
                raise HTTPException(
                    status_code=403,
                    detail="Invalid debug token"
                )

        return await func(request, *args, **kwargs)

    return wrapper


# =============================================================================
# RATE LIMITING HELPERS
# =============================================================================

def get_client_identifier(request: Request) -> str:
    """
    Get a consistent client identifier for rate limiting.
    Uses IP + User-Agent hash to prevent simple bypasses.
    """
    # Get forwarded IP if behind proxy
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"

    # Add user agent for additional entropy
    user_agent = request.headers.get("User-Agent", "")

    # Create hash
    identifier = f"{ip}:{user_agent[:50]}"
    return hashlib.sha256(identifier.encode()).hexdigest()[:16]


# =============================================================================
# INPUT SANITIZATION
# =============================================================================

def sanitize_string_input(value: str, max_length: int = 1000) -> str:
    """
    Sanitize string input to prevent injection attacks.
    """
    if not value:
        return ""

    # Truncate to max length
    value = value[:max_length]

    # Remove null bytes
    value = value.replace('\x00', '')

    # Remove control characters except newlines and tabs
    value = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)

    return value.strip()


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal.
    """
    if not filename:
        return ""

    # Remove path separators
    filename = os.path.basename(filename)

    # Remove suspicious characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)

    # Prevent hidden files
    filename = filename.lstrip('.')

    return filename[:255]  # Max filename length


# =============================================================================
# SECURE PICKLE LOADING
# =============================================================================

class SecureUnpickler:
    """
    Secure pickle loading with restricted classes.

    Only allows loading of specific safe classes.
    """

    # Whitelist of allowed modules and classes
    ALLOWED_MODULES = {
        'sklearn.linear_model._base',
        'sklearn.linear_model._ridge',
        'sklearn.ensemble._forest',
        'sklearn.ensemble._gb',
        'sklearn.tree._classes',
        'sklearn.preprocessing._data',
        'sklearn.pipeline',
        'sklearn.compose._column_transformer',
        'numpy',
        'numpy.core.multiarray',
        'lightgbm.basic',
        'lightgbm.sklearn',
        'xgboost.core',
        'xgboost.sklearn',
        'pandas.core.frame',
        'pandas.core.series',
    }

    @classmethod
    def restricted_loads(cls, data: bytes):
        """
        Load pickle with restrictions.
        Raises ValueError if unsafe classes detected.
        """
        import pickle
        import io

        class RestrictedUnpickler(pickle.Unpickler):
            def find_class(self, module, name):
                # Check if module is in whitelist
                if module in cls.ALLOWED_MODULES:
                    return super().find_class(module, name)

                # Check for safe builtins
                if module == 'builtins' and name in ('dict', 'list', 'tuple', 'set', 'frozenset'):
                    return super().find_class(module, name)

                raise ValueError(f"Unsafe pickle class: {module}.{name}")

        return RestrictedUnpickler(io.BytesIO(data)).load()


# =============================================================================
# API KEY MASKING
# =============================================================================

def mask_api_key(key: Optional[str]) -> str:
    """
    Mask API key for safe logging/display.
    Shows only first 4 and last 4 characters.
    """
    if not key:
        return "[not set]"
    if len(key) < 12:
        return "[invalid key format]"
    return f"{key[:4]}...{key[-4:]}"


def mask_sensitive_data(data: dict, sensitive_keys: Set[str]) -> dict:
    """
    Recursively mask sensitive data in a dictionary.
    """
    result = {}
    for key, value in data.items():
        if key.lower() in sensitive_keys or any(s in key.lower() for s in ['key', 'secret', 'password', 'token']):
            if isinstance(value, str):
                result[key] = mask_api_key(value)
            else:
                result[key] = "[redacted]"
        elif isinstance(value, dict):
            result[key] = mask_sensitive_data(value, sensitive_keys)
        else:
            result[key] = value
    return result


# =============================================================================
# MIDDLEWARE REGISTRATION
# =============================================================================

def add_security_middleware(app: FastAPI):
    """
    Add all security middleware to FastAPI app.
    """
    app.add_middleware(SecurityHeadersMiddleware)
    logger.info("Security middleware registered")

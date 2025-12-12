"""
Global error handling middleware for SmartPlayFPL.

Provides consistent error responses across all API endpoints by handling
common exception types at the application level.
"""

import logging
import traceback
import uuid
from datetime import datetime
from typing import Optional

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger("smartplayfpl.errors")


# =============================================================================
# STANDARD ERROR RESPONSE MODEL
# =============================================================================

class ErrorDetail(BaseModel):
    """Detailed error information."""
    code: str
    message: str
    field: Optional[str] = None


class ErrorResponse(BaseModel):
    """
    Standard error response format for all API errors.

    Example:
    {
        "success": false,
        "error": {
            "code": "FPL_API_ERROR",
            "message": "Failed to fetch team data from FPL API",
            "field": null
        },
        "request_id": "abc123...",
        "timestamp": "2024-01-15T10:30:00Z"
    }
    """
    success: bool = False
    error: ErrorDetail
    request_id: str
    timestamp: str


def create_error_response(
    status_code: int,
    code: str,
    message: str,
    request_id: str,
    field: Optional[str] = None
) -> JSONResponse:
    """Create a standardized JSON error response."""
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            success=False,
            error=ErrorDetail(
                code=code,
                message=message,
                field=field
            ),
            request_id=request_id,
            timestamp=datetime.utcnow().isoformat() + "Z"
        ).model_dump()
    )


# =============================================================================
# EXCEPTION HANDLERS
# =============================================================================

async def fpl_api_error_handler(request: Request, exc: httpx.HTTPStatusError) -> JSONResponse:
    """
    Handle FPL API HTTP errors.
    Maps FPL API status codes to appropriate client responses.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:8])
    fpl_status = exc.response.status_code

    if fpl_status == 404:
        logger.warning(f"[{request_id}] FPL resource not found: {exc.request.url}")
        return create_error_response(
            status_code=404,
            code="RESOURCE_NOT_FOUND",
            message="The requested FPL resource was not found. Please check the team ID or player ID.",
            request_id=request_id
        )
    elif fpl_status == 429:
        logger.warning(f"[{request_id}] FPL API rate limited")
        return create_error_response(
            status_code=429,
            code="FPL_RATE_LIMITED",
            message="FPL API rate limit exceeded. Please try again in a few minutes.",
            request_id=request_id
        )
    elif fpl_status >= 500:
        logger.error(f"[{request_id}] FPL API server error: {fpl_status}")
        return create_error_response(
            status_code=502,
            code="FPL_API_UNAVAILABLE",
            message="FPL API is currently unavailable. Please try again later.",
            request_id=request_id
        )
    else:
        logger.error(f"[{request_id}] FPL API error: {fpl_status} - {exc}")
        return create_error_response(
            status_code=502,
            code="FPL_API_ERROR",
            message=f"Error communicating with FPL API (status {fpl_status})",
            request_id=request_id
        )


async def httpx_timeout_handler(request: Request, exc: httpx.TimeoutException) -> JSONResponse:
    """Handle HTTP request timeouts."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:8])
    logger.warning(f"[{request_id}] Request timeout: {exc}")
    return create_error_response(
        status_code=504,
        code="GATEWAY_TIMEOUT",
        message="Request to external service timed out. Please try again.",
        request_id=request_id
    )


async def httpx_connection_handler(request: Request, exc: httpx.RequestError) -> JSONResponse:
    """Handle HTTP connection errors."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:8])
    logger.error(f"[{request_id}] Connection error: {exc}")
    return create_error_response(
        status_code=502,
        code="CONNECTION_ERROR",
        message="Failed to connect to external service. Please try again later.",
        request_id=request_id
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle FastAPI HTTPExceptions with standard format.
    Preserves the original status code and detail message.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:8])

    # Map common status codes to error codes
    code_mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
        504: "GATEWAY_TIMEOUT",
    }

    error_code = code_mapping.get(exc.status_code, f"HTTP_{exc.status_code}")

    return create_error_response(
        status_code=exc.status_code,
        code=error_code,
        message=str(exc.detail),
        request_id=request_id
    )


async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle validation errors."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:8])
    logger.warning(f"[{request_id}] Validation error: {exc}")
    return create_error_response(
        status_code=400,
        code="VALIDATION_ERROR",
        message=str(exc),
        request_id=request_id
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler for unhandled exceptions.
    Logs the full traceback but returns a generic message to the client.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:8])
    logger.error(f"[{request_id}] Unhandled exception: {exc}")
    logger.error(traceback.format_exc())

    return create_error_response(
        status_code=500,
        code="INTERNAL_ERROR",
        message=str(exc),
        request_id=request_id
    )


# =============================================================================
# REQUEST ID MIDDLEWARE
# =============================================================================

async def add_request_id_middleware(request: Request, call_next):
    """
    Middleware to add a unique request ID to each request.
    This ID is included in error responses for debugging.
    """
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    return response


# =============================================================================
# API CALL LOGGING MIDDLEWARE
# =============================================================================

# AI endpoints that should be flagged
AI_ENDPOINTS = {
    "/api/crowd-insights-ai/",
    "/api/gw-review-ai/",
    "/api/sell-analysis/",
    "/api/buy-analysis/",
    "/api/squad-analysis/",
}


def extract_team_id(path: str) -> Optional[int]:
    """Extract team_id from API path if present."""
    import re
    # Match patterns like /api/team/123 or /api/alerts/456
    match = re.search(r'/(\d+)(?:/|$)', path)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def is_ai_endpoint(path: str) -> bool:
    """Check if the path is an AI endpoint."""
    return any(path.startswith(ai_path) for ai_path in AI_ENDPOINTS)


async def api_logging_middleware(request: Request, call_next):
    """
    Middleware to log all API calls to the database.
    Captures request/response metadata for observability.
    """
    import time
    from database import SessionLocal, APICallLog

    start_time = time.time()

    # Get request info
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:8])
    method = request.method
    path = request.url.path
    query_params = str(request.query_params) if request.query_params else None
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")[:500]

    # Process request
    response = await call_next(request)

    # Calculate response time
    response_time_ms = (time.time() - start_time) * 1000

    # Extract context
    team_id = extract_team_id(path)
    is_ai = is_ai_endpoint(path)

    # Get error info if present (from response headers or body)
    error_code = None
    error_message = None
    if response.status_code >= 400:
        error_code = response.headers.get("X-Error-Code")

    # Skip logging for health checks and static files to reduce noise
    skip_paths = {"/api/health", "/", "/favicon.ico", "/docs", "/openapi.json"}
    if path in skip_paths:
        return response

    # Log to database (async-safe)
    try:
        db = SessionLocal()
        log_entry = APICallLog(
            request_id=request_id,
            method=method,
            path=path[:255],
            query_params=query_params,
            client_ip=client_ip,
            user_agent=user_agent,
            status_code=response.status_code,
            response_time_ms=response_time_ms,
            error_code=error_code,
            error_message=error_message,
            team_id=team_id,
            is_ai_endpoint=is_ai,
        )
        db.add(log_entry)
        db.commit()
        db.close()
    except Exception as e:
        logger.warning(f"Failed to log API call: {e}")

    return response


# =============================================================================
# REGISTRATION FUNCTION
# =============================================================================

def register_error_handlers(app: FastAPI, enable_logging: bool = True) -> None:
    """
    Register all error handlers with the FastAPI application.

    Call this after creating the FastAPI app:
        app = FastAPI(...)
        register_error_handlers(app)

    Args:
        app: FastAPI application instance
        enable_logging: Whether to enable API call logging to database (default: True)
    """
    # Add request ID middleware (must be first to generate request_id)
    app.middleware("http")(add_request_id_middleware)

    # Add API logging middleware (after request ID so it has access to request_id)
    if enable_logging:
        app.middleware("http")(api_logging_middleware)
        logger.info("API call logging enabled")

    # Register exception handlers (order matters - most specific first)
    app.add_exception_handler(httpx.HTTPStatusError, fpl_api_error_handler)
    app.add_exception_handler(httpx.TimeoutException, httpx_timeout_handler)
    app.add_exception_handler(httpx.RequestError, httpx_connection_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(ValueError, value_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    logger.info("Error handlers registered")

"""
API Versioning infrastructure for SmartPlayFPL.

Provides URL-based and header-based API versioning support.

Versioning strategies:
1. URL Path: /api/v1/players, /api/v2/players
2. Header: X-API-Version: v1
3. Query Param: /api/players?version=v1

Current version: v1
"""

from enum import Enum
from typing import Optional, Callable
from functools import wraps
from fastapi import APIRouter, Header, Query, HTTPException, Request
from fastapi.routing import APIRoute
import logging

logger = logging.getLogger("smartplayfpl.versioning")


# =============================================================================
# VERSION DEFINITIONS
# =============================================================================

class APIVersion(str, Enum):
    """Supported API versions."""
    V1 = "v1"
    V2 = "v2"  # Future version placeholder

    @classmethod
    def from_string(cls, value: str) -> "APIVersion":
        """Parse version string to enum."""
        value = value.lower().strip()
        if not value.startswith("v"):
            value = f"v{value}"
        try:
            return cls(value)
        except ValueError:
            raise ValueError(f"Unsupported API version: {value}")


# Current default version
CURRENT_VERSION = APIVersion.V1
SUPPORTED_VERSIONS = [APIVersion.V1]  # Add V2 when ready


# =============================================================================
# VERSION DETECTION
# =============================================================================

def get_api_version(
    request: Request,
    x_api_version: Optional[str] = Header(None, alias="X-API-Version"),
    version: Optional[str] = Query(None, description="API version"),
) -> APIVersion:
    """
    Detect API version from request.

    Priority:
    1. URL path (if using versioned router)
    2. X-API-Version header
    3. Query parameter
    4. Default to current version
    """
    # Check URL path for version
    path = request.url.path
    for v in SUPPORTED_VERSIONS:
        if f"/api/{v.value}/" in path:
            return v

    # Check header
    if x_api_version:
        try:
            return APIVersion.from_string(x_api_version)
        except ValueError as e:
            logger.warning(f"Invalid version header: {x_api_version}")

    # Check query param
    if version:
        try:
            return APIVersion.from_string(version)
        except ValueError as e:
            logger.warning(f"Invalid version query param: {version}")

    # Default
    return CURRENT_VERSION


# =============================================================================
# VERSIONED ROUTER
# =============================================================================

class VersionedAPIRouter(APIRouter):
    """
    Router that supports API versioning.

    Usage:
        router = VersionedAPIRouter(version=APIVersion.V1)

        @router.get("/players")
        async def get_players():
            ...

    This creates endpoints at /api/v1/players
    """

    def __init__(
        self,
        version: APIVersion = CURRENT_VERSION,
        prefix: str = "",
        **kwargs
    ):
        # Prepend version to prefix
        versioned_prefix = f"/api/{version.value}{prefix}"
        super().__init__(prefix=versioned_prefix, **kwargs)
        self.api_version = version

    def add_api_route(
        self,
        path: str,
        endpoint: Callable,
        **kwargs
    ):
        """Override to inject version info into endpoint."""
        # Add version info to route metadata
        if "tags" not in kwargs:
            kwargs["tags"] = []
        kwargs["tags"].append(f"API {self.api_version.value}")

        # Add version to response headers
        original_endpoint = endpoint

        @wraps(original_endpoint)
        async def versioned_endpoint(*args, **kw):
            from fastapi import Response
            response: Response = kw.get("response")
            if response:
                response.headers["X-API-Version"] = self.api_version.value
            return await original_endpoint(*args, **kw)

        super().add_api_route(path, versioned_endpoint, **kwargs)


# =============================================================================
# VERSION DEPRECATION
# =============================================================================

def deprecated(
    version: APIVersion,
    removal_version: Optional[APIVersion] = None,
    message: Optional[str] = None,
):
    """
    Decorator to mark an endpoint as deprecated.

    Usage:
        @router.get("/old-endpoint")
        @deprecated(version=APIVersion.V1, removal_version=APIVersion.V2)
        async def old_endpoint():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from fastapi import Response
            response: Response = kwargs.get("response")
            if response:
                deprecation_msg = f"This endpoint is deprecated in {version.value}"
                if removal_version:
                    deprecation_msg += f" and will be removed in {removal_version.value}"
                if message:
                    deprecation_msg += f". {message}"

                response.headers["X-Deprecation-Warning"] = deprecation_msg
                logger.warning(f"Deprecated endpoint called: {func.__name__}")

            return await func(*args, **kwargs)
        return wrapper
    return decorator


# =============================================================================
# VERSION-SPECIFIC BEHAVIOR
# =============================================================================

def version_switch(
    v1_handler: Callable,
    v2_handler: Optional[Callable] = None,
):
    """
    Create an endpoint that behaves differently based on API version.

    Usage:
        @router.get("/data")
        @version_switch(
            v1_handler=get_data_v1,
            v2_handler=get_data_v2,
        )
        async def get_data(version: APIVersion = Depends(get_api_version)):
            ...
    """
    async def handler(version: APIVersion, *args, **kwargs):
        if version == APIVersion.V1:
            return await v1_handler(*args, **kwargs)
        elif version == APIVersion.V2 and v2_handler:
            return await v2_handler(*args, **kwargs)
        else:
            # Default to v1 behavior
            return await v1_handler(*args, **kwargs)

    return handler


# =============================================================================
# VERSION INFO ENDPOINT
# =============================================================================

def create_version_info_endpoint(router: APIRouter):
    """Add a version info endpoint to a router."""

    @router.get("/version")
    async def get_version_info():
        """Get API version information."""
        return {
            "current_version": CURRENT_VERSION.value,
            "supported_versions": [v.value for v in SUPPORTED_VERSIONS],
            "deprecated_versions": [],  # Add when versions are deprecated
        }


# =============================================================================
# MIGRATION HELPERS
# =============================================================================

class VersionMigration:
    """
    Helper class for version migrations.

    Usage:
        migration = VersionMigration()

        @migration.transform(APIVersion.V1, APIVersion.V2)
        def transform_response(data: dict) -> dict:
            # Transform v1 response to v2 format
            return {...}
    """

    def __init__(self):
        self._transformers: dict[tuple, Callable] = {}

    def transform(self, from_version: APIVersion, to_version: APIVersion):
        """Register a transformation function between versions."""
        def decorator(func: Callable) -> Callable:
            self._transformers[(from_version, to_version)] = func
            return func
        return decorator

    def apply(self, data: dict, from_version: APIVersion, to_version: APIVersion) -> dict:
        """Apply transformation if available."""
        key = (from_version, to_version)
        if key in self._transformers:
            return self._transformers[key](data)
        return data


# Global migration instance
migrations = VersionMigration()


# =============================================================================
# ROUTER FACTORY
# =============================================================================

def create_versioned_routers() -> dict[APIVersion, APIRouter]:
    """
    Create a set of versioned routers.

    Returns dict mapping version to router, allowing version-specific
    endpoint definitions.
    """
    return {v: VersionedAPIRouter(version=v) for v in SUPPORTED_VERSIONS}

"""Middleware package for EDON Gateway."""

from .auth import AuthMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Pass-through stub — rate limiting is handled in auth middleware."""
    async def dispatch(self, request: Request, call_next):
        return await call_next(request)


class ValidationMiddleware(BaseHTTPMiddleware):
    """Pass-through stub — validation is handled per-endpoint."""
    async def dispatch(self, request: Request, call_next):
        return await call_next(request)


class MagValidationMiddleware(BaseHTTPMiddleware):
    """Pass-through stub — MAG validation is handled per-endpoint."""
    async def dispatch(self, request: Request, call_next):
        return await call_next(request)


__all__ = [
    "AuthMiddleware",
    "RateLimitMiddleware",
    "ValidationMiddleware",
    "MagValidationMiddleware",
]

"""
Custom exceptions for application errors.
"""


class FatalValidationError(RuntimeError):
    """Fatal validation error that prevents application from starting."""
    pass


class AuthorizationError(ConnectionError):
    """Authentication/authorization failed."""
    pass


class ServiceUnavailableError(ConnectionError):
    """Service is temporarily unavailable."""
    pass


class ValidationError(RuntimeError):
    """General validation error."""
    pass


class InfraConnectionError(ConnectionError):
    """Infrastructure connection error for retry logic."""
    pass

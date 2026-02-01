import httpx
from infra.exceptions import (
    AuthorizationError,
    ServiceUnavailableError,
    ValidationError,
    FatalValidationError,
    InfraConnectionError,
)
from typing import Type

def map_httpx_error_to_exception(exc: httpx.HTTPError, context: str) -> BaseException:
    """Map httpx errors to exceptions (switch-case)."""
    match exc:
        case httpx.ConnectError():
            raise InfraConnectionError(f"{context}: connection failed") from exc
        case httpx.ReadTimeout() | httpx.ConnectTimeout():
            raise InfraConnectionError(f"{context}: timeout") from exc
        case httpx.RemoteProtocolError():
            raise InfraConnectionError(f"{context}: protocol error") from exc
        case httpx.LocalProtocolError():
            raise FatalValidationError(f"{context}: protocol error") from exc
        case httpx.NetworkError():
            raise InfraConnectionError(f"{context}: network error") from exc
        case httpx.HTTPStatusError():
            raise FatalValidationError(f"{context}: http status error")
        case _:
            raise FatalValidationError(f"{context}: {exc}")

def map_httpx_status_to_exception(status: int, context: str) -> Type[BaseException]:
    """Map HTTP status codes to exceptions (switch-case)."""
    match status:
        case 401 | 403:
            return AuthorizationError
        case 400:
            return ValidationError
        case 404:
            return FatalValidationError
        case 405:
            return FatalValidationError
        case 429:
            return ServiceUnavailableError
        case 500 | 502 | 503 | 504:
            return ServiceUnavailableError
        case _:
            return FatalValidationError

from __future__ import annotations

from wexample_helpers.errors.gateway_error import GatewayError


class GatewayConnectionError(GatewayError):
    """Raised when connection to the API fails."""

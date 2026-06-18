from __future__ import annotations

from wexample_helpers.error.gateway_error import GatewayError


class GatewayAuthenticationError(GatewayError):
    """Raised when authentication to the API fails."""

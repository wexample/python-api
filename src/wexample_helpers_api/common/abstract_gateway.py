from __future__ import annotations

import time
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import requests
from wexample_helpers.classes.field import public_field
from wexample_helpers.classes.mixin.has_snake_short_class_name_class_mixin import (
    HasSnakeShortClassNameClassMixin,
)
from wexample_helpers.classes.mixin.has_two_steps_init import HasTwoStepInit
from wexample_helpers.decorator.base_class import base_class
from wexample_helpers_api.enums.http import ContentType, HttpMethod
from wexample_prompt.mixins.with_io_manager import WithIoManager

if TYPE_CHECKING:
    from collections.abc import Mapping

    from wexample_helpers.const.types import StringsList
    from wexample_helpers_api.common.http_request_payload import HttpRequestPayload
    from wexample_helpers_api.enums.http import Header


@base_class
class AbstractGateway(
    HasSnakeShortClassNameClassMixin,
    WithIoManager,
    HasTwoStepInit,
):
    # Base configuration
    base_url: str | None = public_field(default=None, description="Base API URL")
    # State
    connected: bool = public_field(default=False, description="Connection state")
    # Default request configuration
    default_headers: dict[str, str] = public_field(
        factory=dict, description="Default headers for requests"
    )
    last_exception: Any = public_field(
        default=None, description="Last exception encountered during request"
    )
    last_request_time: float | None = public_field(
        default=None, description="Timestamp of last request"
    )
    quiet: bool = public_field(
        default=False, description="If True, only show errors and warnings"
    )
    rate_limit_delay: float = public_field(
        default=1.0, description="Minimum delay between requests in seconds"
    )
    timeout: int = public_field(default=30, description="Request timeout in seconds")

    @classmethod
    def get_class_name_suffix(cls) -> str | None:
        return "GatewayService"

    def check_connexion(self) -> bool:
        return self.connected

    def check_status_code(self, expected_status_codes: int | list[int] = 200) -> bool:
        return (
            self.make_request(
                endpoint="", expected_status_codes=expected_status_codes, quiet=True
            )
            is not None
        )

    def clear_error(self) -> None:
        self.last_exception = None

    def connect(self) -> bool:
        self.connected = True
        return True

    def format_response_content(self, response: requests.Response | None) -> str:
        """Extract and format response content for logging."""
        if response is None:
            return "Null response"

        try:
            return response.json()
        except (ValueError, AttributeError):
            return response.text

    def get_base_url(self) -> str | None:
        return self.base_url

    def get_expected_env_keys(self) -> StringsList:
        return []

    def get_last_error(self) -> Exception | None:
        return self.last_exception

    def handle_api_response(
        self,
        response: requests.Response | None,
        request_context: HttpRequestPayload,
        exception: Exception | None = None,
        fatal_on_error: bool = False,
        quiet: bool | None = None,
    ) -> requests.Response | None:
        self.last_exception = exception
        is_quiet = self.quiet if quiet is None else quiet

        if response is None:
            if not is_quiet:
                self.io.properties(
                    self._create_request_details(request_context),
                    title="Request Details",
                )
            if exception:
                self.io.error(str(exception), exception=exception, fatal=fatal_on_error)
            return None

        if not is_quiet:
            self.io.debug(
                message=f"{request_context.method} | {response.status_code} -> {request_context.url}",
                symbol="🌍",
            )

        if response.status_code in request_context.expected_status_codes:
            return response

        # Combine request details with response content
        details = {
            **self._create_request_details(request_context, response.status_code),
            "Response Content": self.format_response_content(response),
        }

        if not is_quiet:
            self.io.properties(details, title="Request Details")

        self.io.error(
            message=(
                str(exception) if exception else self._extract_error_message(response)
            ),
            exception=exception,
            fatal=fatal_on_error,
        )
        return response

    def has_error(self) -> bool:
        return self.last_exception is not None

    def make_request(
        self,
        endpoint: str,
        method: HttpMethod = HttpMethod.GET,
        data: dict[str, Any] | bytes | None = None,
        query_params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        files: dict[str, Any] | list[tuple] | None = None,
        call_origin: str | None = None,
        expected_status_codes: int | list[int] | None = None,
        fatal_if_unexpected: bool = False,
        quiet: bool = False,
        stream: bool = False,
        timeout: int | None = None,
        raise_exceptions: bool = False,
    ) -> requests.Response | None:
        from wexample_helpers.errors.gateway_error import GatewayError
        from wexample_helpers_api.common.http_request_payload import HttpRequestPayload
        from wexample_helpers_api.enums.http import Header

        payload = HttpRequestPayload.from_endpoint(
            base_url=self.get_base_url(),
            endpoint=endpoint,
            method=method,
            data=data,
            query_params=query_params,
            headers={**self.default_headers, **(headers or {})},
            call_origin=call_origin,
            expected_status_codes=expected_status_codes,
        )

        if not self.connected:
            self.connect()

        self._handle_rate_limiting()

        # Determine how to send the data based on Content-Type header
        content_type = self._get_header_value(payload.headers, Header.CONTENT_TYPE)

        if files:
            content_type = ContentType.MULTIPART.value
            payload.headers.pop(Header.CONTENT_TYPE.value, None)

        if payload.data is not None:
            if isinstance(payload.data, bytes):
                self.io.log(f"Sending binary payload ({len(payload.data)} bytes)")
            else:
                self.io.log(f"Sending {type(payload.data).__name__} payload")

        request_kwargs: dict[str, Any] = {
            "method": payload.method.value,
            "url": payload.url,
            "params": payload.query_params,
            "headers": payload.headers,
            "timeout": timeout or self.timeout,
            "stream": stream,
        }

        if files:
            request_kwargs["data"] = data or {}
            request_kwargs["files"] = files
        elif content_type in (
            ContentType.FORM_URLENCODED.value,
            ContentType.OCTET_STREAM.value,
        ):
            request_kwargs["data"] = data
        else:
            request_kwargs["json"] = data

        try:
            response = requests.request(**request_kwargs)
        except requests.exceptions.RequestException as exc:
            gateway_error = GatewayError(f"Request failed: {exc}")
            gateway_error.__cause__ = exc

            if raise_exceptions:
                raise gateway_error

            return self.handle_api_response(
                response=None,
                request_context=payload,
                exception=gateway_error,
                fatal_on_error=fatal_if_unexpected,
                quiet=quiet,
            )

        expected = (
            {expected_status_codes}
            if isinstance(expected_status_codes, int)
            else set(expected_status_codes or {200})
        )
        exception = None
        if response.status_code not in expected:
            exception = GatewayError(self._extract_error_message(response))
            if raise_exceptions and exception:
                raise exception

        return self.handle_api_response(
            response=response,
            request_context=payload,
            exception=exception,
            fatal_on_error=fatal_if_unexpected,
            quiet=quiet,
        )

    def setup(self) -> AbstractGateway:
        if self.default_headers is None:
            self.default_headers = {}

        return self

    def _create_request_details(
        self, request_context: HttpRequestPayload, status_code: int | None = None
    ) -> dict[str, Any]:
        """Create request details dictionary for logging."""
        from wexample_helpers.helpers.cli import cli_make_clickable_path

        details: dict[str, Any] = {
            "URL": request_context.url,
            "Method": request_context.method,
        }
        if request_context.call_origin:
            details["Call Origin"] = cli_make_clickable_path(
                request_context.call_origin
            )
        if request_context.data:
            if isinstance(request_context.data, bytes):
                details["Data"] = f"<Binary data: {len(request_context.data)} bytes>"
            else:
                details["Data"] = request_context.data
        if request_context.query_params:
            details["Query Parameters"] = request_context.query_params
        if status_code is not None:
            details["Status"] = status_code
        return details

    def _extract_error_message(self, response: requests.Response) -> str:
        """Extract error message from response."""
        message = f"HTTP {response.status_code}"
        try:
            data = response.json()
            if isinstance(data, dict):
                message = data.get("message", data.get("error", message))
        except (ValueError, AttributeError):
            if response.text:
                message = response.text
        return message

    def _get_header_value(
        self,
        headers: Mapping[str, str] | None,
        name: Header,
    ) -> str | None:
        """
        Case-insensitive lookup of a header followed by normalisation:
        - keep only the part before the first ';'
        - trim whitespace
        - convert to lower-case
        """
        if not headers:
            return None
        raw = next(
            (v for k, v in headers.items() if k.lower() == name.value.lower()),
            None,
        )
        if raw is None:
            return None

        return raw.split(";", 1)[0].strip().lower() or None

    def _handle_rate_limiting(self) -> None:
        if self.last_request_time is not None:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.rate_limit_delay:
                time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

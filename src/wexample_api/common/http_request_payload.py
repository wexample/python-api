from __future__ import annotations

from typing import Any

from wexample_helpers.classes.base_class import BaseClass
from wexample_helpers.classes.field import public_field
from wexample_helpers.decorator.base_class import base_class

from wexample_api.enums.http import HttpMethod


@base_class
class HttpRequestPayload(BaseClass):
    call_origin: str | None = public_field(
        default=None,
        description="Optional identifier of the request origin",
    )
    data: dict[str, Any] | bytes | None = public_field(
        default=None,
        description="Request body as a dictionary, raw bytes, or None",
    )
    expected_status_codes: list[int] | None = public_field(
        default=None,
        description="Optional list of expected HTTP status codes. If None, all responses are accepted.",
    )
    headers: dict[str, str] | None = public_field(
        default=None,
        description="Optional HTTP headers for the request",
    )
    method: HttpMethod = public_field(
        default=HttpMethod.GET,
        description="HTTP method to use for the request",
    )
    query_params: dict[str, Any] | None = public_field(
        default=None,
        description="Optional query parameters to append to the URL",
    )
    url: str = public_field(
        description="Target URL for the HTTP request",
    )

    @classmethod
    def from_endpoint(
        cls,
        base_url: str | None,
        endpoint: str,
        method: HttpMethod = HttpMethod.GET,
        data: dict[str, Any] | bytes | None = None,
        query_params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        call_origin: str | None = None,
        expected_status_codes: int | list[int] | None = None,
    ) -> HttpRequestPayload:
        if base_url:
            url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        else:
            url = endpoint

        if isinstance(expected_status_codes, int):
            expected_status_codes = [expected_status_codes]

        return cls(
            url=url,
            method=method,
            data=data,
            query_params=query_params,
            headers=headers,
            call_origin=call_origin,
            expected_status_codes=expected_status_codes,
        )

    @classmethod
    def from_url(cls, url: str, call_origin: str | None = None) -> HttpRequestPayload:
        return cls(url=url, call_origin=call_origin)

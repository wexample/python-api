from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from wexample_helpers_api.enums.http import HttpMethod


class HttpRequestPayload(BaseModel):
    call_origin: str | None = None
    data: dict[str, Any] | bytes | None = None
    expected_status_codes: list[int] = [200]
    headers: dict[str, str] | None = None
    method: HttpMethod = HttpMethod.GET
    query_params: dict[str, Any] | None = None
    url: str

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
        elif expected_status_codes is None:
            expected_status_codes = [200]

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

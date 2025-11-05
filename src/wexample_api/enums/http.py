from __future__ import annotations

from enum import Enum


class HttpMethod(Enum):
    GET: str = "GET"
    POST: str = "POST"
    PUT: str = "PUT"
    DELETE: str = "DELETE"
    PATCH: str = "PATCH"
    OPTIONS: str = "OPTIONS"
    HEAD: str = "HEAD"


class ContentType(Enum):
    JSON: str = "application/json"
    FORM_URLENCODED: str = "application/x-www-form-urlencoded"
    MULTIPART: str = "multipart/form-data"
    TEXT: str = "text/plain"
    OCTET_STREAM: str = "application/octet-stream"


class Header(Enum):
    CONTENT_TYPE: str = "Content-Type"
    AUTHORIZATION: str = "Authorization"

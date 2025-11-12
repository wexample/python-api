from __future__ import annotations

from wexample_api.enums.http import HttpMethod

HTTP_METHOD_MAP = {
    "GET": HttpMethod.GET,
    "POST": HttpMethod.POST,
    "PUT": HttpMethod.PUT,
    "DELETE": HttpMethod.DELETE,
    "PATCH": HttpMethod.PATCH,
    "OPTIONS": HttpMethod.OPTIONS,
    "HEAD": HttpMethod.HEAD,
}

"""Safe redirect handling for Streamable HTTP test requests."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from requests.models import DEFAULT_REDIRECT_LIMIT

from openapi_to_mcp.adapters.testing.models import ServerConnectionError

_DEFAULT_PORTS = {"http": 80, "https": 443}
_REDIRECT_STATUS_MIN = 300
_REDIRECT_STATUS_MAX = 400


def _same_origin_redirect_url(
    source_url: str, response: requests.Response
) -> str | None:
    location = response.headers.get("Location")
    if response.status_code not in {307, 308} or not location:
        return None
    source = urlsplit(source_url)
    target = urlsplit(urljoin(source_url, location))
    if (source.username, source.password) != (target.username, target.password):
        return None
    source_port = source.port or _DEFAULT_PORTS.get(source.scheme)
    target_port = target.port or _DEFAULT_PORTS.get(target.scheme)
    source_origin = source.scheme, source.hostname, source_port
    target_origin = target.scheme, target.hostname, target_port
    if source_origin == target_origin:
        return target.geturl()
    if (
        source.scheme == "http"
        and source_origin[2] == _DEFAULT_PORTS["http"]
        and target.scheme == "https"
        and target_origin[2] == _DEFAULT_PORTS["https"]
        and source.hostname == target.hostname
    ):
        return target.geturl()
    return None


def post_with_safe_redirects(
    endpoint_url: str, payload: dict[str, Any], headers: dict[str, str]
) -> tuple[requests.Response, str]:
    """Post one JSON-RPC payload without forwarding it to an unsafe redirect."""
    redirect_count = 0
    while True:
        response = requests.post(
            endpoint_url,
            json=payload,
            timeout=30,
            headers=headers,
            allow_redirects=False,
        )
        redirect_url = _same_origin_redirect_url(endpoint_url, response)
        if redirect_url is None:
            if _REDIRECT_STATUS_MIN <= response.status_code < _REDIRECT_STATUS_MAX:
                raise ServerConnectionError(
                    "Streamable HTTP redirect was not followed."
                )
            return response, endpoint_url
        if redirect_count == DEFAULT_REDIRECT_LIMIT:
            raise ServerConnectionError("Streamable HTTP redirect limit exceeded.")
        endpoint_url = redirect_url
        redirect_count += 1

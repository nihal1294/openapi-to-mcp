"""Conservative client-facing hints derived from HTTP methods."""


def derive_tool_annotations(method: str) -> dict[str, bool]:
    """Return only hints supported by the method's standard semantics."""
    method = method.upper()
    if method in {"GET", "HEAD", "OPTIONS", "QUERY"}:
        return {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
    if method == "PUT":
        return {"idempotentHint": True}
    if method == "DELETE":
        return {"destructiveHint": True, "idempotentHint": True}
    return {}

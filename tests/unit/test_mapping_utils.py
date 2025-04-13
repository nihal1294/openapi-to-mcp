import pytest

from openapi_to_mcp.mapping.utils import generate_tool_name


@pytest.mark.parametrize(
    ("method", "path", "expected_name"),
    [
        # Basic cases
        ("GET", "/", "get_root"),
        ("POST", "/users", "post_users"),
        ("GET", "/users/{userId}", "get_users_by_userId"),
        (
            "DELETE",
            "/users/{userId}/posts/{postId}",
            "delete_users_by_userId_posts_by_postId",
        ),
        # Leading/trailing slashes
        ("PUT", "/items/", "put_items"),
        ("PATCH", "items/{itemId}/", "patch_items_by_itemId"),
        # Special characters in path segments (should be replaced)
        ("GET", "/users/find-by-email", "get_users_find_by_email"),
        ("POST", "/data/import/v1.0", "post_data_import_v1_0"),
        ("GET", "/search?query=term", "get_search_query_term"),
        # Path parameters with special chars in name (less common, but test)
        ("GET", "/items/{item-id}", "get_items_by_item_id"),
        ("GET", "/items/{item.id}", "get_items_by_item_id"),
        # Empty path segments (should collapse underscores)
        ("GET", "/a//b", "get_a_b"),
        ("GET", "/a///b", "get_a_b"),
        # Starting with non-alpha
        ("GET", "/123start", "get_123start"),
        ("POST", "/_internal/check", "post_internal_check"),
        # Method casing
        ("get", "/simple", "get_simple"),
        ("PoSt", "/complex/path", "post_complex_path"),
        # Removed commented out code (ERA001 fix)
    ],
)
def test_generate_tool_name(method: str, path: str, expected_name: str) -> None:
    """Tests various method/path combinations for tool name generation."""
    assert generate_tool_name(method, path) == expected_name


def test_generate_tool_name_empty_path() -> None:
    """Test specifically for empty path resulting in method_root."""
    assert generate_tool_name("OPTIONS", "/") == "options_root"


def test_generate_tool_name_invalid_chars_collapse() -> None:
    """Test that multiple invalid chars collapse to single underscore."""
    assert generate_tool_name("GET", "/a-@!#$-b") == "get_a_b"

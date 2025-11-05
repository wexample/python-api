"""Simple HTTP request example using AbstractGateway.

This example demonstrates how to create a basic API client using AbstractGateway
to interact with a public REST API (JSONPlaceholder).
"""

from __future__ import annotations

from wexample_helpers.decorator.base_class import base_class
from wexample_prompt.common.io_manager import IoManager

from wexample_api.common.abstract_gateway import AbstractGateway
from wexample_api.enums.http import HttpMethod


@base_class
class JsonPlaceholderGateway(AbstractGateway):
    """Simple gateway to interact with JSONPlaceholder API."""

    def get_post(self, post_id: int) -> dict | None:
        """Fetch a single post by ID."""
        response = self.make_request(
            endpoint=f"/posts/{post_id}",
            method=HttpMethod.GET,
            expected_status_codes=200,
            call_origin=__file__,
        )
        return response.json() if response else None

    def create_post(self, title: str, body: str, user_id: int = 1) -> dict | None:
        """Create a new post."""
        response = self.make_request(
            endpoint="/posts",
            method=HttpMethod.POST,
            data={"title": title, "body": body, "userId": user_id},
            expected_status_codes=201,
            call_origin=__file__,
        )
        return response.json() if response else None

    def list_posts(self, limit: int = 5) -> list[dict] | None:
        """List posts with optional limit."""
        response = self.make_request(
            endpoint="/posts",
            method=HttpMethod.GET,
            query_params={"_limit": limit},
            expected_status_codes=200,
            call_origin=__file__,
        )
        return response.json() if response else None


def main() -> None:
    """Run the example."""
    # Initialize the gateway with JSONPlaceholder API
    io_manager = IoManager()
    gateway = JsonPlaceholderGateway(
        base_url="https://jsonplaceholder.typicode.com",
        io=io_manager,
    )

    io_manager.print_section("HTTP Request Example with AbstractGateway")

    # Example 1: Get a single post
    io_manager.print_section("1. Fetching a single post")
    post = gateway.get_post(1)
    if post:
        io_manager.log(f"Post title: {post.get('title')}")
        io_manager.log(f"Post body: {post.get('body')[:50]}...")

    # Example 2: List multiple posts
    io_manager.print_section("2. Listing posts")
    posts = gateway.list_posts(limit=3)
    if posts:
        for i, p in enumerate(posts, 1):
            io_manager.log(f"{i}. {p.get('title')}")

    # Example 3: Create a new post
    io_manager.print_section("3. Creating a new post")
    new_post = gateway.create_post(
        title="My Test Post",
        body="This is a test post created via the API gateway.",
    )
    if new_post:
        io_manager.log(f"Created post with ID: {new_post.get('id')}")

    # Example 4: Error handling - request with wrong status code expectation
    io_manager.print_section("4. Error handling example")
    response = gateway.make_request(
        endpoint="/posts/999999",
        method=HttpMethod.GET,
        expected_status_codes=200,
        quiet=False,  # Show error details
    )
    if response is None:
        io_manager.log("Request failed as expected (post not found)")


if __name__ == "__main__":
    main()

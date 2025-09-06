from __future__ import annotations

from typing import Any

from wexample_helpers_api.common.abstract_gateway import AbstractGateway


class DemoSimpleGateway(AbstractGateway):
    """A simple implementation of AbstractGateway for demonstration purposes."""

    def check_connection(self) -> bool:
        # Always return True for demo purposes
        return True

    def get_user_info(self) -> dict[str, Any]:
        """Demo method to get user information."""
        from wexample_helpers_api.enums.http import HttpMethod

        response = self.make_request(
            method=HttpMethod.GET, endpoint="/user", call_origin=__file__
        )
        return response.json()

    def create_item(self, item_data: dict[str, Any]) -> dict[str, Any]:
        """Demo method to create an item."""
        from wexample_helpers_api.enums.http import HttpMethod

        response = self.make_request(
            method=HttpMethod.POST,
            endpoint="/items",
            data=item_data,
            call_origin=__file__,
        )
        return response.json()

    def update_item(self, item_id: str, item_data: dict[str, Any]) -> dict[str, Any]:
        """Demo method to update an item."""
        from wexample_helpers_api.enums.http import HttpMethod

        response = self.make_request(
            method=HttpMethod.PUT,
            endpoint=f"/items/{item_id}",
            data=item_data,
            call_origin=__file__,
        )
        return response.json()

    def delete_item(self, item_id: str) -> None:
        """Demo method to delete an item."""
        from wexample_helpers_api.enums.http import HttpMethod

        self.make_request(
            method=HttpMethod.DELETE, endpoint=f"/items/{item_id}", call_origin=__file__
        )

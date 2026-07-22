"""Reusable API response behavior for invitation endpoints."""

from rest_framework.request import Request
from rest_framework.response import Response


class NoStoreResponseMixin:
    """Prevent browsers and intermediaries from storing personal responses."""

    def finalize_response(
        self,
        request: Request,
        response: Response,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Attach cache directives to success and error responses alike."""
        finalized_response = super().finalize_response(request, response, *args, **kwargs)
        finalized_response["Cache-Control"] = "private, no-store"
        finalized_response["Pragma"] = "no-cache"
        return finalized_response

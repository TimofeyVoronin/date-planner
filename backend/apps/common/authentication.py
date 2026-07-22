"""Authentication and permissions for invitation management capabilities."""

import re

from django.contrib.auth.models import AnonymousUser
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.common.capabilities import management_token_matches
from apps.common.models import Invitation

_MANAGEMENT_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")


class ManagementTokenAuthentication(BaseAuthentication):
    """Extract an opaque management capability from an Authorization header."""

    keyword = b"bearer"

    def authenticate(self, request: Request) -> tuple[AnonymousUser, str] | None:
        """Return the supplied capability without treating it as a user account."""
        parts = get_authorization_header(request).split()
        if not parts:
            return None
        if parts[0].lower() != self.keyword or len(parts) != 2:
            raise AuthenticationFailed("A valid Bearer authorization header is required.")

        try:
            token = parts[1].decode("ascii")
        except UnicodeDecodeError as error:
            raise AuthenticationFailed("The management token is malformed.") from error

        if _MANAGEMENT_TOKEN_PATTERN.fullmatch(token) is None:
            raise AuthenticationFailed("The management token is malformed.")
        return AnonymousUser(), token

    def authenticate_header(self, request: Request) -> str:
        """Advertise the expected HTTP authentication scheme for 401 responses."""
        return "Bearer"


class HasInvitationManagementToken(BasePermission):
    """Allow access only when the capability matches the requested invitation."""

    message = "The management token is invalid for this invitation."

    def has_permission(self, request: Request, view: APIView) -> bool:
        """Require this endpoint's authentication class to parse a Bearer token."""
        return isinstance(request.successful_authenticator, ManagementTokenAuthentication)

    def has_object_permission(
        self,
        request: Request,
        view: APIView,
        invitation: Invitation,
    ) -> bool:
        """Verify the opaque capability against the invitation's stored digest."""
        token = request.auth
        return isinstance(token, str) and management_token_matches(
            token,
            invitation.management_token_hash,
        )


class ManagementTokenAuthenticationScheme(OpenApiAuthenticationExtension):
    """Describe the custom capability as standard HTTP Bearer authentication."""

    target_class = "apps.common.authentication.ManagementTokenAuthentication"
    name = "managementToken"

    def get_security_definition(self, auto_schema: object) -> dict[str, str]:
        """Return the OpenAPI security scheme used by management endpoints."""
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "opaque management token",
            "description": "One-time-issued capability for managing one invitation.",
        }

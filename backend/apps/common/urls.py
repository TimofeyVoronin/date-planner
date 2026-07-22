"""URL routes for common API endpoints."""

from django.urls import path

from apps.common.views import (
    InvitationCreateView,
    InvitationDetailView,
    InvitationManagementDetailView,
    health_check,
)

app_name = "common"

urlpatterns = [
    path("health/", health_check, name="health"),
    path("invitations/", InvitationCreateView.as_view(), name="invitation-create"),
    path(
        "invitations/<uuid:pk>/",
        InvitationDetailView.as_view(),
        name="invitation-detail",
    ),
    path(
        "invitations/<uuid:pk>/manage/",
        InvitationManagementDetailView.as_view(),
        name="invitation-management-detail",
    ),
]

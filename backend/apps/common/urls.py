"""URL routes for common API endpoints."""

from django.urls import path

from apps.common.planning_views import InvitationPlanOptionsView, InvitationSelectionView
from apps.common.views import (
    InvitationCreateView,
    InvitationDetailView,
    InvitationManagementDetailView,
    InvitationResponseView,
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
    path(
        "invitations/<uuid:pk>/response/",
        InvitationResponseView.as_view(),
        name="invitation-response",
    ),
    path(
        "invitations/<uuid:pk>/plan-options/",
        InvitationPlanOptionsView.as_view(),
        name="invitation-plan-options",
    ),
    path(
        "invitations/<uuid:pk>/selection/",
        InvitationSelectionView.as_view(),
        name="invitation-selection",
    ),
]

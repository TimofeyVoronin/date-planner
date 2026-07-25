"""Tests for choosing when invitation date options are prepared."""

from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils.timezone import now
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.models import Invitation, InvitationPlanOption

pytestmark = pytest.mark.django_db


def authorization(token: str) -> dict[str, str]:
    """Build a management capability header."""
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def create_invitation(
    client: APIClient,
    *,
    creation_mode: str = Invitation.CreationMode.EXTENDED,
    planning_mode: str | None = None,
) -> tuple[Invitation, str]:
    """Create an invitation through the API and return its capability."""
    payload: dict[str, str] = {
        "author_name": "Алиса",
        "recipient_name": "Борис",
        "message": "Выберем удобный день",
        "creation_mode": creation_mode,
    }
    if planning_mode is not None:
        payload["planning_mode"] = planning_mode

    response = client.post("/api/v1/invitations/", payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    return Invitation.objects.get(pk=body["id"]), body["management_token"]


def management_path(invitation: Invitation) -> str:
    """Return the protected invitation detail path."""
    return f"/api/v1/invitations/{invitation.pk}/manage/"


def planning_path(invitation: Invitation) -> str:
    """Return the protected planning option path."""
    return f"/api/v1/invitations/{invitation.pk}/plan-options/"


def publication_path(invitation: Invitation) -> str:
    """Return the protected publication path."""
    return f"/api/v1/invitations/{invitation.pk}/publish/"


def plan_payload(*, days: int = 20) -> dict[str, list[dict[str, str]]]:
    """Build two valid future options."""
    return {
        "options": [
            {
                "starts_at": (now() + timedelta(days=days + index)).isoformat(),
                "place": f"Место {index + 1}",
                "comment": "",
            }
            for index in range(2)
        ]
    }


def create_options(invitation: Invitation, *, days: int = 20) -> None:
    """Persist two ordered options for publication checks."""
    InvitationPlanOption.objects.bulk_create(
        [
            InvitationPlanOption(
                invitation=invitation,
                starts_at=now() + timedelta(days=days + index),
                place=f"Место {index + 1}",
                position=index,
            )
            for index in range(2)
        ]
    )


def test_existing_flows_default_to_planning_after_acceptance() -> None:
    """Both creation modes keep the previous planning behavior by default."""
    client = APIClient()

    quick, _ = create_invitation(client, creation_mode=Invitation.CreationMode.QUICK)
    extended, token = create_invitation(client)

    assert quick.planning_mode == Invitation.PlanningMode.AFTER_ACCEPTANCE
    assert extended.planning_mode == Invitation.PlanningMode.AFTER_ACCEPTANCE
    managed = client.get(management_path(extended), **authorization(token))
    assert managed.status_code == status.HTTP_200_OK
    assert managed.json()["planning_mode"] == Invitation.PlanningMode.AFTER_ACCEPTANCE


def test_extended_invitation_can_choose_before_acceptance_during_creation() -> None:
    """The API accepts the preconfigured flow only for an extended invitation."""
    client = APIClient()

    invitation, _ = create_invitation(
        client,
        planning_mode=Invitation.PlanningMode.BEFORE_ACCEPTANCE,
    )

    assert invitation.planning_mode == Invitation.PlanningMode.BEFORE_ACCEPTANCE


def test_quick_invitation_rejects_before_acceptance_mode() -> None:
    """Quick invitations always retain their post-acceptance planning flow."""
    response = APIClient().post(
        "/api/v1/invitations/",
        {
            "author_name": "Алиса",
            "recipient_name": "Борис",
            "message": "",
            "creation_mode": Invitation.CreationMode.QUICK,
            "planning_mode": Invitation.PlanningMode.BEFORE_ACCEPTANCE,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "planning_mode" in response.json()
    assert Invitation.objects.count() == 0


def test_quick_invitation_management_rejects_before_acceptance_mode() -> None:
    """Management PATCH does not silently normalize an incompatible explicit mode."""
    client = APIClient()
    invitation, token = create_invitation(
        client,
        creation_mode=Invitation.CreationMode.QUICK,
    )

    response = client.patch(
        management_path(invitation),
        {"planning_mode": Invitation.PlanningMode.BEFORE_ACCEPTANCE},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "planning_mode" in response.json()
    invitation.refresh_from_db()
    assert invitation.planning_mode == Invitation.PlanningMode.AFTER_ACCEPTANCE


def test_database_rejects_invalid_or_quick_preconfigured_modes() -> None:
    """Database constraints protect records written outside API serializers."""
    with pytest.raises(IntegrityError), transaction.atomic():
        Invitation.objects.create(
            author_name="Алиса",
            recipient_name="Борис",
            planning_mode="invalid_mode",
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        Invitation.objects.create(
            author_name="Алиса",
            recipient_name="Борис",
            creation_mode=Invitation.CreationMode.QUICK,
            planning_mode=Invitation.PlanningMode.BEFORE_ACCEPTANCE,
        )


def test_author_can_change_extended_draft_planning_mode_idempotently() -> None:
    """A draft PATCH persists one mode and exact retries keep updated_at stable."""
    client = APIClient()
    invitation, token = create_invitation(client)

    first = client.patch(
        management_path(invitation),
        {"planning_mode": Invitation.PlanningMode.BEFORE_ACCEPTANCE},
        format="json",
        **authorization(token),
    )
    invitation.refresh_from_db()
    first_updated_at = invitation.updated_at
    repeated = client.patch(
        management_path(invitation),
        {"planning_mode": Invitation.PlanningMode.BEFORE_ACCEPTANCE},
        format="json",
        **authorization(token),
    )

    assert first.status_code == status.HTTP_200_OK
    assert first.json()["planning_mode"] == Invitation.PlanningMode.BEFORE_ACCEPTANCE
    assert repeated.status_code == status.HTTP_200_OK
    invitation.refresh_from_db()
    assert invitation.updated_at == first_updated_at


def test_management_update_rejects_non_object_payload_without_server_error() -> None:
    """Lifecycle prechecks leave malformed JSON payloads to serializer validation."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = client.patch(
        management_path(invitation),
        [{"planning_mode": Invitation.PlanningMode.BEFORE_ACCEPTANCE}],
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    invitation.refresh_from_db()
    assert invitation.planning_mode == Invitation.PlanningMode.AFTER_ACCEPTANCE


def test_published_invitation_cannot_change_planning_mode() -> None:
    """Publication freezes the recipient-facing planning contract."""
    client = APIClient()
    invitation, token = create_invitation(client)
    publish = client.put(
        publication_path(invitation),
        {},
        format="json",
        **authorization(token),
    )
    assert publish.status_code == status.HTTP_200_OK

    response = client.patch(
        management_path(invitation),
        {"planning_mode": Invitation.PlanningMode.BEFORE_ACCEPTANCE},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    invitation.refresh_from_db()
    assert invitation.planning_mode == Invitation.PlanningMode.AFTER_ACCEPTANCE


def test_returning_to_after_acceptance_clears_only_draft_options() -> None:
    """Hidden preconfigured options cannot leak into the later planning flow."""
    client = APIClient()
    invitation, token = create_invitation(
        client,
        planning_mode=Invitation.PlanningMode.BEFORE_ACCEPTANCE,
    )
    create_options(invitation)

    response = client.patch(
        management_path(invitation),
        {"planning_mode": Invitation.PlanningMode.AFTER_ACCEPTANCE},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["plan_options"] == []
    assert not invitation.plan_options.exists()


def test_before_acceptance_mode_can_save_options_while_draft() -> None:
    """Extended drafts may prepare an ordered option set before recipient response."""
    client = APIClient()
    invitation, token = create_invitation(
        client,
        planning_mode=Invitation.PlanningMode.BEFORE_ACCEPTANCE,
    )

    response = client.put(
        planning_path(invitation),
        plan_payload(),
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["plan_options"]) == 2
    invitation.refresh_from_db()
    assert invitation.response_status == Invitation.ResponseStatus.PENDING


def test_after_acceptance_mode_rejects_draft_planning() -> None:
    """The default flow still waits for an accepted public invitation."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = client.put(
        planning_path(invitation),
        plan_payload(),
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert not invitation.plan_options.exists()


def test_pending_recipient_cannot_read_preconfigured_options() -> None:
    """The public payload reveals prepared dates only after an accepted response."""
    client = APIClient()
    invitation, token = create_invitation(
        client,
        planning_mode=Invitation.PlanningMode.BEFORE_ACCEPTANCE,
    )
    create_options(invitation)
    publish = client.put(
        publication_path(invitation),
        {},
        format="json",
        **authorization(token),
    )
    assert publish.status_code == status.HTTP_200_OK
    assert len(publish.json()["plan_options"]) == 2

    public = client.get(f"/api/v1/invitations/{invitation.pk}/")
    declined = client.put(
        f"/api/v1/invitations/{invitation.pk}/response/",
        {"response_status": Invitation.ResponseStatus.DECLINED},
        format="json",
    )
    accepted = client.put(
        f"/api/v1/invitations/{invitation.pk}/response/",
        {"response_status": Invitation.ResponseStatus.ACCEPTED},
        format="json",
    )
    managed = client.get(management_path(invitation), **authorization(token))

    assert public.status_code == status.HTTP_200_OK
    assert public.json()["plan_options"] == []
    assert declined.status_code == status.HTTP_200_OK
    assert declined.json()["plan_options"] == []
    assert accepted.status_code == status.HTTP_200_OK
    assert len(accepted.json()["plan_options"]) == 2
    assert len(managed.json()["plan_options"]) == 2


def test_published_preconfigured_options_cannot_be_replaced() -> None:
    """A published preconfigured set is immutable during the recipient flow."""
    client = APIClient()
    invitation, token = create_invitation(
        client,
        planning_mode=Invitation.PlanningMode.BEFORE_ACCEPTANCE,
    )
    create_options(invitation)
    publish = client.put(
        publication_path(invitation),
        {},
        format="json",
        **authorization(token),
    )
    assert publish.status_code == status.HTTP_200_OK

    response = client.put(
        planning_path(invitation),
        plan_payload(days=40),
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert list(invitation.plan_options.values_list("place", flat=True)) == [
        "Место 1",
        "Место 2",
    ]


def test_preconfigured_publication_requires_two_future_options() -> None:
    """The service does not publish a flow that cannot proceed after acceptance."""
    client = APIClient()
    invitation, token = create_invitation(
        client,
        planning_mode=Invitation.PlanningMode.BEFORE_ACCEPTANCE,
    )

    missing = client.put(
        publication_path(invitation),
        {},
        format="json",
        **authorization(token),
    )
    InvitationPlanOption.objects.create(
        invitation=invitation,
        starts_at=now() - timedelta(minutes=1),
        place="Устаревший вариант",
        position=0,
    )
    InvitationPlanOption.objects.create(
        invitation=invitation,
        starts_at=now() + timedelta(days=1),
        place="Будущий вариант",
        position=1,
    )
    expired = client.put(
        publication_path(invitation),
        {},
        format="json",
        **authorization(token),
    )

    assert missing.status_code == status.HTTP_409_CONFLICT
    assert missing.json()["code"] == "planning_options_required"
    assert expired.status_code == status.HTTP_409_CONFLICT
    assert expired.json()["code"] == "planning_options_expired"
    invitation.refresh_from_db()
    assert invitation.publication_status == Invitation.PublicationStatus.DRAFT


def test_preconfigured_draft_with_future_options_can_publish() -> None:
    """A complete future option set opens the public invitation normally."""
    client = APIClient()
    invitation, token = create_invitation(
        client,
        planning_mode=Invitation.PlanningMode.BEFORE_ACCEPTANCE,
    )
    create_options(invitation)

    response = client.put(
        publication_path(invitation),
        {},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["publication_status"] == Invitation.PublicationStatus.PUBLISHED
    assert len(response.json()["plan_options"]) == 2


def test_openapi_documents_planning_mode_and_publication_conflict() -> None:
    """The generated contract exposes the enum and protected lifecycle response."""
    response = APIClient().get("/api/schema/?format=json")

    assert response.status_code == status.HTTP_200_OK
    schema = response.json()
    invitation_properties = schema["components"]["schemas"]["Invitation"]["properties"]
    assert "planning_mode" in invitation_properties
    component_schemas = schema["components"]["schemas"]
    serialized_components = str(component_schemas)
    assert Invitation.PlanningMode.BEFORE_ACCEPTANCE in serialized_components
    assert Invitation.PlanningMode.AFTER_ACCEPTANCE in serialized_components
    publication_responses = schema["paths"]["/api/v1/invitations/{id}/publish/"]["put"]["responses"]
    assert "409" in publication_responses

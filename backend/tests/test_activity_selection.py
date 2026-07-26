"""Tests for recipient activity selection and its final-confirmation boundary."""

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction
from django.utils.timezone import now as django_now
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.capabilities import generate_management_token, hash_management_token
from apps.common.models import ActivityOption, Invitation, InvitationPlanOption

pytestmark = pytest.mark.django_db


def activity_selection_path(invitation: Invitation) -> str:
    """Return the public activity selection endpoint."""
    return f"/api/v1/invitations/{invitation.pk}/activity-selection/"


def public_path(invitation: Invitation) -> str:
    """Return the public invitation endpoint."""
    return f"/api/v1/invitations/{invitation.pk}/"


def confirmation_path(invitation: Invitation) -> str:
    """Return the protected final confirmation endpoint."""
    return f"/api/v1/invitations/{invitation.pk}/confirmation/"


def authorization(token: str) -> dict[str, str]:
    """Build an HTTP Bearer header for a management capability."""
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def create_invitation(
    *,
    creation_mode: str = Invitation.CreationMode.EXTENDED,
    response_status: str = Invitation.ResponseStatus.ACCEPTED,
    publication_status: str = Invitation.PublicationStatus.PUBLISHED,
) -> tuple[Invitation, str]:
    """Create an extended invitation with a management capability."""
    token = generate_management_token()
    invitation = Invitation.objects.create(
        author_name="Алиса",
        recipient_name="Борис",
        message="Выбери активность",
        creation_mode=creation_mode,
        publication_status=publication_status,
        published_at=(
            None if publication_status == Invitation.PublicationStatus.DRAFT else django_now()
        ),
        management_token_hash=hash_management_token(token),
        response_status=response_status,
        responded_at=(
            None if response_status == Invitation.ResponseStatus.PENDING else django_now()
        ),
    )
    return invitation, token


def create_activities(invitation: Invitation) -> list[ActivityOption]:
    """Create three ordered recipient-facing activities."""
    return [
        ActivityOption.objects.create(
            invitation=invitation,
            title=title,
            description=f"Описание {index + 1}",
            image_key=image_key,
            place=f"Место {index + 1}",
            position=index,
        )
        for index, (title, image_key) in enumerate(
            (
                ("Прогулка", "activity-selection-default"),
                ("Кино", "activity-movie"),
                ("Кофе", "activity-coffee"),
            )
        )
    ]


def create_selected_date(
    invitation: Invitation,
    *,
    confirmed_at=None,
) -> InvitationPlanOption:
    """Create one selected future date, optionally already confirmed."""
    selected_at = confirmed_at - timedelta(minutes=1) if confirmed_at is not None else django_now()
    return InvitationPlanOption.objects.create(
        invitation=invitation,
        starts_at=django_now() + timedelta(days=10),
        place="Кофейня",
        comment="Столик у окна",
        position=0,
        selected_at=selected_at,
        confirmed_at=confirmed_at,
    )


@pytest.mark.parametrize(
    "response_status",
    [Invitation.ResponseStatus.PENDING, Invitation.ResponseStatus.DECLINED],
)
def test_public_snapshot_hides_activities_until_acceptance(response_status: str) -> None:
    """A public recipient cannot inspect prepared activities before accepting."""
    invitation, _ = create_invitation(response_status=response_status)
    create_activities(invitation)

    response = APIClient().get(public_path(invitation))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["activity_options"] == []
    assert response.json()["selected_activity_option_id"] is None
    assert response.json()["activity_selected_at"] is None


def test_accepted_public_snapshot_exposes_ordered_activity_options() -> None:
    """An accepted recipient receives only safe activity fields in author order."""
    invitation, _ = create_invitation()
    options = create_activities(invitation)

    response = APIClient().get(public_path(invitation))

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert [item["id"] for item in body["activity_options"]] == [
        str(option.pk) for option in options
    ]
    assert [item["position"] for item in body["activity_options"]] == [0, 1, 2]
    assert all(
        set(item) == {"id", "title", "description", "image_key", "place", "position"}
        for item in body["activity_options"]
    )
    assert "selected_at" not in body["activity_options"][0]


def test_recipient_selects_and_changes_activity_before_confirmation() -> None:
    """The recipient can save one activity and replace it before final confirmation."""
    invitation, _ = create_invitation()
    options = create_activities(invitation)
    client = APIClient()
    first_selected_at = django_now()

    with patch("apps.common.activity_views.now", return_value=first_selected_at):
        first = client.put(
            activity_selection_path(invitation),
            {"option_id": str(options[0].pk)},
            format="json",
        )

    assert first.status_code == status.HTTP_200_OK
    assert first["Cache-Control"] == "private, no-store"
    assert first.json()["selected_activity_option_id"] == str(options[0].pk)
    assert first.json()["activity_selected_at"] == first_selected_at.isoformat().replace(
        "+00:00", "Z"
    )

    second_selected_at = first_selected_at + timedelta(seconds=1)
    with patch("apps.common.activity_views.now", return_value=second_selected_at):
        changed = client.put(
            activity_selection_path(invitation),
            {"option_id": str(options[2].pk)},
            format="json",
        )

    assert changed.status_code == status.HTTP_200_OK
    assert changed.json()["selected_activity_option_id"] == str(options[2].pk)
    options[0].refresh_from_db()
    options[2].refresh_from_db()
    assert options[0].selected_at is None
    assert options[2].selected_at == second_selected_at


def test_exact_activity_selection_retry_preserves_timestamps() -> None:
    """Repeating the same public choice is a complete no-op."""
    invitation, _ = create_invitation()
    option = create_activities(invitation)[0]
    selected_at = django_now()
    client = APIClient()

    with patch("apps.common.activity_views.now", return_value=selected_at):
        first = client.put(
            activity_selection_path(invitation),
            {"option_id": str(option.pk)},
            format="json",
        )
    assert first.status_code == status.HTTP_200_OK
    invitation.refresh_from_db()
    first_updated_at = invitation.updated_at

    with patch("apps.common.activity_views.now") as mocked_now:
        repeated = client.put(
            activity_selection_path(invitation),
            {"option_id": str(option.pk)},
            format="json",
        )

    assert repeated.status_code == status.HTTP_200_OK
    assert (
        repeated.json()["selected_activity_option_id"]
        == first.json()["selected_activity_option_id"]
    )
    assert repeated.json()["activity_selected_at"] == first.json()["activity_selected_at"]
    mocked_now.assert_not_called()
    invitation.refresh_from_db()
    option.refresh_from_db()
    assert invitation.updated_at == first_updated_at
    assert option.selected_at == selected_at


@pytest.mark.parametrize(
    "response_status",
    [Invitation.ResponseStatus.PENDING, Invitation.ResponseStatus.DECLINED],
)
def test_activity_selection_requires_acceptance(response_status: str) -> None:
    """A pending or declined invitation cannot receive an activity selection."""
    invitation, _ = create_invitation(response_status=response_status)
    option = create_activities(invitation)[0]

    response = APIClient().put(
        activity_selection_path(invitation),
        {"option_id": str(option.pk)},
        format="json",
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    option.refresh_from_db()
    assert option.selected_at is None


def test_quick_invitation_cannot_store_activity_selection() -> None:
    """The compact flow never exposes or accepts activity choices."""
    invitation, _ = create_invitation(creation_mode=Invitation.CreationMode.QUICK)
    option = create_activities(invitation)[0]

    response = APIClient().put(
        activity_selection_path(invitation),
        {"option_id": str(option.pk)},
        format="json",
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"detail": "Activity selection belongs only to extended invitations."}
    option.refresh_from_db()
    assert option.selected_at is None


def test_declining_after_activity_selection_clears_the_saved_choice() -> None:
    """Changing an unconfirmed accepted response to declined clears activity state."""
    invitation, _ = create_invitation()
    option = create_activities(invitation)[0]
    option.selected_at = django_now()
    option.save(update_fields=("selected_at",))

    response = APIClient().put(
        f"/api/v1/invitations/{invitation.pk}/response/",
        {"response_status": Invitation.ResponseStatus.DECLINED},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["activity_options"] == []
    assert response.json()["selected_activity_option_id"] is None
    assert response.json()["activity_selected_at"] is None
    option.refresh_from_db()
    assert option.selected_at is None


def test_activity_selection_rejects_unknown_foreign_and_extra_fields() -> None:
    """Only one owned UUID can be selected and unknown body fields are rejected."""
    invitation, _ = create_invitation()
    options = create_activities(invitation)
    other_invitation, _ = create_invitation()
    foreign_option = create_activities(other_invitation)[0]
    client = APIClient()

    unknown = client.put(
        activity_selection_path(invitation),
        {"option_id": str(uuid4())},
        format="json",
    )
    foreign = client.put(
        activity_selection_path(invitation),
        {"option_id": str(foreign_option.pk)},
        format="json",
    )
    extra = client.put(
        activity_selection_path(invitation),
        {"option_id": str(options[0].pk), "selected_at": "unexpected"},
        format="json",
    )

    assert unknown.status_code == status.HTTP_400_BAD_REQUEST
    assert foreign.status_code == status.HTTP_400_BAD_REQUEST
    assert extra.status_code == status.HTTP_400_BAD_REQUEST
    assert "selected_at" in extra.json()
    assert not invitation.activity_options.filter(selected_at__isnull=False).exists()


def test_draft_and_unknown_invitations_are_hidden_from_activity_selection() -> None:
    """The public selection capability follows the same publication security boundary."""
    draft, _ = create_invitation(publication_status=Invitation.PublicationStatus.DRAFT)
    draft_option = create_activities(draft)[0]
    client = APIClient()

    draft_response = client.put(
        activity_selection_path(draft),
        {"option_id": str(draft_option.pk)},
        format="json",
    )
    missing_response = client.put(
        f"/api/v1/invitations/{uuid4()}/activity-selection/",
        {"option_id": str(uuid4())},
        format="json",
    )

    assert draft_response.status_code == status.HTTP_404_NOT_FOUND
    assert missing_response.status_code == status.HTTP_404_NOT_FOUND


def test_confirmed_plan_freezes_activity_but_exact_retry_remains_safe() -> None:
    """After confirmation the saved activity is immutable while exact retries succeed."""
    invitation, _ = create_invitation()
    options = create_activities(invitation)
    options[0].selected_at = django_now() - timedelta(minutes=2)
    options[0].save(update_fields=("selected_at",))
    confirmed_at = django_now() - timedelta(minutes=1)
    create_selected_date(invitation, confirmed_at=confirmed_at)
    client = APIClient()

    same = client.put(
        activity_selection_path(invitation),
        {"option_id": str(options[0].pk)},
        format="json",
    )
    changed = client.put(
        activity_selection_path(invitation),
        {"option_id": str(options[1].pk)},
        format="json",
    )

    assert same.status_code == status.HTTP_200_OK
    assert changed.status_code == status.HTTP_409_CONFLICT
    options[0].refresh_from_db()
    options[1].refresh_from_db()
    assert options[0].selected_at is not None
    assert options[1].selected_at is None


def test_confirmation_requires_activity_when_extended_options_exist() -> None:
    """The author cannot finalize an extended plan before activity selection."""
    invitation, token = create_invitation()
    create_activities(invitation)
    selected_date = create_selected_date(invitation)

    response = APIClient().put(
        confirmation_path(invitation),
        {"confirmed": True, "option_id": str(selected_date.pk)},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {
        "code": "activity_selection_required",
        "detail": "Confirmation requires a selected activity option.",
    }
    selected_date.refresh_from_db()
    assert selected_date.confirmed_at is None


def test_database_allows_only_one_selected_activity_per_invitation() -> None:
    """The database protects selection uniqueness outside the public API."""
    invitation, _ = create_invitation()
    options = create_activities(invitation)
    options[0].selected_at = django_now()
    options[0].save(update_fields=("selected_at",))

    with pytest.raises(IntegrityError), transaction.atomic():
        options[1].selected_at = django_now()
        options[1].save(update_fields=("selected_at",))


def test_openapi_documents_public_activity_selection_contract() -> None:
    """The schema exposes an unauthenticated PUT with all public outcomes."""
    response = APIClient().get("/api/schema/?format=json")

    assert response.status_code == status.HTTP_200_OK
    schema = response.json()
    operation = schema["paths"]["/api/v1/invitations/{id}/activity-selection/"]["put"]
    assert operation.get("security", []) == []
    assert set(operation["responses"]) == {"200", "400", "404", "409", "429"}
    request_reference = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    request_component = request_reference.rsplit("/", maxsplit=1)[-1]
    assert set(schema["components"]["schemas"][request_component]["properties"]) == {"option_id"}

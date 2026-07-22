"""Tests for proposing and selecting invitation planning options."""

import uuid
from datetime import timedelta, timezone
from unittest.mock import patch

import pytest
from django.db import IntegrityError, transaction
from django.utils.timezone import now as django_now
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.common.capabilities import generate_management_token, hash_management_token
from apps.common.models import Invitation, InvitationPlanOption

pytestmark = pytest.mark.django_db


def invitation_data(
    *,
    author_name: str = "Алиса",
    recipient_name: str = "Борис",
) -> dict[str, str]:
    """Build persisted invitation fields for planning tests."""
    return {
        "author_name": author_name,
        "recipient_name": recipient_name,
        "message": "Давай выберем время и место",
    }


def accepted_invitation(
    *,
    author_name: str = "Алиса",
    recipient_name: str = "Борис",
) -> tuple[Invitation, str]:
    """Create an accepted invitation with an author management capability."""
    management_token = generate_management_token()
    invitation = Invitation.objects.create(
        **invitation_data(author_name=author_name, recipient_name=recipient_name),
        management_token_hash=hash_management_token(management_token),
        response_status=Invitation.ResponseStatus.ACCEPTED,
        responded_at=django_now(),
    )
    return invitation, management_token


def authorization(token: str) -> dict[str, str]:
    """Build an APIClient Bearer header."""
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def plan_path(invitation_id: object) -> str:
    """Return the author planning endpoint for an invitation identifier."""
    return f"/api/v1/invitations/{invitation_id}/plan-options/"


def selection_path(invitation_id: object) -> str:
    """Return the public selection endpoint for an invitation identifier."""
    return f"/api/v1/invitations/{invitation_id}/selection/"


def future_starts_at(index: int = 0):
    """Return a safely future aware datetime."""
    return django_now() + timedelta(days=30 + index)


def plan_payload(count: int = 2, *, prefix: str = "Вариант") -> dict[str, list[dict[str, str]]]:
    """Build an ordered, valid planning payload."""
    return {
        "options": [
            {
                "starts_at": future_starts_at(index).isoformat(),
                "place": f"{prefix} {index + 1}",
                "comment": f"Комментарий {index + 1}",
            }
            for index in range(count)
        ]
    }


def create_plan_options(invitation: Invitation, count: int = 2) -> list[InvitationPlanOption]:
    """Persist ordered future options without using the API."""
    return [
        InvitationPlanOption.objects.create(
            invitation=invitation,
            starts_at=future_starts_at(index),
            place=f"Место {index + 1}",
            comment=f"Комментарий {index + 1}",
            position=index,
        )
        for index in range(count)
    ]


def test_author_can_propose_ordered_options_with_optional_comments() -> None:
    """A valid management capability replaces the ordered planning collection."""
    invitation, token = accepted_invitation()
    payload = plan_payload()
    payload["options"][0].pop("comment")
    payload["options"][1]["comment"] = "   "

    response = APIClient().put(
        plan_path(invitation.pk),
        payload,
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert [option["place"] for option in body["plan_options"]] == [
        "Вариант 1",
        "Вариант 2",
    ]
    assert [option["comment"] for option in body["plan_options"]] == ["", ""]
    assert [option["position"] for option in body["plan_options"]] == [0, 1]
    assert all(uuid.UUID(option["id"]) for option in body["plan_options"])
    assert body["selected_option_id"] is None
    assert body["selected_at"] is None
    assert "management_token" not in body
    assert "management_token_hash" not in body
    assert response["Cache-Control"] == "private, no-store"
    assert response["Pragma"] == "no-cache"

    persisted = list(invitation.plan_options.all())
    assert [option.position for option in persisted] == [0, 1]
    assert [option.place for option in persisted] == ["Вариант 1", "Вариант 2"]


@pytest.mark.parametrize("count", [2, 5])
def test_plan_option_count_boundaries_and_field_limits_are_accepted(count: int) -> None:
    """Both supported collection boundaries accept database-sized text fields."""
    invitation, token = accepted_invitation()
    payload = plan_payload(count)
    payload["options"][0]["place"] = "P" * 200
    payload["options"][0]["comment"] = "C" * 500
    offset = timezone(timedelta(hours=7))
    payload["options"][0]["starts_at"] = future_starts_at().astimezone(offset).isoformat()

    response = APIClient().put(
        plan_path(invitation.pk),
        payload,
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["plan_options"]) == count
    assert response.json()["plan_options"][0]["place"] == "P" * 200
    assert response.json()["plan_options"][0]["comment"] == "C" * 500


def test_plan_put_replaces_options_atomically_and_preserves_new_order() -> None:
    """A changed collection removes old rows and stores only the new order."""
    invitation, token = accepted_invitation()
    client = APIClient()
    first_response = client.put(
        plan_path(invitation.pk),
        plan_payload(prefix="Старый"),
        format="json",
        **authorization(token),
    )
    old_ids = {option["id"] for option in first_response.json()["plan_options"]}
    invitation.refresh_from_db()
    old_updated_at = invitation.updated_at

    replacement_response = client.put(
        plan_path(invitation.pk),
        plan_payload(3, prefix="Новый"),
        format="json",
        **authorization(token),
    )

    assert replacement_response.status_code == status.HTTP_200_OK
    replacement_options = replacement_response.json()["plan_options"]
    assert [option["place"] for option in replacement_options] == [
        "Новый 1",
        "Новый 2",
        "Новый 3",
    ]
    assert old_ids.isdisjoint(option["id"] for option in replacement_options)
    assert InvitationPlanOption.objects.filter(invitation=invitation).count() == 3
    invitation.refresh_from_db()
    assert invitation.updated_at > old_updated_at


def test_identical_plan_put_preserves_option_ids_and_updated_at() -> None:
    """Retrying an identical replacement is an idempotent no-op."""
    invitation, token = accepted_invitation()
    payload = plan_payload()
    client = APIClient()
    first_response = client.put(
        plan_path(invitation.pk),
        payload,
        format="json",
        **authorization(token),
    )
    invitation.refresh_from_db()
    first_updated_at = invitation.updated_at
    first_ids = [option["id"] for option in first_response.json()["plan_options"]]

    repeated_response = client.put(
        plan_path(invitation.pk),
        payload,
        format="json",
        **authorization(token),
    )

    assert repeated_response.status_code == status.HTTP_200_OK
    assert [option["id"] for option in repeated_response.json()["plan_options"]] == first_ids
    invitation.refresh_from_db()
    assert invitation.updated_at == first_updated_at


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"options": None},
        {"options": []},
        {"options": [{}]},
        plan_payload(1),
        plan_payload(6),
        {"options": "not-a-list"},
    ],
)
def test_plan_rejects_invalid_collection_sizes(payload: object) -> None:
    """The author must provide one JSON list containing two to five options."""
    invitation, token = accepted_invitation()

    response = APIClient().put(
        plan_path(invitation.pk),
        payload,
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "options" in response.json()
    assert response["Cache-Control"] == "private, no-store"
    assert not InvitationPlanOption.objects.filter(invitation=invitation).exists()


@pytest.mark.parametrize(
    "case",
    [
        "missing_starts_at",
        "invalid_starts_at",
        "naive_starts_at",
        "past_starts_at",
        "missing_place",
        "blank_place",
        "long_place",
        "null_comment",
        "long_comment",
    ],
)
def test_plan_rejects_invalid_option_fields(case: str) -> None:
    """Each option enforces aware future time and bounded nonblank place data."""
    invitation, token = accepted_invitation()
    payload = plan_payload()
    option = payload["options"][0]
    if case == "missing_starts_at":
        option.pop("starts_at")
    elif case == "invalid_starts_at":
        option["starts_at"] = "not-a-date"
    elif case == "naive_starts_at":
        option["starts_at"] = future_starts_at().replace(tzinfo=None).isoformat()
    elif case == "past_starts_at":
        option["starts_at"] = (django_now() - timedelta(seconds=1)).isoformat()
    elif case == "missing_place":
        option.pop("place")
    elif case == "blank_place":
        option["place"] = "   "
    elif case == "long_place":
        option["place"] = "P" * 201
    elif case == "null_comment":
        option["comment"] = None
    elif case == "long_comment":
        option["comment"] = "C" * 501

    response = APIClient().put(
        plan_path(invitation.pk),
        payload,
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not invitation.plan_options.exists()


def test_plan_rejects_time_equal_to_validation_clock() -> None:
    """Starts-at must be strictly later than the server validation time."""
    invitation, token = accepted_invitation()
    validation_time = django_now()
    payload = plan_payload()
    payload["options"][0]["starts_at"] = validation_time.isoformat()

    with patch("apps.common.serializers.now", return_value=validation_time):
        response = APIClient().put(
            plan_path(invitation.pk),
            payload,
            format="json",
            **authorization(token),
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not invitation.plan_options.exists()


def test_invalid_replacement_keeps_existing_options_unchanged() -> None:
    """Batch validation happens before delete, so an invalid PUT cannot partially replace."""
    invitation, token = accepted_invitation()
    existing = create_plan_options(invitation)

    response = APIClient().put(
        plan_path(invitation.pk),
        plan_payload(1),
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert list(invitation.plan_options.values_list("id", flat=True)) == [
        option.pk for option in existing
    ]


@pytest.mark.parametrize(
    "response_status",
    [Invitation.ResponseStatus.PENDING, Invitation.ResponseStatus.DECLINED],
)
def test_plan_requires_accepted_invitation(response_status: str) -> None:
    """Pending and declined invitations cannot receive planning options."""
    token = generate_management_token()
    invitation = Invitation.objects.create(
        **invitation_data(),
        management_token_hash=hash_management_token(token),
        response_status=response_status,
        responded_at=None if response_status == Invitation.ResponseStatus.PENDING else django_now(),
    )

    response = APIClient().put(
        plan_path(invitation.pk),
        plan_payload(),
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response["Cache-Control"] == "private, no-store"
    assert not invitation.plan_options.exists()


def test_plan_cannot_change_after_recipient_selection() -> None:
    """Once selected, option identifiers remain stable and replacement is blocked."""
    invitation, token = accepted_invitation()
    options = create_plan_options(invitation)
    options[0].selected_at = django_now()
    options[0].save(update_fields=("selected_at",))
    existing_ids = list(invitation.plan_options.values_list("id", flat=True))

    response = APIClient().put(
        plan_path(invitation.pk),
        plan_payload(prefix="Замена"),
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response["Cache-Control"] == "private, no-store"
    assert list(invitation.plan_options.values_list("id", flat=True)) == existing_ids


def test_author_can_replace_options_after_unconfirmed_selection_expires() -> None:
    """An expired non-final choice can be atomically replaced to recover planning."""
    invitation, token = accepted_invitation()
    options = create_plan_options(invitation)
    options[0].starts_at = django_now() - timedelta(seconds=1)
    options[0].selected_at = django_now()
    options[0].save(update_fields=("starts_at", "selected_at"))
    old_ids = [option.pk for option in options]
    invitation.refresh_from_db()
    previous_updated_at = invitation.updated_at

    response = APIClient().put(
        plan_path(invitation.pk),
        plan_payload(prefix="Восстановленный"),
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["selected_option_id"] is None
    assert response.json()["selected_at"] is None
    assert response.json()["confirmed_at"] is None
    assert [option["place"] for option in response.json()["plan_options"]] == [
        "Восстановленный 1",
        "Восстановленный 2",
    ]
    assert not InvitationPlanOption.objects.filter(pk__in=old_ids).exists()
    invitation.refresh_from_db()
    assert invitation.updated_at > previous_updated_at


def test_invalid_recovery_payload_preserves_expired_selection_and_options() -> None:
    """Recovery validates the full replacement before deleting the expired choice."""
    invitation, token = accepted_invitation()
    options = create_plan_options(invitation)
    options[0].starts_at = django_now() - timedelta(seconds=1)
    options[0].selected_at = django_now()
    options[0].save(update_fields=("starts_at", "selected_at"))
    existing_ids = list(invitation.plan_options.values_list("id", flat=True))
    invitation.refresh_from_db()
    previous_updated_at = invitation.updated_at

    response = APIClient().put(
        plan_path(invitation.pk),
        plan_payload(1, prefix="Недостаточно"),
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response["Cache-Control"] == "private, no-store"
    assert list(invitation.plan_options.values_list("id", flat=True)) == existing_ids
    options[0].refresh_from_db()
    invitation.refresh_from_db()
    assert options[0].selected_at is not None
    assert options[0].confirmed_at is None
    assert invitation.updated_at == previous_updated_at


def test_confirmed_expired_selection_cannot_be_replaced() -> None:
    """Elapsed wall-clock time never reopens an already final plan."""
    invitation, token = accepted_invitation()
    starts_at = django_now() - timedelta(seconds=1)
    confirmed_at = starts_at - timedelta(seconds=1)
    selected_at = confirmed_at - timedelta(seconds=1)
    option = InvitationPlanOption.objects.create(
        invitation=invitation,
        starts_at=starts_at,
        place="Уже подтверждено",
        position=0,
        selected_at=selected_at,
        confirmed_at=confirmed_at,
    )
    invitation.refresh_from_db()
    previous_updated_at = invitation.updated_at

    response = APIClient().put(
        plan_path(invitation.pk),
        plan_payload(prefix="Запрещённая замена"),
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response["Cache-Control"] == "private, no-store"
    option.refresh_from_db()
    invitation.refresh_from_db()
    assert option.selected_at == selected_at
    assert option.confirmed_at == confirmed_at
    assert invitation.updated_at == previous_updated_at


def test_plan_endpoint_requires_matching_management_capability() -> None:
    """Missing, incorrect, and cross-invitation tokens cannot propose options."""
    invitation, token = accepted_invitation()
    other_invitation, other_token = accepted_invitation(
        author_name="Виктор",
        recipient_name="Галина",
    )
    client = APIClient()

    missing_response = client.put(plan_path(invitation.pk), plan_payload(), format="json")
    wrong_response = client.put(
        plan_path(invitation.pk),
        plan_payload(),
        format="json",
        **authorization("A" * 43),
    )
    cross_response = client.put(
        plan_path(other_invitation.pk),
        plan_payload(),
        format="json",
        **authorization(token),
    )

    assert missing_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert missing_response["WWW-Authenticate"] == "Bearer"
    assert wrong_response.status_code == status.HTTP_403_FORBIDDEN
    assert cross_response.status_code == status.HTTP_403_FORBIDDEN
    assert token != other_token
    assert InvitationPlanOption.objects.count() == 0


def test_plan_permission_is_checked_before_invalid_body() -> None:
    """A wrong token receives 403 without learning request-validation behavior."""
    invitation, _ = accepted_invitation()

    response = APIClient().put(
        plan_path(invitation.pk),
        {"options": []},
        format="json",
        **authorization("A" * 43),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_plan_unknown_invitation_returns_404() -> None:
    """A valid-looking capability cannot create options for an unknown UUID."""
    response = APIClient().put(
        plan_path(uuid.uuid4()),
        plan_payload(),
        format="json",
        **authorization("A" * 43),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response["Cache-Control"] == "private, no-store"


@pytest.mark.parametrize("method", ["GET", "POST", "PATCH", "DELETE"])
def test_plan_endpoint_rejects_unsupported_methods(method: str) -> None:
    """Author planning exposes only PUT and OPTIONS."""
    invitation, token = accepted_invitation()

    response = APIClient().generic(
        method,
        plan_path(invitation.pk),
        data=plan_payload(),
        content_type="application/json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert response["Cache-Control"] == "private, no-store"


def test_recipient_can_select_owned_future_option() -> None:
    """The public invitation UUID can select one of its offered options."""
    invitation, _ = accepted_invitation()
    options = create_plan_options(invitation)
    selected_at = django_now()

    with patch("apps.common.planning_views.now", return_value=selected_at):
        response = APIClient().put(
            selection_path(invitation.pk),
            {"option_id": str(options[1].pk)},
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["selected_option_id"] == str(options[1].pk)
    assert body["selected_at"] == selected_at.isoformat().replace("+00:00", "Z")
    assert [option["id"] for option in body["plan_options"]] == [
        str(option.pk) for option in options
    ]
    assert "management_token" not in body
    assert "management_token_hash" not in body
    assert response["Cache-Control"] == "private, no-store"
    invitation.refresh_from_db()
    assert invitation.selected_option_id == options[1].pk
    assert invitation.selected_at == selected_at


def test_repeating_same_selection_is_idempotent() -> None:
    """Retrying the same option preserves selection and invitation timestamps."""
    invitation, _ = accepted_invitation()
    option = create_plan_options(invitation)[0]
    selected_at = django_now()
    client = APIClient()

    with patch("apps.common.planning_views.now", return_value=selected_at):
        first_response = client.put(
            selection_path(invitation.pk),
            {"option_id": str(option.pk)},
            format="json",
        )
    invitation.refresh_from_db()
    first_updated_at = invitation.updated_at

    with patch("apps.common.planning_views.now") as mocked_now:
        repeated_response = client.put(
            selection_path(invitation.pk),
            {"option_id": str(option.pk)},
            format="json",
        )

    assert first_response.status_code == status.HTTP_200_OK
    assert repeated_response.status_code == status.HTTP_200_OK
    mocked_now.assert_not_called()
    invitation.refresh_from_db()
    assert invitation.selected_at == selected_at
    assert invitation.updated_at == first_updated_at


def test_recipient_can_change_selection_and_timestamp() -> None:
    """Choosing another owned option replaces both selection fields."""
    invitation, _ = accepted_invitation()
    options = create_plan_options(invitation)
    first_selected_at = django_now()
    second_selected_at = first_selected_at + timedelta(minutes=1)
    client = APIClient()

    with patch(
        "apps.common.planning_views.now",
        side_effect=(first_selected_at, second_selected_at),
    ):
        first_response = client.put(
            selection_path(invitation.pk),
            {"option_id": str(options[0].pk)},
            format="json",
        )
        second_response = client.put(
            selection_path(invitation.pk),
            {"option_id": str(options[1].pk)},
            format="json",
        )

    assert first_response.status_code == status.HTTP_200_OK
    assert second_response.status_code == status.HTTP_200_OK
    assert second_response.json()["selected_option_id"] == str(options[1].pk)
    invitation.refresh_from_db()
    assert invitation.selected_option_id == options[1].pk
    assert invitation.selected_at == second_selected_at


@pytest.mark.parametrize(
    "response_status",
    [Invitation.ResponseStatus.PENDING, Invitation.ResponseStatus.DECLINED],
)
def test_selection_requires_accepted_invitation(response_status: str) -> None:
    """Pending and declined public links cannot select planning options."""
    invitation = Invitation.objects.create(
        **invitation_data(),
        response_status=response_status,
        responded_at=None if response_status == Invitation.ResponseStatus.PENDING else django_now(),
    )
    option = create_plan_options(invitation)[0]

    response = APIClient().put(
        selection_path(invitation.pk),
        {"option_id": str(option.pk)},
        format="json",
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    invitation.refresh_from_db()
    assert invitation.selected_option_id is None
    assert invitation.selected_at is None


@pytest.mark.parametrize("option_id", ["not-a-uuid", str(uuid.uuid4())])
def test_selection_rejects_invalid_or_unknown_option(option_id: str) -> None:
    """Malformed and unavailable option IDs return 400 without a selection."""
    invitation, _ = accepted_invitation()

    response = APIClient().put(
        selection_path(invitation.pk),
        {"option_id": option_id},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "option_id" in response.json()
    assert response["Cache-Control"] == "private, no-store"
    invitation.refresh_from_db()
    assert invitation.selected_option_id is None


def test_selection_rejects_option_from_another_invitation() -> None:
    """An option UUID is scoped to its invitation and reveals no cross-record data."""
    first, _ = accepted_invitation()
    second, _ = accepted_invitation(author_name="Виктор", recipient_name="Галина")
    foreign_option = create_plan_options(second)[0]

    response = APIClient().put(
        selection_path(first.pk),
        {"option_id": str(foreign_option.pk)},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Галина" not in response.content.decode()
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.selected_option_id is None
    assert second.selected_option_id is None


def test_selection_rejects_option_that_is_no_longer_future() -> None:
    """An option that expired after proposal cannot become a new selection."""
    invitation, _ = accepted_invitation()
    option = InvitationPlanOption.objects.create(
        invitation=invitation,
        starts_at=django_now() - timedelta(seconds=1),
        place="Закрывшееся место",
        position=0,
    )

    response = APIClient().put(
        selection_path(invitation.pk),
        {"option_id": str(option.pk)},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    invitation.refresh_from_db()
    assert invitation.selected_option_id is None


def test_selection_unknown_invitation_returns_404() -> None:
    """A valid option-shaped UUID cannot reveal an unknown invitation."""
    response = APIClient().put(
        selection_path(uuid.uuid4()),
        {"option_id": str(uuid.uuid4())},
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response["Cache-Control"] == "private, no-store"


def test_selection_mutates_only_addressed_invitation() -> None:
    """Selections remain isolated when several people use the service."""
    first, _ = accepted_invitation()
    second, _ = accepted_invitation(author_name="Виктор", recipient_name="Галина")
    first_option = create_plan_options(first)[0]
    create_plan_options(second)

    response = APIClient().put(
        selection_path(first.pk),
        {"option_id": str(first_option.pk)},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.selected_option_id == first_option.pk
    assert second.selected_option_id is None


def test_declining_after_selection_clears_selection_but_keeps_options() -> None:
    """A later decline removes the chosen plan without destroying proposals."""
    invitation, _ = accepted_invitation()
    option = create_plan_options(invitation)[0]
    selection_response = APIClient().put(
        selection_path(invitation.pk),
        {"option_id": str(option.pk)},
        format="json",
    )
    assert selection_response.status_code == status.HTTP_200_OK

    decline_response = APIClient().put(
        f"/api/v1/invitations/{invitation.pk}/response/",
        {"response_status": Invitation.ResponseStatus.DECLINED},
        format="json",
    )

    assert decline_response.status_code == status.HTTP_200_OK
    assert decline_response.json()["selected_option_id"] is None
    assert decline_response.json()["selected_at"] is None
    assert len(decline_response.json()["plan_options"]) == 2
    invitation.refresh_from_db()
    assert invitation.selected_option_id is None
    assert invitation.selected_at is None


def test_public_and_management_reads_expose_plan_without_secrets() -> None:
    """Both invitation views expose the plan while retaining capability secrecy."""
    invitation, token = accepted_invitation()
    option = create_plan_options(invitation)[0]
    option.selected_at = django_now()
    option.save(update_fields=("selected_at",))
    client = APIClient()

    public_response = client.get(f"/api/v1/invitations/{invitation.pk}/")
    management_response = client.get(
        f"/api/v1/invitations/{invitation.pk}/manage/",
        **authorization(token),
    )

    for response in (public_response, management_response):
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["selected_option_id"] == str(option.pk)
        assert response.json()["selected_at"] is not None
        assert response.json()["plan_options"][0]["id"] == str(option.pk)
        assert "management_token" not in response.json()
        assert "management_token_hash" not in response.json()
        assert response["Cache-Control"] == "private, no-store"


@pytest.mark.parametrize("method", ["GET", "POST", "PATCH", "DELETE"])
def test_selection_endpoint_rejects_unsupported_methods(method: str) -> None:
    """Public selection exposes only PUT and OPTIONS."""
    invitation, _ = accepted_invitation()

    response = APIClient().generic(
        method,
        selection_path(invitation.pk),
        data={"option_id": str(uuid.uuid4())},
        content_type="application/json",
    )

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert response["Cache-Control"] == "private, no-store"


@pytest.mark.parametrize("path_builder", [plan_path, selection_path])
def test_planning_options_advertise_only_put(path_builder) -> None:
    """Both planning endpoint metadata responses advertise only PUT and OPTIONS."""
    invitation, token = accepted_invitation()

    response = APIClient().options(
        path_builder(invitation.pk),
        **authorization(token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert {method.strip() for method in response["Allow"].split(",")} == {
        "PUT",
        "OPTIONS",
    }
    assert response["Cache-Control"] == "private, no-store"


def test_plan_throttle_returns_retry_after_without_third_replacement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The shared planning limit rejects excess author writes without mutation."""
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "invitation_plan", "2/min")
    invitation, token = accepted_invitation()
    client = APIClient()
    client_address = {"REMOTE_ADDR": "192.0.2.50"}

    first_response = client.put(
        plan_path(invitation.pk),
        plan_payload(prefix="Первый"),
        format="json",
        **authorization(token),
        **client_address,
    )
    second_response = client.put(
        plan_path(invitation.pk),
        plan_payload(prefix="Второй"),
        format="json",
        **authorization(token),
        **client_address,
    )
    throttled_response = client.put(
        plan_path(invitation.pk),
        plan_payload(prefix="Третий"),
        format="json",
        **authorization(token),
        **client_address,
    )

    assert first_response.status_code == status.HTTP_200_OK
    assert second_response.status_code == status.HTTP_200_OK
    assert throttled_response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert throttled_response["Cache-Control"] == "private, no-store"
    retry_after = throttled_response.headers.get("Retry-After")
    assert retry_after is not None
    assert 1 <= int(retry_after) <= 60
    assert list(invitation.plan_options.values_list("place", flat=True)) == [
        "Второй 1",
        "Второй 2",
    ]


def test_spoofed_forwarded_for_cannot_bypass_selection_throttle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Untrusted forwarding headers do not create a new planning client identity."""
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "invitation_plan", "1/min")
    invitation, _ = accepted_invitation()
    options = create_plan_options(invitation)
    client = APIClient()

    first_response = client.put(
        selection_path(invitation.pk),
        {"option_id": str(options[0].pk)},
        format="json",
        REMOTE_ADDR="192.0.2.60",
        HTTP_X_FORWARDED_FOR="198.51.100.1",
    )
    throttled_response = client.put(
        selection_path(invitation.pk),
        {"option_id": str(options[1].pk)},
        format="json",
        REMOTE_ADDR="192.0.2.60",
        HTTP_X_FORWARDED_FOR="203.0.113.1",
    )

    assert first_response.status_code == status.HTTP_200_OK
    assert throttled_response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    invitation.refresh_from_db()
    assert invitation.selected_option_id == options[0].pk


def test_single_selection_constraint_and_invitation_delete_cascade() -> None:
    """The database permits one owned selection and deletes the full aggregate."""
    invitation, _ = accepted_invitation()
    options = create_plan_options(invitation)
    options[0].selected_at = django_now()
    options[0].save(update_fields=("selected_at",))

    with pytest.raises(IntegrityError), transaction.atomic():
        options[1].selected_at = django_now()
        options[1].save(update_fields=("selected_at",))

    invitation_id = invitation.pk
    option_ids = [option.pk for option in options]

    invitation.delete()

    assert not Invitation.objects.filter(pk=invitation_id).exists()
    assert not InvitationPlanOption.objects.filter(pk__in=option_ids).exists()


def test_plan_option_database_position_constraints() -> None:
    """Database constraints prevent duplicate and out-of-range option positions."""
    invitation, _ = accepted_invitation()
    create_plan_options(invitation, count=1)

    with pytest.raises(IntegrityError), transaction.atomic():
        InvitationPlanOption.objects.create(
            invitation=invitation,
            starts_at=future_starts_at(2),
            place="Дубликат позиции",
            position=0,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        InvitationPlanOption.objects.create(
            invitation=invitation,
            starts_at=future_starts_at(3),
            place="Шестая позиция",
            position=5,
        )


def test_openapi_documents_both_planning_contracts() -> None:
    """Schema distinguishes author capability and public recipient operations."""
    response = APIClient().get("/api/schema/?format=json")

    assert response.status_code == status.HTTP_200_OK
    schema = response.json()
    plan_operation = schema["paths"]["/api/v1/invitations/{id}/plan-options/"]["put"]
    selection_operation = schema["paths"]["/api/v1/invitations/{id}/selection/"]["put"]
    assert plan_operation["security"] == [{"managementToken": []}]
    assert selection_operation.get("security", []) == []
    assert set(plan_operation["responses"]) >= {
        "200",
        "400",
        "401",
        "403",
        "404",
        "409",
        "429",
    }
    assert set(selection_operation["responses"]) >= {"200", "400", "404", "409", "429"}
    invitation_properties = schema["components"]["schemas"]["Invitation"]["properties"]
    assert {"plan_options", "selected_option_id", "selected_at"} <= set(invitation_properties)
    option_properties = schema["components"]["schemas"]["InvitationPlanOption"]["properties"]
    assert "position" in option_properties

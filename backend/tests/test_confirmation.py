"""Tests for the author's irreversible final plan confirmation."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from unittest.mock import patch

import pytest
from django.db import IntegrityError, connections, transaction
from django.utils.timezone import now as django_now
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.common.capabilities import generate_management_token, hash_management_token
from apps.common.models import Invitation, InvitationPlanOption

pytestmark = pytest.mark.django_db


def authorization(token: str) -> dict[str, str]:
    """Build an APIClient Bearer authorization header."""
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def confirmation_path(invitation_id: object) -> str:
    """Return the final confirmation endpoint for an invitation identifier."""
    return f"/api/v1/invitations/{invitation_id}/confirmation/"


def selection_path(invitation_id: object) -> str:
    """Return the public planning selection endpoint."""
    return f"/api/v1/invitations/{invitation_id}/selection/"


def plan_path(invitation_id: object) -> str:
    """Return the author planning endpoint."""
    return f"/api/v1/invitations/{invitation_id}/plan-options/"


def response_path(invitation_id: object) -> str:
    """Return the public invitation response endpoint."""
    return f"/api/v1/invitations/{invitation_id}/response/"


def create_invitation(
    *,
    response_status: str = Invitation.ResponseStatus.ACCEPTED,
    author_name: str = "Алиса",
    recipient_name: str = "Борис",
) -> tuple[Invitation, str]:
    """Create an invitation with its own management capability."""
    token = generate_management_token()
    invitation = Invitation.objects.create(
        author_name=author_name,
        recipient_name=recipient_name,
        message="Подтверждаем наш план",
        management_token_hash=hash_management_token(token),
        response_status=response_status,
        responded_at=(
            None if response_status == Invitation.ResponseStatus.PENDING else django_now()
        ),
    )
    return invitation, token


def create_options(
    invitation: Invitation,
    *,
    selected_index: int | None = 0,
    selected_starts_at=None,
) -> list[InvitationPlanOption]:
    """Create two ordered options and optionally mark one as selected."""
    options = [
        InvitationPlanOption.objects.create(
            invitation=invitation,
            starts_at=(
                selected_starts_at
                if index == selected_index and selected_starts_at is not None
                else django_now() + timedelta(days=20 + index)
            ),
            place=f"Место {index + 1}",
            comment=f"Комментарий {index + 1}",
            position=index,
            selected_at=django_now() if index == selected_index else None,
        )
        for index in range(2)
    ]
    return options


def confirm(
    invitation: Invitation,
    token: str,
    option_id: object,
    *,
    client: APIClient | None = None,
):
    """Submit a valid final confirmation request."""
    return (client or APIClient()).put(
        confirmation_path(invitation.pk),
        {"confirmed": True, "option_id": str(option_id)},
        format="json",
        **authorization(token),
    )


def concurrent_put(
    barrier: Barrier,
    path: str,
    payload: dict[str, object],
    headers: dict[str, str] | None = None,
) -> int:
    """Issue a PUT on an independent database connection after all workers are ready."""
    connections.close_all()
    try:
        barrier.wait(timeout=10)
        response = APIClient().put(
            path,
            payload,
            format="json",
            **(headers or {}),
        )
        return response.status_code
    finally:
        connections.close_all()


def test_author_confirms_selected_future_option_once() -> None:
    """A valid capability stores confirmation and exposes only its aggregate timestamp."""
    invitation, token = create_invitation()
    options = create_options(invitation)
    invitation_updated_at = invitation.updated_at
    confirmed_at = django_now()

    with patch("apps.common.confirmation_views.now", return_value=confirmed_at):
        response = confirm(invitation, token, options[0].pk)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["confirmed_at"] == confirmed_at.isoformat().replace("+00:00", "Z")
    assert body["selected_option_id"] == str(options[0].pk)
    assert "confirmed_at" not in body["plan_options"][0]
    assert "management_token" not in body
    assert "management_token_hash" not in body
    assert response["Cache-Control"] == "private, no-store"
    assert response["Pragma"] == "no-cache"

    options[0].refresh_from_db()
    invitation.refresh_from_db()
    assert options[0].confirmed_at == confirmed_at
    assert options[1].confirmed_at is None
    assert invitation.updated_at > invitation_updated_at


def test_exact_confirmation_retry_preserves_both_timestamps() -> None:
    """A repeated confirmation is a no-op and does not even ask for a new clock value."""
    invitation, token = create_invitation()
    option = create_options(invitation)[0]
    first_confirmed_at = django_now()
    client = APIClient()

    with patch("apps.common.confirmation_views.now", return_value=first_confirmed_at):
        first_response = confirm(invitation, token, option.pk, client=client)
    assert first_response.status_code == status.HTTP_200_OK
    option.refresh_from_db()
    invitation.refresh_from_db()
    first_updated_at = invitation.updated_at

    with patch("apps.common.confirmation_views.now") as mocked_now:
        repeated_response = confirm(invitation, token, option.pk, client=client)

    assert repeated_response.status_code == status.HTTP_200_OK
    mocked_now.assert_not_called()
    option.refresh_from_db()
    invitation.refresh_from_db()
    assert option.confirmed_at == first_confirmed_at
    assert invitation.updated_at == first_updated_at
    assert repeated_response.json()["confirmed_at"] == first_response.json()["confirmed_at"]


def test_confirmation_retry_remains_idempotent_after_option_time_passes() -> None:
    """A network retry stays successful even if the already confirmed option has begun."""
    invitation, token = create_invitation()
    starts_at = django_now() - timedelta(seconds=1)
    first_confirmed_at = starts_at - timedelta(seconds=1)
    option = InvitationPlanOption.objects.create(
        invitation=invitation,
        starts_at=starts_at,
        place="Уже начавшееся место",
        position=0,
        selected_at=first_confirmed_at - timedelta(seconds=1),
        confirmed_at=first_confirmed_at,
    )

    with patch("apps.common.confirmation_views.now") as mocked_now:
        repeated_response = confirm(invitation, token, option.pk)

    assert repeated_response.status_code == status.HTTP_200_OK
    mocked_now.assert_not_called()
    option.refresh_from_db()
    assert option.confirmed_at == first_confirmed_at


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"confirmed": False},
        {"confirmed": None},
        {"confirmed": 1},
        {"confirmed": "true"},
        {"confirmed": "1"},
        [],
    ],
)
def test_confirmation_accepts_only_literal_json_true(payload: object) -> None:
    """Missing, coercible, false, null, and non-object bodies cannot mutate state."""
    invitation, token = create_invitation()
    option = create_options(invitation)[0]
    submitted_payload = (
        {"option_id": str(option.pk), **payload} if isinstance(payload, dict) else payload
    )

    response = APIClient().put(
        confirmation_path(invitation.pk),
        submitted_payload,
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response["Cache-Control"] == "private, no-store"
    option.refresh_from_db()
    assert option.confirmed_at is None


@pytest.mark.parametrize(
    "payload",
    [
        {"confirmed": True},
        {"confirmed": True, "option_id": None},
        {"confirmed": True, "option_id": "not-a-uuid"},
        {"confirmed": True, "option_id": 1},
    ],
)
def test_confirmation_requires_a_valid_option_id(payload: dict[str, object]) -> None:
    """Missing or malformed expected option identifiers fail before any mutation."""
    invitation, token = create_invitation()
    option = create_options(invitation)[0]
    invitation.refresh_from_db()
    previous_updated_at = invitation.updated_at

    response = APIClient().put(
        confirmation_path(invitation.pk),
        payload,
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "option_id" in response.json()
    assert response["Cache-Control"] == "private, no-store"
    option.refresh_from_db()
    invitation.refresh_from_db()
    assert option.confirmed_at is None
    assert invitation.updated_at == previous_updated_at


def test_confirmation_rejects_wrong_option_id_without_mutation() -> None:
    """A valid stale UUID cannot confirm whichever option happens to be selected now."""
    invitation, token = create_invitation()
    option = create_options(invitation)[0]
    selected_at = option.selected_at
    invitation.refresh_from_db()
    previous_updated_at = invitation.updated_at

    response = confirm(invitation, token, uuid.uuid4())

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response["Cache-Control"] == "private, no-store"
    option.refresh_from_db()
    invitation.refresh_from_db()
    assert option.selected_at == selected_at
    assert option.confirmed_at is None
    assert invitation.updated_at == previous_updated_at


def test_stale_author_cannot_confirm_previous_option_after_selection_changes() -> None:
    """An author looking at A cannot accidentally confirm newly selected B."""
    invitation, token = create_invitation()
    options = create_options(invitation)
    stale_option_id = options[0].pk
    switch_response = APIClient().put(
        selection_path(invitation.pk),
        {"option_id": str(options[1].pk)},
        format="json",
    )
    assert switch_response.status_code == status.HTTP_200_OK
    options[1].refresh_from_db()
    switched_at = options[1].selected_at
    invitation.refresh_from_db()
    switched_updated_at = invitation.updated_at

    confirmation_response = confirm(invitation, token, stale_option_id)

    assert confirmation_response.status_code == status.HTTP_409_CONFLICT
    options[0].refresh_from_db()
    options[1].refresh_from_db()
    invitation.refresh_from_db()
    assert options[0].selected_at is None
    assert options[0].confirmed_at is None
    assert options[1].selected_at == switched_at
    assert options[1].confirmed_at is None
    assert invitation.updated_at == switched_updated_at


@pytest.mark.parametrize(
    "response_status",
    [Invitation.ResponseStatus.PENDING, Invitation.ResponseStatus.DECLINED],
)
def test_confirmation_requires_accepted_invitation(response_status: str) -> None:
    """A selection cannot bypass the invitation response lifecycle requirement."""
    invitation, token = create_invitation(response_status=response_status)
    option = create_options(invitation)[0]

    response = confirm(invitation, token, option.pk)

    assert response.status_code == status.HTTP_409_CONFLICT
    option.refresh_from_db()
    assert option.confirmed_at is None


def test_confirmation_requires_a_selection() -> None:
    """An accepted invitation cannot be confirmed before the recipient chooses."""
    invitation, token = create_invitation()
    options = create_options(invitation, selected_index=None)

    response = confirm(invitation, token, options[0].pk)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert all(option.confirmed_at is None for option in options)


def test_confirmation_rejects_an_expired_selected_option() -> None:
    """A previously selected option must still be future-dated on first confirmation."""
    invitation, token = create_invitation()
    option = create_options(
        invitation,
        selected_starts_at=django_now() - timedelta(seconds=1),
    )[0]
    invitation.refresh_from_db()
    previous_updated_at = invitation.updated_at

    response = confirm(invitation, token, option.pk)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {
        "code": "selected_option_expired",
        "detail": "The selected option is no longer in the future.",
    }
    assert response["Cache-Control"] == "private, no-store"
    option.refresh_from_db()
    invitation.refresh_from_db()
    assert option.confirmed_at is None
    assert invitation.updated_at == previous_updated_at


def test_confirmation_authentication_and_object_capability_are_enforced() -> None:
    """Missing, malformed, wrong, and cross-invitation capabilities never confirm."""
    invitation, token = create_invitation()
    option = create_options(invitation)[0]
    other_invitation, other_token = create_invitation(
        author_name="Виктор",
        recipient_name="Галина",
    )
    create_options(other_invitation)
    client = APIClient()

    missing = client.put(
        confirmation_path(invitation.pk),
        {"confirmed": True, "option_id": str(option.pk)},
        format="json",
    )
    malformed = client.put(
        confirmation_path(invitation.pk),
        {"confirmed": True, "option_id": str(option.pk)},
        format="json",
        HTTP_AUTHORIZATION="Bearer short",
    )
    wrong = client.put(
        confirmation_path(invitation.pk),
        {"confirmed": True, "option_id": str(option.pk)},
        format="json",
        **authorization(generate_management_token()),
    )
    cross_invitation = client.put(
        confirmation_path(invitation.pk),
        {"confirmed": True, "option_id": str(option.pk)},
        format="json",
        **authorization(other_token),
    )

    assert missing.status_code == status.HTTP_401_UNAUTHORIZED
    assert missing["WWW-Authenticate"] == "Bearer"
    assert malformed.status_code == status.HTTP_401_UNAUTHORIZED
    assert wrong.status_code == status.HTTP_403_FORBIDDEN
    assert cross_invitation.status_code == status.HTTP_403_FORBIDDEN
    assert (
        token
        not in b"".join(
            response.content for response in (missing, malformed, wrong, cross_invitation)
        ).decode()
    )
    option.refresh_from_db()
    assert option.confirmed_at is None


def test_object_authorization_precedes_body_validation() -> None:
    """A caller without the capability cannot use validation as an object oracle."""
    invitation, _ = create_invitation()
    option = create_options(invitation)[0]

    response = APIClient().put(
        confirmation_path(invitation.pk),
        {"confirmed": False},
        format="json",
        **authorization(generate_management_token()),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    option.refresh_from_db()
    assert option.confirmed_at is None


def test_unknown_invitation_returns_404_for_valid_capability_shape() -> None:
    """A syntactically valid capability and UUID cannot confirm a missing record."""
    response = APIClient().put(
        confirmation_path(uuid.uuid4()),
        {"confirmed": True, "option_id": str(uuid.uuid4())},
        format="json",
        **authorization(generate_management_token()),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response["Cache-Control"] == "private, no-store"


def test_confirmation_mutates_only_the_addressed_invitation() -> None:
    """Several people's confirmations remain isolated by invitation and capability."""
    first, first_token = create_invitation()
    first_options = create_options(first)
    second, _ = create_invitation(author_name="Виктор", recipient_name="Галина")
    second_options = create_options(second)

    response = confirm(first, first_token, first_options[0].pk)

    assert response.status_code == status.HTTP_200_OK
    first_options[0].refresh_from_db()
    second_options[0].refresh_from_db()
    assert first_options[0].confirmed_at is not None
    assert second_options[0].confirmed_at is None


def test_confirmed_selection_allows_same_option_but_rejects_a_change() -> None:
    """The recipient may retry the same choice but cannot replace the final plan."""
    invitation, token = create_invitation()
    options = create_options(invitation)
    confirmation_response = confirm(invitation, token, options[0].pk)
    assert confirmation_response.status_code == status.HTTP_200_OK
    options[0].refresh_from_db()
    invitation.refresh_from_db()
    confirmed_at = options[0].confirmed_at
    selected_at = options[0].selected_at
    updated_at = invitation.updated_at

    same_response = APIClient().put(
        selection_path(invitation.pk),
        {"option_id": str(options[0].pk)},
        format="json",
    )
    changed_response = APIClient().put(
        selection_path(invitation.pk),
        {"option_id": str(options[1].pk)},
        format="json",
    )

    assert same_response.status_code == status.HTTP_200_OK
    assert same_response.json()["confirmed_at"] is not None
    assert changed_response.status_code == status.HTTP_409_CONFLICT
    options[0].refresh_from_db()
    options[1].refresh_from_db()
    invitation.refresh_from_db()
    assert options[0].selected_at == selected_at
    assert options[0].confirmed_at == confirmed_at
    assert options[1].selected_at is None
    assert invitation.updated_at == updated_at


def test_confirmed_response_allows_accepted_retry_but_rejects_decline() -> None:
    """The accepted answer becomes immutable after its selected plan is confirmed."""
    invitation, token = create_invitation()
    option = create_options(invitation)[0]
    confirmation_response = confirm(invitation, token, option.pk)
    assert confirmation_response.status_code == status.HTTP_200_OK
    invitation.refresh_from_db()
    responded_at = invitation.responded_at
    updated_at = invitation.updated_at

    accepted_retry = APIClient().put(
        response_path(invitation.pk),
        {"response_status": Invitation.ResponseStatus.ACCEPTED},
        format="json",
    )
    decline = APIClient().put(
        response_path(invitation.pk),
        {"response_status": Invitation.ResponseStatus.DECLINED},
        format="json",
    )

    assert accepted_retry.status_code == status.HTTP_200_OK
    assert decline.status_code == status.HTTP_409_CONFLICT
    invitation.refresh_from_db()
    option.refresh_from_db()
    assert invitation.response_status == Invitation.ResponseStatus.ACCEPTED
    assert invitation.responded_at == responded_at
    assert invitation.updated_at == updated_at
    assert option.selected_at is not None
    assert option.confirmed_at is not None


@pytest.mark.django_db(transaction=True)
def test_concurrent_confirmation_and_decline_preserve_lifecycle_invariant() -> None:
    """Row locking serializes confirm-versus-decline without a mixed final state."""
    invitation, token = create_invitation()
    option = create_options(invitation)[0]
    barrier = Barrier(3)

    with ThreadPoolExecutor(max_workers=2) as executor:
        confirmation_future = executor.submit(
            concurrent_put,
            barrier,
            confirmation_path(invitation.pk),
            {"confirmed": True, "option_id": str(option.pk)},
            authorization(token),
        )
        decline_future = executor.submit(
            concurrent_put,
            barrier,
            response_path(invitation.pk),
            {"response_status": Invitation.ResponseStatus.DECLINED},
        )
        barrier.wait(timeout=10)
        response_statuses = sorted(
            [confirmation_future.result(timeout=10), decline_future.result(timeout=10)]
        )

    assert response_statuses == [status.HTTP_200_OK, status.HTTP_409_CONFLICT]
    invitation.refresh_from_db()
    option.refresh_from_db()
    if invitation.response_status == Invitation.ResponseStatus.ACCEPTED:
        assert option.selected_at is not None
        assert option.confirmed_at is not None
    else:
        assert invitation.response_status == Invitation.ResponseStatus.DECLINED
        assert option.selected_at is None
        assert option.confirmed_at is None


@pytest.mark.django_db(transaction=True)
def test_concurrent_confirmation_and_selection_switch_preserve_final_choice() -> None:
    """Confirm A versus switch B has one winner and never silently confirms B."""
    invitation, token = create_invitation()
    options = create_options(invitation)
    barrier = Barrier(3)

    with ThreadPoolExecutor(max_workers=2) as executor:
        confirmation_future = executor.submit(
            concurrent_put,
            barrier,
            confirmation_path(invitation.pk),
            {"confirmed": True, "option_id": str(options[0].pk)},
            authorization(token),
        )
        switch_future = executor.submit(
            concurrent_put,
            barrier,
            selection_path(invitation.pk),
            {"option_id": str(options[1].pk)},
        )
        barrier.wait(timeout=10)
        confirmation_status = confirmation_future.result(timeout=10)
        switch_status = switch_future.result(timeout=10)

    assert sorted([confirmation_status, switch_status]) == [
        status.HTTP_200_OK,
        status.HTTP_409_CONFLICT,
    ]
    selected_options = list(
        InvitationPlanOption.objects.filter(
            invitation=invitation,
            selected_at__isnull=False,
        )
    )
    confirmed_options = list(
        InvitationPlanOption.objects.filter(
            invitation=invitation,
            confirmed_at__isnull=False,
        )
    )
    assert len(selected_options) == 1
    if selected_options[0].pk == options[0].pk:
        assert confirmation_status == status.HTTP_200_OK
        assert switch_status == status.HTTP_409_CONFLICT
        assert [option.pk for option in confirmed_options] == [options[0].pk]
    else:
        assert selected_options[0].pk == options[1].pk
        assert switch_status == status.HTTP_200_OK
        assert confirmation_status == status.HTTP_409_CONFLICT
        assert confirmed_options == []


def test_confirmed_plan_options_cannot_be_replaced() -> None:
    """Author plan replacement remains forbidden once the selected plan is final."""
    invitation, token = create_invitation()
    options = create_options(invitation)
    confirmation_response = confirm(invitation, token, options[0].pk)
    assert confirmation_response.status_code == status.HTTP_200_OK

    response = APIClient().put(
        plan_path(invitation.pk),
        {
            "options": [
                {
                    "starts_at": (django_now() + timedelta(days=40 + index)).isoformat(),
                    "place": f"Новое место {index + 1}",
                }
                for index in range(2)
            ]
        },
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert list(invitation.plan_options.values_list("pk", flat=True)) == [
        option.pk for option in options
    ]


def test_public_and_management_reads_expose_aggregate_confirmation_without_secrets() -> None:
    """Both reads expose final state but never expose the capability or stored digest."""
    invitation, token = create_invitation()
    options = create_options(invitation)
    confirmation_response = confirm(invitation, token, options[0].pk)
    assert confirmation_response.status_code == status.HTTP_200_OK
    client = APIClient()

    public_response = client.get(f"/api/v1/invitations/{invitation.pk}/")
    management_response = client.get(
        f"/api/v1/invitations/{invitation.pk}/manage/",
        **authorization(token),
    )

    for response in (public_response, management_response):
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["confirmed_at"] is not None
        assert "management_token" not in response.json()
        assert "management_token_hash" not in response.json()
        assert response["Cache-Control"] == "private, no-store"


def test_server_now_is_present_throughout_the_invitation_api_lifecycle() -> None:
    """Create, reads, and every state mutation return an aware server-clock snapshot."""
    client = APIClient()
    before_requests = django_now()
    create_response = client.post(
        "/api/v1/invitations/",
        {
            "author_name": "Алиса",
            "recipient_name": "Борис",
            "message": "Сверяем время с сервером",
        },
        format="json",
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    invitation_id = create_response.json()["id"]
    token = create_response.json()["management_token"]

    public_response = client.get(f"/api/v1/invitations/{invitation_id}/")
    management_response = client.get(
        f"/api/v1/invitations/{invitation_id}/manage/",
        **authorization(token),
    )
    accepted_response = client.put(
        response_path(invitation_id),
        {"response_status": Invitation.ResponseStatus.ACCEPTED},
        format="json",
    )
    plan_response = client.put(
        plan_path(invitation_id),
        {
            "options": [
                {
                    "starts_at": (django_now() + timedelta(days=30 + index)).isoformat(),
                    "place": f"Место {index + 1}",
                }
                for index in range(2)
            ]
        },
        format="json",
        **authorization(token),
    )
    assert plan_response.status_code == status.HTTP_200_OK
    selection_response = client.put(
        selection_path(invitation_id),
        {"option_id": plan_response.json()["plan_options"][0]["id"]},
        format="json",
    )
    confirmation_response = client.put(
        confirmation_path(invitation_id),
        {
            "confirmed": True,
            "option_id": plan_response.json()["plan_options"][0]["id"],
        },
        format="json",
        **authorization(token),
    )
    after_requests = django_now()

    responses = (
        create_response,
        public_response,
        management_response,
        accepted_response,
        plan_response,
        selection_response,
        confirmation_response,
    )
    assert [response.status_code for response in responses] == [
        status.HTTP_201_CREATED,
        status.HTTP_200_OK,
        status.HTTP_200_OK,
        status.HTTP_200_OK,
        status.HTTP_200_OK,
        status.HTTP_200_OK,
        status.HTTP_200_OK,
    ]
    for response in responses:
        server_now = datetime.fromisoformat(response.json()["server_now"]).astimezone(UTC)
        assert before_requests <= server_now <= after_requests


def test_database_rejects_confirmation_without_selection() -> None:
    """The database enforces the confirmation-to-selection lifecycle invariant."""
    invitation, _ = create_invitation()

    with pytest.raises(IntegrityError), transaction.atomic():
        InvitationPlanOption.objects.create(
            invitation=invitation,
            starts_at=django_now() + timedelta(days=20),
            place="Невыбранное место",
            position=0,
            confirmed_at=django_now(),
        )


def test_database_rejects_confirmation_before_selection() -> None:
    """A final confirmation timestamp cannot precede the recipient's selection."""
    invitation, _ = create_invitation()
    selected_at = django_now()

    with pytest.raises(IntegrityError), transaction.atomic():
        InvitationPlanOption.objects.create(
            invitation=invitation,
            starts_at=selected_at + timedelta(days=20),
            place="Нарушенный порядок",
            position=0,
            selected_at=selected_at,
            confirmed_at=selected_at - timedelta(microseconds=1),
        )


def test_database_rejects_confirmation_at_option_start_boundary() -> None:
    """Confirmation must be strictly earlier than starts_at, not equal to it."""
    invitation, _ = create_invitation()
    selected_at = django_now()
    starts_at = selected_at + timedelta(days=20)

    with pytest.raises(IntegrityError), transaction.atomic():
        InvitationPlanOption.objects.create(
            invitation=invitation,
            starts_at=starts_at,
            place="Слишком поздно",
            position=0,
            selected_at=selected_at,
            confirmed_at=starts_at,
        )


def test_database_allows_confirmation_at_selection_boundary() -> None:
    """The lower bound is inclusive when selection and confirmation are atomic-close."""
    invitation, _ = create_invitation()
    selected_at = django_now()

    option = InvitationPlanOption.objects.create(
        invitation=invitation,
        starts_at=selected_at + timedelta(days=20),
        place="Допустимая граница",
        position=0,
        selected_at=selected_at,
        confirmed_at=selected_at,
    )

    option.refresh_from_db()
    assert option.confirmed_at == selected_at


def test_confirmation_throttle_rejects_excess_retries_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The shared planning rate rejects a third confirmation request with Retry-After."""
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "invitation_plan", "2/min")
    invitation, token = create_invitation()
    option = create_options(invitation)[0]
    client = APIClient()
    request_address = {"REMOTE_ADDR": "192.0.2.70"}

    first = client.put(
        confirmation_path(invitation.pk),
        {"confirmed": True, "option_id": str(option.pk)},
        format="json",
        **authorization(token),
        **request_address,
    )
    second = client.put(
        confirmation_path(invitation.pk),
        {"confirmed": True, "option_id": str(option.pk)},
        format="json",
        **authorization(token),
        **request_address,
    )
    option.refresh_from_db()
    confirmed_at = option.confirmed_at
    invitation.refresh_from_db()
    updated_at = invitation.updated_at
    throttled = client.put(
        confirmation_path(invitation.pk),
        {"confirmed": True, "option_id": str(option.pk)},
        format="json",
        **authorization(token),
        **request_address,
    )

    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_200_OK
    assert throttled.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert throttled["Cache-Control"] == "private, no-store"
    assert 1 <= int(throttled["Retry-After"]) <= 60
    option.refresh_from_db()
    invitation.refresh_from_db()
    assert option.confirmed_at == confirmed_at
    assert invitation.updated_at == updated_at


def test_spoofed_forwarded_for_cannot_bypass_confirmation_throttle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Untrusted X-Forwarded-For values do not create new confirmation identities."""
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "invitation_plan", "1/min")
    invitation, token = create_invitation()
    option = create_options(invitation)[0]
    client = APIClient()

    first = client.put(
        confirmation_path(invitation.pk),
        {"confirmed": True, "option_id": str(option.pk)},
        format="json",
        **authorization(token),
        REMOTE_ADDR="192.0.2.71",
        HTTP_X_FORWARDED_FOR="198.51.100.1",
    )
    throttled = client.put(
        confirmation_path(invitation.pk),
        {"confirmed": True, "option_id": str(option.pk)},
        format="json",
        **authorization(token),
        REMOTE_ADDR="192.0.2.71",
        HTTP_X_FORWARDED_FOR="203.0.113.1",
    )

    assert first.status_code == status.HTTP_200_OK
    assert throttled.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.parametrize("method", ["GET", "POST", "PATCH", "DELETE"])
def test_confirmation_endpoint_rejects_unsupported_methods(method: str) -> None:
    """Final confirmation exposes only PUT and OPTIONS."""
    invitation, token = create_invitation()
    option = create_options(invitation)[0]

    response = APIClient().generic(
        method,
        confirmation_path(invitation.pk),
        data={"confirmed": True, "option_id": str(option.pk)},
        content_type="application/json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert response["Cache-Control"] == "private, no-store"


def test_confirmation_options_advertises_only_put() -> None:
    """Endpoint metadata and CORS consumers see only PUT and OPTIONS."""
    invitation, token = create_invitation()

    response = APIClient().options(
        confirmation_path(invitation.pk),
        **authorization(token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert {method.strip() for method in response["Allow"].split(",")} == {
        "PUT",
        "OPTIONS",
    }
    assert response["Cache-Control"] == "private, no-store"


def test_openapi_documents_final_confirmation_contract() -> None:
    """Schema documents management auth, request, result, and all failure statuses."""
    response = APIClient().get("/api/schema/?format=json")

    assert response.status_code == status.HTTP_200_OK
    schema = response.json()
    path = schema["paths"]["/api/v1/invitations/{id}/confirmation/"]
    assert "put" in path
    assert not {"get", "post", "patch", "delete"}.intersection(path)
    operation = path["put"]
    assert operation["security"] == [{"managementToken": []}]
    assert set(operation["responses"]) >= {
        "200",
        "400",
        "401",
        "403",
        "404",
        "409",
        "429",
    }
    request_reference = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    assert request_reference.endswith("/InvitationConfirmation")
    confirmation_schema = schema["components"]["schemas"]["InvitationConfirmation"]
    confirmation_properties = confirmation_schema["properties"]
    assert set(confirmation_schema["required"]) == {"confirmed", "option_id"}
    confirmed_reference = confirmation_properties["confirmed"]["allOf"][0]["$ref"]
    confirmed_schema_name = confirmed_reference.rsplit("/", maxsplit=1)[-1]
    confirmed_schema = schema["components"]["schemas"][confirmed_schema_name]
    assert confirmed_schema == {"type": "boolean", "enum": [True]}
    assert confirmation_properties["option_id"]["type"] == "string"
    assert confirmation_properties["option_id"]["format"] == "uuid"
    invitation_properties = schema["components"]["schemas"]["Invitation"]["properties"]
    assert invitation_properties["confirmed_at"]["readOnly"] is True
    assert invitation_properties["server_now"] == {
        "type": "string",
        "format": "date-time",
        "readOnly": True,
        "description": "Server time captured while serializing this API response.",
    }

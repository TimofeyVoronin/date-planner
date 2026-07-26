"""Tests for invitation-owned activity option collections."""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.models import ActivityOption, Invitation

pytestmark = pytest.mark.django_db


def create_invitation(
    client: APIClient,
    *,
    creation_mode: str = Invitation.CreationMode.EXTENDED,
) -> tuple[Invitation, str]:
    """Create one invitation and return its record and management capability."""
    response = client.post(
        "/api/v1/invitations/",
        {
            "author_name": "Алиса",
            "recipient_name": "Борис",
            "message": "Выбери, чем займёмся",
            "creation_mode": creation_mode,
        },
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    return Invitation.objects.get(pk=body["id"]), body["management_token"]


def authorization(token: str) -> dict[str, str]:
    """Build an HTTP Bearer header for a management capability."""
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def activity_path(invitation: Invitation) -> str:
    """Return the protected collection URL for one invitation."""
    return f"/api/v1/invitations/{invitation.pk}/activity-options/"


def activity_payload(*, suffix: str = "") -> dict[str, list[dict[str, str]]]:
    """Build a valid ordered collection for replacement tests."""
    return {
        "options": [
            {
                "title": f"Прогулка{suffix}",
                "description": "Неспешно пройтись по набережной",
                "image_key": "activity-walk",
                "place": "Набережная",
            },
            {
                "title": f"Кино{suffix}",
                "description": "Выбрать фильм вместе",
                "image_key": "activity-movie",
                "place": "Кинотеатр",
            },
            {
                "title": f"Кофе{suffix}",
                "description": "Посидеть в уютной кофейне",
                "image_key": "activity-coffee",
                "place": "Кофейня",
            },
        ]
    }


def test_activity_option_model_keeps_future_metadata_and_order() -> None:
    """The model reserves optional metadata without exposing it in the first API."""
    invitation = Invitation.objects.create(
        author_name="Алиса",
        recipient_name="Борис",
        creation_mode=Invitation.CreationMode.EXTENDED,
        publication_status=Invitation.PublicationStatus.DRAFT,
        published_at=None,
    )
    option = ActivityOption.objects.create(
        invitation=invitation,
        title="Боулинг",
        description="Две партии",
        image_key="activity-bowling",
        place="Боулинг-клуб",
        estimated_price=Decimal("2500.00"),
        external_url="https://example.com/bowling",
        position=0,
    )

    assert option.pk is not None
    assert option.estimated_price == Decimal("2500.00")
    assert option.external_url == "https://example.com/bowling"
    assert option.created_at is not None
    assert option.updated_at is not None
    assert str(option) == f"{invitation.pk}: Боулинг"


def test_database_rejects_invalid_activity_positions_and_price() -> None:
    """Database constraints protect direct writes outside API serializers."""
    invitation = Invitation.objects.create(
        author_name="Алиса",
        recipient_name="Борис",
        creation_mode=Invitation.CreationMode.EXTENDED,
        publication_status=Invitation.PublicationStatus.DRAFT,
        published_at=None,
    )
    ActivityOption.objects.create(invitation=invitation, title="Кино", position=0)

    with pytest.raises(IntegrityError), transaction.atomic():
        ActivityOption.objects.create(invitation=invitation, title="Кофе", position=0)

    with pytest.raises(IntegrityError), transaction.atomic():
        ActivityOption.objects.create(invitation=invitation, title="Прогулка", position=6)

    with pytest.raises(IntegrityError), transaction.atomic():
        ActivityOption.objects.create(
            invitation=invitation,
            title="Боулинг",
            position=1,
            estimated_price=Decimal("-1.00"),
        )


def test_extended_draft_starts_with_an_empty_activity_collection() -> None:
    """The protected collection exists before the author adds any options."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = client.get(activity_path(invitation), **authorization(token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"options": []}


def test_activity_collection_returns_404_for_unknown_invitation() -> None:
    """A valid capability cannot turn a missing UUID into a visible resource."""
    client = APIClient()
    _, token = create_invitation(client)

    response = client.get(
        f"/api/v1/invitations/{uuid4()}/activity-options/",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_management_can_replace_and_read_ordered_activity_options() -> None:
    """An extended draft stores three to six options in submitted array order."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = client.put(
        activity_path(invitation),
        activity_payload(),
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response["Cache-Control"] == "private, no-store"
    assert response["Pragma"] == "no-cache"
    body = response.json()
    assert [item["position"] for item in body["options"]] == [0, 1, 2]
    assert [item["title"] for item in body["options"]] == [
        "Прогулка",
        "Кино",
        "Кофе",
    ]
    assert all(UUID(item["id"]) for item in body["options"])
    assert all(
        set(item) == {"id", "title", "description", "image_key", "place", "position"}
        for item in body["options"]
    )
    assert list(invitation.activity_options.values_list("title", flat=True)) == [
        "Прогулка",
        "Кино",
        "Кофе",
    ]
    assert not invitation.activity_options.exclude(
        estimated_price__isnull=True,
        external_url="",
    ).exists()

    read_response = client.get(activity_path(invitation), **authorization(token))

    assert read_response.status_code == status.HTTP_200_OK
    assert read_response.json() == body
    assert read_response["Cache-Control"] == "private, no-store"
    assert read_response["Pragma"] == "no-cache"


def test_exact_activity_replacement_retry_is_idempotent() -> None:
    """An identical PUT keeps option UUIDs, timestamps, and invitation updated_at stable."""
    client = APIClient()
    invitation, token = create_invitation(client)
    first = client.put(
        activity_path(invitation),
        activity_payload(),
        format="json",
        **authorization(token),
    )
    assert first.status_code == status.HTTP_200_OK
    invitation.refresh_from_db()
    first_invitation_updated_at = invitation.updated_at
    first_options = list(invitation.activity_options.values("id", "created_at", "updated_at"))

    repeated = client.put(
        activity_path(invitation),
        activity_payload(),
        format="json",
        **authorization(token),
    )

    assert repeated.status_code == status.HTTP_200_OK
    assert repeated.json() == first.json()
    invitation.refresh_from_db()
    assert invitation.updated_at == first_invitation_updated_at
    assert list(invitation.activity_options.values("id", "created_at", "updated_at")) == (
        first_options
    )


def test_changed_activity_collection_is_replaced_atomically() -> None:
    """A changed collection receives new UUIDs and persists its new order as one unit."""
    client = APIClient()
    invitation, token = create_invitation(client)
    first = client.put(
        activity_path(invitation),
        activity_payload(),
        format="json",
        **authorization(token),
    )
    first_ids = {item["id"] for item in first.json()["options"]}
    replacement_payload = activity_payload(suffix=" — новый вариант")
    replacement_payload["options"].reverse()

    replacement = client.put(
        activity_path(invitation),
        replacement_payload,
        format="json",
        **authorization(token),
    )

    assert replacement.status_code == status.HTTP_200_OK
    assert [item["position"] for item in replacement.json()["options"]] == [0, 1, 2]
    assert [item["title"] for item in replacement.json()["options"]] == [
        "Кофе — новый вариант",
        "Кино — новый вариант",
        "Прогулка — новый вариант",
    ]
    assert first_ids.isdisjoint({item["id"] for item in replacement.json()["options"]})


@pytest.mark.parametrize("count", [0, 1, 2, 7])
def test_activity_collection_requires_three_to_six_options(count: int) -> None:
    """The first activity contract rejects collections outside its documented bounds."""
    client = APIClient()
    invitation, token = create_invitation(client)
    options = (activity_payload()["options"] * 3)[:count]

    response = client.put(
        activity_path(invitation),
        {"options": options},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "options" in response.json()
    assert not invitation.activity_options.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "   "),
        ("title", "A" * 121),
        ("description", "A" * 501),
        ("image_key", "A" * 81),
        ("image_key", "https://example.com/image.svg"),
        ("place", "A" * 201),
    ],
)
def test_activity_collection_validates_each_editable_field(field: str, value: str) -> None:
    """Nested validation reports the exact invalid option field."""
    client = APIClient()
    invitation, token = create_invitation(client)
    payload = activity_payload()
    payload["options"][1][field] = value

    response = client.put(
        activity_path(invitation),
        payload,
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field in response.json()["options"][1]
    assert not invitation.activity_options.exists()


@pytest.mark.parametrize("field", ["position", "estimated_price", "external_url", "selected_at"])
def test_first_activity_api_rejects_internal_or_future_fields(field: str) -> None:
    """The first API does not silently accept fields reserved for later tasks."""
    client = APIClient()
    invitation, token = create_invitation(client)
    payload = activity_payload()
    payload["options"][0][field] = "unexpected"

    response = client.put(
        activity_path(invitation),
        payload,
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field in response.json()["options"][0]
    assert not invitation.activity_options.exists()


def test_activity_collection_rejects_unknown_top_level_fields_and_non_object_payload() -> None:
    """Malformed collection shapes return 400 without partial writes or server errors."""
    client = APIClient()
    invitation, token = create_invitation(client)

    unknown = client.put(
        activity_path(invitation),
        {**activity_payload(), "invitation_id": str(invitation.pk)},
        format="json",
        **authorization(token),
    )
    non_object = client.put(
        activity_path(invitation),
        activity_payload()["options"],
        format="json",
        **authorization(token),
    )

    assert unknown.status_code == status.HTTP_400_BAD_REQUEST
    assert "invitation_id" in unknown.json()
    assert non_object.status_code == status.HTTP_400_BAD_REQUEST
    assert not invitation.activity_options.exists()


def test_activity_collection_requires_matching_management_capability() -> None:
    """Missing, invalid, and foreign tokens cannot read or replace another collection."""
    client = APIClient()
    invitation, token = create_invitation(client)
    other_invitation, other_token = create_invitation(client)

    missing = client.get(activity_path(invitation))
    invalid = client.get(activity_path(invitation), **authorization("A" * 43))
    foreign = client.put(
        activity_path(invitation),
        activity_payload(),
        format="json",
        **authorization(other_token),
    )

    assert missing.status_code == status.HTTP_401_UNAUTHORIZED
    assert invalid.status_code == status.HTTP_403_FORBIDDEN
    assert foreign.status_code == status.HTTP_403_FORBIDDEN
    assert not invitation.activity_options.exists()
    assert other_invitation.pk != invitation.pk
    assert token != other_token


def test_quick_invitation_has_no_activity_collection_contract() -> None:
    """Quick invitations cannot read or edit extended-builder activity resources."""
    client = APIClient()
    invitation, token = create_invitation(
        client,
        creation_mode=Invitation.CreationMode.QUICK,
    )

    read_response = client.get(activity_path(invitation), **authorization(token))
    write_response = client.put(
        activity_path(invitation),
        activity_payload(),
        format="json",
        **authorization(token),
    )

    assert read_response.status_code == status.HTTP_409_CONFLICT
    assert write_response.status_code == status.HTTP_409_CONFLICT
    assert not invitation.activity_options.exists()


def test_published_activity_collection_is_read_only() -> None:
    """Publication freezes activity editing while preserving management visibility."""
    client = APIClient()
    invitation, token = create_invitation(client)
    saved = client.put(
        activity_path(invitation),
        activity_payload(),
        format="json",
        **authorization(token),
    )
    assert saved.status_code == status.HTTP_200_OK
    publish = client.put(
        f"/api/v1/invitations/{invitation.pk}/publish/",
        {},
        format="json",
        **authorization(token),
    )
    assert publish.status_code == status.HTTP_200_OK

    read_response = client.get(activity_path(invitation), **authorization(token))
    write_response = client.put(
        activity_path(invitation),
        activity_payload(suffix=" новое"),
        format="json",
        **authorization(token),
    )

    assert read_response.status_code == status.HTTP_200_OK
    assert read_response.json() == saved.json()
    assert write_response.status_code == status.HTTP_409_CONFLICT
    assert [item["title"] for item in read_response.json()["options"]] == [
        "Прогулка",
        "Кино",
        "Кофе",
    ]
    public_response = client.get(f"/api/v1/invitations/{invitation.pk}/")
    assert public_response.status_code == status.HTTP_200_OK
    assert "activity_options" not in public_response.json()


def test_deleting_invitation_cascades_activity_options() -> None:
    """Activity ideas cannot outlive the invitation that owns them."""
    client = APIClient()
    invitation, token = create_invitation(client)
    response = client.put(
        activity_path(invitation),
        activity_payload(),
        format="json",
        **authorization(token),
    )
    assert response.status_code == status.HTTP_200_OK

    invitation.delete()

    assert ActivityOption.objects.count() == 0


def test_openapi_documents_activity_collection_bounds_and_safe_fields() -> None:
    """The schema exposes the protected whole-collection GET and PUT contract."""
    response = APIClient().get("/api/schema/?format=json")

    assert response.status_code == status.HTTP_200_OK
    schema = response.json()
    path = schema["paths"]["/api/v1/invitations/{id}/activity-options/"]
    get_operation = path["get"]
    put_operation = path["put"]
    assert get_operation["security"] == [{"managementToken": []}]
    assert put_operation["security"] == [{"managementToken": []}]
    assert set(put_operation["responses"]) == {"200", "400", "401", "403", "404", "409", "429"}

    request_reference = put_operation["requestBody"]["content"]["application/json"]["schema"][
        "$ref"
    ]
    request_component = request_reference.rsplit("/", maxsplit=1)[-1]
    options_schema = schema["components"]["schemas"][request_component]["properties"]["options"]
    assert options_schema["minItems"] == 3
    assert options_schema["maxItems"] == 6

    item_reference = options_schema["items"]["$ref"]
    item_component = item_reference.rsplit("/", maxsplit=1)[-1]
    assert set(schema["components"]["schemas"][item_component]["properties"]) == {
        "title",
        "description",
        "image_key",
        "place",
    }
    assert "estimated_price" not in str(put_operation)
    assert "external_url" not in str(put_operation)

"""Tests for the safe final-screen text template contract."""

import importlib
import uuid

import pytest
from django.apps import apps as django_apps
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.final_templates import (
    DEFAULT_FINAL_TEXT_TEMPLATE,
    FINAL_TEMPLATE_VARIABLES,
    FinalTemplateValidationError,
    normalize_final_text_template,
    render_final_text_template,
)
from apps.common.models import Invitation, InvitationScreen

pytestmark = pytest.mark.django_db

SCREEN_RESPONSE_FIELDS = {
    "screen_type",
    "title",
    "subtitle",
    "button_text",
    "secondary_button_text",
    "image_key",
    "template_text",
}


def create_invitation(
    client: APIClient,
    *,
    creation_mode: str = Invitation.CreationMode.EXTENDED,
) -> tuple[Invitation, str]:
    """Create one invitation and return its management capability."""
    response = client.post(
        "/api/v1/invitations/",
        {
            "author_name": "Алиса",
            "recipient_name": "Борис",
            "message": "Давай сходим на свидание?",
            "creation_mode": creation_mode,
        },
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    return (
        Invitation.objects.get(pk=response.json()["id"]),
        response.json()["management_token"],
    )


def authorization(token: str) -> dict[str, str]:
    """Build a valid Bearer authorization header."""
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def update_url(invitation: Invitation) -> str:
    """Return the protected final-screen resource URL."""
    return f"/api/v1/invitations/{invitation.pk}/screens/final/"


def test_safe_template_renders_only_exact_allowed_variables() -> None:
    """Rendering substitutes plain values and preserves escaped literal braces."""
    values = {
        "author": "Алиса",
        "recipient": "Борис",
        "date": "27 июля",
        "time": "19:00",
        "place": "Кофейня",
        "activity": "Кино",
    }

    assert FINAL_TEMPLATE_VARIABLES == (
        "author",
        "recipient",
        "date",
        "time",
        "place",
        "activity",
    )
    assert render_final_text_template(
        "{{План}}: {recipient}, {author} ждёт тебя {date} в {time}, "
        "место — {place}, активность — {activity}.",
        values,
    ) == ("{План}: Борис, Алиса ждёт тебя 27 июля в 19:00, место — Кофейня, активность — Кино.")


def test_render_requires_every_referenced_variable_value() -> None:
    """Rendering fails explicitly instead of inventing a missing plan value."""
    with pytest.raises(FinalTemplateValidationError, match="activity"):
        render_final_text_template("План: {activity}", {"recipient": "Борис"})


def test_rendered_values_are_not_parsed_as_nested_templates() -> None:
    """User data remains plain text even when it contains template-like characters."""
    values = {variable: f"value-{variable}" for variable in FINAL_TEMPLATE_VARIABLES}
    values["recipient"] = "{author.name}"

    assert render_final_text_template("Получатель: {recipient}", values) == (
        "Получатель: {author.name}"
    )


@pytest.mark.parametrize(
    "template",
    [
        "{unknown}",
        "{author.name}",
        "{activity[title]}",
        "{date:>20}",
        "{recipient!r}",
        "{}",
        "{recipient",
        "recipient}",
    ],
)
def test_safe_template_rejects_advanced_or_malformed_syntax(template: str) -> None:
    """The allow-list excludes traversal, indexing, conversions, and broken braces."""
    with pytest.raises(FinalTemplateValidationError):
        normalize_final_text_template(template)


def test_template_length_counts_unicode_characters() -> None:
    """The 1000-character limit does not count one emoji as two characters."""
    template = f"{'x' * 999}💘"

    assert normalize_final_text_template(template) == template


def test_extended_screen_defaults_store_only_one_final_template() -> None:
    """New extended invitations receive one default template on the final screen."""
    invitation, _ = create_invitation(APIClient())

    final_screen = invitation.screens.get(screen_type=InvitationScreen.ScreenType.FINAL)
    assert final_screen.template_text == DEFAULT_FINAL_TEXT_TEMPLATE
    assert (
        not invitation.screens.exclude(screen_type=InvitationScreen.ScreenType.FINAL)
        .exclude(template_text="")
        .exists()
    )


def test_template_migration_backfills_existing_final_screens() -> None:
    """The data migration upgrades final screens created before DPL-501."""
    invitation, _ = create_invitation(APIClient())
    final_screen = invitation.screens.get(screen_type=InvitationScreen.ScreenType.FINAL)
    InvitationScreen.objects.filter(pk=final_screen.pk).update(template_text="")
    migration = importlib.import_module(
        "apps.common.migrations.0013_invitationscreen_template_text"
    )

    migration.backfill_final_screen_template(django_apps, None)

    final_screen.refresh_from_db()
    assert final_screen.template_text == DEFAULT_FINAL_TEXT_TEMPLATE


def test_database_rejects_template_on_nonfinal_screen() -> None:
    """A direct database write cannot attach final copy to another screen type."""
    invitation, _ = create_invitation(APIClient())
    screen = invitation.screens.get(screen_type=InvitationScreen.ScreenType.ACCEPTANCE)

    with pytest.raises(IntegrityError), transaction.atomic():
        InvitationScreen.objects.filter(pk=screen.pk).update(
            template_text="{recipient}, это не финальный экран."
        )


@pytest.mark.parametrize(
    "template",
    [
        "{unknown}",
        "{author.name}",
        "{activity[title]}",
        "{date:>20}",
        "{recipient!r}",
        "{recipient",
        "",
        "x" * 1001,
    ],
)
def test_final_template_endpoint_rejects_unsafe_values(template: str) -> None:
    """The management API rejects every value outside the safe grammar."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = client.patch(
        update_url(invitation),
        {"template_text": template},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "template_text" in response.json()


def test_final_template_patch_is_normalized_minimal_and_idempotent() -> None:
    """A safe update trims outer whitespace and exact retries keep timestamps stable."""
    client = APIClient()
    invitation, token = create_invitation(client)
    screen = invitation.screens.get(screen_type=InvitationScreen.ScreenType.FINAL)
    template = "{recipient}, {author} ждёт тебя {date} в {time} в {place}: {activity}."

    first_response = client.patch(
        update_url(invitation),
        {"template_text": f"  {template}  "},
        format="json",
        **authorization(token),
    )

    assert first_response.status_code == status.HTTP_200_OK
    assert first_response.json()["template_text"] == template
    screen.refresh_from_db()
    first_updated_at = screen.updated_at

    second_response = client.patch(
        update_url(invitation),
        {"template_text": template},
        format="json",
        **authorization(token),
    )
    empty_response = client.patch(
        update_url(invitation),
        {},
        format="json",
        **authorization(token),
    )

    assert second_response.status_code == status.HTTP_200_OK
    assert empty_response.status_code == status.HTTP_200_OK
    screen.refresh_from_db()
    assert screen.updated_at == first_updated_at


def test_final_template_endpoint_rejects_other_screen_fields() -> None:
    """DPL-501 exposes only the template before the full DPL-502 editor."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = client.patch(
        update_url(invitation),
        {"title": "Новый финал", "image_key": "final-night"},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert set(response.json()) == {"image_key", "title"}


def test_final_template_requires_capability_and_unpublished_extended_invitation() -> None:
    """Quick and published invitations stay outside the builder editing boundary."""
    client = APIClient()
    draft, draft_token = create_invitation(client)
    _, another_token = create_invitation(client)
    quick, quick_token = create_invitation(
        client,
        creation_mode=Invitation.CreationMode.QUICK,
    )

    missing_response = client.patch(
        update_url(draft),
        {"template_text": DEFAULT_FINAL_TEXT_TEMPLATE},
        format="json",
    )
    wrong_response = client.patch(
        update_url(draft),
        {"template_text": DEFAULT_FINAL_TEXT_TEMPLATE},
        format="json",
        **authorization(another_token),
    )
    quick_response = client.patch(
        update_url(quick),
        {"template_text": DEFAULT_FINAL_TEXT_TEMPLATE},
        format="json",
        **authorization(quick_token),
    )

    publish_response = client.put(
        f"/api/v1/invitations/{draft.pk}/publish/",
        **authorization(draft_token),
    )
    published_response = client.patch(
        update_url(draft),
        {"template_text": "Другая безопасная строка"},
        format="json",
        **authorization(draft_token),
    )

    assert missing_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert wrong_response.status_code == status.HTTP_403_FORBIDDEN
    assert quick_response.status_code == status.HTTP_409_CONFLICT
    assert publish_response.status_code == status.HTTP_200_OK
    assert published_response.status_code == status.HTTP_409_CONFLICT


def test_public_snapshot_exposes_saved_final_template_after_publication() -> None:
    """The recipient receives only the validated final template saved before publication."""
    client = APIClient()
    invitation, token = create_invitation(client)
    template = "{recipient}, встречаемся {date} в {time}: {activity}, место — {place}."

    update_response = client.patch(
        update_url(invitation),
        {"template_text": template},
        format="json",
        **authorization(token),
    )
    publish_response = client.put(
        f"/api/v1/invitations/{invitation.pk}/publish/",
        **authorization(token),
    )
    public_response = client.get(f"/api/v1/invitations/{invitation.pk}/")

    assert update_response.status_code == status.HTTP_200_OK
    assert publish_response.status_code == status.HTTP_200_OK
    assert public_response.status_code == status.HTTP_200_OK
    final_screen = next(
        screen
        for screen in public_response.json()["screens"]
        if screen["screen_type"] == InvitationScreen.ScreenType.FINAL
    )
    assert final_screen["template_text"] == template


def test_final_template_endpoint_returns_404_for_unknown_invitation() -> None:
    """A valid token does not reveal an unrelated or absent invitation."""
    client = APIClient()
    _, token = create_invitation(client)

    response = client.patch(
        f"/api/v1/invitations/{uuid.uuid4()}/screens/final/",
        {"template_text": DEFAULT_FINAL_TEXT_TEMPLATE},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_openapi_documents_final_template_patch_contract() -> None:
    """The schema exposes one safe template field and the normal capability outcomes."""
    response = APIClient().get("/api/schema/?format=json")

    assert response.status_code == status.HTTP_200_OK
    schema = response.json()
    operation = schema["paths"]["/api/v1/invitations/{id}/screens/final/"]["patch"]
    request_component = operation["requestBody"]["content"]["application/json"]["schema"][
        "$ref"
    ].rsplit("/", maxsplit=1)[-1]
    response_component = operation["responses"]["200"]["content"]["application/json"]["schema"][
        "$ref"
    ].rsplit("/", maxsplit=1)[-1]

    assert operation["security"] == [{"managementToken": []}]
    assert set(schema["components"]["schemas"][request_component]["properties"]) == {
        "template_text"
    }
    assert set(schema["components"]["schemas"][response_component]["properties"]) == (
        SCREEN_RESPONSE_FIELDS
    )

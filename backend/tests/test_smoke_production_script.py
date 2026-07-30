"""Focused tests for the post-deployment production smoke client."""

from __future__ import annotations

import html
import importlib.util
import json
import os
import struct
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request

import pytest

PROJECT_ROOT = Path(os.getenv("DATE_PLANNER_PROJECT_ROOT", Path(__file__).resolve().parents[2]))
SCRIPT_PATH = PROJECT_ROOT / "deploy" / "scripts" / "smoke-production.py"
SPEC = importlib.util.spec_from_file_location("date_planner_smoke_production", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
SMOKE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SMOKE
SPEC.loader.exec_module(SMOKE)

APP_ORIGIN = "https://dates.example.test"
API_ORIGIN = "https://api.dates.example.test"
INVITATION_ID = "10000000-0000-4000-8000-000000000001"
PLAN_IDS = (
    "20000000-0000-4000-8000-000000000001",
    "20000000-0000-4000-8000-000000000002",
)
ACTIVITY_IDS = (
    "30000000-0000-4000-8000-000000000001",
    "30000000-0000-4000-8000-000000000002",
    "30000000-0000-4000-8000-000000000003",
)
MANAGEMENT_TOKEN = "production-smoke-secret-capability-value"
CONFIRMED_AT = "2026-07-30T08:00:00Z"

COMMON_HEADERS = {
    "Strict-Transport-Security": "max-age=3600",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
PRIVATE_HEADERS = {
    "Cache-Control": "private, no-store",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow",
}


class FakeResponse:
    """Minimal urllib response returned by the deterministic fake opener."""

    def __init__(
        self,
        body: bytes,
        *,
        headers: Mapping[str, str],
        status: int = 200,
    ) -> None:
        self.body = body
        self.headers = dict(headers)
        self.status = status
        self.closed = False

    def read(self, limit: int) -> bytes:
        return self.body[:limit]

    def close(self) -> None:
        self.closed = True


class FakeOpener:
    """Queue responses and retain requests for capability-boundary assertions."""

    def __init__(self, responses: list[FakeResponse | Exception]) -> None:
        self.responses = responses
        self.requests: list[Request] = []

    def open(self, request: Request, *, timeout: int) -> FakeResponse:
        assert timeout == SMOKE.REQUEST_TIMEOUT_SECONDS
        self.requests.append(request)
        next_response = self.responses.pop(0)
        if isinstance(next_response, Exception):
            raise next_response
        return next_response


def json_response(
    payload: Mapping[str, object],
    *,
    status: int = 200,
) -> FakeResponse:
    headers = {
        **COMMON_HEADERS,
        "Cache-Control": "private, no-store",
        "Content-Type": "application/json",
    }
    return FakeResponse(
        json.dumps(payload, ensure_ascii=False).encode(),
        headers=headers,
        status=status,
    )


def html_response(body: str, *, personal: bool = False) -> FakeResponse:
    headers = {**COMMON_HEADERS, "Content-Type": "text/html; charset=utf-8"}
    if personal:
        headers.update(PRIVATE_HEADERS)
    return FakeResponse(body.encode(), headers=headers)


def invitation(
    *,
    author_name: str = "Production Smoke Author",
    recipient_name: str = "Production Smoke Recipient",
    message: str = "Synthetic production smoke invitation",
    planning_mode: str = "after_acceptance",
    publication_status: str = "draft",
    response_status: str = "pending",
    plan_options: list[dict[str, object]] | None = None,
    activity_options: list[dict[str, object]] | None = None,
    selected_option_id: str | None = None,
    selected_activity_option_id: str | None = None,
    confirmed_plan: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "id": INVITATION_ID,
        "author_name": author_name,
        "recipient_name": recipient_name,
        "message": message,
        "creation_mode": "extended",
        "planning_mode": planning_mode,
        "publication_status": publication_status,
        "published_at": ("2026-07-30T07:00:00Z" if publication_status == "published" else None),
        "response_status": response_status,
        "screens": [
            {"screen_type": screen_type}
            for screen_type in (
                "invitation",
                "acceptance",
                "date_selection",
                "activity_selection",
                "final",
            )
        ],
        "plan_options": plan_options or [],
        "activity_options": activity_options or [],
        "selected_option_id": selected_option_id,
        "selected_at": ("2026-07-30T07:30:00Z" if selected_option_id is not None else None),
        "selected_activity_option_id": selected_activity_option_id,
        "activity_selected_at": (
            "2026-07-30T07:35:00Z" if selected_activity_option_id is not None else None
        ),
        "confirmed_at": CONFIRMED_AT if confirmed_plan is not None else None,
        "confirmed_plan": confirmed_plan,
    }


def invitation_metadata_html() -> str:
    canonical = f"{APP_ORIGIN}/invite/{INVITATION_ID}"
    image_url = f"{APP_ORIGIN}/images/social/invitation-preview.png"
    meta = {
        "description": SMOKE.META_DESCRIPTION,
        "theme-color": "#fff3f6",
        "robots": "noindex, nofollow",
        "referrer": "no-referrer",
        "og:title": SMOKE.META_TITLE,
        "og:description": SMOKE.META_DESCRIPTION,
        "og:type": "website",
        "og:site_name": "Date Planner",
        "og:locale": "ru_RU",
        "og:url": canonical,
        "og:image": image_url,
        "og:image:alt": SMOKE.META_IMAGE_ALT,
        "og:image:width": "1200",
        "og:image:height": "630",
        "twitter:card": "summary_large_image",
        "twitter:title": SMOKE.META_TITLE,
        "twitter:description": SMOKE.META_DESCRIPTION,
        "twitter:image": image_url,
        "twitter:image:alt": SMOKE.META_IMAGE_ALT,
    }
    tags = []
    for name, content in meta.items():
        attribute = "property" if name.startswith("og:") else "name"
        tags.append(
            f'<meta {attribute}="{html.escape(name)}" content="{html.escape(content, quote=True)}">'
        )
    return (
        "<!doctype html><html><head>"
        f"<title>{html.escape(SMOKE.META_TITLE)}</title>"
        f'<link rel="canonical" href="{canonical}">'
        f"{''.join(tags)}</head><body>Date Planner</body></html>"
    )


def production_responses() -> tuple[list[FakeResponse], dict[str, object]]:
    plans = [
        {
            "id": PLAN_IDS[0],
            "starts_at": "2026-08-29T06:00:00Z",
            "time_zone": "UTC",
            "place": "Smoke Garden",
            "comment": "Synthetic first option",
            "position": 0,
        },
        {
            "id": PLAN_IDS[1],
            "starts_at": "2026-08-30T06:00:00Z",
            "time_zone": "UTC",
            "place": "Smoke Gallery",
            "comment": "Synthetic selected option",
            "position": 1,
        },
    ]
    activities = [
        {
            "id": ACTIVITY_IDS[0],
            "title": "Synthetic coffee",
            "description": "Production smoke activity one",
            "image_key": "activity-coffee",
            "place": "Smoke Cafe",
            "position": 0,
        },
        {
            "id": ACTIVITY_IDS[1],
            "title": "Synthetic movie",
            "description": "Production smoke activity two",
            "image_key": "activity-movie",
            "place": "Smoke Cinema",
            "position": 1,
        },
        {
            "id": ACTIVITY_IDS[2],
            "title": "Synthetic walk",
            "description": "Production smoke activity three",
            "image_key": "activity-selection-default",
            "place": "Smoke Park",
            "position": 2,
        },
    ]
    snapshot = {
        "option_id": PLAN_IDS[1],
        "activity_option_id": ACTIVITY_IDS[2],
        "starts_at": plans[1]["starts_at"],
        "time_zone": "UTC",
        "place": plans[1]["place"],
        "comment": plans[1]["comment"],
        "activity_title": activities[2]["title"],
        "activity_description": activities[2]["description"],
        "activity_place": activities[2]["place"],
        "activity_image_key": activities[2]["image_key"],
        "final_title": "Договорились 💞",
        "final_subtitle": "Осталось дождаться итогового подтверждения плана.",
        "final_image_key": "final-default",
        "final_text": (
            "Production Smoke Author and Production Smoke Recipient: "
            "Synthetic walk at Smoke Gallery"
        ),
        "confirmed_at": CONFIRMED_AT,
    }
    selected_invitation = invitation(
        message="Synthetic production smoke draft",
        planning_mode="before_acceptance",
        publication_status="published",
        response_status="accepted",
        plan_options=plans,
        activity_options=activities,
        selected_option_id=PLAN_IDS[1],
        selected_activity_option_id=ACTIVITY_IDS[2],
    )
    final_invitation = {
        **selected_invitation,
        "confirmed_at": CONFIRMED_AT,
        "confirmed_plan": snapshot,
    }
    mutated_invitation = {
        **final_invitation,
        "author_name": "Production Smoke Author Updated",
        "recipient_name": "Production Smoke Recipient Updated",
        "message": "Synthetic production smoke source changed after confirmation",
    }

    png_header = (
        b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 1200, 630)
    )
    responses = [
        html_response("<!doctype html><title>Date Planner</title>"),
        json_response({"status": "ok", "service": "date-planner-backend"}),
        FakeResponse(
            png_header,
            headers={**COMMON_HEADERS, "Content-Type": "image/png"},
        ),
        json_response(
            {
                **invitation(),
                "management_token": MANAGEMENT_TOKEN,
            },
            status=201,
        ),
        json_response(
            invitation(
                message="Synthetic production smoke draft",
                planning_mode="before_acceptance",
            )
        ),
        json_response(
            invitation(
                message="Synthetic production smoke draft",
                planning_mode="before_acceptance",
                plan_options=plans,
            )
        ),
        json_response({"options": activities}),
        json_response(
            invitation(
                message="Synthetic production smoke draft",
                planning_mode="before_acceptance",
                publication_status="published",
                plan_options=plans,
                activity_options=activities,
            )
        ),
        json_response(
            invitation(
                message="Synthetic production smoke draft",
                planning_mode="before_acceptance",
                publication_status="published",
            )
        ),
        json_response(
            invitation(
                message="Synthetic production smoke draft",
                planning_mode="before_acceptance",
                publication_status="published",
                response_status="accepted",
                plan_options=plans,
                activity_options=activities,
            )
        ),
        json_response(
            invitation(
                message="Synthetic production smoke draft",
                planning_mode="before_acceptance",
                publication_status="published",
                response_status="accepted",
                plan_options=plans,
                activity_options=activities,
                selected_option_id=PLAN_IDS[1],
            )
        ),
        json_response(selected_invitation),
        json_response(selected_invitation),
        json_response(final_invitation),
        json_response(final_invitation),
        json_response(mutated_invitation),
        json_response(mutated_invitation),
        json_response(mutated_invitation),
        html_response(invitation_metadata_html(), personal=True),
        html_response("<!doctype html><title>Manage Date Planner</title>", personal=True),
    ]
    return responses, snapshot


def request_headers(request: Request) -> dict[str, str]:
    return {name.lower(): value for name, value in request.header_items()}


def test_smoke_runs_full_lifecycle_without_putting_capability_in_urls_or_bodies() -> None:
    responses, snapshot = production_responses()
    opener = FakeOpener(responses)

    SMOKE.run_smoke(
        app_origin=APP_ORIGIN,
        api_origin=API_ORIGIN,
        opener=opener,
        clock=lambda: datetime(2026, 7, 30, 6, 0, tzinfo=UTC),
    )

    assert opener.responses == []
    assert [
        (request.get_method(), urlsplit(request.full_url).path) for request in opener.requests
    ] == [
        ("GET", "/"),
        ("GET", "/api/v1/ready/"),
        ("GET", "/images/social/invitation-preview.png"),
        ("POST", "/api/v1/invitations/"),
        ("PATCH", f"/api/v1/invitations/{INVITATION_ID}/manage/"),
        ("PUT", f"/api/v1/invitations/{INVITATION_ID}/plan-options/"),
        ("PUT", f"/api/v1/invitations/{INVITATION_ID}/activity-options/"),
        ("PUT", f"/api/v1/invitations/{INVITATION_ID}/publish/"),
        ("GET", f"/api/v1/invitations/{INVITATION_ID}/"),
        ("PUT", f"/api/v1/invitations/{INVITATION_ID}/response/"),
        ("PUT", f"/api/v1/invitations/{INVITATION_ID}/selection/"),
        ("PUT", f"/api/v1/invitations/{INVITATION_ID}/activity-selection/"),
        ("GET", f"/api/v1/invitations/{INVITATION_ID}/manage/"),
        ("PUT", f"/api/v1/invitations/{INVITATION_ID}/confirmation/"),
        ("PUT", f"/api/v1/invitations/{INVITATION_ID}/confirmation/"),
        ("PATCH", f"/api/v1/invitations/{INVITATION_ID}/manage/"),
        ("GET", f"/api/v1/invitations/{INVITATION_ID}/"),
        ("GET", f"/api/v1/invitations/{INVITATION_ID}/manage/"),
        ("GET", f"/invite/{INVITATION_ID}"),
        ("GET", f"/manage/{INVITATION_ID}"),
    ]

    management_request_indexes = {4, 5, 6, 7, 12, 13, 14, 15, 17}
    for index, request in enumerate(opener.requests):
        authorization = request_headers(request).get("authorization")
        if index in management_request_indexes:
            assert authorization == f"Bearer {MANAGEMENT_TOKEN}"
        else:
            assert authorization is None
        assert MANAGEMENT_TOKEN not in request.full_url
        assert "?" not in request.full_url
        assert "#" not in request.full_url
        assert MANAGEMENT_TOKEN.encode() not in (request.data or b"")

    confirmation_bodies = [json.loads(opener.requests[index].data) for index in (13, 14)]
    assert confirmation_bodies == [
        {
            "confirmed": True,
            "option_id": snapshot["option_id"],
            "activity_option_id": snapshot["activity_option_id"],
        },
        {
            "confirmed": True,
            "option_id": snapshot["option_id"],
            "activity_option_id": snapshot["activity_option_id"],
        },
    ]


@pytest.mark.parametrize(
    "arguments",
    [
        [
            "--app-origin",
            "http://dates.example.test",
            "--api-origin",
            API_ORIGIN,
            "--allow-write",
        ],
        [
            "--app-origin",
            APP_ORIGIN,
            "--api-origin",
            f"{API_ORIGIN}/api/v1?secret=value",
            "--allow-write",
        ],
        [
            "--app-origin",
            APP_ORIGIN,
            "--api-origin",
            API_ORIGIN,
        ],
    ],
)
def test_cli_requires_bare_https_origins_and_explicit_write_acknowledgement(
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        SMOKE.main(arguments)

    assert error.value.code == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "secret=value" not in output.err
    assert "http://dates.example.test" not in output.err


def test_cli_never_echoes_an_unknown_management_token(
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret = "must-not-appear-in-argparse-output"

    with pytest.raises(SystemExit) as error:
        SMOKE.main(
            [
                "--app-origin",
                APP_ORIGIN,
                "--api-origin",
                API_ORIGIN,
                "--allow-write",
                "--management-token",
                secret,
            ]
        )

    assert error.value.code == 2
    output = capsys.readouterr()
    assert secret not in output.err
    assert "management-token" not in output.err


def test_cli_failure_output_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    remote_details = (
        f"{MANAGEMENT_TOKEN} {API_ORIGIN}/api/v1/invitations/{INVITATION_ID}/ "
        '{"recipient_name":"Private Person"}'
    )

    def fail_smoke(**kwargs: object) -> None:
        del kwargs
        raise RuntimeError(remote_details)

    monkeypatch.setattr(SMOKE, "run_smoke", fail_smoke)

    result = SMOKE.main(
        [
            "--app-origin",
            APP_ORIGIN,
            "--api-origin",
            API_ORIGIN,
            "--allow-write",
        ]
    )

    assert result == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "Production smoke failed during unexpected verification.\n"
    for sensitive in (MANAGEMENT_TOKEN, API_ORIGIN, INVITATION_ID, "Private Person"):
        assert sensitive not in output.err


def test_http_failures_are_replaced_with_a_fixed_stage() -> None:
    remote_url = f"{API_ORIGIN}/api/v1/invitations/{INVITATION_ID}/"
    opener = FakeOpener(
        [
            HTTPError(
                remote_url,
                500,
                f"token={MANAGEMENT_TOKEN}",
                {},
                None,
            )
        ]
    )
    client = SMOKE.SmokeHttpClient(
        app_origin=APP_ORIGIN,
        api_origin=API_ORIGIN,
        opener=opener,
    )

    with pytest.raises(SMOKE.SmokeFailure) as error:
        client.json(stage=SMOKE.Stage.CONFIRM, path="/api/v1/failing/")

    assert str(error.value) == "final confirmation"
    assert MANAGEMENT_TOKEN not in str(error.value)
    assert INVITATION_ID not in str(error.value)


def test_help_documents_the_persistent_synthetic_record_side_effect() -> None:
    parser = SMOKE.build_parser()
    SMOKE._configure_parser(parser)

    help_text = " ".join(parser.format_help().split())

    assert "one synthetic extended invitation" in help_text
    assert "leaves that confirmed record in the production database" in help_text
    assert "--allow-write" in help_text
    assert "--management-token" not in help_text

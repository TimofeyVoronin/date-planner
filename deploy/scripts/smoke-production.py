#!/usr/bin/env python3
"""Run the destructive, post-deployment Date Planner production smoke test."""

from __future__ import annotations

import argparse
import json
import struct
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from html.parser import HTMLParser
from typing import BinaryIO
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    OpenerDirector,
    Request,
    build_opener,
)
from uuid import UUID

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 20

META_TITLE = "Тебе пришло личное приглашение — Date Planner"
META_DESCRIPTION = "Открой персональное приглашение и выбери удобный вариант встречи."
META_IMAGE_ALT = "Конверт с сердцем и подпись Date Planner"
META_IMAGE_PATH = "/images/social/invitation-preview.png"
EXPECTED_SCREEN_TYPES = (
    "invitation",
    "acceptance",
    "date_selection",
    "activity_selection",
    "final",
)


class Stage(Enum):
    """Fixed public stage names; exceptions and remote data never become diagnostics."""

    CONFIGURATION = "configuration validation"
    APP_PAGE = "application page"
    API_READINESS = "API readiness check"
    SOCIAL_IMAGE = "social preview image"
    CREATE = "invitation creation"
    MANAGEMENT_EDIT = "draft management edit"
    PLAN_OPTIONS = "date option preparation"
    ACTIVITY_OPTIONS = "activity preparation"
    PUBLISH = "invitation publication"
    PUBLIC_BEFORE_ACCEPTANCE = "pre-acceptance visibility check"
    ACCEPT = "recipient acceptance"
    DATE_SELECTION = "recipient date selection"
    ACTIVITY_SELECTION = "recipient activity selection"
    MANAGEMENT_SNAPSHOT = "management snapshot refresh"
    CONFIRM = "final confirmation"
    CONFIRM_RETRY = "confirmation retry"
    SOURCE_MUTATION = "post-confirmation source edit"
    PUBLIC_FINAL = "public final snapshot"
    MANAGEMENT_FINAL = "management final snapshot"
    INVITATION_PAGE = "invitation page metadata"
    MANAGEMENT_PAGE = "management page"
    UNEXPECTED = "unexpected verification"


class SmokeFailure(Exception):
    """A deliberately sanitized smoke-test failure."""

    def __init__(self, stage: Stage) -> None:
        self.stage = stage
        super().__init__(stage.value)


class SafeArgumentParser(argparse.ArgumentParser):
    """Prevent argparse from echoing an unknown argument or secret value."""

    def error(self, message: str) -> None:
        del message
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: invalid arguments\n")


class RejectRedirectHandler(HTTPRedirectHandler):
    """Reject redirects so an Authorization header can never cross origins."""

    def redirect_request(
        self,
        req: Request,
        fp: BinaryIO,
        code: int,
        msg: str,
        headers: Mapping[str, str],
        newurl: str,
    ) -> None:
        del req, fp, code, msg, headers, newurl
        return None


@dataclass(frozen=True)
class HttpResponse:
    """A bounded HTTP response with normalized header names."""

    body: bytes
    headers: Mapping[str, str]


class SmokeHttpClient:
    """Small no-redirect HTTP client that only raises sanitized failures."""

    def __init__(
        self,
        *,
        app_origin: str,
        api_origin: str,
        opener: OpenerDirector,
    ) -> None:
        self.app_origin = app_origin
        self.api_origin = api_origin
        self.opener = opener

    def request(
        self,
        *,
        stage: Stage,
        origin: str,
        path: str,
        method: str = "GET",
        payload: Mapping[str, object] | None = None,
        management_token: str | None = None,
        expected_status: int = 200,
    ) -> HttpResponse:
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": "date-planner-production-smoke/1",
        }
        data = None
        if payload is not None:
            data = json.dumps(
                payload, ensure_ascii=False, separators=(",", ":")
            ).encode()
            headers["Content-Type"] = "application/json"
        if management_token is not None:
            headers["Authorization"] = f"Bearer {management_token}"

        request = Request(
            f"{origin}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            response = self.opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS)
            try:
                status = getattr(response, "status", None)
                if status is None:
                    status = response.getcode()
                body = response.read(MAX_RESPONSE_BYTES + 1)
                response_headers = {
                    name.lower(): value for name, value in response.headers.items()
                }
            finally:
                response.close()
        except (HTTPError, URLError, OSError, TimeoutError, ValueError):
            raise SmokeFailure(stage) from None

        _require(status == expected_status, stage)
        _require(len(body) <= MAX_RESPONSE_BYTES, stage)
        result = HttpResponse(body=body, headers=response_headers)
        _assert_common_security_headers(result.headers, stage)
        return result

    def json(
        self,
        *,
        stage: Stage,
        path: str,
        method: str = "GET",
        payload: Mapping[str, object] | None = None,
        management_token: str | None = None,
        expected_status: int = 200,
        no_store: bool = True,
    ) -> dict[str, object]:
        response = self.request(
            stage=stage,
            origin=self.api_origin,
            path=path,
            method=method,
            payload=payload,
            management_token=management_token,
            expected_status=expected_status,
        )
        _require(
            response.headers.get("content-type", "")
            .lower()
            .startswith("application/json"),
            stage,
        )
        if no_store:
            _assert_private_no_store(response.headers, stage)
        try:
            decoded = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise SmokeFailure(stage) from None
        _require(isinstance(decoded, dict), stage)
        return decoded

    def app(
        self,
        *,
        stage: Stage,
        path: str,
        personal: bool = False,
    ) -> HttpResponse:
        response = self.request(
            stage=stage,
            origin=self.app_origin,
            path=path,
        )
        if personal:
            _assert_private_no_store(response.headers, stage)
            _require(
                response.headers.get("referrer-policy", "").lower() == "no-referrer",
                stage,
            )
            robots = _header_directives(response.headers, "x-robots-tag")
            _require({"noindex", "nofollow"} <= robots, stage)
        return response


class MetadataParser(HTMLParser):
    """Collect the small metadata surface checked by the production smoke."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.canonical_links: list[str] = []
        self.meta: dict[str, list[str]] = {}
        self.title_parts: list[str] = []
        self._inside_title = False

    @property
    def title(self) -> str:
        return "".join(self.title_parts).strip()

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = {name.lower(): value or "" for name, value in attrs}
        normalized_tag = tag.lower()
        if normalized_tag == "title":
            self._inside_title = True
            return
        if normalized_tag == "meta":
            key = attributes.get("property") or attributes.get("name")
            if key:
                self.meta.setdefault(key.lower(), []).append(
                    attributes.get("content", "")
                )
            return
        if normalized_tag == "link":
            relations = {item.lower() for item in attributes.get("rel", "").split()}
            if "canonical" in relations:
                self.canonical_links.append(attributes.get("href", ""))

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._inside_title = False

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            self.title_parts.append(data)


def _require(condition: bool, stage: Stage) -> None:
    if not condition:
        raise SmokeFailure(stage)


def _header_directives(headers: Mapping[str, str], name: str) -> set[str]:
    return {
        directive.strip().lower()
        for directive in headers.get(name, "").split(",")
        if directive.strip()
    }


def _assert_common_security_headers(headers: Mapping[str, str], stage: Stage) -> None:
    _require(bool(headers.get("strict-transport-security", "").strip()), stage)
    _require(headers.get("x-content-type-options", "").lower() == "nosniff", stage)
    _require(headers.get("x-frame-options", "").upper() == "DENY", stage)
    _require(bool(headers.get("permissions-policy", "").strip()), stage)


def _assert_private_no_store(headers: Mapping[str, str], stage: Stage) -> None:
    directives = _header_directives(headers, "cache-control")
    _require({"private", "no-store"} <= directives, stage)


def _parse_https_origin(value: str) -> str:
    try:
        parsed = urlsplit(value)
        parsed_port = parsed.port
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "origin must be a valid HTTPS origin"
        ) from error

    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed_port is not None
        and not 1 <= parsed_port <= 65535
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise argparse.ArgumentTypeError("origin must be a bare HTTPS origin")
    return f"https://{parsed.netloc}"


def build_parser() -> argparse.ArgumentParser:
    """Build a parser whose help makes the production write explicit."""

    return SafeArgumentParser(
        description=(
            "Verify a deployed Date Planner instance through its public HTTPS endpoints. "
            "This writes exactly one synthetic extended invitation, confirms it, and leaves "
            "that confirmed record in the production database; no cleanup is attempted."
        ),
        epilog=(
            "No management token is accepted on the command line. The script obtains the "
            "one-time capability from its own synthetic invitation creation response."
        ),
    )


def _configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--app-origin",
        required=True,
        type=_parse_https_origin,
        help="Public HTTPS app origin, for example https://dates.example.com.",
    )
    parser.add_argument(
        "--api-origin",
        required=True,
        type=_parse_https_origin,
        help="Public HTTPS API origin, for example https://api.dates.example.com.",
    )
    parser.add_argument(
        "--allow-write",
        action="store_true",
        help=(
            "Acknowledge creation of one persistent synthetic invitation and its related "
            "options, selections, and immutable final snapshot."
        ),
    )


def _uuid_string(value: object, stage: Stage) -> str:
    _require(isinstance(value, str), stage)
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        raise SmokeFailure(stage) from None
    _require(str(parsed) == value.lower(), stage)
    return value


def _string(value: object, stage: Stage, *, allow_blank: bool = False) -> str:
    _require(isinstance(value, str), stage)
    if not allow_blank:
        _require(bool(value.strip()), stage)
    return value


def _list(value: object, stage: Stage) -> list[object]:
    _require(isinstance(value, list), stage)
    return value


def _mapping(value: object, stage: Stage) -> dict[str, object]:
    _require(isinstance(value, dict), stage)
    _require(all(isinstance(key, str) for key in value), stage)
    return value


def _contains_forbidden_capability_key(value: object) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in {"management_token", "management_token_hash"}:
                return True
            if _contains_forbidden_capability_key(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_capability_key(item) for item in value)
    return False


def _assert_capability_absent(
    value: object,
    management_token: str,
    stage: Stage,
) -> None:
    _require(not _contains_forbidden_capability_key(value), stage)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
    _require(management_token not in encoded, stage)


def _assert_extended_invitation(
    invitation: Mapping[str, object],
    stage: Stage,
) -> None:
    _uuid_string(invitation.get("id"), stage)
    _require(invitation.get("creation_mode") == "extended", stage)
    screens = _list(invitation.get("screens"), stage)
    screen_types = [_mapping(screen, stage).get("screen_type") for screen in screens]
    _require(tuple(screen_types) == EXPECTED_SCREEN_TYPES, stage)


def _assert_positions(options: Sequence[object], stage: Stage) -> None:
    positions = [_mapping(option, stage).get("position") for option in options]
    _require(positions == list(range(len(options))), stage)


def _assert_option_ids(options: Sequence[object], stage: Stage) -> list[str]:
    ids = [_uuid_string(_mapping(option, stage).get("id"), stage) for option in options]
    _require(len(ids) == len(set(ids)), stage)
    return ids


def _assert_confirmed_snapshot(
    invitation: Mapping[str, object],
    *,
    expected_plan: Mapping[str, object],
    expected_activity: Mapping[str, object],
    expected_snapshot: Mapping[str, object] | None,
    stage: Stage,
) -> dict[str, object]:
    snapshot = _mapping(invitation.get("confirmed_plan"), stage)
    _require(snapshot.get("option_id") == expected_plan.get("id"), stage)
    _require(snapshot.get("activity_option_id") == expected_activity.get("id"), stage)
    _require(snapshot.get("starts_at") == expected_plan.get("starts_at"), stage)
    _require(snapshot.get("time_zone") == expected_plan.get("time_zone"), stage)
    _require(snapshot.get("place") == expected_plan.get("place"), stage)
    _require(snapshot.get("comment") == expected_plan.get("comment"), stage)
    _require(snapshot.get("activity_title") == expected_activity.get("title"), stage)
    _require(
        snapshot.get("activity_description") == expected_activity.get("description"),
        stage,
    )
    _require(snapshot.get("activity_place") == expected_activity.get("place"), stage)
    _require(
        snapshot.get("activity_image_key") == expected_activity.get("image_key"),
        stage,
    )
    for field in (
        "final_title",
        "final_subtitle",
        "final_image_key",
        "final_text",
        "confirmed_at",
    ):
        _string(snapshot.get(field), stage)
    _require(invitation.get("confirmed_at") == snapshot.get("confirmed_at"), stage)
    if expected_snapshot is not None:
        _require(snapshot == expected_snapshot, stage)
    return snapshot


def _assert_png(response: HttpResponse, stage: Stage) -> None:
    _require(
        response.headers.get("content-type", "").lower().startswith("image/png"),
        stage,
    )
    _require(response.body.startswith(b"\x89PNG\r\n\x1a\n"), stage)
    _require(len(response.body) >= 24 and response.body[12:16] == b"IHDR", stage)
    try:
        width, height = struct.unpack(">II", response.body[16:24])
    except struct.error:
        raise SmokeFailure(stage) from None
    _require((width, height) == (1200, 630), stage)


def _assert_invitation_metadata(
    response: HttpResponse,
    *,
    app_origin: str,
    invitation_id: str,
    sensitive_values: Sequence[str],
    stage: Stage,
) -> None:
    _require(
        response.headers.get("content-type", "").lower().startswith("text/html"),
        stage,
    )
    try:
        html = response.body.decode("utf-8")
    except UnicodeDecodeError:
        raise SmokeFailure(stage) from None

    parser = MetadataParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        raise SmokeFailure(stage) from None

    canonical = f"{app_origin}/invite/{quote(invitation_id, safe='')}"
    image_url = f"{app_origin}{META_IMAGE_PATH}"
    expected_meta = {
        "description": META_DESCRIPTION,
        "robots": "noindex, nofollow",
        "referrer": "no-referrer",
        "og:title": META_TITLE,
        "og:description": META_DESCRIPTION,
        "og:type": "website",
        "og:site_name": "Date Planner",
        "og:locale": "ru_RU",
        "og:url": canonical,
        "og:image": image_url,
        "og:image:alt": META_IMAGE_ALT,
        "og:image:width": "1200",
        "og:image:height": "630",
        "twitter:card": "summary_large_image",
        "twitter:title": META_TITLE,
        "twitter:description": META_DESCRIPTION,
        "twitter:image": image_url,
        "twitter:image:alt": META_IMAGE_ALT,
    }
    _require(parser.title == META_TITLE, stage)
    _require(parser.canonical_links == [canonical], stage)
    for key, expected_value in expected_meta.items():
        _require(parser.meta.get(key) == [expected_value], stage)

    metadata_text = "\n".join(
        (
            parser.title,
            *parser.canonical_links,
            *(content for values in parser.meta.values() for content in values),
        )
    ).casefold()
    for sensitive in sensitive_values:
        if sensitive:
            _require(sensitive.casefold() not in metadata_text, stage)
    for unsafe_fragment in (
        "/manage/",
        "management_token",
        "bearer ",
        "token=",
        "?",
        "#",
    ):
        _require(unsafe_fragment not in metadata_text, stage)


def _future_iso_values(clock: Callable[[], datetime]) -> tuple[str, str]:
    now = clock()
    if now.tzinfo is None or now.utcoffset() is None:
        raise SmokeFailure(Stage.CONFIGURATION)
    base = now.astimezone(UTC).replace(microsecond=0)
    return tuple(
        (base + timedelta(days=days)).isoformat().replace("+00:00", "Z")
        for days in (30, 31)
    )


def run_smoke(
    *,
    app_origin: str,
    api_origin: str,
    opener: OpenerDirector | None = None,
    clock: Callable[[], datetime] | None = None,
) -> None:
    """Exercise the full extended-invitation lifecycle through production HTTP."""

    client = SmokeHttpClient(
        app_origin=app_origin,
        api_origin=api_origin,
        opener=opener or build_opener(RejectRedirectHandler()),
    )
    clock = clock or (lambda: datetime.now(UTC))

    app_page = client.app(stage=Stage.APP_PAGE, path="/")
    _require(
        app_page.headers.get("content-type", "").lower().startswith("text/html"),
        Stage.APP_PAGE,
    )

    readiness = client.json(
        stage=Stage.API_READINESS,
        path="/api/v1/ready/",
        no_store=False,
    )
    _require(
        readiness == {"status": "ok", "service": "date-planner-backend"},
        Stage.API_READINESS,
    )

    social_image = client.app(stage=Stage.SOCIAL_IMAGE, path=META_IMAGE_PATH)
    _assert_png(social_image, Stage.SOCIAL_IMAGE)

    original_author = "Production Smoke Author"
    original_recipient = "Production Smoke Recipient"
    original_message = "Synthetic production smoke invitation"
    edited_message = "Synthetic production smoke draft"
    changed_author = "Production Smoke Author Updated"
    changed_recipient = "Production Smoke Recipient Updated"
    changed_message = "Synthetic production smoke source changed after confirmation"
    plan_payloads = (
        {
            "starts_at": starts_at,
            "time_zone": "UTC",
            "place": place,
            "comment": comment,
        }
        for starts_at, place, comment in zip(
            _future_iso_values(clock),
            ("Smoke Garden", "Smoke Gallery"),
            ("Synthetic first option", "Synthetic selected option"),
            strict=True,
        )
    )
    plan_options_payload = list(plan_payloads)
    activity_options_payload = [
        {
            "title": "Synthetic coffee",
            "description": "Production smoke activity one",
            "image_key": "activity-coffee",
            "place": "Smoke Cafe",
        },
        {
            "title": "Synthetic movie",
            "description": "Production smoke activity two",
            "image_key": "activity-movie",
            "place": "Smoke Cinema",
        },
        {
            "title": "Synthetic walk",
            "description": "Production smoke activity three",
            "image_key": "activity-selection-default",
            "place": "Smoke Park",
        },
    ]

    created = client.json(
        stage=Stage.CREATE,
        path="/api/v1/invitations/",
        method="POST",
        payload={
            "author_name": original_author,
            "recipient_name": original_recipient,
            "message": original_message,
            "creation_mode": "extended",
        },
        expected_status=201,
    )
    _assert_extended_invitation(created, Stage.CREATE)
    _require(created.get("publication_status") == "draft", Stage.CREATE)
    _require(created.get("planning_mode") == "after_acceptance", Stage.CREATE)
    invitation_id = _uuid_string(created.get("id"), Stage.CREATE)
    management_token = _string(created.get("management_token"), Stage.CREATE)

    invitation_path = f"/api/v1/invitations/{invitation_id}/"
    management_path = f"{invitation_path}manage/"
    managed = client.json(
        stage=Stage.MANAGEMENT_EDIT,
        path=management_path,
        method="PATCH",
        payload={
            "message": edited_message,
            "planning_mode": "before_acceptance",
        },
        management_token=management_token,
    )
    _assert_capability_absent(managed, management_token, Stage.MANAGEMENT_EDIT)
    _assert_extended_invitation(managed, Stage.MANAGEMENT_EDIT)
    _require(managed.get("message") == edited_message, Stage.MANAGEMENT_EDIT)
    _require(managed.get("planning_mode") == "before_acceptance", Stage.MANAGEMENT_EDIT)

    planned = client.json(
        stage=Stage.PLAN_OPTIONS,
        path=f"{invitation_path}plan-options/",
        method="PUT",
        payload={"options": plan_options_payload},
        management_token=management_token,
    )
    _assert_capability_absent(planned, management_token, Stage.PLAN_OPTIONS)
    persisted_plans = _list(planned.get("plan_options"), Stage.PLAN_OPTIONS)
    _require(len(persisted_plans) == 2, Stage.PLAN_OPTIONS)
    _assert_positions(persisted_plans, Stage.PLAN_OPTIONS)
    plan_ids = _assert_option_ids(persisted_plans, Stage.PLAN_OPTIONS)

    activities = client.json(
        stage=Stage.ACTIVITY_OPTIONS,
        path=f"{invitation_path}activity-options/",
        method="PUT",
        payload={"options": activity_options_payload},
        management_token=management_token,
    )
    _assert_capability_absent(activities, management_token, Stage.ACTIVITY_OPTIONS)
    persisted_activities = _list(activities.get("options"), Stage.ACTIVITY_OPTIONS)
    _require(len(persisted_activities) == 3, Stage.ACTIVITY_OPTIONS)
    _assert_positions(persisted_activities, Stage.ACTIVITY_OPTIONS)
    activity_ids = _assert_option_ids(persisted_activities, Stage.ACTIVITY_OPTIONS)

    published = client.json(
        stage=Stage.PUBLISH,
        path=f"{invitation_path}publish/",
        method="PUT",
        payload={},
        management_token=management_token,
    )
    _assert_capability_absent(published, management_token, Stage.PUBLISH)
    _require(published.get("publication_status") == "published", Stage.PUBLISH)
    _string(published.get("published_at"), Stage.PUBLISH)

    before_acceptance = client.json(
        stage=Stage.PUBLIC_BEFORE_ACCEPTANCE,
        path=invitation_path,
    )
    _assert_capability_absent(
        before_acceptance,
        management_token,
        Stage.PUBLIC_BEFORE_ACCEPTANCE,
    )
    _require(
        before_acceptance.get("response_status") == "pending",
        Stage.PUBLIC_BEFORE_ACCEPTANCE,
    )
    _require(
        before_acceptance.get("plan_options") == [], Stage.PUBLIC_BEFORE_ACCEPTANCE
    )
    _require(
        before_acceptance.get("activity_options") == [], Stage.PUBLIC_BEFORE_ACCEPTANCE
    )

    accepted = client.json(
        stage=Stage.ACCEPT,
        path=f"{invitation_path}response/",
        method="PUT",
        payload={"response_status": "accepted"},
    )
    _assert_capability_absent(accepted, management_token, Stage.ACCEPT)
    _require(accepted.get("response_status") == "accepted", Stage.ACCEPT)
    accepted_plans = _list(accepted.get("plan_options"), Stage.ACCEPT)
    accepted_activities = _list(accepted.get("activity_options"), Stage.ACCEPT)
    _require(_assert_option_ids(accepted_plans, Stage.ACCEPT) == plan_ids, Stage.ACCEPT)
    _require(
        _assert_option_ids(accepted_activities, Stage.ACCEPT) == activity_ids,
        Stage.ACCEPT,
    )

    selected_plan_id = plan_ids[1]
    selected_activity_id = activity_ids[2]
    selected = client.json(
        stage=Stage.DATE_SELECTION,
        path=f"{invitation_path}selection/",
        method="PUT",
        payload={"option_id": selected_plan_id},
    )
    _assert_capability_absent(selected, management_token, Stage.DATE_SELECTION)
    _require(
        selected.get("selected_option_id") == selected_plan_id, Stage.DATE_SELECTION
    )
    _string(selected.get("selected_at"), Stage.DATE_SELECTION)

    activity_selected = client.json(
        stage=Stage.ACTIVITY_SELECTION,
        path=f"{invitation_path}activity-selection/",
        method="PUT",
        payload={"option_id": selected_activity_id},
    )
    _assert_capability_absent(
        activity_selected,
        management_token,
        Stage.ACTIVITY_SELECTION,
    )
    _require(
        activity_selected.get("selected_activity_option_id") == selected_activity_id,
        Stage.ACTIVITY_SELECTION,
    )
    _string(activity_selected.get("activity_selected_at"), Stage.ACTIVITY_SELECTION)

    latest_management = client.json(
        stage=Stage.MANAGEMENT_SNAPSHOT,
        path=management_path,
        management_token=management_token,
    )
    _assert_capability_absent(
        latest_management,
        management_token,
        Stage.MANAGEMENT_SNAPSHOT,
    )
    expected_plan_id = _uuid_string(
        latest_management.get("selected_option_id"),
        Stage.MANAGEMENT_SNAPSHOT,
    )
    expected_activity_id = _uuid_string(
        latest_management.get("selected_activity_option_id"),
        Stage.MANAGEMENT_SNAPSHOT,
    )
    _require(expected_plan_id == selected_plan_id, Stage.MANAGEMENT_SNAPSHOT)
    _require(expected_activity_id == selected_activity_id, Stage.MANAGEMENT_SNAPSHOT)

    management_plans = _list(
        latest_management.get("plan_options"),
        Stage.MANAGEMENT_SNAPSHOT,
    )
    management_activities = _list(
        latest_management.get("activity_options"),
        Stage.MANAGEMENT_SNAPSHOT,
    )
    expected_plan = next(
        (
            _mapping(option, Stage.MANAGEMENT_SNAPSHOT)
            for option in management_plans
            if _mapping(option, Stage.MANAGEMENT_SNAPSHOT).get("id") == expected_plan_id
        ),
        None,
    )
    expected_activity = next(
        (
            _mapping(option, Stage.MANAGEMENT_SNAPSHOT)
            for option in management_activities
            if _mapping(option, Stage.MANAGEMENT_SNAPSHOT).get("id")
            == expected_activity_id
        ),
        None,
    )
    _require(expected_plan is not None, Stage.MANAGEMENT_SNAPSHOT)
    _require(expected_activity is not None, Stage.MANAGEMENT_SNAPSHOT)

    confirmation_payload = {
        "confirmed": True,
        "option_id": expected_plan_id,
        "activity_option_id": expected_activity_id,
    }
    confirmed = client.json(
        stage=Stage.CONFIRM,
        path=f"{invitation_path}confirmation/",
        method="PUT",
        payload=confirmation_payload,
        management_token=management_token,
    )
    _assert_capability_absent(confirmed, management_token, Stage.CONFIRM)
    snapshot = _assert_confirmed_snapshot(
        confirmed,
        expected_plan=expected_plan,
        expected_activity=expected_activity,
        expected_snapshot=None,
        stage=Stage.CONFIRM,
    )

    confirmation_retry = client.json(
        stage=Stage.CONFIRM_RETRY,
        path=f"{invitation_path}confirmation/",
        method="PUT",
        payload=confirmation_payload,
        management_token=management_token,
    )
    _assert_capability_absent(
        confirmation_retry,
        management_token,
        Stage.CONFIRM_RETRY,
    )
    _assert_confirmed_snapshot(
        confirmation_retry,
        expected_plan=expected_plan,
        expected_activity=expected_activity,
        expected_snapshot=snapshot,
        stage=Stage.CONFIRM_RETRY,
    )

    mutated = client.json(
        stage=Stage.SOURCE_MUTATION,
        path=management_path,
        method="PATCH",
        payload={
            "author_name": changed_author,
            "recipient_name": changed_recipient,
            "message": changed_message,
        },
        management_token=management_token,
    )
    _assert_capability_absent(mutated, management_token, Stage.SOURCE_MUTATION)
    _require(mutated.get("author_name") == changed_author, Stage.SOURCE_MUTATION)
    _require(mutated.get("recipient_name") == changed_recipient, Stage.SOURCE_MUTATION)
    _assert_confirmed_snapshot(
        mutated,
        expected_plan=expected_plan,
        expected_activity=expected_activity,
        expected_snapshot=snapshot,
        stage=Stage.SOURCE_MUTATION,
    )

    public_final = client.json(stage=Stage.PUBLIC_FINAL, path=invitation_path)
    _assert_capability_absent(public_final, management_token, Stage.PUBLIC_FINAL)
    _assert_confirmed_snapshot(
        public_final,
        expected_plan=expected_plan,
        expected_activity=expected_activity,
        expected_snapshot=snapshot,
        stage=Stage.PUBLIC_FINAL,
    )

    management_final = client.json(
        stage=Stage.MANAGEMENT_FINAL,
        path=management_path,
        management_token=management_token,
    )
    _assert_capability_absent(
        management_final,
        management_token,
        Stage.MANAGEMENT_FINAL,
    )
    _assert_confirmed_snapshot(
        management_final,
        expected_plan=expected_plan,
        expected_activity=expected_activity,
        expected_snapshot=snapshot,
        stage=Stage.MANAGEMENT_FINAL,
    )

    sensitive_values = (
        management_token,
        original_author,
        original_recipient,
        original_message,
        edited_message,
        changed_author,
        changed_recipient,
        changed_message,
        *(
            _string(item.get(field), Stage.INVITATION_PAGE, allow_blank=True)
            for item in (*plan_options_payload, *activity_options_payload)
            for field in (
                ("place", "comment")
                if "starts_at" in item
                else ("title", "description", "place")
            )
        ),
        _string(snapshot.get("final_text"), Stage.INVITATION_PAGE),
    )
    invitation_page = client.app(
        stage=Stage.INVITATION_PAGE,
        path=f"/invite/{quote(invitation_id, safe='')}",
        personal=True,
    )
    _assert_invitation_metadata(
        invitation_page,
        app_origin=app_origin,
        invitation_id=invitation_id,
        sensitive_values=sensitive_values,
        stage=Stage.INVITATION_PAGE,
    )

    management_page = client.app(
        stage=Stage.MANAGEMENT_PAGE,
        path=f"/manage/{quote(invitation_id, safe='')}",
        personal=True,
    )
    _require(
        management_page.headers.get("content-type", "").lower().startswith("text/html"),
        Stage.MANAGEMENT_PAGE,
    )
    _require(
        management_token.encode() not in management_page.body, Stage.MANAGEMENT_PAGE
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Parse safe CLI input and emit only fixed, non-sensitive diagnostics."""

    parser = build_parser()
    _configure_parser(parser)
    args = parser.parse_args(argv)
    if not args.allow_write:
        parser.error("the explicit write acknowledgement is required")

    try:
        run_smoke(app_origin=args.app_origin, api_origin=args.api_origin)
    except SmokeFailure as error:
        print(f"Production smoke failed during {error.stage.value}.", file=sys.stderr)
        return 1
    except Exception:
        print(
            f"Production smoke failed during {Stage.UNEXPECTED.value}.",
            file=sys.stderr,
        )
        return 1

    print(
        "Production smoke passed. One synthetic confirmed invitation record was created."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

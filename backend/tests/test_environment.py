"""Tests for strict environment parsing."""

import pytest

from config.environment import env_bool, env_int, env_list


@pytest.mark.parametrize("value", ["1", "true", "YES", " on "])
def test_env_bool_accepts_explicit_true_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("FEATURE_FLAG", value)

    assert env_bool("FEATURE_FLAG", False) is True


@pytest.mark.parametrize("value", ["0", "false", "NO", " off "])
def test_env_bool_accepts_explicit_false_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("FEATURE_FLAG", value)

    assert env_bool("FEATURE_FLAG", True) is False


def test_env_bool_rejects_ambiguous_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEATURE_FLAG", "enabled")

    with pytest.raises(ValueError, match="FEATURE_FLAG must be a boolean value"):
        env_bool("FEATURE_FLAG", False)


def test_env_int_applies_minimum(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKER_COUNT", "0")

    with pytest.raises(ValueError, match="WORKER_COUNT must be greater than or equal to 1"):
        env_int("WORKER_COUNT", 2, minimum=1)


def test_env_list_strips_whitespace_and_empty_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOSTS", " api.example.com, ,www.example.com ")

    assert env_list("HOSTS") == ["api.example.com", "www.example.com"]

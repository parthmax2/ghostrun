"""The end-of-session mascot: state selection, opt-out, and TTY/encoding gating."""

import os

import pytest

from ghostrun import mascot


class FakeStream:
    def __init__(self, isatty=True, encoding="utf-8"):
        self._isatty = isatty
        self.encoding = encoding

    def isatty(self):
        return self._isatty


def test_silent_when_nothing_happened():
    assert mascot.render({"replayed": 0, "recorded": 0, "misses": 0}) == ""


def test_silent_on_non_tty():
    stats = {"replayed": 1, "recorded": 0, "misses": 0}
    block = mascot.render(stats, stream=FakeStream(isatty=False))
    assert block != ""
    assert "\x1b[" not in block  # no ANSI color when not a real terminal


def test_opt_out_env_var(monkeypatch):
    monkeypatch.setenv("GHOSTRUN_NO_MASCOT", "1")
    stats = {"replayed": 1, "recorded": 0, "misses": 0}
    assert mascot.render(stats, stream=FakeStream()) == ""


@pytest.mark.parametrize(
    "stats, expected_state",
    [
        ({"replayed": 1, "recorded": 0, "misses": 0}, "replayed"),
        ({"replayed": 0, "recorded": 1, "misses": 0}, "recorded"),
        ({"replayed": 3, "recorded": 2, "misses": 1}, "miss"),  # misses always win
        ({"replayed": 0, "recorded": 3, "misses": 1}, "miss"),
    ],
)
def test_state_selection(stats, expected_state, monkeypatch):
    monkeypatch.delenv("GHOSTRUN_NO_MASCOT", raising=False)
    block = mascot.render(stats, stream=FakeStream(isatty=False))
    face_line = mascot._FACES[expected_state][1]  # eyes line is state-distinctive
    assert face_line in block


def test_color_and_emoji_only_on_tty_utf8(monkeypatch):
    monkeypatch.delenv("GHOSTRUN_NO_MASCOT", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    stats = {"replayed": 1, "recorded": 0, "misses": 0}

    tty_utf8 = mascot.render(stats, stream=FakeStream(isatty=True, encoding="utf-8"))
    assert "\x1b[" in tty_utf8
    assert "\U0001f47b" in tty_utf8  # the ghost emoji

    tty_ascii = mascot.render(stats, stream=FakeStream(isatty=True, encoding="cp1252"))
    assert "\x1b[" in tty_ascii  # color still fine
    assert "\U0001f47b" not in tty_ascii  # emoji withheld -- codepage can't show it
    assert "·" not in tty_ascii  # falls back to plain "-" separator


def test_no_color_env_var_disables_ansi(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    stats = {"replayed": 1, "recorded": 0, "misses": 0}
    block = mascot.render(stats, stream=FakeStream(isatty=True))
    assert "\x1b[" not in block

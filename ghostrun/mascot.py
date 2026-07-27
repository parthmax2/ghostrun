"""The ghostrun terminal mascot: a one-line-per-session ASCII ghost that reacts
to what the interceptor actually did (replayed from cache, hit the network, or
missed in strict replay mode).

Deliberately shown at most once, at the end of a test session -- never per-line
-- so it reads as a signature, not noise. Silent by default whenever output
isn't an interactive TTY (CI logs, piped output) or nothing ghostrun-related
happened, and always silenceable via GHOSTRUN_NO_MASCOT.
"""

from __future__ import annotations

import os
import sys

RESET = "\x1b[0m"
DIM = "\x1b[2m"
BOLD = "\x1b[1m"

_COLOR = {
    "replayed": "\x1b[36m",  # cyan -- calm, nothing cost anything
    "recorded": "\x1b[33m",  # yellow -- the network was actually touched
    "miss": "\x1b[31m",      # red -- something's wrong
}

_EMOJI = {"replayed": "👻", "recorded": "🌐", "miss": "⚠️"}

_FACES = {
    "replayed": [
        "   .-''''-.",
        "  /  o  o  \\",
        " |    ..    |",
        "  \\  '--'  /",
        "   `------`",
    ],
    "recorded": [
        "   .-''''-.",
        "  /  O  O  \\",
        " |    o     |",
        "  \\  '--'  /",
        "   `------`",
    ],
    "miss": [
        "   .-''''-.",
        "  /  x  x  \\",
        " |   /\\    |",
        "  \\  '--'  /",
        "   `------`",
    ],
}


def _state(stats: dict) -> str:
    if stats.get("misses", 0) > 0:
        return "miss"
    if stats.get("recorded", 0) > 0:
        return "recorded"
    if stats.get("replayed", 0) > 0:
        return "replayed"
    return ""


def _supports_color(stream) -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def _supports_emoji(stream) -> bool:
    encoding = getattr(stream, "encoding", None) or ""
    return "UTF" in encoding.upper()


def _summary_line(stats: dict, state: str, emoji: bool, unicode_safe: bool) -> str:
    parts = [
        f"{stats.get('replayed', 0)} replayed",
        f"{stats.get('recorded', 0)} recorded",
    ]
    if stats.get("misses", 0):
        parts.append(f"{stats['misses']} missed")
    mark = f"{_EMOJI[state]} " if emoji else ""
    sep = "·" if unicode_safe else "-"
    return f"{mark}ghostrun  {sep}  " + ", ".join(parts)


def render(stats: dict, stream=None) -> str:
    """Render the mascot block for this session's stats, or "" to show nothing.

    Returns an empty string when nothing ghostrun-related happened (no
    replays, records, or misses) so a suite that never calls @ghostrun.record
    doesn't get an unexplained ghost printed at it.
    """
    stream = stream if stream is not None else sys.stdout
    state = _state(stats)
    if not state:
        return ""
    if os.environ.get("GHOSTRUN_NO_MASCOT"):
        return ""

    color = _supports_color(stream)
    emoji = color and _supports_emoji(stream)

    face = _FACES[state]
    summary = _summary_line(stats, state, emoji, unicode_safe=emoji)
    detail = {
        "replayed": "no network touched",
        "recorded": "the network was touched -- new cache written",
        "miss": "re-run with --ghostrun-record to fix",
    }[state]

    c = _COLOR[state] if color else ""
    r = RESET if color else ""
    dim = DIM if color else ""

    lines = []
    for i, art_line in enumerate(face):
        colored_art = f"{c}{art_line}{r}"
        if i == 0:
            lines.append(f"{colored_art}      {BOLD if color else ''}{summary}{r}")
        elif i == 1:
            lines.append(f"{colored_art}      {dim}{detail}{r}")
        else:
            lines.append(colored_art)
    return "\n" + "\n".join(lines) + "\n"

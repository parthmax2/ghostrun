"""The ghostrun terminal mascot: a one-line-per-session marker that reacts to
what the interceptor actually did (replayed from cache, hit the network, or
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
BOLD = "\x1b[1m"
DIM = "\x1b[2m"

_COLOR = {
    "replayed": "\x1b[36m",  # cyan -- calm, nothing cost anything
    "recorded": "\x1b[33m",  # yellow -- the network was actually touched
    "miss": "\x1b[31m",      # red -- something's wrong
}

# The real 👻 emoji is the mascot on any terminal that can render it -- it
# already looks better than anything drawn from punctuation. ASCII faces are
# only the fallback for terminals/codepages that can't show it.
_ASCII_FACE = {"replayed": "(o o)", "recorded": "(O O)", "miss": "(x x)"}

_DETAIL = {
    "replayed": "no network touched",
    "recorded": "the network was touched -- new cache written",
    "miss": "re-run with --ghostrun-record to fix",
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


def _supports_unicode(stream) -> bool:
    encoding = getattr(stream, "encoding", None) or ""
    return "UTF" in encoding.upper()


def render(stats: dict, stream=None) -> str:
    """Render the mascot line(s) for this session's stats, or "" for nothing.

    Returns an empty string when nothing ghostrun-related happened (no
    replays, records, or misses) so a suite that never calls @ghostrun.record
    doesn't get an unexplained mascot printed at it.
    """
    stream = stream if stream is not None else sys.stdout
    state = _state(stats)
    if not state:
        return ""
    if os.environ.get("GHOSTRUN_NO_MASCOT"):
        return ""

    color = _supports_color(stream)
    unicode_safe = color and _supports_unicode(stream)

    c = _COLOR[state] if color else ""
    r = RESET if color else ""
    bold = BOLD if color else ""
    dim = DIM if color else ""
    sep = "·" if unicode_safe else "-"

    if unicode_safe:
        icon = f"{c}☆{r} \U0001f47b {c}☆{r}"
        icon_width = 5  # visual columns: star, space, ghost(~2), space, star
    else:
        icon = f"{c}{_ASCII_FACE[state]}{r}"
        icon_width = len(_ASCII_FACE[state])

    parts = [f"{stats.get('replayed', 0)} replayed", f"{stats.get('recorded', 0)} recorded"]
    if stats.get("misses", 0):
        parts.append(f"{stats['misses']} missed")
    summary = f"{bold}ghostrun  {sep}  " + ", ".join(parts) + r
    detail = f"{dim}{_DETAIL[state]}{r}"

    pad = " " * icon_width
    return (
        f"\n{icon}   {summary}"
        f"\n{pad}   {detail}\n"
    )

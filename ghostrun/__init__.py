"""ghostrun: pytest for LLMs — deterministic record/replay and semantic assertions.

Local-first, privacy-first. No SaaS, no data leaves your machine by default.

    import ghostrun

    @ghostrun.record(model="gpt-4o-mini")
    def test_reply():
        reply = generate_reply("Where is my refund?")
        ghostrun.expect(reply).contains_intent("apology")
        ghostrun.expect(reply).tone_is("empathetic")
"""

from __future__ import annotations

from .assertions import (
    Expectation,
    SemanticAssertionError,
    ToolCallExpectation,
    expect,
    expect_tool_calls,
)
from .config import Config, get_config, load_config, reset_config, set_config
from .interceptor import CacheMiss, UnsupportedHttpx
from .record import record, recording

__version__ = "2.0.5"


def configure(**kwargs) -> Config:
    """Override configuration for the current process. Returns the new config.

    Example: ``ghostrun.configure(judge="echo")``.
    """
    cfg = get_config().with_overrides(**kwargs)
    set_config(cfg)
    return cfg


__all__ = [
    "record",
    "recording",
    "expect",
    "Expectation",
    "expect_tool_calls",
    "ToolCallExpectation",
    "configure",
    "Config",
    "get_config",
    "load_config",
    "set_config",
    "reset_config",
    "CacheMiss",
    "UnsupportedHttpx",
    "SemanticAssertionError",
    "__version__",
]

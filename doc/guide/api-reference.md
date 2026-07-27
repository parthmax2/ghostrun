# API reference

The complete public surface of `gentest` — everything in `gentest.__all__`.
Anything not listed here is a private implementation detail and may change
without notice.

## Recording

### `gentest.record(func=None, *, model=None, mode=None, cache_dir=None)`

Decorator. Intercepts LLM HTTP calls made inside the decorated test and
records/replays them. Works on sync and async test functions.

```python
@gentest.record(model="gpt-4o-mini")
def test_reply():
    ...
```

Usable bare (`@gentest.record`) or parameterized. `model` is accepted for
documentation purposes and does not change interception behavior — it's not
sent anywhere. `mode` and `cache_dir` override the resolved config for this
test only.

### `gentest.recording(*, model=None, mode=None, cache_dir=None)`

Context-manager form of `record`, for intercepting only part of a test:

```python
def test_reply():
    with gentest.recording():
        reply = generate_reply(...)
    gentest.expect(reply).contains_intent("apology")
```

## Assertions

### `gentest.expect(text, *, judge=None) -> Expectation`

Entry point for semantic and deterministic assertions on a string. Raises
`TypeError` if `text` isn't a `str`. Pass `judge=` to use a specific judge
instance instead of the configured default (mainly useful in tests of your own
code).

**`Expectation` methods** (all chainable, all raise `SemanticAssertionError`
— a subclass of `AssertionError` — on failure):

| Method | Judge-backed? | Description |
| :--- | :---: | :--- |
| `.contains_intent(intent)` | yes | text expresses the given intent/content |
| `.does_not_contain_intent(intent)` | yes | text does *not* express it |
| `.tone_is(tone)` | yes | overall tone matches |
| `.matches(criterion)` | yes | free-form judge criterion escape hatch |
| `.contains(substring)` | no | exact substring match |
| `.does_not_contain(substring)` | no | exact substring absence |
| `.is_valid_json()` | no | `json.loads` succeeds |

### `gentest.expect_tool_calls(calls) -> ToolCallExpectation`

Entry point for tool/function-call assertions. Normalizes OpenAI
(`function.arguments` as a JSON string), Anthropic (`input`), and plain
`{"name", "arguments"}` shapes automatically. `calls` may be `None` or empty.

**`ToolCallExpectation` methods** (all chainable):

| Method | Description |
| :--- | :--- |
| `.called(name)` | some call matches `name` |
| `.did_not_call(name)` | no call matches `name` |
| `.called_once(name)` | exactly one call matches `name` |
| `.call_count(n)` | exactly `n` calls total |
| `.called_with(name, **kwargs)` | some call to `name` has these argument values (subset match) |

`.names` (property) returns the list of called tool names; `len(expectation)`
returns the total call count.

## Configuration

### `gentest.configure(**kwargs) -> Config`

Overrides configuration for the current process. Accepts the same field names
as `Config` below. Returns the resulting `Config`.

```python
gentest.configure(judge="echo", judge_model="qwen2.5:7b")
```

### `gentest.Config`

Frozen dataclass holding all resolved settings:

| Field | Default | Meaning |
| :--- | :--- | :--- |
| `mode` | `"auto"` | `auto` \| `record` \| `replay` |
| `cache_dir` | `.gentest_cache` | Where recordings and verdicts live |
| `judge` | `"ollama"` | `ollama` \| `echo` |
| `judge_model` | `llama3.2:3b` | Model name passed to the judge backend |
| `judge_base_url` | `http://localhost:11434` | Ollama daemon URL |
| `judge_timeout` | `60.0` | Seconds before a judge call times out |
| `judge_cache` | `True` | Cache judge verdicts (see [recording.md](recording.md)) |
| `judge_votes` | `1` | Majority-vote grading count (see [assertions.md](assertions.md)) |

### `gentest.get_config() -> Config`

Returns the active, resolved configuration (defaults → `.gentest.yaml` →
environment → `configure()` overrides), computing it once per process.

### `gentest.load_config(start=None) -> Config`

Re-resolves configuration from scratch (defaults + file + env), ignoring any
prior `configure()` call. Mainly useful in tests of your own configuration.

### `gentest.set_config(cfg)` / `gentest.reset_config()`

Set the active config directly, or clear it so the next `get_config()` call
re-resolves from defaults/file/env. Used internally by the pytest plugin's
CLI-flag handling; rarely needed directly.

## Exceptions

| Exception | Raised when |
| :--- | :--- |
| `gentest.SemanticAssertionError` | Any `Expectation`/`ToolCallExpectation` assertion fails. Subclasses `AssertionError`. |
| `gentest.CacheMiss` | `mode="replay"` and no cached HTTP response or judge verdict exists for the request. |
| `gentest.UnsupportedHttpx` | The installed httpx version doesn't expose the hook the interceptor needs. |
| `gentest.judge.ollama.JudgeUnavailable` | The Ollama daemon is unreachable, the model isn't pulled, or it returned an error — not exported at the top level, imported from `gentest.judge.ollama` if you need to catch it specifically. |

## CLI

See [regression-tracking.md](regression-tracking.md) for `gentest list / show
/ diff` and [configuration.md](configuration.md) for `gentest doctor` and
`gentest init`.

## Pytest plugin

Auto-registered via the `pytest11` entry point — no conftest wiring needed.
Flags: `--gentest-record`, `--gentest-replay`, `--gentest-judge NAME`,
`--gentest-snapshot NAME`, `--gentest-label TEXT`. A `gentest_record` fixture
is also available as a factory form of the decorator for tests that prefer
explicit setup over `@gentest.record`.

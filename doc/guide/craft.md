# Prompt crafting: `ghostrun craft`

Every other guide in this project assumes you already have a prompt and want
to test it for regressions. `craft` is for the step before that: building the
prompt in the first place.

Instead of hand-writing prompt text and eyeballing whether it "feels right,"
you declare a **signature** — the input/output contract — and `ghostrun craft`
runs it for real against worked examples, keeping only the ones your judge
accepts. The result is a prompt with a curated set of few-shot examples that
you load into your app and then test normally.

Under the hood this is layered like a small framework, not one function:
a **signature** (typed contract) is rendered into chat messages by a
pluggable **adapter**, the pair becomes a callable **module**, and `craft()`
is the search that runs a module against worked examples and grades the
result. See [Architecture](#architecture) below if you want to go past the
CLI and call these pieces directly — e.g. to craft a chain-of-thought prompt,
or write your own adapter.

```bash
ghostrun craft refund_reply \
  --spec "question -> answer" \
  --examples examples.jsonl \
  --criterion "answer is empathetic and mentions the refund policy" \
  --model openai:gpt-4o-mini
```

## Why this belongs in ghostrun

The single reason this isn't just "go prompt-engineer separately": `craft`
grades candidate examples with the exact same judge — same backend, same
model, same verdict cache — that `ghostrun.expect(...)` uses at test time
(see [assertions.md](assertions.md)). Craft a prompt against a criterion,
then write a `@ghostrun.record` test against that *same* criterion, and both
stages answer to one judge instead of two hand-maintained descriptions of
"good" that quietly drift apart as the app evolves.

## The signature

A signature is `inputs -> outputs`, comma-separated on each side:

```
question -> answer
review -> sentiment: str, is_urgent: bool
customer_message, order_history -> reply: str, escalate: bool
```

Every field defaults to `str`. Two families of type are supported:

- **Scalar** — `str`, `int`, `float`, `bool`, or a constrained
  `Literal["a", "b", "c"]` — rendered as plain text on the wire.
- **Structured** — `list[str]`, `dict`, `list[int]`, or similar — rendered
  and parsed as JSON on that field's line, since there's no sane way to fit a
  nested value into one line of plain text.

```
review -> sentiment: Literal["positive", "negative", "neutral"], tags: list[str]
```

Every output field is validated through a real (pydantic-backed) type
check — a `Literal` value outside its allowed set, or a structured field that
isn't valid JSON, is treated as a rejected attempt during search, not a
crash.

## The examples file

One JSON object per line, one key per **input** field in the signature:

```jsonl
{"question": "Where is my refund? It's been three weeks."}
{"question": "Can I get a refund on a gift order?"}
{"question": "My refund shows processed but I never got the money."}
```

`craft` runs the signature against each row for real, in order, until it has
`--max-examples` accepted examples or runs out of rows.

## The criterion

Free-form text, graded by ghostrun's judge exactly like
`ghostrun.expect(reply).matches(criterion)`:

```bash
--criterion "answer is empathetic, mentions the refund policy, and does not over-promise a specific refund date"
```

Vague criteria produce vague results here for the same reason they do in
`.matches(...)` — see [assertions.md](assertions.md#how-reliable-is-the-judge)
on judge reliability before relying on a single vote for a nuanced call.

## Grading with gold labels: `metric=`

`--criterion` is judge-graded — a second LLM call decides pass/fail. For a
task where `examples_path` rows already carry the correct answer
(classification, extraction, anything with real ground truth), that's
slower, costs an extra call, and is *less* accurate than just comparing to
the gold value directly. From Python, pass `metric=` instead (CLI-only
crafting doesn't expose this — it's a Python API call):

```python
from ghostrun.craft import craft

def metric(prediction: dict, row: dict) -> bool:
    return prediction["category"] == row["category"] and prediction["urgency"] == row["urgency"]

result = craft(
    "triage", "message -> category, urgency", "examples.jsonl",
    metric=metric,  # examples.jsonl rows carry "category"/"urgency" gold fields
    model="openai:gpt-4o-mini",
)
```

`metric` receives the parsed prediction and the *whole* source row (inputs
and whatever else it carried, gold fields included) — pass exactly one of
`criterion=` or `metric=`, never both. No `Judge` object is constructed or
called on this path at all.

## The model

`--model` is `provider:model`:

```bash
--model openai:gpt-4o-mini
--model anthropic:claude-haiku-4-5-20251001
--model gemini:gemini-1.5-pro
--model groq:llama-3.3-70b-versatile
--model ollama:llama3.2
```

Supported providers: `openai`, `anthropic`, `gemini`, `groq`, `mistral`,
`cohere`, `deepseek`, `xai`, `perplexity`, `openrouter`, `together`,
`fireworks`, `azure`, `bedrock`, `ollama`. Each needs that provider's API key
set (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, ...) except
`ollama` (local daemon), `azure` (`AZURE_API_KEY`/`AZURE_API_BASE`/
`AZURE_API_VERSION`), and `bedrock` (AWS credential chain). Calls go through
[litellm](https://docs.litellm.ai) — retried automatically (2 attempts by
default) — but are deliberately **not** cached or routed through ghostrun's
record/replay interceptor. A search needs a different completion on each
retry to have anything to search over; caching identical requests here would
just return the same rejected answer forever. Recording/replaying is what
you do with the *finished* prompt in a normal test, not during the search
itself.

Two more knobs on the client itself:

- **`--min-interval SECONDS`** paces calls (sleeping before a call if the
  previous one finished less than that long ago). Some providers' free/low
  tiers enforce requests-per-minute limits tight enough that a search making
  back-to-back calls trips them before litellm's own retry logic would help
  — raise this if you're seeing rate-limit errors.
- **Spend tracking** — every `craft()` run reports what it actually cost:
  `result.tokens_used` and `result.estimated_cost_usd` (via
  `litellm.completion_cost`, when the model has pricing data litellm knows
  about), also printed by the CLI. This comes from the `LLMClient` itself
  (`.total_tokens`/`.total_cost`/`.call_count`), so it's available even
  calling `LLMClient` directly outside of `craft()`.

## Retries: `--max-attempts` and `max_repair_attempts`

Two different kinds of retry, easy to conflate:

- **`--max-attempts`** (search-level): when grading rejects a reply, `craft`
  retries that same source example (up to this many times) at a higher
  temperature before giving up on it and moving to the next row. Default
  `1` — no retry, first reply or nothing. A row that never produces an
  accepted reply within the budget is simply skipped; it does not fail the
  whole run.
- **`max_repair_attempts`** (module-level, Python API only): when a reply
  doesn't *parse* — a missing field, invalid JSON on a structured field, a
  `Literal` value outside its allowed set — `Predict`/`ChainOfThought` can
  re-ask the model with the parse error appended ("that reply didn't match
  the required format: ...") instead of raising immediately:

  ```python
  from ghostrun.craft import Predict, Signature

  module = Predict(Signature.parse("question -> answer"), max_repair_attempts=1)
  ```

  Default `0` (raise immediately, matching prior behavior) since it costs an
  extra call per malformed reply; worth turning on for a signature with
  strict types (`Literal`, structured fields) where a real model occasionally
  drifts off-format.

## Real search: `--budget`

By default `craft` runs `BootstrapFewShot`: one greedy pass, for each row
keep the first reply the judge accepts. Fast, but it only ever varies *which
examples* end up in the prompt — the instructions are never touched, and it
never asks "would a different phrasing or example set have generalized
better?"

`--budget` switches to `BayesianSearch`:

```bash
ghostrun craft refund_reply \
  --spec "question -> answer" \
  --examples examples.jsonl \
  --criterion "answer is empathetic and mentions the refund policy" \
  --model openai:gpt-4o-mini \
  --budget 40
```

With a budget set, `craft`:

1. reserves a tail slice of `--examples` as a **held-out set** (`--holdout-ratio`,
   default `0.3`) that never gets used as a few-shot demo,
2. makes one call asking the model to propose a few alternative phrasings of
   the instructions, grounded in the signature and your `--criterion`,
3. runs [optuna](https://optuna.org)'s TPE sampler over trials that each pick
   *which instruction phrasing* to use and *how much to vary* the
   demo-bootstrapping temperature,
4. scores each trial's finished prompt — its instructions + chosen examples —
   against the held-out rows, grading with the judge,
5. saves the best-scoring trial, instructions and all — not just the first
   thing that happened to pass on its own training rows.

This searches over instructions *and* demos, with a real optimizer doing the
searching, not just retried temperature jitter. The number of trials is
roughly `budget // (max_examples * max_attempts + holdout_rows)` (minus one
call spent proposing instructions), so a bigger budget buys more trials —
except when the holdout set is large, in which case scoring it *every
single trial* dominates the cost and a realistic budget barely buys more
than one or two trials, which is barely a search.

**`--holdout-sample-size N`** caps how many held-out rows each trial scores
against (default: all of them). Trade a noisier per-trial score for far more
trials at the same budget — e.g. with a 20-row holdout, capping to 5 lets a
budget that previously afforded 1 trial afford 4. The winning trial's
*demos* are always real accepted examples either way; only the ranking
signal used to pick among trials gets sampled.

**`--resume`** persists search trials to
`<cache_dir>/prompts/<name>.study.sqlite3` (via
[optuna's own storage mechanism](https://optuna.readthedocs.io/en/stable/tutorial/20_recipes/001_rdb.html),
not something ghostrun reimplements). A `craft()` run interrupted partway
through — a network blip, a rate limit, Ctrl+C — can be re-run with the
same `name`/`--budget`/arguments and continue from the trials already
recorded instead of starting the search over from scratch.

Needs at least 4 rows in `--examples` to hold anything out; fewer than that
and `craft` skips holdout scoring (`holdout_score` comes back `None` in the
saved file). If the instruction-proposal meta-call fails twice (malformed
JSON both times), the search falls back to just the original instructions —
`result.instruction_candidates` tells you how many phrasings were actually
in play (`1` means the fallback happened, or `--budget` wasn't used).

## What gets saved

```json
{
  "name": "refund_reply",
  "spec": "question -> answer",
  "instructions": "Given question, produce answer.",
  "criterion": "answer is empathetic and mentions the refund policy",
  "model": "openai:gpt-4o-mini",
  "examples": [
    {"question": "Where is my refund? ...", "answer": "I'm sorry for the wait..."}
  ],
  "crafted_at": "2026-08-28T12:00:00+00:00",
  "holdout_score": null,
  "candidates_tried": 1,
  "budget": null,
  "instruction_candidates": 1,
  "tokens_used": 842,
  "estimated_cost_usd": 0.0003
}
```

`holdout_score`, `candidates_tried`, `budget`, and `instruction_candidates`
are only meaningful when `--budget` was used (see above) — they stay at
their defaults (`null`, `1`, `null`, `1`) for a plain single-pass run.
`tokens_used`/`estimated_cost_usd` are `null` only if a custom `client=`
without usage tracking was passed in.

Saved to `<cache_dir>/prompts/<name>.json` (default `.ghostrun_cache/prompts/`).
Load it back with:

```python
from ghostrun.craft import CraftedPrompt

prompt = CraftedPrompt.load(".ghostrun_cache/prompts/refund_reply.json")
```

`prompt.instructions` and `prompt.examples` are what you assemble into your
app's actual prompt (system instructions + a few worked examples before the
real query) — `craft` hands you the ingredients, not a magic runtime that
calls your app for you.

## Closing the loop: test what you crafted

```python
import ghostrun
from my_app import generate_reply

@ghostrun.record(model="gpt-4o-mini")
def test_refund_reply_is_empathetic():
    reply = generate_reply("Where is my refund? It's been three weeks.")
    ghostrun.expect(reply).matches(
        "answer is empathetic and mentions the refund policy"
    )
```

Same criterion text as `--criterion`, same judge, same cache. Crafting builds
the prompt; this is the regression test that keeps it from silently breaking
later — see [recording.md](recording.md) and
[regression-tracking.md](regression-tracking.md) for the rest of that loop.

## Architecture

`ghostrun.craft` is layered so each piece is swappable and testable on its
own:

```
Signature   -- typed input/output contract ("question -> answer")
    |
Adapter     -- signature + examples + inputs -> chat messages
    |          (and: a raw reply -> typed field values)
Module      -- adapter + signature, callable against an LLMClient
    |          (Predict = one call; ChainOfThought = + a reasoning field)
craft()     -- the search: runs a Module against worked examples,
               grades results with ghostrun's judge, keeps the best
```

The CLI only ever builds a plain `Predict`. To craft a **chain-of-thought**
prompt (the model reasons before answering) or supply your own adapter, call
`craft()` from Python directly:

```python
from ghostrun.craft import ChainOfThought, Signature, craft

module = ChainOfThought(Signature.parse("question -> answer"))

result = craft(
    "refund_reply_cot", "question -> answer", "examples.jsonl",
    "answer is empathetic and mentions the refund policy",
    model="openai:gpt-4o-mini", module=module,
)
```

A crafted chain-of-thought prompt's saved `examples` include the model's
`reasoning` field alongside the real outputs — drop it (or keep it, if your
app also wants to show reasoning) when you assemble the final prompt.

Writing your own adapter means subclassing `Adapter` and implementing
`system_message()`, `build_messages()`, and `parse()` — see
[adapters.py](https://github.com/parthmax2/ghostrun/blob/main/ghostrun/craft/adapters.py)
for the shape `DelimiterAdapter` (the built-in, default one) implements.

### Composed programs: `RAG` and `Agent`

Modules can call other Modules. Two are built in:

```python
from ghostrun.craft import RAG, Agent, Signature, Tool

# retrieval-augmented generation: retrieves passages, then answers with
# them folded into a `context` field. Bring your own retriever -- ghostrun
# doesn't ship a vector store.
rag = RAG(Signature.parse("question -> answer"), retriever=my_retriever, k=3)
prediction = rag.forward(client, question="Where is my refund?")

# a ReAct-style tool loop: the model either calls a tool (run locally,
# fed back as an observation) or finishes, up to max_steps.
lookup = Tool(name="lookup_order", func=lookup_order, description="look up an order by ID")
agent = Agent(Signature.parse("question -> answer"), tools=[lookup], max_steps=5)
prediction = agent.forward(client, question="Where is order A123?")
```

`RAG` uses the signature's *first* input field as the retrieval query, and
folds the retrieved passages into a `context` field before calling an inner
`Predict` (or `ChainOfThought`, with `reasoning=True`). `Agent` builds an
internal step-signature (`thought`, `action`, `action_input`) and loops:
calling a tool locally when the model requests one, or coercing
`action_input` into the real signature's outputs (as JSON, if there's more
than one output field) when the model says `"finish"`.

Neither is wired into `craft()`'s search yet — bootstrapping few-shot
examples for *each step* of a composed program, not just one flat signature,
is real additional work, not built here. Both are usable directly today,
independent of the search.

## If nothing gets accepted

`craft` still saves a prompt with zero examples rather than failing outright,
and the CLI says so explicitly. That usually means one of:

- the criterion is stricter than the model can consistently satisfy at
  `temperature=0` — try raising `--max-attempts`
- the criterion is genuinely ambiguous — see the judge-reliability notes in
  [assertions.md](assertions.md)
- the signature's output types don't match what the model naturally produces
  (e.g. asking for `bool` when the model wants to explain itself) — narrow
  the instructions implied by your field names, or loosen the type to `str`
  and parse further downstream

## Testing craft itself against a real provider

Everything in ghostrun's own test suite for `craft` is stub-based — fast,
free, deterministic. `tests/test_craft_live.py` is a separate, opt-in tier
that makes real calls, excluded by default:

```bash
pytest -m live tests/test_craft_live.py
```

Needs `GEMINI_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY` set;
skipped automatically otherwise. Cheap (a handful of short completions on a
cheap/free-tier-eligible model) but not free — this is what actually proves
a signature/adapter/module change works against a real response shape,
which stub-based tests structurally cannot catch.

## API reference

See [api-reference.md](api-reference.md#prompt-crafting) for the full
`ghostrun.craft` package surface (`Signature`, `Adapter`/`DelimiterAdapter`,
`Module`/`Predict`/`ChainOfThought`, `craft()`, `CraftedPrompt`, `LLMClient`,
exceptions).

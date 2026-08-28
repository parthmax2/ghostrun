"""`ghostrun craft` -- native prompt-building framework: typed signatures,
pluggable adapters, modules, and the bootstrapping search, all without any
network call (a stub LLMClient and stub judge stand in)."""

import json
from pathlib import Path
from typing import Literal

import pytest

from ghostrun.craft import (
    ChainOfThought,
    CraftedPrompt,
    CraftError,
    DelimiterAdapter,
    LLMClient,
    ParseError,
    Predict,
    ProviderError,
    Signature,
    SignatureError,
    craft,
    prompts_dir,
)
from ghostrun.judge.base import Grade


# --- Signature -----------------------------------------------------------


def test_signature_parses_default_str_fields():
    sig = Signature.parse("question -> answer")
    assert [f.name for f in sig.inputs] == ["question"]
    assert [f.name for f in sig.outputs] == ["answer"]
    assert sig.outputs[0].annotation is str


def test_signature_parses_typed_and_multiple_fields():
    sig = Signature.parse("review -> sentiment: str, is_urgent: bool")
    assert [(f.name, f.annotation) for f in sig.outputs] == [("sentiment", str), ("is_urgent", bool)]


def test_signature_parses_structured_types():
    sig = Signature.parse('review -> tags: list[str], meta: dict')
    assert sig.outputs[0].annotation == list[str]
    assert sig.outputs[1].annotation is dict


def test_signature_parses_literal_without_splitting_on_its_commas():
    sig = Signature.parse('review -> sentiment: Literal["pos", "neg", "neutral"]')
    assert sig.outputs[0].annotation == Literal["pos", "neg", "neutral"]


def test_signature_rejects_missing_arrow():
    with pytest.raises(SignatureError, match="->"):
        Signature.parse("question answer")


def test_signature_rejects_unknown_type():
    with pytest.raises(SignatureError, match="unrecognized field type"):
        Signature.parse("question -> answer: NotAType")


def test_signature_rejects_duplicate_field_names():
    with pytest.raises(SignatureError, match="duplicate"):
        Signature.parse("x -> x")


def test_signature_rejects_empty_side():
    with pytest.raises(SignatureError, match="input field"):
        Signature.parse(" -> answer")


def test_signature_with_reasoning_prepends_field():
    sig = Signature.parse("question -> answer")
    augmented = sig.with_reasoning()
    assert [f.name for f in augmented.outputs] == ["reasoning", "answer"]
    assert [f.name for f in sig.outputs] == ["answer"]  # original untouched


def test_signature_coerce_outputs_validates_via_pydantic():
    sig = Signature.parse('review -> sentiment: Literal["pos", "neg"], score: int')
    assert sig.coerce_outputs({"sentiment": "pos", "score": "5"}) == {"sentiment": "pos", "score": 5}
    with pytest.raises(ParseError, match="validation"):
        sig.coerce_outputs({"sentiment": "neutral", "score": "5"})


def test_signature_coerce_outputs_parses_structured_json():
    sig = Signature.parse("review -> tags: list[str]")
    assert sig.coerce_outputs({"tags": '["a", "b"]'}) == {"tags": ["a", "b"]}
    with pytest.raises(ParseError, match="JSON"):
        sig.coerce_outputs({"tags": "not json"})


# --- DelimiterAdapter: template / parse round-trip ------------------------


def test_adapter_build_messages_and_parse_round_trip():
    sig = Signature.parse("question -> answer")
    adapter = DelimiterAdapter()
    messages = adapter.build_messages(sig, examples=[{"question": "Q1", "answer": "A1"}],
                                      inputs={"question": "Q2"})
    assert messages[0] == {"role": "user", "content": ">>> question\nQ1"}
    assert messages[1] == {"role": "assistant", "content": ">>> answer\nA1"}
    assert messages[2] == {"role": "user", "content": ">>> question\nQ2"}

    assert adapter.parse(sig, ">>> answer\nParis") == {"answer": "Paris"}


def test_adapter_parse_coerces_types():
    sig = Signature.parse("review -> sentiment: str, is_urgent: bool, score: int")
    adapter = DelimiterAdapter()
    reply = ">>> sentiment\npositive\n>>> is_urgent\nyes\n>>> score\n7"
    assert adapter.parse(sig, reply) == {"sentiment": "positive", "is_urgent": True, "score": 7}


def test_adapter_parse_structured_field_as_json():
    sig = Signature.parse("review -> tags: list[str]")
    adapter = DelimiterAdapter()
    reply = '>>> tags\n["a", "b"]'
    assert adapter.parse(sig, reply) == {"tags": ["a", "b"]}


def test_adapter_parse_no_markers_raises():
    sig = Signature.parse("question -> answer")
    with pytest.raises(ParseError, match="no .* markers"):
        DelimiterAdapter().parse(sig, "no markers here")


def test_adapter_parse_missing_field_raises():
    sig = Signature.parse("review -> sentiment, urgency")
    with pytest.raises(ParseError, match="missing field 'urgency'"):
        DelimiterAdapter().parse(sig, ">>> sentiment\npositive")


def test_adapter_system_message_lists_fields_in_order():
    sig = Signature.parse("a, b -> c")
    msg = DelimiterAdapter().system_message(sig)
    assert "Given a, b, produce c." in msg
    assert "- a (str)" in msg
    assert "- b (str)" in msg
    assert "- c (str)" in msg


# --- Modules ---------------------------------------------------------------


class ScriptedClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, system, messages, temperature=0.0):
        self.calls.append((system, messages, temperature))
        return self.replies.pop(0)


def test_predict_forward_calls_client_and_parses():
    module = Predict(Signature.parse("question -> answer"))
    client = ScriptedClient([">>> answer\nParis"])
    prediction = module.forward(client, question="Capital of France?")
    assert prediction == {"answer": "Paris"}
    assert prediction.answer == "Paris"  # attribute access
    with pytest.raises(AttributeError):
        prediction.nope


def test_predict_uses_current_demos():
    module = Predict(Signature.parse("question -> answer"))
    module.demos = [{"question": "Q1", "answer": "A1"}]
    client = ScriptedClient([">>> answer\nA2"])
    module.forward(client, question="Q2")
    messages = client.calls[0][1]
    assert messages[0] == {"role": "user", "content": ">>> question\nQ1"}


def test_predict_raises_immediately_when_repair_disabled():
    module = Predict(Signature.parse("question -> answer"))  # max_repair_attempts=0 default
    client = ScriptedClient(["not a valid reply at all"])
    with pytest.raises(ParseError):
        module.forward(client, question="Q")
    assert len(client.calls) == 1  # no retry


def test_predict_repairs_a_malformed_reply():
    module = Predict(Signature.parse("question -> answer"), max_repair_attempts=1)
    client = ScriptedClient(["not a valid reply at all", ">>> answer\nParis"])
    prediction = module.forward(client, question="Capital of France?")
    assert prediction == {"answer": "Paris"}
    assert len(client.calls) == 2
    # the repair turn should include the bad reply and a correction request
    second_call_messages = client.calls[1][1]
    assert second_call_messages[-2] == {"role": "assistant", "content": "not a valid reply at all"}
    assert "didn't match the required format" in second_call_messages[-1]["content"]


def test_predict_gives_up_after_max_repair_attempts():
    module = Predict(Signature.parse("question -> answer"), max_repair_attempts=2)
    client = ScriptedClient(["bad 1", "bad 2", "bad 3"])
    with pytest.raises(ParseError):
        module.forward(client, question="Q")
    assert len(client.calls) == 3  # original + 2 repair attempts


def test_chain_of_thought_adds_reasoning_field():
    module = ChainOfThought(Signature.parse("question -> answer"))
    assert [f.name for f in module.signature.outputs] == ["reasoning", "answer"]
    client = ScriptedClient([">>> reasoning\nFrance's capital is well known.\n>>> answer\nParis"])
    prediction = module.forward(client, question="Capital of France?")
    assert prediction == {"reasoning": "France's capital is well known.", "answer": "Paris"}


# --- LLMClient ------------------------------------------------------------


def test_llm_client_rejects_bad_model_string():
    with pytest.raises(ProviderError, match="provider:model"):
        LLMClient("gpt-4o-mini")


def test_llm_client_rejects_unknown_provider():
    with pytest.raises(ProviderError, match="unsupported provider"):
        LLMClient("notreal:some-model")


def test_llm_client_supports_many_providers():
    for provider in ("openai", "anthropic", "gemini", "groq", "mistral", "cohere",
                     "deepseek", "xai", "perplexity", "openrouter", "together",
                     "fireworks", "azure", "bedrock", "ollama"):
        client = LLMClient(f"{provider}:some-model")
        assert client.provider == provider


def test_llm_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = LLMClient("openai:gpt-4o-mini")
    with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
        client.complete("sys", [{"role": "user", "content": "hi"}])


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


def test_llm_client_complete_translates_model_and_calls_litellm(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _FakeResponse("hello")

    monkeypatch.setattr("ghostrun.craft.providers.litellm.completion", fake_completion)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    client = LLMClient("anthropic:claude-haiku-4-5")
    result = client.complete("sys", [{"role": "user", "content": "hi"}], temperature=0.2)

    assert result == "hello"
    assert captured["model"] == "anthropic/claude-haiku-4-5"
    assert captured["temperature"] == 0.2
    assert captured["messages"][0] == {"role": "system", "content": "sys"}


def test_llm_client_openai_model_has_no_prefix(monkeypatch):
    captured = {}
    monkeypatch.setattr("ghostrun.craft.providers.litellm.completion",
                        lambda **kw: captured.update(kw) or _FakeResponse("hi"))
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    LLMClient("openai:gpt-4o-mini").complete("sys", [])
    assert captured["model"] == "gpt-4o-mini"


def test_llm_client_wraps_litellm_errors_as_provider_error(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("rate limited")

    monkeypatch.setattr("ghostrun.craft.providers.litellm.completion", boom)
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    with pytest.raises(ProviderError, match="rate limited"):
        LLMClient("openai:gpt-4o-mini").complete("sys", [])


class _FakeDelta:
    def __init__(self, content):
        self.content = content


class _FakeStreamChoice:
    def __init__(self, content):
        self.delta = _FakeDelta(content)


class _FakeChunk:
    def __init__(self, content):
        self.choices = [_FakeStreamChoice(content)]


def test_llm_client_stream_yields_text_chunks(monkeypatch):
    def fake_completion(**kwargs):
        assert kwargs["stream"] is True
        return iter([_FakeChunk("Hel"), _FakeChunk("lo"), _FakeChunk(None)])

    monkeypatch.setattr("ghostrun.craft.providers.litellm.completion", fake_completion)
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    chunks = list(LLMClient("openai:gpt-4o-mini").stream("sys", [{"role": "user", "content": "hi"}]))
    assert chunks == ["Hel", "lo"]


class _FakeUsage:
    def __init__(self, total_tokens):
        self.total_tokens = total_tokens


def test_llm_client_tracks_tokens_and_cost(monkeypatch):
    response = _FakeResponse("hi")
    response.usage = _FakeUsage(42)
    monkeypatch.setattr("ghostrun.craft.providers.litellm.completion", lambda **kw: response)
    monkeypatch.setattr("ghostrun.craft.providers.litellm.completion_cost", lambda **kw: 0.002)
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    client = LLMClient("openai:gpt-4o-mini")
    client.complete("sys", [])
    client.complete("sys", [])

    assert client.call_count == 2
    assert client.total_tokens == 84
    assert client.total_cost == pytest.approx(0.004)


def test_llm_client_cost_tracking_survives_missing_pricing_data(monkeypatch):
    monkeypatch.setattr("ghostrun.craft.providers.litellm.completion", lambda **kw: _FakeResponse("hi"))

    def boom(**kw):
        raise Exception("no pricing data for this model")

    monkeypatch.setattr("ghostrun.craft.providers.litellm.completion_cost", boom)
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    client = LLMClient("openai:gpt-4o-mini")
    assert client.complete("sys", []) == "hi"  # doesn't raise
    assert client.total_cost == 0.0


def test_llm_client_min_interval_paces_calls(monkeypatch):
    monkeypatch.setattr("ghostrun.craft.providers.litellm.completion", lambda **kw: _FakeResponse("hi"))
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    slept = []
    monkeypatch.setattr("ghostrun.craft.providers.time.sleep", lambda s: slept.append(s))

    client = LLMClient("openai:gpt-4o-mini", min_interval=5.0)
    client.complete("sys", [])
    assert slept == []  # nothing to pace against on the first call
    client.complete("sys", [])
    assert len(slept) == 1
    assert slept[0] <= 5.0


# --- craft() search loop, fully offline -----------------------------------


class StubClient:
    """Returns a scripted reply per call; records what it was sent."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, system, messages, temperature=0.0):
        self.calls.append((system, messages, temperature))
        return self.replies.pop(0)


class StubJudge:
    def __init__(self, verdicts=None, default=True):
        self.verdicts = list(verdicts) if verdicts is not None else None
        self.default = default
        self.graded = []

    def grade(self, text, criterion):
        self.graded.append((text, criterion))
        passed = self.verdicts.pop(0) if self.verdicts else self.default
        return Grade(passed=passed, reason="stub")


def _examples_file(tmp_path, rows):
    path = tmp_path / "examples.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return path


def test_craft_accepts_examples_the_judge_passes(tmp_path):
    client = StubClient([">>> answer\nParis", ">>> answer\nBerlin"])
    judge = StubJudge(default=True)

    result = craft(
        "capitals", "question -> answer", str(_examples_file(tmp_path, [
            {"question": "Capital of France?"},
            {"question": "Capital of Germany?"},
        ])),
        "is correct",
        model="openai:gpt-4o-mini",
        judge=judge,
        client=client,
        max_examples=4,
        cache_dir=str(tmp_path / "cache"),
    )

    assert result.name == "capitals"
    assert result.examples == [
        {"question": "Capital of France?", "answer": "Paris"},
        {"question": "Capital of Germany?", "answer": "Berlin"},
    ]
    saved = prompts_dir(str(tmp_path / "cache")) / "capitals.json"
    assert saved.is_file()
    assert CraftedPrompt.load(saved).examples == result.examples


def test_craft_stops_at_max_examples(tmp_path):
    client = StubClient([">>> answer\nA", ">>> answer\nB", ">>> answer\nC"])
    judge = StubJudge(default=True)

    result = craft(
        "capped", "question -> answer",
        str(_examples_file(tmp_path, [{"question": f"Q{i}"} for i in range(3)])),
        "is correct", model="openai:gpt-4o-mini", judge=judge, client=client,
        max_examples=2, cache_dir=str(tmp_path / "cache"),
    )
    assert len(result.examples) == 2
    assert len(client.calls) == 2  # never asked for the third


def test_craft_retries_rejected_examples_up_to_max_attempts(tmp_path):
    # First attempt fails the judge, second attempt (higher temperature) passes.
    client = StubClient([">>> answer\nWrong", ">>> answer\nParis"])
    judge = StubJudge(verdicts=[False, True])

    result = craft(
        "retry", "question -> answer",
        str(_examples_file(tmp_path, [{"question": "Capital of France?"}])),
        "is correct", model="openai:gpt-4o-mini", judge=judge, client=client,
        max_examples=4, max_attempts=2, cache_dir=str(tmp_path / "cache"),
    )
    assert result.examples == [{"question": "Capital of France?", "answer": "Paris"}]
    assert client.calls[0][2] == 0.0   # first attempt: temperature 0
    assert client.calls[1][2] == 1.0   # retry: temperature 1


def test_craft_gives_up_after_max_attempts_exhausted(tmp_path):
    client = StubClient([">>> answer\nWrong", ">>> answer\nStillWrong"])
    judge = StubJudge(default=False)

    result = craft(
        "hopeless", "question -> answer",
        str(_examples_file(tmp_path, [{"question": "Q"}])),
        "is correct", model="openai:gpt-4o-mini", judge=judge, client=client,
        max_examples=4, max_attempts=2, cache_dir=str(tmp_path / "cache"),
    )
    assert result.examples == []


def test_craft_raises_on_missing_input_field(tmp_path):
    with pytest.raises(CraftError, match="missing input field"):
        craft(
            "bad", "question -> answer",
            str(_examples_file(tmp_path, [{"not_question": "huh"}])),
            "is correct", model="openai:gpt-4o-mini",
            judge=StubJudge(), client=StubClient([]),
            cache_dir=str(tmp_path / "cache"),
        )


class InstructionAwareClient:
    """A fake client whose reply depends on the *content* of the system
    message, not call order -- robust to however optuna's TPE sampler
    schedules its trials. Replies to the instruction-proposal meta-call
    (detected by "Propose" in the prompt) with a scripted JSON pool; every
    other call answers "GoodAnswer" if its system message (i.e. the
    instructions in effect for that trial) contains "GOOD", else "BadAnswer"."""

    def __init__(self, instruction_pool):
        self.instruction_pool_json = json.dumps(instruction_pool)
        self.calls = []

    def complete(self, system, messages, temperature=0.0):
        self.calls.append((system, messages, temperature))
        last_user = messages[-1]["content"] if messages else ""
        if "Propose" in system or "Propose" in last_user:
            return self.instruction_pool_json
        if "GOOD" in system:
            return ">>> answer\nGoodAnswer"
        return ">>> answer\nBadAnswer"


class ContentJudge:
    """Grades by literal content instead of a scripted verdict queue, for
    the same call-order-independence reason as InstructionAwareClient."""

    def grade(self, text, criterion):
        return Grade(passed="GoodAnswer" in text, reason="content-based")


def test_craft_with_budget_runs_bayesian_search_over_instructions(tmp_path):
    rows = [{"question": f"Q{i}"} for i in range(1, 7)]  # -> 4-row demo pool, 2-row holdout
    client = InstructionAwareClient(["GOOD instructions to follow"])
    judge = ContentJudge()

    result = craft(
        "searched", "question -> answer", str(_examples_file(tmp_path, rows)),
        "is correct", model="openai:gpt-4o-mini", judge=judge, client=client,
        max_examples=1, max_attempts=1, budget=60, holdout_ratio=0.3,
        cache_dir=str(tmp_path / "cache"),
    )

    # BayesianSearch should have found and kept the better-scoring instructions.
    assert result.instructions == "GOOD instructions to follow"
    assert result.holdout_score == 1.0
    assert result.candidates_tried > 1
    assert all(ex["answer"] == "GoodAnswer" for ex in result.examples)

    saved = CraftedPrompt.load(prompts_dir(str(tmp_path / "cache")) / "searched.json")
    assert saved.instructions == "GOOD instructions to follow"
    assert saved.budget == 60


def test_craft_with_budget_and_too_few_rows_skips_holdout(tmp_path):
    # Only 2 rows: split_holdout refuses to split (< 4 rows), so there's
    # nothing to hold out and holdout_score stays None.
    # An empty JSON array is a *valid* (if unhelpful) proposal reply, so the
    # instruction-proposal step succeeds on its first attempt and costs
    # exactly 1 call, matching this test's fixed 3-call budget below.
    client = StubClient(["[]", ">>> answer\nA", ">>> answer\nB"])
    judge = StubJudge(default=True)

    result = craft(
        "small", "question -> answer",
        str(_examples_file(tmp_path, [{"question": "Q1"}, {"question": "Q2"}])),
        "is correct", model="openai:gpt-4o-mini", judge=judge, client=client,
        max_examples=4, max_attempts=1, budget=5, cache_dir=str(tmp_path / "cache"),
    )
    assert result.holdout_score is None
    assert result.candidates_tried == 1


def test_craft_without_budget_leaves_new_fields_at_defaults(tmp_path):
    client = StubClient([">>> answer\nParis"])
    result = craft(
        "unbudgeted", "question -> answer",
        str(_examples_file(tmp_path, [{"question": "Q1"}])),
        "is correct", model="openai:gpt-4o-mini", judge=StubJudge(default=True), client=client,
        cache_dir=str(tmp_path / "cache"),
    )
    assert result.budget is None
    assert result.holdout_score is None
    assert result.candidates_tried == 1


def test_bootstrap_few_shot_optimizer_used_directly():
    from ghostrun.craft.optimizers import BootstrapFewShot, judge_grader

    module = Predict(Signature.parse("question -> answer"))
    client = StubClient([">>> answer\nParis"])
    judge = StubJudge(default=True)
    optimizer = BootstrapFewShot(max_examples=4, max_attempts=1)

    compiled = optimizer.compile(module, [{"question": "Capital of France?"}],
                                 judge_grader(judge, "is correct"), client)
    assert compiled.examples == [{"question": "Capital of France?", "answer": "Paris"}]
    assert compiled.holdout_score is None  # BootstrapFewShot never scores a holdout


def test_split_holdout_reserves_a_tail_slice():
    from ghostrun.craft.optimizers import split_holdout

    rows = [{"question": f"Q{i}"} for i in range(6)]
    demo_pool, holdout = split_holdout(rows, ratio=0.3)
    assert demo_pool == rows[:4]
    assert holdout == rows[4:]


def test_split_holdout_skips_when_too_few_rows():
    from ghostrun.craft.optimizers import split_holdout

    rows = [{"question": "Q1"}, {"question": "Q2"}]
    demo_pool, holdout = split_holdout(rows, ratio=0.3)
    assert demo_pool == rows
    assert holdout == []


def test_craft_can_use_a_custom_module(tmp_path):
    """Passing `module=` lets you craft a ChainOfThought prompt instead of a
    plain one -- the search doesn't care which Module it's driving."""
    module = ChainOfThought(Signature.parse("question -> answer"))
    client = StubClient([">>> reasoning\nBecause geography.\n>>> answer\nParis"])
    judge = StubJudge(default=True)

    result = craft(
        "cot", "question -> answer",
        str(_examples_file(tmp_path, [{"question": "Capital of France?"}])),
        "is correct", model="openai:gpt-4o-mini", judge=judge, client=client,
        module=module, cache_dir=str(tmp_path / "cache"),
    )
    assert result.examples == [{
        "question": "Capital of France?", "reasoning": "Because geography.", "answer": "Paris",
    }]


def test_craft_requires_exactly_one_of_criterion_or_metric(tmp_path):
    path = _examples_file(tmp_path, [{"question": "Q1"}])
    with pytest.raises(CraftError, match="exactly one of"):
        craft("x", "question -> answer", str(path), model="openai:gpt-4o-mini",
              client=StubClient([]), cache_dir=str(tmp_path / "cache"))
    with pytest.raises(CraftError, match="exactly one of"):
        craft("x", "question -> answer", str(path), "is correct",
              metric=lambda pred, row: True, model="openai:gpt-4o-mini",
              client=StubClient([]), cache_dir=str(tmp_path / "cache"))


def test_craft_with_gold_metric_grades_without_a_judge(tmp_path):
    """Rows carry a gold `answer`; the metric compares the prediction to it
    directly -- no Judge object involved at all."""
    rows = [{"question": "Capital of France?", "answer": "Paris"},
            {"question": "Capital of Germany?", "answer": "Berlin"}]
    client = StubClient([">>> answer\nParis", ">>> answer\nWrong"])

    def metric(prediction, row):
        return prediction["answer"] == row["answer"]

    result = craft(
        "gold", "question -> answer", str(_examples_file(tmp_path, rows)),
        metric=metric, model="openai:gpt-4o-mini", client=client,
        max_examples=4, cache_dir=str(tmp_path / "cache"),
    )
    # Only the first row's prediction matched its gold answer.
    assert result.examples == [{"question": "Capital of France?", "answer": "Paris"}]
    assert result.criterion is None


def test_craft_tracks_tokens_and_cost_from_the_client(tmp_path):
    client = StubClient([">>> answer\nParis"])
    client.total_tokens = 123
    client.total_cost = 0.0042

    result = craft(
        "costed", "question -> answer",
        str(_examples_file(tmp_path, [{"question": "Q"}])),
        "is correct", model="openai:gpt-4o-mini", judge=StubJudge(default=True), client=client,
        cache_dir=str(tmp_path / "cache"),
    )
    assert result.tokens_used == 123
    assert result.estimated_cost_usd == 0.0042


def test_craft_with_client_missing_usage_tracking_leaves_cost_none(tmp_path):
    class BareClient:
        def __init__(self):
            self.calls = []

        def complete(self, system, messages, temperature=0.0):
            self.calls.append(1)
            return ">>> answer\nParis"

    result = craft(
        "no_tracking", "question -> answer",
        str(_examples_file(tmp_path, [{"question": "Q"}])),
        "is correct", model="openai:gpt-4o-mini", judge=StubJudge(default=True), client=BareClient(),
        cache_dir=str(tmp_path / "cache"),
    )
    assert result.tokens_used is None
    assert result.estimated_cost_usd is None


def test_bayesian_search_retries_instruction_proposal_once(tmp_path):
    """First proposal reply is garbage, second is valid JSON -- the pool
    should reflect the second attempt, not fall back to just the original."""
    rows = [{"question": f"Q{i}"} for i in range(1, 5)]
    client = StubClient([
        "not json at all",                 # meta call, attempt 1: fails
        json.dumps(["BETTER instructions"]),  # meta call, attempt 2: succeeds
        ">>> answer\nA",                    # bootstrap over demo_pool (2 rows after split)
        ">>> answer\nB",
        ">>> answer\nC",                    # holdout scoring (2 rows after split)
        ">>> answer\nD",
    ])
    judge = StubJudge(default=True)

    result = craft(
        "retry_meta", "question -> answer", str(_examples_file(tmp_path, rows)),
        "is correct", model="openai:gpt-4o-mini", judge=judge, client=client,
        max_examples=2, max_attempts=1, budget=6, holdout_ratio=0.5,
        cache_dir=str(tmp_path / "cache"),
    )
    assert result.instruction_candidates == 2  # original + the recovered proposal


def test_bayesian_search_holdout_sample_size_caps_scoring_cost(tmp_path):
    """10 rows -> holdout of 3 (round(10*0.3)); capping holdout_sample_size
    to 1 should mean each trial scores only 1 holdout row, not all 3."""
    rows = [{"question": f"Q{i}"} for i in range(1, 11)]
    client = StubClient([json.dumps([])] + [">>> answer\nA"] * 40)
    judge = StubJudge(default=True)

    result = craft(
        "capped_holdout", "question -> answer", str(_examples_file(tmp_path, rows)),
        "is correct", model="openai:gpt-4o-mini", judge=judge, client=client,
        max_examples=1, max_attempts=1, budget=6, holdout_ratio=0.3, holdout_sample_size=1,
        cache_dir=str(tmp_path / "cache"),
    )
    # cost_per_trial = max_examples(1) + holdout_sample_size(1) = 2;
    # n_trials = (6-1)//2 = 2 -- would be (6-1)//(1+3)=1 without the cap.
    assert result.candidates_tried == 2


def test_bayesian_search_resume_continues_a_persisted_study(tmp_path):
    rows = [{"question": f"Q{i}"} for i in range(1, 5)]
    examples_path = str(_examples_file(tmp_path, rows))
    cache_dir = str(tmp_path / "cache")

    # 4 rows, holdout_ratio=0.5 -> demo_pool=2, holdout=2; cost_per_trial = 2+2 = 4.
    # First run: budget=5 -> (5-1)//4 = 1 trial: meta(1) + bootstrap(2) + holdout(2) = 5 calls.
    client1 = StubClient([json.dumps([]), ">>> answer\nA", ">>> answer\nB", ">>> answer\nC", ">>> answer\nD"])
    first = craft(
        "resumable", "question -> answer", examples_path, "is correct",
        model="openai:gpt-4o-mini", judge=StubJudge(default=True), client=client1,
        max_examples=2, max_attempts=1, budget=5, holdout_ratio=0.5,
        resume=True, cache_dir=cache_dir,
    )
    assert first.candidates_tried == 1

    study_path = Path(cache_dir) / "prompts" / "resumable.study.sqlite3"
    assert study_path.is_file()

    # Second run, same name, bigger budget=9 -> wants (9-1)//4=2 trials total;
    # 1 already recorded, so only 1 more should run: meta(1) + bootstrap(2) + holdout(2) = 5 calls.
    client2 = StubClient([json.dumps([]), ">>> answer\nA", ">>> answer\nB", ">>> answer\nC", ">>> answer\nD"])
    second = craft(
        "resumable", "question -> answer", examples_path, "is correct",
        model="openai:gpt-4o-mini", judge=StubJudge(default=True), client=client2,
        max_examples=2, max_attempts=1, budget=9, holdout_ratio=0.5,
        resume=True, cache_dir=cache_dir,
    )
    assert second.candidates_tried == 2
    assert len(client2.calls) == 5  # only the 1 new trial's calls, not both trials' worth


def test_craft_raises_on_empty_examples_file(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    with pytest.raises(CraftError, match="no examples"):
        craft(
            "empty", "question -> answer", str(path), "is correct",
            model="openai:gpt-4o-mini", judge=StubJudge(), client=StubClient([]),
            cache_dir=str(tmp_path / "cache"),
        )

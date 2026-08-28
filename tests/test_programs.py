"""`ghostrun.craft.programs` -- composed Modules: RAG (retrieval + answer)
and Agent (ReAct tool loop). Fully offline via a scripted fake client."""

import json

import pytest

from ghostrun.craft import RAG, Agent, ChainOfThought, Prediction, Signature, Tool
from ghostrun.craft.errors import CraftError, ParseError


class ScriptedClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, system, messages, temperature=0.0):
        self.calls.append((system, messages, temperature))
        return self.replies.pop(0)


# --- RAG --------------------------------------------------------------


def test_rag_folds_retrieved_passages_into_context():
    seen_queries = []

    def retriever(query, k):
        seen_queries.append((query, k))
        return [f"passage {i} about {query}" for i in range(k)]

    rag = RAG(Signature.parse("question -> answer"), retriever, k=2)
    client = ScriptedClient([">>> answer\nParis"])

    prediction = rag.forward(client, question="Capital of France?")

    assert prediction == {"answer": "Paris"}
    assert seen_queries == [("Capital of France?", 2)]
    # the context field, built from the retrieved passages, reached the model
    sent_content = " ".join(m["content"] for m in client.calls[0][1])
    assert "passage 0 about Capital of France?" in sent_content
    assert "passage 1 about Capital of France?" in sent_content


def test_rag_uses_first_input_field_as_the_query():
    def retriever(query, k):
        return [query]

    rag = RAG(Signature.parse("question, locale -> answer"), retriever, k=1)
    client = ScriptedClient([">>> answer\nA"])
    rag.forward(client, question="Q", locale="en-US")
    # locale should NOT have been used as the retrieval query
    sent_content = " ".join(m["content"] for m in client.calls[0][1])
    assert "Q" in sent_content


def test_rag_with_reasoning_uses_chain_of_thought():
    rag = RAG(Signature.parse("question -> answer"), lambda q, k: ["p"], reasoning=True)
    assert isinstance(rag.answer_module, ChainOfThought)
    assert "reasoning" in [f.name for f in rag.answer_module.signature.outputs]


def test_rag_passes_demos_through_to_answer_module():
    rag = RAG(Signature.parse("question -> answer"), lambda q, k: ["p"])
    rag.demos = [{"question": "Q1", "context": "c", "answer": "A1"}]
    client = ScriptedClient([">>> answer\nA2"])
    rag.forward(client, question="Q2")
    assert rag.answer_module.demos == rag.demos


def test_rag_rejects_signature_without_input_fields():
    # Signature.parse() itself enforces >=1 input field, so build the
    # zero-input signature directly to exercise RAG's own guard.
    outputs = Signature.parse("question -> answer").outputs
    empty_input_signature = Signature(raw="answer", inputs=[], outputs=outputs)
    with pytest.raises(CraftError, match="at least one input field"):
        RAG(empty_input_signature, lambda q, k: [])


# --- Agent --------------------------------------------------------------


def test_agent_calls_a_tool_then_finishes():
    calls = []

    def search(arg):
        calls.append(arg)
        return "Paris is the capital of France."

    tool = Tool(name="search", func=search, description="search the web")
    agent = Agent(Signature.parse("question -> answer"), tools=[tool], max_steps=3)
    client = ScriptedClient([
        ">>> thought\nI should search.\n>>> action\nsearch\n>>> action_input\nCapital of France",
        ">>> thought\nI know now.\n>>> action\nfinish\n>>> action_input\nParis",
    ])

    prediction = agent.forward(client, question="Capital of France?")

    assert prediction == {"answer": "Paris"}
    assert calls == ["Capital of France"]
    assert len(client.calls) == 2
    # the scratchpad from step 1 should reach step 2 as an input
    step2_content = " ".join(m["content"] for m in client.calls[1][1])
    assert "Observation: Paris is the capital of France." in step2_content


def test_agent_finishes_immediately_without_calling_a_tool():
    agent = Agent(Signature.parse("question -> answer"), tools=[], max_steps=3)
    client = ScriptedClient([">>> thought\nEasy.\n>>> action\nfinish\n>>> action_input\nParis"])
    prediction = agent.forward(client, question="Capital of France?")
    assert prediction == {"answer": "Paris"}


def test_agent_handles_unknown_action_gracefully():
    agent = Agent(Signature.parse("question -> answer"), tools=[], max_steps=2)
    client = ScriptedClient([
        ">>> thought\nOops.\n>>> action\nnonexistent_tool\n>>> action_input\nx",
        ">>> thought\nGiving up gracefully.\n>>> action\nfinish\n>>> action_input\nParis",
    ])
    prediction = agent.forward(client, question="Q")
    assert prediction == {"answer": "Paris"}
    step2_content = " ".join(m["content"] for m in client.calls[1][1])
    assert "Unknown tool" in step2_content


def test_agent_tool_exception_becomes_an_observation_not_a_crash():
    def boom(arg):
        raise RuntimeError("tool broke")

    agent = Agent(Signature.parse("question -> answer"), tools=[Tool("boom", boom)], max_steps=2)
    client = ScriptedClient([
        ">>> thought\nTry it.\n>>> action\nboom\n>>> action_input\nx",
        ">>> thought\nOk.\n>>> action\nfinish\n>>> action_input\nDone",
    ])
    prediction = agent.forward(client, question="Q")
    assert prediction == {"answer": "Done"}
    step2_content = " ".join(m["content"] for m in client.calls[1][1])
    assert "Tool error: tool broke" in step2_content


def test_agent_raises_after_max_steps_without_finishing():
    agent = Agent(Signature.parse("question -> answer"), tools=[], max_steps=2)
    # Never emits "finish", so max_steps has to bite.
    client = ScriptedClient([
        ">>> thought\nHmm.\n>>> action\nnope\n>>> action_input\nx",
        ">>> thought\nStill going.\n>>> action\nnope\n>>> action_input\nx",
    ])
    with pytest.raises(CraftError, match="did not finish within 2 steps"):
        agent.forward(client, question="Q")


def test_agent_multi_field_finish_requires_json():
    agent = Agent(Signature.parse("question -> answer, confidence: float"), tools=[], max_steps=1)
    client = ScriptedClient([
        ">>> thought\nDone.\n>>> action\nfinish\n>>> action_input\nnot json",
    ])
    with pytest.raises(ParseError, match="JSON object"):
        agent.forward(client, question="Q")


def test_agent_multi_field_finish_parses_json():
    agent = Agent(Signature.parse("question -> answer, confidence: float"), tools=[], max_steps=1)
    payload = json.dumps({"answer": "Paris", "confidence": 0.9})
    client = ScriptedClient([
        f">>> thought\nDone.\n>>> action\nfinish\n>>> action_input\n{payload}",
    ])
    prediction = agent.forward(client, question="Q")
    assert prediction == {"answer": "Paris", "confidence": 0.9}


def test_agent_instructions_list_tool_descriptions():
    tool = Tool(name="search", func=lambda x: x, description="looks things up")
    agent = Agent(Signature.parse("question -> answer"), tools=[tool])
    assert "search: looks things up" in agent._step_signature.instructions

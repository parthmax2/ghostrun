"""Template: Retrieval-Augmented Generation (RAG) Evaluation with GhostRun.

Tests that generated answers are grounded in provided context passages and do not hallucinate.
"""

import ghostrun

def rag_pipeline(query: str, context: list[str]) -> str:
    """Mock RAG LLM call answering question using retrieved chunks."""
    return "GhostRun provides 0.04s deterministic test replays by caching HTTP LLM requests locally."

@ghostrun.record(model="gpt-4o-mini")
def test_rag_faithfulness_and_hallucination():
    context = [
        "GhostRun caches HTTP requests locally in .ghostrun_cache.",
        "Replay execution averages 0.04 seconds with zero API cost."
    ]
    query = "How fast does GhostRun replay tests?"
    answer = rag_pipeline(query, context)

    # 1. Check intent matches ground truth context
    ghostrun.expect(answer).contains_intent("0.04s replay speed")
    ghostrun.expect(answer).contains_intent("caching locally")

    # 2. Check no hallucinated pricing / subscription claims
    ghostrun.expect(answer).does_not_contain_intent("paid monthly subscription")

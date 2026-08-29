"""Template: Structured Entity Extractor using GhostRun.

Validates that LLM outputs adhere to valid JSON formatting and extract required fields deterministically.
"""

import json
import ghostrun

def extract_entities(user_text: str) -> dict:
    """Mock LLM call extracting name, organization, and action items."""
    # Replace with real OpenAI / Anthropic call under test
    return {
        "person": "Alex Smith",
        "organization": "Acme Corp",
        "action_item": "Schedule quarterly audit"
    }

@ghostrun.record(model="gpt-4o-mini")
def test_entity_extraction():
    data = extract_entities("Alex Smith from Acme Corp requested to schedule quarterly audit.")

    # 1. Deterministic structure checks
    assert isinstance(data, dict)
    assert data.get("person") == "Alex Smith"
    assert data.get("organization") == "Acme Corp"

    # 2. Semantic intent evaluation on extracted action items
    ghostrun.expect(data["action_item"]).contains_intent("schedule audit")

"""Tool/function-call assertions — where most agent bugs actually live."""

import json

import pytest

import ghostrun
from ghostrun.assertions import SemanticAssertionError

# The three shapes providers actually return.
OPENAI = [{"id": "1", "type": "function", "function": {
    "name": "search_orders", "arguments": json.dumps({"order_id": "A123"})}}]
ANTHROPIC = [{"type": "tool_use", "id": "1",
              "name": "search_orders", "input": {"order_id": "A123"}}]
PLAIN = [{"name": "search_orders", "arguments": {"order_id": "A123"}}]


@pytest.mark.parametrize("calls", [OPENAI, ANTHROPIC, PLAIN],
                         ids=["openai", "anthropic", "plain"])
def test_normalizes_provider_shapes(calls):
    ghostrun.expect_tool_calls(calls).called("search_orders") \
        .called_with("search_orders", order_id="A123")


def test_called_failure_lists_actual():
    with pytest.raises(SemanticAssertionError, match="issue_refund"):
        ghostrun.expect_tool_calls(OPENAI).called("issue_refund")


def test_did_not_call():
    ghostrun.expect_tool_calls(OPENAI).did_not_call("issue_refund")
    with pytest.raises(SemanticAssertionError):
        ghostrun.expect_tool_calls(OPENAI).did_not_call("search_orders")


def test_called_once():
    ghostrun.expect_tool_calls(PLAIN).called_once("search_orders")
    twice = PLAIN + PLAIN
    with pytest.raises(SemanticAssertionError, match="exactly once"):
        ghostrun.expect_tool_calls(twice).called_once("search_orders")


def test_call_count():
    ghostrun.expect_tool_calls(PLAIN).call_count(1)
    ghostrun.expect_tool_calls([]).call_count(0)
    with pytest.raises(SemanticAssertionError):
        ghostrun.expect_tool_calls(PLAIN).call_count(2)


def test_called_with_is_subset_match():
    calls = [{"name": "search", "arguments": {"q": "x", "limit": 10}}]
    ghostrun.expect_tool_calls(calls).called_with("search", q="x")  # ignores limit
    with pytest.raises(SemanticAssertionError):
        ghostrun.expect_tool_calls(calls).called_with("search", q="wrong")


def test_called_with_scans_all_matching_calls():
    calls = [{"name": "search", "arguments": {"q": "a"}},
             {"name": "search", "arguments": {"q": "b"}}]
    ghostrun.expect_tool_calls(calls).called_with("search", q="b")


def test_none_and_empty_are_zero_calls():
    assert len(ghostrun.expect_tool_calls(None)) == 0
    ghostrun.expect_tool_calls(None).did_not_call("anything").call_count(0)


def test_unparsable_arguments_do_not_crash():
    calls = [{"function": {"name": "f", "arguments": "not json{"}}]
    ghostrun.expect_tool_calls(calls).called("f")  # must not raise


def test_chaining():
    ghostrun.expect_tool_calls(OPENAI) \
        .called_once("search_orders") \
        .called_with("search_orders", order_id="A123") \
        .did_not_call("issue_refund") \
        .call_count(1)

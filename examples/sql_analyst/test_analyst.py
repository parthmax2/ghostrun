import os
import sys
import ghostrun

sys.path.insert(0, os.path.dirname(__file__))
from analyst_app import analyze_and_query

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".ghostrun_cache")

@ghostrun.record(model="gpt-4o-mini", cache_dir=CACHE_DIR)
def test_top_spenders_query_generation():
    result = analyze_and_query("Show me top 5 users who spent the most money on completed orders")
    
    # 1. Deterministic assertions
    assert "sql" in result
    sql = result["sql"].upper()
    assert "SELECT" in sql
    assert "USERS" in sql or "ORDERS" in sql
    assert "LIMIT 5" in sql or "TOP 5" in sql

    # 2. GhostRun Semantic Assertions (Checking safety and explanation intent)
    explanation = result["explanation"]
    ghostrun.expect(explanation).contains_intent("highest spending users")
    ghostrun.expect(explanation).does_not_contain_intent("deleting data")

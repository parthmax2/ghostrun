"""Generate pre-recorded offline cache fixtures for the demo AI app."""

import json
from pathlib import Path
from ghostrun.cache import Cache, CachedResponse
from analyst_app import SYSTEM_PROMPT, SCHEMA

def setup_cache():
    cache_dir = Path(__file__).parent / ".ghostrun_cache"
    cache = Cache(str(cache_dir))

    sql_output = {
        "sql": "SELECT users.id, users.name, SUM(orders.amount) AS total_spent FROM users JOIN orders ON users.id = orders.user_id WHERE orders.status = 'completed' GROUP BY users.id, users.name ORDER BY total_spent DESC LIMIT 5;",
        "explanation": "This query calculates total spending per user for completed orders and returns the top 5 highest spending users."
    }

    response_body = {
        "id": "chatcmpl-demo-analyst",
        "object": "chat.completion",
        "created": 1720000000,
        "model": "gpt-4o-mini",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": json.dumps(sql_output)
            },
            "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens": 60, "completion_tokens": 50, "total_tokens": 110}
    }

    question = "Show me top 5 users who spent the most money on completed orders"
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Schema:\n{SCHEMA}\n\nQuestion: {question}"}
        ],
        "temperature": 0.0,
    }

    body_bytes = json.dumps(payload).encode("utf-8")
    resp_bytes = json.dumps(response_body).encode("utf-8")

    from ghostrun.cache import request_key
    key = request_key("POST", "https://api.openai.com/v1/chat/completions", body_bytes)

    cached_resp = CachedResponse(
        status_code=200,
        headers={"content-type": "application/json"},
        body=resp_bytes,
    )

    cache.put(key, "POST", "https://api.openai.com/v1/chat/completions", body_bytes, cached_resp)
    print(f"[OK] Saved ghostrun replay fixture: {key}.json")

if __name__ == "__main__":
    setup_cache()

"""Real-world AI Application: Smart SQL & Data Analyst Agent.

Converts natural language user questions into safe, structured SQL queries and explanations.
"""

from __future__ import annotations

import os
import json
import httpx

OPENAI_URL = "https://api.openai.com/v1/chat/completions"

SYSTEM_PROMPT = """You are an expert Data Analyst AI. 
Given a database schema and a user question, write a safe, read-only SELECT query and a 1-sentence explanation.
Never generate DROP, DELETE, UPDATE, or INSERT queries.
Format your output as valid JSON:
{
  "sql": "SELECT ...",
  "explanation": "..."
}"""

SCHEMA = """
Table: users (id INT, name TEXT, email TEXT, signup_date DATE)
Table: orders (id INT, user_id INT, amount FLOAT, status TEXT, created_at TIMESTAMP)
"""

def analyze_and_query(user_question: str, model: str = "gpt-4o-mini") -> dict:
    """Send natural language request to LLM and parse JSON query result."""
    api_key = os.environ.get("OPENAI_API_KEY", "sk-ghostrun-cached-key")
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Schema:\n{SCHEMA}\n\nQuestion: {user_question}"}
        ],
        "temperature": 0.0,
    }
    
    resp = httpx.post(
        OPENAI_URL,
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    resp.raise_for_status()
    raw_content = resp.json()["choices"][0]["message"]["content"]
    
    try:
        return json.loads(raw_content)
    except json.JSONDecodeError:
        return {"sql": "", "explanation": raw_content}

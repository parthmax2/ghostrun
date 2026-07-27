"""Example GenTest test — runs fully offline against a pre-recorded cache.

The `.gentest_cache/` directory next to this file already contains a recorded
response, so this test needs no API key and no network:

    pytest examples/test_support_reply.py

The semantic assertions are graded by a local Ollama model (default). If a real
judge isn't available (no Ollama, or GENTEST_JUDGE=echo), the test skips rather
than fails — see examples/conftest.py.

To re-record against the real OpenAI API instead:

    export OPENAI_API_KEY=sk-...
    pytest examples/test_support_reply.py --gentest-record
"""

import os

import gentest

from support_app import generate_reply

# Keep this example's cache next to the test file so it works regardless of the
# directory pytest is invoked from. In your own project you can omit cache_dir
# and GenTest uses .gentest_cache at the project root.
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".gentest_cache")


@gentest.record(model="gpt-4o-mini", cache_dir=CACHE_DIR)
def test_refund_reply_is_helpful_and_empathetic():
    reply = generate_reply("Where is my refund? It's been three weeks!")

    gentest.expect(reply).contains_intent("apology")
    gentest.expect(reply).contains_intent("refund")
    gentest.expect(reply).does_not_contain_intent("blaming the customer")
    gentest.expect(reply).tone_is("empathetic")

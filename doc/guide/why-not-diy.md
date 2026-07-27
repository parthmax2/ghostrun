# Why not just ask an LLM to write this?

Fair question — a caching decorator sounds like a five-minute prompt. Here's
what actually happened when this project tried to build one carefully, found
by its own test suite, not hypothetically:

- **A quick version is not thread-safe, and the failure is silent.** The first
  implementation here made interceptor state process-global. Under
  `pytest -n` (parallel test workers), whichever thread installed last silently
  captured *every other thread's* traffic — tests recorded into each other's
  cache directories with no error, no warning, just wrong results on some runs
  and not others. A generated one-off script almost certainly won't hit this in
  the five minutes you spend testing it, and will hit it the first time your
  CI runs tests in parallel.
- **Concurrent cache writes corrupt each other.** Writing a JSON cache file
  in-place lets a parallel reader observe a half-written file and crash with a
  cryptic `JSONDecodeError` that looks like a bug in your own code, not the
  caching layer. Fixed here with atomic temp-file-plus-rename; easy to fix once
  you know to look for it, easy to ship without ever finding it.
- **Naive secret redaction breaks your cache.** The obvious regex for
  `*token*` also matches `max_tokens`, silently corrupting every recorded
  request body you'd want to read back. Getting this right needs an explicit
  safe-list, not just a keyword blocklist.
- **A cache key of just the URL isn't enough.** It needs the normalized
  request body too, or two different prompts silently share one cached
  response.
- **Majority-vote judge caching doesn't do what it sounds like it does.**
  Benchmarked against a real judge (90 live grades, not assumed): on a
  genuinely ambiguous grading case, voting barely helped and *wasn't even
  monotonic* — 3 votes outperformed 5. A generated script implementing "vote 5
  times and take the majority" would ship believing it fixed a problem it only
  partially addressed — see [the full writeup](../judge-voting-benchmark.md).
- **Rendering a diff report for a Windows console can crash on ordinary
  punctuation.** An arrow (`→`), a middle dot (`·`), and an em-dash (`—`) in a
  markdown report are all invisible in testing on Linux CI, and all crash
  `print()` on a default Windows terminal encoding. Caught here by actually
  running the command, not just asserting on its return value.

None of these are exotic. They're the ordinary edge cases that separate code
that passes a first read-through from code that's actually been run under
concurrency, redaction review, cross-platform consoles, and a real
non-deterministic judge. That's the difference between a prompt and a
maintained package: someone already hit these, wrote a test that fails without
the fix, and the fix ships to you.

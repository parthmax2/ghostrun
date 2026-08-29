# Troubleshooting & Debugging Guide

Common questions, gotchas, and solutions when working with GhostRun.

---

## 1. "My CI build is failing on missing cache entries"

### Cause:
By default, `--ghostrun-replay` in CI enforces that **no live network calls** are made. If a developer modified a prompt or added a new test without committing the corresponding `.ghostrun_cache/` fixtures, the replay engine flags a cache miss.

### Solution:
Run the recording run locally with your API key before committing:
```bash
pytest --ghostrun-record
git add .ghostrun_cache/
git commit -m "Update prompt fixtures"
```

---

## 2. "How do I switch judge models from Ollama to OpenAI?"

In your `.ghostrun.yaml`:
```yaml
judge:
  type: "ollama"           # or "echo" for fast offline literal checks
  model: "llama3.2:3b"
  base_url: "http://localhost:11434"
  timeout: 60.0
```

Or configure dynamically in code:
```python
import ghostrun

ghostrun.configure(judge="echo")
```

---

## 3. "How do I run tests completely offline without touching the network?"

Use the `--ghostrun-replay` pytest flag or set the mode in `.ghostrun.yaml`:

```bash
pytest --ghostrun-replay
```

If any test attempts an uncached network call, GhostRun will immediately fail with `CacheMiss` instead of silently spending API credits.

---

## 4. "How do I silence the mascot in automated pipelines?"

Set the environment variable in your CI container:
```bash
export GHOSTRUN_NO_PET=1
export GHOSTRUN_NO_MASCOT=1
```
*(GhostRun already detects GitHub Actions and CI environments automatically).*

# Configuration

Drop a `.ghostrun.yaml` at your project root (see the
[sample file](https://github.com/parthmax2/ghostrun/blob/main/.ghostrun.yaml) in
the repo, or generate one with `ghostrun init`):

```yaml
mode: auto
cache_dir: .ghostrun_cache
judge:
  type: ollama          # or "echo" for an offline heuristic stub
  model: llama3.2:3b
  base_url: http://localhost:11434
  timeout: 60
  votes: 1
  cache: true
```

Everything is overridable by environment variable (`ghostrun_MODE`,
`ghostrun_JUDGE`, `ghostrun_JUDGE_MODEL`, `ghostrun_CACHE_DIR`, `ghostrun_JUDGE_VOTES`,
…) or at runtime via `ghostrun.configure(judge="echo")`. Resolution order:
defaults → `.ghostrun.yaml` → environment variables → `ghostrun.configure(...)`.

Want a cloud judge instead of local? Point the judge at any Ollama-compatible
endpoint, or set `judge: echo` for CI runs that shouldn't depend on a model.

## Pytest flags

Installed as a pytest plugin automatically:

```bash
pytest --ghostrun-record      # re-record fixtures this run
pytest --ghostrun-replay      # replay only; fail on cache miss (CI)
pytest --ghostrun-judge echo  # override the judge backend
pytest --ghostrun-snapshot v1 --ghostrun-label "..."   # save a run snapshot for diffing
```

## Diagnosing a broken setup: `ghostrun doctor`

ghostrun has a few moving parts — cache directory, judge backend, Ollama
reachability, httpx compatibility. If something isn't working, run:

```bash
ghostrun doctor
```

It checks, in order: the resolved configuration, whether the cache directory
exists and is writable, whether the installed httpx version exposes the hook
ghostrun's interceptor needs, and — if the judge backend is `ollama` — whether
the Ollama daemon is reachable and the configured model is actually pulled.
Each failing check prints the specific command to fix it (e.g.
`ollama pull llama3.2:3b`) rather than a stack trace.

## Privacy

By default nothing leaves your machine: LLM responses are cached locally and
grading runs on a local Ollama model. That's the whole design — testing GenAI
under SOC2/HIPAA constraints without shipping prompts to a third party.

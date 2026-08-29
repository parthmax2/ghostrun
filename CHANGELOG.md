# Changelog

All notable changes to ghostrun are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [2.0.5] - 2026-08-29

### Added
- **`ghostrun craft`** — Bayesian prompt optimization & typed signature system (`"inputs -> outputs"`). Automatically discovers high-performing instruction candidates and bootstraps few-shot demonstrations against semantic metric assertions.
- **`@ghostrun.craft.optimize` Decorator** — Auto-tunes application prompts during standard `pytest` runs using Bayesian Search with Optuna.
- **`ghostrun.craft.Signature` & `Predict` Modules** — Declare typed LLM interfaces natively without complex framework dependencies.
- **Comprehensive API Reference & SEO Metadata** for prompt optimization and prompt engineering workflows.
- **Interactive Tactical Desktop Mascot (`ghostrun pet`)** — Transparent, borderless floating companion with 9 real-time animations (`idle`, `running`, `jumping`, `waving`, `review`, `waiting`, `failed`, `thinking`), per-animation frame timings, and screen edge walking locomotion.
- **Native Test Runner (`ghostrun run`)** — Forwarding CLI test runner that automatically executes tests and triggers celebratory victory animations upon 0.04s cache replays.
- **Live Interactive Web Mascot** on documentation site (`ghostrun.parthmax.tech`) hero section.
- **Comprehensive API Reference & SEO Metadata** for DSPy alternatives and prompt engineering keywords.

### Fixed
- Fixed CI matrix dependencies for `pydantic>=2.0`, `litellm>=1.0.0`, `optuna>=3.0.0`, and `pillow>=9.0.0`.
- Fixed PyPI broken relative image references to raw GitHub asset URLs.
- Fixed Tcl/Tkinter memory deallocation race on companion dismissal.
- Domain migration to `ghostrun.parthmax.tech`.

## [0.1.1] - 2026-07-28

### Added
- **Terminal mascot** — a one-line marker printed once at the end of a test
  session, reacting to what the interceptor actually did: calm (`☆ 👻 ☆`,
  cyan) when every call replayed from cache, alert (yellow) when the network
  was actually touched, and a distinct miss face (red) when
  `--ghostrun-replay` hit an uncached request. Falls back to a plain ASCII
  face (`(o o)` / `(O O)` / `(x x)`) on terminals/codepages that can't render
  the emoji. Silent on CI/piped output and `NO_COLOR`, and always
  silenceable via `GHOSTRUN_NO_MASCOT=1`.

### Fixed
- Judge verdict caching ignored a per-test `cache_dir` override passed to
  `@ghostrun.record()`, so verdicts silently leaked into the global cache dir
  instead of living next to the test as documented — the root cause of every
  CI matrix job failing on `--ghostrun-replay`. `recording()` now scopes
  `cache_dir`/`mode` onto the active config for the run.
- `GHOSTRUN_*` environment variables were misnamed `ghostrun_*` (lowercase
  prefix) across the codebase, docs, and CI following the gentest→ghostrun
  rename.
- **`ghostrun init`** — scaffolds a working first test in one command. Detects
  whether `openai` or `anthropic` is importable in the project and generates
  a matching starter test (or a generic httpx-based one if neither is found),
  plus a `.ghostrun.yaml`. Refuses to overwrite existing files without
  `--force`. Verified end-to-end from an actual built wheel in a clean venv,
  including the no-SDK fallback path.
- **Real git history.** Initialized the repository (`git init` + first commit)
  — previously all work in this project existed only as an uncommitted
  working directory.
- **PEP 561 typing marker** (`ghostrun/py.typed`) — the `Typing :: Typed`
  classifier was added to `pyproject.toml` without this; a classifier
  asserting something the package doesn't actually declare would have been a
  false claim, caught before publishing rather than after.
- **`llms.txt`** at the repo root, following the emerging llms.txt convention
  for LLM-crawler-readable project summaries, linking to every doc page.
- **Hosted documentation site** (`mkdocs.yml` + `.github/workflows/docs.yml`,
  mkdocs-material, deploys to GitHub Pages on push to `main`). Verified with a
  real `mkdocs build --strict` locally, which caught a broken link
  (`configuration.md` pointed at `.ghostrun.yaml` via a relative path outside
  the site's `docs_dir`) before it could ship.
- **`CONTRIBUTING.md`** — setup, test requirements (including the parallel-run
  requirement that has caught two real concurrency bugs in this project),
  and where things live in the codebase.
- **API reference** (`doc/guide/api-reference.md`) — every function, class,
  exception, and config field in `ghostrun.__all__`.
- **PyPI/SEO metadata**: expanded `keywords` and `classifiers` in
  `pyproject.toml` for search discoverability, real project URLs (previously
  a placeholder `github.com/ghostrun/ghostrun`), and PyPI/license/Python-version/
  CI badges in the README.
- **`ghostrun doctor`** — diagnoses a broken setup in one command: resolved
  configuration, httpx interceptor-hook compatibility, cache-directory
  writability, and (for the Ollama judge) whether the daemon is reachable and
  the configured model is actually pulled. Each failing check prints the exact
  fix (e.g. `ollama pull llama3.2:3b`) instead of a stack trace. Backed by a
  new `OllamaJudge.is_available()` method, also now reused by the bundled
  example's skip-detection logic instead of a duplicated private helper.
- **Documentation restructure.** The README had grown to 407 lines covering
  install, six feature deep-dives, and a benchmark report in one linear
  scroll — with the "why not just ask an LLM" persuasion essay placed *before*
  Install and Quickstart, meaning a first-time visitor hit a defensive essay
  before seeing how to try the tool. Split into a short landing-page README
  (problem, install, quickstart, a documentation table of contents) plus
  `doc/guide/{recording,assertions,regression-tracking,configuration,
  why-not-diy}.md`. Also fixed a stale cross-reference: the majority-vote
  section linked to `doc/prd.md` for benchmark methodology when the dedicated
  write-up is `doc/judge-voting-benchmark.md`.
- **CI-friendly diff output.** `ghostrun diff --format github-comment` renders
  markdown suitable for posting as a pull-request comment (collapsible
  sections, a table of regressions, output-drift diffs); `--format junit`
  renders standard JUnit XML so a prompt regression shows up in whatever
  CI test-results view you already use, with no ghostrun-specific tooling on
  that end. `-o/--output FILE` writes either to a file instead of stdout. The
  existing `--json` flag keeps working as a shorthand for `--format json`.
  README documents a full GitHub Actions pattern for posting the comment via
  `gh pr comment`.
- **"Why not just ask an LLM to write this?"** README section — the concrete
  bugs found and fixed in ghostrun's own development (thread-safety races,
  torn cache writes, a secret-redaction false positive on `max_tokens`, the
  majority-vote tie-breaking edge case) as the actual case for a maintained
  package over a one-off generated script.
- `doc/judge-voting-benchmark.md` — the majority-vote judge-caching benchmark
  write-up, publishable standalone.
- **Majority-vote judge caching (`judge.votes`).** A single cached verdict
  freezes whatever the judge said on one draw, including if it was wrong —
  published LLM-as-judge studies report ~13–14% flip rates on repeated grading
  of identical input, even at temperature 0. Setting `judge.votes` (or
  `GHOSTRUN_JUDGE_VOTES`) to an odd N > 1 grades N times on a cache miss and
  caches the majority verdict plus the observed disagreement rate
  (`Grade.votes`, `Grade.disagreement_rate`). Even vote counts tie-break
  conservatively to FAIL. Cache keys now include the vote count, so changing
  `votes` correctly invalidates old single-draw entries rather than silently
  reusing them. Default remains `votes: 1`, byte-identical to prior behavior.
  **Benchmarked against the real judge (90 live grades):** 5/6 test conditions
  showed 0% flip rate at temperature 0 (single draws already stable); the one
  genuinely ambiguous case (sarcasm at temperature 0.7) flipped 46.7% of the
  time, and majority voting only marginally/non-monotonically improved
  reliability there (k=1: 49.6%, k=3: 55.8%, k=5: 51.8%) — voting is a better
  *detector* of unreliable criteria (via `disagreement_rate`) than a *fix* for
  them. Full methodology and numbers in `doc/judge-voting-benchmark.md`.
- **Prompt regression tracking (PRD Phase 2, Feature 4).** Runs now snapshot the
  text every assertion saw plus each verdict, so two prompt versions can be
  compared:
  - `pytest --ghostrun-snapshot NAME [--ghostrun-label TEXT]` saves a snapshot;
    every run also refreshes `_last`.
  - New `ghostrun` CLI: `list`, `show`, `diff`, with `--json` and
    `--fail-on-regression` (exit 1) for CI gating.
  - Classifies each assertion as regression / fix / stable / added / removed,
    and reports **output drift** separately — responses that changed while still
    passing, with a similarity ratio and unified diff.
  - Assertions skipped because a test aborted earlier are reported as
    *not evaluated* rather than *removed*, so one failure doesn't look like
    several deletions.
- **Judge verdict caching.** Semantic assertions previously re-invoked the judge
  model on every run, leaving suites slow and non-deterministic — a stochastic
  judge could flip a passing test with no code change. Verdicts are now recorded
  to `.ghostrun_cache/judge/` under the same `auto`/`record`/`replay` semantics as
  HTTP calls, keyed on judge backend + model + text + criterion. Configurable via
  `judge.cache` or `GHOSTRUN_JUDGE_CACHE`. Cuts the bundled example from 23.3s to
  2.7s and makes semantic assertions deterministic.
- Committed tests for async clients and streaming (SSE) record/replay, including
  async streaming — previously working but uncovered.

- **Secret redaction.** The cache is meant to be committed, so credentials are
  now scrubbed before anything hits disk: response auth/cookie headers, and
  secret-looking body keys plus `sk-…`/`ghp_…`/`AKIA…` patterns in free text.
  Benign lookalikes (`max_tokens`, `total_tokens`) are explicitly preserved.
  Response bodies stay verbatim by design — they're what gets replayed.
- **Tool/function-call assertions** via `ghostrun.expect_tool_calls(...)`:
  `called`, `did_not_call`, `called_once`, `call_count`, `called_with` (subset
  match). Normalizes OpenAI, Anthropic, and plain tool-call shapes.
- **Provider coverage** extended from 3 to 16 hosts (Gemini, Vertex, Bedrock,
  Mistral, Cohere, OpenRouter, Groq, Together, Fireworks, DeepSeek, xAI,
  Perplexity). `PROVIDER_HOSTS` is extensible for self-hosted gateways.
- **GitHub Actions CI**: 15-way OS × Python matrix (3.9–3.13 on Linux/macOS/
  Windows), an xdist parallel-safety job, and a build job that verifies the
  wheel installs in a clean venv.
- `UnsupportedHttpx` is raised eagerly if httpx ever drops the private
  `_transport_for_url` hook, instead of tests silently hitting the network.
- MIT `LICENSE` file (previously declared in `pyproject.toml` with no file).

### Fixed
- **Concurrent interceptors wrote into each other's caches.** Active state was
  process-global, so with multiple threads whichever installed last captured
  everyone's traffic. State is now per-thread with a global fallback for threads
  that never installed one.
- **Torn cache reads under parallelism.** Writes were in-place, letting a reader
  observe a half-written file (`JSONDecodeError`). Writes are now atomic via a
  unique temp file + `os.replace`.
- Out-of-order `uninstall()` could unbind another interceptor's state; each now
  removes its own stack frame.

### Changed
- `CacheMiss` now lives in `ghostrun.cache` and covers both HTTP and judge-verdict
  misses. Still importable from `ghostrun` and `ghostrun.interceptor`.
- The example's judge-availability guard no longer probes Ollama in `replay`
  mode, where no model is invoked.

## [0.1.0] — 2026-07-24

Initial Phase 1 MVP.

### Added
- **Deterministic record/replay** via `@ghostrun.record` and the
  `ghostrun.recording()` context manager. Intercepts LLM HTTP traffic at the
  httpx transport layer (covers the OpenAI and Anthropic SDKs) and caches
  responses to `.ghostrun_cache/`. Modes: `auto`, `record`, `replay`.
- **Semantic assertions** via `ghostrun.expect(text)`:
  `contains_intent`, `does_not_contain_intent`, `tone_is`, `matches`, plus
  deterministic `contains`, `does_not_contain`, `is_valid_json`. All chainable.
- **LLM-as-a-judge backends**: local `ollama` (default, private) with actionable
  errors when the daemon or model is missing, and an offline `echo` heuristic
  stub for CI.
- **Pytest plugin** (auto-registered): `--ghostrun-record`, `--ghostrun-replay`,
  `--ghostrun-judge` flags and a `ghostrun_record` fixture.
- **Configuration** via `.ghostrun.yaml`, `GHOSTRUN_*` environment variables, or
  `ghostrun.configure(...)`, resolved defaults → file → env.
- Documentation (`README.md`, `doc/prd.md`), a runnable `examples/` app with a
  pre-recorded cache, and an offline test suite.

### Notes
- The assertion entry point is `ghostrun.expect(...)`, not `ghostrun.assert(...)`
  — `assert` is a reserved Python keyword and cannot be a function name.

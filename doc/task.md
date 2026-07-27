# GenTest — Task Tracker

Living status document. **Update this whenever a task changes state** — same
commit as the work itself, not afterwards.

**Last updated:** 2026-07-24
**Current version:** 0.1.0 (unreleased)
**Test status:** 138 core tests passing, green under `pytest -n 4` (139 incl. examples) · [see verification](#verification-matrix)
**Repo status:** git initialized, first commit made. Remote is **not yet
pushed** — `git init` and a local commit only; add a remote and `git push`
yourself when ready.
**Docs status:** README is a landing page; deep-dives live in `doc/guide/`
(recording, assertions, regression-tracking, configuration, api-reference,
why-not-diy). Hosted docs site is configured (`mkdocs.yml` +
`.github/workflows/docs.yml`, builds clean under `mkdocs build --strict`) but
**not yet live** — GitHub Pages needs the repo pushed and its Pages source set
to "GitHub Actions" in repo settings (one-time, manual, needs repo admin
access this session doesn't have). `llms.txt` added at the repo root.
**Package status:** builds clean, `twine check` PASSED, verified working
install (import + `gentest` console script + pytest plugin auto-registration,
including `gentest init`'s no-SDK fallback) in a fresh venv from the built
wheel — **publish-ready, blocked only on your PyPI account/token**
**See also:** [`comparison.md`](comparison.md) — live competitive research vs. DeepEval, Promptfoo, Ragas, vcr-langchain, and others

---

## Status at a glance

| Track | Done | Status |
| :--- | ---: | :--- |
| **Phase 1 — MVP (open-source core)** | **100%** | ✅ Complete, exceeds original spec |
| **Launch readiness** (ship to PyPI + HN) | **~80%** | 🟢 Engineering done; release + GTM remain |
| **Phase 2 — Feature 4 (regression tracking)** | **100%** | ✅ Complete |
| **Phase 2 — Feature 5 (cloud dashboard)** | **0%** | ⬜ Blocked on positioning decision |
| **Overall vs. full PRD** | **~75%** | 🟢 |

> The honest read: all *code* on the critical path is done and tested — secret
> redaction, thread/xdist safety, provider breadth, tool-call assertions, CI.
> What remains needs either a human decision (positioning), credentials (PyPI),
> or real infrastructure (Phase 2 dashboard).

---

## 1. Phase 1 — MVP ✅ COMPLETE

### Feature 1: Deterministic replay
- [x] Intercept LLM API calls (OpenAI, Anthropic)
- [x] Save request payload + response to `.gentest_cache/`
- [x] Return cached response on subsequent runs
- [x] HTTP-transport interception (not SDK monkey-patching)
- [x] `auto` / `record` / `replay` modes
- [x] Stable cache keys (JSON-normalized, sorted)
- [x] Async client support — *tested*
- [x] Streaming (SSE) support, sync + async — *tested*

### Feature 2: Semantic assertions
- [x] `contains_intent()` / `does_not_contain_intent()`
- [x] `tone_is()` / `matches()` (free-form escape hatch)
- [x] `is_valid_json()`, `contains()`, `does_not_contain()`
- [x] Local Ollama judge as default (zero cost, private)
- [x] Configurable judge via `.gentest.yaml` / env / `configure()`
- [x] Actionable errors when daemon down or model unpulled
- [x] Offline `echo` stub judge for CI plumbing
- [x] **Judge verdict caching** — *beyond original PRD; see §5*
- [x] **Majority-vote judge caching** (`judge.votes`) — grade N times on a cache
      miss, cache the majority + disagreement rate. Reasoning: DeepEval already
      ships single-verdict caching, so that alone isn't a differentiator; this
      addresses a gap neither DeepEval nor the LLM-judge reliability literature
      answers — see [comparison.md](comparison.md) and the benchmark below

### Feature 3: Native pytest integration
- [x] Standard pytest output, no custom CLI
- [x] Auto-registered plugin (`pytest11` entry point)
- [x] `--gentest-record` / `--gentest-replay` / `--gentest-judge` flags
- [x] `gentest_record` fixture

### Documentation & examples
- [x] `README.md`, `doc/prd.md`, `CHANGELOG.md`
- [x] Sample `.gentest.yaml`, `.gitignore`
- [x] Runnable `examples/` app with pre-recorded cache
- [x] Graceful skip when no semantic judge available

---

## 2. Launch readiness 🟢 ~80%

### Packaging & CI
- [x] **GitHub Actions CI** — 3.9–3.13 × Linux/macOS/Windows (15 jobs), plus an
      xdist parallel-safety job and a build job that installs the wheel into a
      clean venv and imports it. Added 2026-07-24.
- [x] LICENSE file — MIT (was declared in `pyproject.toml` with no file present)
- [x] Python 3.9 syntax compatibility verified via AST check
- [ ] **Publish to TestPyPI, then PyPI** — needs your account + API token
- [ ] Tag `v0.1.0`, GitHub release
- [ ] Confirm the CI matrix actually goes green once pushed (**still only ever
      executed on Windows locally** — CI is written but unproven)

### Correctness hardening
- [x] **Secret redaction in cache files** — response auth/cookie headers, secret
      body keys, and `sk-`/`ghp_`/`AKIA` patterns in free text. `max_tokens` and
      friends explicitly preserved. Response bodies verbatim by design.
- [x] **Thread/xdist safety** — per-thread interceptor state + atomic cache
      writes. Verified green under `pytest -n 4`.
- [x] Broaden provider coverage — 3 → 16 hosts, `PROVIDER_HOSTS` extensible
- [x] Guard the private `_transport_for_url` patch — raises `UnsupportedHttpx`
      eagerly rather than silently letting tests hit the network
- [x] Tool-call / function-calling assertions (`expect_tool_calls`)
- [ ] Cache invalidation & pruning strategy (stale entries grow unbounded)
- [ ] Replace the private-API patch with a supported httpx hook *(guarded, but
      still private API — a real fix needs upstream support)*

### Go-to-market
- [ ] 2-minute demo video (the record→replay "aha")
- [ ] **Sharpen the wedge** — see §4. Current pitch is aimed at the wrong competitor.
- [ ] Landing page / docs site
- [ ] HN "Show HN" post
- [ ] Reddit: r/LangChain, r/LocalLLaMA, r/Python
- [ ] Submit to Awesome-LLM lists
- [ ] Discord / community space

---

## 3. Phase 2 — V1.1 & monetization 🟡 50%

### Feature 4: Prompt regression tracking ✅ COMPLETE
- [x] Diff cached outputs of prompt V1 vs V2 side by side (unified diff +
      similarity ratio)
- [x] Report semantic verdict deltas across runs (regression / fix / stable /
      added / removed / not-evaluated)
- [x] CLI surface: `gentest list | show | diff`, `--json`,
      `--fail-on-regression` for CI gating
- [x] Run snapshots via `pytest --gentest-snapshot NAME --gentest-label TEXT`;
      `_last` always written
- [x] Verified end-to-end on a simulated prompt regression

### Feature 5: Cloud dashboard (business model)
- [ ] Hosted dashboard for CI/CD results
- [ ] Eval scores tracked over time
- [ ] Team collaboration
- [ ] Freemium billing (free solo / paid teams)
- [ ] **Open question:** does this contradict the "zero SaaS lock-in" promise the
      whole project is marketed on? Needs a positioning answer before building.

---

## 4. Known risks — open

| Risk | Severity | Status |
| :--- | :--- | :--- |
| **Wrong competitor identified.** PRD targets LangSmith/Braintrust (SaaS). Real rivals are promptfoo, deepeval, Ragas, vcrpy — already open-source *and* local-first. The privacy wedge is not differentiating. | 🔴 High | **Open — blocks GTM, needs a human decision** |
| Phase 2 dashboard may contradict the "zero SaaS lock-in" promise | 🟡 Med | Open — resolve before building |
| Small local judge is an unreliable grader | 🟡 Med | ✅ Mitigated (configurable model + verdict caching pins results) |
| Private httpx API could break on upgrade | 🟡 Med | ✅ Mitigated (eager `UnsupportedHttpx` with actionable message) |
| Cache may contain secrets/PII | 🟡 Med | ✅ Mitigated (redaction on write; response bodies documented as verbatim) |
| Windows-only testing | 🟡 Med | 🟡 CI written for Linux/macOS/Windows — **unproven until pushed** |

**On the wedge:** the real differentiator is **DX and minimalism** — `@record` +
`expect()` is tighter than promptfoo's YAML config. The launch narrative should
lead with that, not privacy. Leading with privacy will get corrected in the HN
comments within an hour.

---

## 5. Notable deviations from the PRD

1. **`gentest.assert()` → `gentest.expect()`** — `assert` is a reserved Python
   keyword; the PRD's snippet was a `SyntaxError`.
2. **Judge verdict caching added** (not in PRD). Without it, semantic assertions
   re-invoked a stochastic model every run, reintroducing the exact
   non-determinism GenTest exists to eliminate. Measured: example 23.3s → 2.7s,
   and now passes with the judge endpoint unreachable.
3. **Interception at httpx transport layer**, satisfying the PRD's own
   "don't monkey-patch SDKs" constraint — though it does patch a *private* httpx
   method, which is logged as a risk above.

---

## Verification matrix

Last full run — all green:

| Scenario | Result |
| :--- | :--- |
| Core suite, isolated | 138 passed · ~2.3s |
| Core suite under `pytest -n 4` (xdist) | 138 passed |
| Prompt regression tracking, end-to-end | regression + drift correctly detected, exit 1 |
| Full repo incl. examples (live Ollama judge) | 139 passed, 2 skipped (live smoke, no API key) |
| Strict replay, judge endpoint **unreachable** | 1 passed · 0.45s |
| `GENTEST_JUDGE=echo` | passes, 1 skipped |
| Ollama down, auto mode | 1 skipped (not failed) · 4.41s |
| Python 3.9 syntax compatibility (AST) | clean |
| `gentest init` from an actual built wheel, clean venv | works, incl. no-SDK fallback path |
| `mkdocs build --strict` | clean (after fixing one broken relative link) |
| `python -m build` + `twine check` | PASSED, `py.typed` and `scaffold.py` confirmed in wheel |

---

## Developer-experience roadmap (from competitive research, see comparison.md)

Prioritized against 13 competing tools researched live (DeepEval, Promptfoo,
Ragas, vcr-langchain, langchain-replay, Giskard, Langfuse, Braintrust,
LangSmith, OpenAI Evals, Inspect AI, CacheSaver, pytest-recording/VCR.py).

**Tier 0 — blocking, needs the user:**
- [ ] Publish to PyPI — no developer can `pip install gentest` yet; every other
      item is moot until this exists. **Prep is done**: `python -m build`
      succeeds, `twine check dist/*` PASSED, and a clean venv install from the
      built wheel was verified to import correctly, register the pytest plugin
      (`pytest11` entry point), and expose the `gentest` console script. What
      remains is `twine upload` with your PyPI account/token — an irreversible
      public action intentionally left for you to run, not automated here.

**Tier 1 — closes gaps the comparison exposed, highest leverage:**
- [x] Majority-vote judge caching (`judge.votes`) — done this session, benchmarked
      against the real judge (90 live grades): 5/6 conditions were perfectly
      stable at temp=0; the one ambiguous case (sarcasm@0.7) flipped 46.7% of
      the time and voting only marginally helped (non-monotonically) —
      **honest finding: voting detects unreliable criteria via
      `disagreement_rate` better than it fixes them.** See prd.md §5B.
- [ ] Cache staleness warnings (`gentest stale --older-than`) — providers
      silently update models behind fixed names (documented: GPT-4 accuracy
      84%→51% between March/June 2023 with no version change); a cache entry
      has no age signal today
- [x] CI-friendly diff output (`gentest diff --format github-comment` /
      `junit`, `-o` to write a file) — done this session, README documents the
      full GitHub Actions `gh pr comment` pattern; a real Windows-console
      Unicode crash (arrow/middle-dot/em-dash in the rendered markdown) was
      found and fixed by actually printing the output, not just asserting on it
- [ ] Cost/savings reporting (`gentest stats`) — token usage already sits in
      every cached response; surface cache-hit-rate/$-saved/time-saved to make
      the adoption pitch a real number instead of a README claim
- [x] **`gentest doctor`** — diagnoses config/httpx/cache-dir/judge reachability
      in one command with actionable fixes, not stack traces. Done this session.
- [x] **`gentest init`** — scaffolds a working first test + `.gentest.yaml`,
      detecting the installed LLM SDK (openai/anthropic/generic fallback).
      Verified end-to-end from an actual built wheel in a clean venv, including
      the fallback path. Done this session.
- [x] **Documentation restructure** — README split into a landing page +
      `doc/guide/` deep-dives (incl. a new API reference); fixed a stale
      cross-link (majority-vote section pointed at the wrong file for
      benchmark methodology).
- [x] **Hosted docs site configured** — `mkdocs.yml` + mkdocs-material +
      `.github/workflows/docs.yml` deploying to GitHub Pages on push to
      `main`. Verified with a real `mkdocs build --strict` (caught and fixed a
      broken relative link before it could ship). **Not live yet** — needs the
      repo pushed and Pages source set to "GitHub Actions" in repo settings,
      a one-time manual step outside this session's access.
- [x] **`llms.txt`** at the repo root (emerging LLM-crawler convention) and
      expanded PyPI `keywords`/`classifiers`, real project URLs (was a
      placeholder `github.com/gentest/gentest`), README badges, PEP 561
      `py.typed` marker, and `CONTRIBUTING.md` — all for discoverability by
      search engines, LLM crawlers, and human contributors respectively.
- [x] **Git repository initialized** — first commit made locally. Not pushed
      to a remote yet.

**Tier 2 — metric breadth (DeepEval ships 50+, GenTest ships ~5):**
- [ ] RAG faithfulness assertion (most-requested RAG metric)
- [ ] Hallucination flag assertion
- Deliberately NOT chasing DeepEval's metric count — 2–3 purpose-built ones,
  not an arms race

**Tier 3 — agent-era gap (nothing in the comparison handles this well either):**
- [ ] Multi-turn/conversation-level assertions
      (`expect_conversation(turns).completed_task()`)

**Tier 4 — deliberately deferred:**
- Static HTML diff report, `requests`-library interception, multi-provider
  matrix testing (this is Promptfoo's identity — chasing it dilutes GenTest's),
  synthetic dataset generation

## Immediate next 3

1. **Push and confirm CI goes green** — the matrix is written but has never
   actually executed; Linux/macOS support is an assumption until it does
2. **Publish to TestPyPI then PyPI** — needs your account + API token
3. **Resolve the positioning question in §4** before writing any launch copy

---

## Changelog for this document

- **2026-07-24 (4)** — Git repository initialized (first local commit,
  no remote pushed yet). Added `gentest init`, `gentest doctor`,
  API reference, `llms.txt`, hosted-docs-site config (mkdocs-material +
  GitHub Pages workflow, verified with a real strict build), `CONTRIBUTING.md`,
  and SEO-relevant PyPI metadata (keywords, classifiers, real URLs, badges,
  `py.typed`). Restructured README into a landing page. Core tests 117 → 138.
  Two real bugs caught by actually running things rather than trusting the
  code: a Windows-console Unicode crash in the PR-comment renderer, and a
  broken relative link in the mkdocs build that only strict-mode caught.
- **2026-07-24 (3)** — Phase 2 Feature 4 (prompt regression tracking) complete:
  run snapshots, comparison engine, `gentest` CLI. Core tests 67 → 91. Two
  reporting bugs found and fixed by end-to-end use (tests recording nothing were
  invisible to the diff; assertions after an abort were mislabeled "removed").
  Overall 60% → 75%.
- **2026-07-24 (2)** — Launch-readiness engineering completed: CI matrix, secret
  redaction, thread/xdist safety, 16 providers, tool-call assertions, httpx
  guard. Core tests 32 → 67. Two real bugs found and fixed by the new tests
  (cross-thread cache contamination; torn reads under parallel writes).
  Launch readiness 35% → 80%.
- **2026-07-24** — Created. Phase 1 marked complete (32 core tests green).
  LICENSE added, ticked off. CI, redaction, and positioning identified as the
  critical path.

# Contributing to ghostrun

Thanks for considering it. This project is young and the codebase is small
enough to read in an afternoon — that's intentional; see
[doc/guide/why-not-diy.md](doc/guide/why-not-diy.md) for the philosophy.

## Setup

```bash
git clone https://github.com/parthmax2/ghostrun.git
cd ghostrun
pip install -e ".[dev]"
pytest            # 138 tests, runs fully offline in a couple of seconds
```

The core suite (`tests/`) never touches the network or requires Ollama — it
uses the `echo` judge stub. The bundled example (`examples/`) exercises the
real Ollama judge when available and skips gracefully otherwise.

## Before opening a PR

- `pytest tests -q` must pass.
- If you touch the interceptor, cache, or judge-caching logic, also run under
  parallel workers: `GHOSTRUN_JUDGE=echo pytest tests -q -n 4` — several real
  bugs in this project (cross-thread cache contamination, torn writes) were
  only found this way, not by the sequential suite.
- New behavior needs a test that fails without the fix. This project has
  found genuine bugs specifically by insisting on this (see the CHANGELOG and
  [doc/guide/why-not-diy.md](doc/guide/why-not-diy.md) for examples) —
  "I tested it manually" is not sufficient for anything touching concurrency,
  caching, or redaction.
- Update `CHANGELOG.md` under `[Unreleased]`.

## Where things live

| Area | File |
| :--- | :--- |
| HTTP record/replay | `ghostrun/interceptor.py`, `ghostrun/cache.py` |
| Semantic assertions | `ghostrun/assertions.py` |
| Judge backends | `ghostrun/judge/` |
| Secret redaction | `ghostrun/redact.py` |
| Prompt regression diffing | `ghostrun/regression.py`, `ghostrun/runlog.py` |
| CLI (`ghostrun list/show/diff/doctor/init`) | `ghostrun/cli.py`, `ghostrun/scaffold.py` |
| Pytest plugin/flags | `ghostrun/plugin.py` |
| Configuration | `ghostrun/config.py` |

## Reporting a bug

Open a GitHub issue with a minimal reproduction. If it involves the
interceptor or cache, please include whether it reproduces under
`pytest -n` (parallel workers) — that distinction has mattered for every
concurrency bug found in this project so far.

## Project philosophy (so PRs align with it)

- **Minimal, not comprehensive.** ghostrun deliberately ships ~5 semantic
  assertion types where DeepEval ships 50+ — see
  [doc/comparison.md](doc/comparison.md) for why breadth isn't the goal here.
- **Measure, don't assert.** Claims about judge accuracy or caching behavior
  in this project are backed by a benchmark against a real judge, not
  intuition — see [doc/judge-voting-benchmark.md](doc/judge-voting-benchmark.md)
  for the standard a new claim should meet.
- **Local-first.** Anything that would send data to a third party by default
  is out of scope.

## License

By contributing, you agree your contributions are licensed under the
project's [MIT license](LICENSE).

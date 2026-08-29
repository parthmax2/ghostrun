"""``ghostrun`` command-line interface for prompt regression tracking.

    ghostrun list                     # show saved run snapshots
    ghostrun show v1                  # inspect one snapshot
    ghostrun diff v1 v2               # compare two runs
    ghostrun diff v1 _last --fail-on-regression   # for CI
    ghostrun diff v1 v2 --format github-comment -o comment.md   # for a PR bot
    ghostrun diff v1 v2 --format junit -o ghostrun.xml            # for CI dashboards
    ghostrun doctor                   # diagnose config/cache/httpx/judge setup
    ghostrun init                     # scaffold a working first test in one command

Test execution itself stays in pytest — this CLI only inspects what a run
recorded.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import runlog, scaffold
from .config import get_config
from .regression import compare, render_github_comment, render_junit, render_text


def _cache_dir(args) -> str:
    return args.cache_dir or get_config().cache_dir


def cmd_list(args) -> int:
    cache_dir = _cache_dir(args)
    names = runlog.list_runs(cache_dir)
    if not names:
        print(f"No run snapshots in {runlog.runs_dir(cache_dir)}.")
        print("Record one with: pytest --ghostrun-snapshot <name>")
        return 0
    print(f"Run snapshots in {runlog.runs_dir(cache_dir)}:")
    for name in names:
        log = runlog.load(cache_dir, name)
        label = f"  [{log.label}]" if log.label else ""
        print(f"  {name:<24} {log.created}  {len(log.tests)} test(s){label}")
    return 0


def cmd_show(args) -> int:
    cache_dir = _cache_dir(args)
    log = runlog.load(cache_dir, args.name)
    if args.json:
        print(json.dumps(log.to_json(), indent=2, ensure_ascii=False))
        return 0
    print(f"Snapshot {log.name!r}  created {log.created}"
          + (f"  label={log.label!r}" if log.label else ""))
    for test_id, rec in sorted(log.tests.items()):
        status = "PASS" if rec.passed else "FAIL"
        print(f"\n[{status}] {test_id}")
        for i, out in enumerate(rec.outputs):
            preview = out if len(out) <= 200 else out[:197] + "..."
            print(f"  output[{i}]: {preview}")
        for a in rec.assertions:
            mark = "pass" if a.passed else "FAIL"
            print(f"    - {a.kind}({a.criterion!r}) [{mark}]"
                  + (f"  {a.reason}" if a.reason and not a.passed else ""))
    return 0


def _render_diff(result, fmt: str, show_diffs: bool, verbose: bool) -> str:
    if fmt == "json":
        return json.dumps({
            "baseline": result.baseline_name,
            "candidate": result.candidate_name,
            "summary": result.summary(),
            "regressions": [
                {"test_id": a.test_id, "kind": a.kind, "criterion": a.criterion,
                 "reason": a.after_reason}
                for a in result.regressions
            ],
            "fixes": [
                {"test_id": a.test_id, "kind": a.kind, "criterion": a.criterion}
                for a in result.fixes
            ],
            "outputs_changed": [
                {"test_id": o.test_id, "index": o.index,
                 "similarity": round(o.similarity, 4)}
                for o in result.changed_outputs
            ],
        }, indent=2, ensure_ascii=False)
    if fmt == "github-comment":
        return render_github_comment(result, show_diffs=show_diffs)
    if fmt == "junit":
        return render_junit(result)
    return render_text(result, show_diffs=show_diffs, verbose=verbose)


def cmd_diff(args) -> int:
    cache_dir = _cache_dir(args)
    baseline = runlog.load(cache_dir, args.baseline)
    candidate = runlog.load(cache_dir, args.candidate)
    result = compare(baseline, candidate)

    fmt = args.format or ("json" if args.json else "text")
    output = _render_diff(result, fmt, show_diffs=not args.no_diff, verbose=args.verbose)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(output)
            if not output.endswith("\n"):
                fh.write("\n")
    else:
        print(output)

    if args.fail_on_regression and result.has_regressions:
        return 1
    return 0


def cmd_doctor(args) -> int:
    from .interceptor import UnsupportedHttpx, _check_httpx_supported
    from .judge.ollama import OllamaJudge

    cfg = get_config()
    if args.cache_dir:
        cfg = cfg.with_overrides(cache_dir=args.cache_dir)
    ok_all = True

    def check(label: str, passed: bool, detail: str) -> None:
        nonlocal ok_all
        print(f"[{'OK  ' if passed else 'FAIL'}] {label}: {detail}")
        if not passed:
            ok_all = False

    print("Resolved configuration")
    print(f"  mode        = {cfg.mode}")
    print(f"  cache_dir   = {cfg.cache_dir}")
    print(f"  judge       = {cfg.judge}")
    print(f"  judge_model = {cfg.judge_model}")
    print(f"  judge_votes = {cfg.judge_votes}")
    print(f"  judge_cache = {cfg.judge_cache}")
    print()

    try:
        _check_httpx_supported()
        check("httpx", True, "interceptor hook available")
    except UnsupportedHttpx as exc:
        check("httpx", False, str(exc))

    cache_path = Path(cfg.cache_dir)
    try:
        cache_path.mkdir(parents=True, exist_ok=True)
        probe = cache_path / ".ghostrun_doctor_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        check("cache dir", True, f"{cache_path.resolve()} is writable")
    except OSError as exc:
        check("cache dir", False, f"{cache_path} is not writable: {exc}")

    if cfg.judge == "echo":
        check("judge", True,
              "echo (offline heuristic stub -- literal substring matching only, "
              "not real semantic grading; fine for CI plumbing, not for real assertions)")
    elif cfg.judge == "ollama":
        ok, reason = OllamaJudge(cfg.judge_model, cfg.judge_base_url,
                                 cfg.judge_timeout).is_available()
        check("judge", ok, reason)
    else:
        check("judge", False, f"unknown judge backend {cfg.judge!r}")

    print()
    print("All checks passed." if ok_all else "Some checks failed -- see FAIL lines above.")
    return 0 if ok_all else 1


def cmd_init(args) -> int:
    target_dir = Path(args.dir or ".").resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    config_path = target_dir / ".ghostrun.yaml"
    test_path = target_dir / args.filename

    existing = [p for p in (config_path, test_path) if p.exists()]
    if existing and not args.force:
        names = ", ".join(p.name for p in existing)
        print(f"error: {names} already exist(s) in {target_dir}. "
              f"Re-run with --force to overwrite.", file=sys.stderr)
        return 1

    sdk = scaffold.detect_sdk()
    config_path.write_text(scaffold.render_config(judge_type=args.judge), encoding="utf-8")
    test_path.write_text(scaffold.render_test_file(sdk, args.filename), encoding="utf-8")

    print(f"Created {config_path.relative_to(target_dir) if target_dir != Path('.').resolve() else config_path.name}")
    print(f"Created {test_path.name}  (detected SDK: {sdk})")
    print()
    print("Next steps:")
    if args.judge == "ollama":
        print("  1. ollama pull llama3.2:3b")
    step = 2 if args.judge == "ollama" else 1
    env_var = "OPENAI_API_KEY" if sdk != "anthropic" else "ANTHROPIC_API_KEY"
    print(f"  {step}. export {env_var}=...  (for the first, recording run)")
    print(f"  {step + 1}. pytest {args.filename}          # records + grades for real")
    print(f"  {step + 2}. pytest {args.filename}          # instant, from cache")
    print()
    print("Run `ghostrun doctor` any time to check your setup.")
    return 0


def cmd_pet(args) -> int:
    try:
        from .pet import run_pet
        run_pet(width=args.width, initial_anim=args.anim)
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Failed to launch GhostRun pet: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ghostrun",
        description="Inspect and compare ghostrun run snapshots.",
    )
    parser.add_argument("--cache-dir", default=None,
                        help="Override the cache directory (default: from config).")
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list", help="List saved run snapshots.")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="Show one run snapshot in detail.")
    p_show.add_argument("name")
    p_show.add_argument("--json", action="store_true", help="Emit JSON.")
    p_show.set_defaults(func=cmd_show)

    p_diff = sub.add_parser("diff", help="Compare two run snapshots.")
    p_diff.add_argument("baseline")
    p_diff.add_argument("candidate", nargs="?", default=runlog.LAST_RUN_NAME,
                        help=f"Defaults to {runlog.LAST_RUN_NAME!r}.")
    p_diff.add_argument("--json", action="store_true",
                        help="Emit JSON. Shorthand for --format json.")
    p_diff.add_argument("--format", choices=["text", "json", "github-comment", "junit"],
                        default=None,
                        help="Output format. 'github-comment' produces markdown for "
                             "posting as a PR comment; 'junit' produces JUnit XML for "
                             "CI test-result dashboards. Defaults to 'text'.")
    p_diff.add_argument("-o", "--output", default=None, metavar="FILE",
                        help="Write to FILE instead of stdout (e.g. for "
                             "`gh pr comment --body-file` or a JUnit results directory).")
    p_diff.add_argument("--no-diff", action="store_true",
                        help="Summarize output drift without printing text diffs.")
    p_diff.add_argument("-v", "--verbose", action="store_true",
                        help="Also list stable assertions.")
    p_diff.add_argument("--fail-on-regression", action="store_true",
                        help="Exit 1 if any PASS->FAIL is found (for CI).")
    p_diff.set_defaults(func=cmd_diff)

    p_doctor = sub.add_parser(
        "doctor", help="Diagnose a broken setup: config, cache dir, httpx, judge backend.")
    p_doctor.set_defaults(func=cmd_doctor)

    p_init = sub.add_parser(
        "init", help="Scaffold a working first test and .ghostrun.yaml in one command.")
    p_init.add_argument("--dir", default=None,
                        help="Directory to scaffold into (default: current directory).")
    p_init.add_argument("--filename", default="test_ghostrun_example.py",
                        help="Name of the generated test file.")
    p_init.add_argument("--judge", choices=["ollama", "echo"], default="ollama",
                        help="Judge backend to configure (default: ollama).")
    p_init.add_argument("--force", action="store_true",
                        help="Overwrite existing .ghostrun.yaml / test file.")
    p_init.set_defaults(func=cmd_init)

    p_pet = sub.add_parser(
        "pet", help="Launch the floating transparent desktop mascot companion.")
    p_pet.add_argument("--width", type=int, default=96, help="Pet width in pixels (default: 96).")
    p_pet.add_argument("--anim", default="idle", help="Initial animation state (default: idle).")
    p_pet.set_defaults(func=cmd_pet)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

"""Unit tests for the ghostrun tactical desktop companion and CLI runner."""

import os
from pathlib import Path
from ghostrun.pet import get_asset_paths, spawn_pet_async
from ghostrun.cli import build_parser, main


def test_pet_asset_paths_exist():
    spritesheet, meta_json = get_asset_paths()
    assert spritesheet.exists(), "spritesheet.png must exist in package assets"
    assert meta_json.exists(), "pet.json metadata must exist in package assets"
    assert spritesheet.stat().st_size > 0
    assert meta_json.stat().st_size > 0


def test_spawn_pet_async_silent_on_ci(monkeypatch):
    monkeypatch.setenv("CI", "true")
    # Should safely return without spawning or throwing exceptions
    spawn_pet_async("jumping", auto_close_ms=100)


def test_cli_pet_parser():
    parser = build_parser()
    args = parser.parse_args(["pet", "--width", "110", "--anim", "running"])
    assert args.command == "pet"
    assert args.width == 110
    assert args.anim == "running"


def test_cli_run_parser():
    parser = build_parser()
    args = parser.parse_args(["run", "examples/test_support_reply.py", "-v"])
    assert args.command == "run"
    assert args.pytest_args == ["examples/test_support_reply.py", "-v"]

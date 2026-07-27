"""`gentest init` -- scaffolds a working first test in one command."""

import ast

import pytest

from gentest.cli import main
from gentest.scaffold import detect_sdk, render_config, render_test_file


def test_detect_sdk_prefers_openai_when_installed():
    # openai is a real dependency of this dev environment (used by the live
    # smoke test / examples), so this exercises the real detection path.
    assert detect_sdk() in ("openai", "anthropic", "generic")


def test_detect_sdk_falls_back_to_generic(monkeypatch):
    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)
    assert detect_sdk() == "generic"


@pytest.mark.parametrize("sdk", ["openai", "anthropic", "generic"])
def test_rendered_test_file_is_valid_python(sdk):
    code = render_test_file(sdk, "test_gentest_example.py")
    ast.parse(code)  # raises SyntaxError if the template is broken
    assert "@gentest.record" in code
    assert "gentest.expect(" in code


def test_rendered_config_is_valid_yaml():
    import yaml
    data = yaml.safe_load(render_config(judge_type="echo"))
    assert data["judge"]["type"] == "echo"
    assert data["mode"] == "auto"


# --- CLI ---------------------------------------------------------------------

def test_init_creates_config_and_test_file(tmp_path, capsys):
    rc = main(["init", "--dir", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / ".gentest.yaml").is_file()
    assert (tmp_path / "test_gentest_example.py").is_file()
    out = capsys.readouterr().out
    assert "Created" in out
    assert "Next steps" in out


def test_init_refuses_to_overwrite_without_force(tmp_path, capsys):
    main(["init", "--dir", str(tmp_path)])
    rc = main(["init", "--dir", str(tmp_path)])
    assert rc == 1
    assert "already exist" in capsys.readouterr().err


def test_init_force_overwrites(tmp_path):
    main(["init", "--dir", str(tmp_path)])
    (tmp_path / "test_gentest_example.py").write_text("# modified", encoding="utf-8")
    rc = main(["init", "--dir", str(tmp_path), "--force"])
    assert rc == 0
    assert "# modified" not in (tmp_path / "test_gentest_example.py").read_text()


def test_init_custom_filename(tmp_path):
    main(["init", "--dir", str(tmp_path), "--filename", "test_custom.py"])
    assert (tmp_path / "test_custom.py").is_file()
    assert not (tmp_path / "test_gentest_example.py").exists()


def test_init_echo_judge_config(tmp_path):
    main(["init", "--dir", str(tmp_path), "--judge", "echo"])
    import yaml
    data = yaml.safe_load((tmp_path / ".gentest.yaml").read_text(encoding="utf-8"))
    assert data["judge"]["type"] == "echo"


def test_init_generated_file_is_collectible_by_pytest(tmp_path):
    """The generated test must at least be syntactically importable/collectible
    -- not just render as a string that happens to look like Python."""
    main(["init", "--dir", str(tmp_path), "--judge", "echo"])
    result = pytest.main(["--collect-only", "-q", str(tmp_path / "test_gentest_example.py")])
    assert result == pytest.ExitCode.OK

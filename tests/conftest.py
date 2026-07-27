import pytest

import gentest
from gentest import config as gt_config


@pytest.fixture(autouse=True)
def isolate_config(tmp_path, monkeypatch):
    """Each test gets a fresh cache dir and the offline echo judge, so the suite
    never touches the network or Ollama."""
    monkeypatch.setenv("GENTEST_JUDGE", "echo")
    monkeypatch.setenv("GENTEST_CACHE_DIR", str(tmp_path / "cache"))
    gt_config.reset_config()
    yield
    gt_config.reset_config()

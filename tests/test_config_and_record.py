import json

import httpx

import ghostrun
from ghostrun import config as gt_config


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("ghostrun_MODE", "replay")
    monkeypatch.setenv("ghostrun_JUDGE", "echo")
    gt_config.reset_config()
    cfg = gt_config.load_config()
    assert cfg.mode == "replay"
    assert cfg.judge == "echo"


def test_yaml_file(tmp_path, monkeypatch):
    (tmp_path / ".ghostrun.yaml").write_text(
        "mode: record\njudge:\n  type: ollama\n  model: qwen2:0.5b\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    gt_config.reset_config()
    cfg = gt_config.load_config()
    assert cfg.mode == "record"
    assert cfg.judge_model == "qwen2:0.5b"


def test_configure_overrides():
    ghostrun.configure(judge="echo", judge_model="x")
    assert ghostrun.get_config().judge_model == "x"


def test_record_decorator_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("ghostrun_CACHE_DIR", str(tmp_path / "c"))
    monkeypatch.setenv("ghostrun_MODE", "auto")
    gt_config.reset_config()

    counter = {"n": 0}

    def call():
        def handler(request):
            counter["n"] += 1
            return httpx.Response(200, json={"reply": "ok"})
        client = httpx.Client(transport=httpx.MockTransport(handler))
        return client.post("https://api.anthropic.com/v1/messages",
                           content=json.dumps({"prompt": "hi"}).encode())

    @ghostrun.record(model="claude")
    def do():
        return call().json()["reply"]

    assert do() == "ok"
    assert do() == "ok"
    assert counter["n"] == 1  # second run replayed from cache

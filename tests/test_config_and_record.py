import json

import httpx

import gentest
from gentest import config as gt_config


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("GENTEST_MODE", "replay")
    monkeypatch.setenv("GENTEST_JUDGE", "echo")
    gt_config.reset_config()
    cfg = gt_config.load_config()
    assert cfg.mode == "replay"
    assert cfg.judge == "echo"


def test_yaml_file(tmp_path, monkeypatch):
    (tmp_path / ".gentest.yaml").write_text(
        "mode: record\njudge:\n  type: ollama\n  model: qwen2:0.5b\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    gt_config.reset_config()
    cfg = gt_config.load_config()
    assert cfg.mode == "record"
    assert cfg.judge_model == "qwen2:0.5b"


def test_configure_overrides():
    gentest.configure(judge="echo", judge_model="x")
    assert gentest.get_config().judge_model == "x"


def test_record_decorator_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("GENTEST_CACHE_DIR", str(tmp_path / "c"))
    monkeypatch.setenv("GENTEST_MODE", "auto")
    gt_config.reset_config()

    counter = {"n": 0}

    def call():
        def handler(request):
            counter["n"] += 1
            return httpx.Response(200, json={"reply": "ok"})
        client = httpx.Client(transport=httpx.MockTransport(handler))
        return client.post("https://api.anthropic.com/v1/messages",
                           content=json.dumps({"prompt": "hi"}).encode())

    @gentest.record(model="claude")
    def do():
        return call().json()["reply"]

    assert do() == "ok"
    assert do() == "ok"
    assert counter["n"] == 1  # second run replayed from cache

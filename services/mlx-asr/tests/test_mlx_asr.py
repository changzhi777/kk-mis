"""mlx-asr 测试 — API Key / 文件大小 / 路径遍历 / 转写 mock。

系统内唯一未配 pytest 的服务，本次补齐。mock MLXTranscriber.transcribe/warmup，
避免真实 mlx_whisper 模型加载/推理（mlx_whisper 是 Apple Silicon 专属，且推理耗时）。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    """TestClient + mock 转写（避免真实 mlx_whisper）。"""
    from app import transcriber
    from app.schemas import Segment, TranscriptionResult

    def fake_transcribe(self, audio_path, language=None, beam_size=None):
        return TranscriptionResult(
            text="测试转写文本",
            language=language or "zh",
            duration=5.0,
            model="test-model",
            segments=[Segment(id=0, start=0.0, end=5.0, text="测试转写文本", speaker=None)],
        )

    monkeypatch.setattr(transcriber.MLXTranscriber, "transcribe", fake_transcribe)
    monkeypatch.setattr(transcriber.MLXTranscriber, "warmup", lambda self: None)
    # 固定 API key + 小上传限制（便于测 413）
    monkeypatch.setattr("app.config.settings.api_key", "test-key")
    monkeypatch.setattr("app.config.settings.max_upload_size_mb", 1)

    from app.main import app
    return TestClient(app)


# ── /health（无需鉴权）─────────────────────────────────────────────────


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "model" in body


# ── API Key 校验 ───────────────────────────────────────────────────────


def test_transcribe_no_api_key_401(client):
    r = client.post("/transcribe", files={"audio": ("t.wav", b"fake", "audio/wav")})
    assert r.status_code == 401


def test_transcribe_wrong_api_key_401(client):
    r = client.post(
        "/transcribe",
        files={"audio": ("t.wav", b"fake", "audio/wav")},
        headers={"X-API-Key": "wrong"},
    )
    assert r.status_code == 401


def test_models_requires_api_key(client):
    r = client.get("/models")
    assert r.status_code == 401


def test_models_with_api_key(client):
    r = client.get("/models", headers={"X-API-Key": "test-key"})
    assert r.status_code == 200


# ── 转写成功（mock）────────────────────────────────────────────────────


def test_transcribe_success(client):
    r = client.post(
        "/transcribe",
        files={"audio": ("test.mp3", b"fake-audio-data", "audio/mpeg")},
        data={"language": "zh"},
        headers={"X-API-Key": "test-key"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == "测试转写文本"
    assert body["language"] == "zh"
    assert body["model"] == "test-model"
    assert len(body["segments"]) == 1


def test_transcribe_default_language_when_omitted(client):
    r = client.post(
        "/transcribe",
        files={"audio": ("t.wav", b"data", "audio/wav")},
        headers={"X-API-Key": "test-key"},
    )
    assert r.status_code == 200
    # fake_transcribe 在 language=None 时返回 "zh"（default_language）
    assert r.json()["language"] == "zh"


# ── 文件大小校验（413）─────────────────────────────────────────────────


def test_transcribe_file_too_large_413(client):
    # max_upload_size_mb=1，造 2MB 内容
    big = b"x" * (2 * 1024 * 1024)
    r = client.post(
        "/transcribe",
        files={"audio": ("big.wav", big, "audio/wav")},
        headers={"X-API-Key": "test-key"},
    )
    assert r.status_code == 413


# ── 路径遍历防护（_safe_filename）──────────────────────────────────────


def test_safe_filename_strips_path_traversal():
    from app.main import _safe_filename

    # 路径部分被 Path.name 去除，只留文件名
    result = _safe_filename("../../etc/passwd")
    assert "/" not in result
    assert result == "passwd"


def test_safe_filename_strips_absolute_path():
    from app.main import _safe_filename

    result = _safe_filename("/tmp/secret/attack.wav")
    assert "/" not in result
    assert result == "attack.wav"


def test_safe_filename_normal():
    from app.main import _safe_filename

    assert _safe_filename("meeting-2026.m4a") == "meeting-2026.m4a"


def test_safe_filename_empty_and_none():
    from app.main import _safe_filename

    assert _safe_filename("") == "audio"
    assert _safe_filename(None) == "audio"


def test_safe_filename_replaces_special_chars():
    from app.main import _safe_filename

    # 中文/空格等非 [a-zA-Z0-9._-] 替换为 _
    result = _safe_filename("会议 纪要.wav")
    assert " " not in result
    assert "/" not in result
    assert result.endswith(".wav")

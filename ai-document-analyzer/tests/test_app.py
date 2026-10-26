"""Smoke test: the Streamlit script renders without raising."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_app_renders_empty_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # keep chat_history out of the repo
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert any("Upload one or more documents" in i.value for i in at.info)


def test_question_without_key_shows_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.chat_input[0].set_value("hello").run()
    assert not at.exception
    assert any("API key" in e.value for e in at.error)

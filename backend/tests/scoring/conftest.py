import pytest


@pytest.fixture(autouse=True)
def no_live_llm(monkeypatch):
    """Tests use only the committed cache and templates, never a running Ollama or GPU tunnel."""
    monkeypatch.setenv("LLM_LIVE", "0")

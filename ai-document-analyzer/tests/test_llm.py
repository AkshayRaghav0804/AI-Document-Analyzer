from types import SimpleNamespace

from docanalyzer import config
from docanalyzer.llm import Analyzer, chunk_text, estimate_tokens


def test_short_text_is_one_chunk():
    assert chunk_text("hello", max_chars=100) == ["hello"]


def test_chunks_respect_limit_and_cover_content():
    text = "\n\n".join(f"paragraph {i} " + "x" * 200 for i in range(100))
    chunks = chunk_text(text, max_chars=2000, overlap=100)
    assert len(chunks) > 1
    assert all(len(c) <= 2000 + 100 + 250 for c in chunks)
    assert "paragraph 0" in chunks[0] and "paragraph 99" in chunks[-1]


def test_single_giant_paragraph_is_split():
    chunks = chunk_text("y" * 10_000, max_chars=1_000, overlap=0)
    assert len(chunks) >= 10


def test_routing_threshold():
    assert not Analyzer.needs_map_reduce("small")
    assert Analyzer.needs_map_reduce("x" * (config.MAX_DIRECT_TOKENS * 4 + 10))
    assert estimate_tokens("x" * 400) == 100


class _FakeStream:
    def __init__(self, parts):
        self.text_stream = iter(parts)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_analyzer(captured):
    analyzer = Analyzer.__new__(Analyzer)
    analyzer.model = "test-model"

    def stream(**kwargs):
        captured.update(kwargs)
        return _FakeStream(["Hel", "lo"])

    analyzer.client = SimpleNamespace(messages=SimpleNamespace(stream=stream))
    return analyzer


def test_direct_answer_streams_and_trims_history():
    captured = {}
    analyzer = _fake_analyzer(captured)
    history = [
        {"role": "assistant", "content": "orphan", "time": "10:00"},  # must be dropped (not user-first)
        {"role": "user", "content": "q1", "time": "10:01"},
        {"role": "assistant", "content": "a1", "time": "10:02"},
    ]
    out = "".join(analyzer.stream_answer("q2", "DOC TEXT", history))
    assert out == "Hello"
    msgs = captured["messages"]
    assert msgs[0]["role"] == "user" and msgs[-1] == {"role": "user", "content": "q2"}
    assert all(set(m) == {"role", "content"} for m in msgs)  # timestamps stripped
    assert "DOC TEXT" in captured["system"][1]["text"]


def test_map_reduce_skips_irrelevant_sections_and_reports_progress(monkeypatch):
    monkeypatch.setattr(config, "CHUNK_CHARS", 1000)
    import docanalyzer.llm as llm

    monkeypatch.setattr(llm, "chunk_text", lambda text: ["sec A", "sec B", "sec C"])
    replies = iter(["Revenue 4.2M (file a.pdf, p2)", "NONE", "Costs 1.1M (sheet Q1)"])
    seen_prompts = []

    def create(**kwargs):
        return SimpleNamespace(content=[SimpleNamespace(text=next(replies))])

    def stream(**kwargs):
        seen_prompts.append(kwargs["messages"][0]["content"])
        return _FakeStream(["Final ", "answer"])

    analyzer = Analyzer.__new__(Analyzer)
    analyzer.model = "m"
    analyzer.client = SimpleNamespace(messages=SimpleNamespace(create=create, stream=stream))

    steps = []
    out = "".join(analyzer._map_reduce("What are the numbers?", "ignored", lambda f, t: steps.append(t)))

    assert out == "Final answer"
    assert "Revenue 4.2M" in seen_prompts[0] and "Costs 1.1M" in seen_prompts[0]
    assert "NONE" not in seen_prompts[0]
    assert steps[0].startswith("Reading section 1 of 3") and steps[-1] == "Combining findings"


def test_map_reduce_with_nothing_relevant(monkeypatch):
    import docanalyzer.llm as llm

    monkeypatch.setattr(llm, "chunk_text", lambda text: ["only"])
    analyzer = Analyzer.__new__(Analyzer)
    analyzer.model = "m"
    analyzer.client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **k: SimpleNamespace(content=[SimpleNamespace(text="NONE")]))
    )
    out = "".join(analyzer._map_reduce("q", "x", None))
    assert "could not find anything relevant" in out

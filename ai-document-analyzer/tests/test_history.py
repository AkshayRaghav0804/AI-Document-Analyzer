from docanalyzer.history import ChatStore


def _msgs(text="What is the revenue?"):
    return [{"role": "user", "content": text}, {"role": "assistant", "content": "4.2M"}]


def test_save_load_roundtrip(tmp_path):
    store = ChatStore(tmp_path)
    cid = store.save(None, _msgs(), ["a.pdf"])
    data = store.load(cid)
    assert data["messages"] == _msgs()
    assert data["file_names"] == ["a.pdf"]
    assert store.list()[0]["id"] == cid


def test_empty_chat_is_not_saved(tmp_path):
    store = ChatStore(tmp_path)
    assert store.save(None, [], []) is None
    assert store.list() == []


def test_updating_keeps_same_id(tmp_path):
    store = ChatStore(tmp_path)
    cid = store.save(None, _msgs(), [])
    assert store.save(cid, _msgs() * 2, []) == cid
    assert len(store.list()) == 1
    assert store.list()[0]["message_count"] == 4


def test_rename_sticks_after_more_messages(tmp_path):
    store = ChatStore(tmp_path)
    cid = store.save(None, _msgs(), [])
    store.rename(cid, "My title")
    store.save(cid, _msgs() * 2, [])
    assert store.list()[0]["title"] == "My title"


def test_search_title_and_body(tmp_path):
    store = ChatStore(tmp_path)
    a = store.save(None, _msgs("alpha question"), [])
    b = store.save(None, [{"role": "user", "content": "other"}, {"role": "assistant", "content": "mentions zebra"}], [])
    assert [c["id"] for c in store.search("alpha")] == [a]
    assert [c["id"] for c in store.search("zebra")] == [b]
    assert len(store.search("")) == 2


def test_delete(tmp_path):
    store = ChatStore(tmp_path)
    cid = store.save(None, _msgs(), [])
    store.delete(cid)
    assert store.list() == [] and store.load(cid) is None


def test_load_rejects_path_traversal(tmp_path):
    store = ChatStore(tmp_path / "chats")
    (tmp_path / "secret.json").write_text("{}")
    assert store.load("../secret") is None

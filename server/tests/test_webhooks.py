import os, sys, importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _fresh(tmp_path, monkeypatch):
    """Import webhooks with an isolated DB path."""
    monkeypatch.setenv("WEBHOOKS_DB_PATH", str(tmp_path / "wh.db"))
    import webhooks
    importlib.reload(webhooks)
    return webhooks


def test_store_and_recent_roundtrip(tmp_path, monkeypatch):
    wh = _fresh(tmp_path, monkeypatch)
    rec = wh.store_event({"eventType": 101, "notifyMs": 111, "sid": "s1",
                          "payload": {"channelName": "c", "labels": {"session": "abc"}}})
    assert rec["id"] >= 1
    assert rec["eventType"] == 101
    assert rec["payload"]["labels"]["session"] == "abc"
    rows = wh.recent_events()
    assert len(rows) == 1
    assert rows[0]["eventType"] == 101


def test_recent_is_newest_last_and_append_only(tmp_path, monkeypatch):
    wh = _fresh(tmp_path, monkeypatch)
    wh.store_event({"eventType": 101, "notifyMs": 1, "sid": "s", "payload": {}})
    wh.store_event({"eventType": 102, "notifyMs": 2, "sid": "s", "payload": {}})
    wh.store_event({"eventType": 102, "notifyMs": 2, "sid": "s", "payload": {}})  # duplicate kept
    rows = wh.recent_events()
    assert [r["eventType"] for r in rows] == [101, 102, 102]  # newest last, dupes retained


def test_reset_clears(tmp_path, monkeypatch):
    wh = _fresh(tmp_path, monkeypatch)
    wh.store_event({"eventType": 101, "notifyMs": 1, "sid": "s", "payload": {}})
    wh.reset_events()
    assert wh.recent_events() == []

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


import hashlib, hmac


def test_verify_dev_mode_when_secret_unset(tmp_path, monkeypatch):
    wh = _fresh(tmp_path, monkeypatch)
    assert wh.verify_signature(None, b'{"a":1}', None) is True
    assert wh.verify_signature("", b'{"a":1}', "anything") is True


def test_verify_requires_matching_hmac_when_secret_set(tmp_path, monkeypatch):
    wh = _fresh(tmp_path, monkeypatch)
    secret, raw = "shh", b'{"eventType":101}'
    good = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    assert wh.verify_signature(secret, raw, good) is True
    assert wh.verify_signature(secret, raw, "deadbeef") is False
    assert wh.verify_signature(secret, raw, None) is False


def test_parse_event_extracts_envelope(tmp_path, monkeypatch):
    wh = _fresh(tmp_path, monkeypatch)
    body = {"eventType": 102, "notifyMs": 9, "sid": "abc",
            "payload": {"channelName": "c", "leaveReason": "idle", "labels": {"session": "s1"}}}
    ev = wh.parse_event(body)
    assert ev["eventType"] == 102 and ev["sid"] == "abc"
    assert ev["payload"]["leaveReason"] == "idle"


def test_parse_event_tolerates_missing_fields(tmp_path, monkeypatch):
    wh = _fresh(tmp_path, monkeypatch)
    ev = wh.parse_event({"eventType": 777})  # unknown type, no payload
    assert ev["eventType"] == 777 and ev["payload"] == {}


def test_event_display_name(tmp_path, monkeypatch):
    wh = _fresh(tmp_path, monkeypatch)
    assert wh.event_display_name(101) == "Agent started"
    assert wh.event_display_name(102) == "Agent stopped"
    assert wh.event_display_name(777) == "Event 777"
    assert wh.event_display_name(None) == "Event"


import asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client(wh):
    app = FastAPI()
    app.include_router(wh.router)
    return TestClient(app)


def test_ncsnotify_stores_and_returns_200_dev_mode(tmp_path, monkeypatch):
    wh = _fresh(tmp_path, monkeypatch)
    client = _client(wh)
    body = {"eventType": 101, "notifyMs": 1, "sid": "s",
            "payload": {"channelName": "c", "labels": {"session": "abc"}}}
    r = client.post("/ncsNotify", json=body)
    assert r.status_code == 200 and r.json()["code"] == 0
    assert wh.recent_events()[0]["eventType"] == 101


def test_ncsnotify_rejects_bad_signature_when_secret_set(tmp_path, monkeypatch):
    monkeypatch.setenv("AGORA_NOTIFICATION_SECRET", "shh")
    wh = _fresh(tmp_path, monkeypatch)
    client = _client(wh)
    r = client.post("/ncsNotify", json={"eventType": 101},
                    headers={"Agora-Signature-V2": "wrong"})
    assert r.status_code == 401
    assert wh.recent_events() == []


def test_reset_endpoint(tmp_path, monkeypatch):
    wh = _fresh(tmp_path, monkeypatch)
    client = _client(wh)
    client.post("/ncsNotify", json={"eventType": 101, "payload": {}})
    r = client.post("/webhooks/reset")
    assert r.status_code == 200
    assert wh.recent_events() == []


def test_sse_hub_publish_subscribe(tmp_path, monkeypatch):
    wh = _fresh(tmp_path, monkeypatch)

    async def go():
        hub = wh.SseHub()
        q = hub.subscribe()
        hub.publish({"eventType": 101})
        got = await asyncio.wait_for(q.get(), timeout=1)
        hub.unsubscribe(q)
        return got

    assert asyncio.run(go())["eventType"] == 101

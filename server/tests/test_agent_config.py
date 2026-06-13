import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("AGORA_APP_ID", "x")
os.environ.setdefault("AGORA_APP_CERTIFICATE", "y")
import agent as a  # noqa: E402
import server as s  # noqa: E402


def test_agent_constructs():
    inst = a.Agent()
    assert inst.openai_model


def test_webhooks_routes_are_mounted():
    paths = {r.path for r in s.app.routes}
    assert "/ncsNotify" in paths
    assert "/webhooks/stream" in paths
    assert "/webhooks/reset" in paths

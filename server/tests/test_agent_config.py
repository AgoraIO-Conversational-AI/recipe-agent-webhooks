import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("AGORA_APP_ID", "x")
os.environ.setdefault("AGORA_APP_CERTIFICATE", "y")
import agent as a  # noqa: E402
import server as s  # noqa: E402


def test_agent_constructs():
    inst = a.Agent()
    assert inst.openai_model


def _all_route_paths(app):
    """Collect paths from both direct routes and included sub-routers (FastAPI compat)."""
    paths = set()
    for r in app.routes:
        if hasattr(r, "path"):
            paths.add(r.path)
        if hasattr(r, "original_router"):
            for sr in r.original_router.routes:
                if hasattr(sr, "path"):
                    paths.add(sr.path)
    return paths


def test_webhooks_routes_are_mounted():
    paths = _all_route_paths(s.app)
    assert "/ncsNotify" in paths
    assert "/webhooks/stream" in paths
    assert "/webhooks/reset" in paths

from app import app

def test_home():
    resp = app.test_client().get("/")
    assert resp.status_code == 200
    assert b"Hello" in resp.data

def test_health():
    resp = app.test_client().get("/health")
    assert resp.status_code == 200
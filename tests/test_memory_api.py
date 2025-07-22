from fastapi.testclient import TestClient
from memory_api import app

def test_root():
    client = TestClient(app)
    response = client.get("/memories/demo")
    assert response.status_code in (200, 501)

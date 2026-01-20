"""
Test health endpoint.
"""
def test_health(client):
    """Test health check."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

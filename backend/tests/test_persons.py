"""
Test person endpoints.
"""
from app.db import models


def test_create_person(client, db):
    """Test creating a person."""
    response = client.post(
        "/v1/persons",
        json={
            "name": "Test Person",
            "consent_confirmed": True,
            "subject_is_adult": True
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Person"
    assert data["consent_confirmed"] is True
    assert data["subject_is_adult"] is True
    assert "id" in data


def test_create_person_without_consent(client, db):
    """Test creating person without consent fails."""
    response = client.post(
        "/v1/persons",
        json={
            "name": "Test Person",
            "consent_confirmed": False,
            "subject_is_adult": True
        }
    )
    assert response.status_code == 400


def test_presign_upload(client, db):
    """Test presigned URL generation."""
    # Create person first
    person_response = client.post(
        "/v1/persons",
        json={
            "name": "Test Person",
            "consent_confirmed": True,
            "subject_is_adult": True
        }
    )
    person_id = person_response.json()["id"]
    
    # Get presigned URL
    response = client.post(
        f"/v1/persons/{person_id}/uploads/presign",
        json={
            "filename": "test.jpg",
            "content_type": "image/jpeg",
            "size_bytes": 1024
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert "key" in data
    assert data["method"] == "PUT"

import pytest
from fastapi.testclient import TestClient
from main import app
from scripts.seed import seed_data

client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    seed_data()


def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_get_departments():
    response = client.get("/api/v1/departments")
    assert response.status_code == 200
    departments = response.json()
    assert len(departments) >= 8
    names = [d["name"] for d in departments]
    assert "Neurology" in names
    assert "Cardiology" in names


def test_get_doctors():
    response = client.get("/api/v1/doctors")
    assert response.status_code == 200
    doctors = response.json()
    assert len(doctors) >= 4
    names = [d["name"] for d in doctors]
    assert "Dr. Lloyd Wilson" in names


def test_book_appointment():
    dept_resp = client.get("/api/v1/departments")
    assert len(dept_resp.json()) > 0
    dept_id = dept_resp.json()[0]["id"]

    payload = {
        "first_name": "Sarah",
        "last_name": "Connor",
        "email": "sarah.connor@example.com",
        "phone": "+1 555-0199",
        "department_id": dept_id,
        "appointment_date": "2026-11-01",
        "appointment_time": "10:30 AM",
        "message": "Routine health checkup consultation"
    }

    response = client.post("/api/v1/appointments", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["first_name"] == "Sarah"
    assert data["status"] == "PENDING"
    assert data["reference_number"].startswith("MED-")

    ref_no = data["reference_number"]
    lookup = client.get(f"/api/v1/appointments/{ref_no}")
    assert lookup.status_code == 200
    assert lookup.json()["reference_number"] == ref_no


def test_get_blogs_and_post_comment():
    blogs_resp = client.get("/api/v1/blogs")
    assert blogs_resp.status_code == 200
    blogs = blogs_resp.json()
    assert len(blogs) > 0
    first_blog = blogs[0]

    comment_payload = {
        "name": "Alex Murphy",
        "email": "alex.murphy@example.com",
        "website": "https://alexmurphy.com",
        "message": "Great medical insight, very helpful article!"
    }
    comment_resp = client.post(f"/api/v1/blogs/{first_blog['id']}/comments", json=comment_payload)
    assert comment_resp.status_code == 201
    assert comment_resp.json()["name"] == "Alex Murphy"


def test_submit_contact_message():
    payload = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "subject": "General inquiry about cardiology appointments",
        "message": "Hello, do you accept international medical insurance?"
    }
    response = client.post("/api/v1/contact", json=payload)
    assert response.status_code == 201
    assert response.json()["subject"] == payload["subject"]


def test_get_stats():
    response = client.get("/api/v1/stats")
    assert response.status_code == 200
    stats = response.json()["stats"]
    assert len(stats) >= 4


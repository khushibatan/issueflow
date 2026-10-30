
import pytest
from fastapi.testclient import TestClient
import app.main as main

@pytest.fixture
def client(tmp_path, monkeypatch):
    # Give each test a separate, temporary database.
    test_database = tmp_path / "test_issueflow.db"
    monkeypatch.setattr(main, "DATABASE", str(test_database))

    # Create the tasks table in the temporary database.
    main.init_db()

    with TestClient(main.app) as test_client:
        yield test_client


def test_home(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to IssueFlow!"}


def test_get_tasks_initially_empty(client):
    response = client.get("/tasks")
    assert response.status_code == 200
    assert response.json() == []


def test_create_task(client):
    response = client.post("/tasks", json={"title": "Learn FastAPI"})

    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "title": "Learn FastAPI",
        "status": "To Do",
        "priority": "Medium"
    }


def test_create_task_strips_extra_spaces(client):
    response = client.post(
        "/tasks",
        json={"title": "  Learn SQLite  "}
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Learn SQLite"


def test_empty_title_rejected(client):
    response = client.post("/tasks", json={"title": ""})
    assert response.status_code == 422


def test_spaces_only_title_rejected(client):
    response = client.post("/tasks", json={"title": "   "})
    assert response.status_code == 422


def test_invalid_status_rejected(client):
    response = client.put("/tasks/1", json={"status": "Banana"})
    assert response.status_code == 422


def test_update_task_status(client):
    created = client.post(
        "/tasks",
        json={"title": "Finish Java assignment"}
    )
    task_id = created.json()["id"]

    response = client.put(
        f"/tasks/{task_id}",
        json={"status": "In Progress"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "In Progress"


def test_update_missing_task(client):
    response = client.put(
        "/tasks/999",
        json={"status": "Done"}
    )

    assert response.status_code == 404


def test_delete_task(client):
    created = client.post(
        "/tasks",
        json={"title": "Temporary task"}
    )
    task_id = created.json()["id"]

    response = client.delete(f"/tasks/{task_id}")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Task deleted successfully"
    }

    remaining_tasks = client.get("/tasks")
    assert remaining_tasks.json() == []


def test_delete_missing_task(client):
    response = client.delete("/tasks/999")
    assert response.status_code == 404



def test_create_task_with_high_priority(client):
    response = client.post(
        "/tasks",
        json={"title": "Submit project", "priority": "High"}
    )

    assert response.status_code == 200
    assert response.json()["priority"] == "High"


def test_create_task_with_low_priority(client):
    response = client.post(
        "/tasks",
        json={"title": "Organize notes", "priority": "Low"}
    )

    assert response.status_code == 200
    assert response.json()["priority"] == "Low"


def test_invalid_priority_rejected(client):
    response = client.post(
        "/tasks",
        json={"title": "Submit project", "priority": "Urgent"}
    )

    assert response.status_code == 422


def test_update_task_priority(client):
    created = client.post(
        "/tasks",
        json={"title": "Finish project", "priority": "Low"}
    )
    task_id = created.json()["id"]

    response = client.put(
        f"/tasks/{task_id}",
        json={"priority": "High"}
    )

    assert response.status_code == 200
    assert response.json()["priority"] == "High"
    assert response.json()["status"] == "To Do"


def test_update_priority_preserves_status(client):
    created = client.post(
        "/tasks",
        json={"title": "Study DSA"}
    )
    task_id = created.json()["id"]

    client.put(
        f"/tasks/{task_id}",
        json={"status": "In Progress"}
    )

    response = client.put(
        f"/tasks/{task_id}",
        json={"priority": "Low"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "In Progress"
    assert response.json()["priority"] == "Low"


def test_empty_update_rejected(client):
    created = client.post(
        "/tasks",
        json={"title": "Study Java"}
    )
    task_id = created.json()["id"]

    response = client.put(
        f"/tasks/{task_id}",
        json={}
    )

    assert response.status_code == 422

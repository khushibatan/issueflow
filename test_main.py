
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
def create_test_issue(client):
    workspace = client.post(
        "/workspaces",
        json={"name": "Test Organisation"}
    )

    issue = client.post(
        "/issues",
        json={
            "workspace_id": workspace.json()["id"],
            "title": "Projector failure",
            "description": "The projector keeps shutting down.",
            "category": "Equipment",
            "priority": "Medium"
        }
    )

    return issue.json()["id"]


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
        "priority": "Medium",
        "due_date": None
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


def test_create_workspace(client):
    response = client.post(
        "/workspaces",
        json={"name": "ABC Organisation"}
    )

    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert response.json()["name"] == "ABC Organisation"


def test_create_workspace_strips_spaces(client):
    response = client.post(
        "/workspaces",
        json={"name": "  Design Agency  "}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Design Agency"


def test_create_workspace_rejects_blank_name(client):
    response = client.post(
        "/workspaces",
        json={"name": "   "}
    )

    assert response.status_code == 422

def test_create_issue(client):
    workspace = client.post(
        "/workspaces",
        json={"name": "Test Organisation"}
    )

    workspace_id = workspace.json()["id"]

    response = client.post(
        "/issues",
        json={
            "workspace_id": workspace_id,
            "title": "Projector not functioning",
            "description": "The projector repeatedly shuts down.",
            "category": "Equipment",
            "priority": "High"
        }
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Projector not functioning"
    assert response.json()["priority"] == "High"
    assert response.json()["status"] == "Open"


def test_create_issue_with_default_priority(client):
    workspace = client.post(
        "/workspaces",
        json={"name": "Test Organisation"}
    )

    response = client.post(
        "/issues",
        json={
            "workspace_id": workspace.json()["id"],
            "title": "Internet connection problem"
        }
    )

    assert response.status_code == 200
    assert response.json()["priority"] == "Medium"
    assert response.json()["status"] == "Open"


def test_create_issue_with_invalid_workspace(client):
    response = client.post(
        "/issues",
        json={
            "workspace_id": 999,
            "title": "Test issue"
        }
    )

    assert response.status_code == 404


def test_create_issue_rejects_blank_title(client):
    workspace = client.post(
        "/workspaces",
        json={"name": "Test Organisation"}
    )

    response = client.post(
        "/issues",
        json={
            "workspace_id": workspace.json()["id"],
            "title": "   "
        }
    )

    assert response.status_code == 422


def test_create_issue_rejects_invalid_priority(client):
    workspace = client.post(
        "/workspaces",
        json={"name": "Test Organisation"}
    )

    response = client.post(
        "/issues",
        json={
            "workspace_id": workspace.json()["id"],
            "title": "Test issue",
            "priority": "Urgent"
        }
    )

    assert response.status_code == 422

def test_get_workspace_issues(client):
    workspace = client.post(
        "/workspaces",
        json={"name": "Test Organisation"}
    )

    workspace_id = workspace.json()["id"]

    client.post(
        "/issues",
        json={
            "workspace_id": workspace_id,
            "title": "Projector failure"
        }
    )

    response = client.get(
        f"/workspaces/{workspace_id}/issues"
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Projector failure"


def test_get_workspace_issues_not_found(client):
    response = client.get("/workspaces/999/issues")

    assert response.status_code == 404


def test_get_individual_issue(client):
    workspace = client.post(
        "/workspaces",
        json={"name": "Test Organisation"}
    )

    issue = client.post(
        "/issues",
        json={
            "workspace_id": workspace.json()["id"],
            "title": "Internet failure"
        }
    )

    issue_id = issue.json()["id"]

    response = client.get(f"/issues/{issue_id}")

    assert response.status_code == 200
    assert response.json()["title"] == "Internet failure"
    assert response.json()["id"] == issue_id


def test_get_individual_issue_not_found(client):
    response = client.get("/issues/999")

    assert response.status_code == 404

def test_update_issue_fields(client):
    issue_id = create_test_issue(client)

    response = client.put(
        f"/issues/{issue_id}",
        json={
            "status": "Investigating",
            "priority": "High"
        }
    )

    assert response.status_code == 200
    assert response.json()["status"] == "Investigating"
    assert response.json()["priority"] == "High"
    assert response.json()["title"] == "Projector failure"


def test_update_issue_title(client):
    issue_id = create_test_issue(client)

    response = client.put(
        f"/issues/{issue_id}",
        json={"title": "Projector requires replacement"}
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Projector requires replacement"


def test_update_missing_issue(client):
    response = client.put(
        "/issues/999",
        json={"status": "Investigating"}
    )

    assert response.status_code == 404


def test_empty_issue_update_rejected(client):
    issue_id = create_test_issue(client)

    response = client.put(
        f"/issues/{issue_id}",
        json={}
    )

    assert response.status_code == 422


def test_blank_issue_title_rejected(client):
    issue_id = create_test_issue(client)

    response = client.put(
        f"/issues/{issue_id}",
        json={"title": "   "}
    )

    assert response.status_code == 422


@pytest.mark.parametrize("field,value", [
    ("priority", "Urgent"),
    ("status", "Banana"),
    ("status", "Verified")
])
def test_invalid_issue_update_rejected(client, field, value):
    issue_id = create_test_issue(client)

    response = client.put(
        f"/issues/{issue_id}",
        json={field: value}
    )

    assert response.status_code == 422

def test_open_issue_can_move_to_investigating(client):
    issue_id = create_test_issue(client)

    response = client.put(
        f"/issues/{issue_id}",
        json={"status": "Investigating"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "Investigating"


def test_open_issue_cannot_move_directly_to_resolved(client):
    issue_id = create_test_issue(client)

    response = client.put(
        f"/issues/{issue_id}",
        json={"status": "Resolved"}
    )

    assert response.status_code == 400
    assert "Cannot change status" in response.json()["detail"]


def test_investigating_issue_can_move_to_resolved(client):
    issue_id = create_test_issue(client)

    client.put(
        f"/issues/{issue_id}",
        json={"status": "Investigating"}
    )

    response = client.put(
        f"/issues/{issue_id}",
        json={"status": "Resolved"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "Resolved"


def test_resolved_issue_can_return_to_investigating(client):
    issue_id = create_test_issue(client)

    client.put(
        f"/issues/{issue_id}",
        json={"status": "Investigating"}
    )

    client.put(
        f"/issues/{issue_id}",
        json={"status": "Resolved"}
    )

    response = client.put(
        f"/issues/{issue_id}",
        json={"status": "Investigating"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "Investigating"


def test_issue_cannot_skip_investigation(client):
    issue_id = create_test_issue(client)

    response = client.put(
        f"/issues/{issue_id}",
        json={"status": "Action Required"}
    )

    assert response.status_code == 400


def test_same_status_update_is_allowed(client):
    issue_id = create_test_issue(client)

    response = client.put(
        f"/issues/{issue_id}",
        json={"status": "Open"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "Open"
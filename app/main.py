from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator
import sqlite3
from typing import Literal
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from uuid import uuid4

app = FastAPI(title="IssueFlow")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500"
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE = "issueflow.db"
EVIDENCE_STORAGE_DIR = Path(__file__).resolve().parent.parent / "data" / "evidence"
MAX_EVIDENCE_SIZE = 5 * 1024 * 1024


# Connect to the database and create the tasks table


def init_db():
    with sqlite3.connect(DATABASE) as connection:

        # Keep the existing task table during our transition.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'To Do',
                priority TEXT NOT NULL DEFAULT 'Medium',
                due_date TEXT
            )
        """)

        # Check existing task columns for older databases.
        columns = connection.execute(
            "PRAGMA table_info(tasks)"
        ).fetchall()

        column_names = [column[1] for column in columns]

        if "priority" not in column_names:
            connection.execute("""
                ALTER TABLE tasks
                ADD COLUMN priority TEXT NOT NULL DEFAULT 'Medium'
            """)

        if "due_date" not in column_names:
            connection.execute("""
                ALTER TABLE tasks
                ADD COLUMN due_date TEXT
            """)

        # An organisation or team using IssueFlow.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS workspaces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # A problem reported within a workspace.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT 'General',
                priority TEXT NOT NULL DEFAULT 'Medium'
                    CHECK (priority IN ('Low', 'Medium', 'High')),
                status TEXT NOT NULL DEFAULT 'Open'
                    CHECK (status IN (
                        'Open',
                        'Investigating',
                        'Action Required',
                        'Resolved',
                        'Verified'
                    )),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (workspace_id)
                    REFERENCES workspaces(id)
                    ON DELETE CASCADE
            )
        """)

        # Investigation records associated with an issue.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS investigation_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_id INTEGER NOT NULL,
                notes TEXT NOT NULL,
                finding TEXT NOT NULL DEFAULT '',
                possible_cause TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (issue_id)
                    REFERENCES issues(id)
                    ON DELETE CASCADE
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                investigation_id INTEGER NOT NULL,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL UNIQUE,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (investigation_id)
                    REFERENCES investigation_records(id)
                    ON DELETE CASCADE
            )
        """)



init_db()

class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Workspace name cannot be empty")
        return value.strip()

class IssueCreate(BaseModel):
    workspace_id: int
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    category: str = Field(default="General", max_length=100)
    priority: Literal["Low", "Medium", "High"] = "Medium"

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Issue title cannot be blank")
        return value.strip()

    @field_validator("description", "category")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

class IssueUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=200
    )

    description: str | None = Field(
        default=None,
        max_length=2000
    )

    category: str | None = Field(
        default=None,
        max_length=100
    )

    priority: Literal["Low", "Medium", "High"] | None = None

    status: Literal[
        "Open",
        "Investigating",
        "Action Required",
        "Resolved"
    ] | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        if value is None:
            return value

        if not value.strip():
            raise ValueError("Issue title cannot be blank")

        return value.strip()

    @field_validator("description", "category")
    @classmethod
    def strip_text(cls, value):
        if value is None:
            return value

        return value.strip()


class InvestigationCreate(BaseModel):
    notes: str
    finding: str = ""
    possible_cause: str = ""

    @field_validator("notes", "finding", "possible_cause")
    @classmethod
    def validate_text(cls, value):
        return value.strip()

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value):
        if not value:
            raise ValueError("Investigation notes cannot be empty")
        return value


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    priority: Literal["Low", "Medium", "High"] = "Medium"
    due_date: str | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title cannot be empty or only spaces")
        return value.strip()

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None

        from datetime import date

        try:
            parsed_date = date.fromisoformat(value)
        except ValueError:
            raise ValueError("Due date must use YYYY-MM-DD format")

        if parsed_date.isoformat() != value:
            raise ValueError("Due date must use YYYY-MM-DD format")

        return value


class TaskUpdate(BaseModel):
    status: Literal["To Do", "In Progress", "Done"] | None = None
    priority: Literal["Low", "Medium", "High"] | None = None

@app.post("/workspaces")
def create_workspace(workspace: WorkspaceCreate):
    with sqlite3.connect(DATABASE) as connection:
        cursor = connection.execute(
            """
            INSERT INTO workspaces (name)
            VALUES (?)
            """,
            (workspace.name,)
        )

        workspace_id = cursor.lastrowid

        connection.row_factory = sqlite3.Row

        row = connection.execute(
            "SELECT * FROM workspaces WHERE id = ?",
            (workspace_id,)
        ).fetchone()

        return dict(row)

@app.post("/issues")
def create_issue(issue: IssueCreate):

    with sqlite3.connect(DATABASE) as connection:

        # Check whether the workspace exists.
        workspace = connection.execute(
            "SELECT id FROM workspaces WHERE id = ?",
            (issue.workspace_id,)
        ).fetchone()

        if workspace is None:
            raise HTTPException(
                status_code=404,
                detail="Workspace not found"
            )

        # Insert the new issue.
        cursor = connection.execute(
            """
            INSERT INTO issues (
                workspace_id,
                title,
                description,
                category,
                priority
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                issue.workspace_id,
                issue.title,
                issue.description,
                issue.category,
                issue.priority
            )
        )

        issue_id = cursor.lastrowid

        # Retrieve the saved issue.
        connection.row_factory = sqlite3.Row

        row = connection.execute(
            "SELECT * FROM issues WHERE id = ?",
            (issue_id,)
        ).fetchone()

        return dict(row)

@app.get("/workspaces/{workspace_id}/issues")
def get_workspace_issues(workspace_id: int, status: str | None = None):

    allowed_statuses = {
        "Open",
        "Investigating",
        "Action Required",
        "Resolved",
        "Verified"
    }

    if status is not None and status not in allowed_statuses:
        raise HTTPException(
            status_code=422,
            detail="Invalid status"
        )

    with sqlite3.connect(DATABASE) as connection:
        connection.row_factory = sqlite3.Row

        workspace = connection.execute(
            "SELECT id FROM workspaces WHERE id = ?",
            (workspace_id,)
        ).fetchone()

        if workspace is None:
            raise HTTPException(
                status_code=404,
                detail="Workspace not found"
            )

        query = """
            SELECT * FROM issues
            WHERE workspace_id = ?
        """
        parameters = [workspace_id]

        if status is not None:
            query += " AND status = ?"
            parameters.append(status)

        query += " ORDER BY created_at DESC, id DESC"

        rows = connection.execute(
            query,
            parameters
        ).fetchall()

        return [dict(row) for row in rows]


@app.post("/issues/{issue_id}/investigations")
def create_investigation(issue_id: int, investigation: InvestigationCreate):

    with sqlite3.connect(DATABASE) as connection:
        connection.row_factory = sqlite3.Row

        issue = connection.execute(
            "SELECT id FROM issues WHERE id = ?",
            (issue_id,)
        ).fetchone()

        if issue is None:
            raise HTTPException(
                status_code=404,
                detail="Issue not found"
            )

        cursor = connection.execute(
            """
            INSERT INTO investigation_records (
                issue_id,
                notes,
                finding,
                possible_cause
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                issue_id,
                investigation.notes,
                investigation.finding,
                investigation.possible_cause
            )
        )

        connection.commit()

        row = connection.execute(
            """
            SELECT * FROM investigation_records
            WHERE id = ?
            """,
            (cursor.lastrowid,)
        ).fetchone()

        return dict(row)


@app.get("/issues/{issue_id}/investigations")
def get_issue_investigations(issue_id: int):

    with sqlite3.connect(DATABASE) as connection:
        connection.row_factory = sqlite3.Row

        issue = connection.execute(
            "SELECT id FROM issues WHERE id = ?",
            (issue_id,)
        ).fetchone()

        if issue is None:
            raise HTTPException(
                status_code=404,
                detail="Issue not found"
            )

        rows = connection.execute(
            """
            SELECT * FROM investigation_records
            WHERE issue_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (issue_id,)
        ).fetchall()

        return [dict(row) for row in rows]


@app.get("/investigations/{investigation_id}")
def get_investigation(investigation_id: int):

    with sqlite3.connect(DATABASE) as connection:
        connection.row_factory = sqlite3.Row

        investigation = connection.execute(
            """
            SELECT * FROM investigation_records
            WHERE id = ?
            """,
            (investigation_id,)
        ).fetchone()

        if investigation is None:
            raise HTTPException(
                status_code=404,
                detail="Investigation record not found"
            )

        return dict(investigation)


def _detect_evidence_type(content: bytes) -> tuple[str, str] | None:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if content.startswith(b"%PDF-"):
        return "application/pdf", ".pdf"
    return None


def _remove_evidence_file(path: Path | None) -> None:
    if path is not None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


@app.post("/investigations/{investigation_id}/evidence")
async def upload_investigation_evidence(
    investigation_id: int,
    file: UploadFile = File(...)
):
    with sqlite3.connect(DATABASE) as connection:
        investigation = connection.execute(
            "SELECT id FROM investigation_records WHERE id = ?",
            (investigation_id,)
        ).fetchone()

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation record not found"
        )

    original_filename = file.filename or ""
    extension = original_filename.rsplit(".", 1)[-1].lower()
    if "." not in original_filename or extension not in {
        "jpg", "jpeg", "png", "pdf"
    }:
        raise HTTPException(
            status_code=415,
            detail="Unsupported evidence file type"
        )

    content = bytearray()
    try:
        while True:
            chunk = await file.read(64 * 1024)
            if not chunk:
                break
            content.extend(chunk)
            if len(content) > MAX_EVIDENCE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail="Evidence file exceeds the 5 MB limit"
                )
    finally:
        await file.close()

    if not content:
        raise HTTPException(status_code=400, detail="Evidence file is empty")

    detected_type = _detect_evidence_type(content)
    if detected_type is None:
        raise HTTPException(
            status_code=415,
            detail="Unsupported evidence file content"
        )

    file_type, stored_extension = detected_type
    expected_extensions = {
        "image/jpeg": {"jpg", "jpeg"},
        "image/png": {"png"},
        "application/pdf": {"pdf"}
    }
    if extension not in expected_extensions[file_type]:
        raise HTTPException(
            status_code=415,
            detail="File extension does not match its content"
        )

    stored_filename = f"{uuid4().hex}{stored_extension}"
    stored_path = EVIDENCE_STORAGE_DIR / stored_filename

    try:
        EVIDENCE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        with stored_path.open("xb") as evidence_file:
            evidence_file.write(content)

        with sqlite3.connect(DATABASE) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            investigation = connection.execute(
                "SELECT id FROM investigation_records WHERE id = ?",
                (investigation_id,)
            ).fetchone()
            if investigation is None:
                raise HTTPException(
                    status_code=404,
                    detail="Investigation record not found"
                )

            cursor = connection.execute(
                """
                INSERT INTO evidence (
                    investigation_id,
                    original_filename,
                    stored_filename,
                    file_type,
                    file_size
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    investigation_id,
                    original_filename,
                    stored_filename,
                    file_type,
                    len(content)
                )
            )
            connection.commit()

            row = connection.execute(
                "SELECT * FROM evidence WHERE id = ?",
                (cursor.lastrowid,)
            ).fetchone()

        return dict(row)
    except HTTPException:
        _remove_evidence_file(stored_path)
        raise
    except OSError:
        _remove_evidence_file(stored_path)
        raise HTTPException(
            status_code=500,
            detail="Unable to store evidence file"
        ) from None
    except sqlite3.Error:
        _remove_evidence_file(stored_path)
        raise HTTPException(
            status_code=500,
            detail="Unable to save evidence metadata"
        ) from None


@app.get("/investigations/{investigation_id}/evidence")
def get_investigation_evidence(investigation_id: int):
    with sqlite3.connect(DATABASE) as connection:
        connection.row_factory = sqlite3.Row
        investigation = connection.execute(
            "SELECT id FROM investigation_records WHERE id = ?",
            (investigation_id,)
        ).fetchone()

        if investigation is None:
            raise HTTPException(
                status_code=404,
                detail="Investigation record not found"
            )

        rows = connection.execute(
            """
            SELECT * FROM evidence
            WHERE investigation_id = ?
            ORDER BY uploaded_at ASC, id ASC
            """,
            (investigation_id,)
        ).fetchall()
        return [dict(row) for row in rows]


@app.get("/issues/{issue_id}")
def get_issue(issue_id: int):

    with sqlite3.connect(DATABASE) as connection:
        connection.row_factory = sqlite3.Row

        row = connection.execute(
            "SELECT * FROM issues WHERE id = ?",
            (issue_id,)
        ).fetchone()

        if row is None:
            raise HTTPException(
                status_code=404,
                detail="Issue not found"
            )

        return dict(row)

@app.put("/issues/{issue_id}")

def update_issue(issue_id: int, update: IssueUpdate):

    changes = update.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=422,
            detail="Provide at least one field to update"
        )

    with sqlite3.connect(DATABASE) as connection:
        connection.row_factory = sqlite3.Row

        existing_issue = connection.execute(
            "SELECT * FROM issues WHERE id = ?",
            (issue_id,)
        ).fetchone()

        if existing_issue is None:
            raise HTTPException(
                status_code=404,
                detail="Issue not found"
            )

        # Check whether the requested status transition is allowed.
        if "status" in changes:
            current_status = existing_issue["status"]
            new_status = changes["status"]

            if new_status is None:
                raise HTTPException(
                    status_code=422,
                    detail="Status cannot be empty"
                )

            if (
                new_status != current_status
                and new_status not in ISSUE_STATUS_TRANSITIONS[current_status]
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot change status from "
                           f"'{current_status}' to '{new_status}'"
                )

        for field, value in changes.items():
            connection.execute(
                f"UPDATE issues SET {field} = ?, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (value, issue_id)
            )

        row = connection.execute(
            "SELECT * FROM issues WHERE id = ?",
            (issue_id,)
        ).fetchone()

        return dict(row)
ISSUE_STATUS_TRANSITIONS = {
    "Open": {"Investigating"},
    "Investigating": {"Action Required", "Resolved"},
    "Action Required": {"Investigating", "Resolved"},
    "Resolved": {"Investigating"},
    "Verified": set()
}
@app.get("/")
def home():
    return {"message": "Welcome to IssueFlow!"}


@app.get("/tasks")
def get_tasks():
    with sqlite3.connect(DATABASE) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM tasks"
        ).fetchall()

        return [dict(row) for row in rows]


@app.post("/tasks")
def create_task(task: TaskCreate):
    with sqlite3.connect(DATABASE) as connection:
        cursor = connection.execute(
            """
            INSERT INTO tasks (title, priority, due_date)
            VALUES (?, ?, ?)
            """,
            (task.title, task.priority, task.due_date)
        )

        task_id = cursor.lastrowid

        connection.row_factory = sqlite3.Row

        row = connection.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,)
        ).fetchone()

        return dict(row)


@app.put("/tasks/{task_id}")
def update_task(task_id: int, update: TaskUpdate):
    changes = update.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=422,
            detail="Provide a status or priority to update"
        )

    with sqlite3.connect(DATABASE) as connection:
        connection.row_factory = sqlite3.Row

        existing_task = connection.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,)
        ).fetchone()

        if existing_task is None:
            raise HTTPException(
                status_code=404,
                detail="Task not found"
            )

        for field, value in changes.items():
            connection.execute(
                f"UPDATE tasks SET {field} = ? WHERE id = ?",
                (value, task_id)
            )

        row = connection.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,)
        ).fetchone()

        return dict(row)



@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    with sqlite3.connect(DATABASE) as connection:
        cursor = connection.execute(
            "DELETE FROM tasks WHERE id = ?",
            (task_id,)
        )

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Task not found"
            )

        return {"message": "Task deleted successfully"}

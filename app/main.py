from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
import sqlite3
from typing import Literal
from fastapi.middleware.cors import CORSMiddleware

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
def get_workspace_issues(workspace_id: int):

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

        rows = connection.execute(
            """
            SELECT * FROM issues
            WHERE workspace_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (workspace_id,)
        ).fetchall()

        return [dict(row) for row in rows]

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
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
        connection.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'To Do',
                priority TEXT NOT NULL DEFAULT 'Medium',
                due_date TEXT
            )
        """)

        # Check which columns already exist.
        columns = connection.execute(
            "PRAGMA table_info(tasks)"
        ).fetchall()

        column_names = [column[1] for column in columns]

        # Migrate existing databases if necessary.
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


init_db()


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
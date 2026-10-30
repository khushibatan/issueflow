
const API_URL = "http://127.0.0.1:8000";

const taskForm = document.getElementById("task-form");
const taskTitle = document.getElementById("task-title");
const taskPriority = document.getElementById("task-priority");
const taskDueDate = document.getElementById("task-due-date");
const taskList = document.getElementById("task-list");
const formMessage = document.getElementById("form-message");
const statusFilter = document.getElementById("status-filter");
const searchInput = document.getElementById("search-input");

const totalCount = document.getElementById("total-count");
const todoCount = document.getElementById("todo-count");
const progressCount = document.getElementById("progress-count");
const doneCount = document.getElementById("done-count");

let tasks = [];

// Show today's date.
document.getElementById("today-date").textContent =
    new Date().toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric"
    });

// Fetch tasks from the backend.
async function loadTasks() {
    try {
        const response = await fetch(`${API_URL}/tasks`);

        if (!response.ok) {
            throw new Error("Could not load tasks.");
        }

        tasks = await response.json();
        renderTasks();
    } catch (error) {
        taskList.replaceChildren();

        const message = document.createElement("p");
        message.className = "empty-state";
        message.textContent =
            "Could not connect to the backend. Make sure your FastAPI server is running.";

        taskList.appendChild(message);
    }
}

// Display tasks and update summary cards.
function renderTasks() {
    // Summary cards always show counts for all tasks.
    totalCount.textContent = tasks.length;

    todoCount.textContent =
        tasks.filter(task => task.status === "To Do").length;

    progressCount.textContent =
        tasks.filter(task => task.status === "In Progress").length;

    doneCount.textContent =
        tasks.filter(task => task.status === "Done").length;

    // Read the selected status and search text.
    const selectedStatus = statusFilter.value;
    const searchText = searchInput.value.trim().toLowerCase();

    // Apply both filters together.
    const filteredTasks = tasks.filter(task => {
        const matchesStatus =
            selectedStatus === "All" ||
            task.status === selectedStatus;

        const matchesSearch =
            task.title.toLowerCase().includes(searchText);

        return matchesStatus && matchesSearch;
    });

    taskList.replaceChildren();

    // Show a message if no tasks match.
    if (filteredTasks.length === 0) {
        const emptyMessage = document.createElement("p");
        emptyMessage.className = "empty-state";

        if (tasks.length === 0) {
            emptyMessage.textContent =
                "No tasks yet. Add your first task above!";
        } else {
            emptyMessage.textContent =
                "No tasks match your search or filter.";
        }

        taskList.appendChild(emptyMessage);
        return;
    }

    // Create a card for each matching task.
    filteredTasks.forEach(task => {
        const item = document.createElement("article");
        item.className = "task-item";

        const details = document.createElement("div");
        details.className = "task-details";

        const title = document.createElement("h3");
        title.textContent = task.title;

    const dueDate = document.createElement("p");
dueDate.className = "task-due-date";

if (task.due_date) {
    const today = new Date();
    const todayString = [
        today.getFullYear(),
        String(today.getMonth() + 1).padStart(2, "0"),
        String(today.getDate()).padStart(2, "0")
    ].join("-");

    const isOverdue =
        task.due_date < todayString && task.status !== "Done";

    if (isOverdue) {
        dueDate.textContent = `Overdue · Due: ${task.due_date}`;
        dueDate.classList.add("overdue");
    } else {
        dueDate.textContent = `Due: ${task.due_date}`;
    }
} else {
    dueDate.textContent = "No due date";
}

        const meta = document.createElement("div");
        meta.className = "task-meta";

        const priority = document.createElement("span");
        priority.className =
            `badge priority-${task.priority.toLowerCase()}`;
        priority.textContent = `${task.priority} priority`;

        const statusBadge = document.createElement("span");
        statusBadge.className = "badge status-badge";
        statusBadge.textContent = task.status;

        meta.append(priority, statusBadge);
        details.append(title, meta, dueDate);

        const actions = document.createElement("div");
        actions.className = "task-actions";

        // Status dropdown.
        const statusSelect = document.createElement("select");

        statusSelect.setAttribute(
            "aria-label",
            `Change status for ${task.title}`
        );

        ["To Do", "In Progress", "Done"].forEach(status => {
            const option = document.createElement("option");

            option.value = status;
            option.textContent = status;
            option.selected = task.status === status;

            statusSelect.appendChild(option);
        });

        statusSelect.addEventListener("change", async () => {
            await updateTask(task.id, {
                status: statusSelect.value
            });
        });

        // Delete button.
        const deleteButton = document.createElement("button");

        deleteButton.type = "button";
        deleteButton.className = "delete-button";
        deleteButton.textContent = "Delete";

        deleteButton.addEventListener("click", async () => {
            await deleteTask(task.id);
        });

        actions.append(statusSelect, deleteButton);
        item.append(details, actions);
        taskList.appendChild(item);
    });
}

// Create a new task.
taskForm.addEventListener("submit", async event => {
    event.preventDefault();

    const title = taskTitle.value.trim();

    if (!title) {
        formMessage.textContent = "Please enter a task title.";
        return;
    }

    const addButton = document.getElementById("add-task-button");

    addButton.disabled = true;
    formMessage.textContent = "Adding task...";

    try {
        const response = await fetch(`${API_URL}/tasks`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                title: title,
                priority: taskPriority.value,
                due_date: taskDueDate.value || null
            })
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(
                result.detail?.[0]?.msg ||
                result.detail ||
                "Could not add task."
            );
        }

        taskForm.reset();
        formMessage.textContent = "Task added successfully!";

        // Reset filters so the new task is visible.
        statusFilter.value = "All";
        searchInput.value = "";

        await loadTasks();
    } catch (error) {
        formMessage.textContent =
            `Error: ${error.message}. Is the backend running?`;
    } finally {
        addButton.disabled = false;
    }
});

// Update a task's status or priority.
async function updateTask(taskId, changes) {
    try {
        const response = await fetch(`${API_URL}/tasks/${taskId}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(changes)
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(
                result.detail?.[0]?.msg ||
                result.detail ||
                "Could not update task."
            );
        }

        formMessage.textContent = "Task updated successfully!";

        await loadTasks();
    } catch (error) {
        formMessage.textContent = `Error: ${error.message}`;
        await loadTasks();
    }
}

// Delete a task.
async function deleteTask(taskId) {
    const confirmed = window.confirm(
        "Are you sure you want to delete this task?"
    );

    if (!confirmed) {
        return;
    }

    try {
        const response = await fetch(`${API_URL}/tasks/${taskId}`, {
            method: "DELETE"
        });

        if (!response.ok) {
            const result = await response.json();
            throw new Error(
                result.detail || "Could not delete task."
            );
        }

        formMessage.textContent = "Task deleted successfully!";

        await loadTasks();
    } catch (error) {
        formMessage.textContent = `Error: ${error.message}`;
    }
}

// Filter tasks by status.
statusFilter.addEventListener("change", renderTasks);

// Search tasks immediately as the user types.
searchInput.addEventListener("input", renderTasks);

// Load saved tasks when the page opens.
loadTasks();

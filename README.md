# IssueFlow

**Clear issues. Better investigations.**

## About

IssueFlow is a workspace-based issue management and investigation platform that helps teams report, track, investigate, and resolve organisational issues.

Designed to be adaptable across different types of teams and organisations, IssueFlow provides a centralised way to manage reported problems, monitor their progress, and document investigation findings.

## Features

- Create and manage workspaces
- Report issues with a title, description, category, and priority
- Track issue status and dashboard statistics
- Search issues and filter by status or priority
- View detailed issue information
- Record investigation notes, findings, and possible causes
- Backend support for uploading JPEG, PNG, and PDF evidence files up to 5 MB
- Light and dark themes
- Responsive user interface

## Tech Stack

- Python
- FastAPI
- SQLite
- HTML5
- CSS3
- JavaScript (Vanilla)

## Issue Lifecycle

| Current Status | Allowed Next Status |
|---|---|
| Open | Investigating |
| Investigating | Action Required, Resolved |
| Action Required | Investigating, Resolved |
| Resolved | Investigating |
| Verified | Terminal state |

**Note:** The current API accepts `Open`, `Investigating`, `Action Required`, and `Resolved` as update targets. `Verified` is supported as a stored and displayed status but cannot currently be set through the update endpoint.

## Project Structure

```text
IssueFlow/
├── app/
│   ├── __init__.py
│   └── main.py
├── frontend/
│   ├── index.html
│   ├── script.js
│   └── style.css
├── requirements.txt
└── test_main.py    
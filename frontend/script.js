const API_URL = "http://127.0.0.1:8000";

const STATUS_TRANSITIONS = {
    Open: ["Investigating"],
    Investigating: ["Action Required", "Resolved"],
    "Action Required": ["Investigating", "Resolved"],
    Resolved: ["Investigating"],
    Verified: []
};

const THEME_STORAGE_KEY = "issueflow-theme";

const elements = {
    workspaceSelect: document.getElementById("workspace-select"),
    createWorkspaceButton: document.getElementById("create-workspace-button"),
    themeToggle: document.getElementById("theme-toggle"),
    openIssueFormButton: document.getElementById("open-issue-form-button"),
    currentDate: document.getElementById("current-date"),
    totalIssues: document.getElementById("total-issues"),
    openIssues: document.getElementById("open-issues"),
    investigatingIssues: document.getElementById("investigating-issues"),
    actionRequiredIssues: document.getElementById("action-required-issues"),
    resolvedIssues: document.getElementById("resolved-issues"),
    issueForm: document.getElementById("issue-form"),
    issueTitle: document.getElementById("issue-title"),
    issueDescription: document.getElementById("issue-description"),
    issueCategory: document.getElementById("issue-category"),
    issuePriority: document.getElementById("issue-priority"),
    issueFormMessage: document.getElementById("issue-form-message"),
    issueSearch: document.getElementById("issue-search"),
    issueStatusFilter: document.getElementById("issue-status-filter"),
    issuePriorityFilter: document.getElementById("issue-priority-filter"),
    issueList: document.getElementById("issue-list"),
    issueDetailPanel: document.getElementById("issue-detail-panel"),
    issueDetailTitle: document.getElementById("issue-detail-title"),
    issueDetailDescription: document.getElementById("issue-detail-description"),
    issueDetailCategory: document.getElementById("issue-detail-category"),
    issueDetailPriority: document.getElementById("issue-detail-priority"),
    issueDetailStatus: document.getElementById("issue-detail-status"),
    investigationList: document.getElementById("investigation-list"),
    investigationForm: document.getElementById("investigation-form"),
    investigationNotes: document.getElementById("investigation-notes"),
    investigationFinding: document.getElementById("investigation-finding"),
    investigationCause: document.getElementById("investigation-cause"),
    investigationMessage: document.getElementById("investigation-message")
};

let workspaces = [];
let issues = [];
let selectedIssueId = null;
let issueLoadError = "";
let workspaceRequestNumber = 0;
let issueRequestNumber = 0;
let detailRequestNumber = 0;
let statusMessage;
let statusSelect;

async function requestJSON(path, options = {}) {
    let response;

    try {
        response = await fetch(`${API_URL}${path}`, options);
    } catch {
        throw new Error("Could not connect to the IssueFlow backend.");
    }

    let result = null;
    try {
        result = await response.json();
    } catch {
        result = null;
    }

    if (!response.ok) {
        const detail = result && result.detail;
        const message = Array.isArray(detail)
            ? detail.map(item => item.msg).filter(Boolean).join(" ")
            : detail;
        throw new Error(message || `Request failed (${response.status}).`);
    }

    return result;
}

function setMessage(element, message) {
    if (element) {
        element.textContent = message;
    }
}

function applyTheme(theme, savePreference = true) {
    const selectedTheme = theme === "dark" ? "dark" : "light";
    const isDark = selectedTheme === "dark";
    document.documentElement.dataset.theme = selectedTheme;

    if (elements.themeToggle) {
        const icon = elements.themeToggle.querySelector(".theme-toggle-icon");
        const label = elements.themeToggle.querySelector(".theme-toggle-label");
        const nextTheme = isDark ? "light" : "dark";
        const toggleLabel = `Switch to ${nextTheme} theme`;

        elements.themeToggle.setAttribute("aria-label", toggleLabel);
        elements.themeToggle.setAttribute("aria-pressed", String(isDark));
        elements.themeToggle.title = toggleLabel;
        if (icon) icon.textContent = isDark ? "☀" : "☾";
        if (label) label.textContent = toggleLabel;
    }

    const themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) {
        themeColor.content = getComputedStyle(document.documentElement)
            .getPropertyValue("--background")
            .trim();
    }

    if (savePreference) {
        try {
            window.localStorage.setItem(THEME_STORAGE_KEY, selectedTheme);
        } catch (error) {
            console.warn("Could not save the IssueFlow theme preference.", error);
        }
    }
}

function initializeTheme() {
    let savedTheme = "light";
    try {
        savedTheme = window.localStorage.getItem(THEME_STORAGE_KEY) === "dark"
            ? "dark"
            : "light";
    } catch (error) {
        console.warn("Could not read the saved IssueFlow theme preference.", error);
    }

    applyTheme(savedTheme, false);

    if (elements.themeToggle) {
        elements.themeToggle.addEventListener("click", () => {
            const currentTheme = document.documentElement.dataset.theme;
            applyTheme(currentTheme === "dark" ? "light" : "dark");
        });
    }
}

function setSummaryCounts(issueItems) {
    const counts = {
        total: issueItems.length,
        open: issueItems.filter(issue => issue.status === "Open").length,
        investigating: issueItems.filter(issue => issue.status === "Investigating").length,
        actionRequired: issueItems.filter(issue => issue.status === "Action Required").length,
        resolved: issueItems.filter(issue => issue.status === "Resolved").length
    };

    if (elements.totalIssues) elements.totalIssues.textContent = counts.total;
    if (elements.openIssues) elements.openIssues.textContent = counts.open;
    if (elements.investigatingIssues) elements.investigatingIssues.textContent = counts.investigating;
    if (elements.actionRequiredIssues) elements.actionRequiredIssues.textContent = counts.actionRequired;
    if (elements.resolvedIssues) elements.resolvedIssues.textContent = counts.resolved;
}

function showEmptyMessage(container, heading, description) {
    if (!container) return;

    const emptyState = document.createElement("div");
    emptyState.className = "empty-state";

    const title = document.createElement("h3");
    title.textContent = heading;
    const message = document.createElement("p");
    message.textContent = description;

    emptyState.append(title, message);
    container.replaceChildren(emptyState);
}

function createBadge(label, type, variant) {
    const badge = document.createElement("span");
    badge.textContent = label;
    badge.className = `issue-badge issue-badge-${type}`;
    if (variant) badge.classList.add(`is-${variant}`);
    return badge;
}

function formatDate(value) {
    if (!value) return "Date unavailable";

    const date = new Date(value.includes("T") ? value : value.replace(" ", "T"));
    if (Number.isNaN(date.getTime())) return value;

    return new Intl.DateTimeFormat(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric"
    }).format(date);
}

function renderIssues() {
    if (!elements.issueList) return;
    setSummaryCounts(issues);

    if (!elements.workspaceSelect || !elements.workspaceSelect.value) {
        showEmptyMessage(
            elements.issueList,
            "No workspace selected",
            "Create or select a workspace to view its issues."
        );
        return;
    }

    if (issueLoadError) {
        showEmptyMessage(elements.issueList, "Issues could not be loaded", issueLoadError);
        return;
    }

    const searchText = elements.issueSearch
        ? elements.issueSearch.value.trim().toLocaleLowerCase()
        : "";
    const selectedStatus = elements.issueStatusFilter
        ? elements.issueStatusFilter.value
        : "";
    const selectedPriority = elements.issuePriorityFilter
        ? elements.issuePriorityFilter.value
        : "";

    const filteredIssues = issues.filter(issue => {
        const searchableText = `${issue.title || ""} ${issue.description || ""}`.toLocaleLowerCase();
        return (
            (!searchText || searchableText.includes(searchText)) &&
            (!selectedStatus || issue.status === selectedStatus) &&
            (!selectedPriority || issue.priority === selectedPriority)
        );
    });

    if (filteredIssues.length === 0) {
        if (issues.length === 0) {
            showEmptyMessage(
                elements.issueList,
                "No issues yet",
                "Create an issue to start tracking an investigation."
            );
        } else {
            showEmptyMessage(
                elements.issueList,
                "No matching issues",
                "Try changing your search or filters."
            );
        }
        return;
    }

    const cards = filteredIssues.map(issue => {
        const card = document.createElement("article");
        card.className = "panel";
        card.style.marginBottom = "0";

        const heading = document.createElement("div");
        heading.className = "panel-heading";
        const title = document.createElement("h2");
        title.textContent = issue.title;
        heading.append(title);

        const description = document.createElement("p");
        description.className = "panel-description";
        description.textContent = issue.description || "No description provided.";

        const metadata = document.createElement("div");
        metadata.style.display = "flex";
        metadata.style.flexWrap = "wrap";
        metadata.style.alignItems = "center";
        metadata.style.gap = "8px";
        metadata.style.marginTop = "12px";
        const priority = issue.priority || "Medium";
        const status = issue.status || "Open";
        metadata.append(
            createBadge(issue.category || "General", "category"),
            createBadge(priority, "priority", priority.toLowerCase()),
            createBadge(status, "status", status.toLowerCase().replace(/\s+/g, "-"))
        );

        const created = document.createElement("p");
        created.className = "panel-description";
        created.style.marginTop = "10px";
        created.textContent = `Created ${formatDate(issue.created_at)}`;

        const openButton = document.createElement("button");
        openButton.type = "button";
        openButton.className = "button button-secondary";
        openButton.textContent = "View details";
        openButton.style.marginTop = "12px";
        openButton.addEventListener("click", () => loadIssueDetails(issue.id));

        card.append(heading, description, metadata, created, openButton);
        return card;
    });

    elements.issueList.replaceChildren(...cards);
}

async function loadWorkspaces(selectId) {
    if (!elements.workspaceSelect) return;
    const requestNumber = ++workspaceRequestNumber;
    const previousSelection = elements.workspaceSelect.value;

    try {
        const result = await requestJSON("/workspaces");
        if (requestNumber !== workspaceRequestNumber) return;

        workspaces = Array.isArray(result) ? result : [];
        const fragment = document.createDocumentFragment();
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "Select a workspace";
        fragment.append(placeholder);

        workspaces.forEach(workspace => {
            const option = document.createElement("option");
            option.value = String(workspace.id);
            option.textContent = workspace.name;
            fragment.append(option);
        });
        elements.workspaceSelect.replaceChildren(fragment);

        const preferred = selectId == null ? previousSelection : String(selectId);
        const preferredExists = workspaces.some(workspace => String(workspace.id) === preferred);
        elements.workspaceSelect.value = preferredExists
            ? preferred
            : workspaces.length
                ? String(workspaces[0].id)
                : "";

        if (elements.workspaceSelect.value) {
            await loadIssues(elements.workspaceSelect.value);
        } else {
            issues = [];
            issueLoadError = "";
            setSummaryCounts(issues);
            showEmptyMessage(
                elements.issueList,
                "No workspaces yet",
                "Create a workspace to start managing issues."
            );
        }
    } catch (error) {
        if (requestNumber !== workspaceRequestNumber) return;
        workspaces = [];
        issues = [];
        elements.workspaceSelect.replaceChildren();
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "Workspaces unavailable";
        elements.workspaceSelect.append(placeholder);
        setSummaryCounts(issues);
        showEmptyMessage(elements.issueList, "Workspaces could not be loaded", error.message);
    }
}

async function loadIssues(workspaceId) {
    if (!workspaceId) {
        issues = [];
        issueLoadError = "";
        renderIssues();
        return;
    }

    const requestNumber = ++issueRequestNumber;
    try {
        const result = await requestJSON(`/workspaces/${encodeURIComponent(workspaceId)}/issues`);
        if (
            requestNumber !== issueRequestNumber ||
            String(elements.workspaceSelect.value) !== String(workspaceId)
        ) {
            return;
        }
        issues = Array.isArray(result) ? result : [];
        issueLoadError = "";
    } catch (error) {
        if (requestNumber !== issueRequestNumber) return;
        issues = [];
        issueLoadError = error.message;
    }
    renderIssues();
}

function setupDetailPanel() {
    if (!elements.issueDetailPanel) return;

    const heading = elements.issueDetailPanel.querySelector(".detail-heading");
    const summary = elements.issueDetailPanel.querySelector(".detail-summary");
    if (!heading || !summary) return;

    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.className = "button button-secondary";
    closeButton.textContent = "Close";
    closeButton.setAttribute("aria-label", "Close issue details");
    closeButton.addEventListener("click", closeDetailPanel);
    heading.append(closeButton);

    const controls = document.createElement("div");
    controls.style.display = "flex";
    controls.style.flexWrap = "wrap";
    controls.style.alignItems = "center";
    controls.style.gap = "10px";
    controls.style.marginTop = "14px";

    const label = document.createElement("label");
    label.htmlFor = "issue-status-update";
    label.textContent = "Update status";

    statusSelect = document.createElement("select");
    statusSelect.id = "issue-status-update";
    statusSelect.style.width = "auto";
    statusSelect.addEventListener("change", updateIssueStatus);

    statusMessage = document.createElement("p");
    statusMessage.className = "form-message";
    statusMessage.setAttribute("role", "status");
    statusMessage.setAttribute("aria-live", "polite");

    controls.append(label, statusSelect, statusMessage);
    summary.append(controls);
}

function closeDetailPanel() {
    selectedIssueId = null;
    if (elements.issueDetailPanel) elements.issueDetailPanel.hidden = true;
    if (elements.investigationForm) elements.investigationForm.reset();
    setMessage(elements.investigationMessage, "");
}

function renderStatusChoices(status) {
    if (!statusSelect) return;

    statusSelect.replaceChildren();
    const transitions = STATUS_TRANSITIONS[status] || [];
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = transitions.length ? "Choose next status" : "No further transitions";
    placeholder.selected = true;
    statusSelect.append(placeholder);
    statusSelect.disabled = transitions.length === 0;

    transitions.forEach(nextStatus => {
        const option = document.createElement("option");
        option.value = nextStatus;
        option.textContent = nextStatus;
        statusSelect.append(option);
    });
}

async function loadIssueDetails(issueId) {
    if (!elements.issueDetailPanel) return;
    selectedIssueId = issueId;
    const requestNumber = ++detailRequestNumber;
    elements.issueDetailPanel.hidden = false;
    elements.issueDetailPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    setMessage(statusMessage, "Loading issue details...");
    setMessage(elements.investigationMessage, "");

    try {
        const [issue, investigations] = await Promise.all([
            requestJSON(`/issues/${encodeURIComponent(issueId)}`),
            requestJSON(`/issues/${encodeURIComponent(issueId)}/investigations`)
        ]);
        if (requestNumber !== detailRequestNumber || selectedIssueId !== issueId) return;

        elements.issueDetailTitle.textContent = issue.title;
        elements.issueDetailDescription.textContent = issue.description || "No description provided.";
        elements.issueDetailCategory.textContent = issue.category || "General";
        elements.issueDetailPriority.textContent = issue.priority;
        elements.issueDetailStatus.textContent = issue.status;
        renderStatusChoices(issue.status);
        setMessage(statusMessage, "");
        renderInvestigations(investigations);
    } catch (error) {
        if (requestNumber !== detailRequestNumber) return;
        elements.issueDetailTitle.textContent = "Issue details unavailable";
        elements.issueDetailDescription.textContent = error.message;
        elements.issueDetailCategory.textContent = "";
        elements.issueDetailPriority.textContent = "";
        elements.issueDetailStatus.textContent = "";
        renderStatusChoices("Verified");
        showEmptyMessage(
            elements.investigationList,
            "Investigation history unavailable",
            error.message
        );
        setMessage(statusMessage, error.message);
    }
}

function renderInvestigations(records) {
    if (!elements.investigationList) return;
    if (!Array.isArray(records) || records.length === 0) {
        showEmptyMessage(
            elements.investigationList,
            "No investigation records yet",
            "Add notes below to record the investigation."
        );
        return;
    }

    const entries = records.map(record => {
        const entry = document.createElement("article");
        entry.className = "panel";
        entry.style.marginBottom = "0";

        const date = document.createElement("p");
        date.className = "eyebrow";
        date.textContent = formatDate(record.created_at);

        const notes = document.createElement("p");
        notes.textContent = record.notes;
        notes.style.whiteSpace = "pre-wrap";

        entry.append(date, notes);

        if (record.finding) {
            const finding = document.createElement("p");
            finding.textContent = `Finding: ${record.finding}`;
            finding.style.whiteSpace = "pre-wrap";
            entry.append(finding);
        }

        if (record.possible_cause) {
            const cause = document.createElement("p");
            cause.textContent = `Possible cause: ${record.possible_cause}`;
            cause.style.whiteSpace = "pre-wrap";
            entry.append(cause);
        }
        return entry;
    });

    elements.investigationList.replaceChildren(...entries);
}

async function updateIssueStatus(event) {
    const nextStatus = event.target.value;
    if (!selectedIssueId || !nextStatus) return;

    const currentIssue = issues.find(issue => issue.id === selectedIssueId);
    const allowedTransitions = currentIssue
        ? STATUS_TRANSITIONS[currentIssue.status] || []
        : [];
    if (!allowedTransitions.includes(nextStatus)) {
        setMessage(statusMessage, "That status transition is not available.");
        if (currentIssue) renderStatusChoices(currentIssue.status);
        return;
    }

    statusSelect.disabled = true;
    setMessage(statusMessage, "Updating status...");
    try {
        await requestJSON(`/issues/${encodeURIComponent(selectedIssueId)}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: nextStatus })
        });
        await loadIssues(elements.workspaceSelect.value);
        await loadIssueDetails(selectedIssueId);
        setMessage(statusMessage, "Issue status updated.");
    } catch (error) {
        setMessage(statusMessage, error.message);
        if (currentIssue) {
            statusSelect.disabled = false;
            renderStatusChoices(currentIssue.status);
        }
    }
}

async function createWorkspace() {
    const name = window.prompt("Enter a name for the new workspace:");
    if (name === null) return;
    if (!name.trim()) {
        setMessage(elements.issueFormMessage, "Workspace name cannot be blank.");
        return;
    }

    elements.createWorkspaceButton.disabled = true;
    setMessage(elements.issueFormMessage, "Creating workspace...");
    try {
        const workspace = await requestJSON("/workspaces", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: name.trim() })
        });
        closeDetailPanel();
        await loadWorkspaces(workspace.id);
        setMessage(elements.issueFormMessage, "Workspace created successfully.");
    } catch (error) {
        setMessage(elements.issueFormMessage, error.message);
    } finally {
        elements.createWorkspaceButton.disabled = false;
    }
}

async function createIssue(event) {
    event.preventDefault();
    const workspaceId = elements.workspaceSelect ? elements.workspaceSelect.value : "";
    const title = elements.issueTitle.value.trim();

    if (!workspaceId) {
        setMessage(elements.issueFormMessage, "Create or select a workspace first.");
        return;
    }
    if (!title) {
        setMessage(elements.issueFormMessage, "Enter an issue title.");
        elements.issueTitle.focus();
        return;
    }

    const submitButton = elements.issueForm.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;
    setMessage(elements.issueFormMessage, "Creating issue...");
    try {
        await requestJSON("/issues", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                workspace_id: Number(workspaceId),
                title,
                description: elements.issueDescription.value.trim(),
                category: elements.issueCategory.value.trim() || "General",
                priority: elements.issuePriority.value
            })
        });

        elements.issueForm.reset();
        elements.issueSearch.value = "";
        elements.issueStatusFilter.value = "";
        elements.issuePriorityFilter.value = "";
        setMessage(elements.issueFormMessage, "Issue created successfully.");
        await loadIssues(workspaceId);
    } catch (error) {
        setMessage(elements.issueFormMessage, error.message);
    } finally {
        if (submitButton) submitButton.disabled = false;
    }
}

async function createInvestigation(event) {
    event.preventDefault();
    if (!selectedIssueId) {
        setMessage(elements.investigationMessage, "Select an issue before adding an investigation.");
        return;
    }

    const notes = elements.investigationNotes.value.trim();
    if (!notes) {
        setMessage(elements.investigationMessage, "Investigation notes cannot be blank.");
        elements.investigationNotes.focus();
        return;
    }

    const submitButton = elements.investigationForm.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;
    setMessage(elements.investigationMessage, "Saving investigation...");
    try {
        const issueId = selectedIssueId;
        await requestJSON(`/issues/${encodeURIComponent(issueId)}/investigations`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                notes,
                finding: elements.investigationFinding.value.trim(),
                possible_cause: elements.investigationCause.value.trim()
            })
        });
        elements.investigationForm.reset();
        const updatedRecords = await requestJSON(`/issues/${encodeURIComponent(issueId)}/investigations`);
        if (selectedIssueId === issueId) renderInvestigations(updatedRecords);
        setMessage(elements.investigationMessage, "Investigation saved successfully.");
    } catch (error) {
        setMessage(elements.investigationMessage, error.message);
    } finally {
        if (submitButton) submitButton.disabled = false;
    }
}

function initializeDashboard() {
    initializeTheme();

    if (elements.currentDate) {
        const now = new Date();
        elements.currentDate.textContent = new Intl.DateTimeFormat(undefined, {
            day: "numeric",
            month: "short",
            year: "numeric"
        }).format(now);
        elements.currentDate.dateTime = now.toISOString().slice(0, 10);
    }

    setupDetailPanel();

    if (elements.workspaceSelect) {
        elements.workspaceSelect.addEventListener("change", () => {
            closeDetailPanel();
            loadIssues(elements.workspaceSelect.value);
        });
    }
    if (elements.createWorkspaceButton) {
        elements.createWorkspaceButton.addEventListener("click", createWorkspace);
    }
    if (elements.openIssueFormButton && elements.issueForm) {
        elements.openIssueFormButton.addEventListener("click", () => {
            elements.issueForm.scrollIntoView({ behavior: "smooth", block: "center" });
            elements.issueTitle.focus({ preventScroll: true });
        });
    }
    if (elements.issueForm) {
        elements.issueForm.addEventListener("submit", createIssue);
    }
    if (elements.issueSearch) {
        elements.issueSearch.addEventListener("input", renderIssues);
    }
    if (elements.issueStatusFilter) {
        elements.issueStatusFilter.addEventListener("change", renderIssues);
    }
    if (elements.issuePriorityFilter) {
        elements.issuePriorityFilter.addEventListener("change", renderIssues);
    }
    if (elements.investigationForm) {
        elements.investigationForm.addEventListener("submit", createInvestigation);
    }

    loadWorkspaces();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeDashboard, { once: true });
} else {
    initializeDashboard();
}

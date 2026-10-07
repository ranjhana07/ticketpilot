const state = {
  tickets: [],
  selectedId: null,
  detail: null,
  filter: "all",
  query: "",
  config: null,
};

const $ = (selector) => document.querySelector(selector);

const PRIORITY_CLASS = { urgent: "badge-bad", high: "badge-warn", normal: "", low: "badge-muted" };
const STATUS_LABEL = {
  new: "New",
  triaged: "Triaged",
  awaiting_approval: "Needs approval",
  awaiting_review: "Ready for review",
  escalated: "Escalated",
  replied: "Replied",
};
const STATUS_CLASS = {
  awaiting_approval: "badge-warn",
  awaiting_review: "badge-good",
  escalated: "badge-bad",
  replied: "badge-muted",
};
const DONE_STATUSES = new Set(["replied"]);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail);
    } catch (error) {
      detail = response.statusText;
    }
    throw new Error(detail);
  }
  return response.json();
}

function el(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

function badge(text, extraClass = "") {
  return el("span", { class: `badge ${extraClass}`.trim(), text });
}

function formatIntent(intent) {
  return intent ? intent.replaceAll("_", " ") : "unclassified";
}

function relativeTime(iso) {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (Number.isNaN(minutes)) return "";
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function toast(message, kind = "info") {
  const node = $("#toast");
  node.textContent = message;
  node.dataset.kind = kind;
  node.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => {
    node.hidden = true;
  }, 3500);
}

function matchesFilter(ticket) {
  const status = ticket.status;
  if (state.filter === "open" && DONE_STATUSES.has(status)) return false;
  if (state.filter === "awaiting_approval" && status !== "awaiting_approval") return false;
  if (state.filter === "awaiting_review" && status !== "awaiting_review") return false;
  if (state.filter === "done" && !DONE_STATUSES.has(status)) return false;
  if (!state.query) return true;
  const haystack = `${ticket.id} ${ticket.subject} ${ticket.customer_email} ${ticket.customer_name}`.toLowerCase();
  return haystack.includes(state.query.toLowerCase());
}

function renderQueue() {
  const list = $("#queue-list");
  list.replaceChildren();
  const visible = state.tickets.filter(matchesFilter);
  $("#queue-empty").hidden = visible.length > 0;
  for (const ticket of visible) {
    const triage = ticket.triage || {};
    const item = el(
      "button",
      {
        class: `queue-item${ticket.id === state.selectedId ? " is-selected" : ""}`,
        type: "button",
        "data-id": ticket.id,
        onclick: () => selectTicket(ticket.id),
      },
      el(
        "div",
        { class: "queue-row" },
        el("span", { class: "eyebrow", text: ticket.id }),
        el("span", { class: "muted small", text: relativeTime(ticket.created_at) }),
      ),
      el("div", { class: "queue-subject", text: ticket.subject }),
      el("div", { class: "muted small", text: ticket.customer_name || ticket.customer_email }),
      el(
        "div",
        { class: "queue-meta" },
        triage.priority ? badge(triage.priority, PRIORITY_CLASS[triage.priority]) : null,
        badge(formatIntent(triage.intent), "badge-muted"),
        badge(STATUS_LABEL[ticket.status] || ticket.status, STATUS_CLASS[ticket.status] || "badge-muted"),
      ),
    );
    list.append(el("li", {}, item));
  }
}

async function loadTickets() {
  state.tickets = await api("/api/tickets");
  renderQueue();
}

async function selectTicket(id) {
  state.selectedId = id;
  renderQueue();
}

async function init() {
  try {
    state.config = await api("/api/config");
    $("#model-badge").textContent = state.config.llm_provider === "scripted" ? "scripted model" : state.config.model;
    $("#limits-badge").textContent = `auto refund up to $${state.config.auto_refund_limit}`;
    await loadTickets();
  } catch (error) {
    toast(error.message, "error");
  }
}

$("#refresh").addEventListener("click", () => loadTickets().catch((error) => toast(error.message, "error")));
$("#search").addEventListener("input", (event) => {
  state.query = event.target.value.trim();
  renderQueue();
});
$("#filters").addEventListener("click", (event) => {
  const button = event.target.closest("[data-filter]");
  if (!button) return;
  state.filter = button.dataset.filter;
  document.querySelectorAll("#filters .chip").forEach((chip) => chip.classList.toggle("is-active", chip === button));
  renderQueue();
});

init();

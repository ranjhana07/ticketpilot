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

function triageCell(label, value, meter) {
  return el(
    "div",
    { class: "triage-cell" },
    el("div", { class: "label", text: label }),
    el("div", { class: "value", text: value }),
    meter === undefined ? null : el("div", { class: "meter" }, el("span", { style: `width:${Math.round(meter * 100)}%` })),
  );
}

function renderTriage(triage) {
  const container = $("#triage");
  container.replaceChildren();
  if (!triage || !triage.intent) {
    container.append(el("p", { class: "muted small", text: "No triage result yet." }));
    return;
  }
  const alternatives = (triage.top_intents || []).slice(1, 3).map(([name, score]) => `${formatIntent(name)} ${Math.round(score * 100)}%`);
  container.append(
    triageCell("Intent", formatIntent(triage.intent), triage.intent_confidence),
    triageCell("Priority", triage.priority_bumped ? `${triage.priority} (raised)` : triage.priority, triage.priority_confidence),
    triageCell("Sentiment", `${triage.sentiment_label} (${triage.sentiment})`),
    triageCell("Urgency", `${Math.round(triage.urgency * 100)}%`, triage.urgency),
    triageCell("Language", triage.language),
    triageCell("PII found", triage.pii_labels.length ? triage.pii_labels.join(", ") : "none"),
  );
  if (alternatives.length) {
    container.append(triageCell("Also possible", alternatives.join(", ")));
  }
}

function renderDuplicates(triage) {
  const box = $("#duplicates");
  const matches = (triage && triage.duplicates) || [];
  box.hidden = matches.length === 0;
  box.textContent = matches.length
    ? `Possible duplicate of ${matches.map((match) => `${match.ticket_id} (${Math.round(match.score * 100)}%)`).join(", ")}`
    : "";
}

function renderNotes(notes) {
  const list = $("#notes");
  list.replaceChildren(...notes.map((note) => el("li", {}, el("strong", { text: `${note.author}: ` }), note.body)));
  $("#notes-block").hidden = notes.length === 0;
}

function renderDetail() {
  const ticket = state.detail;
  $("#detail-empty").hidden = Boolean(ticket);
  $("#detail").hidden = !ticket;
  if (!ticket) return;
  $("#detail-id").textContent = `${ticket.id} / ${ticket.channel}`;
  $("#detail-subject").textContent = ticket.subject;
  $("#detail-from").textContent = `${ticket.customer_name || "Unknown sender"} <${ticket.customer_email}> / ${relativeTime(ticket.created_at)}`;
  $("#detail-body").textContent = ticket.body;
  renderTriage(ticket.triage);
  renderDuplicates(ticket.triage);
  renderNotes(ticket.notes || []);
  const locked = ["replied", "awaiting_approval"].includes(ticket.status);
  $("#run-agent").disabled = locked;
  $("#run-agent").textContent = ticket.proposal ? "Run agent again" : "Run agent";
}

async function selectTicket(id) {
  state.selectedId = id;
  renderQueue();
  try {
    state.detail = await api(`/api/tickets/${id}`);
    renderDetail();
    renderProposal();
    renderDraft();
  } catch (error) {
    toast(error.message, "error");
  }
}

const money = (value) => `$${Number(value).toFixed(2)}`;

function describeAction(action) {
  const args = action.args || {};
  switch (action.tool) {
    case "lookup_customer":
      return `Look up customer ${args.email}`;
    case "verify_identity":
      return `Verify sender owns ${args.customer_id}`;
    case "get_order":
      return `Read order ${args.order_id}`;
    case "list_customer_orders":
      return `List orders for ${args.customer_id}`;
    case "refund_order":
      return `Refund ${money(args.amount)} on ${args.order_id}`;
    case "reset_password":
      return `Send password reset link for ${args.customer_id}`;
    case "update_subscription":
      return `Move ${args.customer_id} to the ${args.plan} plan`;
    case "cancel_subscription":
      return `Cancel subscription for ${args.customer_id}`;
    case "escalate_to_human":
      return `Escalate to ${args.team}`;
    case "add_internal_note":
      return "Add internal note";
    case "search_knowledge_base":
      return "Search the help center";
    default:
      return action.tool;
  }
}

function actionDetail(action) {
  if (action.status === "blocked") return action.reason || action.rule;
  if (action.status === "failed") return action.result && action.result.error;
  if (action.tool === "escalate_to_human") return action.args.reason;
  if (action.tool === "add_internal_note") return action.args.note;
  if (action.tool === "verify_identity") {
    return action.result && action.result.verified ? "Sender matches the account email" : "Sender does not match the account";
  }
  if (action.approved_by) return `Approved by ${action.approved_by}`;
  return "";
}

const ACTION_STATUS_CLASS = { executed: "badge-good", blocked: "badge-bad", failed: "badge-warn" };

function renderActions(actions) {
  const list = $("#actions");
  list.replaceChildren();
  if (!actions.length) {
    list.append(el("li", { class: "muted small", text: "The agent did not take any action." }));
    return;
  }
  for (const action of actions) {
    const detail = actionDetail(action);
    list.append(
      el(
        "li",
        { class: `timeline-item is-${action.status}` },
        el(
          "div",
          { class: "queue-row" },
          el("span", { class: "timeline-title", text: describeAction(action) }),
          badge(action.status, ACTION_STATUS_CLASS[action.status] || "badge-muted"),
        ),
        detail ? el("p", { class: "muted small", text: detail }) : null,
      ),
    );
  }
}

function renderApprovals(pending) {
  $("#approvals").hidden = pending.length === 0;
  const list = $("#approval-list");
  list.replaceChildren();
  state.choices = {};
  for (const item of pending) {
    const row = el("li", { class: "approval-item" });
    const choose = (value) => () => {
      state.choices[item.call_id] = value;
      row.querySelectorAll("button").forEach((button) => button.classList.toggle("is-active", button.dataset.value === value));
      $("#submit-approvals").disabled = pending.some((entry) => !state.choices[entry.call_id]);
    };
    row.append(
      el("strong", { text: describeAction(item) }),
      el("p", { class: "muted small", text: item.reason }),
      el(
        "div",
        { class: "segmented" },
        el("button", { type: "button", class: "chip", "data-value": "approve", text: "Approve", onclick: choose("approve") }),
        el("button", { type: "button", class: "chip", "data-value": "reject", text: "Reject", onclick: choose("reject") }),
      ),
    );
    list.append(row);
  }
  $("#submit-approvals").disabled = pending.length > 0;
}

function renderProposal() {
  const ticket = state.detail;
  const proposal = ticket && ticket.proposal;
  $("#proposal-empty").hidden = Boolean(proposal);
  $("#proposal").hidden = !proposal;
  if (!proposal) return;
  renderApprovals(proposal.pending_approvals || []);
  renderActions(proposal.actions || []);
}

async function runAgent() {
  const button = $("#run-agent");
  button.disabled = true;
  button.textContent = "Running";
  try {
    await api(`/api/tickets/${state.selectedId}/run`, { method: "POST" });
    await selectTicket(state.selectedId);
    await loadTickets();
    toast(state.detail.status === "awaiting_approval" ? "Agent paused, approval needed" : "Agent finished");
  } catch (error) {
    toast(error.message, "error");
    renderDetail();
  }
}

async function submitApprovals() {
  const button = $("#submit-approvals");
  button.disabled = true;
  try {
    await api(`/api/tickets/${state.selectedId}/approve`, {
      method: "POST",
      body: { decisions: state.choices, reviewer: $("#reviewer").value.trim() || "reviewer" },
    });
    await selectTicket(state.selectedId);
    await loadTickets();
    toast("Decisions submitted");
  } catch (error) {
    button.disabled = false;
    toast(error.message, "error");
  }
}

function renderDraft() {
  const ticket = state.detail;
  const draft = ticket && ticket.draft;
  const sent = Boolean(draft && draft.sent_at);
  const waiting = ticket && ticket.status === "awaiting_approval";
  const textarea = $("#draft-text");
  textarea.value = draft ? draft.reply : "";
  textarea.disabled = !draft || sent;
  $("#save-draft").disabled = !draft || sent;
  $("#send-reply").disabled = !draft || sent || waiting;
  const flag = $("#draft-flag");
  flag.hidden = !draft;
  if (draft) {
    flag.textContent = sent ? "sent" : draft.edited ? "edited" : draft.needs_human_attention ? "needs attention" : "ready";
    flag.className = `badge ${sent ? "badge-muted" : draft.needs_human_attention ? "badge-warn" : "badge-good"}`;
  }
  const citations = $("#citations");
  citations.replaceChildren();
  const known = new Map(((ticket && ticket.proposal && ticket.proposal.kb_hits) || []).map((hit) => [hit.article_id, hit]));
  for (const id of (draft && draft.citations) || []) {
    const hit = known.get(id);
    citations.append(badge(hit ? `${hit.title}` : id, "badge-muted"));
  }
  let status = "";
  if (sent) status = `Sent by ${draft.sent_by} at ${new Date(draft.sent_at).toLocaleString()}`;
  else if (waiting) status = "Resolve the pending approvals before sending.";
  else if (draft && draft.citations.length === 0) status = "This draft cites no help center article.";
  $("#draft-status").textContent = status;
}

async function saveDraft() {
  const reply = $("#draft-text").value.trim();
  if (!reply) {
    toast("The reply cannot be empty", "error");
    return false;
  }
  try {
    state.detail = { ...state.detail, ...(await api(`/api/tickets/${state.selectedId}/draft`, { method: "PUT", body: { reply } })) };
    renderDraft();
    toast("Draft saved");
    return true;
  } catch (error) {
    toast(error.message, "error");
    return false;
  }
}

async function sendReply() {
  const current = state.detail.draft ? state.detail.draft.reply : "";
  if ($("#draft-text").value.trim() !== current && !(await saveDraft())) return;
  try {
    const reviewer = $("#reviewer").value.trim() || "reviewer";
    state.detail = { ...state.detail, ...(await api(`/api/tickets/${state.selectedId}/send`, { method: "POST", body: { reviewer } })) };
    renderDetail();
    renderDraft();
    await loadTickets();
    toast("Reply sent");
  } catch (error) {
    toast(error.message, "error");
  }
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

$("#run-agent").addEventListener("click", runAgent);
$("#save-draft").addEventListener("click", saveDraft);
$("#send-reply").addEventListener("click", sendReply);
$("#submit-approvals").addEventListener("click", submitApprovals);
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

function visibleIds() {
  return state.tickets.filter(matchesFilter).map((ticket) => ticket.id);
}

document.addEventListener("keydown", (event) => {
  const typing = ["INPUT", "TEXTAREA"].includes(document.activeElement.tagName);
  if (typing || event.metaKey || event.ctrlKey || event.altKey) return;
  const ids = visibleIds();
  const position = ids.indexOf(state.selectedId);
  if (event.key === "j" && position < ids.length - 1) selectTicket(ids[position + 1]);
  if (event.key === "k" && position > 0) selectTicket(ids[position - 1]);
  if (event.key === "r" && state.selectedId && !$("#run-agent").disabled) runAgent();
  if (event.key === "/") {
    event.preventDefault();
    $("#search").focus();
  }
});

init();

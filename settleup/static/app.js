const state = {
  people: [],
  expenses: [],
  activeParticipants: new Set(),
};

const $ = (sel) => document.querySelector(sel);

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}

/* ---------- People ---------- */

function renderPeople() {
  const list = $("#peopleList");
  if (state.people.length === 0) {
    list.innerHTML = `<span class="empty-note">No one added yet — add group members below.</span>`;
  } else {
    list.innerHTML = state.people
      .map(
        (name) => `
      <span class="chip" data-name="${escapeHtml(name)}">
        ${escapeHtml(name)}
        <button data-action="remove-person" data-name="${escapeHtml(name)}" title="Remove">&times;</button>
      </span>`
      )
      .join("");
  }

  // Payer select
  const payerSel = $("#expPayer");
  const prevPayer = payerSel.value;
  payerSel.innerHTML = state.people
    .map((p) => `<option value="${escapeHtml(p)}">${escapeHtml(p)}</option>`)
    .join("");
  if (state.people.includes(prevPayer)) payerSel.value = prevPayer;

  // Participant toggles
  const partWrap = $("#expParticipants");
  if (state.people.length === 0) {
    partWrap.innerHTML = `<span class="empty-note">Add people first</span>`;
  } else {
    partWrap.innerHTML = state.people
      .map((p) => {
        const active = state.activeParticipants.has(p);
        return `<button type="button" class="p-toggle ${active ? "active" : ""}" data-name="${escapeHtml(p)}">${escapeHtml(p)}</button>`;
      })
      .join("");
  }
}

$("#personForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("#personName");
  const name = input.value.trim();
  if (!name) return;
  try {
    const data = await api("/api/person", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
    state.people = data.people;
    input.value = "";
    renderPeople();
    refreshLedgerAndSettlement();
  } catch (err) {
    alert(err.message);
  }
});

$("#peopleList").addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-action='remove-person']");
  if (!btn) return;
  const name = btn.dataset.name;
  const data = await api(`/api/person/${encodeURIComponent(name)}`, { method: "DELETE" });
  state.people = data.people;
  state.activeParticipants.delete(name);
  await loadExpenses();
  renderPeople();
  refreshLedgerAndSettlement();
});

$("#expParticipants").addEventListener("click", (e) => {
  const btn = e.target.closest(".p-toggle");
  if (!btn) return;
  const name = btn.dataset.name;
  if (state.activeParticipants.has(name)) {
    state.activeParticipants.delete(name);
  } else {
    state.activeParticipants.add(name);
  }
  renderPeople();
});

/* ---------- Expenses ---------- */

function renderExpenses() {
  const list = $("#expenseList");
  if (state.expenses.length === 0) {
    list.innerHTML = `<span class="empty-note">No expenses logged yet.</span>`;
    return;
  }
  list.innerHTML = state.expenses
    .map((exp) => {
      const others = exp.participants.length;
      return `
      <div class="expense-row" data-id="${exp.id}">
        <div class="exp-main">
          <span class="exp-desc">${escapeHtml(exp.description)}</span>
          <span class="exp-meta">${escapeHtml(exp.payer)} paid · split ${others} way${others === 1 ? "" : "s"}</span>
        </div>
        <div class="exp-right">
          <span class="exp-amount">$${exp.amount.toFixed(2)}</span>
          <button class="del-btn" data-action="remove-expense" data-id="${exp.id}" title="Delete">&times;</button>
        </div>
      </div>`;
    })
    .join("");
}

$("#expenseForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const description = $("#expDesc").value.trim();
  const amount = $("#expAmount").value;
  const payer = $("#expPayer").value;
  const participants = Array.from(state.activeParticipants);

  if (!payer) return alert("Add people first.");
  if (participants.length === 0) return alert("Select at least one participant.");

  try {
    const data = await api("/api/expense", {
      method: "POST",
      body: JSON.stringify({ description, amount, payer, participants }),
    });
    state.expenses = data.expenses;
    $("#expDesc").value = "";
    $("#expAmount").value = "";
    state.activeParticipants.clear();
    renderExpenses();
    renderPeople();
    refreshLedgerAndSettlement();
  } catch (err) {
    alert(err.message);
  }
});

$("#expenseList").addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-action='remove-expense']");
  if (!btn) return;
  const data = await api(`/api/expense/${btn.dataset.id}`, { method: "DELETE" });
  state.expenses = data.expenses;
  renderExpenses();
  refreshLedgerAndSettlement();
});

async function loadExpenses() {
  // expenses come bundled with settle response too, but keep this for
  // the person-removal flow where we need a fresh list
  const data = await api("/api/settle");
  // settle endpoint doesn't return expenses; re-derive isn't needed here
  // since server already trimmed them on person removal — just re-render
}

/* ---------- Ledger + Settlement ---------- */

function renderLedger(balances) {
  const wrap = $("#balanceLedger");
  const people = Object.keys(balances);
  if (people.length === 0) {
    wrap.innerHTML = `<span class="empty-note">Balances will appear once expenses are added.</span>`;
    return;
  }

  const maxAbs = Math.max(1, ...people.map((p) => Math.abs(balances[p])));

  wrap.innerHTML = people
    .map((name) => {
      const bal = balances[name];
      const pct = Math.min(50, (Math.abs(bal) / maxAbs) * 50);
      const cls = bal > 0.01 ? "pos" : bal < -0.01 ? "neg" : "zero";
      const sign = bal > 0.01 ? "+" : "";
      return `
      <div class="ledger-row">
        <span class="ledger-name">${escapeHtml(name)}</span>
        <div class="ledger-track">
          ${bal > 0.01 ? `<div class="ledger-fill pos" style="width:${pct}%"></div>` : ""}
          ${bal < -0.01 ? `<div class="ledger-fill neg" style="width:${pct}%"></div>` : ""}
        </div>
        <span class="ledger-amt ${cls}">${sign}$${bal.toFixed(2)}</span>
      </div>`;
    })
    .join("");
}

function renderSettlement(data) {
  const summary = $("#settlementSummary");
  const list = $("#settlementList");

  if (data.transactions.length === 0) {
    summary.innerHTML = `Everyone is settled up.`;
    list.innerHTML = "";
    return;
  }

  const savedBadge =
    data.transactions_saved > 0
      ? `<span class="saved-badge">−${data.transactions_saved} vs. naive</span>`
      : "";

  summary.innerHTML = `<strong>${data.optimized_count}</strong> transaction${data.optimized_count === 1 ? "" : "s"} needed to settle everyone up${savedBadge}`;

  list.innerHTML = data.transactions
    .map(
      (t) => `
    <div class="settle-row">
      <span class="settle-from">${escapeHtml(t.from)}</span>
      <span class="settle-arrow">pays &rarr;</span>
      <span class="settle-to">${escapeHtml(t.to)}</span>
      <span class="settle-amt">$${t.amount.toFixed(2)}</span>
    </div>`
    )
    .join("");
}

async function refreshLedgerAndSettlement() {
  const data = await api("/api/settle");
  renderLedger(data.balances);
  renderSettlement(data);
}

/* ---------- Reset ---------- */

$("#resetBtn").addEventListener("click", async () => {
  if (!confirm("Start a new trip? This clears all people and expenses.")) return;
  await api("/api/reset", { method: "POST" });
  window.location.reload();
});

/* ---------- Utils ---------- */

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

/* ---------- Init ---------- */

function init() {
  state.people = window.__INITIAL_PEOPLE__ || [];
  state.expenses = window.__INITIAL_EXPENSES__ || [];
  renderPeople();
  renderExpenses();
  refreshLedgerAndSettlement();
}

init();

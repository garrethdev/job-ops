/* job-ops dashboard — client logic.
   Talks only to /api/* (password in x-dash-key header). No secrets here. */

let LEADS = [];
const $ = (s) => document.querySelector(s);
const esc = (s) => (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const KEY = () => localStorage.getItem("dashkey") || "";
const H = () => ({ "x-dash-key": KEY(), "Content-Type": "application/json" });

const LANE_LABELS = {
  "gtm-engineer": "GTM Engineer", "software-architect": "Software Architect",
  "ai-consultant": "AI Consultant", "ai-video-editor": "AI Video Editor",
  "product-lead": "Product Lead", "marketing-lead": "Marketing Lead", "lookup": "Contact lookup",
};
const laneLabel = (l) => LANE_LABELS[l] || l || "—";
const scoreClass = (s) => (s >= 8 ? "s-hi" : s >= 6 ? "s-mid" : "s-lo");

function toast(msg, ms = 2600) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove("show"), ms);
}

/* --- auth ---------------------------------------------------------------- */
function showGate(err) { $("#gate").hidden = false; $("#pwerr").textContent = err || ""; $("#pw").focus(); }
function submitPw() { localStorage.setItem("dashkey", $("#pw").value); $("#gate").hidden = true; load(); }
function logout() { localStorage.removeItem("dashkey"); location.reload(); }

async function api(path, opts) {
  const r = await fetch(path, { ...opts, headers: { ...H(), ...((opts && opts.headers) || {}) } });
  if (r.status === 401) {
    localStorage.removeItem("dashkey");
    showGate("Wrong password. Try again.");
    throw new Error("unauthorized");
  }
  return r;
}

/* --- load + render ------------------------------------------------------- */
async function load() {
  if (!KEY()) { showGate(); return; }
  let d;
  try { d = await (await api("/api/leads")).json(); } catch (e) { return; }
  LEADS = d.leads || [];
  const ap = $("#apollo");
  ap.textContent = d.apollo_ready ? "apollo ready" : "apollo: no key";
  ap.className = "badge " + (d.apollo_ready ? "ok" : "no");
  render();
}

function render() {
  const lane = $("#f-lane").value, min = +$("#f-min").value,
        onlyNew = $("#f-enriched").checked, q = $("#f-q").value.toLowerCase();
  const rows = $("#rows");
  rows.innerHTML = "";
  const list = LEADS.filter((x) =>
    (!lane || x.lane === lane) && x.fit_score >= min &&
    (!onlyNew || !(x.contact && x.contact.linkedin)) &&
    (!q || (x.title + " " + x.company).toLowerCase().includes(q)));
  $("#count").textContent = list.length + " / " + LEADS.length + " leads";
  $("#empty").hidden = list.length > 0;
  for (const x of list) rows.appendChild(rowEl(x));
}

function rowEl(x) {
  const tr = document.createElement("tr");
  tr.dataset.id = x.id;
  const c = x.contact || {};
  const contactHtml = c.linkedin
    ? `<div class="contact__name">${esc(c.name)}</div>
       <div class="contact__title">${esc(c.title)}</div>
       <div class="contact__row">
         ${c.linkedin ? `<a href="${esc(c.linkedin)}" target="_blank">LinkedIn ↗</a>` : ""}
         ${c.email ? `<a href="mailto:${esc(c.email)}">${esc(c.email)}</a>` : '<span class="muted">no email</span>'}
       </div>`
    : `<span class="muted">—</span>`;
  const flags = (x.red_flags || []).length ? `<div class="flags">⚠ ${esc(x.red_flags.join("; "))}</div>` : "";
  tr.innerHTML = `
    <td><span class="score ${scoreClass(x.fit_score)}">${x.fit_score ?? "·"}</span></td>
    <td><div class="role">${esc(x.title)}</div><div class="rationale">${esc(x.fit_rationale || "")}</div>${flags}</td>
    <td>${x.url ? `<a href="${esc(x.url)}" target="_blank">${esc(x.company)} ↗</a>` : esc(x.company)}
        <div class="loc">${esc(x.location || "")}</div></td>
    <td><span class="lane">${laneLabel(x.lane)}</span></td>
    <td>${contactHtml}</td>
    <td><div class="notes__disp" title="click to edit">${esc(x.notes) || '<span class="muted">+ note</span>'}</div></td>
    <td><div class="acts">
      <button class="btn btn--primary act-li">${c.linkedin ? "✓ LinkedIn" : "🔗 Find LinkedIn"}</button>
      <button class="btn act-em">✉ Email</button>
      <button class="btn act-draft" title="draft outreach email in your voice">✍️ Draft</button>
      <button class="btn btn--danger act-rej" title="reject (hides it, remembers your no)">🗑</button>
    </div></td>`;
  tr.querySelector(".act-li").onclick = () => enrich(x.id, tr);
  tr.querySelector(".act-em").onclick = () => findEmail(x.id, tr);
  tr.querySelector(".act-draft").onclick = () => draftFromRow(x.id);
  tr.querySelector(".act-rej").onclick = () => reject(x.id, tr);
  tr.querySelector(".notes__disp").onclick = (e) => editNotes(x, e.currentTarget);
  return tr;
}

/* --- actions ------------------------------------------------------------- */
async function enrich(id, tr) {
  const lead = LEADS.find((l) => l.id === id);
  if (lead.contact && lead.contact.linkedin) { toast("Already revealed (no credit)."); return; }
  const btn = tr.querySelector(".act-li");
  btn.disabled = true; btn.textContent = "⏳ finding…";
  try {
    const d = await (await api(`/api/enrich?id=${encodeURIComponent(id)}`, { method: "POST" })).json();
    Object.assign(lead, d.lead);
    const cr = (d.meta && d.meta.credits_used) || 0;
    if (d.lead.contact && d.lead.contact.linkedin) toast(`Found ${d.lead.contact.name} · ${cr} credit`);
    else toast("No decision-maker found · 0 credits");
    tr.replaceWith(rowEl(lead));
  } catch (e) { btn.disabled = false; btn.textContent = "🔗 Find LinkedIn"; }
}

function findEmail(id, tr) {
  const lead = LEADS.find((l) => l.id === id), c = lead.contact || {};
  if (c.email) { navigator.clipboard && navigator.clipboard.writeText(c.email); toast("Email: " + c.email + " (copied)"); }
  else enrich(id, tr);
}

async function reject(id, tr) {
  const lead = LEADS.find((l) => l.id === id);
  if (!confirm(`Reject:\n${lead.title} — ${lead.company}?\n(Hidden from the board; kept so the system learns.)`)) return;
  try {
    await api(`/api/reject?id=${encodeURIComponent(id)}`, { method: "POST" });
    LEADS = LEADS.filter((l) => l.id !== id);
    tr.remove(); render(); toast("Rejected.");
  } catch (e) {}
}

function editNotes(x, disp) {
  const td = disp.parentElement;
  td.innerHTML = `<div class="notes__edit"><textarea>${esc(x.notes)}</textarea>
    <div><button class="btn btn--primary act-save">Save</button> <button class="btn act-cancel">Cancel</button></div></div>`;
  const ta = td.querySelector("textarea");
  ta.focus();
  const restore = () => {
    td.innerHTML = `<div class="notes__disp" title="click to edit">${esc(x.notes) || '<span class="muted">+ note</span>'}</div>`;
    td.querySelector(".notes__disp").onclick = (e) => editNotes(x, e.currentTarget);
  };
  td.querySelector(".act-save").onclick = async () => {
    try {
      const d = await (await api(`/api/notes?id=${encodeURIComponent(x.id)}`, { method: "POST", body: JSON.stringify({ notes: ta.value }) })).json();
      x.notes = d.lead.notes;
      const lead = LEADS.find((l) => l.id === x.id); if (lead) lead.notes = d.lead.notes;
      toast("Note saved.");
    } catch (e) {}
    restore();
  };
  td.querySelector(".act-cancel").onclick = restore;
}

/* --- tabs ----------------------------------------------------------------- */
function showTab(name) {
  const leads = name === "leads";
  $("#view-leads").hidden = !leads;
  $("#view-outreach").hidden = leads;
  $("#tab-leads").classList.toggle("tab--active", leads);
  $("#tab-outreach").classList.toggle("tab--active", !leads);
  if (!leads) fillLeadPicker();
}

/* --- outreach: craft an email in Garreth's voice -> Gmail draft ----------- */
function fillLeadPicker(selectedId) {
  const sel = $("#o-lead");
  const current = selectedId || sel.value;
  sel.innerHTML = "";
  const sorted = [...LEADS].sort((a, b) => (b.fit_score || 0) - (a.fit_score || 0));
  for (const l of sorted) {
    const opt = document.createElement("option");
    const who = l.contact && l.contact.name ? ` · ${l.contact.name}` : "";
    opt.value = l.id;
    opt.textContent = `[${l.fit_score ?? "·"}] ${l.title} — ${l.company}${who}`;
    sel.appendChild(opt);
  }
  if (current && LEADS.some((l) => l.id === current)) sel.value = current;
}

function draftFromRow(id) {
  showTab("outreach");
  fillLeadPicker(id);
  $("#o-context").focus();
}

async function craftDraft() {
  const id = $("#o-lead").value;
  if (!id) { toast("Pick a lead first."); return; }
  const btn = $("#o-btn"), old = btn.textContent;
  btn.disabled = true; btn.textContent = "⏳ writing in your voice…";
  $("#o-status").textContent = "Crafting the email and saving to Gmail Drafts…";
  $("#o-preview").hidden = true;
  try {
    const d = await (await api(`/api/draft?id=${encodeURIComponent(id)}`, {
      method: "POST", body: JSON.stringify({ context: $("#o-context").value }),
    })).json();
    if (d.error) { $("#o-status").textContent = "Failed: " + d.error; return; }
    const lead = LEADS.find((l) => l.id === id);
    if (lead && d.lead) Object.assign(lead, d.lead);
    $("#o-subject").textContent = d.email.subject;
    $("#o-body").textContent = d.email.body;
    $("#o-to").textContent = d.to.startsWith("(") ? d.to : "To: " + d.to;
    $("#o-preview").hidden = false;
    $("#o-status").textContent = "Done — it's in your Gmail Drafts under “Sendouts”.";
    toast("Draft saved to Gmail (Sendouts).");
  } catch (e) {
    $("#o-status").textContent = "Request failed.";
  } finally {
    btn.disabled = false; btn.textContent = old;
  }
}

/* --- find a contact (ad-hoc company lookup) ------------------------------ */
async function findContactSearch() {
  const company = $("#find-company").value.trim();
  if (!company) { toast("Enter a company."); return; }
  const role = $("#find-role").value.trim();
  const lane = $("#find-lane").value;
  const btn = $("#find-btn"), old = btn.textContent;
  btn.disabled = true; btn.textContent = "⏳ finding…";
  $("#find-status").textContent = "Searching Apollo…";
  try {
    const d = await (await api("/api/find", { method: "POST", body: JSON.stringify({ company, role, lane }) })).json();
    const lead = d.lead, c = lead.contact || {}, cr = (d.meta && d.meta.credits_used) || 0;
    LEADS = [lead, ...LEADS.filter((l) => l.id !== lead.id)];  // surface it on the board
    render();
    if (c.linkedin) {
      $("#find-status").innerHTML =
        `Found <b>${esc(c.name)}</b> · ${esc(c.title)} · ` +
        `<a href="${esc(c.linkedin)}" target="_blank">LinkedIn ↗</a>` +
        (c.email ? ` · <a href="mailto:${esc(c.email)}">${esc(c.email)}</a>` : "");
      toast(`Found ${c.name} · ${cr} credit`);
    } else {
      $("#find-status").textContent = `No contact found for ${company} (saved to board). 0 credits.`;
    }
    $("#find-company").value = ""; $("#find-role").value = "";
  } catch (e) {
    $("#find-status").textContent = "Search failed.";
  } finally {
    btn.disabled = false; btn.textContent = old;
  }
}

/* --- boot ---------------------------------------------------------------- */
["#f-lane", "#f-min", "#f-enriched", "#f-q"].forEach((s) => $(s).addEventListener("input", render));
$("#pw") && $("#pw").addEventListener("keydown", (e) => { if (e.key === "Enter") submitPw(); });
load();

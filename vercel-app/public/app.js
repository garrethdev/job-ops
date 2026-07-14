/* job-ops dashboard — client logic (ES module).
   Talks only to /api/* (password in x-dash-key header). No secrets here.
   Pure helpers live in format.js so they can be unit-tested. */

import { esc, safeUrl, safeEmail, laneLabel, scoreClass, initials, fmtDate, stripTag } from "./format.js";

const STAGE_LABEL = { new: "New", wip: "Working", reached_out: "Reached out" };
const STAGES = ["new", "wip", "reached_out"];
function stageOf(x) { return x.stage || (x.outreached_at ? "reached_out" : "new"); }
function stageCell(x) {
  const cur = stageOf(x);
  const opts = STAGES.map((s) => `<option value="${s}"${s === cur ? " selected" : ""}>${STAGE_LABEL[s]}</option>`).join("");
  const date = cur === "reached_out" && x.outreached_at ? `<div class="stage-date">${esc(fmtDate(x.outreached_at))}</div>` : "";
  return `<select class="stage-sel stage-sel--${cur} act-stage" title="set stage">${opts}</select>${date}`;
}

let LEADS = [];
const $ = (s) => document.querySelector(s);
const KEY = () => localStorage.getItem("dashkey") || "";
const H = () => ({ "x-dash-key": KEY(), "Content-Type": "application/json" });

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
        onlyNew = $("#f-enriched").checked, q = $("#f-q").value.toLowerCase(),
        stage = $("#f-stage").value;
  const rows = $("#rows");
  rows.innerHTML = "";
  const list = LEADS.filter((x) =>
    (!lane || x.lane === lane) && x.fit_score >= min &&
    (!onlyNew || !(x.contact && x.contact.linkedin)) &&
    (!stage || (stage === "active" ? stageOf(x) !== "new" : stageOf(x) === stage)) &&
    (!q || (x.title + " " + x.company).toLowerCase().includes(q)));
  $("#count").textContent = list.length + " / " + LEADS.length + " leads";
  $("#empty").hidden = list.length > 0;
  for (const x of list) rows.appendChild(rowEl(x));
}

function rowEl(x) {
  const tr = document.createElement("tr");
  tr.dataset.id = x.id;
  const c = x.contact || {};
  const liUrl = safeUrl(c.linkedin), em = safeEmail(c.email);
  const contactHtml = c.linkedin
    ? `<div class="contact">
         <div class="avatar">${esc(initials(c.name))}</div>
         <div class="contact__body">
           <div class="contact__name">${esc(c.name)}</div>
           <div class="contact__title">${esc(c.title)}</div>
           <div class="contact__row">
             ${liUrl ? `<a href="${esc(liUrl)}" target="_blank" rel="noopener noreferrer">LinkedIn ↗</a>` : ""}
             ${em ? `<a href="mailto:${esc(em)}">${esc(em)}</a>` : '<span class="muted">no email</span>'}
           </div>
         </div>
       </div>`
    : `<span class="muted">—</span>`;
  const flags = (x.red_flags || []).length ? `<div class="flags">⚠ ${esc(x.red_flags.join("; "))}</div>` : "";
  tr.innerHTML = `
    <td><span class="score ${scoreClass(x.fit_score)}">${x.fit_score ?? "·"}</span></td>
    <td><div class="role role--link" title="View role details">${esc(x.title)}</div><div class="rationale">${esc(stripTag(x.fit_rationale))}</div>${flags}</td>
    <td>${safeUrl(x.url) ? `<a href="${esc(safeUrl(x.url))}" target="_blank" rel="noopener noreferrer">${esc(x.company)} ↗</a>` : esc(x.company)}
        <div class="loc">${esc(x.location || "")}</div></td>
    <td><span class="lane lane--${esc(x.lane || "none")}">${laneLabel(x.lane)}</span></td>
    <td>${contactHtml}</td>
    <td><div class="notes__disp" title="click to edit">${esc(x.notes) || '<span class="muted">+ note</span>'}</div></td>
    <td class="stage">${stageCell(x)}</td>
    <td><div class="acts">
      <button class="btn btn--primary act-li">${c.linkedin ? "✓ LinkedIn" : "🔗 Find LinkedIn"}</button>
      <button class="btn act-em">✉ Email</button>
      <button class="btn act-draft" title="draft outreach email in your voice">✍️ Draft</button>
      <button class="btn btn--danger act-rej" title="reject (hides it, remembers your no)">🗑</button>
    </div></td>`;
  tr.querySelector(".act-li").onclick = () => enrich(x.id, tr);
  tr.querySelector(".act-em").onclick = () => findEmail(x.id, tr);
  tr.querySelector(".act-draft").onclick = () => draftFromRow(x.id);
  tr.querySelector(".act-stage").onchange = (e) => setStage(x.id, e.target.value, tr);
  tr.querySelector(".act-rej").onclick = () => reject(x.id, tr);
  tr.querySelector(".role--link").onclick = () => openDetail(x.id);
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

async function setStage(id, stage, tr) {
  const lead = LEADS.find((l) => l.id === id);
  const sel = tr.querySelector(".act-stage");
  const prev = stageOf(lead);
  sel.disabled = true;
  try {
    const d = await (await api(`/api/stage?id=${encodeURIComponent(id)}`, {
      method: "POST", body: JSON.stringify({ stage }),
    })).json();
    if (d.error) throw new Error(d.error);
    Object.assign(lead, d.lead);
    tr.replaceWith(rowEl(lead));
    toast(`Stage → ${STAGE_LABEL[stage]}${stage === "reached_out" && d.lead.outreached_at ? " (" + fmtDate(d.lead.outreached_at) + ")" : ""}.`);
  } catch (e) {
    sel.value = prev; sel.disabled = false;
    toast("Couldn’t update stage.");
  }
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
  $("#o-editor").hidden = true;      // clear any stale draft from another lead
  delete $("#o-editor").dataset.leadId;
  $("#o-status").textContent = "";
  $("#o-context").focus();
}

// Step 1: LLM writes the email in your voice and drops it into editable fields.
// Nothing is saved to Gmail yet.
async function craftEmail() {
  const id = $("#o-lead").value;
  if (!id) { toast("Pick a lead first."); return; }
  const btn = $("#o-craft"), old = btn.textContent;
  btn.disabled = true; btn.textContent = "⏳ writing in your voice…";
  $("#o-status").textContent = "Writing a first draft you can edit…";
  try {
    const d = await (await api(`/api/craft?id=${encodeURIComponent(id)}`, {
      method: "POST", body: JSON.stringify({ context: $("#o-context").value }),
    })).json();
    // If the user switched leads while this was in flight, discard the stale
    // result — otherwise we'd show lead A's email while the picker reads lead B.
    if ($("#o-lead").value !== id) return;
    if (d.error) { $("#o-status").textContent = "Failed: " + d.error; return; }
    $("#o-editor").dataset.leadId = id;   // the lead this draft actually belongs to
    $("#o-to").value = d.to || "";
    $("#o-subject").value = d.email.subject || "";
    $("#o-body").value = d.email.body || "";
    $("#o-editor").hidden = false;
    $("#o-save-status").textContent = "";
    $("#o-status").textContent = "Draft ready — edit it, then save to Gmail.";
    $("#o-subject").focus();
  } catch (e) {
    $("#o-status").textContent = "Request failed.";
  } finally {
    btn.disabled = false; btn.textContent = old;
  }
}

// Step 2: save the edited email into Gmail Drafts (labeled), move lead -> Working.
async function saveDraft() {
  // Save against the lead the visible content was crafted for, not whatever the
  // picker currently reads (guards against a lead switch after crafting).
  const id = $("#o-editor").dataset.leadId;
  if (!id) { $("#o-save-status").textContent = "Craft the email first."; return; }
  const subject = $("#o-subject").value.trim();
  const body = $("#o-body").value.trim();
  if (!subject || !body) { $("#o-save-status").textContent = "Add a subject and body first."; return; }
  const btn = $("#o-save"), old = btn.textContent;
  btn.disabled = true; btn.textContent = "⏳ saving…";
  $("#o-save-status").textContent = "Saving to Gmail Drafts…";
  try {
    const d = await (await api(`/api/draft?id=${encodeURIComponent(id)}`, {
      method: "POST", body: JSON.stringify({ subject, body, to: $("#o-to").value.trim() }),
    })).json();
    if (d.error) { $("#o-save-status").textContent = "Failed: " + d.error; return; }
    const lead = LEADS.find((l) => l.id === id);
    if (lead && d.lead) { Object.assign(lead, d.lead); render(); }
    $("#o-save-status").textContent = "Saved — it's in your Gmail Drafts under “Sendouts”.";
    toast("Draft saved to Gmail (Sendouts). Lead → Working.");
  } catch (e) {
    $("#o-save-status").textContent = "Request failed.";
  } finally {
    btn.disabled = false; btn.textContent = old;
  }
}

/* --- role detail modal --------------------------------------------------- */
function openDetail(id) {
  const x = LEADS.find((l) => l.id === id);
  if (!x) return;
  const c = x.contact || {};
  const url = safeUrl(x.url);
  const meta = [x.location, x.comp, x.source_detail && "via " + x.source_detail]
    .filter(Boolean).map((m) => `<span class="d-tag">${esc(m)}</span>`).join("");
  const desc = (x.snippet || "").trim();
  $("#d-body").innerHTML = `
    <div class="d-head">
      <span class="score ${scoreClass(x.fit_score)}">${x.fit_score ?? "·"}</span>
      <div>
        <div class="d-title">${esc(x.title)}</div>
        <div class="d-company">${esc(x.company)} · <span class="lane lane--${esc(x.lane || "none")}">${laneLabel(x.lane)}</span></div>
      </div>
    </div>
    <div class="d-meta">${meta || '<span class="d-tag">no location/comp captured</span>'}
      <span class="d-tag stage-sel--${stageOf(x)}" style="font-weight:600">${STAGE_LABEL[stageOf(x)]}${stageOf(x) === "reached_out" && x.outreached_at ? " · " + esc(fmtDate(x.outreached_at)) : ""}</span>
    </div>
    ${url ? `<a class="d-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">View original posting ↗</a>` : ""}
    ${x.fit_rationale ? `<div class="d-section"><h4>Why it fits</h4><div class="d-rationale">${esc(stripTag(x.fit_rationale))}</div></div>` : ""}
    ${(x.red_flags || []).length ? `<div class="d-section"><h4>Flags</h4><div class="d-flag">⚠ ${esc(x.red_flags.join("; "))}</div></div>` : ""}
    <div class="d-section"><h4>About the role</h4>
      <div class="d-desc">${desc ? esc(desc) : '<span class="muted">No description was captured for this role' + (url ? " — open the original posting above." : ".") + "</span>"}</div>
    </div>
    ${c.linkedin || c.name ? `<div class="d-section"><h4>Contact</h4><div class="d-rationale">${esc(c.name || "")}${c.title ? " · " + esc(c.title) : ""}${safeUrl(c.linkedin) ? ` · <a href="${esc(safeUrl(c.linkedin))}" target="_blank" rel="noopener noreferrer">LinkedIn ↗</a>` : ""}${safeEmail(c.email) ? ` · <a href="mailto:${esc(safeEmail(c.email))}">${esc(safeEmail(c.email))}</a>` : ""}</div></div>` : ""}
    ${x.notes ? `<div class="d-section"><h4>Notes</h4><div class="d-rationale">${esc(x.notes)}</div></div>` : ""}`;
  $("#detail").hidden = false;
}
function closeDetail() { $("#detail").hidden = true; }

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
      const liUrl = safeUrl(c.linkedin), em = safeEmail(c.email);
      $("#find-status").innerHTML =
        `Found <b>${esc(c.name)}</b> · ${esc(c.title)} ` +
        (liUrl ? `· <a href="${esc(liUrl)}" target="_blank" rel="noopener noreferrer">LinkedIn ↗</a>` : "") +
        (em ? ` · <a href="mailto:${esc(em)}">${esc(em)}</a>` : "");
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
["#f-lane", "#f-stage", "#f-min", "#f-enriched", "#f-q"].forEach((s) => $(s).addEventListener("input", render));
$("#pw") && $("#pw").addEventListener("keydown", (e) => { if (e.key === "Enter") submitPw(); });
$("#o-lead") && $("#o-lead").addEventListener("change", () => {
  $("#o-editor").hidden = true; delete $("#o-editor").dataset.leadId;
  $("#o-status").textContent = ""; // stale draft for another lead
});
$("#d-close").addEventListener("click", closeDetail);
$("#d-backdrop").addEventListener("click", closeDetail);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDetail(); });

// This file is a module, so top-level functions aren't global. Expose the ones
// referenced by inline onclick= handlers in index.html.
Object.assign(window, { submitPw, logout, load, showTab, craftEmail, saveDraft, findContactSearch });

load();

import { requireAuth } from "../lib/auth.js";
import { insertLead } from "../lib/supa.js";
import { findContact } from "../lib/apollo.js";
import { makeId } from "../lib/id.js";

// Ad-hoc contact lookup: given a company (+ optional role/lane), find the
// decision-maker via Apollo and save the result as a lead on the board.
export default async function handler(req, res) {
  if (!requireAuth(req, res)) return;
  const { company, role, lane } = req.body || {};
  if (!company || !company.trim()) return res.status(400).json({ error: "company required" });
  const co = company.trim();
  try {
    const { contact, meta } = await findContact(co, lane || "");
    const now = new Date().toISOString();
    const title = (role && role.trim()) || `Contact — ${co}`;
    const row = {
      id: makeId(co, title),
      schema_version: 1,
      lane: lane || "lookup",
      source: "manual",
      source_detail: "lookup",
      title,
      company: co,
      url: "", location: "", comp: "", posted: "",
      first_seen: now, last_seen: now,
      fit_score: 7,
      fit_rationale: "Added via contact search.",
      red_flags: [],
      contact: contact || { name: "", title: "", email: "", linkedin: "" },
      notes: "",
      status: contact && contact.linkedin ? "enriched" : "new",
      snippet: "",
    };
    const lead = await insertLead(row);
    res.json({ lead, meta });
  } catch (e) {
    res.status(502).json({ error: `find: ${e.message || e}` });
  }
}

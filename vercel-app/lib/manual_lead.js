import { makeId } from "./id.js";

// Lanes selectable when adding a lead by hand (superset of the 4 target lanes,
// plus the two the manual leads on the board already use). Empty lane is allowed.
export const MANUAL_LANES = [
  "gtm-engineer", "software-architect", "ai-consultant", "ai-video-editor",
  "product-lead", "marketing-lead",
];

/** Build a store-shaped lead row from user-entered fields. Pure (pass `now`).
 *  Throws if title/company are missing. id matches the Python pipeline so a
 *  hand-added lead dedupes against a scraped one for the same role. */
export function buildManualRow(input, now) {
  const title = String((input && input.title) || "").trim();
  const company = String((input && input.company) || "").trim();
  if (!title || !company) throw new Error("title and company are required");

  const lane = MANUAL_LANES.includes(input.lane) ? input.lane : "";
  const fit = Number.isInteger(input.fit) && input.fit >= 0 && input.fit <= 10 ? input.fit : 7;

  return {
    id: makeId(company, title),
    schema_version: 1,
    lane,
    source: "manual",
    source_detail: "manual",
    title,
    company,
    url: String(input.url || "").trim(),
    location: String(input.location || "").trim(),
    comp: String(input.comp || "").trim(),
    posted: "",
    first_seen: now,
    last_seen: now,
    fit_score: fit,
    fit_rationale: "Added manually.",
    red_flags: [],
    contact: { name: "", title: "", email: "", linkedin: "" },
    notes: String(input.notes || "").trim(),
    status: "new",
    stage: "new",
    snippet: String(input.description || input.snippet || "").trim(),
  };
}

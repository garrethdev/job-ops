import { test } from "node:test";
import assert from "node:assert/strict";
import { buildManualRow, MANUAL_LANES } from "../lib/manual_lead.js";
import { makeId } from "../lib/id.js";

const NOW = "2026-07-14T00:00:00Z";

test("builds a valid manual lead with pipeline-matching id", () => {
  const r = buildManualRow({ title: "Head of AI", company: "Kin Health, Inc.", lane: "ai-consultant" }, NOW);
  assert.equal(r.id, makeId("Kin Health, Inc.", "Head of AI")); // dedupes vs a scraped version
  assert.equal(r.source, "manual");
  assert.equal(r.source_detail, "manual");
  assert.equal(r.stage, "new");
  assert.equal(r.status, "new");
  assert.equal(r.lane, "ai-consultant");
  assert.equal(r.fit_score, 7); // default surfaces above the min-fit filter
});

test("requires title and company", () => {
  assert.throws(() => buildManualRow({ company: "X" }, NOW), /required/);
  assert.throws(() => buildManualRow({ title: "Y" }, NOW), /required/);
  assert.throws(() => buildManualRow({ title: " ", company: " " }, NOW), /required/);
});

test("rejects an unknown lane (falls back to empty) and clamps fit", () => {
  const r = buildManualRow({ title: "T", company: "C", lane: "wizard", fit: 99 }, NOW);
  assert.equal(r.lane, "");
  assert.equal(r.fit_score, 7);
  const r2 = buildManualRow({ title: "T", company: "C", fit: 9 }, NOW);
  assert.equal(r2.fit_score, 9);
});

test("maps description -> snippet and trims fields", () => {
  const r = buildManualRow({ title: "  T ", company: " C ", description: "  the role  ", url: " http://x " }, NOW);
  assert.equal(r.title, "T");
  assert.equal(r.company, "C");
  assert.equal(r.snippet, "the role");
  assert.equal(r.url, "http://x");
});

test("MANUAL_LANES includes the four target lanes", () => {
  for (const l of ["gtm-engineer", "software-architect", "ai-consultant", "ai-video-editor"])
    assert.ok(MANUAL_LANES.includes(l));
});

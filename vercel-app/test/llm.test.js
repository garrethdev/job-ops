import { test } from "node:test";
import assert from "node:assert/strict";
import { parseEmailJSON } from "../lib/llm.js";

test("parses clean JSON", () => {
  const r = parseEmailJSON('{"subject":"Hi","body":"Hello there"}');
  assert.deepEqual(r, { subject: "Hi", body: "Hello there" });
});

test("parses ```json-fenced and prose-wrapped JSON", () => {
  const fenced = '```json\n{"subject":"S","body":"B"}\n```';
  assert.deepEqual(parseEmailJSON(fenced), { subject: "S", body: "B" });
  const prose = 'Sure! Here is your email:\n{"subject":"S","body":"B"}\nHope that helps.';
  assert.deepEqual(parseEmailJSON(prose), { subject: "S", body: "B" });
});

test("body containing inner braces survives (outer-brace slice)", () => {
  const r = parseEmailJSON('{"subject":"S","body":"use {this} today"}');
  assert.equal(r.body, "use {this} today");
});

test("throws a clear error when subject or body missing", () => {
  assert.throws(() => parseEmailJSON('{"subject":"only"}'), /incomplete email/);
  assert.throws(() => parseEmailJSON('{"body":"only"}'), /incomplete email/);
});

test("throws a clear error when there is no JSON object", () => {
  assert.throws(() => parseEmailJSON("no json here"), /no JSON object/);
  assert.throws(() => parseEmailJSON(""), /no JSON object/);
});

test("clamps subject to 150 and body to 4000", () => {
  const r = parseEmailJSON(JSON.stringify({ subject: "x".repeat(300), body: "y".repeat(9000) }));
  assert.equal(r.subject.length, 150);
  assert.equal(r.body.length, 4000);
});

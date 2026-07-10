import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { makeId, normalizeCompany } from "../lib/id.js";

const vectors = JSON.parse(
  readFileSync(fileURLToPath(new URL("../../tests/fixtures/id_vectors.json", import.meta.url)), "utf-8")
);

test("JS makeId matches the Python golden vectors byte-for-byte", () => {
  for (const v of vectors) {
    assert.equal(makeId(v.company, v.title), v.id, `mismatch for "${v.company}" / "${v.title}"`);
  }
});

test("legal suffixes are stripped so variants collapse to one id", () => {
  assert.equal(makeId("Acme Inc", "Engineer"), makeId("acme, inc.", "engineer"));
  assert.equal(normalizeCompany("Vercel Inc"), normalizeCompany("vercel"));
});

test("fixture isn't trivially passing (a suffix-free name still matches Python)", () => {
  const openai = vectors.find((v) => v.company === "OpenAI");
  assert.ok(openai && makeId("OpenAI", "Research Engineer") === openai.id);
});

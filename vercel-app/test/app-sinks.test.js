import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// Regression guard: laneLabel() passes unknown lane strings through verbatim,
// so anywhere app.js interpolates it into innerHTML it must be esc()-wrapped.
test("app.js never interpolates laneLabel() into HTML unescaped", () => {
  const src = readFileSync(fileURLToPath(new URL("../public/app.js", import.meta.url)), "utf8");
  const bare = src.match(/\$\{(?!esc\(laneLabel\()[^}]*laneLabel\([^}]*\}/g) || [];
  assert.deepEqual(bare, [], "unescaped laneLabel() HTML interpolation(s) found");
  // Sanity: the two known sinks (leads row + detail modal) are still present, escaped.
  const escaped = src.match(/\$\{esc\(laneLabel\(x\.lane\)\)\}/g) || [];
  assert.ok(escaped.length >= 2, "expected the escaped laneLabel sinks to exist");
});

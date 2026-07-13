import { test } from "node:test";
import assert from "node:assert/strict";
import { STAGES, STAGE_LABEL, isStage } from "../lib/stage.js";

test("STAGES are the three workflow states, labeled", () => {
  assert.deepEqual(STAGES, ["new", "wip", "reached_out"]);
  assert.equal(STAGE_LABEL.wip, "Working");
  assert.equal(STAGE_LABEL.reached_out, "Reached out");
});

test("isStage accepts only valid stages", () => {
  assert.ok(isStage("new") && isStage("wip") && isStage("reached_out"));
  assert.ok(!isStage("applied"));
  assert.ok(!isStage(""));
  assert.ok(!isStage("REACHED_OUT"));
  assert.ok(!isStage(null));
});

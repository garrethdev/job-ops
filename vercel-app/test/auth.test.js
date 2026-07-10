import { test } from "node:test";
import assert from "node:assert/strict";
import { requireAuth, safeEqual } from "../lib/auth.js";

function fakeRes() {
  return {
    _status: null, _json: null,
    status(c) { this._status = c; return this; },
    json(o) { this._json = o; return this; },
  };
}
const req = (key) => ({ headers: key === undefined ? {} : { "x-dash-key": key } });

test("matching password -> true, no 401", () => {
  process.env.DASH_PASSWORD = "secret";
  const res = fakeRes();
  assert.equal(requireAuth(req("secret"), res), true);
  assert.equal(res._status, null);
});

test("mismatched header -> false + 401 unauthorized", () => {
  process.env.DASH_PASSWORD = "secret";
  const res = fakeRes();
  assert.equal(requireAuth(req("nope"), res), false);
  assert.equal(res._status, 401);
  assert.deepEqual(res._json, { error: "unauthorized" });
});

test("missing header -> 401", () => {
  process.env.DASH_PASSWORD = "secret";
  const res = fakeRes();
  assert.equal(requireAuth(req(undefined), res), false);
  assert.equal(res._status, 401);
});

test("DASH_PASSWORD unset -> 401 even with a header", () => {
  delete process.env.DASH_PASSWORD;
  const res = fakeRes();
  assert.equal(requireAuth(req("anything"), res), false);
  assert.equal(res._status, 401);
});

test("safeEqual", () => {
  assert.equal(safeEqual("abc", "abc"), true);
  assert.equal(safeEqual("abc", "abd"), false);
  assert.equal(safeEqual("abc", "abcd"), false);
  assert.equal(safeEqual(undefined, "x"), false);
});

import { test } from "node:test";
import assert from "node:assert/strict";
import { esc, safeUrl, safeEmail, laneLabel, scoreClass, initials, fmtDate, stripTag, sortLeads } from "../public/format.js";

test("sortLeads orders by date (newest default) and by fit", () => {
  const mk = (id, first_seen, fit_score) => ({ id, first_seen, fit_score });
  const a = mk("a", "2026-07-10T00:00:00Z", 5);
  const b = mk("b", "2026-07-14T00:00:00Z", 9);
  const c = mk("c", "2026-07-12T00:00:00Z", 7);
  assert.deepEqual(sortLeads([a, b, c], "newest").map((x) => x.id), ["b", "c", "a"]);
  assert.deepEqual(sortLeads([a, b, c], "oldest").map((x) => x.id), ["a", "c", "b"]);
  assert.deepEqual(sortLeads([a, b, c], "fit").map((x) => x.id), ["b", "c", "a"]);
  assert.deepEqual(sortLeads([a, b, c], undefined).map((x) => x.id), ["b", "c", "a"]); // defaults newest
});
import { looksLikeEmail } from "../lib/mime.js";

test("safeUrl blocks dangerous schemes, keeps http(s)", () => {
  assert.equal(safeUrl("javascript:alert(1)"), "");
  assert.equal(safeUrl("data:text/html,x"), "");
  assert.equal(safeUrl("//evil.com"), "");            // protocol-relative
  assert.equal(safeUrl("https://x.com"), "https://x.com");
  assert.equal(safeUrl("HTTP://x.com/a"), "HTTP://x.com/a");
  assert.equal(safeUrl(" https://x "), "https://x");   // trimmed
  assert.equal(safeUrl(null), "");
});

test("safeEmail accept/reject", () => {
  assert.equal(safeEmail("a@b.com"), "a@b.com");
  assert.equal(safeEmail('"><img src=x onerror=1>@x.com'), "");
  assert.equal(safeEmail("a@b"), "");
  assert.equal(safeEmail("a b@c.com"), "");
  assert.equal(safeEmail(""), "");
});

test("safeEmail stays in lockstep with lib/mime looksLikeEmail", () => {
  for (const s of ["a@b.com", "a@b.com, c@d.com", "a@b", "notanemail", "x y@z.com", ""]) {
    assert.equal(Boolean(safeEmail(s)), looksLikeEmail(s), `disagree on "${s}"`);
  }
});

test("esc escapes HTML metacharacters", () => {
  assert.equal(esc("<script>"), "&lt;script&gt;");
  assert.equal(esc('a & "b"'), "a &amp; &quot;b&quot;");
  assert.equal(esc(null), "");
});

test("laneLabel maps known lanes, passes through unknown, dashes empty", () => {
  assert.equal(laneLabel("gtm-engineer"), "GTM Engineer");
  assert.equal(laneLabel("marketing-lead"), "Marketing Lead");
  assert.equal(laneLabel("unknown"), "unknown");
  assert.equal(laneLabel(""), "—");
});

test("initials for avatars", () => {
  assert.equal(initials("Jim Allen"), "JA");
  assert.equal(initials("Oliver"), "O");
  assert.equal(initials("  jane   q   doe "), "JD"); // first + last
  assert.equal(initials(""), "?");
  assert.equal(initials(null), "?");
});

test("fmtDate formats ISO -> 'Mon D, YYYY' (UTC), empty for junk", () => {
  assert.equal(fmtDate("2026-07-10T14:04:00Z"), "Jul 10, 2026");
  assert.equal(fmtDate("2026-01-01T00:00:00Z"), "Jan 1, 2026");
  assert.equal(fmtDate(""), "");
  assert.equal(fmtDate(null), "");
  assert.equal(fmtDate("not-a-date"), "");
});

test("stripTag removes a leading [model] tag", () => {
  assert.equal(stripTag("[deepseek/deepseek-chat-v3-0324] The role focuses on AI."), "The role focuses on AI.");
  assert.equal(stripTag("No tag here"), "No tag here");
  assert.equal(stripTag(""), "");
  assert.equal(stripTag("[a] [b] text"), "[b] text"); // only the first, leading tag
});

test("scoreClass boundaries at 8 and 6", () => {
  assert.equal(scoreClass(9), "s-hi");
  assert.equal(scoreClass(8), "s-hi");
  assert.equal(scoreClass(7), "s-mid");
  assert.equal(scoreClass(6), "s-mid");
  assert.equal(scoreClass(5), "s-lo");
  assert.equal(scoreClass(0), "s-lo");
});

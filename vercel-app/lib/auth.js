// Password gate. Every API function checks this. The browser sends the password
// in the x-dash-key header (kept in localStorage after the login prompt).
// Uses a constant-time-ish compare to avoid trivial timing leaks.

function safeEqual(a, b) {
  a = String(a || ""); b = String(b || "");
  if (a.length !== b.length) return false;
  let out = 0;
  for (let i = 0; i < a.length; i++) out |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return out === 0;
}

export function requireAuth(req, res) {
  const expected = process.env.DASH_PASSWORD;
  const given = req.headers["x-dash-key"];
  if (!expected || !safeEqual(given, expected)) {
    res.status(401).json({ error: "unauthorized" });
    return false;
  }
  return true;
}

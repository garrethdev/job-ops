// LinkedIn read side — pulls a person's most recent public post via
// ScrapeCreators (no login cookie, read-only). Used by api/linkedin.js so the
// drafted comment can react to something they actually posted.
//
// Needs SCRAPECREATORS_API_KEY in the Vercel project env. Read-only; ~1 credit
// per profile fetch (cached by ScrapeCreators).

const SC_BASE = "https://api.scrapecreators.com/v1/linkedin/profile";

// Normalize whatever we have (a full URL or a bare handle) to a profile URL.
export function profileUrl(linkedin) {
  const s = String(linkedin || "").trim();
  if (!s) return "";
  if (/^https?:\/\//i.test(s)) return s;
  if (s.startsWith("in/")) return `https://www.linkedin.com/${s}`;
  return `https://www.linkedin.com/in/${s.replace(/^\/+/, "")}`;
}

// Return { post_text, post_url } for the person's latest post, or empty strings.
export async function latestPost(linkedin) {
  const key = process.env.SCRAPECREATORS_API_KEY;
  if (!key) throw new Error("SCRAPECREATORS_API_KEY not set");
  const url = profileUrl(linkedin);
  if (!url) return { post_text: "", post_url: "" };

  const r = await fetch(`${SC_BASE}?url=${encodeURIComponent(url)}`, {
    headers: { "x-api-key": key },
  });
  if (!r.ok) throw new Error(`scrapecreators ${r.status}: ${(await r.text()).slice(0, 160)}`);
  const data = await r.json();
  const posts = Array.isArray(data.recentPosts) ? data.recentPosts : [];
  if (!posts.length) return { post_text: "", post_url: "" };

  // recentPosts are newest-first; title carries the post body in this API.
  const p = posts[0];
  return { post_text: String(p.title || "").trim(), post_url: String(p.link || "").trim() };
}

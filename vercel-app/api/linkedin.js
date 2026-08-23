import { requireAuth } from "../lib/auth.js";
import { getLead, patchLead } from "../lib/supa.js";
import { buildLinkedInPrompt } from "../lib/voice.js";
import { latestPost, profileUrl } from "../lib/linkedin.js";

const OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions";

// Robust-ish JSON extraction (the model may wrap it in prose / fences).
function parseJSON(text) {
  const s = String(text || "");
  const m = s.match(/\{[\s\S]*\}/);
  if (!m) throw new Error("no JSON in model output");
  return JSON.parse(m[0]);
}

async function draftLinkedIn(lead, post) {
  const r = await fetch(OPENROUTER_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.OPENROUTER_API_KEY}`,
      "Content-Type": "application/json",
      "HTTP-Referer": "https://github.com/job-ops",
      "X-Title": "job-ops",
    },
    body: JSON.stringify({
      model: process.env.OPENROUTER_MODEL || "deepseek/deepseek-chat-v3-0324",
      temperature: 0.5,
      max_tokens: 500,
      messages: [{ role: "user", content: buildLinkedInPrompt(lead, post) }],
    }),
  });
  if (!r.ok) throw new Error(`llm ${r.status}: ${(await r.text()).slice(0, 200)}`);
  const data = await r.json();
  return parseJSON(data.choices[0].message.content);
}

// POST /api/linkedin?id=<leadId>
//   default: read their latest post + draft {comment, dm}, RETURN for editing.
//   body {approve:true, comment, dm, post_url}: persist into contact.li,
//     li_stage="approved" — the local browser runner then acts on it.
export default async function handler(req, res) {
  if (!requireAuth(req, res)) return;
  const id = req.query.id;
  const body = req.body || {};
  try {
    const lead = await getLead(id);
    if (!lead) return res.status(404).json({ error: "lead not found" });
    const c = lead.contact || {};
    if (!c.linkedin) return res.status(400).json({ error: "no LinkedIn URL — run Find LinkedIn first" });

    // --- approve path: persist the (possibly edited) comment/DM ------------
    if (body.approve) {
      const li = {
        ...(c.li || {}),
        url: profileUrl(c.linkedin),
        post_url: String(body.post_url || (c.li && c.li.post_url) || ""),
        comment: String(body.comment || "").trim(),
        dm: String(body.dm || "").trim(),
        li_stage: "approved",
        approved_at: new Date().toISOString(),
      };
      const updated = await patchLead(id, { contact: { ...c, li } });
      return res.json({ lead: updated, li });
    }

    // --- draft path: fetch latest post + write the two assets --------------
    let post = { post_text: "", post_url: "" };
    try { post = await latestPost(c.linkedin); }
    catch (e) { /* keep going with no post — prompt handles the empty case */ }
    const out = await draftLinkedIn(lead, post);
    res.json({
      comment: out.comment || "",
      dm: out.dm || "",
      post_url: post.post_url || "",
      post_text: post.post_text || "",
      profile: profileUrl(c.linkedin),
    });
  } catch (e) {
    res.status(502).json({ error: `linkedin: ${e.message || e}` });
  }
}

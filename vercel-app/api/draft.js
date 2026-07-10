import { requireAuth } from "../lib/auth.js";
import { getLead, patchLead } from "../lib/supa.js";
import { buildPrompt } from "../lib/voice.js";
import { createLabeledDraft, OUTREACH_LABEL } from "../lib/gmail.js";
import { parseEmailJSON } from "../lib/llm.js";

const OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions";

async function craftEmail(lead, extraContext) {
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
      temperature: 0.4,
      max_tokens: 500,
      messages: [{ role: "user", content: buildPrompt(lead, extraContext) }],
    }),
  });
  if (!r.ok) throw new Error(`llm ${r.status}: ${(await r.text()).slice(0, 200)}`);
  const data = await r.json();
  return parseEmailJSON(data.choices[0].message.content);
}

// POST /api/draft?id=<leadId>  body: {context?} ->
// crafts an email in Garreth's voice and saves it as a labeled Gmail draft.
export default async function handler(req, res) {
  if (!requireAuth(req, res)) return;
  const id = req.query.id;
  const extraContext = String((req.body && req.body.context) || "");
  try {
    const lead = await getLead(id);
    if (!lead) return res.status(404).json({ error: "lead not found" });

    const email = await craftEmail(lead, extraContext);
    const to = (lead.contact && lead.contact.email) || "";
    const draft = await createLabeledDraft({ to, subject: email.subject, body: email.body });

    const note = ((lead.notes || "") + `\n[draft] "${email.subject}" -> Gmail Drafts (${OUTREACH_LABEL})`).trim();
    const patch = { notes: note };
    if (lead.status === "new" || lead.status === "enriched") patch.status = "queued_for_apply";
    const updated = await patchLead(id, patch);

    res.json({ lead: updated, email, draft, to: to || "(no email on lead — fill in To: in Gmail)" });
  } catch (e) {
    res.status(502).json({ error: `draft: ${e.message || e}` });
  }
}

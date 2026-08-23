// Garreth's outreach voice. Profile distilled (via LLM) from ~25 of his real
// sent emails on 2026-07-10, anchored by a sample he provided. Used by
// api/draft.js to craft outreach drafts that sound like him.

export const VOICE_PROFILE = `
Tone: direct, pragmatic, slightly informal. Professional but approachable. No corporate fluff.
Greeting: "Hi [First Name]," (default). "Hey" only for familiar contacts.
Sign-off: "Best," or "Best regards," — short.
Rhythm: short, crisp sentences. Max 3-4 lines per paragraph, usually 1-2 sentences each.
Characteristic moves: friendly opener ("I saw the opportunity and wanted to reach out"),
a genuine compliment about what the company is doing, a compact credibility line,
then a soft, permission-based ask ("Can I send you some of my previous work?",
"Would you be interested in a quick overview?").
Punctuation: hard stops, minimal em dashes/semicolons, no exclamation overload.
Never: corporate jargon (leverage, synergies), long paragraphs, passive voice, hard sells.
`.trim();

export const SAMPLE_EMAIL = `
Hi [Name],

I saw the opportunity and wanted to reach out. I think what you guys are doing in the space is great.

My background is in the DTC AI and product space. I've worked with the likes of Amazon as well as smaller wellness DTC brands, helping them scale massively.

Can I send you some of my previous work?

Best,
`.trim();

// Verified background facts the email may use. The model must not invent others.
export const BACKGROUND_FACTS = `
- Background: DTC, AI, and product space.
- Has worked with Amazon and with smaller wellness DTC brands, helping them scale.
- Offers fractional/consulting engagement; can share previous work on request.
`.trim();

export function buildPrompt(lead, extraContext) {
  const c = lead.contact || {};
  const firstName = (c.name || "").trim().split(/\s+/)[0] || "";
  return `You write outreach emails AS Garreth, matching his voice exactly.

VOICE PROFILE:
${VOICE_PROFILE}

SAMPLE EMAIL HE WROTE (structure + register to imitate):
${SAMPLE_EMAIL}

VERIFIED BACKGROUND FACTS (use only these — never invent experience, clients, or numbers):
${BACKGROUND_FACTS}

THE OPPORTUNITY:
Role: ${lead.title || ""}
Company: ${lead.company || ""}
Details: ${(lead.snippet || "").slice(0, 900)}
Contact: ${c.name || "(unknown)"}${c.title ? " — " + c.title : ""}
${extraContext ? "EXTRA CONTEXT FROM GARRETH:\n" + extraContext.slice(0, 600) : ""}

Write ONE short outreach email (60-110 words) in Garreth's voice:
- Greeting: "Hi ${firstName || "[Name]"}," ${firstName ? "" : '(no name known — use "Hi there,")'}
- Open like the sample: saw the role, genuine specific nod to what the company does.
- One compact credibility paragraph grounded ONLY in the verified facts, angled to this role.
- End with a soft permission ask like the sample.
- Sign off "Best,\\n\\nGarreth".
- Subject line: short and human, mentions the role, no clickbait.

Respond with ONLY a JSON object: {"subject": "...", "body": "..."}`;
}

// LinkedIn outreach — same voice, but two short assets reacting to a specific
// post: a public COMMENT (get on their radar) and a follow-up DM. The "comment
// first, then DM" sequence is the Aakash Gupta playbook. Both must feel human
// and specific, never like a pitch.
export function buildLinkedInPrompt(lead, post) {
  const c = lead.contact || {};
  const firstName = (c.name || "").trim().split(/\s+/)[0] || "there";
  const postText = String((post && post.post_text) || "").slice(0, 1200);
  return `You write LinkedIn outreach AS Garreth, matching his voice exactly.

VOICE PROFILE:
${VOICE_PROFILE}

VERIFIED BACKGROUND FACTS (use only these — never invent experience, clients, or numbers):
${BACKGROUND_FACTS}

WHO:
${c.name || "(unknown)"}${c.title ? " — " + c.title : ""} at ${lead.company || ""}
Open role you're interested in: ${lead.title || ""}

THEIR MOST RECENT POST (react to THIS — be specific to what they actually said):
${postText || "(no recent post available — write a comment that references the company's work instead)"}

Write TWO things:

1) COMMENT — a public comment on that post. 1-2 sentences. Adds a genuine,
   specific thought or a small insight that shows you read it. NO pitch, NO ask,
   NO links, NO "great post". Sounds like a sharp peer, not a job-seeker.

2) DM — a short direct message (3-4 sentences) sent a day or two later.
   Open by referencing the post or their work specifically. One compact
   credibility line grounded ONLY in the verified facts, angled to the ${lead.title || "role"}.
   End with a soft, permission-based ask ("open to a quick chat?"). Greet "Hi ${firstName},".
   No hard sell, no bullet points, no links.

Respond with ONLY a JSON object: {"comment": "...", "dm": "..."}`;
}

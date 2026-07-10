// Parse a free-form LLM reply into a validated {subject, body}. Pure — unit
// tested in test/llm.test.js. Handles clean JSON, ```json fences, and JSON
// wrapped in prose by slicing to the outer braces. Clamps lengths.

export function parseEmailJSON(text) {
  const s = String(text || "");
  const start = s.indexOf("{");
  const end = s.lastIndexOf("}");
  if (start === -1 || end === -1 || end < start) {
    throw new Error("llm returned no JSON object");
  }
  let parsed;
  try {
    parsed = JSON.parse(s.slice(start, end + 1));
  } catch (e) {
    throw new Error("llm returned unparseable JSON: " + e.message);
  }
  if (!parsed || !parsed.subject || !parsed.body) {
    throw new Error("llm returned incomplete email (missing subject or body)");
  }
  return {
    subject: String(parsed.subject).slice(0, 150),
    body: String(parsed.body).slice(0, 4000),
  };
}

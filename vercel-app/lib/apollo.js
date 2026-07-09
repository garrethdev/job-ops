// Apollo contact finder (JS port of core/apollo.py) — runs server-side only.
// org name -> domain (free) -> people search by title (free) -> match reveal (1 credit).

const BASE = "https://api.apollo.io/api/v1";

const TITLES_BY_LANE = {
  "software-architect": ["VP Engineering", "VP of Engineering", "Head of Engineering",
    "Director of Engineering", "CTO", "Engineering Manager"],
  "gtm-engineer": ["VP Sales", "Head of Growth", "Chief Revenue Officer", "VP Marketing",
    "Head of Revenue", "Head of Sales", "Founder"],
  "ai-consultant": ["CTO", "Head of AI", "Chief AI Officer", "VP Engineering", "Head of Data", "Founder"],
  "ai-video-editor": ["Head of Content", "Creative Director", "Head of Production",
    "Head of Social", "Head of Marketing", "Brand Director"],
};
const FALLBACK_TITLES = ["Founder", "CEO", "CTO", "Head of Talent", "Recruiter", "Hiring Manager"];

async function post(endpoint, payload) {
  const r = await fetch(`${BASE}/${endpoint}`, {
    method: "POST",
    headers: { "X-Api-Key": process.env.APOLLO_API_KEY, "Content-Type": "application/json", "Cache-Control": "no-cache" },
    body: JSON.stringify(payload),
  });
  const data = await r.json();
  if (data && data.error) throw new Error(String(data.error));
  return data;
}

async function resolveDomain(company) {
  const d = await post("mixed_companies/search", { q_organization_name: company, per_page: 1 });
  const orgs = d.organizations || d.accounts || [];
  for (const o of orgs) if (o.primary_domain) return o.primary_domain;
  return null;
}

async function searchPeople({ domain, company, titles, seniorities, per_page = 5 }) {
  const payload = { per_page, page: 1 };
  if (titles) payload.person_titles = titles;
  if (seniorities) payload.person_seniorities = seniorities;
  if (domain) payload.q_organization_domains_list = [domain];
  else payload.q_keywords = company;
  const d = await post("mixed_people/api_search", payload);
  return d.people || [];
}

async function matchPerson(id) {
  const d = await post("people/match", { id, reveal_personal_emails: true });
  return d.person || null;
}

export async function findContact(company, lane) {
  const titles = TITLES_BY_LANE[lane] || FALLBACK_TITLES;
  const domain = await resolveDomain(company);

  let candidates = await searchPeople({ domain, company, titles });
  let tier = "role-titles";
  if (!candidates.length) { candidates = await searchPeople({ domain, company, titles: FALLBACK_TITLES }); tier = "leadership-titles"; }
  if (!candidates.length) {
    candidates = await searchPeople({ domain, company, seniorities: ["c_suite", "vp", "head", "director", "owner", "partner", "founder"] });
    tier = "any-senior";
  }
  const meta = { domain, candidates: candidates.length, match_tier: tier, credits_used: 0 };
  if (!candidates.length) return { contact: null, meta: { ...meta, reason: "no decision-maker found" } };

  const person = await matchPerson(candidates[0].id);
  meta.credits_used = person ? 1 : 0;
  if (!person) return { contact: null, meta: { ...meta, reason: "match failed" } };

  const contact = {
    name: person.name || `${person.first_name || ""} ${person.last_name || ""}`.trim(),
    title: person.title || candidates[0].title || "",
    email: person.email || "",
    linkedin: person.linkedin_url || "",
  };
  return { contact, meta };
}

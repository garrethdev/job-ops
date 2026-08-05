# Character 3 — Part 1: Reddit Jealousy Quote Mining

Character 3 format: a woman on a treadmill, with on-screen motivational text made
of **real things other women said to her out of jealousy**. Part 1 builds the
quote bank that Parts 2 (before/after video) and 3 (iPhoneify touch-ups) draw from.

Copy everything in the block below into a fresh Claude Code session.

---

```
# ROLE

You are a research operator building a quote bank for a short-form video series
called "Character 3." Your only job in this run is SOURCING. You do not write
scripts, generate video, or touch any render pipeline.

# THE ANGLE (so you know what a good quote looks like)

The video shows a woman running on a treadmill. Over her, on screen, we show
verbatim things OTHER WOMEN said to her while she was changing her body — comments
that are dressed up as concern, humor, or compliments but are actually jealousy.
The sting IS the motivation. The viewer should recognize the line instantly and
think "someone said that exact thing to me."

# WHAT YOU ARE HUNTING

Verbatim quotes, spoken BY a woman, TO the poster (or to a woman the poster is
writing about), in reaction to her losing weight, getting fit, getting attention,
or otherwise leveling up.

## Categories (tag every quote with exactly one)

1. concern_troll      — "You're getting too skinny, it's not cute anymore."
2. cheating_accusation— "Must be nice to take the easy way out."
3. doom_prediction    — "You'll gain it all back, everyone does."
4. minimizing         — "Must be nice to have time to work out."
5. nostalgia_guilt    — "I liked you better before. You're no fun now."
6. exclusion          — she stopped being invited / went cold (quote the line said)
7. appearance_policing— "Who are you dressing up for?"
8. backhanded         — "You look amazing! I'd never have the confidence to wear that."

## Hard filters — REJECT anything that fails

- Not verbatim. If the post paraphrases ("she basically implied I cheated"), reject.
  The quote must appear in the source as reported speech, ideally in quote marks.
- Speaker is not a woman, or gender is unstated and unguessable from context.
- Spoken by the poster about herself (self-talk, intrusive thoughts) — reject.
- Longer than 14 words. On-screen text has to be readable in ~1.5 seconds.
- Contains a name, handle, employer, city, or any detail that identifies a real
  person. Reject rather than redact — there are plenty of quotes.
- Names a specific drug brand (Ozempic, Wegovy, Mounjaro, Zepbound, etc.). If the
  quote is otherwise perfect, keep it but set `needs_generic_swap: true` and put a
  generic rewrite in `quote_text_safe` ("the shot" / "GLP-1" / "the peptide").
- References suicide, self-harm, or an eating disorder diagnosis. Skip the whole
  thread — do not mine it, do not quote around it.
- Mean but not jealous ("you're a bad friend") — this angle is envy only.

## Style bar — what makes a KEEPER

- Short, spoken, and specific. "You're just going to gain it back" beats
  "she told me that statistically most people regain the weight."
- Sounds like something said out loud at a kitchen table, not written online.
- Lands as a punch on its own with zero setup context.
- Under 10 words is the sweet spot. Under 6 is gold.

# WHERE TO LOOK

Search these subreddits (search each one, do not just do a global search):

  Weight / body:   r/loseit, r/progresspics, r/CICO, r/1200isplenty,
                   r/PetiteFitness, r/xxfitness, r/WomenOver30Fitness,
                   r/SuperMorbidlyObese, r/glowups, r/BodyAcceptance
  GLP-1:           r/Ozempic, r/Semaglutide, r/Mounjaro, r/Zepbound,
                   r/tirzepatidecompound, r/GLP1, r/WegovyWeightLoss
  Social fallout:  r/TwoXChromosomes, r/AskWomenOver30, r/offmychest,
                   r/Vent, r/relationship_advice, r/AmItheAsshole,
                   r/JUSTNOFAMILY, r/JUSTNOMIL, r/friendship

## Query bank (run each against each relevant sub, plus site-wide)

  "friends jealous of my weight loss"
  "she said I'm getting too skinny"
  "coworker comments since I lost weight"
  "sister stopped talking to me after I lost weight"
  "my friend said I took the easy way out"
  "people say I'll gain it back"
  "backhanded compliments weight loss"
  "friends changed after I got fit"
  "mom keeps commenting on my body"
  "she said I looked better before"
  "left out since I lost weight"
  "girl at the gym said"
  "why are women so mean about weight loss"
  "concern trolling weight loss friend"
  "jealous friend fitness journey"

Also mine the COMMENTS on high-scoring posts — the comment section of a "my friend
said X" post is usually 200 women posting their own X. That is the densest ore in
the whole operation. For any post you keep a quote from, pull its top 50 comments
and mine those too.

# HOW TO FETCH

Try in this order and stop at the first one that works:

1. Reddit public JSON — no auth, but set a real User-Agent:
     https://www.reddit.com/r/{sub}/search.json?q={query}&restrict_sr=1&sort=top&t=all&limit=100
     https://www.reddit.com/comments/{post_id}.json?sort=top&limit=100
   Sleep 1s between requests. If you get 403/429 from a datacenter IP, move on.
2. Firecrawl — firecrawl_search for discovery, firecrawl_scrape on
   old.reddit.com/... permalinks (old.reddit renders comments as plain HTML).
3. WebSearch with `site:reddit.com` + the query, then scrape the hits.

Pushshift is dead. Do not try it.

Cap the run at ~200 fetches total. Log every query you ran and its yield so the
next run does not repeat dry queries.

# DEDUPE

Normalize (lowercase, strip punctuation and filler like "like"/"honestly", collapse
whitespace) before comparing. Two quotes that normalize to within a couple of words
of each other are the same quote — keep the shorter, punchier one and increment
`seen_count` on it. `seen_count` is a signal, not noise: a line ten women
independently reported is the most relatable line in the bank.

# OUTPUT

Write TWO files to ./output/character-3/:

1. `jealousy_quotes.jsonl` — one object per KEPT quote:

   {
     "quote_id": "c3-0001",
     "quote_text": "You're getting too skinny, it's not cute anymore.",
     "quote_text_safe": null,
     "needs_generic_swap": false,
     "word_count": 8,
     "category": "concern_troll",
     "speaker_relation": "close friend",
     "speaker_gender_evidence": "poster says 'my best friend, she'",
     "sting_score": 4,
     "arc_position": "mid",
     "seen_count": 3,
     "context_summary": "Poster down 60lbs, friend group went cold at brunch.",
     "subreddit": "r/loseit",
     "post_title": "...",
     "permalink": "https://reddit.com/r/loseit/comments/...",
     "post_date": "2025-03-14",
     "source_type": "comment",
     "verbatim_confidence": "quoted"
   }

   Field notes:
   - `sting_score` 1-5: how hard it lands cold, with no context. Only 4s and 5s
     should ever make it into a video.
   - `arc_position`: "early" (small digs), "mid" (open doubt),
     "payoff" (the cruelest line — the one the video ends on).
   - `verbatim_confidence`: "quoted" (in quote marks in the source) or
     "reported" (clearly a direct quote but unmarked). Never invent a third value.

2. `jealousy_quotes_rejected.jsonl` — every quote you considered and dropped,
   with a `reject_reason`. This is how the filters get tuned. Do not skip it.

Then print a summary table to chat: total kept, count per category, count per
sting_score, the top 10 by sting_score, and the queries that returned nothing.

# TARGETS

- 150+ quotes examined
- 40+ kept at sting_score >= 3
- 12+ kept at sting_score >= 4, spread across at least 5 categories
- At least 3 candidates tagged arc_position "payoff"

If you finish the query bank under target, write your own queries in the same
shape and keep going. Report the ones you invented.

# RULES

- Never invent, embellish, or "clean up" a quote. Fix only capitalization and
  obvious typos. If you rewrite for safety, the original stays in `quote_text`
  and the rewrite goes in `quote_text_safe`.
- No usernames, ever — not in the files, not in the summary. Permalinks stay in
  the data file for verification and never go on screen.
- No ampersands and no em dashes in anything you write.
- Do not generate video, scripts, captions, or images in this run. Sourcing only.
- If a subreddit is private, banned, or empty, note it and move on. Do not
  work around access controls.
```

---

## After this runs

`jealousy_quotes.jsonl` is the input to Part 2 (before/after video). Sort by
`arc_position` then `sting_score` to get the on-screen order: small digs while
she is warming up, the cruelest line at the sprint. Six to eight quotes fills a
30 to 40 second cut.

Part 3 (iPhoneify touch-ups) runs after the cut is locked and does not read this
file.

---
name: gdoc
description: Create a clean, skimmable, well-formatted Google Doc from content, matching the locked house style (Geist font, H1/H2/H3 hierarchy, bullets, bold lead-in labels, indented code blocks (never a border), real Google Docs tables). Trigger with /gdoc or whenever the user asks to "create/build/make a Google Doc", turn notes/a plan/an SOP/a report into a Google Doc, or format content as a Google Doc.
---

# Google Doc Builder

Turns any content (a plan, SOP, brief, report, playbook) into a clean, skimmable
Google Doc that matches the locked house visual style. The user pointed to the
"DFY Client Onboarding SOP" as the canonical reference for how docs should look.

This skill produces docs that look like that reference, every time, without
re-asking about formatting.

## When to use

- `/gdoc` is typed.
- The user asks to create / build / make a Google Doc.
- The user hands over notes, a markdown draft, an SOP, a plan, or a report and
  wants it as a formatted Google Doc.

## When the Doc is for a Formester content page (blog / listicle / product / landing / alt / review / template)

If the Doc being built is the **copy-review deliverable for a page or blog produced by any of the Formester content-creation skills** (`/blog`, `/product-page`, `/landing-page`, `/alt-page`, `/listicle`, `/review-page`, `/template-page`, `/mf-listicles`), the STRUCTURE of the Doc is locked by the shared content-doc standard at [`~/.claude/skills/_shared/doc_content_standard.md`](../_shared/doc_content_standard.md).

Non-negotiables from that standard:

- **Metadata table first** (Title, Description, Meta title, Meta description, Primary keyword, Primary keyword volume (US), Secondary keywords, Slug, Recommended URL, CMS link). Every row filled.
- **Verbatim final copy only.** No commentary, no `**Why:**` lines, no `[REUSE: ...]` annotations, no placement notes, no schema JSON, no cover URL or media ids, no preflight-status footer.
- **Explicit heading markers inline:** every heading line starts with `[H1] ` / `[H2] ` / `[H3] ` as a plain-text prefix (before the heading text, on the same line).
- **Image markers as standalone lines:** `[Image: descriptive alt text]` wherever an on-page image will render. No image URLs.

The visual spec below (Geist typography, real tables, etc.) still applies. The content-doc standard governs what's IN the Doc; this skill's visual spec governs how it's typeset. When updating an existing content Doc, regenerate in place via `--doc-id <existing_id>` (never mint a new URL for the same page).

## The visual spec (locked: do not re-ask, do not deviate)

- **Font:** Geist everywhere (title, headings, body, bullets, tables, code).
- **Margins:** 72pt all four sides.
- **Title (H1):** Geist 18pt bold. One per doc, at the top.
- **Section headings (H2):** Geist 15pt bold. Number them (`1.`, `2.`, ...) when
  the doc has clear sequential sections, matching the reference.
- **Subsections (H3):** Geist 12pt bold.
- **Body:** Geist 11pt.
- **Bullets:** `BULLET_DISC_CIRCLE_SQUARE`, 11pt. Use a bold lead-in label where
  it aids skimming: `**Label**: detail`.
- **Ordered steps:** numbered list, 11pt.
- **Bold lead-in line (`label`):** a standalone bold 11pt line above a block.
- **Code / structured blocks:** Geist 10pt, muted grey, indented. **Never a left
  border or any grey vertical line** (banned by Harsh, 2026-10-01). For payloads, configs, email copy, command snippets.
- **Tables:** real Google Docs tables with a bold, lightly shaded header row.
  Use tables for any comparison / spec / lookup data (tools, plans, costs).

All of this is applied automatically by `build_gdoc.py`. You do not hand-build
batchUpdate requests.

## Content rules (every section earns its place)

- Make it actionable and skimmable. The doc should read like a tight operating
  spec, not an essay.
- No backstory / situation / diagnosis recaps.
- No "why this approach" / "what this does not include" meta-sections.
- No skill walkthroughs explaining how the doc was produced.
- No scoring breakdowns or anti-pattern lists unless directly actionable.
- No emojis unless the user explicitly asks.
- No em dashes (—) or en dashes (–) anywhere in the doc's prose.
- **No grey vertical lines / left borders** on any block, ever.
- **No hanging indents:** wrapped lines must align with the first line. Any
  indented block sets `indentFirstLine` equal to `indentStart`.
- **Copy spacing:** in any email, message or ad copy, put a blank line between
  every sentence (each sentence is its own line, separated by an empty line).
  The subject line stays on its own line above the body.
- Lead bullets with a bold label when it speeds scanning.
- Prefer a table over a long bulleted list when the data is comparative.

## Humanizer pass (mandatory, runs before every build)

Every doc's prose gets a humanizer pass before `build_gdoc.py` runs. This is
what makes the docs read as written by a person. Do not ask whether to run it;
skip only if the user says "skip humanizer", "raw" or "unedited".

- **If the `humanizer` skill is installed** (`~/.claude/skills/humanizer/`,
  source: https://github.com/blader/humanizer, MIT), invoke it on the draft
  text first.
- **If it is not installed**, apply the checklist below yourself.

**Scope:** title, lede, headings, body, bullets, labels and any copy inside
code blocks (emails, messages, ads). Leave alone: actual code, commands, JSON,
table cells that are pure data, URLs, and verbatim quotes or third-party text.

**Checklist (rewrite, don't just delete; keep every point the draft makes):**

1. **No em or en dashes.** Replace with a period, comma, colon or parentheses.
   Scan the final spec for `—` and `–`; any hit means it isn't done.
2. **Cut inflated significance:** "pivotal", "crucial", "key role", "testament
   to", "underscores", "evolving landscape", "marks a shift", "setting the stage".
3. **Cut AI vocabulary:** delve, additionally, enhance, foster, garner,
   showcase, intricate, tapestry, vibrant, valuable, seamless, robust, leverage.
4. **Use plain verbs:** "is/has" instead of "serves as / stands as / boasts / features".
5. **No tacked-on -ing clauses** ("..., ensuring X", "..., highlighting Y").
6. **No "not just X, it's Y"** constructions or clipped tails like "no guesswork".
7. **Break forced groups of three.** Use two items, or four, if that's what's true.
8. **No promo tone or vague authority:** "stunning", "renowned", "experts say",
   "industry reports show". Name the source or drop the claim.
9. **Cut filler and hedging:** "in order to" → "to", "it is important to note
   that" → delete, "could potentially" → "can".
10. **No chatbot residue:** "I hope this helps", "Certainly!", "Let me know",
    "Here is a...", "Great question".
11. **Sentence-case headings,** straight quotes, no emojis, no decorative bold
    mid-sentence. (Bold lead-in labels on bullets are house style and stay.)
12. **Vary rhythm.** Mix short and long sentences; don't start three in a row
    the same way. For opinion or narrative docs, let a point of view show.

## How to run

0. **Draft the content, then run the humanizer pass above** on it.

1. **Write the content spec** as a JSON file (in the scratchpad dir). Shape:

```json
{
  "title": "Document Title",
  "lede": "Optional one-paragraph intro under the title.",
  "blocks": [
    {"t": "h2",     "text": "1. Section heading"},
    {"t": "h3",     "text": "Subsection heading"},
    {"t": "body",   "text": "Paragraph. Supports **bold**, `code`, [link](url)."},
    {"t": "bullet", "text": "**Label**: a bullet with a bold lead-in."},
    {"t": "num",    "text": "An ordered step."},
    {"t": "label",  "text": "A bold lead-in line above the next block."},
    {"t": "code",   "text": "line one\nline two"},
    {"t": "table",  "header": ["Col A", "Col B"], "rows": [["1", "2"], ["3", "4"]]}
  ]
}
```

   Inline markdown works in any text field: `**bold**`, `` `code` ``,
   `[text](url)`. Aliases: `h1`->title, `p`->body, `li`->bullet, `ol`->num,
   `bold`->label, `quote`/`pre`->code.

2. **Run the builder** through the nuBeam project venv (it carries the
   operations@nubeam.io OAuth token):

```bash
cd "/Users/harshshah/Documents/Claude Workflows/nuBeam/NB - Second Brain/scripts/push_to_drive"
./.venv/bin/python ~/.claude/skills/gdoc/build_gdoc.py <spec.json>
```

   - Creates a NEW doc and prints its URL.
   - To overwrite an existing doc: `--doc-id <ID>` (clears and rebuilds the body).
   - To share: `--share email@domain.com` (defaults to writer) or
     `--share email@domain.com:reader`.

3. **Give the user the URL.** Keep internal/strategy docs private to
   operations@nubeam.io; share to specific people only, never `anyone-with-link`.

## Auth

The builder reads `token.json` + `credentials.json` from the nuBeam
`scripts/push_to_drive` directory by default. Override with the `GDOC_AUTH_DIR`
env var to point at a different OAuth dir. If the token is expired, run the
project's `reauth.py` first. Creating and editing app-owned docs works with the
existing `drive.file` scope.

## Notes

- The builder is idempotent on `--doc-id`: it wipes the body and rebuilds, so you
  can iterate on content and re-run safely.
- Tables are inserted as real Docs tables (bottom-to-top to keep indices stable),
  not monospace pipe blocks, so they stay editable and skimmable.
- For very long docs, prefer numbered H2 sections + H3 subsections to keep the
  outline navigable in the Docs sidebar.

## Multi-tab docs

For a doc with several tabs (e.g. copies in one tab, strategy in another), use
`build_gdoc_tabs.py` instead. Same house style, same block shapes; the spec wraps
one spec per tab:

```json
{"title": "Doc title", "tabs": [
  {"tab": "Tab name", "title": "Tab heading", "lede": "...", "blocks": [ ... ]},
  {"tab": "Second tab", "title": "...", "blocks": [ ... ]}
]}
```

```bash
cd "<project>/scripts/push_to_drive"
GDOC_AUTH_DIR="$PWD/kg_auth" ./.venv/bin/python ~/.claude/skills/gdoc/build_gdoc_tabs.py <tabs.json> [--doc-id ID] [--share email]
```

Tabs are created with `addDocumentTab` when missing and rebuilt in place when
present, so re-running on `--doc-id` is safe. The first tab of a new doc is
renamed to the first tab spec. Images are not supported in tab mode.

Auth note (2026-09-24): the operations@nubeam.io token in `scripts/push_to_drive`
fails to refresh ("invalid_client"). `kg_auth/` (harsh@klientsgrowth.com) works;
point `GDOC_AUTH_DIR` at it until the nuBeam client secret is fixed.

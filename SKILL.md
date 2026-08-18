---
name: gdoc
description: Create a clean, skimmable, well-formatted Google Doc from content, matching the locked house style (Geist font, H1/H2/H3 hierarchy, bullets, bold lead-in labels, bordered code blocks, real Google Docs tables). Trigger with /gdoc or whenever the user asks to "create/build/make a Google Doc", turn notes/a plan/an SOP/a report into a Google Doc, or format content as a Google Doc.
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

The visual spec below (Geist typography, real tables, etc.) still applies — the content-doc standard governs what's IN the Doc; this skill's visual spec governs how it's typeset. When updating an existing content Doc, regenerate in place via `--doc-id <existing_id>` (never mint a new URL for the same page).

## The visual spec (locked — do not re-ask, do not deviate)

- **Font:** Geist everywhere (title, headings, body, bullets, tables, code).
- **Margins:** 72pt all four sides.
- **Title (H1):** Geist 18pt bold. One per doc, at the top.
- **Section headings (H2):** Geist 15pt bold. Number them (`1.`, `2.`, ...) when
  the doc has clear sequential sections, matching the reference.
- **Subsections (H3):** Geist 12pt bold.
- **Body:** Geist 11pt.
- **Bullets:** `BULLET_DISC_CIRCLE_SQUARE`, 11pt. Use a bold lead-in label where
  it aids skimming: `**Label** — detail`.
- **Ordered steps:** numbered list, 11pt.
- **Bold lead-in line (`label`):** a standalone bold 11pt line above a block.
- **Code / structured blocks:** Geist 10pt, muted grey, 2pt grey left border,
  indented. For payloads, configs, email copy, command snippets.
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
- No em-dashes in any cold outreach copy embedded in the doc (project rule).
- Lead bullets with a bold label when it speeds scanning.
- Prefer a table over a long bulleted list when the data is comparative.

## How to run

1. **Write the content spec** as a JSON file (in the scratchpad dir). Shape:

```json
{
  "title": "Document Title",
  "lede": "Optional one-paragraph intro under the title.",
  "blocks": [
    {"t": "h2",     "text": "1. Section heading"},
    {"t": "h3",     "text": "Subsection heading"},
    {"t": "body",   "text": "Paragraph. Supports **bold**, `code`, [link](url)."},
    {"t": "bullet", "text": "**Label** — a bullet with a bold lead-in."},
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

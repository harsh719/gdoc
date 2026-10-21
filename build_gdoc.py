"""Build a clean, skimmable Google Doc to the locked house spec.

Produces docs matching the reference style: Geist font, H1/H2/H3 hierarchy,
11pt body + bullets, bold lead-in labels, indented code blocks (no border), and
REAL Google Docs tables with a bold header row.

Auth: reuses the nuBeam Second Brain OAuth helper (operations@nubeam.io).
Token + credentials are read from GDOC_AUTH_DIR, defaulting to the project's
scripts/push_to_drive directory. The cached token already carries drive.file +
spreadsheets + readonly scopes, which is enough to create and edit app-owned docs.

Usage:
    python build_gdoc.py <spec.json> [--doc-id EXISTING_ID] [--share EMAIL[:role]]

Spec JSON shape:
{
  "title": "Document Title",
  "lede": "Optional one-paragraph intro under the title (supports inline md).",
  "blocks": [
    {"t": "h2",     "text": "1. Section heading"},
    {"t": "h3",     "text": "Subsection heading"},
    {"t": "body",   "text": "A paragraph. Supports **bold**, `code`, [link](url)."},
    {"t": "bullet", "text": "A point. Use **Label** — detail for lead-in labels."},
    {"t": "num",    "text": "An ordered step."},
    {"t": "label",  "text": "A bold lead-in line above a block."},
    {"t": "code",   "text": "monospace-ish block\\nsecond line"},
    {"t": "table",  "header": ["Col A", "Col B"], "rows": [["1", "2"], ["3", "4"]]}
  ]
}

Inline markdown supported in any text field: **bold**, `code`, [text](url).
Prints the doc URL on success.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ---------------------------------------------------------------- auth

DEFAULT_AUTH_DIR = Path(
    "/Users/harshshah/Documents/Agentic workflows/nuBeam/NB - Second Brain/scripts/push_to_drive"
)
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]


def _auth_dir() -> Path:
    return Path(os.environ.get("GDOC_AUTH_DIR", str(DEFAULT_AUTH_DIR)))


def _creds() -> Credentials:
    token = _auth_dir() / "token.json"
    if not token.exists():
        sys.exit(
            f"No token at {token}. Set GDOC_AUTH_DIR to a dir with token.json "
            f"(operations@nubeam.io), or run the project's reauth.py first."
        )
    stored = json.loads(token.read_text()).get("scopes")
    return Credentials.from_authorized_user_file(str(token), stored or SCOPES)


def docs_service():
    return build("docs", "v1", credentials=_creds())


def drive_service():
    return build("drive", "v3", credentials=_creds())


# ---------------------------------------------------------------- house spec

GEIST = {"weightedFontFamily": {"fontFamily": "Geist"}}


def _pt(n):
    return {"magnitude": n, "unit": "PT"}


def _para_style(named, above, below, extra=None):
    ps = {
        "namedStyleType": named,
        "spaceAbove": _pt(above),
        "spaceBelow": _pt(below),
    }
    fields = "namedStyleType,spaceAbove,spaceBelow"
    if extra:
        ps.update(extra)
        fields += "," + ",".join(extra.keys())
    return ps, fields


def _text_style(size, bold, color=None):
    ts = {"weightedFontFamily": GEIST["weightedFontFamily"], "fontSize": _pt(size), "bold": bold}
    fields = "weightedFontFamily,fontSize,bold"
    if color:
        ts["foregroundColor"] = {"color": {"rgbColor": color}}
        fields += ",foregroundColor"
    return ts, fields


# kind -> (named style, fontsize, bold, spaceAbove, spaceBelow, color, extra_para)
BLOCK_SPEC = {
    "title":  ("HEADING_1",   18, True,  0,  12, {"red": 0.0, "green": 0.0, "blue": 0.0}, None),
    "h2":     ("HEADING_2",   15, True,  18, 6,  {"red": 0.1, "green": 0.1, "blue": 0.1}, None),
    "h3":     ("HEADING_3",   12, True,  12, 4,  {"red": 0.15, "green": 0.15, "blue": 0.15}, None),
    "body":   ("NORMAL_TEXT", 11, False, 4,  4,  None, None),
    "bullet": ("NORMAL_TEXT", 11, False, 2,  2,  None, None),
    "num":    ("NORMAL_TEXT", 11, False, 2,  2,  None, None),
    "label":  ("NORMAL_TEXT", 11, True,  8,  2,  None, None),
    "code":   ("NORMAL_TEXT", 10, False, 4,  8,  {"red": 0.2, "green": 0.2, "blue": 0.2}, {
        "indentStart": _pt(18),
        "indentFirstLine": _pt(18),  # must equal indentStart or wrapped lines hang (2026-10-01)
        "indentEnd": _pt(18),
        # NO borderLeft: Harsh banned the grey vertical line (2026-10-01).
    }),
}

# normalize aliases
ALIASES = {"h1": "title", "p": "body", "para": "body", "paragraph": "body",
           "li": "bullet", "ul": "bullet", "ol": "num", "numbered": "num",
           "bold": "label", "quote": "code", "pre": "code"}


# ---------------------------------------------------------------- inline md

BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
CODE_RE = re.compile(r"`([^`]+?)`")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def parse_inline(text: str):
    """Return (plain_text, [ {type,start,end,url?} ]) with block-local offsets."""
    out = []
    styles = []
    i = 0
    while i < len(text):
        m = LINK_RE.match(text, i)
        if m:
            start = len("".join(out))
            out.append(m.group(1))
            styles.append({"type": "link", "start": start, "end": start + len(m.group(1)), "url": m.group(2)})
            i = m.end()
            continue
        m = BOLD_RE.match(text, i)
        if m:
            start = len("".join(out))
            # Recurse: bold can wrap a link, e.g. **[title](url)**. Without this the
            # inner markdown is emitted literally and leaks into the document.
            inner_plain, inner_styles = parse_inline(m.group(1))
            out.append(inner_plain)
            styles.append({"type": "bold", "start": start, "end": start + len(inner_plain)})
            for st in inner_styles:
                styles.append({**st, "start": start + st["start"], "end": start + st["end"]})
            i = m.end()
            continue
        m = CODE_RE.match(text, i)
        if m:
            start = len("".join(out))
            out.append(m.group(1))
            styles.append({"type": "inlinecode", "start": start, "end": start + len(m.group(1))})
            i = m.end()
            continue
        out.append(text[i])
        i += 1
    return "".join(out), styles


# ---------------------------------------------------------------- build

def normalize_blocks(spec: dict) -> list[dict]:
    blocks = [{"t": "title", "text": spec["title"]}]
    if spec.get("lede"):
        blocks.append({"t": "body", "text": spec["lede"]})
    for b in spec.get("blocks", []):
        t = ALIASES.get(b.get("t"), b.get("t"))
        b = dict(b)
        b["t"] = t
        blocks.append(b)
    return blocks


def build_doc(spec: dict, doc_id: str | None = None):
    docs = docs_service()
    title = spec["title"]

    if doc_id is None:
        created = docs.documents().create(body={"title": title}).execute()
        doc_id = created["documentId"]
    else:
        # clear existing body
        d = docs.documents().get(documentId=doc_id).execute()
        end = d["body"]["content"][-1]["endIndex"]
        if end > 2:
            docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
                {"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end - 1}}}
            ]}).execute()

    blocks = normalize_blocks(spec)

    # Pass 1: build a single text string + record ranges. Tables become a
    # one-char placeholder paragraph; we fill real tables in a later pass.
    text_parts: list[str] = []
    para_ops: list[tuple] = []      # (start, end, kind)
    inline_ops: list[dict] = []     # absolute inline style ranges
    table_jobs: list[dict] = []     # {index, header, rows}
    image_jobs: list[dict] = []     # {index, path, width}
    cursor = 1

    for b in blocks:
        kind = b["t"]
        if kind == "image":
            # placeholder empty paragraph; the inline image is inserted here later
            seg = "\n"
            text_parts.append(seg)
            image_jobs.append({"index": cursor, "path": b["path"], "width": b.get("width", 468),
                               "caption": b.get("caption")})
            cursor += len(seg)
            continue
        if kind == "table":
            # placeholder empty paragraph; real table inserted here later
            seg = "\n"
            text_parts.append(seg)
            table_jobs.append({"index": cursor, "header": b.get("header"), "rows": b.get("rows", [])})
            cursor += len(seg)
            continue
        if kind == "code":
            raw = b["text"].replace("\r\n", "\n")
            seg = raw + "\n"
            text_parts.append(seg)
            para_ops.append((cursor, cursor + len(seg) - 1, "code"))
            cursor += len(seg)
            continue
        plain, styles = parse_inline(b["text"])
        seg = plain + "\n"
        text_parts.append(seg)
        para_ops.append((cursor, cursor + len(seg) - 1, kind))
        for s in styles:
            inline_ops.append({**s, "start": cursor + s["start"], "end": cursor + s["end"]})
        cursor += len(seg)

    full_text = "".join(text_parts)

    # Insert all text at once.
    docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
        {"insertText": {"location": {"index": 1}, "text": full_text}}
    ]}).execute()

    # Pass 2: paragraph + base text styles.
    reqs: list[dict] = []
    for start, end, kind in para_ops:
        if end <= start:
            continue
        named, size, bold, above, below, color, extra = BLOCK_SPEC[kind]
        ps, pfields = _para_style(named, above, below, extra)
        reqs.append({"updateParagraphStyle": {
            "range": {"startIndex": start, "endIndex": end}, "paragraphStyle": ps, "fields": pfields}})
        ts, tfields = _text_style(size, bold, color)
        reqs.append({"updateTextStyle": {
            "range": {"startIndex": start, "endIndex": end}, "textStyle": ts, "fields": tfields}})
        if kind == "bullet":
            reqs.append({"createParagraphBullets": {
                "range": {"startIndex": start, "endIndex": end}, "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
        elif kind == "num":
            reqs.append({"createParagraphBullets": {
                "range": {"startIndex": start, "endIndex": end}, "bulletPreset": "NUMBERED_DECIMAL_ALPHA_ROMAN"}})

    # Pass 3: inline overrides (bold / code / link).
    for s in inline_ops:
        if s["end"] <= s["start"]:
            continue
        if s["type"] == "bold":
            reqs.append({"updateTextStyle": {
                "range": {"startIndex": s["start"], "endIndex": s["end"]},
                "textStyle": {"bold": True}, "fields": "bold"}})
        elif s["type"] == "inlinecode":
            reqs.append({"updateTextStyle": {
                "range": {"startIndex": s["start"], "endIndex": s["end"]},
                "textStyle": {"weightedFontFamily": {"fontFamily": "Roboto Mono"},
                              "backgroundColor": {"color": {"rgbColor": {"red": 0.95, "green": 0.95, "blue": 0.96}}}},
                "fields": "weightedFontFamily,backgroundColor"}})
        elif s["type"] == "link":
            reqs.append({"updateTextStyle": {
                "range": {"startIndex": s["start"], "endIndex": s["end"]},
                "textStyle": {"link": {"url": s["url"]}}, "fields": "link"}})

    for i in range(0, len(reqs), 400):
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": reqs[i:i + 400]}).execute()

    # Page margins (match reference: 72pt all sides).
    docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
        {"updateDocumentStyle": {"documentStyle": {
            "marginTop": _pt(72), "marginBottom": _pt(72),
            "marginLeft": _pt(72), "marginRight": _pt(72),
            "documentFormat": {"documentMode": "PAGES"}},
            "fields": "marginTop,marginBottom,marginLeft,marginRight,documentFormat"}}
    ]}).execute()

    # Pass 4: tables + images, bottom-to-top so earlier placeholder indices stay valid.
    jobs = [dict(j, kind="table") for j in table_jobs] + [dict(j, kind="image") for j in image_jobs]
    uploaded: list[str] = []
    for job in sorted(jobs, key=lambda j: -j["index"]):
        if job["kind"] == "table":
            _insert_table(docs, doc_id, job["index"], job.get("header"), job.get("rows", []))
        else:
            fid = _insert_image(docs, doc_id, job["index"], job["path"], job["width"], job.get("caption"))
            if fid:
                uploaded.append(fid)
    # revoke the temporary anyone-with-link share used so Docs could fetch the bytes
    for fid in uploaded:
        try:
            drive_service().permissions().delete(fileId=fid, permissionId="anyoneWithLink").execute()
        except Exception:
            pass

    return doc_id


_IMG_FOLDER_CACHE: dict = {}


def _img_folder(drive):
    """One Drive folder that holds images embedded by this builder (kept so the doc's images stay resolvable)."""
    if "id" in _IMG_FOLDER_CACHE:
        return _IMG_FOLDER_CACHE["id"]
    q = "name='gdoc-builder-images' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    r = drive.files().list(q=q, fields="files(id)").execute().get("files", [])
    if r:
        fid = r[0]["id"]
    else:
        fid = drive.files().create(body={"name": "gdoc-builder-images",
                                         "mimeType": "application/vnd.google-apps.folder"}, fields="id").execute()["id"]
    _IMG_FOLDER_CACHE["id"] = fid
    return fid


def _insert_image(docs, doc_id, at_index, path, width_pt, caption=None):
    """Upload a local image to Drive, share it by link for the fetch, insert it inline at `at_index`
    (the placeholder paragraph), sized to `width_pt` wide (aspect preserved). Returns the Drive file id."""
    from googleapiclient.http import MediaFileUpload
    p = Path(path)
    if not p.exists():
        print(f"[image] missing: {path}", file=sys.stderr)
        return None
    drive = drive_service()
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    meta = {"name": p.name, "parents": [_img_folder(drive)]}
    f = drive.files().create(body=meta, media_body=MediaFileUpload(str(p), mimetype=mime),
                             fields="id").execute()
    fid = f["id"]
    drive.permissions().create(fileId=fid, body={"type": "anyone", "role": "reader"}).execute()
    uri = f"https://drive.google.com/uc?export=download&id={fid}"
    # width only: Docs keeps the aspect ratio when a single dimension is given
    reqs = [{"insertInlineImage": {"location": {"index": at_index}, "uri": uri,
                                   "objectSize": {"width": _pt(width_pt)}}}]
    if caption:
        reqs.append({"insertText": {"location": {"index": at_index + 1}, "text": "\n" + caption}})
    docs.documents().batchUpdate(documentId=doc_id, body={"requests": reqs}).execute()
    if caption:
        d = docs.documents().get(documentId=doc_id).execute()
        # style the caption paragraph (the one right after the image) as small grey text
        st = at_index + 2; en = st + len(caption)
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
            {"updateTextStyle": {"range": {"startIndex": st, "endIndex": en},
                                 "textStyle": {"fontSize": _pt(9), "italic": True,
                                               "foregroundColor": {"color": {"rgbColor": {"red": 0.45, "green": 0.45, "blue": 0.5}}}},
                                 "fields": "fontSize,italic,foregroundColor"}}]}).execute()
    return fid


def _insert_table(docs, doc_id, at_index, header, rows):
    data = ([header] if header else []) + rows
    if not data:
        return
    nrows = len(data)
    ncols = max(len(r) for r in data)

    docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
        {"insertTable": {"location": {"index": at_index}, "rows": nrows, "columns": ncols}}
    ]}).execute()

    # Find the table we just inserted (first table at/after at_index).
    d = docs.documents().get(documentId=doc_id).execute()
    table_el = None
    for el in d["body"]["content"]:
        if "table" in el and el.get("startIndex", 0) >= at_index:
            table_el = el
            break
    if table_el is None:
        return

    # Collect cell insertion points; fill in reverse so indices stay valid.
    cells = []
    for r, row in enumerate(table_el["table"]["tableRows"]):
        for c, cell in enumerate(row["tableCells"]):
            cstart = cell["content"][0]["startIndex"]
            val = data[r][c] if r < len(data) and c < len(data[r]) else ""
            cells.append((cstart, str(val)))
    fill = [{"insertText": {"location": {"index": cs}, "text": v}}
            for cs, v in sorted(cells, key=lambda x: -x[0]) if v]
    if fill:
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": fill}).execute()

    # Re-fetch to style cell text (ranges are stable within a pure-style batch).
    d = docs.documents().get(documentId=doc_id).execute()
    table_el = None
    for el in d["body"]["content"]:
        if "table" in el and el.get("startIndex", 0) >= at_index:
            table_el = el
            break
    style_reqs = []
    for r, row in enumerate(table_el["table"]["tableRows"]):
        is_header = bool(header) and r == 0
        for cell in row["tableCells"]:
            cs = cell["content"][0]["startIndex"]
            ce = cell["content"][-1]["endIndex"] - 1
            if ce <= cs:
                continue
            style_reqs.append({"updateTextStyle": {
                "range": {"startIndex": cs, "endIndex": ce},
                "textStyle": {"weightedFontFamily": {"fontFamily": "Geist"},
                              "fontSize": _pt(11), "bold": is_header},
                "fields": "weightedFontFamily,fontSize,bold"}})
            if is_header:
                style_reqs.append({"updateTableCellStyle": {
                    "tableCellStyle": {"backgroundColor": {"color": {"rgbColor": {
                        "red": 0.95, "green": 0.95, "blue": 0.96}}}},
                    "fields": "backgroundColor",
                    "tableRange": {
                        "tableCellLocation": {
                            "tableStartLocation": {"index": table_el["startIndex"]},
                            "rowIndex": 0,
                            "columnIndex": row["tableCells"].index(cell),
                        },
                        "rowSpan": 1, "columnSpan": 1,
                    }}})
    # Fit columns to the page content width (612pt letter - 72pt margins each side),
    # weighting wider columns by their longest cell text so nothing cuts off in page mode.
    content_w = 612 - 72 - 72 - 2
    lens = [0] * ncols
    for row in data:
        for c, val in enumerate(row):
            lens[c] = max(lens[c], min(len(str(val)), 60))
    weights = [max(n, 6) ** 0.8 for n in lens]
    widths = [max(55, content_w * w / sum(weights)) for w in weights]
    scale = content_w / sum(widths)
    style_reqs += [{"updateTableColumnProperties": {
        "tableStartLocation": {"index": table_el["startIndex"]},
        "columnIndices": [c],
        "tableColumnProperties": {"widthType": "FIXED_WIDTH",
                                  "width": {"magnitude": round(w * scale, 1), "unit": "PT"}},
        "fields": "widthType,width"}} for c, w in enumerate(widths)]

    for i in range(0, len(style_reqs), 400):
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": style_reqs[i:i + 400]}).execute()


def share(doc_id, email, role="writer"):
    drive_service().permissions().create(
        fileId=doc_id,
        body={"type": "user", "role": role, "emailAddress": email},
        sendNotificationEmail=False,
    ).execute()


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    spec_path = args[0]
    doc_id = None
    share_target = None
    i = 1
    while i < len(args):
        if args[i] == "--doc-id":
            doc_id = args[i + 1]; i += 2
        elif args[i] == "--share":
            share_target = args[i + 1]; i += 2
        else:
            i += 1

    spec = json.loads(Path(spec_path).read_text())
    doc_id = build_doc(spec, doc_id)

    if share_target:
        email, _, role = share_target.partition(":")
        share(doc_id, email, role or "writer")
        print(f"Shared with {email} ({role or 'writer'})")

    print(f"https://docs.google.com/document/d/{doc_id}/edit")


if __name__ == "__main__":
    main()

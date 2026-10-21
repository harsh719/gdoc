#!/usr/bin/env python3
"""Tab-aware companion to build_gdoc.py.

Usage:
  build_gdoc_tabs.py <tabs.json> [--doc-id ID] [--share email[:role]]

tabs.json:
  {"title": "Doc title", "tabs": [ {"tab": "Tab name", <same spec shape as build_gdoc.py: title, lede, blocks>}, ... ]}

Each tab spec is rendered with the exact same house style as build_gdoc.py (same
BLOCK_SPEC, inline parsing, tables). Tabs are created with addDocumentTab if
missing and rebuilt in place if present. The first tab of a new doc is renamed
to the first tab spec's name.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_gdoc as G  # noqa: E402


def _tabs(docs, doc_id):
    d = docs.documents().get(documentId=doc_id, includeTabsContent=True).execute()
    out = []
    for t in d.get("tabs", []):
        out.append((t["tabProperties"]["title"], t["tabProperties"]["tabId"], t["documentTab"]["body"]["content"]))
    return out


def _ensure_tab(docs, doc_id, name, rename_first=False):
    tabs = _tabs(docs, doc_id)
    for title, tid, _ in tabs:
        if title == name:
            return tid
    if rename_first and tabs:
        tid = tabs[0][1]
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
            {"updateDocumentTabProperties": {"tabProperties": {"tabId": tid, "title": name}, "fields": "title"}}
        ]}).execute()
        return tid
    docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
        {"addDocumentTab": {"tabProperties": {"title": name}}}
    ]}).execute()
    for title, tid, _ in _tabs(docs, doc_id):
        if title == name:
            return tid
    raise RuntimeError(f"could not create tab {name}")


def _clear_tab(docs, doc_id, tab_id):
    for _, tid, content in _tabs(docs, doc_id):
        if tid == tab_id:
            end = content[-1]["endIndex"]
            if end > 2:
                docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
                    {"deleteContentRange": {"range": {"tabId": tab_id, "startIndex": 1, "endIndex": end - 1}}}
                ]}).execute()
            return


def _tab_content(docs, doc_id, tab_id):
    for _, tid, content in _tabs(docs, doc_id):
        if tid == tab_id:
            return content
    return []


def _insert_table(docs, doc_id, tab_id, at_index, header, rows):
    data = ([header] if header else []) + rows
    if not data:
        return
    nrows, ncols = len(data), max(len(r) for r in data)
    docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
        {"insertTable": {"location": {"tabId": tab_id, "index": at_index}, "rows": nrows, "columns": ncols}}
    ]}).execute()

    def find_table():
        for el in _tab_content(docs, doc_id, tab_id):
            if "table" in el and el.get("startIndex", 0) >= at_index:
                return el
        return None

    table_el = find_table()
    if table_el is None:
        return
    cells = []
    for r, row in enumerate(table_el["table"]["tableRows"]):
        for c, cell in enumerate(row["tableCells"]):
            cstart = cell["content"][0]["startIndex"]
            val = data[r][c] if r < len(data) and c < len(data[r]) else ""
            cells.append((cstart, str(val)))
    fill = [{"insertText": {"location": {"tabId": tab_id, "index": cs}, "text": v}}
            for cs, v in sorted(cells, key=lambda x: -x[0]) if v]
    if fill:
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": fill}).execute()
    table_el = find_table()
    style_reqs = []
    for r, row in enumerate(table_el["table"]["tableRows"]):
        is_header = bool(header) and r == 0
        for ci, cell in enumerate(row["tableCells"]):
            cs = cell["content"][0]["startIndex"]
            ce = cell["content"][-1]["endIndex"] - 1
            if ce <= cs:
                continue
            style_reqs.append({"updateTextStyle": {
                "range": {"tabId": tab_id, "startIndex": cs, "endIndex": ce},
                "textStyle": {"weightedFontFamily": {"fontFamily": "Geist"}, "fontSize": G._pt(11), "bold": is_header},
                "fields": "weightedFontFamily,fontSize,bold"}})
            if is_header:
                style_reqs.append({"updateTableCellStyle": {
                    "tableCellStyle": {"backgroundColor": {"color": {"rgbColor": {"red": 0.95, "green": 0.95, "blue": 0.96}}}},
                    "fields": "backgroundColor",
                    "tableRange": {"tableCellLocation": {
                        "tableStartLocation": {"tabId": tab_id, "index": table_el["startIndex"]},
                        "rowIndex": 0, "columnIndex": ci}, "rowSpan": 1, "columnSpan": 1}}})
    for i in range(0, len(style_reqs), 400):
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": style_reqs[i:i + 400]}).execute()


def build_tab(docs, doc_id, tab_id, spec):
    _clear_tab(docs, doc_id, tab_id)
    blocks = G.normalize_blocks(spec)
    text_parts, para_ops, inline_ops, table_jobs = [], [], [], []
    cursor = 1
    for b in blocks:
        kind = b["t"]
        if kind == "image":
            continue  # not supported in tab mode
        if kind == "table":
            text_parts.append("\n")
            table_jobs.append({"index": cursor, "header": b.get("header"), "rows": b.get("rows", [])})
            cursor += 1
            continue
        if kind == "code":
            seg = b["text"].replace("\r\n", "\n") + "\n"
            text_parts.append(seg)
            para_ops.append((cursor, cursor + len(seg) - 1, "code"))
            cursor += len(seg)
            continue
        plain, styles = G.parse_inline(b["text"])
        seg = plain + "\n"
        text_parts.append(seg)
        para_ops.append((cursor, cursor + len(seg) - 1, kind))
        for s in styles:
            inline_ops.append({**s, "start": cursor + s["start"], "end": cursor + s["end"]})
        cursor += len(seg)

    full_text = "".join(text_parts)
    # insert in chunks (API limit on request size)
    pos = 1
    for i in range(0, len(full_text), 60000):
        chunk = full_text[i:i + 60000]
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
            {"insertText": {"location": {"tabId": tab_id, "index": pos}, "text": chunk}}]}).execute()
        pos += len(chunk)

    reqs = []
    for start, end, kind in para_ops:
        if end <= start:
            continue
        named, size, bold, above, below, color, extra = G.BLOCK_SPEC[kind]
        ps, pfields = G._para_style(named, above, below, extra)
        rng = {"tabId": tab_id, "startIndex": start, "endIndex": end}
        reqs.append({"updateParagraphStyle": {"range": rng, "paragraphStyle": ps, "fields": pfields}})
        ts, tfields = G._text_style(size, bold, color)
        reqs.append({"updateTextStyle": {"range": rng, "textStyle": ts, "fields": tfields}})
        if kind == "bullet":
            reqs.append({"createParagraphBullets": {"range": rng, "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
        elif kind == "num":
            reqs.append({"createParagraphBullets": {"range": rng, "bulletPreset": "NUMBERED_DECIMAL_ALPHA_ROMAN"}})
    for s in inline_ops:
        if s["end"] <= s["start"]:
            continue
        rng = {"tabId": tab_id, "startIndex": s["start"], "endIndex": s["end"]}
        if s["type"] == "bold":
            reqs.append({"updateTextStyle": {"range": rng, "textStyle": {"bold": True}, "fields": "bold"}})
        elif s["type"] == "inlinecode":
            reqs.append({"updateTextStyle": {"range": rng, "textStyle": {
                "weightedFontFamily": {"fontFamily": "Roboto Mono"},
                "backgroundColor": {"color": {"rgbColor": {"red": 0.95, "green": 0.95, "blue": 0.96}}}},
                "fields": "weightedFontFamily,backgroundColor"}})
        elif s["type"] == "link":
            reqs.append({"updateTextStyle": {"range": rng, "textStyle": {"link": {"url": s["url"]}}, "fields": "link"}})
    for i in range(0, len(reqs), 400):
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": reqs[i:i + 400]}).execute()

    docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
        {"updateDocumentStyle": {"tabId": tab_id, "documentStyle": {
            "marginTop": G._pt(72), "marginBottom": G._pt(72), "marginLeft": G._pt(72), "marginRight": G._pt(72)},
            "fields": "marginTop,marginBottom,marginLeft,marginRight"}}]}).execute()

    for job in sorted(table_jobs, key=lambda j: -j["index"]):
        _insert_table(docs, doc_id, tab_id, job["index"], job.get("header"), job.get("rows", []))


def build(spec, doc_id=None):
    docs = G.docs_service()
    if doc_id is None:
        doc_id = docs.documents().create(body={"title": spec["title"]}).execute()["documentId"]
    else:
        G.drive_service().files().update(fileId=doc_id, body={"name": spec["title"]}).execute()
    for i, tab in enumerate(spec["tabs"]):
        tid = _ensure_tab(docs, doc_id, tab["tab"], rename_first=(i == 0))
        build_tab(docs, doc_id, tid, tab)
        print(f"tab built: {tab['tab']}", file=sys.stderr)
    return doc_id


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    doc_id, share_target = None, None
    i = 1
    while i < len(args):
        if args[i] == "--doc-id":
            doc_id = args[i + 1]; i += 2
        elif args[i] == "--share":
            share_target = args[i + 1]; i += 2
        else:
            i += 1
    spec = json.loads(Path(args[0]).read_text())
    doc_id = build(spec, doc_id)
    if share_target:
        email, _, role = share_target.partition(":")
        G.share(doc_id, email, role or "writer")
    print(f"https://docs.google.com/document/d/{doc_id}/edit")


if __name__ == "__main__":
    main()

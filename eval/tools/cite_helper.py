#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标注辅助：把候选题目对应的原文片段按行号抽出来，供你填 gold_span_ids 与写答案要点。

用法:
    python cite_helper.py --qid q001                # 只抽某一条
    python cite_helper.py --limit 5                 # 抽前 5 条候选
    python cite_helper.py --type multi_hop --limit 3
"""
import argparse
import csv
import re
import sys
from pathlib import Path

BASE = Path(r"D:\DSH-WORK\knowagent\eval")
CORPUS = Path(r"D:\DSH-WORK\corpus\raw")
H = re.compile(r"(?m)^(#{2,3})\s+(.+?)\s*$")
MAX_LINES = 60


def resolve(doc_id: str) -> Path:
    p = CORPUS / doc_id
    if p.exists():
        return p
    # 容错：候选里的路径可能带 docs/ 前缀或 ../ 相对路径
    alt = CORPUS / doc_id.replace("docs/", "", 1)
    if alt.exists():
        return alt
    hits = list(CORPUS.rglob(Path(doc_id).name))
    return hits[0] if hits else p


def extract_section(path: Path, title_hint: str):
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    marks = [(i, m.group(2).strip()) for i, l in enumerate(lines)
             for m in [H.match(l)] if m]
    for idx, (i, title) in enumerate(marks):
        if title_hint and title_hint[:20] in title:
            end = marks[idx + 1][0] if idx + 1 < len(marks) else len(lines)
            return title, lines[i:min(end, i + MAX_LINES)], i
    return None, None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default=str(BASE / "questions_candidates.csv"))
    ap.add_argument("--qid", default="")
    ap.add_argument("--type", default="")
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--out", default=str(BASE / "annotation_worksheet.md"))
    args = ap.parse_args()

    qpath = Path(args.questions)
    with qpath.open(encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))

    if args.qid:
        rows = [r for r in rows if r.get("qid") == args.qid]
    if args.type:
        rows = [r for r in rows if r.get("type") == args.type]
    rows = rows[: args.limit]

    out = []
    out.append("# 标注工作表（由 cite_helper.py 生成）\n")
    out.append("> 用法：每条候选下方是原文片段。请在 CSV 里补 `question` / `answer_keypoints` /")
    out.append("> `kp_keywords` / `gold_span_ids`，并把要点对应的原文行复制到 `gold_spans/<qid>.txt`。\n")

    for r in rows:
        doc_id = (r.get("gold_doc_ids") or "").split("|")[0]
        hint = r.get("_source_title", "")
        out.append("---\n")
        out.append(f"## {r.get('qid') or '(未编号)'} · {r.get('type')}\n")
        out.append(f"- 来源文档：`{doc_id}`")
        out.append(f"- 候选章节：{hint}")
        if r.get("_refs"):
            out.append(f"- 该文档引用了：`{r['_refs']}`  ← 多跳题的第二跳候选")
        out.append(f"- 正文字数：{r.get('_body_chars')}")
        out.append("")
        path = resolve(doc_id)
        title, body, start = (None, None, None)
        if path.exists() and hint:
            title, body, start = extract_section(path, hint)
        if body:
            out.append(f"**原文（{path.name}，从第 {start + 1} 行起）**\n")
            out.append("```markdown")
            for off, line in enumerate(body):
                out.append(f"{start + 1 + off:4d}| {line}")
            out.append("```\n")
        else:
            out.append(f"> ⚠️ 未能自动定位章节，请手动打开 `{path}` 查找「{hint}」。\n")

    Path(args.out).write_text("\n".join(out), encoding="utf-8")
    print(f"已生成 {args.out}")
    print(f"包含 {len(rows)} 条候选的原文片段，打开它逐条标注即可。")


if __name__ == "__main__":
    main()

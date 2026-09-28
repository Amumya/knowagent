#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从语料中抽候选评测题（只生成骨架，答案必须人工标注）。

用法:
    python build_questions.py                 # 用默认路径
    python build_questions.py --corpus X --out Y
"""
import argparse
import csv
import hashlib
import random
import re
from collections import defaultdict
from pathlib import Path

DEFAULT_CORPUS = Path(r"D:\DSH-WORK\corpus\raw")
DEFAULT_OUT = Path(r"D:\DSH-WORK\knowagent\eval\questions_candidates.csv")
SEED = 20260928

H = re.compile(r"(?m)^(#{2,3})\s+(.+?)\s*$")
LINK_MD = re.compile(r"\]\(([^)]+\.mdx?)(?:#[^)]*)?\)")
DEPRECATED = re.compile(
    r"(?i)\b(deprecat\w*|no longer|removed in|breaking change|renamed to|"
    r"has been replaced|不再支持|已废弃|已弃用|更名为)"
)
FRONTMATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.S)


def strip_frontmatter(text: str) -> str:
    return FRONTMATTER.sub("", text, count=1)


def split_sections(text: str):
    """按 ## / ### 切分，返回 [(层级, 标题, 正文)]。"""
    marks = [(m.start(), m.group(1), m.group(2).strip()) for m in H.finditer(text)]
    out = []
    for i, (pos, level, title) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        out.append((level, title, text[pos:end]))
    return out


def cluster_key(title: str) -> str:
    """粗糙语义聚类 key：取标题前两个长度>2 的英文实词，用于限制同簇最多 2 条。"""
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]+", title.lower()) if len(w) > 2]
    if words:
        return "-".join(words[:2])
    return hashlib.md5(title.encode("utf-8")).hexdigest()[:8]


def classify(body: str, level: str) -> str:
    if LINK_MD.search(body):
        return "multi_hop"
    if DEPRECATED.search(body):
        return "comparison"
    return "single_hop"


# ---------- 对比题候选：中英/版本对偶分析 ----------

def build_pair_index(files, corpus: Path):
    """建立 (lang 无关的相对路径) -> {lang: (path, text)} 索引。"""
    idx = defaultdict(dict)
    for f in files:
        rel = f.relative_to(corpus).as_posix()
        parts = rel.split("/")
        if len(parts) < 3:
            continue
        lang, rest = parts[0], "/".join(parts[1:])
        try:
            idx[rest][lang] = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
    return idx


def comparison_candidates(pair_index):
    """返回对比题候选：(相对路径, 理由)。"""
    out = []
    for rest, langs in pair_index.items():
        if "en" not in langs or "zh" not in langs:
            continue
        en_txt, zh_txt = strip_frontmatter(langs["en"]), strip_frontmatter(langs["zh"])

        # ① 结构缺失：英文有、中文没有的三级标题（翻译滞后，典型的冲突来源）
        en_titles = {m.group(2).strip() for m in H.finditer(en_txt) if m.group(1) == "###"}
        zh_titles = {m.group(2).strip() for m in H.finditer(zh_txt) if m.group(1) == "###"}
        missing = en_titles - zh_titles
        if missing:
            sample = sorted(missing)[0]
            out.append((rest, f"中文文档缺少英文版小节「{sample}」等 {len(missing)} 处（翻译滞后）"))

        # ② 内容显著不等：中文版明显短于英文版
        en_chars = len(re.sub(r"\s", "", en_txt))
        zh_chars = len(re.sub(r"\s", "", zh_txt))
        if zh_chars > 0 and en_chars > 400 and zh_chars / en_chars < 0.6:
            out.append((rest, f"中文版正文仅英文版的 {zh_chars/en_chars:.0%}（内容不对等）"))

        # ③ 中文版出现过时措辞
        if re.search(r"(不再支持|已废弃|已弃用|即将移除|建议改用|已更名为)", zh_txt):
            out.append((rest, "中文文档含废弃/更名相关措辞，与英文版可能不同步"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--per-cluster", type=int, default=2)
    ap.add_argument("--min-chars", type=int, default=200)
    ap.add_argument("--quota-single", type=int, default=80)
    ap.add_argument("--quota-multi", type=int, default=80)
    ap.add_argument("--quota-compare", type=int, default=50)
    args = ap.parse_args()

    corpus = Path(args.corpus)
    out = Path(args.out)
    random.seed(SEED)

    files = sorted(corpus.rglob("*.md")) + sorted(corpus.rglob("*.mdx"))
    print(f"扫描到 {len(files)} 个文档文件")

    rows, cluster_count, doclink_index = [], defaultdict(int), defaultdict(set)

    for f in files:
        try:
            raw = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        text = strip_frontmatter(raw)
        rel = f.relative_to(corpus).as_posix()
        parts = rel.split("/")
        lang = parts[0] if len(parts) > 0 else "unknown"
        ver = parts[1] if len(parts) > 1 else "unknown"

        # 记录本文档引用了哪些别的文档（用于多跳配对）
        for m in LINK_MD.finditer(text):
            doclink_index[rel].add(m.group(1))

        for level, title, body in split_sections(text):
            body_chars = len(re.sub(r"\s", "", body))
            if body_chars < args.min_chars:
                continue
            ck = cluster_key(title)
            if cluster_count[ck] >= args.per_cluster:
                continue
            cluster_count[ck] += 1
            qtype = classify(body, level)
            rows.append({
                "qid": "",
                "type": qtype,
                "difficulty": "",
                "split": "",
                "question": "",
                "gold_doc_ids": rel,
                "gold_span_ids": "",
                "minimal_evidence": rel,
                "distractor_doc_ids": "",
                "answer_keypoints": "",
                "kp_keywords": "",
                "must_refuse": "0",
                "tenant_scope": "",
                "version_scope": ver,
                "sensitivity": "public",
                "rationale": f"候选来源：{rel} 的「{title}」（{level}，{body_chars} 字）",
                "author": "",
                "date": "",
                "reviewed": "0",
                "_source_title": title,
                "_lang": lang,
                "_body_chars": body_chars,
                "_refs": "|".join(sorted(doclink_index[rel])) or "",
            })

    by_type = defaultdict(list)
    for r in rows:
        by_type[r["type"]].append(r)

    # ---------- 补足对比题候选：用中英对偶分析 ----------
    pair_index = build_pair_index(files, corpus)
    for rest, reason in comparison_candidates(pair_index):
        en_path = f"en/{rest}"
        zh_path = f"zh/{rest}"
        if reason.startswith("中文文档缺少"):
            gold = f"{en_path}|{zh_path}"
        else:
            gold = f"{en_path}|{zh_path}"
        by_type["comparison"].append({
            "qid": "", "type": "comparison", "difficulty": "", "split": "",
            "question": "",
            "gold_doc_ids": gold,
            "gold_span_ids": "",
            "minimal_evidence": gold,
            "distractor_doc_ids": "",
            "answer_keypoints": "", "kp_keywords": "",
            "must_refuse": "0",
            "tenant_scope": "tenant_en|tenant_zh",
            "version_scope": "latest",
            "sensitivity": "public",
            "rationale": f"对比题候选（中英对偶）：{reason}",
            "author": "", "date": "", "reviewed": "0",
            "_source_title": reason[:60],
            "_lang": "zh+en",
            "_body_chars": 0,
            "_refs": "",
        })

    picked = []
    for t, quota in (("single_hop", args.quota_single),
                     ("multi_hop", args.quota_multi),
                     ("comparison", args.quota_compare)):
        pool = by_type.get(t, [])
        random.shuffle(pool)
        picked += pool[:quota]

    if not picked:
        print("没有抽到候选，检查语料路径与 --min-chars")
        return

    out.parent.mkdir(parents=True, exist_ok=True)
    fields = list(picked[0].keys())
    with out.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(picked)

    print(f"\n生成候选 {len(picked)} 条 → {out}")
    for t in ("single_hop", "multi_hop", "comparison"):
        print(f"  {t:12s} 候选池 {len(by_type.get(t, [])):4d} 条，已抽 {len([p for p in picked if p['type'] == t]):3d} 条")
    print(f"\n总候选池规模：{len(rows)} 条（受 --per-cluster={args.per_cluster} 限制）")
    print("\n★ 下一步（人工）：")
    print("  1) 从候选里筛出 32 条单跳 + 32 条多跳 + 32 条对比，删掉多余的")
    print("  2) 给每条写 question（口语化，不要照抄标题）")
    print("  3) 填 answer_keypoints（2-4 个要点）和 kp_keywords（与要点一一对应）")
    print("  4) 填 gold_span_ids，并把原文摘录存到 eval/gold_spans/<qid>.txt")
    print("  5) 另外手工造 32 条超纲题（must_refuse=1）")
    print("  6) 跑 validate.py 校验，FAIL 清零后再跑系统")


if __name__ == "__main__":
    main()

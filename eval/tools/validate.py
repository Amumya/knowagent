#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校验评测集标注质量。跑指标之前必须先让 FAIL 清零。

用法:
    python validate.py
    python validate.py --questions X --negatives Y
"""
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

BASE = Path(r"D:\DSH-WORK\knowagent\eval")
DEFAULT_Q = BASE / "questions.csv"
DEFAULT_HN = BASE / "hard_negatives.csv"

REQUIRED = [
    "qid", "type", "difficulty", "split", "question", "gold_doc_ids", "gold_span_ids",
    "minimal_evidence", "answer_keypoints", "kp_keywords", "must_refuse",
    "tenant_scope", "rationale", "author", "date", "reviewed",
]
VALID_TYPE = {"single_hop", "multi_hop", "comparison", "out_of_scope"}
TARGET_PER_TYPE = 32
MIN_PER_TYPE = 28


def load(p: Path):
    with p.open(encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def split_multi(v: str):
    return [x.strip() for x in (v or "").split("|") if x.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default=str(DEFAULT_Q))
    ap.add_argument("--negatives", default=str(DEFAULT_HN))
    args = ap.parse_args()

    qp = Path(args.questions)
    if not qp.exists():
        print(f"❌ 找不到 {qp}")
        sys.exit(1)

    rows = load(qp)
    fails, warns = [], []
    print(f"读入 {qp.name}：{len(rows)} 条\n")

    # 1) 必填字段
    for i, r in enumerate(rows, 2):
        for f in REQUIRED:
            if not (r.get(f) or "").strip():
                fails.append(f"第{i}行 qid={r.get('qid') or '?'} 缺字段 {f}")

    # 2) qid 唯一 + 题型合法
    ids = [r["qid"] for r in rows if (r.get("qid") or "").strip()]
    for dup, n in Counter(ids).items():
        if n > 1:
            fails.append(f"qid 重复：{dup} 出现 {n} 次")
    for i, r in enumerate(rows, 2):
        if r.get("type") not in VALID_TYPE:
            fails.append(f"第{i}行 type 非法：{r.get('type')}")

    # 3) 四类数量
    tc = Counter(r.get("type") for r in rows)
    print("题型分布：", dict(tc))
    for t in VALID_TYPE:
        if tc.get(t, 0) < MIN_PER_TYPE:
            fails.append(f"题型 {t} 只有 {tc.get(t,0)} 条，少于 {MIN_PER_TYPE} 条（目标 {TARGET_PER_TYPE}）")
    total = len(rows)
    if total and abs(tc.get("out_of_scope", 0) / total - 0.25) > 0.06:
        warns.append(f"超纲题占比 {tc.get('out_of_scope',0)/total:.1%}，建议约 25%")

    # 4) 逻辑一致性
    for i, r in enumerate(rows, 2):
        qid, t = r.get("qid") or f"第{i}行", r.get("type")
        ev = split_multi(r.get("minimal_evidence"))
        gold = split_multi(r.get("gold_doc_ids"))
        if t == "out_of_scope":
            if r.get("must_refuse") != "1":
                fails.append(f"{qid}: 超纲题必须 must_refuse=1")
            if gold:
                fails.append(f"{qid}: 超纲题不应有 gold_doc_ids")
        else:
            if r.get("must_refuse") == "1" and t != "out_of_scope":
                warns.append(f"{qid}: 非超纲题标了 must_refuse=1？")
            if not gold:
                fails.append(f"{qid}: 非超纲题必须有 gold_doc_ids")
            if not (r.get("answer_keypoints") or "").strip():
                fails.append(f"{qid}: 非超纲题必须有 answer_keypoints")
            if not (r.get("kp_keywords") or "").strip():
                fails.append(f"{qid}: 非超纲题必须有 kp_keywords")
            if not (r.get("gold_span_ids") or "").strip():
                warns.append(f"{qid}: 没填 gold_span_ids（引用正确率将无法计算）")
        if t == "multi_hop" and len(ev) < 2:
            fails.append(f"{qid}: 多跳题的 minimal_evidence 必须 ≥2 篇，当前 {len(ev)}")
        if t == "comparison" and len(ev) < 2:
            warns.append(f"{qid}: 对比题建议 minimal_evidence ≥2 篇（当前 {len(ev)}）")
        if r.get("difficulty") not in {"easy", "medium", "hard"}:
            fails.append(f"{qid}: difficulty 非法（{r.get('difficulty')}）")
        if r.get("split") not in {"dev", "test"}:
            fails.append(f"{qid}: split 非法（{r.get('split')}）")
        if not split_multi(r.get("tenant_scope")):
            warns.append(f"{qid}: tenant_scope 为空（权限过滤将无从测试）")

    # 5) 要点与关键词数量一致
    for r in rows:
        kps = split_multi(r.get("answer_keypoints"))
        kws = split_multi(r.get("kp_keywords"))
        if kps and kws and len(kps) != len(kws):
            fails.append(f"{r.get('qid')}: 要点数({len(kps)}) 与 关键词组数({len(kws)}) 不一致")

    # 6) 问题质量
    for r in rows:
        q = (r.get("question") or "").strip()
        if not q:
            continue
        if len(q) < 8:
            warns.append(f"{r.get('qid')}: 问题过短（{len(q)} 字），检索可能过易")
        if q.endswith("是什么？") or q.endswith("是什么?"):
            warns.append(f"{r.get('qid')}: 问题形如「X是什么」，建议改成用户口吻的真实提问")

    # 7) split 比例
    sc = Counter(r.get("split") for r in rows)
    print("split 分布：", dict(sc))

    # 8) 权限陷阱表
    hn_path = Path(args.negatives)
    if hn_path.exists():
        hn = load(hn_path)
        print(f"\n读入 {hn_path.name}：{len(hn)} 条")
        scn = Counter(r.get("scenario", "") for r in hn)
        print("场景分布：", dict(scn))
        for need in ("越权直问", "缓存越权", "撤权失效", "Prompt注入"):
            if scn.get(need, 0) == 0:
                warns.append(f"权限陷阱缺少场景：{need}")
        if len(hn) < 12:
            warns.append(f"权限陷阱只有 {len(hn)} 条，建议 ≥15 条")
        for r in hn:
            for f in ("case_id", "scenario", "requester_tenant", "target_doc_ids", "question", "assertion", "expected_result"):
                if not (r.get(f) or "").strip():
                    fails.append(f"{r.get('case_id') or '?'}: 权限陷阱缺字段 {f}")
    else:
        warns.append(f"{hn_path.name} 不存在（权限陷阱是准入条件，强烈建议补上）")

    print("\n" + "=" * 62)
    print(f"FAIL {len(fails)} 项 / WARN {len(warns)} 项")
    for f in fails[:60]:
        print("  ❌", f)
    if len(fails) > 60:
        print(f"  ... 另有 {len(fails)-60} 项 FAIL")
    for w in warns[:30]:
        print("  ⚠️ ", w)
    if len(warns) > 30:
        print(f"  ... 另有 {len(warns)-30} 项 WARN")
    if not fails:
        print("\n✅ 校验通过，可以跑系统取数了。")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

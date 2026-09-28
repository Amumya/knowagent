#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用确定性规则给检索/生成结果打分（不含 LLM-as-judge，可完全复现）。

系统侧需要输出 JSONL，每题一行：
{"qid":"q007",
 "retrieved_top5":["en/latest/plugins/traffic-split.md","..."],
 "retrieved_top10":["..."],
 "reranked":["..."],
 "context_doc_ids":["en/latest/plugins/traffic-split.md"],
 "answer":"...",
 "citations":[{"doc_id":"en/latest/plugins/traffic-split.md","span":"..."}],
 "refused":false,
 "leak_count":0,
 "latency_ms":840,"tokens_in":3200,"tokens_out":410}

用法:
    python score.py results/baseline_naive.jsonl
"""
import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

BASE = Path(r"D:\DSH-WORK\knowagent\eval")


def split_multi(v):
    return [x.strip() for x in (v or "").split("|") if x.strip()]


def hit_keypoints(answer: str, kp_keywords: str):
    """要点覆盖率。

    规则：kp_keywords 用 '|' 分组，组数应与 answer_keypoints 数一致。
    组内：'+' 连接的词必须全部出现；单个词可用 '/' 给同义词（出现任一即可）。
    返回 (命中组数, 总组数)。
    """
    if not answer or not kp_keywords:
        return 0, 0
    groups = split_multi(kp_keywords)
    low = answer.lower()
    got = 0
    for g in groups:
        ok = True
        for term in g.split("+"):
            alts = [a.strip().lower() for a in term.split("/") if a.strip()]
            if not alts:
                continue
            if not any(a in low for a in alts):
                ok = False
                break
        if ok:
            got += 1
    return got, len(groups)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run", help="系统输出的 JSONL 文件")
    ap.add_argument("--questions", default=str(BASE / "questions.csv"))
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()

    qpath = Path(args.questions)
    if not qpath.exists():
        print(f"❌ 找不到 {qpath}")
        sys.exit(1)
    with qpath.open(encoding="utf-8-sig") as fh:
        qs = {r["qid"]: r for r in csv.DictReader(fh)}

    run_path = Path(args.run)
    runs = [json.loads(l) for l in run_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    per_type = defaultdict(lambda: {"n": 0, "recall5": 0, "recall10": 0, "cov_sum": 0.0, "cov_n": 0})
    recall5 = recall10 = 0
    mrr = []
    cov_all = []
    cite_ok = cite_tot = 0
    refuse_ok = refuse_n = 0
    over_refuse = normal_n = 0
    leaks = 0
    lat, tin, tout = [], [], []
    missing = []

    for r in runs:
        q = qs.get(r.get("qid"))
        if not q:
            missing.append(r.get("qid"))
            continue
        t = q["type"]
        st = per_type[t]
        st["n"] += 1

        gold = set(split_multi(q["gold_doc_ids"]))
        top5 = set(r.get("retrieved_top5") or [])
        top10 = set(r.get("retrieved_top10") or [])

        if q["must_refuse"] == "1":
            refuse_n += 1
            if r.get("refused"):
                refuse_ok += 1
        else:
            normal_n += 1
            if r.get("refused"):
                over_refuse += 1
            if gold and gold <= top5:
                recall5 += 1
                st["recall5"] += 1
            if gold and gold <= top10:
                recall10 += 1
                st["recall10"] += 1
            rank = next((i + 1 for i, d in enumerate(r.get("retrieved_top10") or []) if d in gold), None)
            mrr.append(1.0 / rank if rank else 0.0)
            got, tot = hit_keypoints(r.get("answer", ""), q["kp_keywords"])
            if tot:
                c = got / tot
                cov_all.append(c)
                st["cov_sum"] += c
                st["cov_n"] += 1
            for c_ in (r.get("citations") or []):
                cite_tot += 1
                if c_.get("doc_id") in gold:
                    cite_ok += 1

        leaks += int(r.get("leak_count") or 0)
        if r.get("latency_ms") is not None:
            lat.append(float(r["latency_ms"]))
        if r.get("tokens_in") is not None:
            tin.append(float(r["tokens_in"]))
        if r.get("tokens_out") is not None:
            tout.append(float(r["tokens_out"]))

    def pct(a, b):
        return f"{a / b:.1%}" if b else "n/a"

    def p95(xs):
        if not xs:
            return None
        xs = sorted(xs)
        k = max(0, min(len(xs) - 1, int(round(0.95 * (len(xs) - 1)))))
        return xs[k]

    print(f"评测文件：{run_path.name}")
    print(f"有效题目：{len(runs) - len(missing)} / {len(runs)}" + (f"（未匹配 qid: {missing[:5]}）" if missing else ""))
    print("=" * 62)
    print(f"Recall@5            {pct(recall5, normal_n)}")
    print(f"Recall@10           {pct(recall10, normal_n)}")
    print(f"MRR@10              {statistics.mean(mrr):.3f}" if mrr else "MRR@10              n/a")
    print(f"要点覆盖率(均值)     {statistics.mean(cov_all):.1%}" if cov_all else "要点覆盖率          n/a")
    print(f"引用正确率           {pct(cite_ok, cite_tot)}  ({cite_ok}/{cite_tot})")
    print(f"超纲拒答率           {pct(refuse_ok, refuse_n)}  ({refuse_ok}/{refuse_n})")
    print(f"过度拒答率           {pct(over_refuse, normal_n)}  ({over_refuse}/{normal_n})")
    print(f"越权命中数           {leaks}" + ("   ✅" if leaks == 0 else "   ❌ 必须为 0"))
    if lat:
        print(f"延迟  P50/P95        {statistics.median(lat):.0f} / {p95(lat):.0f} ms")
    if tin:
        print(f"平均 token 输入/输出  {statistics.mean(tin):.0f} / {statistics.mean(tout) if tout else 0:.0f}")

    print("\n分层报告（面试就报这个，不要只报总分）：")
    print(f"  {'类型':<14}{'n':>4}  {'Recall@5':>9}  {'Recall@10':>10}  {'要点覆盖':>9}")
    for t in ("single_hop", "multi_hop", "comparison", "out_of_scope"):
        st = per_type.get(t)
        if not st or st["n"] == 0:
            continue
        cov = (st["cov_sum"] / st["cov_n"]) if st["cov_n"] else 0.0
        print(f"  {t:<14}{st['n']:>4}  {st['recall5']/st['n']:>9.1%}  {st['recall10']/st['n']:>10.1%}  {cov:>9.1%}")

    if args.json_out:
        out = {
            "run": run_path.name,
            "n": len(runs),
            "recall5": recall5 / normal_n if normal_n else None,
            "recall10": recall10 / normal_n if normal_n else None,
            "mrr10": statistics.mean(mrr) if mrr else None,
            "keypoint_coverage": statistics.mean(cov_all) if cov_all else None,
            "citation_precision": cite_ok / cite_tot if cite_tot else None,
            "refuse_accuracy": refuse_ok / refuse_n if refuse_n else None,
            "over_refuse_rate": over_refuse / normal_n if normal_n else None,
            "leaks": leaks,
            "per_type": {k: dict(v) for k, v in per_type.items()},
        }
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n结果已写入 {args.json_out}")


if __name__ == "__main__":
    main()

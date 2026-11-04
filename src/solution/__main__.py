"""Công cụ thực nghiệm nhanh.

    python -m solution bench            # ablation retrieval trên train, không sinh câu trả lời
    python -m solution warm train       # chạy pipeline song song để làm nóng cache cho `neorag run`

`bench` chỉ gọi LLM cho bước viết lại câu hỏi (cache sau lần đầu), nên thử nhiều cấu hình
retrieval gần như miễn phí. Metric dùng đúng hàm của bộ chấm chính thức (neorag.metrics.retrieval).
"""

from __future__ import annotations

import argparse
import copy
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from neorag.data import DATA_DIR, load_corpus, load_queries, read_jsonl
from neorag.metrics.retrieval import score_query
from solution.pipeline import PipelineConfig, SolutionPipeline
from solution.query import QueryPlan

# Mỗi dòng ablation đổi đúng một yếu tố so với dòng "full".
ABLATIONS: dict[str, dict] = {
    "dense_only_no_rewrite": {"rewrite": False, "use_bm25": False},
    "bm25_only_no_rewrite": {"rewrite": False, "use_dense": False},
    "hybrid_no_rewrite": {"rewrite": False},
    "hybrid_rewrite_no_club": {"club_boost": 0.0},
    "dense_only_rewrite": {"use_bm25": False},
    "bm25_only_rewrite": {"use_dense": False},
    "full": {},
    # E2
    "full_no_metadata": {"index_metadata": False},
    "full+diversify": {"diversify_clubs": True},
    "full+rerank": {"use_rerank": True},
    "full+rerank+diversify": {"use_rerank": True, "diversify_clubs": True},
    # E4
    "diversify_off": {"diversify_clubs": False},
    "diversify+intro": {"diversify_prefer_intro": True},
    # E6
    "anchors": {"use_anchors": True},
    "anchors_bm25_only": {
        "use_anchors": True,
        "w_anchor_dense": 0.0,
        "w_anchor_dense_original": 0.0,
        "w_anchor_dense_sub": 0.0,
    },
    "anchors_dense_only": {"use_anchors": True, "w_anchor_bm25": 0.0},
    # Nhánh R (giai đoạn A): mở rộng tập ứng viên cho reranker Haiku
    "e7": {},
    "r1_depth30_max10": {"rerank_depth": 30, "rerank_max": 10},
    "r2_anchor_cand": {"use_anchors": True, "anchors_candidates_only": True},
    "r12": {
        "rerank_depth": 30,
        "rerank_max": 10,
        "use_anchors": True,
        "anchors_candidates_only": True,
    },
    "r12_max8": {
        "rerank_depth": 30,
        "rerank_max": 8,
        "use_anchors": True,
        "anchors_candidates_only": True,
    },
}


def _config(overrides: dict) -> PipelineConfig:
    cfg = copy.deepcopy(PipelineConfig.from_env())
    for key, value in overrides.items():
        target = cfg if hasattr(cfg, key) and key != "retrieval" else cfg.retrieval
        setattr(target, key, value)
    return cfg


def bench(workers: int, only: list[str] | None, stress: bool = False) -> int:
    corpus = load_corpus()
    queries = load_queries(DATA_DIR / "train" / "questions.jsonl")
    types = {
        r["id"]: r.get("type", "?") for r in read_jsonl(DATA_DIR / "train" / "questions.jsonl")
    }
    queries = [q for q in queries if q.relevant_ids]  # câu không có doc đúng không tính retrieval
    if stress:  # biến thể không dấu + viết tắt của chính câu train (solution.stress)
        from dataclasses import replace

        from solution.stress import stress_variant

        queries = [replace(q, query=stress_variant(q.query, i)) for i, q in enumerate(queries)]

    base = SolutionPipeline(_config({}))
    base.index(corpus)
    with ThreadPoolExecutor(workers) as pool:  # viết lại câu hỏi song song một lần, dùng chung
        plans = dict(
            zip(
                [q.id for q in queries],
                pool.map(base.rewriter, [q.query for q in queries]),
                strict=True,
            )
        )

    names = only or list(ABLATIONS)
    print(
        f"{'config':26}{'Pool':>6}{'R@pool':>8}{'R@5':>8}{'MRR@5':>8}{'NDCG@5':>8}{'Retr.':>8}"
        f"   ({len(queries)} câu{', stress' if stress else ''})"
    )
    per_type: dict[str, dict] = {}
    for name in names:
        cfg = _config(ABLATIONS[name])
        pipe = SolutionPipeline(cfg, llm=base.llm)  # embedding có cache: index lại gần như tức thì
        pipe.index(corpus)
        retr = pipe.retriever

        def one(q, cfg=cfg, retr=retr):
            plan = plans[q.id] if cfg.rewrite else QueryPlan(q.query, q.query)
            ids = [d.id for d in retr.retrieve(plan, cfg.n_retrieved)]
            pool = {retr.docs[i].id for i in retr.candidate_pool(plan)}
            rel = set(q.relevant_ids)
            return score_query(ids, rel, [5]) | {
                "pool": len(pool),
                "recall@pool": len(rel & pool) / len(rel),
            }

        with ThreadPoolExecutor(workers) as executor:  # rerank gọi Haiku: chạy song song
            results = list(executor.map(one, queries))
        keys = ("pool", "recall@pool", "recall@5", "mrr@5", "ndcg@5")
        totals, by_type = defaultdict(float), defaultdict(lambda: defaultdict(float))
        for q, m in zip(queries, results, strict=True):
            for key in keys:
                totals[key] += m[key]
                by_type[types[q.id]][key] += m[key]
            by_type[types[q.id]]["n"] += 1
        n = len(queries)
        r, mrr, ndcg = (totals[k] / n * 100 for k in ("recall@5", "mrr@5", "ndcg@5"))
        print(
            f"{name:26}{totals['pool'] / n:6.1f}{totals['recall@pool'] / n * 100:8.2f}"
            f"{r:8.2f}{mrr:8.2f}{ndcg:8.2f}{(r + mrr + ndcg) / 3:8.2f}"
        )
        per_type[name] = by_type
    print("\nTheo loại câu hỏi (mỗi cấu hình: R@pool / R@5 / NDCG@5):")
    first = per_type[names[0]]
    for t in sorted(first, key=lambda t: -first[t]["n"]):
        cells = [
            "{:.2f}/{:.2f}/{:.2f}".format(
                *(
                    per_type[name][t][k] / per_type[name][t]["n"]
                    for k in ("recall@pool", "recall@5", "ndcg@5")
                )
            )
            for name in names
        ]
        print(f"  {t:20}{int(first[t]['n']):4}  " + "  ".join(cells))
    return 0


def warm(split: str, workers: int) -> int:
    pipe = SolutionPipeline()
    pipe.index(load_corpus())
    queries = load_queries(DATA_DIR / split / "questions.jsonl")
    with ThreadPoolExecutor(workers) as pool:
        for i, _ in enumerate(pool.map(pipe.run, [q.query for q in queries]), 1):
            print(f"\r{i}/{len(queries)}", end="", flush=True)
    print(
        f"\nĐã làm nóng cache cho {split}. Chạy tiếp: neorag run {split} "
        "--pipeline solution.pipeline:SolutionPipeline"
    )
    return 0


def build_anchors() -> int:
    import os

    from neorag.llm import LLMClient
    from solution import anchors

    res = anchors.generate(
        load_corpus(),
        LLMClient(cache_path=".cache/solution.sqlite"),
        os.getenv("LLM_MODEL", "claude-haiku-5-5"),
    )
    anchors.save(res)
    print(f"Đã ghi {len(res)} đoạn vào {anchors.ANCHORS_PATH}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m solution")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bench", help="ablation retrieval trên train")
    b.add_argument("--only", nargs="*", choices=list(ABLATIONS))
    b.add_argument("--workers", type=int, default=6)
    b.add_argument(
        "--stress", action="store_true", help="câu train bỏ dấu + viết tắt (proxy Private)"
    )
    sub.add_parser(
        "anchors", help="sinh câu hỏi giả định cho từng đoạn (data/solution/doc_anchors.jsonl)"
    )
    w = sub.add_parser("warm", help="chạy pipeline song song để làm nóng cache")
    w.add_argument("split")
    w.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if args.cmd == "bench":
        return bench(args.workers, args.only, args.stress)
    if args.cmd == "anchors":
        return build_anchors()
    return warm(args.split, args.workers)


if __name__ == "__main__":
    sys.exit(main())

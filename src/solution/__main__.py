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
}


def _config(overrides: dict) -> PipelineConfig:
    cfg = copy.deepcopy(PipelineConfig.from_env())
    for key, value in overrides.items():
        target = cfg if hasattr(cfg, key) and key != "retrieval" else cfg.retrieval
        setattr(target, key, value)
    return cfg


def bench(workers: int, only: list[str] | None) -> int:
    corpus = load_corpus()
    queries = load_queries(DATA_DIR / "train" / "questions.jsonl")
    types = {
        r["id"]: r.get("type", "?") for r in read_jsonl(DATA_DIR / "train" / "questions.jsonl")
    }
    queries = [q for q in queries if q.relevant_ids]  # câu không có doc đúng không tính retrieval

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
    reranker = None
    print(f"{'config':26}{'R@5':>8}{'MRR@5':>8}{'NDCG@5':>8}{'Retr.':>8}   ({len(queries)} câu)")
    for name in names:
        cfg = _config(ABLATIONS[name])
        cfg.retrieval.use_rerank, use_rerank = False, cfg.retrieval.use_rerank
        pipe = SolutionPipeline(cfg, llm=base.llm)  # embedding có cache: index lại gần như tức thì
        pipe.index(corpus)
        if use_rerank:
            if reranker is None:
                from solution.rerank import CrossEncoderReranker

                reranker = CrossEncoderReranker()
            cfg.retrieval.use_rerank, pipe.retriever.reranker = True, reranker
        totals, by_type = defaultdict(float), defaultdict(lambda: defaultdict(float))
        for q in queries:
            plan = plans[q.id] if cfg.rewrite else QueryPlan(q.query, q.query)
            ids = [d.id for d in pipe.retriever.retrieve(plan, cfg.n_retrieved)]
            m = score_query(ids, set(q.relevant_ids), [5])
            for key in ("recall@5", "mrr@5", "ndcg@5"):
                totals[key] += m[key]
                by_type[types[q.id]][key] += m[key]
            by_type[types[q.id]]["n"] += 1
        n = len(queries)
        r, mrr, ndcg = (totals[k] / n * 100 for k in ("recall@5", "mrr@5", "ndcg@5"))
        print(f"{name:26}{r:8.2f}{mrr:8.2f}{ndcg:8.2f}{(r + mrr + ndcg) / 3:8.2f}")
        if name == names[-1]:
            print(f"\nTheo loại câu hỏi ({name}):")
            for t, v in sorted(by_type.items(), key=lambda kv: -kv[1]["n"]):
                print(
                    f"  {t:22}{int(v['n']):4}  R@5 {v['recall@5'] / v['n']:.2f}  MRR@5 {v['mrr@5'] / v['n']:.2f}"
                )
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


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m solution")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bench", help="ablation retrieval trên train")
    b.add_argument("--only", nargs="*", choices=list(ABLATIONS))
    b.add_argument("--workers", type=int, default=6)
    w = sub.add_parser("warm", help="chạy pipeline song song để làm nóng cache")
    w.add_argument("split")
    w.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if args.cmd == "bench":
        return bench(args.workers, args.only)
    return warm(args.split, args.workers)


if __name__ == "__main__":
    sys.exit(main())

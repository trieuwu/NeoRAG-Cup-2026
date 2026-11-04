"""scripts/sanity_check.py: cảnh báo đỏ khi lần chạy có fallback hoặc lệch xa tham chiếu."""

from __future__ import annotations

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "sanity_check", Path(__file__).parents[1] / "scripts" / "sanity_check.py"
)
sanity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sanity)

REF = {"abstain_rate": 0.1, "mean_answer_chars": 200.0, "mean_ids": 10}
QUESTIONS = [{"id": f"q{i}", "query": f"câu {i}"} for i in range(10)]


def _run(answers=None, fallback_at=None, n=10):
    preds = [
        {
            "id": f"q{i}",
            "retrieved_ids": list(range(1, 11)),
            "answer": (answers or {}).get(i, f"Đáp án số {i} " * 14),
        }
        for i in range(n)
    ]
    log = [
        {
            "query": f"câu {i}",
            "fallback_used": i == fallback_at,
            "abstained": i == 0,
            "latency_ms": 5000.0,
            "incidents": [{"stage": "rerank", "error": "x"}] if i == fallback_at else [],
        }
        for i in range(n)
    ]
    stats = sanity.summarize(preds, log)
    return {lvl for lvl, _ in sanity.check(stats, REF, preds, log, QUESTIONS)}, sanity.check(
        stats, REF, preds, log, QUESTIONS
    )


def test_clean_run_is_green():
    levels, _ = _run()
    assert levels == {"green"}


def test_fallback_is_red_and_names_question():
    levels, results = _run(fallback_at=3)
    assert "red" in levels
    assert any("q3" in msg for lvl, msg in results if lvl == "red")


def test_missing_questions_and_repeated_answers_are_red():
    assert "red" in _run(n=8)[0]
    assert "red" in _run(answers={i: "Giống nhau." for i in range(5)})[0]

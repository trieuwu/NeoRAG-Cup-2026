"""Kiểm tra nhanh một lần chạy trước khi nộp: so log và predictions với lần chạy tham chiếu (E7 Public).

    python scripts/sanity_check.py --pred outputs/private_0730_pred.jsonl \
        --log outputs/private_0730_log.jsonl --questions data/private_test/questions.jsonl

Cảnh báo ĐỎ (mã thoát 1) khi: thiếu/thừa câu, có câu dùng fallback, có answer trùng nhau bất thường,
tỷ lệ từ chối hoặc độ dài câu trả lời lệch xa tham chiếu, ít id hơn bình thường, latency quá cao.
Tạo lại file tham chiếu từ một lần chạy tốt: thêm --write-reference configs/sanity_reference.json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter
from pathlib import Path

DEFAULT_REFERENCE = Path("configs/sanity_reference.json")

if os.name == "nt":
    os.system("")  # bật mã màu ANSI trên Windows console
RED, YELLOW, GREEN, RESET = "\033[91m", "\033[93m", "\033[92m", "\033[0m"


def _read_jsonl(path: str | Path) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8-sig")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def summarize(preds: list[dict], log: list[dict]) -> dict:
    latencies = sorted(r["latency_ms"] for r in log) or [0.0]
    n = max(len(log), 1)
    return {
        "n": len(preds),
        "fallback": sum(bool(r.get("fallback_used")) for r in log),
        "abstain_rate": round(sum(bool(r.get("abstained")) for r in log) / n, 4),
        "mean_answer_chars": round(statistics.mean(len(p["answer"]) for p in preds), 1),
        "mean_ids": round(statistics.mean(len(p["retrieved_ids"]) for p in preds), 2),
        "latency_median_ms": round(statistics.median(latencies), 1),
        "latency_p95_ms": latencies[min(len(latencies) - 1, int(0.95 * len(latencies)))],
    }


def check(stats: dict, ref: dict, preds: list[dict], log: list[dict], questions: list[dict]):
    """Trả về danh sách (mức, thông điệp); mức là 'red', 'yellow' hoặc 'green'."""
    out: list[tuple[str, str]] = []
    by_query = {q["query"]: q["id"] for q in questions}

    expected = {q["id"] for q in questions}
    got = [p["id"] for p in preds]
    if set(got) != expected or len(got) != len(set(got)):
        missing, extra = expected - set(got), set(got) - expected
        out.append(
            (
                "red",
                f"Số câu sai: {len(got)}/{len(expected)}, thiếu {sorted(missing)[:5]}, thừa {sorted(extra)[:5]}",
            )
        )
    else:
        out.append(("green", f"Đủ {len(expected)} câu, không trùng id"))

    if len(log) != len(preds):
        out.append(
            (
                "yellow",
                f"Log có {len(log)} dòng, predictions có {len(preds)} (log ghi thêm nếu chạy lại cùng file)",
            )
        )

    bad = [r for r in log if r.get("fallback_used")]
    if bad:
        stages = Counter(i["stage"] for r in bad for i in r.get("incidents", []))
        ids = [by_query.get(r["query"], "?") for r in bad]
        out.append(
            (
                "red",
                f"{len(bad)} câu dùng fallback {dict(stages)}: {ids[:10]} → chạy lại (cache giữ câu đã ổn)",
            )
        )
    else:
        out.append(("green", "Không câu nào dùng fallback"))

    dup = [a for a, c in Counter(p["answer"] for p in preds).items() if c >= 3]
    if dup:
        out.append(("red", f"{len(dup)} câu trả lời lặp lại ≥ 3 lần: {dup[0][:80]!r}"))

    diff = stats["abstain_rate"] - ref["abstain_rate"]
    level = "red" if abs(diff) > 0.15 else "yellow" if abs(diff) > 0.08 else "green"
    out.append(
        (level, f"Tỷ lệ từ chối {stats['abstain_rate']:.0%} (tham chiếu {ref['abstain_rate']:.0%})")
    )

    ratio = stats["mean_answer_chars"] / ref["mean_answer_chars"]
    level = "red" if not 0.6 <= ratio <= 1.6 else "yellow" if not 0.8 <= ratio <= 1.25 else "green"
    out.append(
        (
            level,
            f"Độ dài TB {stats['mean_answer_chars']:.0f} ký tự (tham chiếu {ref['mean_answer_chars']:.0f})",
        )
    )

    level = "red" if stats["mean_ids"] < ref["mean_ids"] - 1 else "green"
    out.append((level, f"Số id TB {stats['mean_ids']} (tham chiếu {ref['mean_ids']})"))

    med, p95 = stats["latency_median_ms"], stats["latency_p95_ms"]
    if med < 50:
        out.append(
            (
                "yellow",
                f"Latency median {med:.0f} ms: kết quả lấy từ cache, không phản ánh latency thật",
            )
        )
    else:
        level = "red" if p95 > 120_000 else "yellow" if med > 30_000 else "green"
        out.append((level, f"Latency median {med / 1000:.1f}s, p95 {p95 / 1000:.1f}s"))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pred", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--questions", required=True)
    ap.add_argument("--reference", default=str(DEFAULT_REFERENCE))
    ap.add_argument("--write-reference", help="ghi thống kê của lần chạy này làm tham chiếu")
    args = ap.parse_args(argv)

    preds, log, questions = (
        _read_jsonl(args.pred),
        _read_jsonl(args.log),
        _read_jsonl(args.questions),
    )
    stats = summarize(preds, log)
    if args.write_reference:
        Path(args.write_reference).write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
        print(f"Đã ghi tham chiếu: {args.write_reference}")
        return 0

    ref = json.loads(Path(args.reference).read_text(encoding="utf-8"))
    results = check(stats, ref, preds, log, questions)
    colors = {"red": RED + "ĐỎ  ", "yellow": YELLOW + "VÀNG", "green": GREEN + "XANH"}
    for level, msg in results:
        print(f"{colors[level]}{RESET}  {msg}")
    red = sum(level == "red" for level, _ in results)
    print(
        f"\n{RED + 'CÓ CẢNH BÁO ĐỎ: chưa nộp, xem docs/private-day.md' if red else GREEN + 'SANITY CHECK XANH'}{RESET}"
    )
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())

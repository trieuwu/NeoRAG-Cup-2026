"""So hai file predictions (.jsonl hoặc .zip nộp bài): câu nào khác retrieved_ids hoặc answer.

Dùng làm kiểm tra hồi quy: bản mới phải khớp hoàn toàn bản đã nộp nếu cấu hình không đổi.

    python scripts/compare_predictions.py outputs/public_test_submission_e7_88.95.zip outputs/x_pred.jsonl
Thoát với mã 0 nếu khớp hoàn toàn, 1 nếu có câu khác.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from pathlib import Path


def load(path: str | Path) -> dict[str, dict]:
    path = Path(path)
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.endswith(".jsonl"))
            text = io.TextIOWrapper(z.open(name), encoding="utf-8-sig").read()
    else:
        text = path.read_text(encoding="utf-8-sig")
    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    return {r["id"]: r for r in rows}


def compare(a: dict[str, dict], b: dict[str, dict]) -> dict[str, list[str]]:
    only_a, only_b = sorted(a.keys() - b.keys()), sorted(b.keys() - a.keys())
    common = sorted(a.keys() & b.keys())
    return {
        "only_a": only_a,
        "only_b": only_b,
        "ids": [k for k in common if a[k]["retrieved_ids"] != b[k]["retrieved_ids"]],
        "answer": [k for k in common if a[k]["answer"] != b[k]["answer"]],
        "common": common,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("reference")
    ap.add_argument("candidate")
    args = ap.parse_args(argv)
    diff = compare(load(args.reference), load(args.candidate))
    n = len(diff["common"])
    same = n - len(set(diff["ids"]) | set(diff["answer"]))
    print(f"Khớp hoàn toàn: {same}/{n} câu")
    for key, label in [
        ("ids", "khác retrieved_ids"),
        ("answer", "khác answer"),
        ("only_a", "chỉ có trong file tham chiếu"),
        ("only_b", "chỉ có trong file mới"),
    ]:
        if diff[key]:
            print(f"  {label} ({len(diff[key])}): {', '.join(diff[key][:10])}")
    ok = same == n and not diff["only_a"] and not diff["only_b"]
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

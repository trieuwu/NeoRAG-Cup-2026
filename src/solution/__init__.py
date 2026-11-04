"""Pipeline RAG của thí sinh cho NeoRAG Cup 2026.

Kiến trúc (xem docs/strategy.md):
    câu hỏi ─► QueryRewriter (Haiku: thêm dấu, mở rộng viết tắt, nhận diện CLB, tách ý)
            ─► HybridRetriever (BM25 trên văn bản bỏ dấu + dense bge-m3, gộp RRF, ưu tiên đúng CLB)
            ─► Generator (Haiku: trả lời ngắn, bám tài liệu, từ chối đúng cách)
"""

from solution.pipeline import SolutionPipeline

__all__ = ["SolutionPipeline"]

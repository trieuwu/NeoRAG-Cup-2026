"""Test pipeline của thí sinh (src/solution). Chạy offline bằng LLM và embedding giả."""

from __future__ import annotations

import json
import re

import pytest

from conftest import FakeEmbedder, FakeLLM
from solution.bm25 import BM25
from solution.pipeline import PipelineConfig, SolutionPipeline
from solution.query import QueryPlan, parse_plan
from solution.retrieval import rrf
from solution.textproc import expand_abbreviations, fold, tokens


def test_fold_removes_vietnamese_accents():
    assert fold("CLB Lập Trình PTIT, Đa phương tiện!") == "clb lap trinh ptit da phuong tien"


def test_expand_abbreviations_keeps_original_words():
    assert expand_abbreviations("clb mm o hv") == "clb mm o hv multimedia hoc vien"


def test_tokens_keep_meaningful_words_that_collide_with_stopwords():
    toks = tokens("Ban sự kiện")
    assert "ban" in toks and "ban_su" in toks


def test_bm25_matches_unaccented_query_to_accented_doc():
    docs = [tokens("CLB Lập Trình PTIT thành lập 2011"), tokens("CLB Multimedia chụp ảnh")]
    scores = BM25(docs).scores(tokens("clb lap trinh thanh lap nam nao"))
    assert scores[0] > scores[1]


def test_rrf_rewards_agreement_between_rankings():
    scores = rrf([([1, 2, 3], 1.0), ([2, 1, 3], 1.0)], k=60)
    assert scores[1] == scores[2] > scores[3]


def test_parse_plan_reads_json_and_filters_unknown_clubs():
    reply = 'Kết quả: {"query": "CLB Multimedia PTIT có phòng riêng không?", "clubs": ["multimedia", "xyz"], "sub_queries": []}'
    plan = parse_plan("clb mm co phong rieng ko", reply)
    assert plan.rewritten == "CLB Multimedia PTIT có phòng riêng không?"
    assert plan.clubs == ["multimedia"]


def test_parse_plan_falls_back_to_original_on_bad_json():
    plan = parse_plan("cau hoi goc", "xin lỗi, tôi không hiểu {")
    assert plan == QueryPlan("cau hoi goc", "cau hoi goc")


def _pipeline(corpus, responder) -> tuple[SolutionPipeline, FakeLLM]:
    llm = FakeLLM(responder)
    pipe = SolutionPipeline(
        PipelineConfig(dynamic_few_shot=False), llm=llm
    )  # few-shot động có test riêng
    pipe.retriever.embedder = FakeEmbedder()
    pipe.index(corpus)
    return pipe, llm


def test_pipeline_uses_rewrite_and_club_boost(corpus):
    def responder(messages):
        if "chuẩn hóa câu hỏi" in messages[0]["content"]:
            return json.dumps(
                {"query": "CLB Multimedia PTIT thành lập khi nào?", "clubs": ["multimedia"]}
            )
        return "CLB Multimedia PTIT thành lập ngày 10/11/2012."

    pipe, llm = _pipeline(corpus, responder)
    out = pipe.run("clb mm thanh lap khi nao")
    assert out.retrieved_ids[0] == 2
    assert sorted(out.retrieved_ids) == [1, 2, 3]
    assert out.answer.endswith("10/11/2012.")
    assert len(llm.calls) == 3  # viết lại câu hỏi + rerank + sinh câu trả lời


def test_pipeline_never_sends_temperature(corpus, monkeypatch):
    sent = []
    pipe, llm = _pipeline(corpus, lambda m: "{}")
    original = llm.chat
    monkeypatch.setattr(
        llm, "chat", lambda messages, model, **kw: sent.append(kw) or original(messages, model)
    )
    pipe.run("proptit thanh lap khi nao")
    assert sent and all("temperature" not in kw for kw in sent)


def test_config_reads_env_overrides(monkeypatch):
    monkeypatch.setenv("RAG_REWRITE", "0")
    monkeypatch.setenv("RAG_CLUB_BOOST", "2.5")
    monkeypatch.setenv("RAG_CONTEXT_K", "3")
    cfg = PipelineConfig.from_env()
    assert cfg.rewrite is False and cfg.context_k == 3 and cfg.retrieval.club_boost == 2.5


class FakeReranker:
    """Cross-encoder giả: đoạn nào chứa từ khóa thì điểm cao."""

    def __init__(self, keyword: str):
        self.keyword = keyword

    def score(self, queries, docs):
        return {d.id: float(self.keyword in d.text) for d in docs}


def test_rerank_promotes_doc_preferred_by_cross_encoder(corpus):
    from solution.retrieval import HybridRetriever, RetrievalConfig

    cfg = RetrievalConfig(use_rerank=True, w_rerank=5.0, club_boost=0.0)
    retriever = HybridRetriever(FakeEmbedder(), cfg, FakeReranker("2023"))
    retriever.index(corpus)
    docs = retriever.retrieve(QueryPlan("clb thanh lap", "CLB thành lập ngày nào"), n=3)
    assert docs[0].id == 3  # đoạn GCC "ra đời năm 2023" được cross-encoder đẩy lên đầu


def test_diversify_puts_every_asked_club_in_top_k(corpus):
    from solution.retrieval import HybridRetriever, RetrievalConfig

    retriever = HybridRetriever(FakeEmbedder(), RetrievalConfig(diversify_clubs=True))
    retriever.index(corpus)
    plan = QueryPlan("so sanh", "So sánh", clubs=["proptit", "gcc"])
    ranked = retriever._diversify(plan, [0, 1, 2], k=2)  # top-2 ban đầu: ProPTIT, Multimedia
    assert {corpus[i].club for i in ranked[:2]} >= {"CLB Lập Trình PTIT", corpus[2].club}


def test_few_shot_prompt_keeps_real_question_last(corpus):
    from solution.prompts import FEW_SHOT, answer_messages

    msgs = answer_messages("câu hỏi thật", "câu hỏi thật", corpus, "v3")
    assert len(msgs) == 2 + 2 * len(FEW_SHOT)
    assert msgs[-1]["role"] == "user" and "câu hỏi thật" in msgs[-1]["content"]
    assert "TÀI LIỆU" in msgs[-1]["content"]


def test_rewrite_prompt_v2_asks_one_sub_query_per_club():
    from solution.query import REWRITE_PROMPTS

    assert "TỪNG CLB" in REWRITE_PROMPTS["v2"] and "TỪNG CLB" not in REWRITE_PROMPTS["v1"]
    llm = FakeLLM(lambda m: "{}")
    from solution.query import QueryRewriter

    QueryRewriter(llm, "m", "v2")("so sanh proptit va gcc")
    assert llm.calls[0][0]["content"] == REWRITE_PROMPTS["v2"]


def test_diversify_prefer_intro_picks_intro_doc():
    from neorag.data import Document
    from solution.retrieval import HybridRetriever, RetrievalConfig

    docs = [
        Document(1, "Cộng đồng S2B", "Giới thiệu chung", "S2B gồm 3 CLB."),
        Document(2, "CLB Lập Trình PTIT", "Lịch sử", "Lịch sử ProPTIT."),
        Document(3, "CLB Lập Trình PTIT", "Giới thiệu chung", "ProPTIT thành lập 2011."),
        Document(4, "CLB Multimedia PTIT", "Giới thiệu chung", "MPC thành lập 2012."),
    ]
    retriever = HybridRetriever(FakeEmbedder(), RetrievalConfig(diversify_prefer_intro=True))
    retriever.index(docs)
    plan = QueryPlan("so sanh", "So sánh", clubs=["proptit", "multimedia"])
    top = retriever._diversify(plan, [0, 1, 2, 3], k=2)[:2]
    assert {docs[i].id for i in top} == {3, 4}


def test_v4_prompt_uses_v4_system_and_few_shot(corpus):
    from solution.prompts import ANSWER_SYSTEM_V4, FEW_SHOT, answer_messages

    msgs = answer_messages("q", "q", corpus, "v4")
    assert msgs[0]["content"] == ANSWER_SYSTEM_V4 and len(msgs) == 2 + 2 * len(FEW_SHOT)


def test_expand_abbreviations_handles_ptit_terms_and_phrases():
    from solution.textproc import expand_abbreviations

    out = expand_abbreviations(fold("clb pro sinh hoạt ở cs hđ, có cộng đrl ko"))
    assert "co so ha dong" in out and "diem ren luyen" in out and "proptit" in out


def test_ambiguous_unaccented_words_are_not_expanded():
    from solution.textproc import ABBREVIATIONS

    for word in ["ve", "nhan", "thi", "tc", "tin", "c", "btc", "dn"]:
        assert word not in ABBREVIATIONS


def test_rewrite_v3_has_disambiguation_and_advice_rules():
    from solution.query import REWRITE_PROMPTS

    v3 = REWRITE_PROMPTS["v3"]
    assert "đứng lớp" in v3 and "nhắn" in v3 and "xin tư vấn" in v3 and "ICPC" in v3


def test_v5_prompt_extends_v4(corpus):
    from solution.prompts import ANSWER_SYSTEM_V4, ANSWER_SYSTEM_V5, answer_messages

    assert ANSWER_SYSTEM_V5.startswith(ANSWER_SYSTEM_V4.split("8.")[0])
    assert "KHÔNG hỏi" in ANSWER_SYSTEM_V5
    assert answer_messages("q", "q", corpus, "v5")[0]["content"] == ANSWER_SYSTEM_V5


def test_anchor_doc_score_is_max_over_doc_questions():
    import numpy as np

    from solution.retrieval import HybridRetriever

    r = HybridRetriever(FakeEmbedder())
    r.docs = [object(), object()]
    r.anchor_vectors = np.array([[1.0, 0.0], [0.0, 1.0], [0.6, 0.8]], dtype=np.float32)
    r.anchor_owner = np.array([0, 0, 1])
    scores = r._anchor_doc_scores(np.array([0.0, 1.0], dtype=np.float32))
    assert scores.tolist() == pytest.approx([1.0, 0.8])


def test_dynamic_few_shot_leave_one_out(tmp_path):
    from solution.fewshot import FewShotSelector

    path = tmp_path / "q.jsonl"
    rows = [
        {
            "id": "t1",
            "query": "CLB Lập Trình PTIT thành lập khi nào?",
            "answer": "Ngày 09/10/2011.",
        },
        {"id": "t2", "query": "ProPTIT ra đời năm nào?", "answer": "Năm 2011."},
        {"id": "t3", "query": "GCC có mấy nhánh đào tạo?", "answer": "Hai nhánh."},
    ]
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    sel = FewShotSelector(FakeEmbedder(), k=2, path=path)
    picked = sel.select(QueryPlan(rows[0]["query"], rows[0]["query"]))
    assert "t1" not in {e.id for e in picked} and len(picked) == 2


def test_v6_prompt_uses_dynamic_examples(corpus):
    from solution.prompts import ANSWER_SYSTEM_V6, DYNAMIC_INTRO, answer_messages

    msgs = answer_messages("q", "q", corpus, "v6", examples=[("vd hỏi", "vd đáp")])
    assert msgs[0]["content"] == ANSWER_SYSTEM_V6
    assert msgs[1]["content"].startswith(DYNAMIC_INTRO) and msgs[2]["content"] == "vd đáp"
    assert len(msgs) == 4 and "KHÍA CẠNH" in ANSWER_SYSTEM_V6


def test_llm_reranker_parses_ranking_and_ignores_unknown_ids(corpus):
    from solution.rerank import LLMReranker

    llm = FakeLLM(lambda m: 'Kết quả: {"ranking": [3, 99, 1, 3]}')
    scores = LLMReranker(llm, "m").score(["GCC ra đời năm nào?"], corpus)
    assert scores[3] > scores[1] and 2 not in scores and 99 not in scores
    assert "temperature" not in str(llm.calls)


def test_llm_reranker_bad_json_keeps_rrf_order(corpus):
    from solution.rerank import LLMReranker
    from solution.retrieval import HybridRetriever, RetrievalConfig

    assert LLMReranker(FakeLLM(lambda m: "không hiểu"), "m").score(["q"], corpus) == {}
    plan = QueryPlan("gcc ra doi nam nao", "GCC ra đời năm nào")
    base = HybridRetriever(FakeEmbedder(), RetrievalConfig(use_rerank=False))
    base.index(corpus)
    broken = HybridRetriever(
        FakeEmbedder(), RetrievalConfig(use_rerank=True), LLMReranker(FakeLLM(lambda m: "?"), "m")
    )
    broken.index(corpus)
    assert [d.id for d in broken.retrieve(plan)] == [d.id for d in base.retrieve(plan)]


def test_llm_reranker_prompt_unchanged_for_default_max(corpus):
    """max_ids = 8 phải sinh đúng prompt của E7 (giữ cache), giá trị khác đổi con số trong prompt."""
    from solution.rerank import LLMReranker

    assert "(tối đa 8 id)" in LLMReranker(FakeLLM(lambda m: ""), "m").system
    assert "(tối đa 10 id)" in LLMReranker(FakeLLM(lambda m: ""), "m", max_ids=10).system


def test_anchor_candidates_extend_pool_without_changing_rrf_order(corpus):
    """Anchors chỉ thêm ứng viên vào cuối tập rerank; thứ hạng RRF không đổi."""
    from solution.bm25 import BM25
    from solution.retrieval import HybridRetriever, RetrievalConfig

    plan = QueryPlan("gcc ra doi nam nao", "GCC ra đời năm nào")
    base = HybridRetriever(FakeEmbedder(), RetrievalConfig(rerank_depth=1))
    base.index(corpus)
    cfg = RetrievalConfig(
        rerank_depth=1, use_anchors=True, anchors_candidates_only=True, anchor_candidates=2
    )
    r = HybridRetriever(FakeEmbedder(), cfg)
    r.docs, r.bm25, r.doc_vectors = base.docs, base.bm25, base.doc_vectors
    # anchors giả: chỉ đoạn cuối khớp câu hỏi
    r.anchor_bm25 = BM25([[] for _ in corpus[:-1]] + [tokens("gcc ra doi nam nao")])
    assert r.fused_ranking(plan) == base.fused_ranking(plan)
    pool = r.candidate_pool(plan)
    assert pool[0] == base.fused_ranking(plan)[0] and len(corpus) - 1 in pool


def test_stress_variant_removes_accents_and_abbreviates():
    from solution.stress import stress_variant

    q = "Sinh viên Học viện ngành đa phương tiện vào CLB Multimedia PTIT được không?"
    assert stress_variant(q, 0) == "sv hv nganh dpt vao mm dc ko"
    assert stress_variant(q, 1) == "sv hv nganh dpt vao mpc dc k"


def test_harddev_groups_are_deterministic_and_filter_needs_exact_passages():
    from neorag.data import Document
    from solution import harddev

    docs = [
        Document(i + 1, club, topic, f"{club} {topic} năm {2010 + i}, hoạt động số {i}.")
        for i, (club, topic) in enumerate(
            (c, t)
            for c in ("CLB A", "CLB B", "CLB C")
            for t in ("Giới thiệu", "Đào tạo", "Sự kiện")
        )
    ]
    vectors = FakeEmbedder().embed([d.text for d in docs])
    groups = harddev.sample_groups(docs, vectors, 9, seed=1)
    assert groups == harddev.sample_groups(docs, vectors, 9, seed=1)
    assert {g.kind for g in groups} == set(harddev.KINDS)

    def responder(messages):
        if "tạo câu hỏi kiểm thử" in messages[0]["content"]:
            return '{"ok": true, "question": "q?"}'
        ids = [int(x) for x in re.findall(r"^\[(\d+)\]", messages[1]["content"], re.M)]
        return json.dumps({"ids": ids[:1], "ambiguous": True})  # chỉ chọn một đoạn

    kept, stats = harddev.build(docs, vectors, FakeLLM(responder), "m", n=9, workers=1)
    assert all(len(r["relevant_ids"]) == 1 for r in kept)  # nhóm nhiều đoạn bị loại
    assert sum(stats.values()) + len(kept) == 9 and stats["thiếu đoạn"] > 0

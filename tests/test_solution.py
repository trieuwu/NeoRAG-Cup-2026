"""Test pipeline của thí sinh (src/solution). Chạy offline bằng LLM và embedding giả."""

from __future__ import annotations

import json

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
    pipe = SolutionPipeline(PipelineConfig(), llm=llm)
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
    assert len(llm.calls) == 2  # 1 lời gọi viết lại câu hỏi + 1 lời gọi sinh câu trả lời


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

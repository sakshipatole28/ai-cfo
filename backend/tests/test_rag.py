import pytest
from fastapi.testclient import TestClient

from aicfo.config import REPO_ROOT
from aicfo.evals.rag_eval import evaluate, load_golden
from aicfo.llm import FakeLLM, LLMError
from aicfo.main import create_app
from aicfo.rag.answer import Answerer, verify
from aicfo.rag.corpus import CorpusError, chunk_document, load_corpus, parse_document
from aicfo.rag.embeddings import HashingEmbedder
from aicfo.rag.guard import check_answer, check_question
from aicfo.rag.retriever import HybridRetriever
from aicfo.rag.text import numbers, tokenize

KB = REPO_ROOT / "data" / "kb"
OFF_TOPIC = [
    "What is the capital of France?",
    "Who won the cricket world cup in 2011?",
    "How do I reset my router password?",
    "Explain photosynthesis in plants",
]


@pytest.fixture(scope="module")
def retriever() -> HybridRetriever:
    _, chunks = load_corpus(KB)
    return HybridRetriever(chunks, HashingEmbedder())


# Corpus
def test_corpus_loads_with_unique_chunks() -> None:
    docs, chunks = load_corpus(KB)
    assert len(docs) >= 9
    assert len({c.id for c in chunks}) == len(chunks)
    assert all(c.text and c.section for c in chunks)
    assert max(len(c.text) for c in chunks) < 1000


def test_every_document_states_it_is_a_summary_or_fictional() -> None:
    docs, _ = load_corpus(KB)
    assert all(("summary" in d.kind.lower()) or ("fictional" in d.kind.lower()) for d in docs)


def test_parse_rejects_missing_front_matter() -> None:
    with pytest.raises(CorpusError):
        parse_document("## No front matter\ntext")
    with pytest.raises(CorpusError):
        parse_document("---\nid: x\n---\nbody")


def test_long_sections_are_split_with_overlap() -> None:
    raw = (
        "---\nid: t\nissuer: x\ntitle: T\nsource_url: u\nversion: v\neffective: e\nkind: summary\n---\n## S\n"
        + " ".join(f"Sentence number {i} explains a rule in detail." for i in range(40))
    )
    chunks = chunk_document(parse_document(raw), max_chars=300)
    assert len(chunks) > 3
    last_of_first = chunks[0].text.split(". ")[-1]
    assert last_of_first.rstrip(".") in chunks[1].text


# Text utilities
def test_tokenize_stems_and_drops_stopwords() -> None:
    assert tokenize("The distribution of funds") == tokenize("distribute fund")


def test_numbers_are_normalised() -> None:
    assert numbers("₹1,50,000 and 12.5% and ₹1.25 lakh") == {"150000", "12.5", "1.25"}


# Retrieval quality gate (CI fails if retrieval regresses)
@pytest.mark.parametrize("mode", ["bm25", "hybrid"])
def test_golden_retrieval_quality(retriever: HybridRetriever, mode: str) -> None:
    report = evaluate(retriever, mode)  # type: ignore[arg-type]
    assert report.questions >= 28
    assert report.hit_at_3 >= 0.9
    assert report.mrr >= 0.85


def test_hybrid_reports_both_rankings(retriever: HybridRetriever) -> None:
    hit = retriever.search("LTCG exemption 1.25 lakh", k=1)[0]
    assert hit.chunk.doc.id == "it-capital-gains"
    assert hit.bm25_rank is not None and hit.dense_rank is not None


# Answers
def test_all_golden_questions_get_cited_answers(retriever: HybridRetriever) -> None:
    answerer = Answerer(retriever)
    for row in load_golden():
        a = answerer.ask(str(row["q"]))
        assert a.mode == "extractive", row["q"]
        assert a.citations and not verify(a.text, a.hits, a.question)


@pytest.mark.parametrize("question", OFF_TOPIC)
def test_off_topic_questions_are_declined(retriever: HybridRetriever, question: str) -> None:
    assert Answerer(retriever).ask(question).mode == "not_found"


def test_buy_sell_questions_are_refused_with_citation(retriever: HybridRetriever) -> None:
    a = Answerer(retriever).ask("Should Rohan buy more Reliance shares?")
    assert a.mode == "refused"
    assert a.citations[0].doc_id == "sebi-ia-regulations"


def test_llm_answer_with_valid_citations_is_used(retriever: HybridRetriever) -> None:
    llm = FakeLLM("Long-term gains above ₹1.25 lakh in a year are taxed at 12.5% [1].")
    a = Answerer(retriever, llm).ask("How are long-term gains on equity funds taxed?")
    assert a.mode == "llm"
    assert [c.n for c in a.citations] == [1]


def test_llm_answer_with_invented_number_falls_back(retriever: HybridRetriever) -> None:
    llm = FakeLLM("Long-term gains are taxed at 15% above ₹2 lakh [1].")
    a = Answerer(retriever, llm).ask("How are long-term gains on equity funds taxed?")
    assert a.mode == "extractive"
    assert any("numbers not in sources" in i for i in a.issues)


def test_llm_answer_with_bad_citation_falls_back(retriever: HybridRetriever) -> None:
    a = Answerer(retriever, FakeLLM("Gains are taxed at 12.5% [9].")).ask(
        "How are long-term gains on equity funds taxed?"
    )
    assert a.mode == "extractive"
    assert any("out of range" in i for i in a.issues)


def test_llm_failure_falls_back(retriever: HybridRetriever) -> None:
    def boom(_s: str, _u: str) -> str:
        raise LLMError("down")

    a = Answerer(retriever, FakeLLM(boom)).ask("How many levels does the riskometer have?")
    assert a.mode == "extractive"
    assert "down" in a.issues[0]


def test_identifiers_are_redacted_before_the_model_sees_them(retriever: HybridRetriever) -> None:
    llm = FakeLLM("NOT_FOUND")
    Answerer(retriever, llm).ask("Client ABCDE1234F asks how long ELSS units are locked in")
    assert llm.calls and "ABCDE1234F" not in llm.calls[0][1]


# Guard
@pytest.mark.parametrize(
    "q",
    [
        "Should Rohan buy more Reliance?",
        "Which stocks should I pick?",
        "Give me a multibagger tip",
        "Can my client sell HDFC Bank now?",
    ],
)
def test_guard_blocks_advice_requests(q: str) -> None:
    assert not check_question(q).allowed


@pytest.mark.parametrize(
    "q", ["How is LTCG taxed?", "What is a flexi cap fund?", "Can a client withdraw consent?"]
)
def test_guard_allows_rule_questions(q: str) -> None:
    assert check_question(q).allowed


def test_guard_flags_promises_in_answers() -> None:
    assert not check_answer("This fund offers guaranteed returns.").allowed
    assert not check_answer("You should buy this stock.").allowed


# API
def test_api_documents_and_ask() -> None:
    client = TestClient(create_app())
    docs = client.get("/v1/kb/documents").json()
    assert {d["id"] for d in docs} >= {"it-capital-gains", "dpdp-act"}
    r = client.post(
        "/v1/rag/ask", json={"question": "Within how many hours must a data breach be reported?"}
    )
    body = r.json()
    assert r.status_code == 200
    assert body["mode"] == "extractive"
    assert body["citations"][0]["doc_id"] == "dpdp-act"
    assert "72" in body["answer"]


def test_api_search_and_validation() -> None:
    client = TestClient(create_app())
    hits = client.post(
        "/v1/rag/search", json={"query": "riskometer levels", "k": 3, "mode": "bm25"}
    ).json()
    assert hits[0]["doc_id"] == "sebi-mf-disclosure"
    assert client.post("/v1/rag/ask", json={"question": "x"}).status_code == 422


def test_fullwidth_citations_are_normalised() -> None:
    """gpt-oss (Groq) writes 【1】; the verifier reads [1]. Only the brackets change."""
    from aicfo.rag.text import normalise_citations

    assert (
        normalise_citations("Default regime【1】 and ［2］ 〔 3 〕.")
        == "Default regime[1] and [2] [3]."
    )
    assert normalise_citations("No markers, 12% stays.") == "No markers, 12% stays."


def test_llm_answer_with_fullwidth_citation_is_accepted() -> None:
    from aicfo.llm import FakeLLM
    from aicfo.rag.answer import Answerer
    from aicfo.rag.service import get_rag

    answer = Answerer(
        get_rag().retriever, FakeLLM("The new tax regime is the default for individuals【1】.")
    )
    a = answer.ask("Which tax regime applies by default to individuals?")
    assert a.mode == "llm" and a.text.endswith("[1].")


def test_hard_paraphrase_set_is_retrievable_even_without_real_embeddings() -> None:
    """16 paraphrased questions: the right document must be within the top 5 for nearly all."""
    from aicfo.evals.rag_eval import HARD, evaluate, load_golden
    from aicfo.rag.service import get_rag

    rows = load_golden(HARD)
    assert len(rows) >= 16
    report = evaluate(get_rag().retriever, "hybrid", rows)
    assert report.hit_at_5 >= 0.9  # offline fallback; real embeddings reach 1.00 (see README)

import json

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from aicfo.agents.copilot import Copilot
from aicfo.agents.review import Draft, ReviewPipeline, serialise
from aicfo.agents.tools import all_evidence
from aicfo.core.analytics import snapshot
from aicfo.core.book import load_book
from aicfo.core.format import inr, inr_short
from aicfo.llm import FakeLLM
from aicfo.main import create_app
from aicfo.ml.compliance_classifier import cross_validate, get_classifier
from aicfo.rag.answer import Answerer
from aicfo.rag.service import get_rag

BOOK = load_book()
CLIENTS = list(BOOK.clients)


@pytest.fixture(scope="module")
def pipeline() -> ReviewPipeline:
    return ReviewPipeline(get_rag().retriever)


# ---------------- deterministic core ----------------
def test_hand_checked_numbers_for_rohan() -> None:
    s = snapshot("rohan-deshpande", BOOK)
    assert round(s.total) == 2_905_000
    assert round(s.allocation_pct["Equity"], 1) == 84.2
    assert round(s.drift["Equity"], 1) == 14.2
    top = s.overlaps[0]
    assert {top.a.ref, top.b.ref} == {"NSB", "HN50"} and round(top.pct, 1) == 69.4
    assert s.exposures[0].symbol == "HDFCBANK" and round(s.exposures[0].pct_of_total, 1) == 13.9
    assert s.exemption_left == 87_000
    assert [(u.position.ref, u.lot.days_to_long) for u in s.upcoming_lots] == [
        ("MFC", 12),
        ("ITC", 19),
    ]


@pytest.mark.parametrize("cid", CLIENTS)
def test_invariants_for_every_client(cid: str) -> None:
    s = snapshot(cid, BOOK)
    assert sum(s.allocation_pct.values()) == pytest.approx(100)
    assert sum(s.drift.values()) == pytest.approx(0, abs=1e-9)
    assert all(0 <= o.pct <= 100 for o in s.overlaps)
    assert all(lot.cost >= 0 for p in s.positions for lot in p.lots)
    assert 0 <= s.look_through_pct <= 100


def test_overlap_is_symmetric() -> None:
    w = BOOK.funds
    a, b = w["NSB"].weights, w["HN50"].weights
    ab = sum(min(a[k], b[k]) for k in a.keys() & b.keys())
    ba = sum(min(b[k], a[k]) for k in b.keys() & a.keys())
    assert ab == ba


@given(st.floats(min_value=0, max_value=1e10, allow_nan=False))
@settings(max_examples=200)
def test_indian_grouping_round_trips(value: float) -> None:
    assert int(inr(value).replace("₹", "").replace(",", "")) == round(value)


def test_short_format() -> None:
    assert inr_short(411_500) == "₹4.12 L" and inr_short(21_000_000) == "₹2.10 Cr"


# ---------------- agents ----------------
def test_graph_runs_every_node_in_order(pipeline: ReviewPipeline) -> None:
    st_ = pipeline.run("rohan-deshpande")
    nodes = [t.node for t in st_["trace"]]
    assert nodes[:2] == ["load_snapshot", "compute_evidence"]
    assert set(nodes[2:5]) == {
        "overlap_analyst",
        "allocation_analyst",
        "tax_analyst",
    }  # parallel fan-out
    assert nodes[5:] == ["rank", "explainer", "compliance", "verifier"]


def test_rohan_findings_match_firm_policy(pipeline: ReviewPipeline) -> None:
    drafts = pipeline.run("rohan-deshpande")["drafts"]
    kinds = {d.candidate.kind: d for d in drafts}
    assert set(kinds) == {"drift", "overlap", "concentration", "tax-timing", "harvest"}
    assert kinds["drift"].candidate.severity == "high"
    assert kinds["overlap"].candidate.severity == "medium"  # 69.4% < 70% high threshold
    assert drafts[0].candidate.kind == "drift"  # highest severity ranks first


@pytest.mark.parametrize("cid", CLIENTS)
def test_every_draft_is_cited_verified_and_number_safe(pipeline: ReviewPipeline, cid: str) -> None:
    for d in pipeline.run(cid)["drafts"]:
        assert d.status == "draft", (cid, d.verifier, d.compliance)
        assert d.citations and "[1]" in d.text
        assert d.verifier["passed"]
        assert "{client}" in d.text  # names are filled in by the browser, never by the server


def test_verifier_rejects_invented_numbers(pipeline: ReviewPipeline) -> None:
    st_ = pipeline.run("rohan-deshpande")
    good = st_["drafts"][0]
    bad = Draft(good.candidate, good.text.replace("84.2%", "91.7%"), good.citations)
    assert any("unsupported numbers" in i for i in pipeline.check(bad, st_["evidence"]))


def test_dismissed_findings_are_skipped(pipeline: ReviewPipeline) -> None:
    first = pipeline.run("rohan-deshpande")["drafts"][0].candidate.id
    again = pipeline.run("rohan-deshpande", dismissed=[first])["drafts"]
    assert first not in {d.candidate.id for d in again}


def test_mfd_profile_blocks_advice_like_text() -> None:
    llm = FakeLLM(
        lambda system, user: (
            "You should sell this fund now and buy more HDFC Bank [1]."
            if "Rewrite" in system
            else '{"selected": []}'
        )
    )
    p = ReviewPipeline(get_rag().retriever, llm)
    drafts = p.run("rohan-deshpande", profile="MFD")["drafts"]
    assert drafts == [] or all(d.status == "dropped" for d in drafts if d.author == "llm")


def test_llm_analyst_selection_is_validated() -> None:
    reply = json.dumps(
        {
            "selected": [
                {
                    "evidence_id": "drift:equity",
                    "severity": "low",
                    "title": "x",
                    "rationale": "model says low",
                },
                {"evidence_id": "made-up", "severity": "high"},
            ]
        }
    )
    llm = FakeLLM(lambda system, user: reply if "Return ONLY JSON" in system else "NOT USED")
    p = ReviewPipeline(get_rag().retriever, llm)
    st_ = p.run("rohan-deshpande")
    ids = [c.evidence_ids[0] for c in st_["candidates"]]
    assert "made-up" not in ids
    drift = next(c for c in st_["candidates"] if c.kind == "drift")
    assert drift.severity == "low" and drift.rationale == "model says low"


def test_llm_rewrite_with_new_number_falls_back_to_template() -> None:
    llm = FakeLLM(
        lambda system, user: (
            "Equity is 99% of {client}'s portfolio [1]." if "Rewrite" in system else "not json"
        )
    )
    p = ReviewPipeline(get_rag().retriever, llm)
    for d in p.run("rohan-deshpande")["drafts"]:
        assert d.author == "template" and d.verifier["passed"] and d.verifier["rewrites"] >= 1


def test_serialised_run_is_json(pipeline: ReviewPipeline) -> None:
    data = serialise(pipeline.run("kavya-nair"))
    assert json.loads(json.dumps(data))["client_id"] == "kavya-nair"


def test_evidence_ids_are_unique() -> None:
    ev = all_evidence(snapshot("rohan-deshpande", BOOK), BOOK)
    assert len(ev) == len(set(ev))


# ---------------- ML classifier ----------------
def test_classifier_cross_validated_quality() -> None:
    m = cross_validate()
    assert m.f1 >= 0.8 and m.precision >= 0.85


def test_classifier_separates_advice_from_facts() -> None:
    c = get_classifier()
    assert c.score("You should sell the index fund now.") > 0.6
    assert c.score("Equity is 84.2% of the portfolio against a 70% target.") < 0.3


# ---------------- copilot ----------------
def test_copilot_tools_rules_and_refusal() -> None:
    cp = Copilot(Answerer(get_rag().retriever))
    a = cp.ask("rohan-deshpande", "Which funds overlap the most?")
    assert a.mode == "tools" and a.tool_calls[0]["tool"] == "get_overlap" and "69.4%" in a.answer
    r = cp.ask("rohan-deshpande", "What records must an adviser keep?")
    assert r.mode == "rules" and r.citations
    assert cp.ask("rohan-deshpande", "Should Rohan buy Reliance?").mode == "refused"


def test_copilot_llm_loop_with_tool_call_and_verified_answer() -> None:
    script = iter(
        ['{"tool": "get_drift", "args": {}}', '{"answer": "Equity is +14.2 pts above the model."}']
    )
    cp = Copilot(Answerer(get_rag().retriever), FakeLLM(lambda s, u: next(script)))
    a = cp.ask("rohan-deshpande", "Why is equity high?")
    assert a.mode == "llm" and a.tool_calls[0]["tool"] == "get_drift"


def test_copilot_llm_invented_number_is_rejected() -> None:
    script = iter(
        ['{"tool": "get_drift", "args": {}}', '{"answer": "Equity is 97% of the portfolio."}']
    )
    cp = Copilot(Answerer(get_rag().retriever), FakeLLM(lambda s, u: next(script)))
    a = cp.ask("rohan-deshpande", "Why is equity high?")
    assert a.mode == "tools" and a.issues


# ---------------- API ----------------
def test_agents_api() -> None:
    client = TestClient(create_app())
    rows = client.get("/v1/clients").json()
    assert len(rows) == 12 and "name" not in rows[0]
    run = client.post("/v1/clients/rohan-deshpande/review", json={"profile": "RIA"}).json()
    assert len(run["drafts"]) == 5 and run["trace"][-1]["node"] == "verifier"
    cp = client.post(
        "/v1/clients/rohan-deshpande/copilot", json={"question": "How much LTCG exemption is left?"}
    ).json()
    assert "₹87,000" in cp["answer"]
    assert client.post("/v1/clients/nobody/review", json={}).status_code == 404

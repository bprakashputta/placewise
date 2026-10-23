"""Block 5: RAG pieces without DB/network: filters SQL, RRF fusion, grouping, citation verification."""
import asyncio

import pytest

from placewise.rag import answer as A
from placewise.rag.retrieve import Filters, Hit, _or_query, _where, fuse, group_by_candidate


def h(cid, pid, vr=None, kr=None, content="x", section="job"):
    return Hit(cid, pid, 100 + pid, section, content, vec_rank=vr, kw_rank=kr)


def test_where_builds_parameterized_filters():
    sql, args = _where(Filters(discipline="civil", metro="DFW", license_codes=["PE:TX", "LEED_AP"], min_years=8))
    assert "p.discipline = %s" in sql and "(p.metro = %s OR p.open_to_relocation)" in sql
    assert "%s = ANY(p.license_codes)" in sql and "lc = %s OR lc LIKE %s" in sql   # stateless keys: any state
    assert "p.years_experience >= %s" in sql
    assert args == ["civil", "DFW", "PE:TX", "LEED_AP", "LEED\\_AP:%", 8]
    assert _where(Filters()) == ("TRUE", [])


def test_or_query_drops_stopwords_and_keeps_terms():
    assert _or_query("drainage and HEC-RAS with Civil 3D") == "drainage OR HEC-RAS OR Civil OR 3D"


def test_rrf_rewards_agreement_between_vector_and_keyword():
    fused = fuse([h(1, 1, vr=1), h(2, 2, vr=2)], [h(2, 2, kr=1), h(3, 3, kr=2)])
    assert [x.chunk_id for x in fused][0] == 2          # in both lists → top
    both = next(x for x in fused if x.chunk_id == 2)
    assert both.vec_rank == 2 and both.kw_rank == 1
    assert both.rrf == pytest.approx(1 / 62 + 1 / 61)


def test_group_by_candidate_best_chunk_plus_bonus():
    hits = [h(1, 7), h(2, 7), h(3, 8)]
    hits[0].rrf, hits[1].rrf, hits[2].rrf = 0.03, 0.02, 0.031
    groups = group_by_candidate(hits)
    assert groups[0].person_id == 7                   # 0.03 + 0.15*0.02 = 0.033 > 0.031
    assert len(groups[0].chunks) == 2


def test_citation_verification_drops_unsupported(monkeypatch):
    hits = [h(10, 1, content="Led the Plano Channel Improvements using HEC-RAS.")]

    class FakeModel:
        async def ainvoke(self, msgs, config=None):
            return {"parsed": A.RagAnswer(answer="ok", citations=[
                A.Citation(chunk_id=10, quote="Plano  Channel Improvements"),   # whitespace differs: kept
                A.Citation(chunk_id=10, quote="managed a $90M highway"),       # not in text: dropped
                A.Citation(chunk_id=99, quote="anything")]),                    # not retrieved: dropped
                    "raw": None}

    monkeypatch.setattr(A, "_structured", lambda model, schema: FakeModel())
    ans, usage, dropped = asyncio.run(A.answer("q", hits, {1: "Jane"}, {1: {"license_codes": ["PE:TX"],
                                                                         "years_experience": 9, "city": "Plano",
                                                                         "metro": "DFW"}}))
    assert [c.quote for c in ans.citations] == ["Plano  Channel Improvements"]
    assert len(dropped) == 2


def test_understand_falls_back_without_filters_on_error(monkeypatch):
    class Boom:
        async def ainvoke(self, *a, **k):
            raise RuntimeError("api down")

    monkeypatch.setattr(A, "_structured", lambda model, schema: Boom())
    plan, usage = asyncio.run(A.understand("Texas PE in DFW"))
    assert plan.search_query == "Texas PE in DFW" and plan.filters == Filters()


def test_understand_normalizes_license_codes(monkeypatch):
    class Fake:
        async def ainvoke(self, *a, **k):
            return {"parsed": A.QueryPlan(filters=Filters(license_codes=["pe:tx", "leed_ap"]), search_query="x"),
                    "raw": None}

    monkeypatch.setattr(A, "_structured", lambda model, schema: Fake())
    plan, _ = asyncio.run(A.understand("q"))
    assert plan.filters.license_codes == ["PE:TX", "LEED_AP"]


def test_facts_line_marks_relocation_and_states():
    line = A._facts({"license_codes": ["PE:TX", "LEED_AP"], "years_experience": 9.5, "city": "Plano",
                     "metro": "DFW", "open_to_relocation": True})
    assert "PE in TX" in line and "9.5" in line and "open to relocation" in line

"""Pydantic schemas. These are the contracts between the LLM and the rest of the system:
every LLM output is validated against one of these before it touches the database."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Discipline(str, Enum):
    architecture = "architecture"
    interior_design = "interior_design"
    civil = "civil"
    structural = "structural"
    mep = "mep"
    construction_management = "construction_management"
    other = "other"


# Canonical license / certification keys. Normalizing these is what lets us filter in SQL
# instead of asking the LLM "does this person have a PE?" for every candidate.
LICENSE_KEYS = ["PE", "EIT", "RA", "AIT", "NCIDQ", "PMP", "LEED_AP", "LEED_GA", "CCM", "OSHA_30", "SE"]


class License(BaseModel):
    key: str = Field(description=f"One of {LICENSE_KEYS}. 'Pursuing' or 'eligible' does NOT count; use EIT/AIT when stated.")
    state: str | None = Field(None, description="Two-letter US state for state-issued licenses (PE, RA, SE), else null")
    evidence: str = Field(description="Exact text copied from the resume that shows this license")


class Project(BaseModel):
    name: str
    role: str | None = None
    sector: str | None = None
    value_usd: float | None = Field(None, description="Construction value in USD if stated")


class CandidateProfile(BaseModel):
    full_name: str
    current_title: str | None = None
    current_employer: str | None = None
    city: str | None = None
    state: str | None = None
    metro: str = Field(description="One of: DFW, Houston, Austin, San Antonio, Other")
    open_to_relocation: bool | None = None
    discipline: Discipline
    years_experience: float = Field(description="Total professional years in the field, computed from dates if needed")
    licenses: list[License] = []
    software: list[str] = Field(default=[], description="Tools like Revit, AutoCAD, Civil 3D, Procore, P6, Bluebeam")
    sectors: list[str] = Field(default=[], description="Market sectors worked in, e.g. healthcare, transportation, education")
    projects: list[Project] = []
    summary: str = Field(description="Two sentences, factual, no hype")
    missing_info: list[str] = Field(default=[], description="Important facts the resume does not state")


class Requirement(BaseModel):
    text: str = Field(description="The requirement in plain words")
    category: str = Field(description="license | software | sector | experience | education | location | other")
    key: str | None = Field(None, description="Normalized key when category=license (one of LICENSE_KEYS) or a tool name for software")
    state: str | None = Field(None, description="Required license state, e.g. TX, if stated")
    weight: int = Field(3, ge=1, le=5, description="Importance 1-5")


class JobOrder(BaseModel):
    title: str
    client_company: str | None = None
    city: str | None = None
    metro: str = Field(description="One of: DFW, Houston, Austin, San Antonio, Other")
    work_mode: str | None = Field(None, description="onsite | hybrid | remote")
    employment_type: str | None = Field(None, description="direct_hire | contract | contract_to_hire")
    discipline: Discipline
    min_years: float | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    must_have: list[Requirement]
    nice_to_have: list[Requirement] = []
    open_questions: list[str] = Field(default=[], description="Things the recruiter should clarify with the hiring manager")


class Verdict(str, Enum):
    met = "met"
    partial = "partial"
    not_met = "not_met"
    unknown = "unknown"


class RequirementCheck(BaseModel):
    requirement: str
    verdict: Verdict
    evidence: str | None = Field(None, description="Exact quote from the resume supporting the verdict, or null")
    note: str | None = None


class MatchAssessment(BaseModel):
    must_have: list[RequirementCheck]
    nice_to_have: list[RequirementCheck] = []
    strengths: list[str] = []
    gaps: list[str] = []
    flags: list[str] = Field(default=[], description="Risks a recruiter must check, e.g. license in another state")
    summary: str


class OutreachDraft(BaseModel):
    subject: str
    body: str


class Citation(BaseModel):
    chunk_id: int
    quote: str


class RagAnswer(BaseModel):
    answer: str
    citations: list[Citation] = []
    candidate_ids: list[int] = []


class SearchFilters(BaseModel):
    """Structured filters parsed out of a natural-language question."""
    metro: str | None = None
    discipline: Discipline | None = None
    license_keys: list[str] = []
    min_years: float | None = None
    rewritten_query: str = Field(description="The question rewritten as a search query for resume text")

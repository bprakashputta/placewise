"""Structured job order (from recruiter notes) and per-candidate match assessment."""
from typing import Literal

from pydantic import BaseModel, Field

Discipline = Literal["architecture", "interior_design", "civil", "structural", "mep", "construction_management",
                     "other"]


class Requirement(BaseModel):
    text: str = Field(description="The requirement in plain words, as a recruiter would say it")
    kind: Literal["discipline", "license", "years", "location", "software", "sector", "specialty", "other"]
    priority: Literal["must", "nice"] = Field(description="'must' only if the notes say required/must/need")
    key: str | None = Field(None, description="license key (PE, EIT, RA, SE, NCIDQ, TX_RID, LEED_AP, PMP, CCM, "
                                              "OSHA_30) or a software name")
    state: str | None = Field(None, description="Two-letter state for a state license, if stated")
    value: str | None = Field(None, description="years as a number, metro name, sector or specialty")


class JobSpec(BaseModel):
    title: str
    client: str | None = Field(None, description="As described in the notes (keep it generic)")
    city: str | None = None
    metro: Literal["DFW", "Houston", "Austin", "San Antonio", "Other"] | None = None
    work_mode: Literal["onsite", "hybrid", "remote"] | None = None
    employment_type: Literal["direct_hire", "contract", "contract_to_hire"] | None = None
    salary: str | None = None
    discipline: Discipline
    subdiscipline: str | None = None
    min_years: float | None = None
    requirements: list[Requirement]
    open_questions: list[str] = Field(default_factory=list,
                                      description="What the recruiter still needs to ask the hiring manager")


class RequirementVerdict(BaseModel):
    requirement: str = Field(description="Copy the requirement text exactly")
    verdict: Literal["met", "partial", "not_met", "unknown"]
    evidence: str | None = Field(None, description="A short quote copied EXACTLY from the candidate profile text, "
                                                   "or null if there is none")
    note: str | None = None


class MatchAssessment(BaseModel):
    verdicts: list[RequirementVerdict]
    flags: list[str] = Field(default_factory=list,
                             description="Risks a recruiter must check, e.g. license in another state, old experience")
    summary: str = Field(description="Two sentences: why this candidate fits or doesn't")

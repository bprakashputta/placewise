"""What the extraction LLM must return (validated by Pydantic before anything is stored)."""
from typing import Literal

from pydantic import BaseModel, Field

CredentialKey = Literal["PE", "EIT", "RA", "SE", "NCARB", "NCIDQ", "TX_RID", "LEED_AP", "LEED_GA", "PMP", "CCM",
                        "OSHA_30", "OTHER"]
Discipline = Literal["architecture", "interior_design", "civil", "structural", "mep", "construction_management",
                     "other"]


class ExtractedJob(BaseModel):
    title: str
    employer: str
    location: str | None = None
    start: str | None = Field(None, description="Start date exactly as written, e.g. 'Jan 2019', '01/19', '2019'")
    end: str | None = Field(None, description="End date exactly as written, or 'Present'")
    highlights: list[str] = Field(default_factory=list, description="The job's bullet points, copied verbatim")


class ExtractedCredential(BaseModel):
    quote: str = Field(description="The exact text from the resume that mentions this credential")
    key: CredentialKey
    state: str | None = Field(None, description="Two-letter US state for state-issued licenses (PE, RA, SE, EIT), "
                                                "only if the resume says it")
    status: Literal["active", "pursuing", "exam_scheduled", "expired"] = Field(
        description="'pursuing'/'exam_scheduled' if not yet licensed; 'expired' if inactive/lapsed")


class ExtractedEducation(BaseModel):
    degree: str
    school: str
    year: str | None = None


class WritingQuality(BaseModel):
    rating: Literal["good", "fair", "poor"]
    issues: list[Literal["typos", "vague_bullets", "inconsistent_formatting", "unusual_headings",
                         "no_quantified_results", "run_on_sentences"]] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list, description="Up to 3 short verbatim examples")


class ExtractedProfile(BaseModel):
    full_name: str
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    state: str | None = Field(None, description="Two-letter US state of the candidate's location")
    open_to_relocation: bool | None = Field(None, description="True only if the resume says so")
    headline: str = Field(description="Their title/focus in under 12 words, from the resume")
    discipline: Discipline
    subdiscipline: str | None = Field(None, description="e.g. transportation, drainage, Electrical, Mechanical, "
                                                        "estimating, field operations")
    summary: str | None = None
    jobs: list[ExtractedJob]
    credentials: list[ExtractedCredential] = Field(default_factory=list)
    software: list[str] = Field(default_factory=list, description="Software tools named in the resume")
    sectors: list[str] = Field(default_factory=list, description="Market sectors the person worked in")
    education: list[ExtractedEducation] = Field(default_factory=list)
    writing_quality: WritingQuality

"""Structured resume returned by the writer LLM (validated with Pydantic via LangChain).

Structure is what makes layouts reliable: the renderer knows exactly which text is a job
title, a company, a date or a bullet, instead of guessing from free text.
"""
from pydantic import BaseModel, Field, field_validator


class ResumeJob(BaseModel):
    title: str = Field(description="Job title, copied exactly from the facts")
    employer: str = Field(description="Employer, copied exactly from the facts")
    location: str = Field(description="City, ST")
    start: str = Field(description="Start date, copied exactly from the facts")
    end: str = Field(description="End date, copied exactly from the facts ('Present' for the current job)")
    bullets: list[str] = Field(description="2-5 accomplishment bullets starting with action verbs; weave the job's "
                                           "projects (name and value) into these bullets")


class ResumeEducation(BaseModel):
    degree: str
    school: str
    year: str


class ResumeSection(BaseModel):
    heading: str
    items: list[str]

    @field_validator("items", mode="before")
    @classmethod
    def flatten(cls, v):
        """The model sometimes nests lists one level deep for 'Selected Projects'. Flatten instead of rejecting."""
        if isinstance(v, list):
            out = []
            for x in v:
                out.extend(map(str, x) if isinstance(x, list) else [str(x)])
            return out
        return v


class StructuredResume(BaseModel):
    name: str
    contact: list[str] = Field(description="Email, phone, 'City, ST', and 'Open to relocation' if true")
    headline: str = Field(description="A short professional headline under the name, e.g. 'Licensed Civil Engineer "
                                      "| Transportation'. Must not mention credentials not in the facts.")
    summary_heading: str
    summary: str = Field(description="2-4 sentences; mention market sectors here (there is no sectors section)")
    experience_heading: str
    jobs: list[ResumeJob]
    skills_heading: str
    skills: list[str] = Field(description="Software from the facts, plus a few generic professional skills")
    credentials_heading: str
    credentials: list[str] = Field(description="Exactly the credential strings from the facts; empty list if none")
    education_heading: str
    education: list[ResumeEducation]
    extra_sections: list[ResumeSection] = Field(default_factory=list,
                                                description="Optional, e.g. 'Selected Projects' or 'Affiliations'; "
                                                            "only facts-based content")

    def to_text(self) -> str:
        """Plain-text rendering, used for the fact check, TXT files and search later."""
        out = [self.name, " | ".join(self.contact), self.headline, "", self.summary_heading, self.summary, "",
               self.experience_heading]
        for j in self.jobs:
            out += [f"{j.title}, {j.employer}, {j.location}", f"{j.start} - {j.end}",
                    *[f"- {b}" for b in j.bullets], ""]
        if self.skills:
            out += [self.skills_heading, ", ".join(self.skills), ""]
        if self.credentials:
            out += [self.credentials_heading, *self.credentials, ""]
        out += [self.education_heading, *[f"{e.degree}, {e.school}, {e.year}" for e in self.education], ""]
        for s in self.extra_sections:
            out += [s.heading, *[f"- {i}" for i in s.items], ""]
        return "\n".join(out).strip()

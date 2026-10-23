"""Shared builders for the Block 1 seed tests. Synthetic data only; no LLM, no writes to /app/data."""
from __future__ import annotations

from placewise.seed.facts import CandidateFacts, Credential, Education, Job, Style
from placewise.seed.resume_schema import ResumeEducation, ResumeJob, StructuredResume


def make_facts(**over) -> CandidateFacts:
    """A small, hand-built civil engineer with a Texas PE. Override any field."""
    base = dict(
        candidate_id="C9001", person_id="P9001", first_name="Testy", last_name="Fixture",
        email="testy.fixture@example.com", phone="(214) 555-0100", city="Dallas", state="TX", metro="DFW",
        open_to_relocation=False, discipline="civil", subdiscipline="transportation", years_experience=8.0,
        current_title="Senior Project Engineer", current_employer="Acme Civil Group",
        jobs=[
            Job(title="Senior Project Engineer", employer="Acme Civil Group", city="Dallas", state="TX",
                start="2022-03", end=None, start_text="Mar 2022", end_text="Present"),
            Job(title="Civil Engineer in Training", employer="Roadway Partners", city="Plano", state="TX",
                start="2018-06", end="2022-03", start_text="Jun 2018", end_text="Mar 2022"),
        ],
        credentials=[Credential(key="PE", state="TX", number="123456", text="P.E., Texas #123456")],
        software=["Civil 3D", "MicroStation"],
        sectors=["transportation"],
        education=[Education(degree="BS Civil Engineering", school="Texas Tech University", year=2018)],
        desired_salary=120000, availability="passive",
        style=Style(template="classic", persona="concise", length="medium", file_format="pdf",
                    header_style="standard", date_style="Mon YYYY"),
    )
    base.update(over)
    return CandidateFacts(**base)


def make_resume(c: CandidateFacts, **over) -> StructuredResume:
    """A structured resume that exactly matches the facts (should pass every check)."""
    contact = [c.email, c.phone, f"{c.city}, {c.state}"] + (["Open to relocation"] if c.open_to_relocation else [])
    base = dict(
        name=c.full_name, contact=contact, headline="Experienced design professional",
        summary_heading="Summary", summary="Delivers projects on time and on budget for public clients.",
        experience_heading="Experience",
        jobs=[ResumeJob(title=j.title, employer=j.employer, location=f"{j.city}, {j.state}", start=j.start_text,
                        end=j.end_text, bullets=["Delivered design packages on schedule.",
                                                 "Coordinated with clients and reviewers."]) for j in c.jobs],
        skills_heading="Skills", skills=list(c.software) + ["Client communication"],
        credentials_heading="Credentials", credentials=[cr.text for cr in c.credentials],
        education_heading="Education",
        education=[ResumeEducation(degree=e.degree, school=e.school, year=str(e.year)) for e in c.education],
    )
    base.update(over)
    return StructuredResume(**base)

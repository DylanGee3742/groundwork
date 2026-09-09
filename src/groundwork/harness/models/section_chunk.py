from pydantic import BaseModel
from typing import Literal

SectionType = Literal[
    "background",            # ECW Profile, Scope of Procurement — context only, not extracted
    "technical",              # Specification, Detailed Deliverables (D1–D7)
    "criteria",                # Award Criteria — weighted/pass-fail scoring
    "submission_procedural",   # Submission requirements/timetable — compulsory documents, deadlines
    "compliance",              # Terms and conditions — TUPE, GDPR, bribery, collusive bidding, social value
    "appendix_template",       # Form of Tender, Price Schedule, Supplier Technical Q&A
    "unclassified",            # fallback when pattern-matching can't confidently assign a type
]

class SectionChunk(BaseModel):
    id: int
    heading: str 
    content: str
    numbering_key: str 
    section_type: SectionType
    page_start: int
    page_end: int
    previous_chunk_id: int
    next_chunk_id: int
    position: int
    parent_key: str

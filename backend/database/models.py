from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from .db import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String)
    salary = Column(String)
    remote_flag = Column(Boolean, default=False)
    easy_apply = Column(Boolean, default=False)  # Phase 2 hook
    apply_url = Column(String)
    raw_description = Column(Text)

    # Scoring (filled by scorer agent)
    score = Column(Float)
    domain_flag = Column(String)        # in-scope / out-of-scope / borderline
    top_matches = Column(JSON)          # list[str]
    top_gaps = Column(JSON)             # list[str]

    # Lifecycle: scraped / scored / filtered_out / rejected / tailoring / ready / review_needed / applied / manual_apply_needed
    status = Column(String, default="scraped", index=True)

    date_scraped = Column(DateTime, default=datetime.utcnow, index=True)
    date_applied = Column(DateTime)

    # Source dedupe — same job won't be re-ingested across CSV drops
    source_hash = Column(String, unique=True, index=True)

    resumes = relationship("Resume", back_populates="job", cascade="all, delete-orphan")
    calendar_events = relationship("CalendarEvent", back_populates="job", cascade="all, delete-orphan")


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    latex_content = Column(Text)
    pdf_path = Column(String)
    iteration_count = Column(Integer, default=0)
    critic_verdict = Column(String)         # APPROVED / NEEDS WORK
    changelog = Column(Text)
    unfixable_items = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="resumes")


class EmailLog(Base):
    __tablename__ = "email_log"

    id = Column(Integer, primary_key=True)
    gmail_msg_id = Column(String, unique=True, index=True)
    sender = Column(String)
    subject = Column(String)
    body_snippet = Column(Text)
    category = Column(String, index=True)   # REAL_RESPONSE / SPAM_TRAP / AUTO_REJECTION / NEUTRAL
    confidence = Column(String)
    reason = Column(String)
    received_at = Column(DateTime, default=datetime.utcnow)
    alerted = Column(Boolean, default=False)


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    disguised_name = Column(String)
    real_details = Column(Text)
    event_time = Column(DateTime)
    google_event_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="calendar_events")


# Phase 2 — auto-apply log. Schema kept here so the table exists from day one;
# inserts only start once Phase 2 is built.
class ApplicationAttempt(Base):
    __tablename__ = "application_attempts"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    attempted_at = Column(DateTime, default=datetime.utcnow)
    success = Column(Boolean, default=False)
    failure_reason = Column(String)

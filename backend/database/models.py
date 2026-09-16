from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from .db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)

    # Telegram is optional per user — see .claude/specs/multi-user/approach.md
    telegram_enabled = Column(Boolean, default=False)
    telegram_bot_token = Column(String)
    telegram_chat_id = Column(String)

    # Free-text blocks, same style as the old hardcoded prompts.py constants —
    # injected directly into scorer/improver system prompts per user.
    candidate_profile = Column(Text)      # education, current role, presentation rules
    locked_skill_set = Column(Text)       # hard ceiling on what agents may claim
    project_library = Column(Text)        # verified facts + DO-NOT-CLAIM per project
    role_type_prefs = Column(Text)        # ranked role-type preference + penalties
    location_prefs = Column(Text)
    salary_pref = Column(String)

    master_resume_tex = Column(Text)      # this user's own LaTeX template + content

    created_at = Column(DateTime, default=datetime.utcnow)

    groq_keys = relationship("GroqKey", back_populates="user", cascade="all, delete-orphan")
    job_states = relationship("JobUserState", back_populates="user", cascade="all, delete-orphan")
    resumes = relationship("Resume", back_populates="user", cascade="all, delete-orphan")


class GroqKey(Base):
    """Plural Groq keys per user, rotated on quota exhaustion — tailoring only,
    scoring runs on the shared local Ollama instance. See groq_client.py."""
    __tablename__ = "groq_keys"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    key = Column(String, nullable=False)
    label = Column(String)                 # optional human label ("personal", "college acct")
    is_active = Column(Boolean, default=True)
    last_failure_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="groq_keys")


class InviteToken(Base):
    """Signup gate — /signup?token=... . Public site, so signup is invite-only."""
    __tablename__ = "invite_tokens"

    id = Column(Integer, primary_key=True)
    token = Column(String, unique=True, nullable=False, index=True)
    label = Column(String)                 # e.g. "vasu" — who this was generated for
    created_by_user_id = Column(Integer, ForeignKey("users.id"))
    used_by_user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    used_at = Column(DateTime)


class Job(Base):
    """Shared scrape data only — jobs are the same pool for every user. Per-user
    score/status/matches/gaps live on JobUserState, not here."""
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

    date_scraped = Column(DateTime, default=datetime.utcnow, index=True)

    # Source dedupe — same job won't be re-ingested across CSV drops
    source_hash = Column(String, unique=True, index=True)

    user_states = relationship("JobUserState", back_populates="job", cascade="all, delete-orphan")
    resumes = relationship("Resume", back_populates="job", cascade="all, delete-orphan")
    calendar_events = relationship("CalendarEvent", back_populates="job", cascade="all, delete-orphan")


class JobUserState(Base):
    """Per-(job, user) scoring + lifecycle — the same job can be a 10/10 for one
    user and a 2/10 for another. Written by the scorer (shared Ollama, once per
    active user per job) and advanced by the tailor loop."""
    __tablename__ = "job_user_state"
    __table_args__ = (UniqueConstraint("job_id", "user_id", name="uq_job_user"),)

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    score = Column(Float)
    domain_flag = Column(String)        # in-scope / out-of-scope / borderline
    top_matches = Column(JSON)          # list[str]
    top_gaps = Column(JSON)             # list[str]

    # Lifecycle: scored / filtered_out / rejected / tailoring / ready / review_needed / applied
    status = Column(String, default="scored", index=True)
    date_applied = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="user_states")
    user = relationship("User", back_populates="job_states")


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    latex_content = Column(Text)
    pdf_path = Column(String)
    iteration_count = Column(Integer, default=0)
    critic_verdict = Column(String)         # APPROVED / NEEDS WORK
    changelog = Column(Text)
    unfixable_items = Column(Text)
    # Flaw 2 tailoring checks (mechanical, no-AI). See agents/quality_check.py.
    similarity_to_master = Column(Float)    # 0..1; ~1.0 => resume ~unchanged
    jd_skill_coverage = Column(Float)       # 0..1; None when JD names no known skill
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="resumes")
    user = relationship("User", back_populates="resumes")


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

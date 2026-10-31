
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="operative")
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    case_reference = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    status = Column(String(50), default="open", nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class ReportFormat(Base):
    __tablename__ = "report_formats"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class IntelligenceReport(Base):
    __tablename__ = "intelligence_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_reference = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=True)
    heading = Column(String(500), nullable=True)
    report_format_id = Column(
        Integer, ForeignKey("report_formats.id"), nullable=True
    )
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=True)
    reporting_officer_id = Column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    department_id = Column(
        Integer, ForeignKey("departments.id"), nullable=True
    )
    incident_date = Column(DateTime(timezone=True), nullable=True)
    incident_time = Column(String(20), nullable=True)
    location = Column(String(255), nullable=True)
    lga = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    status = Column(String(50), default="submitted", nullable=False)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class RawReport(Base):
    __tablename__ = "raw_reports"

    id = Column(Integer, primary_key=True, index=True)
    intelligence_report_id = Column(
        Integer,
        ForeignKey("intelligence_reports.id"),
        nullable=False,
        index=True
    )
    submitted_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    raw_text = Column(String, nullable=False)
    submitted_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProcessedReport(Base):
    __tablename__ = "processed_reports"

    id = Column(Integer, primary_key=True, index=True)
    intelligence_report_id = Column(
        Integer,
        ForeignKey("intelligence_reports.id"),
        nullable=False,
        index=True
    )
    heading = Column(String(500), nullable=True)
    body = Column(String, nullable=True)
    comment = Column(String, nullable=True)
    processed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    processed_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    actor_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    actor_username = Column(String(100), nullable=False)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(Integer, nullable=True)
    details = Column(String(1000), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )


class ReportAccess(Base):
    __tablename__ = "report_access"

    id = Column(Integer, primary_key=True, index=True)

    report_id = Column(
        Integer,
        ForeignKey("intelligence_reports.id"),
        nullable=False,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    granted_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )


class ReportTasking(Base):
    __tablename__ = "report_taskings"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(
        Integer,
        ForeignKey("intelligence_reports.id"),
        nullable=False,
        index=True
    )
    department_id = Column(
        Integer,
        ForeignKey("departments.id"),
        nullable=False
    )
    assigned_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )
    instruction = Column(String(50), nullable=False)
    tasking_note = Column(String(1000), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )


class Investigation(Base):
    """Structured investigation dossier linked to a parent case."""
    __tablename__ = "investigations"

    id = Column(Integer, primary_key=True, index=True)
    investigation_reference = Column(String(100), unique=True, nullable=False, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    status = Column(String(50), nullable=False, default="draft")
    introduction = Column(String, nullable=True)
    facts_of_case = Column(String, nullable=True)
    objective_of_investigation = Column(String, nullable=True)
    investigation_activities = Column(String, nullable=True)
    background_check = Column(String, nullable=True)
    suspect_statements = Column(String, nullable=True)
    mobile_phone_exploitation = Column(String, nullable=True)
    findings = Column(String, nullable=True)
    conclusion = Column(String, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class LearningReference(Base):
    """
    An explicitly approved reference example for improving future AI report
    processing. Official report approval does not automatically create one.
    """
    __tablename__ = "learning_references"

    id = Column(Integer, primary_key=True, index=True)

    intelligence_report_id = Column(
        Integer,
        ForeignKey("intelligence_reports.id"),
        nullable=True,
        index=True,
    )
    processed_report_id = Column(
        Integer,
        ForeignKey("processed_reports.id"),
        nullable=True,
        index=True,
    )

    report_category = Column(String(100), nullable=False, index=True)
    approved_final_text = Column(String, nullable=False)

    submitted_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )
    approved_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )
    approved_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    is_active = Column(Boolean, default=True, nullable=False, index=True)
    withdrawn_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    withdrawn_at = Column(DateTime(timezone=True), nullable=True)
    review_notes = Column(String(1000), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

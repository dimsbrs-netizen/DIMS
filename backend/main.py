from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from pwdlib import PasswordHash

import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import jwt

from database import engine, Base, get_db
import models
from ai_service import process_raw_report

def record_audit(
    db: Session,
    actor: models.User,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: str | None = None
):
    audit_entry = models.AuditLog(
        actor_id=actor.id,
        actor_username=actor.username,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details
    )

    db.add(audit_entry)


# Create the FastAPI application
app = FastAPI(
    title="DIMS",
    description="DSS Intelligence Management System",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://dims-two.vercel.app",
],

    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize password hashing
password_hash = PasswordHash.recommended()

# Create database tables
Base.metadata.create_all(bind=engine)

# Additive migration for existing prototype databases. SQLAlchemy create_all()
# does not add columns to existing tables, so add the nullable department link
# when upgrading an older DIMS database. Existing user accounts remain intact.
from sqlalchemy import inspect, text

_user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
if "department_id" not in _user_columns:
    with engine.begin() as _connection:
        _connection.execute(
            text("ALTER TABLE users ADD COLUMN department_id INTEGER REFERENCES departments(id)")
        )

# Add forced password change support without changing existing account states.
if "must_change_password" not in _user_columns:
    with engine.begin() as _connection:
        _connection.execute(
            text("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT FALSE")
        )

# Consolidate legacy duplicate processed rows into one shared record per report.
# Older rows are preserved as edit-history snapshots before they are removed.
with engine.begin() as _connection:
    _duplicate_reports = _connection.execute(text(
        "SELECT intelligence_report_id FROM processed_reports "
        "GROUP BY intelligence_report_id HAVING COUNT(*) > 1"
    )).fetchall()
    for (_report_id,) in _duplicate_reports:
        _rows = _connection.execute(text(
            "SELECT id, heading, body, comment, processed_by, processed_at "
            "FROM processed_reports WHERE intelligence_report_id = :rid "
            "ORDER BY processed_at ASC, id ASC"
        ), {"rid": _report_id}).mappings().all()
        if len(_rows) < 2:
            continue
        _canonical_id = _rows[-1]["id"]
        for _old in _rows[:-1]:
            # Keep any edit history already attached to an older row.
            _connection.execute(text(
                "UPDATE processed_report_edit_history "
                "SET processed_report_id = :canonical "
                "WHERE processed_report_id = :old_id"
            ), {"canonical": _canonical_id, "old_id": _old["id"]})
            if _old["processed_by"] is not None:
                _connection.execute(text(
                    "INSERT INTO processed_report_edit_history "
                    "(processed_report_id, edited_by, previous_heading, previous_body, previous_comment, edited_at) "
                    "VALUES (:pid, :editor, :heading, :body, :comment, :edited_at)"
                ), {"pid": _canonical_id, "editor": _old["processed_by"],
                    "heading": _old["heading"], "body": _old["body"],
                    "comment": _old["comment"], "edited_at": _old["processed_at"]})
            _connection.execute(text("DELETE FROM processed_reports WHERE id = :old_id"), {"old_id": _old["id"]})


# Registration request
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)



class ReportSubmission(BaseModel):
    raw_text: str = Field(min_length=10)
    title: str | None = Field(default=None, max_length=255)
    report_format_id: int | None = None
    case_id: int | None = None
    department_id: int | None = None
    incident_date: datetime | None = None
    incident_time: str | None = Field(default=None, max_length=20)
    location: str | None = Field(default=None, max_length=255)
    lga: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)



class ReportTaskingRequest(BaseModel):
    department_id: int
    instruction: str
    tasking_note: str | None = None
    
class ReportProcessing(BaseModel):
    heading: str = Field(min_length=3, max_length=500)
    body: str = Field(min_length=1)
    comment: str | None = None



# Home endpoint
@app.get("/")
def home():
    return {
        "system": "DIMS",
        "status": "Running",
        "version": "0.1.0"
    }


# Health check
@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }


# User registration
@app.post("/register", status_code=403)
def register_user():
    raise HTTPException(
        status_code=403,
        detail="Public registration is disabled. Contact the DIMS Administrator for an account."
    )

# Login request
class UserLogin(BaseModel):
    username: str
    password: str


class UserStatusUpdate(BaseModel):
    is_active: bool


class UserRoleUpdate(BaseModel):
    role: str


    # User login
@app.post("/login")
def login_user(user: UserLogin, db: Session = Depends(get_db)):

   
    # Find user
    db_user = db.query(models.User).filter(
        models.User.username == user.username
    ).first()

    # Check username
    if not db_user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    # Verify password
    if not password_hash.verify(
        user.password,
        db_user.hashed_password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

#Check account status
    if not db_user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is inactive"
    )

    # Generate JWT access token
    access_token = jwt.encode(
        {
            "sub": db_user.username,
            "exp": datetime.now(timezone.utc)
            + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
)

    return {
    "message": "Login successful",
    "access_token": access_token,
    "token_type": "bearer",
    "user_id": db_user.id,
    "username": db_user.username,
    "role": db_user.role,
    "full_name": db_user.full_name,
    "designation": db_user.designation,
    "formation": db_user.formation,
    "must_change_password": bool(getattr(db_user, "must_change_password", False))
}


# Load environment variables
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not configured")
security = HTTPBearer()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")

        if not username:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token"
            )

    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token"
        )

    db_user = db.query(models.User).filter(
        models.User.username == username
    ).first()

    if not db_user:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    # Enforce account status centrally for every endpoint using authentication.
    if not db_user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive.")

    # Temporary passwords permit access only to the password change endpoint.
    if getattr(db_user, "must_change_password", False) and request.url.path.rstrip("/") != "/auth/change-password":
        raise HTTPException(
            status_code=403,
            detail="Password change required. Sign in with your temporary password and change it to continue."
        )

    return db_user



# DIMS role permissions
ROLE_PERMISSIONS = {
    "operative": {
        "CREATE_REPORT",
        "VIEW_REPORT",
        "EDIT_REPORT",
        "VIEW_CASE",
    },

    "analyst": {
        "CREATE_REPORT",
        "VIEW_REPORT",
        "EDIT_REPORT",
        "PROCESS_INTELLIGENCE",
        "VIEW_CASE",
        "CREATE_CASE",
    },

    "supervisor": {
        "CREATE_REPORT",
        "VIEW_REPORT",
        "EDIT_REPORT",
        "PROCESS_INTELLIGENCE",
        "VIEW_CASE",
        "CREATE_CASE",
        "ASSIGN_CASE",
        "VIEW_AUDIT_LOG",
    },

    "management": {
        "CREATE_REPORT",
        "VIEW_REPORT",
        "EDIT_REPORT",
        "PROCESS_INTELLIGENCE",
        "VIEW_CASE",
        "CREATE_CASE",
        "ASSIGN_CASE",
        "APPROVE_REPORT",
        "APPROVE_LEARNING_REFERENCE",
        "VIEW_AUDIT_LOG",
    },

    "admin": {
        "MANAGE_USERS",
        "VIEW_AUDIT_LOG",
    },
}


def require_role(*allowed_roles):
    def role_checker(
        current_user: models.User = Depends(get_current_user)
    ):
        if not current_user.is_active:
            raise HTTPException(
                status_code=403,
                detail="Your account is inactive."
            )

        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to access this resource"
            )

        return current_user

    return role_checker


def require_permission(required_permission):
    def permission_checker(
        current_user: models.User = Depends(get_current_user)
    ):
        if not current_user.is_active:
            raise HTTPException(
                status_code=403,
                detail="Your account is inactive."
            )

        user_permissions = ROLE_PERMISSIONS.get(
            current_user.role,
            set()
        )

        if required_permission not in user_permissions:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to perform this action"
            )

        return current_user

    return permission_checker


@app.get("/me")
def get_my_profile(current_user=Depends(get_current_user)):
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "department_id": current_user.department_id
    }


@app.get("/admin")
def admin_dashboard(
    current_user: models.User = Depends(require_role("admin"))
):
    return {
        "message": "Welcome to the DIMS Admin Dashboard",
        "user_id": current_user.id,
        "username": current_user.username,
        "role": current_user.role
    }


@app.get("/users")
def list_users(
    current_user: models.User = Depends(require_permission("MANAGE_USERS")),
    db: Session = Depends(get_db)
):
    users = db.query(models.User).all()
    

    return [
        {
            "user_id": user.id,
            "username": user.username,
            "role": user.role,
            "full_name": user.full_name,
            "designation": user.designation,
            "formation": user.formation,
            "department_id": user.department_id,
            "department": (
                db.query(models.Department).filter(models.Department.id == user.department_id).first().name
                if user.department_id else None
            ),
            "is_active": user.is_active,
            "created_at": user.created_at
        }
        for user in users
    ]


@app.patch("/users/{user_id}/status")
def update_user_status(
    user_id: int,
    status: UserStatusUpdate,
    current_user: models.User = Depends(require_role("admin")),

    db: Session = Depends(get_db)
):

    
    user = db.query(models.User).filter(
        models.User.id == user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )


    old_status = user.is_active
    user.is_active = status.is_active

    record_audit(
        db=db,
        actor=current_user,
        action="USER_STATUS_CHANGED",
        entity_type="user",
        entity_id=user.id,
        details=f"Account active status changed from {old_status} to {user.is_active}"
    )

    db.commit()
    db.refresh(user)


    return {
        "message": "User status updated successfully",
        "user_id": user.id,
        "username": user.username,
        "is_active": user.is_active
    }



@app.patch("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    role_update: UserRoleUpdate,
    current_user: models.User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    allowed_roles = {
        "operative",
        "analyst",
        "supervisor",
        "management",
        "admin"
    }

    # Normalize role input to lowercase.
    new_role = role_update.role.strip().lower()

    if new_role not in allowed_roles:
        raise HTTPException(
            status_code=400,
            detail="Invalid role. Allowed roles: operative, analyst, supervisor, management, admin"
        )

    if user_id == current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Administrators cannot change their own role"
        )

    user = db.query(models.User).filter(
        models.User.id == user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )


    old_role = user.role
    user.role = new_role

    record_audit(
        db=db,
        actor=current_user,
        action="USER_ROLE_CHANGED",
        entity_type="user",
        entity_id=user.id,
        details=f"Role changed from {old_role} to {new_role}"
    )

    db.commit()
    db.refresh(user)


    return {
        "message": "User role updated successfully",
        "user_id": user.id,
        "username": user.username,
        "old_role": old_role,
        "new_role": user.role
    }


class UserDepartmentUpdate(BaseModel):
    department_id: int | None = None


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=255)


@app.post("/departments", status_code=201)
def create_department(
    payload: DepartmentCreate,
    current_user: models.User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    name = payload.name.strip()
    if db.query(models.Department).filter(models.Department.name.ilike(name)).first():
        raise HTTPException(status_code=409, detail="A department with this name already exists.")
    department = models.Department(name=name, description=(payload.description or "").strip() or None, is_active=True)
    db.add(department)
    try:
        db.flush()
        record_audit(db, current_user, "DEPARTMENT_CREATED", "department", department.id, f"Created department {department.name}")
        db.commit()
        db.refresh(department)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to create department.")
    return {"id": department.id, "name": department.name, "description": department.description, "is_active": department.is_active}


@app.get("/departments")
def list_departments(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_active or current_user.role not in {"admin", "management"}:
        raise HTTPException(status_code=403, detail="Only Admin and Management can view department records.")
    departments = (
        db.query(models.Department)
        .filter(models.Department.is_active == True)
        .order_by(models.Department.name.asc())
        .all()
    )
    return [
        {"id": item.id, "name": item.name, "description": item.description}
        for item in departments
    ]


@app.patch("/users/{user_id}/department")
def update_user_department(
    user_id: int,
    assignment: UserDepartmentUpdate,
    current_user: models.User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role != "analyst":
        raise HTTPException(status_code=400, detail="Department assignment is required here only for Analyst accounts.")
    if assignment.department_id is None:
        raise HTTPException(status_code=400, detail="An Analyst must be assigned to a department.")
    department = (
        db.query(models.Department)
        .filter(models.Department.id == assignment.department_id, models.Department.is_active == True)
        .first()
    )
    if not department:
        raise HTTPException(status_code=404, detail="Active department not found")
    previous_department_id = user.department_id
    user.department_id = department.id
    record_audit(
        db, current_user, "USER_DEPARTMENT_CHANGED", "user", user.id,
        f"Department changed from {previous_department_id} to {department.id} ({department.name})"
    )
    db.commit()
    db.refresh(user)
    return {
        "message": "Analyst department updated successfully",
        "user_id": user.id,
        "username": user.username,
        "department_id": user.department_id,
        "department": department.name,
    }


import secrets


@app.post("/reports", status_code=201)
def submit_report(
    submission: ReportSubmission,
    current_user: models.User = Depends(
        require_permission("CREATE_REPORT")
    ),
    db: Session = Depends(get_db)
):
    # Validate optional linked records.
    if submission.report_format_id is not None:
        report_format = db.query(models.ReportFormat).filter(
            models.ReportFormat.id == submission.report_format_id,
            models.ReportFormat.is_active == True
        ).first()

        if not report_format:
            raise HTTPException(
                status_code=400,
                detail="Report format not found or inactive"
            )

    if submission.case_id is not None:
        case = db.query(models.Case).filter(
            models.Case.id == submission.case_id
        ).first()

        if not case:
            raise HTTPException(
                status_code=400,
                detail="Case not found"
            )

    if submission.department_id is not None:
        department = db.query(models.Department).filter(
            models.Department.id == submission.department_id,
            models.Department.is_active == True
        ).first()

        if not department:
            raise HTTPException(
                status_code=400,
                detail="Department not found or inactive"
            )

    # Generate a unique report reference.
    report_reference = f"DIMS-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(4).upper()}"

    report = models.IntelligenceReport(
        report_reference=report_reference,
        title=submission.title,
        report_format_id=submission.report_format_id,
        case_id=submission.case_id,
        reporting_officer_id=current_user.id,
        department_id=submission.department_id,
        incident_date=submission.incident_date,
        incident_time=submission.incident_time,
        location=submission.location,
        lga=submission.lga,
        state=submission.state,
        status="submitted"
    )

    try:
        db.add(report)
        db.flush()

        raw_report = models.RawReport(
            intelligence_report_id=report.id,
            submitted_by=current_user.id,
            raw_text=submission.raw_text
        )

        
        db.add(raw_report)

        record_audit(
        db=db,
        actor=current_user,
        action="REPORT_SUBMITTED",
        entity_type="intelligence_report",
        entity_id=report.id,
        details=f"Report reference: {report.report_reference}"
        )

        db.commit()
        db.refresh(report)


        return {
            "message": "Report submitted successfully",
            "report_id": report.id,
            "report_reference": report.report_reference,
            "status": report.status,
            "submitted_by": current_user.username
        }

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Report submission failed"
        )


def can_access_report(
    report: models.IntelligenceReport,
    current_user: models.User,
    db: Session
) -> bool:
    # Management can access all reports.
    if current_user.role == "management":
        return True

    # Admin does not automatically access intelligence reports.
    if current_user.role == "admin":
        return False

    # The reporting operative can access their own report.
    if report.reporting_officer_id == current_user.id:
        return True

    # Analysts can access only reports actively assigned to their department.
    if current_user.role == "analyst" and current_user.is_active and current_user.department_id:
        department_assignment = (
            db.query(models.ReportTasking)
            .filter(
                models.ReportTasking.report_id == report.id,
                models.ReportTasking.department_id == current_user.department_id,
                models.ReportTasking.is_active == True,
            )
            .first()
        )
        if department_assignment:
            return True

    # A previous reviewer retains read-only access after forwarding the report.
    previous_review = (
        db.query(models.ReportForwardHistory)
        .filter(
            models.ReportForwardHistory.report_id == report.id,
            models.ReportForwardHistory.sender_id == current_user.id,
        )
        .first()
    )
    if previous_review and current_user.is_active:
        return True

    # A report remains accessible to its currently assigned reviewer.
    workflow_assignment = db.query(models.ReportWorkflow).filter_by(
        report_id=report.id, current_assignee_id=current_user.id, workflow_status="in_review"
    ).first()
    if workflow_assignment and current_user.is_active:
        return True

    # Other users need an explicit report-access grant.
    access_grant = (
        db.query(models.ReportAccess)
        .filter(
            models.ReportAccess.report_id == report.id,
            models.ReportAccess.user_id == current_user.id
        )
        .first()
    )
    return access_grant is not None



class CaseCreation(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


@app.post("/cases", status_code=201)
def create_case(
    case_data: CaseCreation,
    current_user: models.User = Depends(
        require_permission("CREATE_CASE")
    ),
    db: Session = Depends(get_db)
):
    import uuid
    from datetime import datetime

    case_reference = (
        f"DIMS-CASE-{datetime.now().strftime('%Y%m%d')}-"
        f"{uuid.uuid4().hex[:6].upper()}"
    )

    new_case = models.Case(
        case_reference=case_reference,
        title=case_data.title,
        description=case_data.description,
        status="open",
        created_by=current_user.id
    )

    db.add(new_case)
    db.commit()
    db.refresh(new_case)

    record_audit(
        db,
        current_user,
        "CASE_CREATED",
        "case",
        new_case.id,
        f"Created case {new_case.case_reference}"
    )

    db.commit()

    return {
        "message": "Case created successfully",
        "id": new_case.id,
        "case_reference": new_case.case_reference,
        "title": new_case.title,
        "description": new_case.description,
        "status": new_case.status,
        "created_by": new_case.created_by,
        "created_at": new_case.created_at
    }


@app.get("/cases")
def list_cases(
    current_user: models.User = Depends(
        require_permission("VIEW_CASE")
    ),
    db: Session = Depends(get_db)
):
    cases = (
        db.query(models.Case)
        .order_by(models.Case.created_at.desc())
        .all()
    )

    return {
        "count": len(cases),
        "cases": [
            {
                "id": case.id,
                "case_reference": case.case_reference,
                "title": case.title,
                "description": case.description,
                "status": case.status,
                "created_by": case.created_by,
                "created_at": case.created_at,
                "updated_at": case.updated_at
            }
            for case in cases
        ]
    }


@app.get("/cases/{case_id}")
def get_case(
    case_id: int,
    current_user: models.User = Depends(
        require_permission("VIEW_CASE")
    ),
    db: Session = Depends(get_db)
):
    case = (
        db.query(models.Case)
        .filter(models.Case.id == case_id)
        .first()
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    return {
        "id": case.id,
        "case_reference": case.case_reference,
        "title": case.title,
        "description": case.description,
        "status": case.status,
        "created_by": case.created_by,
        "created_at": case.created_at,
        "updated_at": case.updated_at
    }





class CaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class CaseStatusUpdate(BaseModel):
    status: str


@app.patch("/cases/{case_id}")
def update_case(
    case_id: int,
    case_data: CaseUpdate,
    current_user: models.User = Depends(
        require_permission("CREATE_CASE")
    ),
    db: Session = Depends(get_db)
):
    case = db.query(models.Case).filter(
        models.Case.id == case_id
    ).first()

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    changes = case_data.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one field to update"
        )

    for field, value in changes.items():
        setattr(case, field, value)

    record_audit(
        db,
        current_user,
        "CASE_UPDATED",
        "case",
        case.id,
        f"Updated fields: {', '.join(changes.keys())}"
    )

    db.commit()
    db.refresh(case)

    return {
        "message": "Case updated successfully",
        "id": case.id,
        "case_reference": case.case_reference,
        "title": case.title,
        "description": case.description,
        "status": case.status,
        "updated_at": case.updated_at
    }


@app.patch("/cases/{case_id}/status")
def update_case_status(
    case_id: int,
    status_data: CaseStatusUpdate,
    current_user: models.User = Depends(
        require_permission("CREATE_CASE")
    ),
    db: Session = Depends(get_db)
):
    allowed_statuses = {
        "open",
        "under investigation",
        "closed"
    }

    new_status = status_data.status.strip().lower()

    if new_status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid status. Choose: open, "
                "under investigation, or closed."
            )
        )

    case = db.query(models.Case).filter(
        models.Case.id == case_id
    ).first()

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    old_status = case.status
    case.status = new_status

    record_audit(
        db,
        current_user,
        "CASE_STATUS_UPDATED",
        "case",
        case.id,
        f"Status changed from {old_status} to {new_status}"
    )

    db.commit()
    db.refresh(case)

    return {
        "message": "Case status updated successfully",
        "id": case.id,
        "case_reference": case.case_reference,
        "status": case.status,
        "updated_at": case.updated_at
    }


# Investigation Management: structured dossier linked to a case.
INVESTIGATION_SECTIONS = {
    "introduction", "facts_of_case", "objective_of_investigation",
    "investigation_activities", "background_check", "suspect_statements",
    "mobile_phone_exploitation", "findings", "conclusion"
}

class InvestigationCreate(BaseModel):
    case_id: int
    title: str = Field(..., min_length=3, max_length=500)
    introduction: str | None = None
    facts_of_case: str | None = None
    objective_of_investigation: str | None = None
    investigation_activities: str | None = None
    background_check: str | None = None
    suspect_statements: str | None = None
    mobile_phone_exploitation: str | None = None
    findings: str | None = None
    conclusion: str | None = None

class InvestigationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=500)
    status: str | None = None
    introduction: str | None = None
    facts_of_case: str | None = None
    objective_of_investigation: str | None = None
    investigation_activities: str | None = None
    background_check: str | None = None
    suspect_statements: str | None = None
    mobile_phone_exploitation: str | None = None
    findings: str | None = None
    conclusion: str | None = None

def investigation_payload(item):
    return {
        "id": item.id,
        "investigation_reference": item.investigation_reference,
        "case_id": item.case_id,
        "title": item.title,
        "status": item.status,
        "introduction": item.introduction,
        "facts_of_case": item.facts_of_case,
        "objective_of_investigation": item.objective_of_investigation,
        "investigation_activities": item.investigation_activities,
        "background_check": item.background_check,
        "suspect_statements": item.suspect_statements,
        "mobile_phone_exploitation": item.mobile_phone_exploitation,
        "findings": item.findings,
        "conclusion": item.conclusion,
        "created_by": item.created_by,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }

@app.get("/investigations")
def list_investigations(
    case_id: int | None = None,
    current_user: models.User = Depends(require_permission("VIEW_CASE")),
    db: Session = Depends(get_db),
):
    query = db.query(models.Investigation)
    if case_id is not None:
        query = query.filter(models.Investigation.case_id == case_id)
    items = query.order_by(models.Investigation.updated_at.desc()).all()
    return {"count": len(items), "investigations": [investigation_payload(item) for item in items]}

@app.post("/investigations", status_code=201)
def create_investigation(
    data: InvestigationCreate,
    current_user: models.User = Depends(require_permission("CREATE_CASE")),
    db: Session = Depends(get_db),
):
    case = db.query(models.Case).filter(models.Case.id == data.case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Parent case not found")
    import uuid
    reference = f"DIMS-INV-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    values = data.model_dump()
    item = models.Investigation(
        investigation_reference=reference,
        case_id=data.case_id,
        title=data.title.strip(),
        created_by=current_user.id,
        **{key: value for key, value in values.items() if key not in {"case_id", "title"}}
    )
    db.add(item)
    db.flush()
    record_audit(db, current_user, "INVESTIGATION_CREATED", "investigation", item.id,
                 f"Created {reference} under case {case.case_reference}")
    db.commit()
    db.refresh(item)
    return {"message": "Investigation created successfully", **investigation_payload(item)}

@app.get("/investigations/{investigation_id}")
def get_investigation(
    investigation_id: int,
    current_user: models.User = Depends(require_permission("VIEW_CASE")),
    db: Session = Depends(get_db),
):
    item = db.query(models.Investigation).filter(models.Investigation.id == investigation_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return investigation_payload(item)

@app.patch("/investigations/{investigation_id}")
def update_investigation(
    investigation_id: int,
    data: InvestigationUpdate,
    current_user: models.User = Depends(require_permission("CREATE_CASE")),
    db: Session = Depends(get_db),
):
    item = db.query(models.Investigation).filter(models.Investigation.id == investigation_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    changes = data.model_dump(exclude_unset=True)
    if "status" in changes:
        changes["status"] = (changes["status"] or "").strip().lower()
        if changes["status"] not in {"draft", "in progress", "completed"}:
            raise HTTPException(status_code=400, detail="Status must be draft, in progress, or completed")
    if not changes:
        raise HTTPException(status_code=400, detail="Provide at least one field to update")
    for field, value in changes.items():
        setattr(item, field, value.strip() if field == "title" and value else value)
    record_audit(db, current_user, "INVESTIGATION_UPDATED", "investigation", item.id,
                 f"Updated fields: {', '.join(changes.keys())}")
    db.commit()
    db.refresh(item)
    return {"message": "Investigation updated successfully", **investigation_payload(item)}

@app.get("/reports")
def list_reports(
    current_user: models.User = Depends(
        require_permission("VIEW_REPORT")
    ),
    db: Session = Depends(get_db)
):
    query = db.query(models.IntelligenceReport)

    # Management can view all reports.
    if current_user.role == "management":
        reports = query.all()

    # Admin has no automatic access to intelligence reports.
    elif current_user.role == "admin":
        reports = []

    # Other roles can view reports they submitted or
    # reports explicitly granted to them.
    else:
        accessible_report_ids = (
            db.query(models.ReportAccess.report_id)
            .filter(models.ReportAccess.user_id == current_user.id)
        )

        if current_user.role == "analyst" and current_user.department_id:
            department_report_ids = (
                db.query(models.ReportTasking.report_id)
                .filter(
                    models.ReportTasking.department_id == current_user.department_id,
                    models.ReportTasking.is_active == True,
                )
            )
        else:
            department_report_ids = db.query(models.ReportTasking.report_id).filter(False)

        workflow_report_ids = db.query(models.ReportWorkflow.report_id).filter(
            models.ReportWorkflow.current_assignee_id == current_user.id,
            models.ReportWorkflow.workflow_status == "in_review"
        )
        reports = (
            query.filter(
                (models.IntelligenceReport.reporting_officer_id == current_user.id)
                | models.IntelligenceReport.id.in_(accessible_report_ids)
                | models.IntelligenceReport.id.in_(department_report_ids)
                | models.IntelligenceReport.id.in_(workflow_report_ids)
            ).all()
        )

    reports.sort(
        key=lambda report: report.created_at,
        reverse=True
    )

    results = []

    for report in reports:
        raw_report = (
            db.query(models.RawReport)
            .filter(
                models.RawReport.intelligence_report_id == report.id
            )
            .order_by(
                models.RawReport.submitted_at.desc()
            )
            .first()
        )

        results.append({
            "report_id": report.id,
            "report_reference": report.report_reference,
            "title": report.title,
            "heading": report.heading,
            "status": report.status,
            "incident_date": report.incident_date,
            "incident_time": report.incident_time,
            "location": report.location,
            "lga": report.lga,
            "state": report.state,
            "submitted_by": report.reporting_officer_id,
            "created_at": report.created_at,
            "raw_text": raw_report.raw_text if raw_report else None
        })

    return {
        "count": len(results),
        "reports": results
    }




@app.get("/reports/{report_id}")
def get_report(
    report_id: int,
    current_user: models.User = Depends(
        require_permission("VIEW_REPORT")
    ),
    db: Session = Depends(get_db)
):
    report = (
        db.query(models.IntelligenceReport)
        .filter(
            models.IntelligenceReport.id == report_id
        )
        .first()
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found"
        )

    if not can_access_report(report, current_user, db):
        raise HTTPException(
            status_code=404,
            detail="Report not found"
        )

    processed_report = db.query(models.ProcessedReport).filter_by(intelligence_report_id=report.id).order_by(models.ProcessedReport.id.desc()).first()
    raw_report = (
        db.query(models.RawReport)
        .filter(
            models.RawReport.intelligence_report_id == report.id
        )
        .order_by(
            models.RawReport.submitted_at.desc()
        )
        .first()
    )

    return {
        "report_id": report.id,
        "report_reference": report.report_reference,
        "title": report.title,
        "heading": report.heading,
        "report_format_id": report.report_format_id,
        "case_id": report.case_id,
        "reporting_officer_id": report.reporting_officer_id,
        "department_id": report.department_id,
        "status": report.status,
        "incident_date": report.incident_date,
        "incident_time": report.incident_time,
        "location": report.location,
        "lga": report.lga,
        "state": report.state,
        "created_at": report.created_at,
        "raw_text": raw_report.raw_text if raw_report else None,
        "processed_heading": processed_report.heading if processed_report else None,
        "processed_body": processed_report.body if processed_report else None,
        "processed_comment": processed_report.comment if processed_report else None
    }


@app.post("/reports/{report_id}/process", status_code=201)
def process_report(
    report_id: int,
    processing: ReportProcessing,
    current_user: models.User = Depends(
        require_permission("PROCESS_INTELLIGENCE")
    ),
    db: Session = Depends(get_db)
):
    report = db.query(models.IntelligenceReport).filter(
        models.IntelligenceReport.id == report_id
    ).first()

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found"
        )

    if not can_access_report(report, current_user, db):
        raise HTTPException(
            status_code=404,
            detail="Report not found"
        )

    # Processing is permitted only while the Analyst's department has an
    # active Management assignment. The tasking instruction does not limit
    # access: all valid instructions authorise departmental handling.
    if current_user.role == "analyst":
        if not current_user.department_id:
            raise HTTPException(status_code=403, detail="Your Analyst account has no department assignment.")
        active_assignment = (
            db.query(models.ReportTasking)
            .filter(
                models.ReportTasking.report_id == report.id,
                models.ReportTasking.department_id == current_user.department_id,
                models.ReportTasking.is_active == True,
            )
            .first()
        )
        if not active_assignment:
            raise HTTPException(status_code=403, detail="This report is not currently assigned to your department.")


    workflow = db.query(models.ReportWorkflow).filter_by(report_id=report.id).first()
    if current_user.role == "analyst" and workflow and workflow.current_assignee_id != current_user.id:
        raise HTTPException(status_code=403, detail="This report has been forwarded. The Analyst can no longer edit it.")
    if current_user.role in {"management", "supervisor"}:
        if not workflow or workflow.current_assignee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Only the current assigned reviewer may edit this report.")
    processed = db.query(models.ProcessedReport).filter_by(intelligence_report_id=report.id).order_by(models.ProcessedReport.id.desc()).first()
    if processed is None:
        processed = models.ProcessedReport(intelligence_report_id=report.id, processed_by=current_user.id)
        db.add(processed)
    else:
        db.add(models.ProcessedReportEditHistory(
            processed_report_id=processed.id, edited_by=current_user.id,
            previous_heading=processed.heading, previous_body=processed.body,
            previous_comment=processed.comment
        ))
    processed.heading = processing.heading
    processed.body = processing.body
    processed.comment = processing.comment
    processed.processed_by = current_user.id
    processed.processed_at = datetime.now(timezone.utc)

    try:
        # Update the report's current heading and workflow status.
        report.heading = processing.heading
        report.status = "processed"

        db.flush()

        record_audit(
            db=db,
            actor=current_user,
            action="INTELLIGENCE_PROCESSED",
            entity_type="intelligence_report",
            entity_id=report.id,
            details=f"Processed report ID: {processed.id}"
        )

        db.commit()
        db.refresh(processed)
        db.refresh(report)

        return {
            "message": "Intelligence processing saved successfully",
            "report_id": report.id,
            "report_reference": report.report_reference,
            "processed_report_id": processed.id,
            "heading": processed.heading,
            "status": report.status,
            "processed_by": current_user.username,
            "processed_at": processed.processed_at
        }


    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to save processed report"
        )


@app.get("/reports/{report_id}/processing-history")
def get_processing_history(
    report_id: int,
    current_user: models.User = Depends(
        require_permission("VIEW_REPORT")
    ),
    db: Session = Depends(get_db)
):
    report = db.query(models.IntelligenceReport).filter(
        models.IntelligenceReport.id == report_id
    ).first()

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found"
        )

    if not can_access_report(report, current_user, db):
        raise HTTPException(
            status_code=404,
            detail="Report not found"
        )

    raw_reports = (
        db.query(models.RawReport)
        .filter(
            models.RawReport.intelligence_report_id == report_id
        )
        .order_by(models.RawReport.submitted_at.asc())
        .all()
    )

    edit_history = (
        db.query(models.ProcessedReportEditHistory)
        .join(models.ProcessedReport, models.ProcessedReport.id == models.ProcessedReportEditHistory.processed_report_id)
        .filter(models.ProcessedReport.intelligence_report_id == report_id)
        .order_by(models.ProcessedReportEditHistory.edited_at.asc())
        .all()
    )

    processed_reports = (
        db.query(models.ProcessedReport)
        .filter(
            models.ProcessedReport.intelligence_report_id == report_id
        )
        .order_by(models.ProcessedReport.processed_at.asc())
        .all()
    )

    return {
        "report_id": report.id,
        "report_reference": report.report_reference,
        "status": report.status,
        "original_submissions": [
            {
                "submitted_by": item.submitted_by,
                "submitted_at": item.submitted_at,
                "raw_text": item.raw_text
            }
            for item in raw_reports
        ],
        "processing_history": [
            {
                "processed_report_id": item.id,
                "heading": item.heading,
                "body": item.body,
                "comment": item.comment,
                "processed_by": item.processed_by,
                "processed_at": item.processed_at
            }
            for item in processed_reports
        ],
        "edit_history": [
            {"edited_by": item.edited_by,
             "edited_by_name": (db.query(models.User).filter(models.User.id == item.edited_by).first().full_name
                                or db.query(models.User).filter(models.User.id == item.edited_by).first().username)
                               if db.query(models.User).filter(models.User.id == item.edited_by).first() else "Unknown user",
             "previous_heading": item.previous_heading,
             "previous_body": item.previous_body, "previous_comment": item.previous_comment,
             "edited_at": item.edited_at}
            for item in edit_history
        ]
    }



@app.post("/reports/{report_id}/approve")
def approve_report(
    report_id: int,
    current_user: models.User = Depends(
        require_role("management")
    ),
    db: Session = Depends(get_db)
):
    report = db.query(models.IntelligenceReport).filter(
        models.IntelligenceReport.id == report_id
    ).first()

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found"
        )

    designation = (current_user.designation or "").strip().lower()
    if not ("state director" in designation or designation == "sds"):
        raise HTTPException(status_code=403, detail="Only the State Director designation can approve reports in this release.")
    workflow = db.query(models.ReportWorkflow).filter_by(report_id=report.id).first()
    if not workflow or workflow.current_assignee_id != current_user.id:
        raise HTTPException(status_code=403, detail="This report is not currently assigned to you for final approval.")

    if report.status == "approved":
        raise HTTPException(
            status_code=409,
            detail="This report has already been approved."
        )

    if report.status != "processed":
        raise HTTPException(
            status_code=400,
            detail="Only processed reports can be approved."
        )

    try:

        report.status = "approved"
        workflow.workflow_status = "approved"
        report.approved_by = current_user.id
        report.approved_at = datetime.now(timezone.utc)

        # Approval closes the departmental work item while preserving its history.
        db.query(models.ReportTasking).filter(
            models.ReportTasking.report_id == report.id,
            models.ReportTasking.is_active == True,
        ).update({"is_active": False}, synchronize_session=False)

        record_audit(
            db=db,
            actor=current_user,
            action="REPORT_APPROVED",
            entity_type="intelligence_report",
            entity_id=report.id,
            details=f"Report reference: {report.report_reference}"
        )

        db.commit()
        db.refresh(report)


        return {
            "message": "Report approved successfully",
            "report_id": report.id,
            "report_reference": report.report_reference,
            "status": report.status,
            "approved_by": current_user.username,
            "approved_at": report.approved_at
        }

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to approve report"
        )


@app.get("/audit-logs")
def list_audit_logs(
    current_user: models.User = Depends(
        require_permission("VIEW_AUDIT_LOG")
    ),
    db: Session = Depends(get_db),
    limit: int = 100,
    offset: int = 0
):
    if limit < 1 or limit > 500:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 500"
        )

    if offset < 0:
        raise HTTPException(
            status_code=400,
            detail="Offset cannot be negative"
        )

    logs = (
        db.query(models.AuditLog)
        .order_by(
            models.AuditLog.created_at.desc(),
            models.AuditLog.id.desc()
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "count": len(logs),
        "audit_logs": [
            {
                "id": log.id,
                "actor_id": log.actor_id,
                "actor_username": log.actor_username,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "details": log.details,
                "created_at": log.created_at
            }
            for log in logs
        ]
    }

@app.post("/reports/{report_id}/task")
def assign_report_to_unit(
    report_id: int,
    request: ReportTaskingRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "management" or not current_user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Only active Management users can assign reports."
        )

    allowed_instructions = [
        "Process", "Treat", "Peruse", "FNA",
        "Collate", "File", "Update"
    ]

    if request.instruction not in allowed_instructions:
        raise HTTPException(
            status_code=400,
            detail="Invalid tasking instruction."
        )

    report = db.query(models.IntelligenceReport).filter(
        models.IntelligenceReport.id == report_id
    ).first()

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found."
        )

    department = db.query(models.Department).filter(
        models.Department.id == request.department_id,
        models.Department.is_active == True
    ).first()

    if not department:
        raise HTTPException(
            status_code=404,
            detail="Active Unit/Department not found."
        )

    existing_assignment = db.query(models.ReportTasking).filter(
        models.ReportTasking.report_id == report_id,
        models.ReportTasking.is_active == True,
    ).first()
    if existing_assignment:
        raise HTTPException(
            status_code=409,
            detail="This report already has an active departmental assignment. Use the reassign action to transfer access."
        )

    tasking = models.ReportTasking(
        report_id=report_id,
        department_id=department.id,
        assigned_by=current_user.id,
        instruction=request.instruction,
        tasking_note=request.tasking_note,
        is_active=True,
    )

    try:
        db.add(tasking)

        record_audit(
            db,
            current_user,
            "REPORT_ASSIGNED_TO_UNIT",
            "intelligence_report",
            report_id,
            f"Unit ID: {department.id}; "
            f"Instruction: {request.instruction}"
        )

        db.commit()
        db.refresh(tasking)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Report assignment could not be saved."
        )

    return {
        "message": "Report assigned successfully.",
        "tasking_id": tasking.id,
        "report_id": report_id,
        "unit": department.name,
        "instruction": tasking.instruction,
        "assigned_by": current_user.username,
        "assigned_at": tasking.created_at,
    }

@app.get("/reports/{report_id}/tasking-history")
def get_report_tasking_history(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        require_role("management")
    ),
):
    report = db.query(models.IntelligenceReport).filter(
        models.IntelligenceReport.id == report_id
    ).first()

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found."
        )

    taskings = (
        db.query(models.ReportTasking)
        .filter(models.ReportTasking.report_id == report_id)
        .order_by(models.ReportTasking.created_at.desc())
        .all()
    )

    results = []

    for tasking in taskings:
        department = db.query(models.Department).filter(
            models.Department.id == tasking.department_id
        ).first()

        assigning_user = db.query(models.User).filter(
            models.User.id == tasking.assigned_by
        ).first()

        results.append({
            "tasking_id": tasking.id,
            "report_id": tasking.report_id,
            "unit": department.name if department else None,
            "instruction": tasking.instruction,
            "tasking_note": tasking.tasking_note,
            "assigned_by": (
                assigning_user.username if assigning_user else None
            ),
            "is_active": tasking.is_active,
            "assigned_at": tasking.created_at,
        })

    return {
        "report_id": report_id,
        "report_reference": report.report_reference,
        "tasking_count": len(results),
        "tasking_history": results,
    }


@app.post("/reports/{report_id}/reassign")
def reassign_report_to_unit(
    report_id: int,
    request: ReportTaskingRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "management" or not current_user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Only active Management users can reassign reports."
        )

    allowed_instructions = [
        "Process", "Treat", "Peruse", "FNA",
        "Collate", "File", "Update"
    ]

    instruction = request.instruction.strip()

    if instruction not in allowed_instructions:
        raise HTTPException(
            status_code=400,
            detail="Invalid tasking instruction."
        )

    report = db.query(models.IntelligenceReport).filter(
        models.IntelligenceReport.id == report_id
    ).first()

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found."
        )

    department = db.query(models.Department).filter(
        models.Department.id == request.department_id,
        models.Department.is_active == True
    ).first()

    if not department:
        raise HTTPException(
            status_code=404,
            detail="Active Unit/Department not found."
        )

    try:
        active_taskings = (
            db.query(models.ReportTasking)
            .filter(
                models.ReportTasking.report_id == report_id,
                models.ReportTasking.is_active == True
            )
            .all()
        )

        for tasking in active_taskings:
            tasking.is_active = False

        new_tasking = models.ReportTasking(
            report_id=report_id,
            department_id=department.id,
            assigned_by=current_user.id,
            instruction=instruction,
            tasking_note=request.tasking_note,
            is_active=True,
        )

        db.add(new_tasking)

        record_audit(
            db,
            current_user,
            "REPORT_REASSIGNED_TO_UNIT",
            "intelligence_report",
            report_id,
            f"New Unit ID: {department.id}; "
            f"Instruction: {instruction}"
        )

        db.commit()
        db.refresh(new_tasking)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Report reassignment could not be saved."
        )

    return {
        "message": "Report reassigned successfully.",
        "tasking_id": new_tasking.id,
        "report_id": report_id,
        "unit": department.name,
        "instruction": new_tasking.instruction,
        "assigned_by": current_user.username,
        "assigned_at": new_tasking.created_at,
    }



@app.get("/taskings/active")
def get_active_taskings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "management" or not current_user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Only active Management users can view all active taskings."
        )

    taskings = (
        db.query(models.ReportTasking)
        .filter(models.ReportTasking.is_active == True)
        .order_by(models.ReportTasking.created_at.desc())
        .all()
    )

    results = []

    for tasking in taskings:
        report = db.query(models.IntelligenceReport).filter(
            models.IntelligenceReport.id == tasking.report_id
        ).first()

        if not report or report.status in {"approved", "discarded"}:
            continue

        department = db.query(models.Department).filter(
            models.Department.id == tasking.department_id
        ).first()

        assigning_user = db.query(models.User).filter(
            models.User.id == tasking.assigned_by
        ).first()

        results.append({
            "tasking_id": tasking.id,
            "report_id": tasking.report_id,
            "report_reference": (
                report.report_reference if report else None
            ),
            "report_heading": report.heading if report else None,
            "unit": department.name if department else None,
            "instruction": tasking.instruction,
            "tasking_note": tasking.tasking_note,
            "assigned_by": (
                assigning_user.username if assigning_user else None
            ),
            "assigned_at": tasking.created_at,
        })

    return {
        "active_tasking_count": len(results),
        "active_taskings": results,
    }


@app.get("/taskings/my-work")
def get_analyst_taskings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "analyst" or not current_user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Only active Analysts can use this endpoint."
        )

    if not current_user.department_id:
        return {"tasking_count": 0, "assigned_reports": [], "message": "Your Analyst account has not been assigned to a department."}

    taskings = (
        db.query(models.ReportTasking)
        .filter(
            models.ReportTasking.is_active == True,
            models.ReportTasking.department_id == current_user.department_id,
        )
        .order_by(models.ReportTasking.created_at.desc())
        .all()
    )

    results = []

    for tasking in taskings:
        report = db.query(models.IntelligenceReport).filter(
            models.IntelligenceReport.id == tasking.report_id
        ).first()

        department = db.query(models.Department).filter(
            models.Department.id == tasking.department_id
        ).first()

        if not report or report.status in {"approved", "discarded"}:
            continue

        results.append({
            "report_id": report.id,
            "report_reference": report.report_reference,
            "title": report.title,
            "heading": report.heading or report.title,
            "location": report.location,
            "lga": report.lga,
            "unit": department.name if department else None,
            "instruction": tasking.instruction,
            "tasking_note": tasking.tasking_note,
            "assigned_at": tasking.created_at,
            "report_status": report.status,
        })

    return {
        "tasking_count": len(results),
        "assigned_reports": results,
    }


# ---------------------------------------------------------------------------
# AI Intelligence Processing (prototype; human review required)
# ---------------------------------------------------------------------------
class AIReportProcessingRequest(BaseModel):
    raw_text: str = Field(min_length=20, max_length=12000)


@app.post("/ai/process-report")
def process_intelligence_with_ai(
    payload: AIReportProcessingRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Prototype safeguard: only synthetic/declassified material should be used.
    try:
        result = process_raw_report(payload.raw_text, "")
    
    except Exception as exc:
        import traceback
        traceback.print_exc()
        from openai import OpenAIError

        if isinstance(exc, OpenAIError):
            raise HTTPException(
                status_code=502,
                detail=f"AI gateway error: {type(exc).__name__}: {str(exc)}"
            ) from None
        if isinstance(exc, RuntimeError):
            raise HTTPException(status_code=503, detail=str(exc)) from None
        raise HTTPException(
            status_code=500,
            detail=f"AI processing error: {type(exc).__name__}: {str(exc)}"
        ) from None

    record_audit(
        db, current_user, "AI_REPORT_PROCESSED", "ai_processing", None,
        f"Model={result['model']}; "
        f"input_tokens={result['usage']['input_tokens']}; output_tokens={result['usage']['output_tokens']}"
    )
    db.commit()
    return {
        "status": "draft_for_analyst_review",
        "notice": "AI-generated draft. Verify every claim against source material before use.",
        **result,
    }


@app.post("/reports/{report_id}/approve-learning-reference")
def approve_learning_reference(
    report_id: int,
    current_user: models.User = Depends(
        require_permission("APPROVE_LEARNING_REFERENCE")
    ),
    db: Session = Depends(get_db),
):
    report = (
        db.query(models.IntelligenceReport)
        .filter(models.IntelligenceReport.id == report_id)
        .first()
    )

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if not can_access_report(report, current_user, db):
        raise HTTPException(status_code=404, detail="Report not found")

    processed_report = (
        db.query(models.ProcessedReport)
        .filter(
            models.ProcessedReport.intelligence_report_id == report_id
        )
        .order_by(models.ProcessedReport.processed_at.desc())
        .first()
    )

    if not processed_report:
        raise HTTPException(
            status_code=400,
            detail="No processed report exists for this report",
        )

    final_text = "\n\n".join(
        part.strip()
        for part in [
            processed_report.heading or "",
            processed_report.body or "",
            processed_report.comment or "",
        ]
        if part and part.strip()
    )

    if not final_text:
        raise HTTPException(
            status_code=400,
            detail="The processed report has no content to approve",
        )

    existing_reference = (
        db.query(models.LearningReference)
        .filter(
            models.LearningReference.processed_report_id
            == processed_report.id,
            models.LearningReference.is_active.is_(True),
        )
        .first()
    )

    if existing_reference:
        raise HTTPException(
            status_code=409,
            detail="This processed report is already an active learning reference",
        )

    reference = models.LearningReference(
        intelligence_report_id=report_id,
        processed_report_id=processed_report.id,
        report_category=str(
            getattr(report, "report_type", None)
            or getattr(report, "category", None)
            or "Unclassified"
        ),
        approved_final_text=final_text,
        submitted_by=processed_report.processed_by,
        approved_by=current_user.id,
    )

    db.add(reference)
    record_audit(
        db=db,
        actor=current_user,
        action="APPROVE_LEARNING_REFERENCE",
        entity_type="LearningReference",
        entity_id=report_id,
        details=(
            f"Approved processed report {processed_report.id} "
            "as a learning reference."
        ),
    )

    try:
        db.commit()
        db.refresh(reference)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to save learning reference",
        )

    return {
        "message": "Learning reference approved successfully",
        "learning_reference_id": reference.id,
        "report_id": report_id,
        "processed_report_id": processed_report.id,
        "approved_by": current_user.username,
        "approved_at": reference.approved_at,
    }


from pydantic import BaseModel, Field


class CorrectedReportInput(BaseModel):
    heading: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1)
    comment: str = ""


@app.post("/reports/{report_id}/save-correction")
def save_report_correction(
    report_id: int,
    payload: CorrectedReportInput,
    current_user: models.User = Depends(
        require_permission("PROCESS_INTELLIGENCE")
    ),
    db: Session = Depends(get_db),
):
    report = (
        db.query(models.IntelligenceReport)
        .filter(models.IntelligenceReport.id == report_id)
        .first()
    )

    if not report or not can_access_report(report, current_user, db):
        raise HTTPException(status_code=404, detail="Report not found")

    if current_user.role == "analyst":
        active_assignment = (
            db.query(models.ReportTasking)
            .filter(
                models.ReportTasking.report_id == report_id,
                models.ReportTasking.department_id == current_user.department_id,
                models.ReportTasking.is_active == True,
            )
            .first()
        ) if current_user.department_id else None
        if not active_assignment:
            raise HTTPException(status_code=403, detail="This report is not currently assigned to your department.")

    corrected_heading = payload.heading.strip()
    corrected_body = payload.body.strip()
    corrected_comment = payload.comment.strip()

    if not corrected_heading or not corrected_body:
        raise HTTPException(
            status_code=422,
            detail="Heading and body must not be empty",
        )

    corrected = models.ProcessedReport(
        intelligence_report_id=report_id,
        heading=corrected_heading,
        body=corrected_body,
        comment=corrected_comment,
        processed_by=current_user.id,
    )

    db.add(corrected)
    record_audit(
        db=db,
        actor=current_user,
        action="SAVE_REPORT_CORRECTION",
        entity_type="ProcessedReport",
        entity_id=report_id,
        details="Saved a new analyst-corrected report version.",
    )

    try:
        db.commit()
        db.refresh(corrected)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to save corrected report",
        )

    return {
        "message": "Corrected report version saved",
        "report_id": report_id,
        "processed_report_id": corrected.id,
        "saved_by": current_user.username,
        "saved_at": corrected.processed_at,
    }
class ManualLearningReferenceInput(BaseModel):
    report_category: str
    title: str
    approved_final_text: str



@app.post("/learning-references/manual")
def save_manual_learning_reference(
    payload: ManualLearningReferenceInput,
    current_user: models.User = Depends(
        require_permission("PROCESS_INTELLIGENCE")
    ),
    db: Session = Depends(get_db),
):
    title = payload.title.strip()
    final_text = payload.approved_final_text.strip()
    category = payload.report_category.strip()

    if not title or not final_text or not category:
        raise HTTPException(
            status_code=400,
            detail="Title, report category, and final report are required.",
        )

    reference = models.LearningReference(
        intelligence_report_id=None,
        processed_report_id=None,
        report_category=category,
        approved_final_text=final_text,
        submitted_by=current_user.id,
        approved_by=current_user.id,
        review_notes=f"Manual learning reference: {title}",
    )

    try:
        db.add(reference)
        db.commit()
        db.refresh(reference)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to save learning reference. Check the database schema.",
        )

    return {
        "message": "Learning reference saved successfully.",
        "learning_reference_id": reference.id,
        "title": title,
        "report_category": category,
    }


@app.get("/learning-references/manual")
def get_manual_learning_references(
    current_user: models.User = Depends(
        require_permission("PROCESS_INTELLIGENCE")
    ),
    db: Session = Depends(get_db),
):
    references = (
        db.query(models.LearningReference)
        .filter(models.LearningReference.is_active == True)
        .order_by(models.LearningReference.created_at.desc())
        .all()
    )

    return [
        {
            "id": reference.id,
            "title": (
                reference.review_notes.replace(
                    "Manual learning reference: ", "", 1
                )
                if reference.review_notes
                else "Untitled Reference"
            ),
            "report_category": reference.report_category,
            "approved_final_text": reference.approved_final_text,
            "created_at": (
                reference.created_at.isoformat()
                if reference.created_at
                else None
            ),
        }
        for reference in references
    ]

# ---------------------------------------------------------------------------
# DIMS administration and report review workflow extensions
# ---------------------------------------------------------------------------
class AdminUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="operative")
    full_name: str | None = Field(default=None, max_length=150)
    designation: str | None = Field(default=None, max_length=150)
    formation: str | None = Field(default=None, max_length=255)
    department_id: int | None = None

class AdminUserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=150)
    designation: str | None = Field(default=None, max_length=150)
    formation: str | None = Field(default=None, max_length=255)
    department_id: int | None = None

class AdminPasswordReset(BaseModel):
    temporary_password: str = Field(min_length=8, max_length=128)

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

class ReportForwardRequest(BaseModel):
    recipient_id: int
    note: str | None = Field(default=None, max_length=1000)

class ReportDiscardRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


@app.post("/auth/change-password")
def change_own_password(
    payload: ChangePasswordRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not password_hash.verify(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must be different from the temporary password.")
    current_user.hashed_password = password_hash.hash(payload.new_password)
    current_user.must_change_password = False
    record_audit(
        db,
        current_user,
        "USER_PASSWORD_CHANGED",
        "user",
        current_user.id,
        "User changed their password."
    )
    db.commit()
    return {"message": "Password changed successfully. You can now access DIMS."}


def _user_payload(user, db):
    dept = db.query(models.Department).filter(models.Department.id == user.department_id).first() if user.department_id else None
    return {"user_id": user.id, "username": user.username, "role": user.role,
            "full_name": user.full_name, "designation": user.designation,
            "formation": user.formation, "department_id": user.department_id,
            "department": dept.name if dept else None, "is_active": user.is_active,
            "created_at": user.created_at}

@app.post("/admin/users", status_code=201)
def admin_create_user(payload: AdminUserCreate, current_user: models.User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    role = payload.role.strip().lower()
    if role not in {"operative", "analyst", "supervisor", "management", "admin"}:
        raise HTTPException(status_code=400, detail="Invalid system role.")
    if db.query(models.User).filter(models.User.username == payload.username.strip()).first():
        raise HTTPException(status_code=409, detail="Username already exists.")
    if role == "analyst" and not payload.department_id:
        raise HTTPException(status_code=400, detail="Analyst accounts must be assigned to a department.")
    if payload.department_id and not db.query(models.Department).filter(models.Department.id == payload.department_id, models.Department.is_active == True).first():
        raise HTTPException(status_code=400, detail="Selected department is unavailable.")
    user = models.User(username=payload.username.strip(), hashed_password=password_hash.hash(payload.password), role=role,
        full_name=(payload.full_name or "").strip() or None, designation=(payload.designation or "").strip() or None,
        formation=(payload.formation or "").strip() or None, department_id=payload.department_id,
        is_active=True, must_change_password=True)
    db.add(user); db.flush()
    record_audit(db, current_user, "USER_CREATED", "user", user.id, f"Created {role} account {user.username}")
    db.commit(); db.refresh(user)
    return _user_payload(user, db)

@app.patch("/admin/users/{user_id}")
def admin_update_user(user_id: int, payload: AdminUserUpdate, current_user: models.User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404, detail="User not found.")
    if user_id == current_user.id and payload.department_id is not None:
        raise HTTPException(status_code=403, detail="You cannot change your own administrative profile.")
    if payload.department_id is not None:
        if user.role != "analyst": raise HTTPException(status_code=400, detail="Department assignment is for Analyst accounts only.")
        if not db.query(models.Department).filter(models.Department.id == payload.department_id, models.Department.is_active == True).first():
            raise HTTPException(status_code=400, detail="Selected department is unavailable.")
        user.department_id = payload.department_id
    if payload.full_name is not None: user.full_name = payload.full_name.strip() or None
    if payload.designation is not None: user.designation = payload.designation.strip() or None
    if payload.formation is not None: user.formation = payload.formation.strip() or None
    record_audit(db, current_user, "USER_PROFILE_UPDATED", "user", user.id, "Updated user profile details")
    db.commit(); db.refresh(user)
    return _user_payload(user, db)

@app.post("/admin/users/{user_id}/reset-password")
def admin_reset_user_password(
    user_id: int,
    payload: AdminPasswordReset,
    current_user: models.User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="Use the account recovery procedure for your own administrator account.")
    target.hashed_password = password_hash.hash(payload.temporary_password)
    target.must_change_password = True
    record_audit(db, current_user, "USER_PASSWORD_RESET", "user", target.id,
                 f"Administrator reset password for account {target.username}")
    db.commit()
    return {"message": f"Temporary password set for {target.username}. The account holder must change it at next sign-in. Communicate it directly and securely."}


@app.get("/admin/summary")
def admin_summary(current_user: models.User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return {"users": db.query(models.User).count(), "active_users": db.query(models.User).filter(models.User.is_active == True).count(),
            "departments": db.query(models.Department).filter(models.Department.is_active == True).count(),
            "analysts_unassigned": db.query(models.User).filter(models.User.role == "analyst", models.User.department_id == None).count()}

@app.get("/reports/{report_id}/workflow")
def report_workflow(report_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = db.query(models.IntelligenceReport).filter(models.IntelligenceReport.id == report_id).first()
    if not report or not can_access_report(report, current_user, db): raise HTTPException(status_code=404, detail="Report not found.")
    wf = db.query(models.ReportWorkflow).filter_by(report_id=report_id).first()
    history = db.query(models.ReportForwardHistory).filter_by(report_id=report_id).order_by(models.ReportForwardHistory.created_at.asc()).all()
    def person(uid):
        u = db.query(models.User).filter(models.User.id == uid).first()
        return {"user_id": u.id, "username": u.username, "full_name": u.full_name, "designation": u.designation} if u else None
    return {"current_assignee": person(wf.current_assignee_id) if wf and wf.current_assignee_id else None,
            "current_stage": wf.current_stage if wf else "department", "workflow_status": wf.workflow_status if wf else report.status,
            "history": [{"sender": person(h.sender_id), "recipient": person(h.recipient_id), "note": h.note, "created_at": h.created_at} for h in history]}

@app.get("/workflow/pending")
def workflow_pending(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.is_active: raise HTTPException(status_code=403, detail="Inactive account.")
    rows = db.query(models.ReportWorkflow).filter(models.ReportWorkflow.current_assignee_id == current_user.id, models.ReportWorkflow.workflow_status == "in_review").all()
    result = []
    for wf in rows:
        report = db.query(models.IntelligenceReport).filter(models.IntelligenceReport.id == wf.report_id).first()
        if report:
            result.append({"report_id": report.id, "report_reference": report.report_reference, "heading": report.heading or report.title, "status": report.status, "location": report.location, "lga": report.lga, "current_stage": wf.current_stage})
    return {"pending_reports": result, "count": len(result)}

@app.post("/reports/{report_id}/forward")
def forward_report(report_id: int, payload: ReportForwardRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = db.query(models.IntelligenceReport).filter_by(id=report_id).first()
    if not report or not can_access_report(report, current_user, db): raise HTTPException(status_code=404, detail="Report not found.")
    if report.status in {"approved", "discarded"}: raise HTTPException(status_code=409, detail="This report is closed.")
    processed = db.query(models.ProcessedReport).filter_by(intelligence_report_id=report_id).order_by(models.ProcessedReport.id.desc()).first()
    if not processed: raise HTTPException(status_code=400, detail="Save the processed report before forwarding.")
    recipient = db.query(models.User).filter_by(id=payload.recipient_id, is_active=True).first()
    if not recipient or recipient.role not in {"management", "supervisor"}: raise HTTPException(status_code=400, detail="Recipient must be an active Supervisor or Management account.")
    def rank(u):
        d = (u.designation or "").lower()
        if "state director" in d or d.strip() == "sds": return 4
        if "deputy director" in d or d.strip() == "dd": return 3
        if "assistant director" in d or d.strip() == "ad": return 2
        if "supervisor" in d: return 1
        return 0
    wf = db.query(models.ReportWorkflow).filter_by(report_id=report_id).first()
    if current_user.role == "analyst":
        if wf and wf.current_assignee_id != current_user.id:
            raise HTTPException(status_code=403, detail="This report has already been forwarded for management review.")
        if not db.query(models.ReportTasking).filter_by(report_id=report_id, department_id=current_user.department_id, is_active=True).first():
            raise HTTPException(status_code=403, detail="Your department is not assigned to this report.")
        sender_rank = 0
    elif current_user.role in {"management", "supervisor"}:
        if not wf or wf.current_assignee_id != current_user.id: raise HTTPException(status_code=403, detail="Only the current reviewer may forward this report.")
        sender_rank = rank(current_user)
    else: raise HTTPException(status_code=403, detail="This account cannot forward reports.")
    recipient_rank = rank(recipient)
    if recipient_rank <= sender_rank: raise HTTPException(status_code=400, detail="Reports can only be forwarded to a higher management designation.")
    if recipient_rank == 0: raise HTTPException(status_code=400, detail="Recipient designation is not configured as a review level.")
    if not wf:
        wf = models.ReportWorkflow(report_id=report_id, current_assignee_id=recipient.id, current_stage=recipient.designation or "Management", workflow_status="in_review")
        db.add(wf)
    else:
        wf.current_assignee_id = recipient.id; wf.current_stage = recipient.designation or "Management"
    db.add(models.ReportForwardHistory(report_id=report_id, sender_id=current_user.id, recipient_id=recipient.id, note=payload.note))
    db.add(models.Notification(user_id=recipient.id, report_id=report_id, title="Report forwarded for review", message=f"{report.report_reference} has been forwarded to you."))
    record_audit(db, current_user, "REPORT_FORWARDED", "intelligence_report", report_id, f"Forwarded to user ID {recipient.id}")
    db.commit()
    return {"message": "Report forwarded successfully.", "recipient": recipient.username, "designation": recipient.designation}

@app.get("/workflow/reviewed")
def workflow_reviewed(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.is_active or current_user.role not in {"supervisor", "management"}:
        raise HTTPException(status_code=403, detail="Only reviewing officers can view previously reviewed reports.")
    rows = (
        db.query(models.ReportForwardHistory.report_id)
        .filter(models.ReportForwardHistory.sender_id == current_user.id)
        .distinct()
        .all()
    )
    reviewed = []
    for (report_id,) in rows:
        report = db.query(models.IntelligenceReport).filter_by(id=report_id).first()
        workflow = db.query(models.ReportWorkflow).filter_by(report_id=report_id).first()
        if not report or not can_access_report(report, current_user, db):
            continue
        assignee = db.query(models.User).filter_by(id=workflow.current_assignee_id).first() if workflow and workflow.current_assignee_id else None
        reviewed.append({
            "report_id": report.id,
            "report_reference": report.report_reference,
            "heading": report.heading or report.title,
            "status": report.status,
            "location": report.location,
            "lga": report.lga,
            "current_stage": workflow.current_stage if workflow else report.status,
            "current_assignee": (assignee.full_name or assignee.username) if assignee else None,
            "workflow_status": workflow.workflow_status if workflow else report.status,
        })
    reviewed.sort(key=lambda item: item["report_reference"], reverse=True)
    return {"reviewed_reports": reviewed, "count": len(reviewed)}


@app.get("/notifications")
def list_notifications(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(models.Notification).filter_by(user_id=current_user.id).order_by(models.Notification.created_at.desc()).limit(100).all()
    return {"notifications": [{"id": n.id, "report_id": n.report_id, "title": n.title, "message": n.message, "is_read": n.is_read, "created_at": n.created_at} for n in items], "unread_count": sum(1 for n in items if not n.is_read)}

@app.patch("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(models.Notification).filter_by(id=notification_id, user_id=current_user.id).first()
    if not item: raise HTTPException(status_code=404, detail="Notification not found.")
    item.is_read = True; db.commit(); return {"message": "Notification marked as read."}

@app.post("/reports/{report_id}/discard")
def discard_report(report_id: int, payload: ReportDiscardRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = db.query(models.IntelligenceReport).filter_by(id=report_id).first()
    if not report: raise HTTPException(status_code=404, detail="Report not found.")
    d = (current_user.designation or "").lower()
    if current_user.role != "management" or not ("state director" in d or d.strip() == "sds"):
        raise HTTPException(status_code=403, detail="Only the State Director designation can discard reports in this release.")
    wf = db.query(models.ReportWorkflow).filter_by(report_id=report_id).first()
    if not wf or wf.current_assignee_id != current_user.id: raise HTTPException(status_code=403, detail="This report is not currently assigned to you.")
    report.status = "discarded"; wf.workflow_status = "discarded"
    db.query(models.ReportTasking).filter_by(report_id=report.id, is_active=True).update({"is_active": False}, synchronize_session=False)
    record_audit(db, current_user, "REPORT_DISCARDED", "intelligence_report", report_id, payload.reason)
    db.commit(); return {"message": "Report discarded.", "status": report.status}

@app.get("/workflow/reviewers")
def workflow_reviewers(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in {"analyst", "management", "supervisor"}: raise HTTPException(status_code=403, detail="Not authorised.")
    users = db.query(models.User).filter(models.User.role.in_(["management", "supervisor"]), models.User.is_active == True).all()
    def rank(u):
        d=(u.designation or "").lower()
        if "state director" in d or d.strip()=="sds": return 4
        if "deputy director" in d or d.strip()=="dd": return 3
        if "assistant director" in d or d.strip()=="ad": return 2
        if "supervisor" in d: return 1
        return 0
    own=0 if current_user.role=="analyst" else rank(current_user)
    return [{"user_id":u.id,"username":u.username,"full_name":u.full_name,"designation":u.designation,"formation":u.formation} for u in users if rank(u)>own]

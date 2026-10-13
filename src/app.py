"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

ADMIN_SESSION_COOKIE = "mergington_organizer_session"
ADMIN_SESSION_SECONDS = 8 * 60 * 60
ADMIN_AUDIT_LOG = Path(os.getenv("ADMIN_AUDIT_LOG", "/tmp/mergington-admin-audit.jsonl"))


class AdminCredentials(BaseModel):
    username: str
    password: str


class ActivityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(max_length=500)
    schedule: str = Field(min_length=1, max_length=160)
    max_participants: int = Field(gt=0, le=500)


class ActivityUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=500)
    schedule: str | None = Field(default=None, min_length=1, max_length=160)
    max_participants: int | None = Field(default=None, gt=0, le=500)
    is_open: bool | None = None


def _password_matches(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, expected_text = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        if iterations < 100_000 or iterations > 2_000_000:
            return False
        salt = bytes.fromhex(salt_text)
        expected = bytes.fromhex(expected_text)
        if len(salt) < 16 or len(expected) != hashlib.sha256().digest_size:
            return False
    except (ValueError, TypeError):
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return hmac.compare_digest(actual, expected)


def _create_admin_session(username: str) -> str:
    expires_at = int(datetime.now(timezone.utc).timestamp()) + ADMIN_SESSION_SECONDS
    payload = f"{username}:{expires_at}"
    secret = os.getenv("SESSION_SECRET", "").encode()
    signature = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def _get_admin_user(request: Request) -> str | None:
    token = request.cookies.get(ADMIN_SESSION_COOKIE, "")
    username, separator, remainder = token.partition(":")
    expires_text, separator_two, signature = remainder.partition(":")
    secret = os.getenv("SESSION_SECRET", "").encode()
    configured_username = os.getenv("ADMIN_USERNAME", "").strip()
    if (
        not all((separator, separator_two, configured_username))
        or len(secret) < 32
        or ":" in configured_username
    ):
        return None
    if not hmac.compare_digest(username, configured_username):
        return None
    try:
        expires_at = int(expires_text)
    except ValueError:
        return None
    if expires_at <= int(datetime.now(timezone.utc).timestamp()):
        return None

    payload = f"{username}:{expires_at}"
    expected = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    return username if hmac.compare_digest(signature, expected) else None


def require_admin(request: Request) -> str:
    username = _get_admin_user(request)
    if not username:
        raise HTTPException(status_code=401, detail="Organizer sign-in required")
    return username


def _record_admin_action(username: str, action: str, activity: str) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "username": username,
        "action": action,
        "activity": activity,
    }
    ADMIN_AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with ADMIN_AUDIT_LOG.open("a", encoding="utf-8") as audit_file:
        audit_file.write(json.dumps(entry) + "\n")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


@app.post("/admin/login")
def admin_login(credentials: AdminCredentials, response: Response):
    username = os.getenv("ADMIN_USERNAME", "").strip()
    password_hash = os.getenv("ADMIN_PASSWORD_HASH", "")
    session_secret = os.getenv("SESSION_SECRET", "")
    if not username or not password_hash or len(session_secret) < 32 or ":" in username:
        raise HTTPException(status_code=503, detail="Organizer sign-in is not configured")
    if not hmac.compare_digest(credentials.username, username) or not _password_matches(
        credentials.password, password_hash
    ):
        raise HTTPException(status_code=401, detail="Invalid organizer credentials")

    secure_cookie = os.getenv("COOKIE_SECURE", "").lower() in {"1", "true", "yes"}
    response.set_cookie(
        ADMIN_SESSION_COOKIE,
        _create_admin_session(username),
        max_age=ADMIN_SESSION_SECONDS,
        httponly=True,
        secure=secure_cookie,
        samesite="strict",
        path="/",
    )
    return {"message": "Organizer signed in"}


@app.post("/admin/logout")
def admin_logout(response: Response):
    response.delete_cookie(ADMIN_SESSION_COOKIE, path="/")
    return {"message": "Organizer signed out"}


@app.get("/admin/me")
def admin_status(request: Request):
    return {"authenticated": _get_admin_user(request) is not None}


@app.get("/admin/audit-log")
def get_admin_audit_log(admin_username: str = Depends(require_admin)):
    if not ADMIN_AUDIT_LOG.exists():
        return []
    with ADMIN_AUDIT_LOG.open("r", encoding="utf-8") as audit_file:
        entries = []
        for line in audit_file:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return list(reversed(entries[-100:]))


@app.post("/admin/activities", status_code=201)
def create_activity(
    activity_data: ActivityCreate,
    admin_username: str = Depends(require_admin),
):
    name = activity_data.name.strip()
    if not name or "/" in name or "\\" in name:
        raise HTTPException(status_code=422, detail="Activity name is blank or contains a path separator")
    if name in activities:
        raise HTTPException(status_code=409, detail="Activity already exists")

    activities[name] = {
        "description": activity_data.description.strip(),
        "schedule": activity_data.schedule.strip(),
        "max_participants": activity_data.max_participants,
        "participants": [],
        "is_open": True,
    }
    _record_admin_action(admin_username, "created", name)
    return {"message": f"Created {name}"}


@app.patch("/admin/activities/{activity_name}")
def update_activity(
    activity_name: str,
    updates: ActivityUpdate,
    admin_username: str = Depends(require_admin),
):
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    activity = activities[activity_name]
    changes = {
        key: value
        for key, value in updates.model_dump(exclude_unset=True).items()
        if value is not None
    }
    if not changes:
        raise HTTPException(status_code=400, detail="No activity changes provided")
    if "max_participants" in changes and changes["max_participants"] < len(
        activity["participants"]
    ):
        raise HTTPException(
            status_code=409,
            detail="Capacity cannot be lower than the current participant count",
        )
    for key in ("description", "schedule"):
        if key in changes:
            changes[key] = changes[key].strip()
    if "schedule" in changes and not changes["schedule"]:
        raise HTTPException(status_code=422, detail="Schedule cannot be blank")
    activity.update(changes)
    _record_admin_action(admin_username, "updated", activity_name)
    return {"message": f"Updated {activity_name}"}


@app.delete("/admin/activities/{activity_name}/participants/{email}")
def admin_remove_participant(
    activity_name: str,
    email: str,
    admin_username: str = Depends(require_admin),
):
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")
    participants = activities[activity_name]["participants"]
    if email not in participants:
        raise HTTPException(status_code=404, detail="Participant not found")
    participants.remove(email)
    _record_admin_action(admin_username, "removed participant", activity_name)
    return {"message": f"Removed {email} from {activity_name}"}


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    if not activity.get("is_open", True):
        raise HTTPException(status_code=400, detail="Activity is closed for signups")

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    if len(activity["participants"]) >= activity["max_participants"]:
        raise HTTPException(status_code=400, detail="Activity is full")

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Reject unauthenticated unregister requests; organizers use the admin route."""
    raise HTTPException(
        status_code=401,
        detail="Organizer sign-in is required to unregister a participant",
    )

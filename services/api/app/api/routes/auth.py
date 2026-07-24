from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.config import settings
from app.core.database import Database, get_db
from app.core.rate_limit import enforce_auth_rate_limit
from app.core.security import create_access_token, hash_password, verify_password
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from app.services.workspace import (
    create_workspace_for_user,
    get_workspace_for_user,
    new_id,
    now_iso,
    serialize_user,
    serialize_workspace,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise HTTPException(status_code=422, detail="邮箱格式不正确")
    return normalized


@router.post("/register", response_model=AuthResponse)
def register(
    payload: RegisterRequest,
    request: Request,
    conn: Database = Depends(get_db),
):
    enforce_auth_rate_limit(
        request,
        conn,
        kind="register",
        limit=settings.registration_rate_limit,
        window_seconds=settings.registration_rate_window_seconds,
    )
    email = normalize_email(payload.email)
    exists = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if exists is not None:
        raise HTTPException(status_code=409, detail="这个邮箱已经注册")

    if conn.dialect == "postgres":
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtext(?))",
            ("agentpulse:registration-capacity",),
        )
    user_count = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
    if settings.registration_max_users > 0 and user_count >= settings.registration_max_users:
        raise HTTPException(status_code=503, detail="内测名额已满")

    user_id = new_id("user")
    conn.execute(
        """
        INSERT INTO users (id, email, password_hash, display_name, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user_id,
            email,
            hash_password(payload.password),
            payload.display_name,
            now_iso(),
        ),
    )
    workspace = create_workspace_for_user(conn, user_id, payload.workspace_name)
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return AuthResponse(
        access_token=create_access_token(user_id),
        user=serialize_user(user),
        workspace=serialize_workspace(workspace),
    )


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    request: Request,
    conn: Database = Depends(get_db),
):
    enforce_auth_rate_limit(
        request,
        conn,
        kind="login",
        limit=settings.login_rate_limit,
        window_seconds=settings.login_rate_window_seconds,
    )
    email = normalize_email(payload.email)
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="邮箱或密码不正确")

    workspace = get_workspace_for_user(conn, user["id"])
    if workspace is None:
        workspace = create_workspace_for_user(conn, user["id"], "我的一人公司")
    return AuthResponse(
        access_token=create_access_token(user["id"]),
        user=serialize_user(user),
        workspace=serialize_workspace(workspace),
    )

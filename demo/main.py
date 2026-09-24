"""
GSIS Gabay AI Executive Demo — FastAPI Application Server
=========================================================
Serves:
  - High-Fidelity Official GSIS Website (`gsis.gov.ph`) + GSIS Touch Mobile Simulator UI (`/`)
  - Phase 1 & Phase 2 Multi-Agent Chat API (`POST /api/chat`)
  - Identity-Bound Mock Authentication + Registration + 25-User Quota Cap (`POST /api/auth/*`)
  - Mock MCP Server Tool Registry & Live Record Inspector (`GET /mcp/v1/tools`, `GET /api/member/records`)
"""

import os
import time
import uuid
import hmac
import json
import base64
import hashlib
import random
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.db_adapter import init_database, get_connection
from backend.seeder_engine import (
    MAX_MOCK_USERS,
    DemoQuotaExceededError,
    get_custom_mock_user_count,
    seed_preseeded_personas,
    register_custom_mock_member,
)
from backend.mcp_server import get_full_member_bundle, MCP_TOOLS_MANIFEST
from backend.multi_agent import run_multi_agent_turn


JWT_SECRET = os.getenv("GSIS_DEMO_JWT_SECRET", "gsis-gabay-ai-executive-demo-2026-secret-key")
OTP_STORE: Dict[str, Dict[str, Any]] = {}


def create_jwt(payload: Dict[str, Any]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signing_input = f"{h_b64}.{p_b64}".encode()
    sig = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    s_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    return f"{h_b64}.{p_b64}.{s_b64}"


def verify_jwt(token: str) -> Optional[Dict[str, Any]]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        signing_input = f"{parts[0]}.{parts[1]}".encode()
        expected_sig = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
        expected_b64 = base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")
        if not hmac.compare_digest(parts[2], expected_b64):
            return None
        pad = "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + pad).decode())
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def get_authenticated_bp_from_header(authorization: Optional[str]) -> Optional[str]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.replace("Bearer ", "").strip()
    claims = verify_jwt(token)
    if not claims or not claims.get("mfa_verified"):
        return None
    return claims.get("bp_number")


app = FastAPI(
    title="GSIS Gabay AI — Omnichannel Multi-Agent Executive Demo",
    description="STRICTLY DEMO ONLY: Synthetic Mock Data Architecture for GSIS Omnichannel AI Chatbot (Phase 1 & Phase 2)",
    version="1.2.0-DEMO",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_database()
    seed_preseeded_personas()
    import threading
    from backend.model_armor import sync_gcp_model_armor_and_dlp_templates
    threading.Thread(target=sync_gcp_model_armor_and_dlp_templates, daemon=True).start()


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterMockRequest(BaseModel):
    email: str
    username: str
    password: str
    full_name: str
    birth_date: str
    gender: str = "Female"
    civil_status: str = "Married"
    mobile_number: str = "0917-555-0199"
    agency_name: str = "Department of Education (DepEd)"
    basic_monthly_salary: Optional[float] = None


class VerifyOtpRequest(BaseModel):
    otp_session_id: str
    otp_code: str


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    channel: str = "gwaps_web"


@app.get("/api/status")
def api_status():
    custom_count = get_custom_mock_user_count()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT bp_number, username, full_name, age, civil_status, agency_code,
               position_title, basic_monthly_salary, total_ppp_years, is_preseeded
        FROM gsis_members
        ORDER BY is_preseeded DESC, created_at DESC
        """
    )
    members = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT COUNT(*) as cnt FROM gsis_faq_documents")
    faq_count = int(cur.fetchone()["cnt"])
    conn.close()

    return {
        "status": "ONLINE",
        "demo_notice": "STRICTLY FOR EXECUTIVE DEMO & EVALUATION PURPOSES ONLY — 100% SYNTHETIC MOCK DATA",
        "gcp_project": os.getenv("GOOGLE_CLOUD_PROJECT", "markea-testbed-dev"),
        "gcp_region": os.getenv("GOOGLE_CLOUD_REGION", "asia-southeast1"),
        "models": {
            "fast_tier": "gemini-3.7-flash",
            "reasoning_tier": "gemini-3.1-pro",
            "security_shield": "Google Cloud Model Armor (gsis-gabay-armor-v1)",
        },
        "quota": {
            "custom_mock_users_count": custom_count,
            "max_custom_mock_users": MAX_MOCK_USERS,
            "remaining_slots": max(0, MAX_MOCK_USERS - custom_count),
            "quota_reached": custom_count >= MAX_MOCK_USERS,
        },
        "faq_corpus_documents": faq_count,
        "members": members,
        "mcp_tools": MCP_TOOLS_MANIFEST,
    }


@app.post("/api/auth/login")
def api_login(req: LoginRequest):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT bp_number, username, password_hash, full_name, email, mobile_masked,
               agency_name, position_title
        FROM gsis_members
        WHERE LOWER(username) = LOWER(?)
        """,
        (req.username.strip(),),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid username or password. Try pre-seeded user 'maria.santos' with password 'gsis2026'.")

    member = dict(row)
    pw_hash = hashlib.sha256(req.password.encode("utf-8")).hexdigest()
    if pw_hash != member["password_hash"]:
        raise HTTPException(status_code=401, detail="Invalid password. (Pre-seeded personas use password: gsis2026)")

    otp_code = f"{random.randint(100000, 999999)}"
    otp_session_id = f"otp-{uuid.uuid4().hex[:12]}"
    OTP_STORE[otp_session_id] = {
        "bp_number": member["bp_number"],
        "username": member["username"],
        "full_name": member["full_name"],
        "otp_code": otp_code,
        "expires_at": time.time() + 600,
    }

    return {
        "status": "OTP_REQUIRED",
        "otp_session_id": otp_session_id,
        "simulated_otp_code": otp_code,
        "mobile_masked": member["mobile_masked"],
        "member_preview": {
            "bp_number": member["bp_number"],
            "username": member["username"],
            "full_name": member["full_name"],
            "agency_name": member["agency_name"],
            "position_title": member["position_title"],
        },
        "message": f"Simulated 6-digit OTP sent to {member['mobile_masked']} and {member['email']}.",
    }


@app.post("/api/auth/register-mock")
def api_register_mock(req: RegisterMockRequest):
    try:
        result = register_custom_mock_member(
            email=req.email,
            username=req.username,
            password=req.password,
            full_name=req.full_name,
            birth_date=req.birth_date,
            gender=req.gender,
            civil_status=req.civil_status,
            mobile_number=req.mobile_number,
            agency_name=req.agency_name,
            basic_monthly_salary=req.basic_monthly_salary,
        )
    except DemoQuotaExceededError as qe:
        return JSONResponse(
            status_code=429,
            content={
                "error_code": qe.code,
                "message": qe.message,
                "current_count": qe.current_count,
                "max_allowed": qe.max_allowed,
                "preseeded_accounts": [
                    {"username": "maria.santos", "password": "gsis2026", "persona": "Active Teacher III (DepEd)"},
                    {"username": "juan.delacruz", "password": "gsis2026", "persona": "Retiring Engineer IV (DPWH, Age 60)"},
                    {"username": "rosa.reyes", "password": "gsis2026", "persona": "Old-Age Pensioner (DOF, Age 67)"},
                ],
            },
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    otp_code = f"{random.randint(100000, 999999)}"
    otp_session_id = f"otp-{uuid.uuid4().hex[:12]}"
    OTP_STORE[otp_session_id] = {
        "bp_number": result["bp_number"],
        "username": result["username"],
        "full_name": result["full_name"],
        "otp_code": otp_code,
        "expires_at": time.time() + 600,
    }

    return {
        "status": "REGISTERED_OTP_REQUIRED",
        "otp_session_id": otp_session_id,
        "simulated_otp_code": otp_code,
        "seeded_member": result,
        "message": (
            f"Custom Mock Member '{result['full_name']}' (BP {result['bp_number']}) seeded across all 5 GSIS tables! "
            f"Quota: {result['custom_mock_users_count']} / {result['max_custom_mock_users']}. Verify the 6-digit OTP to complete login."
        ),
    }


@app.post("/api/auth/verify-otp")
def api_verify_otp(req: VerifyOtpRequest):
    session = OTP_STORE.get(req.otp_session_id)
    if not session:
        raise HTTPException(status_code=400, detail="OTP session expired or invalid. Please log in again.")
    if req.otp_code.strip() != session["otp_code"]:
        raise HTTPException(status_code=401, detail=f"Invalid 6-digit OTP code. Expected simulated code: {session['otp_code']}")

    bp_number = session["bp_number"]
    claims = {
        "sub": session["username"],
        "bp_number": bp_number,
        "full_name": session["full_name"],
        "mfa_verified": True,
        "iat": int(time.time()),
        "exp": int(time.time()) + 14400,
    }
    token = create_jwt(claims)
    bundle = get_full_member_bundle(bp_number)
    return {
        "status": "AUTHENTICATED",
        "access_token": token,
        "claims": claims,
        "member_bundle": bundle,
    }


@app.get("/api/member/records")
def api_member_records(authorization: Optional[str] = Header(default=None)):
    bp = get_authenticated_bp_from_header(authorization)
    if not bp:
        raise HTTPException(status_code=401, detail="Unauthorized: Valid MFA-verified JWT required.")
    return get_full_member_bundle(bp)


@app.get("/mcp/v1/tools")
def api_mcp_tools():
    return {
        "server": "gsis-gabay-mock-mcp-server-v1",
        "identity_binding": "JWT_SERVER_SIDE_CLAIM_ONLY (Zero Natural Language BP Acceptance)",
        "tools": MCP_TOOLS_MANIFEST,
    }


@app.post("/api/chat")
def api_chat(req: ChatRequest, authorization: Optional[str] = Header(default=None)):
    authenticated_bp = get_authenticated_bp_from_header(authorization)
    result = run_multi_agent_turn(
        prompt=req.prompt,
        authenticated_bp=authenticated_bp,
        channel=req.channel,
    )
    return result


STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return index_file.read_text(encoding="utf-8")
    return HTMLResponse("<h1>GSIS Gabay AI Demo Server Running</h1>")

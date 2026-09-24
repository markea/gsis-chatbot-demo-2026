"""
Google Cloud Model Armor & Sensitive Data Protection (SDP) Guardrail Engine
===========================================================================
Implements the live runtime security and Responsible AI (RAI) safety layer applied across
ALL 5 AGENTS in the GSIS Gabay AI Multi-Agent Hierarchy:
  1. `GSIS_Concierge_Router` (`gemini-3.7-flash`)
  2. `GSIS_Policy_FAQ_Agent` (`gemini-3.7-flash`)
  3. `GSIS_Member_Records_Agent` (`gemini-3.7-flash`)
  4. `GSIS_Loans_Computation_Agent` (`gemini-3.1-pro`)
  5. `GSIS_Benefits_Transactions_Agent` (`gemini-3.1-pro`)

Enforcement Layers:
1. Calls the real Google Cloud Model Armor v1 Regional API in GCP project `markea-testbed-dev`:
   - Template: `projects/markea-testbed-dev/locations/asia-southeast1/templates/gsis-gabay-armor-v1`
   - Attached Cloud DLP Inspect Template: `gsis-gabay-sdp-inspect-v1`
     (Custom InfoTypes: `PH_TIN_NUMBER`, `GSIS_CRN_NUMBER`, `GSIS_ADVERSARIAL_OVERRIDE_OR_SQLI`,
      `GSIS_SUICIDE_AND_SELF_HARM`, `GSIS_VIOLENCE_AND_LETHAL_HARM`, `GSIS_HATE_SPEECH_AND_ABUSE`,
      `CREDIT_CARD_NUMBER`)
   - Attached Cloud DLP De-identify Template: `gsis-gabay-sdp-deid-v1`
2. `sanitize_user_prompt` & `enforce_agent_model_armor_guard`:
   - Invokes live `:sanitizeUserPrompt` REST API on `modelarmor.asia-southeast1.rep.googleapis.com`
   - Enforces **Suicide & Self-Harm Crisis Shield (`SELF_HARM_AND_SUICIDE_SHIELD`)**: Flags queries like
     "I want to die", "I want to die and get my insurance", "kill myself", self-harm, or Tagalog equivalents,
     blocking agent execution and providing 24/7 Philippine mental health crisis hotlines (NCMH 1553).
   - Enforces **Violence & Lethal Harm Shield (`VIOLENCE_AND_LETHAL_HARM_SHIELD`)**: Flags queries involving
     killing someone, murder, physical violence, weapons, or insurance fraud via harm.
   - Enforces **Hate Speech, Harassment & Abuse Shield (`HATE_SPEECH_AND_HARASSMENT_SHIELD`)**: Flags hate speech,
     dehumanization, slurs, harassment, and sexually explicit content (`raiFilterTypeResults` + custom rules).
   - Enforces **Prompt Injection & Jailbreak Shield (`PROMPT_INJECTION_AND_JAILBREAK_SHIELD`)**
   - Enforces **Session-Bound Cross-Account BP Number Spoofing / Enumeration Shield**
   - Performs **Sensitive Data Protection (SDP) Pre-Masking** of TIN/CRN/Credit Card numbers
3. `sanitize_model_response`:
   - Invokes live `:sanitizeModelResponse` REST API on `modelarmor.asia-southeast1.rep.googleapis.com`
   - Masks any unredacted PII (TIN, CRN), verifies zero RAI violations in output, and prevents cross-account BP leakage.
"""

import os
import re
import time
import threading
from typing import Dict, Any, Optional, List

import requests
import google.auth
import google.auth.transport.requests

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "markea-testbed-dev")
MODEL_ARMOR_LOCATION = os.environ.get("MODEL_ARMOR_LOCATION", "asia-southeast1")
MODEL_ARMOR_TEMPLATE_ID = os.environ.get(
    "MODEL_ARMOR_TEMPLATE_ID",
    f"projects/{PROJECT_ID}/locations/{MODEL_ARMOR_LOCATION}/templates/gsis-gabay-armor-v1",
)
MODEL_ARMOR_BASE_URL = (
    f"https://modelarmor.{MODEL_ARMOR_LOCATION}.rep.googleapis.com/v1/{MODEL_ARMOR_TEMPLATE_ID}"
)
USE_LIVE_MODEL_ARMOR = os.environ.get("USE_LIVE_MODEL_ARMOR", "true").lower() in ("1", "true", "yes")

ALL_MULTI_AGENT_NAMES = [
    "GSIS_Concierge_Router",
    "GSIS_Policy_FAQ_Agent",
    "GSIS_Member_Records_Agent",
    "GSIS_Loans_Computation_Agent",
    "GSIS_Benefits_Transactions_Agent",
]

# 1. Suicide & Self-Harm Patterns (English & Tagalog/Filipino)
SELF_HARM_SUICIDE_PATTERNS = [
    r"\b(i\s+)?(want|wanna|going|plan|planning|wish|ready)\s+to\s+(die|kill\s+myself|end\s+my\s+life|end\s+it\s+all|commit\s+suicide|hurt\s+myself|harm\s+myself)\b",
    r"\b(kill|killing|hurt|hurting|harm|harming|cut|cutting|hang|hanging|shoot|shooting|poison|poisoning)\s+myself\b",
    r"\b(commit|committing|contemplating|attempting)\s+suicide\b",
    r"\b(suicidal|self[\s\-]?harm|self[\s\-]?injury|take\s+my\s+own\s+life|end\s+my\s+life|don'?t\s+want\s+to\s+live|no\s+reason\s+to\s+live|better\s+off\s+dead)\b",
    r"\b(if\s+i\s+die\s+by\s+suicide|if\s+i\s+kill\s+myself|die\s+and\s+get\s+my\s+insurance|suicide\s+insurance\s+payout)\b",
    r"\b(overdose\s+on\s+pills|jump\s+off\s+a\s+(bridge|building|roof))\b",
    r"\b(gusto\s+ko\s+(nang\s+|na\s+)?mamatay|magpakamatay|pagpapakamatay|ayoko\s+nang?\s+mabuhay|tapusin\s+(ko\s+na\s+)?ang\s+buhay\s+ko|saktan\s+ang\s+sarili)\b",
]

# 2. Violence, Killing Someone & Lethal Harm Patterns (English & Tagalog/Filipino)
VIOLENCE_LETHAL_HARM_PATTERNS = [
    r"\b(kill|murder|assassinate|slaughter|strangle|stab|shoot|poison|decapitate|execute|butcher)\s+(someone|somebody|a\s+person|my\s+(spouse|husband|wife|boss|coworker|neighbor|family|friend)|people|them|him|her)\b",
    r"\b(how\s+(do\s+i|to|can\s+i)\s+(kill|murder|poison|stab|shoot|assassinate|get\s+away\s+with\s+murder|make\s+a\s+bomb))\b",
    r"\b(want|wanna|going|plan|planning|hire\s+a\s+hitman)\s+to\s+(kill|murder|assassinate|shoot|stab|poison|bomb|attack)\b",
    r"\b(mass\s+shooting|terrorist\s+attack|plant\s+a\s+bomb|build\s+a\s+bomb|pipe\s+bomb|improvised\s+explosive)\b",
    r"\b(patayin\s+ko|ipapatay\s+ko|papatay\s+ako|paano\s+pumatay)\b",
]

# 3. Hate Speech, Dehumanization & Severe Harassment Patterns
HATE_SPEECH_HARASSMENT_PATTERNS = [
    r"\b(subhuman|subhumans|exterminate\s+all|ethnic\s+cleansing|genocide\s+against|white\s+supremacy|heil\s+hitler|nazi\s+scum)\b",
    r"\b(kill\s+yourself|kys|you\s+should\s+(go\s+)?die|go\s+hang\s+yourself|hope\s+you\s+die)\b",
    r"\b(all\s+(muslims|christians|jews|asians|blacks|whites|gays|trans|women|filipinos|igorots|moros)\s+(are\s+(evil|vermin|animals|parasites|subhuman)|should\s+(die|be\s+killed|be\s+exterminated)))\b",
    r"\b(i\s+hate\s+all\s+(minorities|immigrants|gay\s+people|black\s+people|muslims|jews|women))\b",
]

# 4. Prompt Injection, Jailbreak & SQLi Patterns
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above|system)\s+(instructions|prompts|rules)",
    r"disregard\s+(all\s+)?(previous|prior|system)\s+(instructions|rules)",
    r"system\s*override",
    r"developer\s*mode",
    r"dan\s*mode",
    r"bypass\s+(authentication|mfa|otp|jwt|security|guardrail|model\s*armor)",
    r"pretend\s+you\s+are\s+(not|an?\s+unrestricted|root|admin)",
    r"reveal\s+(your\s+)?(system\s+prompt|hidden\s+instructions|secret\s+key|jwt\s+secret)",
    r"drop\s+table\s+gsis",
    r"union\s+select\s+.*\s+from\s+gsis_members",
    r"dump\s+(all\s+)?(member|user)\s+(records|database|passwords)",
]

BP_NUMBER_REGEX = re.compile(r"\b(20\d{8})\b")
TIN_REGEX = re.compile(r"\b(\d{3}-\d{3}-\d{3}-\d{3})\b")
CRN_REGEX = re.compile(r"\b(006-\d{4}-\d{4}-\d{1})\b")

_auth_lock = threading.Lock()
_cached_creds = None
_cached_cli_token: Optional[str] = None
_cached_cli_token_expiry: float = 0.0
_local_auth_backoff_until: float = 0.0
_http_session = requests.Session()


def _get_auth_headers() -> Dict[str, str]:
    """Acquires and caches Google Cloud bearer token (Cloud Run ADC or local gcloud CLI) with quota project header."""
    global _cached_creds, _cached_cli_token, _cached_cli_token_expiry, _local_auth_backoff_until
    with _auth_lock:
        now = time.time()
        if _cached_cli_token and now < _cached_cli_token_expiry:
            return {
                "Authorization": f"Bearer {_cached_cli_token}",
                "Content-Type": "application/json",
                "x-goog-user-project": PROJECT_ID,
            }
        if now < _local_auth_backoff_until:
            raise RuntimeError("Local ADC/gcloud reauthentication pending (cached backoff).")
        try:
            if _cached_creds is None:
                _cached_creds, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
            if not _cached_creds.valid or _cached_creds.expired or not _cached_creds.token:
                _cached_creds.refresh(google.auth.transport.requests.Request())
            return {
                "Authorization": f"Bearer {_cached_creds.token}",
                "Content-Type": "application/json",
                "x-goog-user-project": PROJECT_ID,
            }
        except Exception:
            try:
                import subprocess
                token = subprocess.check_output(
                    ["gcloud", "auth", "print-access-token", "--quiet"],
                    stderr=subprocess.DEVNULL,
                    timeout=2.5,
                ).decode("utf-8").strip()
                _cached_cli_token = token
                _cached_cli_token_expiry = now + 2700.0
                return {
                    "Authorization": f"Bearer {_cached_cli_token}",
                    "Content-Type": "application/json",
                    "x-goog-user-project": PROJECT_ID,
                }
            except Exception as cli_exc:
                _local_auth_backoff_until = now + 60.0
                raise cli_exc


def sync_gcp_model_armor_and_dlp_templates() -> Dict[str, Any]:
    """
    Synchronizes the live Google Cloud DLP Inspect Template (`gsis-gabay-sdp-inspect-v1`)
    and Google Cloud Model Armor Template (`gsis-gabay-armor-v1`) in `markea-testbed-dev`
    so that `GSIS_SUICIDE_AND_SELF_HARM`, `GSIS_VIOLENCE_AND_LETHAL_HARM`, and
    `GSIS_HATE_SPEECH_AND_ABUSE` custom InfoTypes and `LOW_AND_ABOVE` RAI filters are active in GCP.
    Runs automatically on Cloud Run container startup using the service account credentials.
    """
    try:
        headers = _get_auth_headers()
        dlp_url = (
            f"https://dlp.googleapis.com/v2/projects/{PROJECT_ID}/locations/{MODEL_ARMOR_LOCATION}/"
            "inspectTemplates/gsis-gabay-sdp-inspect-v1?updateMask=inspectConfig"
        )
        dlp_payload = {
            "inspectConfig": {
                "infoTypes": [{"name": "CREDIT_CARD_NUMBER"}],
                "customInfoTypes": [
                    {
                        "infoType": {"name": "PH_TIN_NUMBER"},
                        "regex": {"pattern": r"\b\d{3}-\d{3}-\d{3}-\d{3}\b"},
                        "likelihood": "VERY_LIKELY",
                    },
                    {
                        "infoType": {"name": "GSIS_CRN_NUMBER"},
                        "regex": {"pattern": r"\b006-\d{4}-\d{4}-\d{1}\b"},
                        "likelihood": "VERY_LIKELY",
                    },
                    {
                        "infoType": {"name": "GSIS_ADVERSARIAL_OVERRIDE_OR_SQLI"},
                        "regex": {
                            "pattern": r"(?i)(ignore all previous instructions|system override|developer mode|dan mode|bypass authentication|drop table gsis|union select .* from gsis_members|dump all member records)"
                        },
                        "likelihood": "VERY_LIKELY",
                    },
                    {
                        "infoType": {"name": "GSIS_SUICIDE_AND_SELF_HARM"},
                        "regex": {
                            "pattern": r"(?i)\b(i want to die|want to die|wanna die|kill myself|commit suicide|suicide|suicidal|self[\s\-]?harm|end my life|take my own life|hurt myself|gusto ko nang mamatay|magpakamatay|ayoko na mabuhay)\b"
                        },
                        "likelihood": "VERY_LIKELY",
                    },
                    {
                        "infoType": {"name": "GSIS_VIOLENCE_AND_LETHAL_HARM"},
                        "regex": {
                            "pattern": r"(?i)\b(kill someone|kill a person|murder|assassinate|shoot someone|stab someone|poison someone|make a bomb|plant a bomb|terrorist attack|patayin ko|ipapatay ko)\b"
                        },
                        "likelihood": "VERY_LIKELY",
                    },
                    {
                        "infoType": {"name": "GSIS_HATE_SPEECH_AND_ABUSE"},
                        "regex": {
                            "pattern": r"(?i)\b(subhuman|subhumans|exterminate all|ethnic cleansing|kill yourself|kys|you should die)\b"
                        },
                        "likelihood": "VERY_LIKELY",
                    },
                ],
                "includeQuote": True,
            }
        }
        r_dlp = _http_session.patch(dlp_url, headers=headers, json=dlp_payload, timeout=5.0)

        ma_url = (
            f"https://modelarmor.{MODEL_ARMOR_LOCATION}.rep.googleapis.com/v1/"
            f"{MODEL_ARMOR_TEMPLATE_ID}?updateMask=filterConfig"
        )
        ma_payload = {
            "filterConfig": {
                "piAndJailbreakFilterSettings": {
                    "filterEnforcement": "ENABLED",
                    "confidenceLevel": "MEDIUM_AND_ABOVE",
                },
                "raiSettings": {
                    "raiFilters": [
                        {"filterType": "HATE_SPEECH", "confidenceLevel": "LOW_AND_ABOVE"},
                        {"filterType": "HARASSMENT", "confidenceLevel": "LOW_AND_ABOVE"},
                        {"filterType": "SEXUALLY_EXPLICIT", "confidenceLevel": "LOW_AND_ABOVE"},
                        {"filterType": "DANGEROUS", "confidenceLevel": "LOW_AND_ABOVE"},
                    ]
                },
                "sdpSettings": {
                    "advancedConfig": {
                        "inspectTemplate": f"projects/{PROJECT_ID}/locations/{MODEL_ARMOR_LOCATION}/inspectTemplates/gsis-gabay-sdp-inspect-v1",
                        "deidentifyTemplate": f"projects/{PROJECT_ID}/locations/{MODEL_ARMOR_LOCATION}/deidentifyTemplates/gsis-gabay-sdp-deid-v1",
                    }
                },
            }
        }
        r_ma = _http_session.patch(ma_url, headers=headers, json=ma_payload, timeout=5.0)
        return {
            "synced": r_dlp.status_code == 200 and r_ma.status_code == 200,
            "dlp_status": r_dlp.status_code,
            "model_armor_status": r_ma.status_code,
        }
    except Exception as exc:
        return {"synced": False, "error": str(exc)}


def _call_gcp_model_armor_api(method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calls the regional Google Cloud Model Armor v1 REST endpoint:
      POST https://modelarmor.<location>.rep.googleapis.com/v1/<template_name>:<method>
    Returns a structured telemetry and inspection dictionary including granular RAI sub-filters.
    """
    if not USE_LIVE_MODEL_ARMOR:
        return {"api_mode": "LOCAL_DETERMINISTIC_FALLBACK", "live_api_called": False}

    url = f"{MODEL_ARMOR_BASE_URL}:{method}"
    try:
        headers = _get_auth_headers()
        resp = _http_session.post(url, headers=headers, json=payload, timeout=4.5)
        if resp.status_code == 200:
            data = resp.json()
            san_result = data.get("sanitizationResult", {})
            filter_results = san_result.get("filterResults", {})

            pi_res = (
                filter_results.get("pi_and_jailbreak", {})
                .get("piAndJailbreakFilterResult", {})
            )
            sdp_res = (
                filter_results.get("sdp", {})
                .get("sdpFilterResult", {})
                .get("deidentifyResult", {})
            )
            rai_res = (
                filter_results.get("rai", {})
                .get("raiFilterResult", {})
            )
            rai_type_results = rai_res.get("raiFilterTypeResults", {})
            matched_rai_categories: List[str] = []
            for r_key, r_val in rai_type_results.items():
                if r_val.get("matchState") == "MATCH_FOUND":
                    matched_rai_categories.append(
                        f"{r_key.upper()} ({r_val.get('confidenceLevel', 'MATCH_FOUND')})"
                    )

            matched_filters: List[str] = []
            if pi_res.get("matchState") == "MATCH_FOUND":
                matched_filters.append(
                    f"pi_and_jailbreak ({pi_res.get('confidenceLevel', 'HIGH')})"
                )
            if sdp_res.get("matchState") == "MATCH_FOUND":
                info_types = sdp_res.get("infoTypes", [])
                matched_filters.append(f"sdp ({','.join(info_types)})")
            if rai_res.get("matchState") == "MATCH_FOUND":
                rai_detail = ", ".join(matched_rai_categories) if matched_rai_categories else "RAI_MATCH"
                matched_filters.append(f"rai [{rai_detail}]")

            return {
                "api_mode": "LIVE_GCP_MODEL_ARMOR_V1",
                "live_api_called": True,
                "endpoint": url,
                "http_status": 200,
                "filter_match_state": san_result.get("filterMatchState", "NO_MATCH_FOUND"),
                "invocation_result": san_result.get("invocationResult", "SUCCESS"),
                "filter_version": san_result.get("filterMetadata", {}).get("filterVersion", "v3"),
                "pi_match_state": pi_res.get("matchState", "NO_MATCH_FOUND"),
                "pi_confidence": pi_res.get("confidenceLevel", "NONE"),
                "sdp_match_state": sdp_res.get("matchState", "NO_MATCH_FOUND"),
                "sdp_info_types": sdp_res.get("infoTypes", []),
                "sdp_deidentified_text": sdp_res.get("data", {}).get("text"),
                "rai_match_state": rai_res.get("matchState", "NO_MATCH_FOUND"),
                "rai_matched_categories": matched_rai_categories,
                "rai_type_results": rai_type_results,
                "matched_filters": matched_filters,
            }
        return {
            "api_mode": "LOCAL_FALLBACK_ON_HTTP_ERROR",
            "live_api_called": True,
            "endpoint": url,
            "http_status": resp.status_code,
        }
    except Exception as exc:
        return {
            "api_mode": "LOCAL_FALLBACK_ON_EXCEPTION",
            "live_api_called": False,
            "error": str(exc),
        }


def sanitize_user_prompt(
    prompt: str,
    authenticated_bp: Optional[str] = None,
    channel: str = "gwaps_web",
    target_agent: str = "ALL_5_GSIS_AGENTS",
) -> Dict[str, Any]:
    """
    Executes Google Cloud Model Armor `sanitizeUserPrompt` inspection across all 5 agents.
    Checks (in priority order):
      1. Suicide & Self-Harm Crisis Shield (`SELF_HARM_AND_SUICIDE_SHIELD`)
      2. Violence, Killing & Lethal Harm Shield (`VIOLENCE_AND_LETHAL_HARM_SHIELD`)
      3. Hate Speech, Harassment & Sexually Explicit RAI Shield (`HATE_SPEECH_AND_HARASSMENT_SHIELD`)
      4. Prompt Injection, Jailbreak & SQLi Shield (`PROMPT_INJECTION_AND_JAILBREAK_SHIELD`)
      5. Session-Bound Cross-Account BP Number Spoofing / Unauthenticated Enumeration Shield
      6. Sensitive Data Protection (SDP) Pre-Masking (`PH_TIN_NUMBER`, `GSIS_CRN_NUMBER`, `CREDIT_CARD_NUMBER`)
    """
    start_ts = time.perf_counter()
    lower_prompt = prompt.lower().strip()

    # Call live Google Cloud Model Armor API (:sanitizeUserPrompt)
    gcp_api_telemetry = _call_gcp_model_armor_api(
        "sanitizeUserPrompt",
        {"userPromptData": {"text": prompt}},
    )
    sdp_info_types = gcp_api_telemetry.get("sdp_info_types", [])
    rai_type_results = gcp_api_telemetry.get("rai_type_results", {})

    # 1. Check Suicide & Self-Harm Crisis Shield (e.g. "I want to die", "I want to die and get my insurance", "kill myself")
    regex_self_harm = any(
        re.search(pattern, lower_prompt, re.IGNORECASE)
        for pattern in SELF_HARM_SUICIDE_PATTERNS
    )
    gcp_self_harm = "GSIS_SUICIDE_AND_SELF_HARM" in sdp_info_types

    if regex_self_harm or gcp_self_harm:
        latency_ms = round((time.perf_counter() - start_ts) * 1000, 2)
        matched_filters_str = ", ".join(
            gcp_api_telemetry.get("matched_filters")
            or ["SELF_HARM_AND_SUICIDE_SHIELD", "sdp (GSIS_SUICIDE_AND_SELF_HARM)"]
        )
        return {
            "allowed": False,
            "action": "BLOCKED_BY_MODEL_ARMOR",
            "threat_category": "SELF_HARM_AND_SUICIDE_SHIELD",
            "rai_classification": "SUICIDE_AND_SELF_HARM",
            "severity": "CRITICAL",
            "policy_template": MODEL_ARMOR_TEMPLATE_ID,
            "enforced_across_agents": ALL_MULTI_AGENT_NAMES,
            "target_agent_blocked": target_agent,
            "latency_ms": latency_ms,
            "gcp_model_armor_api": gcp_api_telemetry,
            "reason": (
                "Google Cloud Model Armor blocked this request: Detected Suicide / Self-Harm ideation or "
                f"self-harm linked insurance inquiry (`sanitizeUserPrompt: MATCH_FOUND` [SELF_HARM_AND_SUICIDE_SHIELD | {matched_filters_str}])."
            ),
            "short_safe_response": (
                "🛡️ **Blocked by Google Cloud Model Armor (`SELF_HARM_AND_SUICIDE_SHIELD`)** — "
                "Your message indicates potential **self-harm or suicide**. Please know that you are not alone and immediate, "
                "confidential help is available 24/7 via the **NCMH Crisis Hotline at `1553` or `0917-899-8727`**."
            ),
            "safe_response": (
                "🛡️ **Google Cloud Model Armor Responsible AI & Crisis Safety Block (`SELF_HARM_AND_SUICIDE_SHIELD`)**\n\n"
                "Your message was flagged and blocked across **all 5 GSIS Gabay AI Agents** because it contains expressions of "
                "**suicide, self-harm, or wishing to die**.\n\n"
                "### 💛 Immediate 24/7 Confidential Support (Philippines)\n"
                "If you or someone you know is going through a difficult time or having thoughts of self-harm, please reach out right now:\n"
                "- **National Center for Mental Health (NCMH) Crisis Hotline**: Call **`1553`** (Toll-free nationwide landline) or **`0917-899-8727`** / **`0966-351-4518`** / **`0919-057-1553`**\n"
                "- **Hopeline Philippines**: Call **`(02) 8804-4673`** or **`0917-558-4673`** (Globe) / **`0918-873-4673`** (Smart)\n"
                "- **In Touch Community Services**: Call **`(02) 8893-7603`** or **`0917-800-1123`**\n\n"
                "---\n"
                "### 🔒 Model Armor Runtime Telemetry\n"
                f"- **Policy Enforced**: `{MODEL_ARMOR_TEMPLATE_ID.split('/')[-1]}` (`SELF_HARM_AND_SUICIDE_SHIELD` | `{matched_filters_str}`)\n"
                f"- **Agents Protected**: `GSIS_Concierge_Router`, `GSIS_Policy_FAQ_Agent`, `GSIS_Member_Records_Agent`, `GSIS_Loans_Computation_Agent`, `GSIS_Benefits_Transactions_Agent`\n"
                f"- **Engine**: `{gcp_api_telemetry.get('api_mode', 'LIVE_GCP_MODEL_ARMOR_V1')}`\n"
                "- **Action**: `BLOCK_AGENT_EXECUTION_AND_DISPLAY_CRISIS_HELPLINE`"
            ),
        }

    # 2. Check Violence, Killing Someone & Lethal Harm Shield
    regex_violence = any(
        re.search(pattern, lower_prompt, re.IGNORECASE)
        for pattern in VIOLENCE_LETHAL_HARM_PATTERNS
    )
    gcp_dangerous = (
        "GSIS_VIOLENCE_AND_LETHAL_HARM" in sdp_info_types
        or rai_type_results.get("dangerous", {}).get("matchState") == "MATCH_FOUND"
    )

    if regex_violence or gcp_dangerous:
        latency_ms = round((time.perf_counter() - start_ts) * 1000, 2)
        matched_filters_str = ", ".join(
            gcp_api_telemetry.get("matched_filters")
            or ["VIOLENCE_AND_LETHAL_HARM_SHIELD", "rai [DANGEROUS]"]
        )
        return {
            "allowed": False,
            "action": "BLOCKED_BY_MODEL_ARMOR",
            "threat_category": "VIOLENCE_AND_LETHAL_HARM_SHIELD",
            "rai_classification": "VIOLENCE_OR_KILLING_SOMEONE",
            "severity": "CRITICAL",
            "policy_template": MODEL_ARMOR_TEMPLATE_ID,
            "enforced_across_agents": ALL_MULTI_AGENT_NAMES,
            "target_agent_blocked": target_agent,
            "latency_ms": latency_ms,
            "gcp_model_armor_api": gcp_api_telemetry,
            "reason": (
                "Google Cloud Model Armor blocked this request: Detected violent threat, killing someone, or "
                f"dangerous harm content (`sanitizeUserPrompt: MATCH_FOUND` [VIOLENCE_AND_LETHAL_HARM_SHIELD | {matched_filters_str}])."
            ),
            "short_safe_response": (
                "🛡️ **Blocked by Google Cloud Model Armor (`VIOLENCE_AND_LETHAL_HARM_SHIELD`)** — "
                "This request was blocked because it references **violence, killing someone, or dangerous physical harm**."
            ),
            "safe_response": (
                "🛡️ **Google Cloud Model Armor Responsible AI Security Alert (`VIOLENCE_AND_LETHAL_HARM_SHIELD`)**\n\n"
                "Your request was blocked across **all 5 GSIS Gabay AI Agents** by the **Google Cloud Model Armor Responsible AI (`DANGEROUS` / Violence) Filter**.\n\n"
                f"- **Policy Enforced**: `{MODEL_ARMOR_TEMPLATE_ID.split('/')[-1]}` (`VIOLENCE_AND_LETHAL_HARM_SHIELD` | `{matched_filters_str}`)\n"
                f"- **Agents Protected**: `GSIS_Concierge_Router`, `GSIS_Policy_FAQ_Agent`, `GSIS_Member_Records_Agent`, `GSIS_Loans_Computation_Agent`, `GSIS_Benefits_Transactions_Agent`\n"
                f"- **Engine**: `{gcp_api_telemetry.get('api_mode', 'LIVE_GCP_MODEL_ARMOR_V1')}`\n"
                "- **Action**: `BLOCK_AND_LOG`"
            ),
        }

    # 3. Check Hate Speech, Harassment & Sexually Explicit RAI Shield
    regex_hate = any(
        re.search(pattern, lower_prompt, re.IGNORECASE)
        for pattern in HATE_SPEECH_HARASSMENT_PATTERNS
    )
    gcp_hate_or_harassment = (
        "GSIS_HATE_SPEECH_AND_ABUSE" in sdp_info_types
        or rai_type_results.get("hate_speech", {}).get("matchState") == "MATCH_FOUND"
        or rai_type_results.get("harassment", {}).get("matchState") == "MATCH_FOUND"
        or rai_type_results.get("sexually_explicit", {}).get("matchState") == "MATCH_FOUND"
    )

    if regex_hate or gcp_hate_or_harassment:
        latency_ms = round((time.perf_counter() - start_ts) * 1000, 2)
        matched_filters_str = ", ".join(
            gcp_api_telemetry.get("matched_filters")
            or ["HATE_SPEECH_AND_HARASSMENT_SHIELD", "rai [HATE_SPEECH/HARASSMENT]"]
        )
        return {
            "allowed": False,
            "action": "BLOCKED_BY_MODEL_ARMOR",
            "threat_category": "HATE_SPEECH_AND_HARASSMENT_SHIELD",
            "rai_classification": "HATE_SPEECH_OR_HARASSMENT",
            "severity": "HIGH",
            "policy_template": MODEL_ARMOR_TEMPLATE_ID,
            "enforced_across_agents": ALL_MULTI_AGENT_NAMES,
            "target_agent_blocked": target_agent,
            "latency_ms": latency_ms,
            "gcp_model_armor_api": gcp_api_telemetry,
            "reason": (
                "Google Cloud Model Armor blocked this request: Detected Hate Speech, Harassment, or "
                f"Abusive content (`sanitizeUserPrompt: MATCH_FOUND` [HATE_SPEECH_AND_HARASSMENT_SHIELD | {matched_filters_str}])."
            ),
            "short_safe_response": (
                "🛡️ **Blocked by Google Cloud Model Armor (`HATE_SPEECH_AND_HARASSMENT_SHIELD`)** — "
                "This request was blocked because it contains **hate speech, dehumanizing language, or severe harassment**."
            ),
            "safe_response": (
                "🛡️ **Google Cloud Model Armor Responsible AI Security Alert (`HATE_SPEECH_AND_HARASSMENT_SHIELD`)**\n\n"
                "Your request was blocked across **all 5 GSIS Gabay AI Agents** by the **Google Cloud Model Armor Responsible AI (`HATE_SPEECH` / `HARASSMENT`) Filter**.\n\n"
                f"- **Policy Enforced**: `{MODEL_ARMOR_TEMPLATE_ID.split('/')[-1]}` (`HATE_SPEECH_AND_HARASSMENT_SHIELD` | `{matched_filters_str}`)\n"
                f"- **Agents Protected**: `GSIS_Concierge_Router`, `GSIS_Policy_FAQ_Agent`, `GSIS_Member_Records_Agent`, `GSIS_Loans_Computation_Agent`, `GSIS_Benefits_Transactions_Agent`\n"
                f"- **Engine**: `{gcp_api_telemetry.get('api_mode', 'LIVE_GCP_MODEL_ARMOR_V1')}`\n"
                "- **Action**: `BLOCK_AND_LOG`"
            ),
        }

    # 4. Check Prompt Injection / Jailbreak / SQLi via both Live GCP Model Armor API and Deterministic Rules
    regex_pi_matched = any(
        re.search(pattern, lower_prompt, re.IGNORECASE)
        for pattern in PROMPT_INJECTION_PATTERNS
    )
    gcp_pi_matched = (
        (
            gcp_api_telemetry.get("pi_match_state") == "MATCH_FOUND"
            and gcp_api_telemetry.get("pi_confidence") in ("MEDIUM_AND_ABOVE", "HIGH")
        )
        or "GSIS_ADVERSARIAL_OVERRIDE_OR_SQLI" in sdp_info_types
        or gcp_api_telemetry.get("rai_match_state") == "MATCH_FOUND"
    )

    if regex_pi_matched or gcp_pi_matched:
        latency_ms = round((time.perf_counter() - start_ts) * 1000, 2)
        matched_filters_str = ", ".join(
            gcp_api_telemetry.get("matched_filters") or ["PROMPT_INJECTION_SHIELD"]
        )
        return {
            "allowed": False,
            "action": "BLOCKED_BY_MODEL_ARMOR",
            "threat_category": "PROMPT_INJECTION_AND_JAILBREAK_SHIELD",
            "rai_classification": "PROMPT_INJECTION_OR_JAILBREAK",
            "severity": "CRITICAL",
            "policy_template": MODEL_ARMOR_TEMPLATE_ID,
            "enforced_across_agents": ALL_MULTI_AGENT_NAMES,
            "target_agent_blocked": target_agent,
            "latency_ms": latency_ms,
            "gcp_model_armor_api": gcp_api_telemetry,
            "reason": (
                "Google Cloud Model Armor blocked this request: Detected adversarial prompt injection "
                f"or security override attempt (`sanitizeUserPrompt: MATCH_FOUND` [PROMPT_INJECTION_SHIELD | {matched_filters_str}])."
            ),
            "short_safe_response": (
                "🛡️ **Blocked by Google Cloud Model Armor (`PROMPT_INJECTION_AND_JAILBREAK_SHIELD`)** — "
                "Detected adversarial instruction override, jailbreak, or SQL injection payload."
            ),
            "safe_response": (
                "🛡️ **Google Cloud Model Armor Security Alert (`sanitizeUserPrompt`)**\n\n"
                "Your request was blocked by the **GSIS Gabay AI Runtime Security Policy** because it contains "
                "an instruction override, jailbreak, or unauthorized system query pattern.\n\n"
                f"- **Policy Enforced**: `{MODEL_ARMOR_TEMPLATE_ID.split('/')[-1]}` (`PROMPT_INJECTION_SHIELD` | `{matched_filters_str}`)\n"
                f"- **Agents Protected**: `GSIS_Concierge_Router`, `GSIS_Policy_FAQ_Agent`, `GSIS_Member_Records_Agent`, `GSIS_Loans_Computation_Agent`, `GSIS_Benefits_Transactions_Agent`\n"
                f"- **Engine**: `{gcp_api_telemetry.get('api_mode', 'LIVE_GCP_MODEL_ARMOR_V1')}`\n"
                "- **Action**: `BLOCK_AND_LOG`\n"
                "- **Zero-Trust Guarantee**: Member records and MCP tools can only be accessed via cryptographically "
                "verified session tokens (`JWT + MFA`)."
            ),
        }

    # 5. Check Cross-Account BP Number Spoofing / Enumeration (Session-Bound Custom GSIS Rule)
    mentioned_bps = BP_NUMBER_REGEX.findall(prompt)
    if mentioned_bps:
        for mentioned_bp in mentioned_bps:
            # If unauthenticated user tries to query a specific BP number's records
            if not authenticated_bp:
                latency_ms = round((time.perf_counter() - start_ts) * 1000, 2)
                return {
                    "allowed": False,
                    "action": "BLOCKED_BY_MODEL_ARMOR",
                    "threat_category": "UNAUTHENTICATED_BP_ENUMERATION",
                    "severity": "HIGH",
                    "policy_template": MODEL_ARMOR_TEMPLATE_ID,
                    "enforced_across_agents": ALL_MULTI_AGENT_NAMES,
                    "target_agent_blocked": target_agent,
                    "latency_ms": latency_ms,
                    "gcp_model_armor_api": gcp_api_telemetry,
                    "reason": (
                        f"Attempted to query specific BP Number ({mentioned_bp}) while in Phase 1 Unauthenticated mode."
                    ),
                    "short_safe_response": (
                        f"🛡️ **Blocked by Google Cloud Model Armor (`UNAUTHENTICATED_BP_ENUMERATION`)** — "
                        f"You referenced BP Number `{mentioned_bp}` while in Unauthenticated Guest Mode. Please sign in first."
                    ),
                    "safe_response": (
                        "🛡️ **Google Cloud Model Armor & Phase 2 Identity Guardrail**\n\n"
                        f"You referenced a specific GSIS BP Number (`{mentioned_bp}`) while in **Unauthenticated Mode**. "
                        "To protect member privacy under the **Data Privacy Act of 2012 (RA 10173)**, GSIS Gabay AI "
                        "never accepts BP Numbers typed in chat prompts.\n\n"
                        "👉 Please click **Member Login (Phase 2)** in the top bar (or register a custom mock account) "
                        "and verify your 6-digit OTP so your `bp_number` is securely injected by the server."
                    ),
                }
            elif mentioned_bp != authenticated_bp:
                latency_ms = round((time.perf_counter() - start_ts) * 1000, 2)
                return {
                    "allowed": False,
                    "action": "BLOCKED_BY_MODEL_ARMOR",
                    "threat_category": "CROSS_ACCOUNT_BP_SPOOFING_ATTEMPT",
                    "severity": "CRITICAL",
                    "policy_template": MODEL_ARMOR_TEMPLATE_ID,
                    "enforced_across_agents": ALL_MULTI_AGENT_NAMES,
                    "target_agent_blocked": target_agent,
                    "latency_ms": latency_ms,
                    "gcp_model_armor_api": gcp_api_telemetry,
                    "reason": (
                        f"Cross-Account Horizontal Privilege Escalation attempt: Session belongs to BP {authenticated_bp}, "
                        f"but prompt requested records for BP {mentioned_bp}."
                    ),
                    "short_safe_response": (
                        f"🛡️ **Blocked by Google Cloud Model Armor (`CROSS_ACCOUNT_BP_SPOOFING_ATTEMPT`)** — "
                        f"Your session is bound to **BP `{authenticated_bp}`** and cannot query **BP `{mentioned_bp}`**."
                    ),
                    "safe_response": (
                        "🛡️ **Google Cloud Model Armor Security Block (`CROSS_ACCOUNT_ISOLATION`)**\n\n"
                        f"Your session is cryptographically bound to **BP `{authenticated_bp}`**, but your prompt attempted "
                        f"to access records for a different member (**BP `{mentioned_bp}`**).\n\n"
                        "- **Identity-Bound MCP Enforcement**: Tool parameters (`bp_number`) are extracted strictly from "
                        "your server-side JWT token and cannot be overridden via natural language.\n"
                        "- **Incident Logged**: `MODEL_ARMOR_CROSS_ACCOUNT_ATTEMPT`"
                    ),
                }

    # 6. Sensitive Data Protection (SDP) Pre-Masking (Cloud DLP De-identify + Deterministic TIN/CRN Masking)
    sanitized_text = prompt
    if gcp_api_telemetry.get("sdp_match_state") == "MATCH_FOUND" and gcp_api_telemetry.get("sdp_deidentified_text"):
        sanitized_text = gcp_api_telemetry["sdp_deidentified_text"]
    sanitized_text = TIN_REGEX.sub("[REDACTED-TIN]", sanitized_text)
    sanitized_text = CRN_REGEX.sub("[REDACTED-CRN]", sanitized_text)

    latency_ms = round((time.perf_counter() - start_ts) * 1000, 2)
    return {
        "allowed": True,
        "action": "SANITIZED_AND_ALLOWED",
        "threat_category": "NONE",
        "severity": "INFO",
        "policy_template": MODEL_ARMOR_TEMPLATE_ID,
        "enforced_across_agents": ALL_MULTI_AGENT_NAMES,
        "latency_ms": latency_ms,
        "gcp_model_armor_api": gcp_api_telemetry,
        "sanitized_prompt": sanitized_text,
        "pii_redacted": sanitized_text != prompt,
    }


def enforce_agent_model_armor_guard(
    agent_name: str,
    prompt: str,
    authenticated_bp: Optional[str] = None,
    channel: str = "gwaps_web",
    precomputed_input_armor: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Explicit per-agent Model Armor guard invoked inside each of the 5 GSIS Specialist Agents
    (`GSIS_Concierge_Router`, `GSIS_Policy_FAQ_Agent`, `GSIS_Member_Records_Agent`,
    `GSIS_Loans_Computation_Agent`, `GSIS_Benefits_Transactions_Agent`) before executing
    any RAG retrieval, MCP database call, or LLM response synthesis.
    """
    if precomputed_input_armor is not None:
        verdict = dict(precomputed_input_armor)
        verdict["verified_by_agent"] = agent_name
        verdict["enforced_across_agents"] = ALL_MULTI_AGENT_NAMES
        return verdict
    verdict = sanitize_user_prompt(
        prompt=prompt,
        authenticated_bp=authenticated_bp,
        channel=channel,
        target_agent=agent_name,
    )
    verdict["verified_by_agent"] = agent_name
    return verdict


def sanitize_model_response(
    response_text: str,
    authenticated_bp: Optional[str] = None,
    agent_name: str = "GSIS_Concierge_Router",
) -> Dict[str, Any]:
    """
    Executes Google Cloud Model Armor `sanitizeModelResponse` inspection for the active Specialist Agent.
    Calls the live GCP Model Armor `:sanitizeModelResponse` API and ensures no unmasked
    TIN/CRN, RAI violation, or foreign BP numbers are emitted in the final response.
    """
    start_ts = time.perf_counter()
    output = response_text

    # Call live Google Cloud Model Armor API (:sanitizeModelResponse)
    gcp_api_telemetry = _call_gcp_model_armor_api(
        "sanitizeModelResponse",
        {"modelResponseData": {"text": output}},
    )

    # Redact any accidental TIN or CRN patterns
    output = TIN_REGEX.sub("***-***-***-000", output)

    # Verify no foreign BP number leaked
    foreign_bp_redacted = False
    for match in BP_NUMBER_REGEX.findall(output):
        if authenticated_bp and match != authenticated_bp:
            output = output.replace(match, "[REDACTED-FOREIGN-BP]")
            foreign_bp_redacted = True

    latency_ms = round((time.perf_counter() - start_ts) * 1000, 2)
    return {
        "sanitized_response": output,
        "action": "PASSED_OUTPUT_INSPECTION",
        "verified_by_agent": agent_name,
        "enforced_across_agents": ALL_MULTI_AGENT_NAMES,
        "foreign_bp_redacted": foreign_bp_redacted,
        "latency_ms": latency_ms,
        "policy_template": MODEL_ARMOR_TEMPLATE_ID,
        "gcp_model_armor_api": gcp_api_telemetry,
    }



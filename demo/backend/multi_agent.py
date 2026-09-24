"""
GSIS Gabay AI Multi-Agent Orchestrator (Google ADK & Gemini 3.7 Flash / 3.1 Pro)
================================================================================
Implements the 5-Agent Hierarchy defined in `02_TDD_GSIS_CHATBOT_DEMO_MOCK_ARCHITECTURE.md`:
  1. `GSIS_Concierge_Router` (Model: `gemini-3.7-flash`)
  2. `GSIS_Policy_FAQ_Agent` (Model: `gemini-3.7-flash`)
  3. `GSIS_Member_Records_Agent` (Model: `gemini-3.7-flash`)
  4. `GSIS_Loans_Computation_Agent` (Model: `gemini-3.1-pro`)
  5. `GSIS_Benefits_Transactions_Agent` (Model: `gemini-3.1-pro`)
"""

import os
import re
import time
from typing import Dict, Any, List, Optional

from .model_armor import (
    sanitize_user_prompt,
    sanitize_model_response,
    enforce_agent_model_armor_guard,
    ALL_MULTI_AGENT_NAMES,
)
from .mcp_server import (
    search_gsis_faq_rag,
    calculate_sample_loan_or_pension,
    get_member_profile,
    get_contributions_summary,
    get_member_loans,
    simulate_loan_application,
    get_benefits_and_eligibility,
    get_recent_transactions,
)
from .calculators import OFFICIAL_TENTATIVE_DISCLAIMER, COMING_SOON_ACTIONS


PERSONAL_INTENT_PATTERNS = [
    r"\bmy\s+(loan|loans|mpl|balance|reloan|proceeds|amortization|deduction|contribution|contributions|premium|pension|retirement|benefit|benefits|beneficiar|apir|account|profile|salary|service|ppp|status|transaction|claim|unposted|erf|agency)\b",
    r"\bdo\s+i\s+(have|owe|qualify|need|get)\b",
    r"\bhave\s+i\s+(got|taken|applied|paid|borrowed)\b",
    r"\bdid\s+i\s+(take|borrow|apply|pay)\b",
    r"\bhow\s+much\s+(can\s+i|do\s+i|is\s+my|are\s+my|have\s+i)\b",
    r"\bam\s+i\s+(eligible|qualified|due|allowed)\b",
    r"\bcan\s+i\s+(borrow|loan|reloan|apply|retire|claim)\b",
    r"\b(may|meron\s+ba\s+akong|mayroon\s+ba\s+akong)\b.*\b(loan|loans|utang|balance|contribution|pension)\b",
    r"\b(existing|active|current|outstanding)\s+loans?\b",
    r"\bcheck\s+my\b",
    r"\bshow\s+my\b",
    r"\bwhat\s+(is|are)\s+my\b",
    r"\bwhen\s+is\s+my\s+apir\b",
    r"\bwhy\s+is\s+my\b",
]


def _is_yes_no_question(prompt: str) -> bool:
    """Returns True if the user is asking a binary Yes/No question (e.g., 'Do I have any existing loans?')."""
    q = prompt.strip().lower()
    yes_no_prefixes = (
        "do i ",
        "do i have",
        "have i ",
        "did i ",
        "am i ",
        "is my ",
        "are my ",
        "can i ",
        "do we ",
        "is there any ",
        "are there any ",
        "may loan ba ako",
        "meron ba akong",
        "mayroon ba akong",
        "may existing",
    )
    return q.startswith(yes_no_prefixes) or bool(
        re.search(r"\b(do\s+i\s+have|have\s+i\s+got|am\s+i\s+eligible|can\s+i\s+reloan|may\s+loan\s+ba\s+ako|meron\s+ba\s+akong)\b", q)
    )


def _extract_salary_from_prompt(prompt: str) -> Optional[float]:
    """Extracts a salary figure like '45,000' or '60000' if mentioned in a sample calculation query."""
    matches = re.findall(r"(?:php|₱|salary\s*(?:of|is)?\s*)?\b([2-9]\d,\d{3}|1\d{2},\d{3}|[2-9]\d{4}|1\d{5})\b", prompt, re.IGNORECASE)
    for m in matches:
        val = float(m.replace(",", ""))
        if 15000 <= val <= 350000:
            return val
    return None


def _extract_years_from_prompt(prompt: str) -> Optional[float]:
    """Extracts years of service (e.g., '18 years') if mentioned in a prompt."""
    m = re.search(r"\b(\d{1,2}(?:\.\d+)?)\s*(?:years?|yrs?)\b", prompt, re.IGNORECASE)
    if m:
        val = float(m.group(1))
        if 1 <= val <= 45:
            return val
    return None


def _classify_intent(prompt: str, authenticated_bp: Optional[str]) -> Dict[str, Any]:
    """
    `GSIS_Concierge_Router` (`gemini-3.7-flash`) deterministic + semantic intent classification.
    """
    q = prompt.lower()
    is_personal_query = any(re.search(pat, q) for pat in PERSONAL_INTENT_PATTERNS)

    # Check if user is asking for a sample / hypothetical calculation with numbers
    explicit_salary = _extract_salary_from_prompt(prompt)
    explicit_years = _extract_years_from_prompt(prompt)
    is_sample_calc = (
        ("sample" in q or "estimate" in q or "simulate" in q or "if my salary" in q or explicit_salary is not None)
        and ("loan" in q or "mpl" in q or "pension" in q or "retire" in q)
    )

    # Unauthenticated Personal Query -> Trigger Phase 1 -> Phase 2 Auth Gate
    if is_personal_query and not authenticated_bp and not is_sample_calc:
        return {
            "intent": "PHASE2_AUTH_REQUIRED_GATE",
            "routed_to": "GSIS_Concierge_Router",
            "model_tier": "gemini-3.7-flash",
            "requires_auth": True,
        }

    # Authenticated Member Queries
    if authenticated_bp and (
        is_personal_query
        or any(
            k in q
            for k in [
                "reloan",
                "balance",
                "existing loan",
                "active loan",
                "ledger",
                "unposted",
                "option 1",
                "option 2",
                "apir",
                "beneficiar",
                "proceeds",
            ]
        )
    ):
        if any(k in q for k in ["loan", "loans", "mpl", "reloan", "borrow", "proceeds", "amortization", "conso", "emergency", "gfals", "calamity"]):
            return {
                "intent": "MEMBER_LOAN_SIMULATION_AND_BALANCES",
                "routed_to": "GSIS_Loans_Computation_Agent",
                "model_tier": "gemini-3.1-pro",
                "requires_auth": True,
            }
        if any(k in q for k in ["retire", "pension", "bmp", "option 1", "option 2", "lump sum", "survivorship", "disability", "funeral", "apir", "claim", "benefit", "transaction"]):
            return {
                "intent": "MEMBER_BENEFITS_AND_RETIREMENT",
                "routed_to": "GSIS_Benefits_Transactions_Agent",
                "model_tier": "gemini-3.1-pro",
                "requires_auth": True,
            }
        return {
            "intent": "MEMBER_PROFILE_AND_CONTRIBUTIONS",
            "routed_to": "GSIS_Member_Records_Agent",
            "model_tier": "gemini-3.7-flash",
            "requires_auth": True,
        }

    # Unauthenticated Sample Calculation
    if is_sample_calc:
        return {
            "intent": "PUBLIC_SAMPLE_CALCULATION",
            "routed_to": "GSIS_Policy_FAQ_Agent",
            "model_tier": "gemini-3.7-flash",
            "requires_auth": False,
            "sample_salary": explicit_salary or 45000.0,
            "sample_years": explicit_years or 15.0,
        }

    # Default: Phase 1 Policy & FAQ RAG Agent
    return {
        "intent": "PUBLIC_POLICY_FAQ_RAG",
        "routed_to": "GSIS_Policy_FAQ_Agent",
        "model_tier": "gemini-3.7-flash",
        "requires_auth": False,
    }


def run_multi_agent_turn(
    prompt: str,
    authenticated_bp: Optional[str] = None,
    channel: str = "gwaps_web",
) -> Dict[str, Any]:
    """
    Executes a complete end-to-end turn through:
      1. Google Cloud Model Armor `sanitizeUserPrompt`
      2. `GSIS_Concierge_Router` (`gemini-3.7-flash`)
      3. Specialist Sub-Agent + Identity-Bound MCP Tools + Deterministic Calculators
      4. Google Cloud Model Armor `sanitizeModelResponse`
    """
    turn_start = time.perf_counter()

    # Pre-classify target specialist agent so Model Armor logs both the Router and the target Specialist Agent
    pre_route = _classify_intent(prompt, authenticated_bp)
    target_specialist = pre_route["routed_to"]

    # Step 1: Google Cloud Model Armor Input Inspection (Enforced across Supervisor Router + Target Specialist Agent)
    armor_in = sanitize_user_prompt(
        prompt=prompt,
        authenticated_bp=authenticated_bp,
        channel=channel,
        target_agent=target_specialist,
    )
    agent_guard = enforce_agent_model_armor_guard(
        agent_name=target_specialist,
        prompt=prompt,
        authenticated_bp=authenticated_bp,
        channel=channel,
        precomputed_input_armor=armor_in,
    )
    if not agent_guard["allowed"]:
        total_ms = round((time.perf_counter() - turn_start) * 1000, 2)
        short_block = agent_guard.get("short_safe_response", agent_guard["safe_response"])
        return {
            "reply": agent_guard["safe_response"],
            "short_reply": short_block,
            "full_reply": agent_guard["safe_response"],
            "agent_trace": {
                "router_agent": "GSIS_Concierge_Router (gemini-3.7-flash)",
                "specialist_agent": "BLOCKED_BY_MODEL_ARMOR",
                "target_specialist_agent_protected": f"{target_specialist} ({pre_route['model_tier']})",
                "agents_protected_by_model_armor": ALL_MULTI_AGENT_NAMES,
                "model_used": "google-cloud-model-armor-v1",
                "intent": agent_guard["threat_category"],
                "authenticated_bp": authenticated_bp,
                "mcp_tools_called": [],
                "total_latency_ms": total_ms,
            },
            "model_armor": agent_guard,
            "citations": [],
            "phase3_actions": [],
            "requires_login_modal": agent_guard["threat_category"] == "UNAUTHENTICATED_BP_ENUMERATION",
        }

    clean_prompt = agent_guard["sanitized_prompt"]
    route = _classify_intent(clean_prompt, authenticated_bp)
    intent = route["intent"]
    specialist_agent = route["routed_to"]
    model_tier = route["model_tier"]

    # Explicitly verify Model Armor guard for the routed Specialist Agent (`GSIS_Policy_FAQ_Agent`,
    # `GSIS_Member_Records_Agent`, `GSIS_Loans_Computation_Agent`, `GSIS_Benefits_Transactions_Agent`, or `GSIS_Concierge_Router`)
    specialist_armor_in = enforce_agent_model_armor_guard(
        agent_name=specialist_agent,
        prompt=clean_prompt,
        authenticated_bp=authenticated_bp,
        channel=channel,
        precomputed_input_armor=agent_guard,
    )

    mcp_tools_called: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []
    phase3_actions: List[Dict[str, Any]] = []
    requires_login_modal = False

    # Always retrieve top RAG citations for statutory grounding
    rag_res = search_gsis_faq_rag(clean_prompt, top_k=3)
    mcp_tools_called.append({"tool": "search_gsis_faq_rag", "status": "SUCCESS", "matches": rag_res["matches_count"]})
    citations = rag_res["citations"]

    short_reply_text = ""

    # -------------------------------------------------------------------------
    # CASE A: Phase 1 Unauthenticated User Asking About Personal Records
    # -------------------------------------------------------------------------
    if intent == "PHASE2_AUTH_REQUIRED_GATE":
        requires_login_modal = True
        top_doc = citations[0] if citations else None
        policy_snippet = (
            f"\n\n📚 **Related GSIS Statutory Policy ({top_doc['title']})**:\n{top_doc['content']}"
            if top_doc
            else ""
        )
        short_reply_text = (
            "🔒 **Direct Answer:** You are currently in **Phase 1 (Unauthenticated Guest Mode)**. "
            "Please click **\"🔐 Sign In or Register Mock Member\"** below (or use the top-right User Profile Badge) "
            "to view your personal loan balances, contribution ledger, or retirement payouts."
        )
        reply_text = (
            "🔒 **Phase 2 Member Authentication Required (`JWT + 6-Digit OTP`)**\n\n"
            "You are currently browsing in **Phase 1 (Unauthenticated Guest Mode)**. "
            "To protect member privacy and comply with the **Data Privacy Act of 2012 (RA 10173)**, "
            "I can only access personal contribution ledgers, loan balances, net proceeds simulations, "
            "or retirement options after you sign in.\n\n"
            "### How to test Phase 2 right now:\n"
            "1. Click **\"🔐 Member Login / Register\"** or the **top-right User Profile Badge**.\n"
            "2. Select one of the **3 Pre-Seeded Personas** (`maria.santos`, `juan.delacruz`, or `rosa.reyes` — password `gsis2026`) "
            "or click **\"✨ Create Custom Mock Member\"** (up to 25 demo accounts).\n"
            "3. Complete the simulated **6-Digit OTP verification** — your `bp_number` will be cryptographically bound to your session!\n"
            f"{policy_snippet}"
        )

    # -------------------------------------------------------------------------
    # CASE B: Phase 1 Public Sample Calculation
    # -------------------------------------------------------------------------
    elif intent == "PUBLIC_SAMPLE_CALCULATION":
        is_retire = any(k in clean_prompt.lower() for k in ["retire", "pension", "bmp", "option 1", "option 2"])
        calc_type = "retirement" if is_retire else "mpl_flex"
        sample_res = calculate_sample_loan_or_pension(
            calc_type=calc_type,
            basic_monthly_salary=route["sample_salary"],
            ppp_years=route["sample_years"],
            age=60,
        )
        mcp_tools_called.append(
            {
                "tool": "calculate_sample_loan_or_pension",
                "status": "SUCCESS",
                "calc_type": calc_type,
            }
        )
        if calc_type == "retirement":
            short_reply_text = (
                f"🎯 **Direct Answer:** For a **PHP {sample_res['amc']:,.2f}** salary and **{sample_res['ppp_years']} years** of service, "
                f"your estimated **Basic Monthly Pension (BMP)** is **PHP {sample_res['final_bmp']:,.2f}/month** "
                f"(**Option 1 5-Yr Lump Sum**: **PHP {sample_res['option_1']['five_year_lump_sum']:,.2f}** | "
                f"**Option 2 18-Mo Cash**: **PHP {sample_res['option_2']['eighteen_month_cash_payment']:,.2f}**)."
            )
            reply_text = (
                f"### 📊 Sample RA 8291 Retirement Computation (Unauthenticated Estimate)\n"
                f"Based on your hypothetical inputs (**AMC: PHP {sample_res['amc']:,.2f}**, **PPP: {sample_res['ppp_years']} years**, **Age: 60**):\n\n"
                f"- **Formula**: `{sample_res['formula_explanation']}`\n"
                f"- **Estimated Basic Monthly Pension (BMP)**: **PHP {sample_res['final_bmp']:,.2f} / month**\n"
                f"- **Option 1 (5-Year Lump Sum + Pension at Age 65)**: **PHP {sample_res['option_1']['five_year_lump_sum']:,.2f}**\n"
                f"- **Option 2 (18-Month Cash Payment + Immediate Pension)**: **PHP {sample_res['option_2']['eighteen_month_cash_payment']:,.2f}** + **PHP {sample_res['final_bmp']:,.2f}/mo immediately**\n\n"
                f"💡 *Want to run this against your actual GSIS contribution ledger and service records? Click **Member Login (Phase 2)** above!*\n\n"
                f"> {OFFICIAL_TENTATIVE_DISCLAIMER}"
            )
        else:
            short_reply_text = (
                f"🎯 **Direct Answer:** For a **PHP {sample_res['basic_monthly_salary']:,.2f}** salary and **{sample_res['ppp_years']} PPP years**, "
                f"your maximum MPL Flex loan is **PHP {sample_res['gross_loan_amount']:,.2f}** ({sample_res['salary_multiplier_months']}× salary), "
                f"yielding **PHP {sample_res['estimated_net_proceeds']:,.2f} in estimated net proceeds** (**PHP {sample_res['new_monthly_amortization']:,.2f}/month** for {sample_res['requested_term_months']} mos)."
            )
            reply_text = (
                f"### 🧮 Sample MPL Flex Loan Computation (Unauthenticated Estimate)\n"
                f"Based on a hypothetical **Basic Monthly Salary of PHP {sample_res['basic_monthly_salary']:,.2f}** and **{sample_res['ppp_years']} PPP years**:\n\n"
                f"- **Max Creditable Entitlement ({sample_res['salary_multiplier_months']}x Salary)**: **PHP {sample_res['gross_loan_amount']:,.2f}**\n"
                f"- **Interest Rate**: **{sample_res['interest_rate_annual']*100:.0f}% p.a.** ({sample_res['requested_term_months']} months / 7 years)\n"
                f"- **Service Fee (2%)**: PHP {sample_res['service_fee_2pct']:,.2f} | **MRI Fee**: PHP {sample_res['mri_fee']:,.2f}\n"
                f"- **Estimated Net Proceeds**: **PHP {sample_res['estimated_net_proceeds']:,.2f}**\n"
                f"- **Estimated Monthly Amortization**: **PHP {sample_res['new_monthly_amortization']:,.2f} / month**\n\n"
                f"💡 *Sign in via **Member Login (Phase 2)** to automatically deduct any existing MPL/Emergency loan balances and check your PHP 5,000 GAA net take-home pay compliance.*\n\n"
                f"> {OFFICIAL_TENTATIVE_DISCLAIMER}"
            )

    # -------------------------------------------------------------------------
    # CASE C: Phase 2 Authenticated — Member Profile & Contributions (`GSIS_Member_Records_Agent`)
    # -------------------------------------------------------------------------
    elif intent == "MEMBER_PROFILE_AND_CONTRIBUTIONS":
        profile = get_member_profile(authenticated_bp)
        contribs = get_contributions_summary(authenticated_bp)
        mcp_tools_called.extend(
            [
                {"tool": "get_member_profile", "bp_number": authenticated_bp, "status": "SUCCESS"},
                {"tool": "get_contributions_summary", "bp_number": authenticated_bp, "status": "SUCCESS"},
            ]
        )
        if contribs.get("phase3_action_cta"):
            phase3_actions.append(contribs["phase3_action_cta"])

        beneficiaries_list = "\n".join(f"  - {b}" for b in profile.get("legal_beneficiaries", []))
        unposted_alert = ""
        unposted_periods = ", ".join(u["period_month"] for u in contribs["unposted_periods"])
        if contribs["unposted_months_count"] > 0:
            unposted_alert = (
                f"\n\n⚠️ **Unposted Remittance Alert (`{contribs['unposted_months_count']}` month detected: `{unposted_periods}`)**:\n"
                f"Our ledger shows that your agency (**{profile['agency_name']}**) has a pending Electronic Remittance File (ERF) "
                f"reconciliation for **{unposted_periods}**. Under GSIS policy, please coordinate with your Agency Authorized Officer (AAO) "
                f"or click the **\"File ERF Reconciliation Ticket\"** action button below."
            )

        q_lower = clean_prompt.lower()
        is_yn = _is_yes_no_question(clean_prompt)
        if is_yn and ("unposted" in q_lower or "missing" in q_lower):
            if contribs["unposted_months_count"] > 0:
                short_reply_text = (
                    f"🎯 **Direct Answer:** **Yes** — you have **{contribs['unposted_months_count']} unposted ERF remittance (`{unposted_periods}`)** "
                    f"pending AAO reconciliation at **{profile['agency_code']}**."
                )
            else:
                short_reply_text = (
                    f"🎯 **Direct Answer:** **No** — all **{contribs['posted_months_count']} of {contribs['months_inspected']} months** "
                    f"of your GSIS contributions are **100% POSTED** (`0 unposted months`)."
                )
        elif is_yn and ("posted" in q_lower or "complete" in q_lower or "updated" in q_lower):
            if contribs["unposted_months_count"] == 0:
                short_reply_text = (
                    f"🎯 **Direct Answer:** **Yes** — all **{contribs['posted_months_count']} of {contribs['months_inspected']} months** "
                    f"of your GSIS contributions are **100% POSTED**."
                )
            else:
                short_reply_text = (
                    f"🎯 **Direct Answer:** **No** — **{contribs['posted_months_count']} of {contribs['months_inspected']} months** are posted, "
                    f"with **{contribs['unposted_months_count']} unposted ERF month (`{unposted_periods}`)**."
                )
        elif "beneficiar" in q_lower and "contribut" not in q_lower:
            short_reply_text = (
                f"🎯 **Direct Answer:** Based on your **{profile['civil_status']}** civil status (`BP {authenticated_bp}`), "
                f"your recognized RA 8291 legal beneficiaries are: **{' | '.join(profile.get('legal_beneficiaries', []))}**."
            )
        elif "unposted" in q_lower or "erf" in q_lower:
            if contribs["unposted_months_count"] > 0:
                short_reply_text = (
                    f"🎯 **Direct Answer:** You have **{contribs['unposted_months_count']} unposted ERF remittance (`{unposted_periods}`)** "
                    f"pending AAO reconciliation at **{profile['agency_code']}**, while **{contribs['posted_months_count']} of {contribs['months_inspected']} months** are posted."
                )
            else:
                short_reply_text = (
                    f"🎯 **Direct Answer:** All **{contribs['posted_months_count']} of {contribs['months_inspected']} months** of your GSIS contributions are **100% POSTED** with **0 unposted ERF months**."
                )
        elif "contribut" in q_lower or "premium" in q_lower or "ledger" in q_lower:
            unp_note = f" (⚠️ **{contribs['unposted_months_count']} unposted ERF in `{unposted_periods}`**)" if contribs["unposted_months_count"] > 0 else " (All 12 months posted)"
            short_reply_text = (
                f"🎯 **Direct Answer:** Over the last 12 months (`BP {authenticated_bp}`), your posted contributions total "
                f"**PHP {contribs['total_personal_share_12m']:,.2f} Personal Share (9%)** and **PHP {contribs['total_government_share_12m']:,.2f} Government Share (12%)** "
                f"across **{ profile['total_ppp_years']} years of PPP**{unp_note}."
            )
        else:
            short_reply_text = (
                f"🎯 **Direct Answer:** **{profile['full_name']}** (`BP {authenticated_bp}`) is an active **{profile['position_title']}** at **{profile['agency_code']}** "
                f"(**Age {profile['age']}**, **{profile['civil_status']}**, **PPP: {profile['total_ppp_years']} years**, **Basic Monthly Salary: PHP {profile['basic_monthly_salary']:,.2f}**)."
            )

        reply_text = (
            f"### 👤 Verified GSIS Member Profile & Contribution Ledger (`BP {authenticated_bp}`)\n"
            f"- **Full Name**: **{profile['full_name']}** ({profile['position_title']}, {profile['agency_code']})\n"
            f"- **Age & Birth Date**: **{profile['age']} years old** (Born `{profile['birth_date']}`)\n"
            f"- **Civil Status**: **{profile['civil_status']}**\n"
            f"- **Recognized Legal Beneficiaries (RA 8291)**:\n{beneficiaries_list}\n"
            f"- **Total Periods with Paid Premiums (PPP)**: **{profile['total_ppp_years']} years** (First Day of Service: `{profile['first_day_of_service']}`)\n"
            f"- **Basic Monthly Salary**: **PHP {profile['basic_monthly_salary']:,.2f}** (Net Take-Home Pay: **PHP {profile['net_take_home_pay']:,.2f}**)\n\n"
            f"#### 📊 Last 12 Months Contribution Summary (9% EE / 12% ER)\n"
            f"- **Posted Months**: **{contribs['posted_months_count']} / {contribs['months_inspected']} months**\n"
            f"- **Total 12-Month Personal Share (9%)**: **PHP {contribs['total_personal_share_12m']:,.2f}**\n"
            f"- **Total 12-Month Government Share (12%)**: **PHP {contribs['total_government_share_12m']:,.2f}**"
            f"{unposted_alert}"
        )

    # -------------------------------------------------------------------------
    # CASE D: Phase 2 Authenticated — Loans & Reloan Simulation (`GSIS_Loans_Computation_Agent`)
    # -------------------------------------------------------------------------
    elif intent == "MEMBER_LOAN_SIMULATION_AND_BALANCES":
        requested_amt = _extract_salary_from_prompt(clean_prompt)
        profile = get_member_profile(authenticated_bp)
        loans_info = get_member_loans(authenticated_bp)
        sim = simulate_loan_application(
            bp_number=authenticated_bp,
            loan_type="MPL_FLEX",
            requested_amount=requested_amt,
            term_months=84,
        )
        mcp_tools_called.extend(
            [
                {"tool": "get_member_profile", "bp_number": authenticated_bp, "status": "SUCCESS"},
                {"tool": "get_member_loans", "bp_number": authenticated_bp, "status": "SUCCESS"},
                {"tool": "simulate_loan_application", "bp_number": authenticated_bp, "status": "SUCCESS"},
            ]
        )
        phase3_actions.append(COMING_SOON_ACTIONS["mpl_flex_apply"])

        loan_rows_md = ""
        for l in loans_info["loans"]:
            loan_rows_md += (
                f"- **`{l['loan_type']}` (`{l['loan_id']}`)**: Outstanding Balance **PHP {l['outstanding_balance']:,.2f}** "
                f"| Monthly Amortization: **PHP {l['monthly_amortization']:,.2f}** | Remaining Duration: **{l['remaining_months']} / {l['term_months']} months**\n"
            )
        if not loan_rows_md:
            loan_rows_md = "- *No active outstanding loans on record.*\n"

        # Pinpoint short answer based on what the user specifically asked
        q_lower = clean_prompt.lower()
        is_yn = _is_yes_no_question(clean_prompt)
        matched_specific_loan = None
        for l in loans_info["loans"]:
            if l["loan_id"].lower() in q_lower or (l["loan_type"] == "EMERGENCY_LOAN" and "emergency" in q_lower):
                matched_specific_loan = l
                break

        if is_yn and not any(w in q_lower for w in ["how much", "what is", "show", "list"]):
            if any(w in q_lower for w in ["can i", "am i eligible", "am i qualified", "reloan"]):
                can_reloan = sim["gaa_5000_threshold_passed"] and sim["estimated_net_proceeds"] > 0
                if can_reloan:
                    short_reply_text = (
                        f"🎯 **Direct Answer:** **Yes** — you are eligible to reloan up to **PHP {sim['gross_loan_amount']:,.2f}** (`MPL Flex`), "
                        f"yielding **PHP {sim['estimated_net_proceeds']:,.2f}** in estimated net proceeds."
                    )
                else:
                    short_reply_text = (
                        f"🎯 **Direct Answer:** **No** — your current net take-home pay or PPP does not meet the statutory reloan threshold."
                    )
            elif "emergency" in q_lower:
                if matched_specific_loan:
                    short_reply_text = (
                        f"🎯 **Direct Answer:** **Yes** — you have an active **`{matched_specific_loan['loan_type']}` (`{matched_specific_loan['loan_id']}`)** "
                        f"with an outstanding balance of **PHP {matched_specific_loan['outstanding_balance']:,.2f}**."
                    )
                else:
                    short_reply_text = "🎯 **Direct Answer:** **No** — you do not have an active Emergency Loan on record."
            else:
                count = loans_info["active_loans_count"]
                if count > 0:
                    loan_names = " & ".join(f"`{l['loan_type']}`" for l in loans_info["loans"])
                    plural = "s" if count > 1 else ""
                    short_reply_text = (
                        f"🎯 **Direct Answer:** **Yes** — you have **{count} active loan{plural}** ({loan_names}) "
                        f"totaling **PHP {loans_info['total_outstanding_balance']:,.2f}**."
                    )
                else:
                    short_reply_text = (
                        "🎯 **Direct Answer:** **No** — you currently have **0 active loans** (`PHP 0.00` outstanding balance)."
                    )
        elif matched_specific_loan:
            short_reply_text = (
                f"🎯 **Direct Answer:** Your outstanding balance for **`{matched_specific_loan['loan_type']}` (`{matched_specific_loan['loan_id']}`)** "
                f"is **PHP {matched_specific_loan['outstanding_balance']:,.2f}** "
                f"(with **{matched_specific_loan['remaining_months']} months** remaining at **PHP {matched_specific_loan['monthly_amortization']:,.2f}/month**)."
            )
        elif "balance" in q_lower and not any(w in q_lower for w in ["simulate", "reloan", "proceeds", "borrow"]):
            if loans_info["active_loans_count"] == 0:
                short_reply_text = f"🎯 **Direct Answer:** You currently have **PHP 0.00** in outstanding GSIS loan balances (`0 active loans`)."
            else:
                per_loan_str = " | ".join(
                    f"**{l['loan_type']} (`{l['loan_id']}`)**: **PHP {l['outstanding_balance']:,.2f}**"
                    for l in loans_info["loans"]
                )
                short_reply_text = (
                    f"🎯 **Direct Answer:** Your total outstanding loan balance is **PHP {loans_info['total_outstanding_balance']:,.2f}** "
                    f"({per_loan_str})."
                )
        else:
            short_reply_text = (
                f"🎯 **Direct Answer:** You can reloan a gross **MPL Flex** amount of **PHP {sim['gross_loan_amount']:,.2f}** ({sim['salary_multiplier_months']}× salary), "
                f"giving you **PHP {sim['estimated_net_proceeds']:,.2f} in estimated net take-home proceeds** after deducting your **PHP {sim['outstanding_offset']:,.2f}** existing loan balance and fees "
                f"(new monthly amortization: **PHP {sim['new_monthly_amortization']:,.2f}/month**)."
            )

        gaa_badge = (
            "✅ **PASSES GAA PHP 5,000 Net Take-Home Pay Threshold**"
            if sim["gaa_5000_threshold_passed"]
            else "⚠️ **BELOW GAA PHP 5,000 Net Take-Home Pay Threshold (Requires Lower Loan Amount)**"
        )

        reply_text = (
            f"### 💳 Active GSIS Loan Balances & Deterministic MPL Flex Reloan Simulation (`BP {authenticated_bp}`)\n"
            f"#### 1. Current Active Loan Ledger\n"
            f"{loan_rows_md}"
            f"- **Total Outstanding Balance**: **PHP {loans_info['total_outstanding_balance']:,.2f}**\n"
            f"- **Total Current Monthly Amortization**: **PHP {loans_info['total_monthly_amortization']:,.2f} / month**\n\n"
            f"#### 2. Deterministic MPL Flex Renewal / Reloan Computation (`Gemini 3.1 Pro` + Python Calculator)\n"
            f"Based on your **PPP of {profile['total_ppp_years']} years** and **Basic Monthly Salary of PHP {profile['basic_monthly_salary']:,.2f}**:\n"
            f"- **Maximum MPL Flex Entitlement ({sim['salary_multiplier_months']}x Salary Cap)**: **PHP {sim['max_loanable_entitlement']:,.2f}**\n"
            f"- **Gross Loan Amount Simulated**: **PHP {sim['gross_loan_amount']:,.2f}** ({sim['requested_term_months']} months @ {sim['interest_rate_annual']*100:.0f}% p.a.)\n"
            f"- **Less: Outstanding Loan Offset (`MPL_FLEX`)**: `- PHP {sim['outstanding_offset']:,.2f}`\n"
            f"- **Less: 2% Service Fee**: `- PHP {sim['service_fee_2pct']:,.2f}`\n"
            f"- **Less: MRI Protection Fee**: `- PHP {sim['mri_fee']:,.2f}`\n"
            f"- 💰 **Estimated Net Take-Home Loan Proceeds**: **PHP {sim['estimated_net_proceeds']:,.2f}**\n"
            f"- 📅 **New Monthly Amortization**: **PHP {sim['new_monthly_amortization']:,.2f} / month**\n"
            f"- **Post-Loan Net Pay Check**: **PHP {sim['projected_net_take_home_pay']:,.2f}** ({gaa_badge})\n\n"
            f"> {OFFICIAL_TENTATIVE_DISCLAIMER}"
        )

    # -------------------------------------------------------------------------
    # CASE E: Phase 2 Authenticated — Benefits, Retirement & APIR (`GSIS_Benefits_Transactions_Agent`)
    # -------------------------------------------------------------------------
    elif intent == "MEMBER_BENEFITS_AND_RETIREMENT":
        benefits = get_benefits_and_eligibility(authenticated_bp)
        txns = get_recent_transactions(authenticated_bp)
        mcp_tools_called.extend(
            [
                {"tool": "get_benefits_and_eligibility", "bp_number": authenticated_bp, "status": "SUCCESS"},
                {"tool": "get_recent_transactions", "bp_number": authenticated_bp, "status": "SUCCESS"},
            ]
        )
        phase3_actions.append(COMING_SOON_ACTIONS["apir_schedule"])
        calc = benefits["deterministic_ra8291_computation"]
        beneficiaries_str = ", ".join(benefits.get("legal_beneficiaries", []))

        q_lower = clean_prompt.lower()
        is_yn = _is_yes_no_question(clean_prompt)
        if is_yn and not any(w in q_lower for w in ["how much", "what is", "show"]):
            if "apir" in q_lower:
                if benefits.get("apir_status") == "ACTIVE_COMPLIANT":
                    short_reply_text = (
                        f"🎯 **Direct Answer:** **Yes** — your APIR status is **`ACTIVE_COMPLIANT`** "
                        f"(next due on **`{benefits['apir_next_due_date']}`**)."
                    )
                else:
                    short_reply_text = (
                        f"🎯 **Direct Answer:** **No** — your APIR status is **`{benefits['apir_status']}`** "
                        f"(next due on **`{benefits['apir_next_due_date']}`**)."
                    )
            else:
                is_retire_eligible = benefits.get("age", 0) >= 60 and calc.get("ppp_years", 0) >= 15
                if is_retire_eligible:
                    short_reply_text = (
                        f"🎯 **Direct Answer:** **Yes** — at **Age {benefits['age']}** with **{calc['ppp_years']} PPP years**, "
                        f"you qualify for RA 8291 retirement (**BMP: PHP {calc['final_bmp']:,.2f}/month**)."
                    )
                else:
                    short_reply_text = (
                        f"🎯 **Direct Answer:** **No** — you are currently **Age {benefits['age']}** with **{calc['ppp_years']} PPP years** "
                        f"(RA 8291 requires Age 60 + 15 PPP years; your projected BMP at Age 60 is **PHP {calc['final_bmp']:,.2f}/month**)."
                    )
        elif "apir" in q_lower and "option" not in q_lower and "pension" not in q_lower:
            short_reply_text = (
                f"🎯 **Direct Answer:** Your **APIR Status** is **`{benefits['apir_status']}`** with a next scheduled due date of "
                f"**`{benefits['apir_next_due_date']}`** (*{benefits['apir_birth_month_rule']}*)."
            )
        else:
            short_reply_text = (
                f"🎯 **Direct Answer:** Your deterministic **RA 8291 Basic Monthly Pension (BMP)** is **PHP {calc['final_bmp']:,.2f}/month** "
                f"(**Option 1 5-Yr Lump Sum**: **PHP {calc['option_1']['five_year_lump_sum']:,.2f}** | "
                f"**Option 2 18-Mo Cash Payment**: **PHP {calc['option_2']['eighteen_month_cash_payment']:,.2f}** + immediate monthly pension | "
                f"**APIR Due**: `{benefits['apir_next_due_date']}`)."
            )

        reply_text = (
            f"### 🏛️ RA 8291 Retirement Options, Survivorship & APIR Schedule (`BP {authenticated_bp}`)\n"
            f"- **Member**: **{benefits['member_name']}** | **Age**: **{benefits['age']}** | **Civil Status**: **{benefits['civil_status']}**\n"
            f"- **Recognized Legal Beneficiaries**: {beneficiaries_str}\n"
            f"- **APIR (Annual Pensioners Information Revalidation) Status**: **`{benefits['apir_status']}`** "
            f"(Next Due: **`{benefits['apir_next_due_date']}`** — *{benefits['apir_birth_month_rule']}*)\n\n"
            f"#### Deterministic RA 8291 Pension Computation (`BMP = 0.025 × (AMC + 700) × PPP`)\n"
            f"- **Formula Applied**: `{calc['formula_explanation']}`\n"
            f"- **Basic Monthly Pension (BMP)**: **PHP {calc['final_bmp']:,.2f} / month** *(90% AMC statutory cap: PHP {calc['max_bmp_cap_90pct']:,.2f})*\n"
            f"- **Option 1 (60-Month / 5-Year Lump Sum + Monthly Pension after 5 Years)**:\n"
            f"  - Upfront 5-Year Lump Sum: **PHP {calc['option_1']['five_year_lump_sum']:,.2f}**\n"
            f"  - Monthly Life Pension (Resumes after 5 years): **PHP {calc['option_1']['monthly_pension_after_5_years']:,.2f} / month**\n"
            f"- **Option 2 (18-Month Cash Payment + Immediate Monthly Life Pension)**:\n"
            f"  - Immediate 18-Month Cash Payment: **PHP {calc['option_2']['eighteen_month_cash_payment']:,.2f}**\n"
            f"  - Immediate Monthly Life Pension (Starts Month 1): **PHP {calc['option_2']['immediate_monthly_pension']:,.2f} / month**\n"
            f"- **Survivorship Spouse Pension (50% of BMP)**: **PHP {calc['survivorship_spouse_monthly_pension']:,.2f} / month** "
            f"| **Funeral Benefit**: **PHP {calc['funeral_benefit']:,.2f}**\n\n"
            f"> {OFFICIAL_TENTATIVE_DISCLAIMER}"
        )

    # -------------------------------------------------------------------------
    # CASE F: Phase 1 / General GSIS Policy & FAQ RAG (`GSIS_Policy_FAQ_Agent`)
    # -------------------------------------------------------------------------
    else:
        top_doc = citations[0] if citations else None
        if top_doc:
            first_para = top_doc["content"].split("\n\n")[0].strip()
            short_reply_text = f"🎯 **Direct Answer ({top_doc['title']}):** {first_para}"
        else:
            short_reply_text = "🎯 **Direct Answer:** Please see the official GSIS policy guidance below."

        bullet_points = []
        for idx, doc in enumerate(citations, 1):
            bullet_points.append(
                f"**{idx}. {doc['title']} (`{doc['doc_id']}` — {doc['category']})**\n"
                f"{doc['content']}\n"
                f"🔗 *Official Source*: [{doc['url']}]({doc['url']})"
            )
        joined_docs = "\n\n".join(bullet_points)
        reply_text = (
            f"### 📚 Official GSIS Policy & FAQ Guidance (`GSIS_Policy_FAQ_Agent`)\n\n"
            f"{joined_docs}\n\n"
            f"---\n"
            f"💡 *Tip: You can ask me for a **sample MPL Flex or Retirement calculation** by providing a salary (e.g., \"Estimate MPL Flex for PHP 45,000 salary and 15 years of service\"), or click **Member Login (Phase 2)** to inspect your personal GSIS records.*"
        )

    # Step 4: Google Cloud Model Armor Output Inspection (`sanitizeModelResponse`) for active Specialist Agent
    armor_out = sanitize_model_response(
        response_text=reply_text,
        authenticated_bp=authenticated_bp,
        agent_name=specialist_agent,
    )
    short_armor_out = sanitize_model_response(
        response_text=short_reply_text,
        authenticated_bp=authenticated_bp,
        agent_name=specialist_agent,
    )
    total_ms = round((time.perf_counter() - turn_start) * 1000, 2)

    return {
        "reply": armor_out["sanitized_response"],
        "short_reply": short_armor_out["sanitized_response"],
        "full_reply": armor_out["sanitized_response"],
        "agent_trace": {
            "router_agent": "GSIS_Concierge_Router (gemini-3.7-flash)",
            "specialist_agent": f"{specialist_agent} ({model_tier})",
            "agents_protected_by_model_armor": ALL_MULTI_AGENT_NAMES,
            "model_used": model_tier,
            "intent": intent,
            "authenticated_bp": authenticated_bp,
            "mcp_tools_called": mcp_tools_called,
            "total_latency_ms": total_ms,
        },
        "model_armor": {
            "input_inspection": specialist_armor_in,
            "output_inspection": armor_out,
            "enforced_across_agents": ALL_MULTI_AGENT_NAMES,
        },
        "citations": citations,
        "phase3_actions": phase3_actions,
        "requires_login_modal": requires_login_modal,
    }

"""
GSIS Mock Model Context Protocol (MCP) Server & Tool Registry
=============================================================
Implements the 6 Phase 2 Identity-Bound MCP tools (`bp_number` injected strictly
from server-side verified JWT claims) and 2 Phase 1 Public FAQ/Calculator tools:

Phase 1 Tools (Unauthenticated / Public):
  1. `search_gsis_faq_rag(query, category)`
  2. `calculate_sample_loan_or_pension(calc_type, basic_monthly_salary, ppp_years, age)`

Phase 2 Tools (Authenticated + OTP Verified — Identity-Bound `bp_number`):
  3. `get_member_profile(bp_number)`
  4. `get_contributions_summary(bp_number)`
  5. `get_member_loans(bp_number)`
  6. `simulate_loan_application(bp_number, loan_type, requested_amount, term_months)`
  7. `get_benefits_and_eligibility(bp_number)`
  8. `get_recent_transactions(bp_number)`
"""

import json
import re
from typing import Dict, Any, List, Optional
from .db_adapter import get_connection
from .calculators import (
    simulate_mpl_flex_reloan,
    calculate_ra8291_retirement,
    OFFICIAL_TENTATIVE_DISCLAIMER,
    COMING_SOON_ACTIONS,
)


def search_gsis_faq_rag(query: str, top_k: int = 4) -> Dict[str, Any]:
    """
    Retrieves top-matching official GSIS FAQ & policy documents from `gsis_faq_documents`
    using keyword + token overlap scoring with official source URL citations.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT doc_id, title, category, url, content, keywords_json FROM gsis_faq_documents")
    rows = cur.fetchall()
    conn.close()

    tokens = [
        t.lower()
        for t in re.findall(r"[a-zA-Z0-9]+", query.lower())
        if len(t) > 2 and t.lower() not in {"what", "how", "the", "for", "and", "can", "who", "are", "with", "gsis"}
    ]

    scored_docs = []
    for row in rows:
        doc = dict(row)
        keywords = json.loads(doc.get("keywords_json") or "[]")
        haystack = f"{doc['title']} {doc['category']} {' '.join(keywords)} {doc['content']}".lower()
        score = 0.0
        for tok in tokens:
            if tok in doc["title"].lower():
                score += 4.0
            if any(tok in kw.lower() for kw in keywords):
                score += 3.5
            if tok in doc["category"].lower():
                score += 2.0
            if tok in haystack:
                score += 1.5
        if score > 0:
            scored_docs.append((score, doc))

    scored_docs.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, d in scored_docs[:top_k]:
        results.append(
            {
                "doc_id": d["doc_id"],
                "title": d["title"],
                "category": d["category"],
                "url": d["url"],
                "content": d["content"],
                "relevance_score": round(score, 2),
            }
        )

    # Fallback to general overview if no keywords matched
    if not results and rows:
        for r in rows[:2]:
            d = dict(r)
            results.append(
                {
                    "doc_id": d["doc_id"],
                    "title": d["title"],
                    "category": d["category"],
                    "url": d["url"],
                    "content": d["content"],
                    "relevance_score": 1.0,
                }
            )

    return {
        "tool": "search_gsis_faq_rag",
        "query": query,
        "matches_count": len(results),
        "citations": results,
    }


def calculate_sample_loan_or_pension(
    calc_type: str = "mpl_flex",
    basic_monthly_salary: float = 45000.0,
    ppp_years: float = 15.0,
    age: int = 60,
) -> Dict[str, Any]:
    """
    Phase 1 Unauthenticated Sample Calculator for visitors who provide hypothetical salary/PPP figures.
    """
    if calc_type == "retirement":
        res = calculate_ra8291_retirement(
            amc=basic_monthly_salary,
            ppp_years=ppp_years,
            age=age,
        )
        res["tool"] = "calculate_sample_loan_or_pension"
        return res
    else:
        res = simulate_mpl_flex_reloan(
            basic_monthly_salary=basic_monthly_salary,
            ppp_years=ppp_years,
            requested_term_months=84,
            existing_loans=[],
        )
        res["tool"] = "calculate_sample_loan_or_pension"
        return res


def get_member_profile(bp_number: str) -> Dict[str, Any]:
    """
    MCP Tool 1: Retrieves member profile, civil status, legal beneficiaries, and APIR schedule.
    `bp_number` is strictly injected from the verified server-side JWT.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT bp_number, crn_masked, username, email, full_name, birth_date, age,
               gender, civil_status, legal_beneficiaries_json, mobile_masked,
               agency_name, agency_code, position_title, salary_grade,
               basic_monthly_salary, first_day_of_service, total_ppp_years,
               employment_status, member_category, net_take_home_pay,
               apir_status, apir_next_due_date, apir_birth_month_rule, is_preseeded
        FROM gsis_members WHERE bp_number = ?
        """,
        (bp_number,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"error": f"Member with BP {bp_number} not found"}

    data = dict(row)
    data["legal_beneficiaries"] = json.loads(data.pop("legal_beneficiaries_json", "[]"))
    data["tool"] = "get_member_profile"
    return data


def get_contributions_summary(bp_number: str) -> Dict[str, Any]:
    """
    MCP Tool 2: Retrieves member's 9% personal share & 12% government share ledger,
    total PPP years, and any unposted ERF flags.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT period_month, personal_share, government_share, ecc_share,
               posting_status, remarks, remitting_agency, posted_date
        FROM gsis_contributions
        WHERE bp_number = ?
        ORDER BY period_month DESC
        """,
        (bp_number,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    posted_rows = [r for r in rows if r["posting_status"] == "POSTED"]
    unposted_rows = [r for r in rows if r["posting_status"] != "POSTED"]
    total_ps_12m = round(sum(r["personal_share"] for r in posted_rows), 2)
    total_gs_12m = round(sum(r["government_share"] for r in posted_rows), 2)

    return {
        "tool": "get_contributions_summary",
        "bp_number": bp_number,
        "months_inspected": len(rows),
        "posted_months_count": len(posted_rows),
        "unposted_months_count": len(unposted_rows),
        "unposted_periods": unposted_rows,
        "total_personal_share_12m": total_ps_12m,
        "total_government_share_12m": total_gs_12m,
        "statutory_rates": {"employee_personal_share": "9%", "employer_government_share": "12%"},
        "ledger": rows,
        "phase3_action_cta": COMING_SOON_ACTIONS["erf_reconciliation"] if unposted_rows else None,
    }


def get_member_loans(bp_number: str) -> Dict[str, Any]:
    """
    MCP Tool 3: Retrieves all active GSIS loans, principal, interest rates,
    monthly amortization, outstanding balances, and remaining months.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT loan_id, loan_type, principal_amount, interest_rate_annual,
               term_months, remaining_months, monthly_amortization,
               outstanding_balance, arrears_amount, loan_status,
               granted_date, maturity_date
        FROM gsis_loans
        WHERE bp_number = ?
        ORDER BY outstanding_balance DESC
        """,
        (bp_number,),
    )
    loans = [dict(r) for r in cur.fetchall()]
    conn.close()

    total_outstanding = round(sum(l["outstanding_balance"] for l in loans if l["loan_status"] == "ACTIVE"), 2)
    total_monthly_amort = round(sum(l["monthly_amortization"] for l in loans if l["loan_status"] == "ACTIVE"), 2)

    return {
        "tool": "get_member_loans",
        "bp_number": bp_number,
        "active_loans_count": len(loans),
        "total_outstanding_balance": total_outstanding,
        "total_monthly_amortization": total_monthly_amort,
        "loans": loans,
    }


def simulate_loan_application(
    bp_number: str,
    loan_type: str = "MPL_FLEX",
    requested_amount: Optional[float] = None,
    term_months: int = 84,
) -> Dict[str, Any]:
    """
    MCP Tool 4: Runs the 100% deterministic Python MPL Flex Reloan & Net Proceeds Calculator
    using the member's actual salary, PPP years, and outstanding loans from the database.
    """
    profile = get_member_profile(bp_number)
    if "error" in profile:
        return profile
    loans_data = get_member_loans(bp_number)

    simulation = simulate_mpl_flex_reloan(
        basic_monthly_salary=float(profile["basic_monthly_salary"]),
        ppp_years=float(profile["total_ppp_years"]),
        requested_amount=requested_amount,
        requested_term_months=term_months,
        existing_loans=loans_data.get("loans", []),
        current_net_take_home_pay=float(profile["net_take_home_pay"]),
    )
    simulation["tool"] = "simulate_loan_application"
    simulation["bp_number"] = bp_number
    simulation["member_name"] = profile["full_name"]
    return simulation


def get_benefits_and_eligibility(bp_number: str) -> Dict[str, Any]:
    """
    MCP Tool 5: Retrieves the member's RA 8291 Option 1 & Option 2 Retirement / Life Insurance
    and APIR status, verified via the deterministic RA 8291 calculator.
    """
    profile = get_member_profile(bp_number)
    if "error" in profile:
        return profile

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT claim_id, benefit_type, law_basis, eligibility_status,
               estimated_bmp, option1_5yr_lump_sum, option2_18mo_cash_payment,
               cash_surrender_value, survivorship_spouse_pension,
               claim_status, notes
        FROM gsis_benefits_claims
        WHERE bp_number = ?
        """,
        (bp_number,),
    )
    claims = [dict(r) for r in cur.fetchall()]
    conn.close()

    deterministic_calc = calculate_ra8291_retirement(
        amc=float(profile["basic_monthly_salary"]),
        ppp_years=float(profile["total_ppp_years"]),
        age=int(profile["age"]),
    )

    return {
        "tool": "get_benefits_and_eligibility",
        "bp_number": bp_number,
        "member_name": profile["full_name"],
        "age": profile["age"],
        "civil_status": profile["civil_status"],
        "legal_beneficiaries": profile["legal_beneficiaries"],
        "apir_status": profile["apir_status"],
        "apir_next_due_date": profile["apir_next_due_date"],
        "apir_birth_month_rule": profile["apir_birth_month_rule"],
        "claims_records": claims,
        "deterministic_ra8291_computation": deterministic_calc,
        "disclaimer": OFFICIAL_TENTATIVE_DISCLAIMER,
        "phase3_action_cta": COMING_SOON_ACTIONS["apir_schedule"],
    }


def get_recent_transactions(bp_number: str) -> Dict[str, Any]:
    """
    MCP Tool 6: Retrieves recent GSIS transactions, loan disbursements, and claim statuses.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT txn_id, txn_date, txn_type, channel, amount, status, description
        FROM gsis_transactions
        WHERE bp_number = ?
        ORDER BY txn_date DESC
        """,
        (bp_number,),
    )
    txns = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {
        "tool": "get_recent_transactions",
        "bp_number": bp_number,
        "transactions_count": len(txns),
        "transactions": txns,
    }


def get_full_member_bundle(bp_number: str) -> Dict[str, Any]:
    """
    Helper for the UI "My GSIS Live Database & MCP Inspector" drawer to view all seeded tables.
    """
    return {
        "profile": get_member_profile(bp_number),
        "contributions": get_contributions_summary(bp_number),
        "loans": get_member_loans(bp_number),
        "loan_simulation": simulate_loan_application(bp_number),
        "benefits": get_benefits_and_eligibility(bp_number),
        "transactions": get_recent_transactions(bp_number),
    }


MCP_TOOLS_MANIFEST = [
    {
        "name": "search_gsis_faq_rag",
        "phase": "Phase 1 (Public)",
        "description": "Searches the 50 official scraped GSIS policy and FAQ documents with source citations.",
    },
    {
        "name": "calculate_sample_loan_or_pension",
        "phase": "Phase 1 (Public)",
        "description": "Runs deterministic sample MPL Flex or RA 8291 retirement calculation for unauthenticated users.",
    },
    {
        "name": "get_member_profile",
        "phase": "Phase 2 (Identity-Bound JWT)",
        "description": "Retrieves member profile, age, civil status, legal beneficiaries, salary, PPP, and APIR schedule.",
    },
    {
        "name": "get_contributions_summary",
        "phase": "Phase 2 (Identity-Bound JWT)",
        "description": "Retrieves 12-month 9% EE / 12% ER contribution ledger and unposted ERF flags.",
    },
    {
        "name": "get_member_loans",
        "phase": "Phase 2 (Identity-Bound JWT)",
        "description": "Retrieves active GSIS loans, outstanding balances, remaining months, and monthly amortizations.",
    },
    {
        "name": "simulate_loan_application",
        "phase": "Phase 2 (Identity-Bound JWT)",
        "description": "Executes deterministic Python MPL Flex reloan calculator with loan offset and net proceeds.",
    },
    {
        "name": "get_benefits_and_eligibility",
        "phase": "Phase 2 (Identity-Bound JWT)",
        "description": "Computes RA 8291 Basic Monthly Pension (BMP), Option 1 vs Option 2, Survivorship, and APIR status.",
    },
    {
        "name": "get_recent_transactions",
        "phase": "Phase 2 (Identity-Bound JWT)",
        "description": "Lists recent GSIS Touch / GWAPS disbursements, applications, and APIR logs.",
    },
]

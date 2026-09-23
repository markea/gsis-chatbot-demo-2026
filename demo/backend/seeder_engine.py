"""
Age- & Civil-Status-Consistent Synthetic GSIS Member Data Seeder & 25-User Quota Enforcement
============================================================================================
Implements:
  - Hard Limit of `MAX_MOCK_USERS = 25` for custom mock user registrations (`DemoQuotaExceededError`)
  - 3 Pre-Seeded Executive Personas (`maria.santos`, `juan.delacruz`, `rosa.reyes` — password `gsis2026`)
  - Age-bounded PPP (`PPP <= Age - 21`), Birth-Month APIR scheduling, and Civil-Status Legal Beneficiaries
"""

import json
import random
import hashlib
from datetime import date
from typing import Dict, Any, List, Optional

from .db_adapter import get_connection
from .calculators import calculate_ra8291_retirement

MAX_MOCK_USERS = 25

MONTH_NAMES = [
    "",
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]


class DemoQuotaExceededError(Exception):
    def __init__(self, current_count: int, max_allowed: int = MAX_MOCK_USERS):
        self.code = "DEMO_USER_LIMIT_REACHED"
        self.current_count = current_count
        self.max_allowed = max_allowed
        self.message = (
            f"Maximum limit of {max_allowed} custom mock users reached ({current_count}/{max_allowed}) "
            "for this demo environment. New mock user registration is disabled. "
            "Please sign in using one of the 3 pre-seeded demo personas (maria.santos, juan.delacruz, or rosa.reyes — password: gsis2026)."
        )
        super().__init__(self.message)


def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_custom_mock_user_count() -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM gsis_members WHERE is_preseeded = 0")
    cnt = int(cur.fetchone()["cnt"])
    conn.close()
    return cnt


def _derive_legal_beneficiaries(civil_status: str, full_name: str) -> List[str]:
    last_name = full_name.split()[-1]
    cs = civil_status.strip().lower()
    if cs == "married":
        return [
            f"Primary Legal Spouse: Roberto/Elena {last_name} (Survivorship 50% BMP Entitlement)",
            f"Primary Dependent Child: Lucas {last_name} (Age 14, Unmarried Minor)",
            f"Primary Dependent Child: Sofia {last_name} (Age 10, Unmarried Minor)",
        ]
    elif cs == "widowed":
        return [
            f"Primary Legal Heirs: Surviving Legitimate Children of {last_name} Family (Deceased Spouse Recorded)",
            f"Dependent Child / Beneficiary: Gabriel {last_name}",
        ]
    elif cs == "legally separated":
        return [
            f"Primary Legal Heirs: Legitimate Dependent Children ({last_name} Family)",
            "Secondary Legal Heirs: Surviving Parents (Spouse excluded per Legal Separation Decree)",
        ]
    else:
        return [
            f"Secondary Legal Heirs (Single Civil Status): Surviving Parents (Arturo & Corazon {last_name})",
            f"Contingent Legal Beneficiaries: Legitimate Siblings of {full_name}",
        ]


def _seed_member_tables(
    *,
    bp_number: str,
    crn_masked: str,
    username: str,
    email: str,
    password: str,
    full_name: str,
    birth_date: str,
    age: int,
    gender: str,
    civil_status: str,
    mobile_masked: str,
    agency_name: str,
    agency_code: str,
    position_title: str,
    salary_grade: int,
    basic_monthly_salary: float,
    first_day_of_service: str,
    total_ppp_years: float,
    employment_status: str,
    member_category: str,
    net_take_home_pay: float,
    apir_status: str,
    apir_next_due_date: str,
    apir_birth_month_rule: str,
    is_preseeded: int,
    unposted_month: Optional[str],
    loans_list: List[Dict[str, Any]],
) -> None:
    conn = get_connection()
    cur = conn.cursor()

    beneficiaries = _derive_legal_beneficiaries(civil_status, full_name)

    cur.execute(
        """
        INSERT OR REPLACE INTO gsis_members (
            bp_number, crn_masked, username, email, password_hash, full_name,
            birth_date, age, gender, civil_status, legal_beneficiaries_json,
            mobile_masked, agency_name, agency_code, position_title, salary_grade,
            basic_monthly_salary, first_day_of_service, total_ppp_years,
            employment_status, member_category, net_take_home_pay,
            apir_status, apir_next_due_date, apir_birth_month_rule, is_preseeded
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            bp_number, crn_masked, username, email, _hash_pw(password), full_name,
            birth_date, age, gender, civil_status, json.dumps(beneficiaries),
            mobile_masked, agency_name, agency_code, position_title, salary_grade,
            basic_monthly_salary, first_day_of_service, total_ppp_years,
            employment_status, member_category, net_take_home_pay,
            apir_status, apir_next_due_date, apir_birth_month_rule, is_preseeded,
        ),
    )

    # Clear and re-seed 12 months of contributions
    cur.execute("DELETE FROM gsis_contributions WHERE bp_number = ?", (bp_number,))
    periods = [
        "2026-08", "2026-07", "2026-06", "2026-05", "2026-04", "2026-03",
        "2026-02", "2026-01", "2025-12", "2025-11", "2025-10", "2025-09",
    ]
    ps = round(basic_monthly_salary * 0.09, 2)
    gs = round(basic_monthly_salary * 0.12, 2)
    for pm in periods:
        is_unposted = unposted_month == pm
        status = "UNPOSTED_ERF_PENDING_AAO" if is_unposted else "POSTED"
        remarks = (
            "Pending Agency Electronic Remittance File (ERF) reconciliation with AAO"
            if is_unposted
            else "Remitted & Posted via eBCS"
        )
        cur.execute(
            """
            INSERT INTO gsis_contributions
            (bp_number, period_month, personal_share, government_share, ecc_share, posting_status, remarks, remitting_agency, posted_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (bp_number, pm, ps, gs, 100.0, status, remarks, agency_code, "Pending" if is_unposted else f"{pm}-10"),
        )

    # Clear and re-seed loans
    cur.execute("DELETE FROM gsis_loans WHERE bp_number = ?", (bp_number,))
    for l in loans_list:
        cur.execute(
            """
            INSERT INTO gsis_loans
            (loan_id, bp_number, loan_type, principal_amount, interest_rate_annual,
             term_months, remaining_months, monthly_amortization, outstanding_balance,
             arrears_amount, loan_status, granted_date, maturity_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                l["loan_id"], bp_number, l["loan_type"], l["principal_amount"],
                l["interest_rate_annual"], l["term_months"], l["remaining_months"],
                l["monthly_amortization"], l["outstanding_balance"], 0.0,
                "ACTIVE", l["granted_date"], l["maturity_date"],
            ),
        )

    # Seed RA 8291 benefits summary
    cur.execute("DELETE FROM gsis_benefits_claims WHERE bp_number = ?", (bp_number,))
    ret_calc = calculate_ra8291_retirement(amc=basic_monthly_salary, ppp_years=total_ppp_years, age=age)
    cur.execute(
        """
        INSERT INTO gsis_benefits_claims
        (claim_id, bp_number, benefit_type, law_basis, eligibility_status,
         estimated_bmp, option1_5yr_lump_sum, option2_18mo_cash_payment,
         cash_surrender_value, survivorship_spouse_pension, claim_status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"CLM-{bp_number[-5:]}",
            bp_number,
            "RA 8291 Retirement & Compulsory Life Insurance (LEP)",
            "Republic Act No. 8291",
            "ELIGIBLE_NOW" if age >= 60 and total_ppp_years >= 15 else "FUTURE_ELIGIBLE_AT_AGE_60",
            ret_calc["final_bmp"],
            ret_calc["option_1"]["five_year_lump_sum"],
            ret_calc["option_2"]["eighteen_month_cash_payment"],
            round(basic_monthly_salary * total_ppp_years * 0.16, 2),
            ret_calc["survivorship_spouse_monthly_pension"],
            "ACTIVE_PENSION_LEDGER" if employment_status == "PENSIONER" else "PRE_RETIREMENT_PROJECTION",
            f"Birth-Month APIR Rule: {apir_birth_month_rule}",
        ),
    )

    # Seed recent transactions
    cur.execute("DELETE FROM gsis_transactions WHERE bp_number = ?", (bp_number,))
    cur.execute(
        """
        INSERT INTO gsis_transactions
        (txn_id, bp_number, txn_date, txn_type, channel, amount, status, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"TXN-{bp_number[-5:]}-01",
            bp_number,
            "2026-08-15",
            "EBCS_PREMIUM_REMITTANCE",
            "GWAPS / Agency eBCS",
            round(ps + gs, 2),
            "COMPLETED",
            f"Monthly 9% EE (PHP {ps:,.2f}) + 12% ER (PHP {gs:,.2f}) Remittance Posted",
        ),
    )

    conn.commit()
    conn.close()


def seed_preseeded_personas() -> None:
    """Seeds the 3 flagship executive personas (is_preseeded = 1)."""
    # 1. Maria Clara D. Santos (Active Teacher III, DepEd, Age 39, Married, 1 Unposted ERF)
    _seed_member_tables(
        bp_number="2016041822",
        crn_masked="006-****-****-1",
        username="maria.santos",
        email="maria.santos@deped.gov.ph",
        password="gsis2026",
        full_name="Maria Clara D. Santos",
        birth_date="1987-03-14",
        age=39,
        gender="Female",
        civil_status="Married",
        mobile_masked="0917-***-4821",
        agency_name="Department of Education (DepEd)",
        agency_code="DepEd-NCR",
        position_title="Teacher III",
        salary_grade=13,
        basic_monthly_salary=46725.00,
        first_day_of_service="2011-06-01",
        total_ppp_years=15.0,
        employment_status="ACTIVE",
        member_category="Active Regular Member",
        net_take_home_pay=31450.00,
        apir_status="NOT_YET_REQUIRED_ACTIVE_MEMBER",
        apir_next_due_date="2047-03-31 (Upon Retirement in Birth Month March)",
        apir_birth_month_rule="Scheduled every March (Birth Month: March) upon pensioner status",
        is_preseeded=1,
        unposted_month="2026-07",
        loans_list=[
            {
                "loan_id": "LN-MPL-2016041822",
                "loan_type": "MPL_FLEX",
                "principal_amount": 320000.00,
                "interest_rate_annual": 0.06,
                "term_months": 84,
                "remaining_months": 36,
                "monthly_amortization": 4674.74,
                "outstanding_balance": 142350.00,
                "granted_date": "2022-09-01",
                "maturity_date": "2029-09-01",
            },
            {
                "loan_id": "LN-EML-2016041822",
                "loan_type": "EMERGENCY_LOAN",
                "principal_amount": 20000.00,
                "interest_rate_annual": 0.06,
                "term_months": 36,
                "remaining_months": 14,
                "monthly_amortization": 608.44,
                "outstanding_balance": 8150.00,
                "granted_date": "2024-11-01",
                "maturity_date": "2027-11-01",
            },
        ],
    )

    # 2. Juan Miguel R. Dela Cruz (Retiring Engineer IV, DPWH, Age 60, Widowed, 34 yrs PPP)
    _seed_member_tables(
        bp_number="2001089311",
        crn_masked="006-****-****-8",
        username="juan.delacruz",
        email="juan.delacruz@dpwh.gov.ph",
        password="gsis2026",
        full_name="Juan Miguel R. Dela Cruz",
        birth_date="1966-08-22",
        age=60,
        gender="Male",
        civil_status="Widowed",
        mobile_masked="0918-***-9012",
        agency_name="Department of Public Works and Highways (DPWH)",
        agency_code="DPWH",
        position_title="Engineer IV",
        salary_grade=22,
        basic_monthly_salary=78500.00,
        first_day_of_service="1992-08-15",
        total_ppp_years=34.0,
        employment_status="ACTIVE_RETIRING",
        member_category="Optional Retirement Eligible (RA 8291 Age 60)",
        net_take_home_pay=58200.00,
        apir_status="INITIAL_ENROLLMENT_UPON_RETIREMENT",
        apir_next_due_date="2027-08-31 (Birth Month: August)",
        apir_birth_month_rule="Scheduled annually every August (Birth Month: August)",
        is_preseeded=1,
        unposted_month=None,
        loans_list=[
            {
                "loan_id": "LN-MPL-2001089311",
                "loan_type": "MPL_FLEX",
                "principal_amount": 250000.00,
                "interest_rate_annual": 0.06,
                "term_months": 60,
                "remaining_months": 16,
                "monthly_amortization": 4833.20,
                "outstanding_balance": 68400.00,
                "granted_date": "2023-01-15",
                "maturity_date": "2028-01-15",
            }
        ],
    )

    # 3. Rosa Elena V. Reyes (Old-Age Pensioner, DOF, Age 67, Single, APIR Due October 2026)
    _seed_member_tables(
        bp_number="1992031409",
        crn_masked="006-****-****-4",
        username="rosa.reyes",
        email="rosa.reyes.pensioner@gsis.gov.ph",
        password="gsis2026",
        full_name="Rosa Elena V. Reyes",
        birth_date="1959-10-12",
        age=67,
        gender="Female",
        civil_status="Single",
        mobile_masked="0917-***-3310",
        agency_name="Department of Finance (DOF - Retired)",
        agency_code="DOF-RET",
        position_title="Retired Chief Administrative Officer",
        salary_grade=24,
        basic_monthly_salary=48500.00,
        first_day_of_service="1986-04-01",
        total_ppp_years=27.6,
        employment_status="PENSIONER",
        member_category="RA 8291 Old-Age Retiree Pensioner",
        net_take_home_pay=33962.25,
        apir_status="DUE_OCTOBER_2026",
        apir_next_due_date="2026-10-31",
        apir_birth_month_rule="Mandatory Annual Revalidation every October (Birth Month: October) via GSIS Touch Facial Biometrics",
        is_preseeded=1,
        unposted_month=None,
        loans_list=[],
    )


def register_custom_mock_member(
    *,
    email: str,
    username: str,
    password: str,
    full_name: str,
    birth_date: str,
    gender: str,
    civil_status: str,
    mobile_number: str,
    agency_name: str,
    basic_monthly_salary: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Enforces the hard limit of `MAX_MOCK_USERS = 25` custom mock users (`DemoQuotaExceededError`)
    and dynamically seeds an age- & civil-status-consistent member across all 5 tables.
    """
    current_count = get_custom_mock_user_count()
    if current_count >= MAX_MOCK_USERS:
        raise DemoQuotaExceededError(current_count=current_count, max_allowed=MAX_MOCK_USERS)

    today = date(2026, 9, 23)
    try:
        bdate = date.fromisoformat(birth_date)
    except Exception:
        bdate = date(1984, 5, 15)
        birth_date = bdate.isoformat()

    age = today.year - bdate.year - ((today.month, today.day) < (bdate.month, bdate.day))
    age = max(22, min(80, age))

    # Strict Age-to-Service Consistency: PPP <= Age - 21
    max_ppp = max(1.0, float(age - 21))
    ppp_years = round(min(max_ppp, max(1.5, max_ppp * 0.72)), 1)
    start_year = today.year - int(ppp_years)
    first_day = f"{start_year}-{bdate.month:02d}-01"

    salary = round(basic_monthly_salary or random.choice([36619.0, 46725.0, 57347.0, 68415.0]), 2)
    bp_number = f"20{random.randint(10000000, 99999999)}"
    birth_month_name = MONTH_NAMES[bdate.month]

    agency_code = "GOV-PH"
    if "DepEd" in agency_name:
        agency_code = "DepEd"
    elif "DPWH" in agency_name:
        agency_code = "DPWH"
    elif "DOH" in agency_name:
        agency_code = "DOH"
    elif "SC" in agency_name:
        agency_code = "SC-PH"
    elif "DOF" in agency_name:
        agency_code = "DOF"

    loans_list = [
        {
            "loan_id": f"LN-MPL-{bp_number[-6:]}",
            "loan_type": "MPL_FLEX",
            "principal_amount": round(salary * 5, 2),
            "interest_rate_annual": 0.06,
            "term_months": 84,
            "remaining_months": 42,
            "monthly_amortization": round((salary * 5) * 0.0146, 2),
            "outstanding_balance": round(salary * 2.4, 2),
            "granted_date": "2023-06-01",
            "maturity_date": "2030-06-01",
        }
    ]

    _seed_member_tables(
        bp_number=bp_number,
        crn_masked=f"006-****-****-{random.randint(1, 9)}",
        username=username.strip(),
        email=email.strip(),
        password=password,
        full_name=full_name.strip(),
        birth_date=birth_date,
        age=age,
        gender=gender,
        civil_status=civil_status,
        mobile_masked=mobile_number[:4] + "-***-" + mobile_number[-4:],
        agency_name=agency_name,
        agency_code=agency_code,
        position_title="Senior Government Officer II",
        salary_grade=16,
        basic_monthly_salary=salary,
        first_day_of_service=first_day,
        total_ppp_years=ppp_years,
        employment_status="PENSIONER" if age >= 65 else "ACTIVE",
        member_category="RA 8291 Pensioner" if age >= 65 else "Active Regular Member",
        net_take_home_pay=round(salary * 0.68, 2),
        apir_status=f"DUE_{birth_month_name.upper()}_2026" if age >= 60 else "NOT_YET_REQUIRED_ACTIVE_MEMBER",
        apir_next_due_date=f"2026-{bdate.month:02d}-28 (Birth Month: {birth_month_name})",
        apir_birth_month_rule=f"Scheduled annually every {birth_month_name} (Birth Month: {birth_month_name}) via GSIS Touch",
        is_preseeded=0,
        unposted_month="2026-07",
        loans_list=loans_list,
    )

    new_count = get_custom_mock_user_count()
    return {
        "bp_number": bp_number,
        "username": username.strip(),
        "full_name": full_name.strip(),
        "age": age,
        "civil_status": civil_status,
        "total_ppp_years": ppp_years,
        "basic_monthly_salary": salary,
        "custom_mock_users_count": new_count,
        "max_custom_mock_users": MAX_MOCK_USERS,
    }

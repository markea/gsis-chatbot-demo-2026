"""
GSIS Gabay AI — Dual-Mode AlloyDB / SQLite Relational & Vector Schema Adapter
=============================================================================
Creates and manages the 6 core tables defined in `02_TDD_GSIS_CHATBOT_DEMO_MOCK_ARCHITECTURE.md`:
  1. `gsis_members`
  2. `gsis_contributions`
  3. `gsis_loans`
  4. `gsis_benefits_claims`
  5. `gsis_transactions`
  6. `gsis_faq_documents` (automatically populated with the 50 scraped official GSIS FAQs)
"""

import os
import json
import sqlite3
from pathlib import Path

DB_FILE_PATH = os.getenv(
    "GSIS_DEMO_DB_PATH",
    str(Path(__file__).resolve().parent.parent / "data" / "gsis_gabay_demo.sqlite3"),
)
FAQ_CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "gsis_official_faq_corpus.json"


def get_connection() -> sqlite3.Connection:
    Path(DB_FILE_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_database() -> None:
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS gsis_members (
            bp_number TEXT PRIMARY KEY,
            crn_masked TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            birth_date TEXT NOT NULL,
            age INTEGER NOT NULL,
            gender TEXT NOT NULL,
            civil_status TEXT NOT NULL,
            legal_beneficiaries_json TEXT NOT NULL,
            mobile_masked TEXT NOT NULL,
            agency_name TEXT NOT NULL,
            agency_code TEXT NOT NULL,
            position_title TEXT NOT NULL,
            salary_grade INTEGER NOT NULL,
            basic_monthly_salary REAL NOT NULL,
            first_day_of_service TEXT NOT NULL,
            total_ppp_years REAL NOT NULL,
            employment_status TEXT NOT NULL,
            member_category TEXT NOT NULL,
            net_take_home_pay REAL NOT NULL,
            apir_status TEXT NOT NULL,
            apir_next_due_date TEXT NOT NULL,
            apir_birth_month_rule TEXT NOT NULL,
            is_preseeded INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS gsis_contributions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bp_number TEXT NOT NULL,
            period_month TEXT NOT NULL,
            personal_share REAL NOT NULL,
            government_share REAL NOT NULL,
            ecc_share REAL NOT NULL,
            posting_status TEXT NOT NULL,
            remarks TEXT NOT NULL,
            remitting_agency TEXT NOT NULL,
            posted_date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS gsis_loans (
            loan_id TEXT PRIMARY KEY,
            bp_number TEXT NOT NULL,
            loan_type TEXT NOT NULL,
            principal_amount REAL NOT NULL,
            interest_rate_annual REAL NOT NULL,
            term_months INTEGER NOT NULL,
            remaining_months INTEGER NOT NULL,
            monthly_amortization REAL NOT NULL,
            outstanding_balance REAL NOT NULL,
            arrears_amount REAL NOT NULL,
            loan_status TEXT NOT NULL,
            granted_date TEXT NOT NULL,
            maturity_date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS gsis_benefits_claims (
            claim_id TEXT PRIMARY KEY,
            bp_number TEXT NOT NULL,
            benefit_type TEXT NOT NULL,
            law_basis TEXT NOT NULL,
            eligibility_status TEXT NOT NULL,
            estimated_bmp REAL NOT NULL,
            option1_5yr_lump_sum REAL NOT NULL,
            option2_18mo_cash_payment REAL NOT NULL,
            cash_surrender_value REAL NOT NULL,
            survivorship_spouse_pension REAL NOT NULL,
            claim_status TEXT NOT NULL,
            notes TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS gsis_transactions (
            txn_id TEXT PRIMARY KEY,
            bp_number TEXT NOT NULL,
            txn_date TEXT NOT NULL,
            txn_type TEXT NOT NULL,
            channel TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL,
            description TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS gsis_faq_documents (
            doc_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            url TEXT NOT NULL,
            content TEXT NOT NULL,
            keywords_json TEXT NOT NULL,
            scraped_at TEXT NOT NULL
        );
        """
    )

    # Seed 50 scraped official GSIS FAQ documents if empty
    cur.execute("SELECT COUNT(*) AS cnt FROM gsis_faq_documents")
    if int(cur.fetchone()["cnt"]) == 0 and FAQ_CORPUS_PATH.exists():
        raw = json.loads(FAQ_CORPUS_PATH.read_text(encoding="utf-8"))
        docs = raw.get("documents", []) if isinstance(raw, dict) else raw
        for d in docs:
            kw_raw = d.get("keywords", [])
            kw_list = kw_raw.split() if isinstance(kw_raw, str) else list(kw_raw)
            cur.execute(
                """
                INSERT OR REPLACE INTO gsis_faq_documents
                (doc_id, title, category, url, content, keywords_json, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    d["doc_id"],
                    d.get("title") or d.get("question_title", ""),
                    d.get("category", "GENERAL"),
                    d.get("url") or d.get("source_url", "https://www.gsis.gov.ph/"),
                    d.get("content") or d.get("official_answer_markdown", ""),
                    json.dumps(kw_list),
                    d.get("scraped_at", "2026-09-23T00:00:00Z"),
                ),
            )

    conn.commit()
    conn.close()

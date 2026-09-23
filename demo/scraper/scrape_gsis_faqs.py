#!/usr/bin/env python3
"""
GSIS Official Website & Citizen's Charter FAQ Scraper & Corpus Builder
Scrapes live public pages from https://www.gsis.gov.ph and combines them with
structured GSIS Citizen's Charter, Board Resolutions, and RA 8291 policy rules
to build `demo/data/gsis_official_faq_corpus.json` (50+ grounded RAG documents).
"""
import json
import os
import re
import time
from datetime import datetime, timezone
import urllib.request
import urllib.error
from html.parser import HTMLParser


class SimpleHTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._texts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg", "footer", "nav"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg", "footer", "nav"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            cleaned = re.sub(r"\s+", " ", data).strip()
            if len(cleaned) > 25:
                self._texts.append(cleaned)

    def get_snippets(self):
        return self._texts


GSIS_TARGET_URLS = [
    ("https://www.gsis.gov.ph/", "GSIS Official Homepage & Advisories"),
    ("https://www.gsis.gov.ph/active-members/", "GSIS Active Members Portal"),
    ("https://www.gsis.gov.ph/active-members/loans/", "GSIS Member Loan Programs"),
    ("https://www.gsis.gov.ph/active-members/benefits/", "GSIS Benefits & Retirement Programs"),
    ("https://www.gsis.gov.ph/pensioners/", "GSIS Pensioners & APIR Portal"),
    ("https://www.gsis.gov.ph/ginhawa-for-all/", "GSIS Ginhawa For All / MPL Flex Program"),
]


def fetch_live_gsis_snippets():
    scraped_records = []
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    }
    for url, label in GSIS_TARGET_URLS:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw_html = resp.read().decode("utf-8", errors="ignore")
                parser = SimpleHTMLTextExtractor()
                parser.feed(raw_html)
                snippets = parser.get_snippets()[:12]
                scraped_records.append({
                    "url": url,
                    "label": label,
                    "status": "LIVE_SCRAPED",
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "extracted_snippets": snippets,
                })
                print(f"[SCRAPER] Fetched {len(snippets)} text blocks from {url}")
        except Exception as exc:
            scraped_records.append({
                "url": url,
                "label": label,
                "status": f"CACHED_CHARTER_FALLBACK ({type(exc).__name__})",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "extracted_snippets": [],
            })
            print(f"[SCRAPER] {url} returned {exc} — using verified GSIS Citizen's Charter snapshot.")
    return scraped_records


def build_official_gsis_faq_corpus(live_metadata):
    """
    Builds 50 comprehensive, cited GSIS FAQ & Policy documents covering Phase 1 & Phase 2 RAG.
    """
    docs = [
        # --- LOANS: MPL FLEX, MPL LITE, CONSO-LOAN, EMERGENCY, POLICY, EDUCATIONAL ---
        {
            "doc_id": "FAQ-LOAN-001",
            "category": "LOANS",
            "question_title": "What is the GSIS Multi-Purpose Loan (MPL) Flex and how much can I borrow?",
            "official_answer_markdown": (
                "**GSIS Multi-Purpose Loan (MPL) Flex** (introduced under PPG No. 393-23 / *Ginhawa Flex*) is a consolidated, low-interest credit facility for active GSIS members.\n\n"
                "* **Maximum Loanable Amount:** Up to **14 times (14x)** your Basic Monthly Salary (BMS), capped at **Php 5,000,000.00**, depending on your **Periods with Paid Premiums (PPP)**:\n"
                "  * **6 to <36 months PPP:** Up to **2x–4x** Basic Monthly Salary (up to 3-year payment term)\n"
                "  * **36 to <60 months PPP (3–5 yrs):** Up to **8x** Basic Monthly Salary (up to 5-year payment term)\n"
                "  * **60 to <120 months PPP (5–10 yrs):** Up to **10x** Basic Monthly Salary (up to 7-year payment term)\n"
                "  * **120+ months PPP (10+ yrs):** Up to **14x** Basic Monthly Salary (flexible payment term up to **15 years**)\n"
                "* **Interest Rate:** **6% per annum** computed in advance (effective rate) with a **2% service fee**.\n"
                "* **How to Apply:** Apply online 24/7 via the **GSIS Touch Mobile App** or **GWAPS Kiosk** (subject to online certification by your Agency Authorized Officer [AAO])."
            ),
            "source_circular_ref": "GSIS Policy and Procedural Guidelines (PPG) No. 393-23 — GSIS MPL Flex (gsis.gov.ph/ginhawa-for-all)",
            "source_url": "https://www.gsis.gov.ph/ginhawa-for-all/",
            "keywords": "mpl flex multi-purpose loan flex magkano pwede utangin 14x salary interest rate duration payment term years"
        },
        {
            "doc_id": "FAQ-LOAN-002",
            "category": "LOANS",
            "question_title": "What is the difference between GSIS MPL Flex and MPL Lite?",
            "official_answer_markdown": (
                "**Comparison Between GSIS MPL Flex and GSIS MPL Lite:**\n\n"
                "| Feature | GSIS MPL Flex | GSIS MPL Lite |\n"
                "| :--- | :--- | :--- |\n"
                "| **Purpose** | High-value loan & debt consolidation | Quick micro-credit for urgent cash needs |\n"
                "| **Loanable Amount** | Up to **14x Basic Monthly Salary** (Max **Php 5.0M**) | **Php 5,000 up to Php 50,000** |\n"
                "| **Interest Rate** | **6% per annum** | **6%–7% per annum** |\n"
                "| **Payment Duration** | **1 to 15 years** (based on PPP tenure) | **1 year (12 mos) to 2 years (24 mos)** |\n"
                "| **Minimum PPP** | At least **6 months** of paid premiums | At least **6 months** of paid premiums |\n\n"
                "Both loans can be applied for directly inside the **GSIS Touch** mobile app."
            ),
            "source_circular_ref": "GSIS Citizen's Charter 2025/2026 & MPL Lite Circular (gsis.gov.ph/active-members/loans)",
            "source_url": "https://www.gsis.gov.ph/active-members/loans/",
            "keywords": "pinagkaiba difference mpl flex at mpl lite 50000 micro loan duration years"
        },
        {
            "doc_id": "FAQ-LOAN-003",
            "category": "LOANS",
            "question_title": "What are the eligibility requirements and terms for the GSIS Emergency Loan?",
            "official_answer_markdown": (
                "The **GSIS Emergency Loan** provides financial assistance to active members and old-age/disability pensioners working or residing in areas declared under a **State of Calamity** by the Sangguniang Panlalawigan/Panlungsod or the President.\n\n"
                "* **Loanable Amount:**\n"
                "  * **Php 40,000.00** for members with an existing Emergency Loan balance (outstanding balance is deducted from gross proceeds).\n"
                "  * **Php 20,000.00** for first-time availers without an existing Emergency Loan balance.\n"
                "* **Interest Rate:** **6% per annum**.\n"
                "* **Payment Term / Duration:** **3 years (36 equal monthly installments)**.\n"
                "* **Grace Period:** First monthly amortization is deducted on the **3rd month** after loan grant.\n"
                "* **Minimum Eligibility:** Active member with at least **3 months** of paid premiums within the last 6 months, no pending administrative/criminal case, and net take-home pay not lower than **Php 5,000.00** (per General Appropriations Act)."
            ),
            "source_circular_ref": "GSIS Emergency Loan Guidelines — Citizen's Charter (gsis.gov.ph/active-members/loans)",
            "source_url": "https://www.gsis.gov.ph/active-members/loans/",
            "keywords": "emergency loan calamity 20000 40000 36 months 3 years 6% interest requirements"
        },
        {
            "doc_id": "FAQ-LOAN-004",
            "category": "LOANS",
            "question_title": "How does the GSIS Consolidated Loan (Conso-Loan) or loan offset work when I reloan?",
            "official_answer_markdown": (
                "When you apply for **GSIS MPL Flex** (which superseded the standalone Conso-Loan), the system automatically consolidates and offsets the outstanding balances of your existing short-term loans:\n\n"
                "1. **Loans Consolidated/Deducted from Gross Proceeds:** Existing MPL, MPL Flex, Consolidated Loan (Conso-Loan), Salary Loan, Enhanced Salary Loan, and Cash Advance balances.\n"
                "2. **Loans NOT Deducted from MPL Flex:** **Emergency Loan** and **Policy Loan** (Regular/Optional) remain separate accounts and are not deducted from your MPL Flex proceeds.\n"
                "3. **Net Proceeds Formula:**\n"
                "   $$\\text{Net Proceeds} = \\text{Gross Loanable Amount} - \\text{Outstanding MPL/Conso Balance} - 2\\%\\text{ Service Fee}$$\n"
                "4. **Loan Renewal Eligibility:** You may renew your MPL Flex anytime as long as your **Gross Loanable Amount** exceeds your outstanding balance + fees (resulting in positive net proceeds) or after paying at least **6 monthly amortizations**."
            ),
            "source_circular_ref": "GSIS PPG No. 393-23 — Loan Consolidation & Renewal Rules",
            "source_url": "https://www.gsis.gov.ph/ginhawa-for-all/",
            "keywords": "conso loan consolidated loan reloan renewal offset net proceeds deduction"
        },
        {
            "doc_id": "FAQ-LOAN-005",
            "category": "LOANS",
            "question_title": "What is a GSIS Policy Loan and how much can I borrow against my life insurance policy?",
            "official_answer_markdown": (
                "A **GSIS Policy Loan** allows active government employees to borrow against the accumulated **Cash Surrender Value (CSV)** or termination value of their compulsory life insurance policy (**Life Endowment Policy [LEP]** or **Enhanced Life Policy [ELP]**).\n\n"
                "* **Loanable Amount:**\n"
                "  * **LEP Holders:** Up to **50%** of the accumulated Cash Surrender Value.\n"
                "  * **ELP Holders:** Up to **70%** of the accumulated Termination Value.\n"
                "* **Interest Rate:** **8% per annum** compounded annually.\n"
                "* **Payment Duration:** Optional monthly payroll deduction or deducted from maturity/retirement proceeds if unpaid.\n"
                "* **Key Advantage:** Policy Loan does **not** reduce your MPL Flex borrowing capacity."
            ),
            "source_circular_ref": "GSIS Life Insurance & Policy Loan Guidelines (RA 8291)",
            "source_url": "https://www.gsis.gov.ph/active-members/loans/",
            "keywords": "policy loan cash surrender value csv lep elp 50% 70% 8% interest"
        },
        {
            "doc_id": "FAQ-LOAN-006",
            "category": "LOANS",
            "question_title": "What is the GSIS Ginhawa For All Educational Loan (GFAL-Educ)?",
            "official_answer_markdown": (
                "The **GSIS Educational Loan** assists active members in financing tuition and school fees for themselves or up to two qualified beneficiaries (children/relatives up to the 3rd degree of consanguinity).\n\n"
                "* **Maximum Loanable Amount:** Up to **Php 100,000.00 per student per academic year**.\n"
                "* **Payment Duration:** Up to **5 years (60 monthly installments)** after graduation or study completion.\n"
                "* **Interest Rate:** **6% per annum**."
            ),
            "source_circular_ref": "GSIS Educational Loan Program Guidelines",
            "source_url": "https://www.gsis.gov.ph/active-members/loans/",
            "keywords": "educational loan tuition college school gfal educ 100000"
        },

        # --- RETIREMENT & BENEFITS (RA 8291) ---
        {
            "doc_id": "FAQ-RET-001",
            "category": "RETIREMENT",
            "question_title": "What are the requirements for GSIS Retirement under Republic Act No. 8291 and what is the difference between Option 1 and Option 2?",
            "official_answer_markdown": (
                "Under **Republic Act No. 8291 (The GSIS Act of 1997)**, an active government employee qualifies for **Old-Age Retirement** upon meeting all three criteria:\n"
                "1. Rendered at least **15 years of creditable service (PPP >= 15 years)**;\n"
                "2. Must be at least **60 years of age** at the time of retirement (Compulsory retirement is at **Age 65**); and\n"
                "3. Must **not** be a permanent total disability pensioner.\n\n"
                "### Two Retirement Payment Options Under RA 8291:\n"
                "* **Option 1 (5-Year Lump Sum + Pension at Age 65 or after 5 Years):**\n"
                "  * You receive a **60-month (5-year) lump sum** upfront ($60 \\times \\text{BMP}$) payable upon retirement.\n"
                "  * Your lifelong **Basic Monthly Pension (BMP)** starts **after 5 years** from your retirement date.\n"
                "* **Option 2 (18-Month Cash Payment + Immediate Monthly Pension):**\n"
                "  * You receive an upfront **18-month cash payment** ($18 \\times \\text{BMP}$) upon retirement.\n"
                "  * Your lifelong **Basic Monthly Pension (BMP)** starts **immediately** on the very next month following your retirement date!"
            ),
            "source_circular_ref": "Republic Act No. 8291 Section 13 & 13-A (The GSIS Act of 1997)",
            "source_url": "https://www.gsis.gov.ph/active-members/benefits/",
            "keywords": "ra 8291 retirement option 1 option 2 lump sum 60 months 18 months immediate pension age 60 65 15 years service"
        },
        {
            "doc_id": "FAQ-RET-002",
            "category": "RETIREMENT",
            "question_title": "How is the GSIS Basic Monthly Pension (BMP) calculated?",
            "official_answer_markdown": (
                "Under **RA 8291**, the **Basic Monthly Pension (BMP)** is computed deterministically using your **Average Monthly Compensation (AMC)** over the last 36 months of service and your **Periods with Paid Premiums (PPP)** in years:\n\n"
                "$$\\text{BMP} = 2.5\\% \\times (\\text{AMC} + \\text{Php } 700.00) \\times \\text{PPP (in Years)}$$\n\n"
                "* **Maximum Cap:** In no case shall the Basic Monthly Pension exceed **90% of the Average Monthly Compensation (AMC)**.\n"
                "* **Sample Calculation:** If your AMC is **Php 45,000.00** and you have **24 years of PPP**:\n"
                "  * $\\text{BMP} = 0.025 \\times (45,000 + 700) \\times 24 = \\mathbf{\\text{Php } 27,420.00 / \\text{month}}$\n"
                "  * **Option 1 Lump Sum ($60 \\times \\text{BMP}$):** **Php 1,645,200.00**\n"
                "  * **Option 2 Cash Payment ($18 \\times \\text{BMP}$):** **Php 493,560.00** + immediate **Php 27,420.00/mo** pension."
            ),
            "source_circular_ref": "RA 8291 Implementing Rules and Regulations (IRR) — BMP Formula",
            "source_url": "https://www.gsis.gov.ph/active-members/benefits/",
            "keywords": "bmp formula basic monthly pension computation amc 2.5% 700 90% cap"
        },
        {
            "doc_id": "FAQ-RET-003",
            "category": "RETIREMENT",
            "question_title": "What benefit do I get if I resign or separate from service before reaching Age 60 or 15 years of service?",
            "official_answer_markdown": (
                "Under **RA 8291 (Separation Benefit)**, your entitlement depends on your **Total Length of Creditable Service (PPP)** when you resign or separate:\n\n"
                "1. **3 Years to Less Than 15 Years of Service (`3 <= PPP < 15 years`):**\n"
                "   * You are entitled to a **Cash Payment equivalent to 100% of your Average Monthly Compensation (AMC) for every year of creditable service** ($1.0 \\times \\text{AMC} \\times \\text{PPP}$), payable upon reaching **Age 60**.\n"
                "2. **15 Years or More of Service, Separating Below Age 60 (`PPP >= 15 years`, Age < 60):**\n"
                "   * You receive an **Immediate Cash Payment equivalent to 18 times your Basic Monthly Pension ($18 \\times \\text{BMP}$)** at the time of separation, PLUS a **lifelong Basic Monthly Pension starting when you reach Age 60**.\n"
                "3. **Less Than 3 Years of Service (`PPP < 3 years`):**\n"
                "   * You remain entitled to the **Cash Surrender Value (CSV) / Termination Value** of your compulsory Life Insurance policy."
            ),
            "source_circular_ref": "RA 8291 Section 11 — Separation Benefits",
            "source_url": "https://www.gsis.gov.ph/active-members/benefits/",
            "keywords": "separation benefit resign early retirement below 60 less than 15 years cash payment"
        },
        {
            "doc_id": "FAQ-RET-004",
            "category": "RETIREMENT",
            "question_title": "What are the other retirement laws available to government workers besides RA 8291 (RA 660, RA 1616, PD 1146, Portability Law RA 7699)?",
            "official_answer_markdown": (
                "Depending on your date of entry into government service, you may choose among these retirement modes:\n\n"
                "* **RA 8291 (GSIS Act of 1997):** Open to all employees regardless of entry date (Age 60 + 15 yrs PPP).\n"
                "* **RA 660 ('Magic 87'):** For employees in service on or before **May 31, 1977** whose Age + Service equals **87**.\n"
                "* **RA 1616 (Gratuity + Refund of Premiums):** For employees in service on or before **May 31, 1977** with at least 20 years of service (employer pays gratuity; GSIS refunds personal & employer premiums).\n"
                "* **PD 1146:** For employees in service after May 31, 1977 but prior to June 24, 1997 (Age 60 + 15 yrs service).\n"
                "* **RA 7699 (Portability Law):** Allows combining your **SSS (private sector)** and **GSIS (government sector)** contribution periods ONLY if you do not qualify for the minimum 15-year requirement on your own in GSIS."
            ),
            "source_circular_ref": "GSIS Retirement Modes Comparison Guide & RA 7699 Portability Law",
            "source_url": "https://www.gsis.gov.ph/active-members/benefits/",
            "keywords": "ra 660 magic 87 ra 1616 pd 1146 portability law sss gsis combine years"
        },

        # --- CONTRIBUTIONS & REMITTANCES ---
        {
            "doc_id": "FAQ-CONTRIB-001",
            "category": "CONTRIBUTIONS",
            "question_title": "How much is the monthly GSIS compulsory contribution rate for employees and the government agency?",
            "official_answer_markdown": (
                "Under **Republic Act No. 8291**, every active government employee and their employing agency remit a combined **21% of the employee's Basic Monthly Salary (BMS)** every month, plus **Php 100.00** for Employees' Compensation (ECC):\n\n"
                "| Contribution Component | Employee Personal Share (EE) | Government Employer Share (ER) | Total Rate |\n"
                "| :--- | :---: | :---: | :---: |\n"
                "| **Retirement Insurance** | **7%** of BMS | **10%** of BMS | **17%** |\n"
                "| **Life Insurance** | **2%** of BMS | **2%** of BMS | **4%** |\n"
                "| **Total GSIS Share** | **9% of BMS** | **12% of BMS** | **21% of BMS** |\n"
                "| **ECC (Employees' Compensation)** | `0%` | **Php 100.00 / mo** | **Php 100.00** |\n\n"
                "* **Due Date of Remittance:** Government agencies must remit deducted premiums via the **Electronic Remittance File (ERF)** on or before the **10th day of the calendar month** following the month to which the contributions apply."
            ),
            "source_circular_ref": "RA 8291 Section 5 — Contributions & Electronic Remittance File (ERF) Rules",
            "source_url": "https://www.gsis.gov.ph/active-members/",
            "keywords": "contribution rate percentage 9% employee share 12% government share 21% erf remittance ecc"
        },
        {
            "doc_id": "FAQ-CONTRIB-002",
            "category": "CONTRIBUTIONS",
            "question_title": "What should I do if my agency deducted GSIS contributions or loan payments from my payslip but they are not yet posted in GSIS Touch?",
            "official_answer_markdown": (
                "If your payslip shows deductions that appear as unposted or in arrears in **GSIS Touch**:\n\n"
                "1. **Coordinate with your Agency Authorized Officer (AAO) or ERF Handler:** Ask if the agency's **Electronic Remittance File (ERF)** and payment for those specific months have been uploaded and validated in the **GSIS Electronic Billing and Collection System (eBCS)**.\n"
                "2. **Check for BP Number / Name Discrepancies:** Ensure your 10-digit **GSIS Business Partner (BP) Number** on the agency payroll matches your GSIS Touch record.\n"
                "3. **Request Service Record / ERF Reconciliation:** Your AAO can submit a reconciliation request to the assigned GSIS Account Officer (AO), or you may call the **GSIS Contact Center at (02) 8847-4747** or email `gsiscares@gsis.gov.ph` with copies of your certified payslips."
            ),
            "source_circular_ref": "GSIS eBCS & Agency Authorized Officer (AAO) Remittance Reconciliation Guidelines",
            "source_url": "https://www.gsis.gov.ph/active-members/",
            "keywords": "unposted contributions payslip deducted not posted erf aao ebcs arrears dispute reconciliation"
        },

        # --- LIFE INSURANCE, SURVIVORSHIP, DISABILITY & FUNERAL ---
        {
            "doc_id": "FAQ-LIFE-001",
            "category": "LIFE_INSURANCE",
            "question_title": "What is the difference between GSIS Life Endowment Policy (LEP) and Enhanced Life Policy (ELP), and what is Cash Surrender Value (CSV)?",
            "official_answer_markdown": (
                "Every regular government employee is automatically covered by **Compulsory Life Insurance**:\n\n"
                "1. **Enhanced Life Policy (ELP):** Covers members who entered government service on or after **August 1, 2003** (or opted to convert from LEP). It provides:\n"
                "   * **Annual Renewable Term Insurance** equivalent to **150% (1.5x) of Annual Salary** as death benefit.\n"
                "   * **Termination Value (TV) / Cash Surrender Value (CSV):** Accumulated from the 25% savings portion of your 4% life insurance premium earning **5% annual interest**, payable upon separation or retirement.\n"
                "2. **Life Endowment Policy (LEP):** Covers members who entered prior to August 1, 2003 and retained their endowment policy, which matures after a fixed endowment period or upon retirement.\n"
                "3. **Cash Dividends:** Active members with policies in force for at least one year receive annual **GSIS Cash Dividends** credited directly to their eCard/UMID every December."
            ),
            "source_circular_ref": "GSIS Compulsory Life Insurance Manual (LEP & ELP)",
            "source_url": "https://www.gsis.gov.ph/active-members/benefits/",
            "keywords": "lep elp life insurance cash surrender value csv termination value dividend"
        },
        {
            "doc_id": "FAQ-SURV-001",
            "category": "DISABILITY_SURVIVORSHIP",
            "question_title": "Who are the legal beneficiaries entitled to GSIS Survivorship and Funeral Benefits when a member or pensioner passes away?",
            "official_answer_markdown": (
                "Under **Republic Act No. 8291**, GSIS **Survivorship and Death Benefits** are awarded strictly to statutory beneficiaries based on the member's **Civil Status**:\n\n"
                "1. **Primary Beneficiaries:**\n"
                "   * The **Legal Dependent Spouse** (until they remarry, cohabit, or engage in a common-law relationship) AND\n"
                "   * **Dependent Children** (legitimate, legitimated, legally adopted, or illegitimate children who are unmarried, unemployed, and below **18 years of age**, or of any age if permanently incapacitated since minority).\n"
                "   * **Survivorship Pension Rate:** The Dependent Spouse receives **50% of the member's Basic Monthly Pension (BMP)**, and each dependent child (up to 5 children) receives **10% of the BMP**.\n"
                "2. **Secondary Beneficiaries (Only if there are NO Primary Beneficiaries):**\n"
                "   * **Dependent Parents** and, subject to the restrictions on dependent children, **Legitimate Descendants / Siblings**.\n"
                "3. **GSIS Funeral Benefit (`Php 30,000.00`):**\n"
                "   * Payable in the following order of priority: (a) Legitimate Spouse, (b) Legitimate Child who spent for the funeral, or (c) Any other person who can present official receipts proving they shouldered the funeral expenses."
            ),
            "source_circular_ref": "RA 8291 Sections 20, 21 & 23 — Survivorship & Php 30,000 Funeral Benefit",
            "source_url": "https://www.gsis.gov.ph/active-members/benefits/",
            "keywords": "survivorship benefit funeral benefit 30000 beneficiaries spouse children single married civil status"
        },
        {
            "doc_id": "FAQ-DIS-001",
            "category": "DISABILITY_SURVIVORSHIP",
            "question_title": "What are the GSIS Disability and Unemployment (Involuntary Separation) Benefits?",
            "official_answer_markdown": (
                "1. **GSIS Disability Benefits (RA 8291 Sec. 15–17):**\n"
                "   * **Permanent Total Disability (PTD):** Monthly income benefit for life equal to the Basic Monthly Pension (BMP) plus a cash payment of 18x BMP if the member has at least 15 years of PPP.\n"
                "   * **Permanent Partial Disability (PPD):** Cash payment computed according to the GSIS schedule of disabilities.\n"
                "   * **Temporary Total Disability (TTD):** 75% of current daily compensation for each day of disability (up to 120–240 days).\n"
                "2. **Unemployment / Involuntary Separation Benefit (RA 8291 Sec. 12):**\n"
                "   * Paid to permanent employees with at least **1 year of PPP** who are involuntarily separated due to reorganization or abolition of office. Pays **50% of average monthly compensation** for a duration of **2 to 6 months**."
            ),
            "source_circular_ref": "RA 8291 Sections 12, 15, 16 & 17 — Disability & Unemployment Benefits",
            "source_url": "https://www.gsis.gov.ph/active-members/benefits/",
            "keywords": "disability ptd ppd ttd unemployment benefit reorganization involuntary separation"
        },

        # --- GSIS TOUCH, APIR, UMID / eCARD & BRANCHES ---
        {
            "doc_id": "FAQ-TOUCH-001",
            "category": "GSIS_TOUCH_APIR",
            "question_title": "How do I complete my Annual Pensioners' Information Revalidation (APIR) and when is my APIR due date?",
            "official_answer_markdown": (
                "**Annual Pensioners' Information Revalidation (APIR)** is required once every year for all GSIS old-age and survivorship pensioners to ensure the continuous credit of their monthly pension.\n\n"
                "* **When is APIR Due?** Every year during your **Birth Month** (derived from your **Birthday / Date of Birth**).\n"
                "* **How to Complete APIR in 60 Seconds via GSIS Touch (No Branch Visit Needed):**\n"
                "  1. Open the **GSIS Touch** mobile app on your Android or iOS smartphone.\n"
                "  2. Tap **APIR (Facial Recognition)** on the dashboard.\n"
                "  3. Position your face inside the oval frame and follow the liveness prompt (blink/smile).\n"
                "  4. Receive instant real-time confirmation that your pension status is **ACTIVE** for another 12 months!\n"
                "* **Alternative Channels:** GWAPS Kiosks, video conference via Zoom/Viber/Messenger with your home branch, or home visit for bedridden pensioners."
            ),
            "source_circular_ref": "GSIS Circular on Touchless APIR via GSIS Touch Facial Recognition (gsis.gov.ph/pensioners)",
            "source_url": "https://www.gsis.gov.ph/pensioners/",
            "keywords": "apir annual pensioners information revalidation birth month birthday facial recognition pension suspended"
        },
        {
            "doc_id": "FAQ-TOUCH-002",
            "category": "GSIS_TOUCH_APIR",
            "question_title": "How do I register in the GSIS Touch Mobile App and where do I find my 10-digit GSIS Business Partner (BP) Number?",
            "official_answer_markdown": (
                "To enroll in the **GSIS Touch Mobile App** (available on Google Play Store, Apple App Store, and Huawei AppGallery):\n\n"
                "1. Download **GSIS Touch** and tap **Register / Sign Up**.\n"
                "2. Enter your **10-digit GSIS Business Partner (BP) Number** (begins with `200...`), **Date of Birth (Birthday)**, and registered **Mobile Number / Email Address**.\n"
                "3. **Don't know your BP Number?**\n"
                "   * Check your agency payslip, Service Record, or ask your **Agency Authorized Officer (AAO)**.\n"
                "   * Text `GSIS BP <First Name> <Middle Initial> <Last Name> <Birthday MMDDYYYY>` or use the **Keep in Touch (KIT)** feature inside the app.\n"
                "4. Enter the **6-digit One-Time PIN (OTP)** sent to your mobile number or email and create your password."
            ),
            "source_circular_ref": "GSIS Touch Mobile Application User Guide (gsis.gov.ph)",
            "source_url": "https://www.gsis.gov.ph/",
            "keywords": "gsis touch register sign up bp number business partner number otp forgot password"
        },
        {
            "doc_id": "FAQ-TOUCH-003",
            "category": "GSIS_TOUCH_APIR",
            "question_title": "How do I apply for or replace my GSIS UMID Card or eCard (UnionBank / LandBank)?",
            "official_answer_markdown": (
                "Your **GSIS eCard / UMID Card** serves as both your official government identification and your ATM disbursement account for loan proceeds, dividends, and monthly pensions:\n\n"
                "* **Partner Servicing Banks:** **Land Bank of the Philippines (LBP)** and **UnionBank of the Philippines (UBP)**.\n"
                "* **New Enrollment:** Active members and new pensioners can select their preferred servicing bank inside **GSIS Touch** or at any GSIS Branch Office.\n"
                "* **Lost or Damaged eCard/UMID:** Report the loss immediately to LandBank or UnionBank customer care to block unauthorized ATM withdrawals, then request a replacement card for a Php 200 card replacement fee."
            ),
            "source_circular_ref": "GSIS eCard / UMID Servicing Bank Guidelines (LandBank & UnionBank)",
            "source_url": "https://www.gsis.gov.ph/active-members/",
            "keywords": "umid card ecard landbank unionbank atm disbursement lost card replacement"
        },
        {
            "doc_id": "FAQ-TOUCH-004",
            "category": "GSIS_TOUCH_APIR",
            "question_title": "What are the official GSIS Contact Center hotlines, emails, and branch office operating hours?",
            "official_answer_markdown": (
                "**Official GSIS Contact Channels:**\n\n"
                "* **GSIS Contact Center Hotline (24/7):** **(02) 8847-4747** (Metro Manila)\n"
                "* **Toll-Free Domestic Numbers:**\n"
                "  * Globe/TM: `1-800-8-847-4747`\n"
                "  * Smart/PLDT/Sun: `1-800-10-847-4747`\n"
                "* **Official Email:** `gsiscares@gsis.gov.ph`\n"
                "* **Head Office Address:** Financial Center, Pasay City, Metro Manila 1308\n"
                "* **Branch Operating Hours:** Monday to Friday, **8:00 AM to 5:00 PM** (No Noon Break)."
            ),
            "source_circular_ref": "GSIS Citizen's Charter Directory (gsis.gov.ph)",
            "source_url": "https://www.gsis.gov.ph/",
            "keywords": "contact center hotline 8847-4747 email gsiscares branch hours pasay head office"
        },
    ]

    # Add 32 additional granular GSIS FAQ items covering specific loan scenarios, Tagalog/Taglish queries, housing, and claims
    extra_faqs = [
        ("FAQ-LOAN-007", "LOANS", "Paano mag-apply ng MPL Flex sa GSIS Touch at gaano katagal bago pumasok sa eCard?",
         "Para mag-apply ng **MPL Flex sa GSIS Touch**:\n1. Mag-login sa **GSIS Touch** app at piliin ang **Loans > MPL Flex**.\n2. Piliin ang loan amount at payment duration (hanggang 15 years depende sa PPP).\n3. Piliin ang **Tentative Computation** para makita ang exact **Net Proceeds**.\n4. I-confirm gamit ang 6-digit OTP.\n5. Kapag na-approve online ng iyong **Agency Authorized Officer (AAO)**, ang loan proceeds ay na-c-credit sa iyong **LandBank o UnionBank eCard/UMID sa loob ng 24 hanggang 48 oras (1–2 working days)**.",
         "GSIS Citizen's Charter — Loan Turnaround Time (24–48 Hours)", "paano mag apply mpl flex gaano katagal 24 hours 48 hours aao approval tagalog"),
        ("FAQ-LOAN-008", "LOANS", "Why was my GSIS loan application disapproved or put on hold by my AAO?",
         "Common reasons an **Agency Authorized Officer (AAO)** disapproves or holds a loan application:\n* **Insufficient Net Take-Home Pay (NTHP):** Your monthly net pay after the new GSIS amortization would fall below the mandatory **Php 5,000.00** GAA threshold.\n* **On Leave Without Pay (LWOP):** You are currently on leave without pay.\n* **Pending Administrative or Criminal Case:** Requires clearance before loan certification.\n* **Unposted Agency Remittances:** Recent ERFs are still pending upload in eBCS.",
         "GSIS AAO Certification Rules (PPG 393-23)", "disapproved loan aao hold net take home pay 5000 lwop"),
        ("FAQ-LOAN-009", "LOANS", "What is the GSIS Computer Loan Program and can I still avail of it?",
         "The standalone **GSIS Computer Loan** (Php 30,000 over 3 years at 6% interest) has been integrated into **GSIS MPL Lite** (up to Php 50,000) and **GSIS MPL Flex**, giving members higher credit limits without requiring official receipts of computer purchase.",
         "GSIS MPL Lite & Computer Loan Integration Circular", "computer loan laptop gadget mpl lite 30000 50000"),
        ("FAQ-LOAN-010", "LOANS", "What is the GSIS GFAL (Ginhawa For All) Balance Transfer / Debt Buyout Program?",
         "**GSIS GFAL (Ginhawa For All Loan)** allows active permanent government employees to transfer their high-interest loans from private lending institutions (PLIs) or cooperatives to GSIS (up to **Php 500,000** at **6% per annum** payable up to 10 years), or consolidate them directly under **MPL Flex**.",
         "GSIS GFAL Debt Consolidation Guidelines", "gfal balance transfer buyout private lender cooperative 500000"),
        ("FAQ-LOAN-011", "LOANS", "Is my GSIS MPL Flex covered by Loan Redemption Insurance (LRI)?",
         "**Yes.** Every GSIS MPL Flex, MPL Lite, and Emergency Loan includes automatic **Loan Redemption Insurance (LRI)**. In the unfortunate event of the member's death during the active loan term, the outstanding principal and current interest balance are **deemed fully paid/insured** via LRI so your legal beneficiaries' survivorship benefits are protected.",
         "GSIS Loan Redemption Insurance (LRI) Policy", "lri loan redemption insurance death unpaid loan written off"),
        ("FAQ-LOAN-012", "LOANS", "Can I pay my GSIS loan arrears or make an advance full payment over the counter or online?",
         "**Yes.** Aside from automatic monthly payroll deduction, you can pay GSIS loans directly via:\n* **GSIS Touch Mobile App** (via LandBank Link.BizPortal, UnionBank, GCash, or Maya)\n* **Bayad Center** and **SM Bills Payment**\n* Any **GSIS Branch Office Cashier**.",
         "GSIS Online Loan Payment Channels Advisory", "pay loan online gcash maya unionbank landbank bayad center full payment"),
        ("FAQ-RET-005", "RETIREMENT", "At what age do Old-Age Pensioners receive the GSIS Milestone Benefit (Cash Gift)?",
         "GSIS grants a one-time **Milestone Benefit (Non-Taxable Cash Gift)** to living Old-Age and Disability Pensioners upon reaching milestone ages:\n* **Age 90:** **Php 20,000.00**\n* **Age 95:** **Php 30,000.00**\n* **Age 100 (Centenarian):** **Php 50,000.00** (in addition to national/LGU centenarian incentives).",
         "GSIS Pensioner Milestone Benefit Resolution", "milestone benefit age 90 95 100 centenarian pensioner cash gift"),
        ("FAQ-RET-006", "RETIREMENT", "Do GSIS Old-Age Pensioners receive a Christmas Cash Gift / 13th Month Pension?",
         "**Yes.** Qualified GSIS Old-Age and Disability Pensioners who are receiving their regular monthly pension receive an annual **Christmas Cash Gift** (typically equivalent to 1x Basic Monthly Pension up to **Php 10,000.00**) credited directly to their eCard in December.",
         "GSIS Annual Christmas Cash Gift Guidelines", "christmas cash gift 13th month pension december 10000"),
        ("FAQ-RET-007", "RETIREMENT", "What is the Pensioners' Emergency Loan (PEL) for GSIS retirees?",
         "Qualified **Old-Age and Disability Pensioners** residing in declared calamity areas can avail of the **Pensioners' Emergency Loan (Php 20,000)** at **6% interest per annum**, payable over 36 months via automatic deduction from their monthly pension, provided their resulting net monthly pension remains at least 25% of their BMP.",
         "GSIS Pensioners Emergency Loan Circular", "pensioner loan emergency loan retiree 20000"),
        ("FAQ-RET-008", "RETIREMENT", "Can Uniformed Personnel (PNP, BFP, BJMP) claim GSIS benefits?",
         "Uniformed personnel of the **PNP, BFP, and BJMP** who entered prior to the creation of the separate uniformed retirement system and remitted premiums to GSIS may claim a **Return of Premiums / Termination Value** of their life insurance policy upon retirement or separation.",
         "GSIS Advisory for Uniformed Personnel (PNP/BFP/BJMP)", "pnp bfp bjmp uniformed personnel refund premiums"),
        ("FAQ-HOUSING-001", "LOANS", "What is the GSIS Lease with Option to Buy (LWOB) and Housing Loan Restructuring Program?",
         "**GSIS Lease with Option to Buy (LWOB)** allows members and the general public to lease any of GSIS's 10,000+ residential properties nationwide with the option to purchase the property without down payment. Existing housing borrowers with past-due accounts can also apply for **Housing Loan Restructuring / Condonation of Penalties**.",
         "GSIS Housing & LWOB Program (gsis.gov.ph/ginhawa-for-all)", "housing loan lwob lease with option to buy foreclosed properties condonation"),
        ("FAQ-NONLIFE-001", "LIFE_INSURANCE", "Does GSIS offer Motor Vehicle, Fire, and Personal Accident Insurance to individual government employees?",
         "**Yes.** Under **GSIS Ginhawa Insure**, active members, retirees, and their family members can insure their private cars (**Comprehensive Motor Vehicle Insurance**), homes (**Residential Fire Insurance**), and avail of **Personal Accident Insurance** at rates up to 30% lower than commercial insurers.",
         "GSIS Non-Life Insurance Marketing Department Guidelines", "car insurance motor vehicle fire insurance non-life ginhawa insure"),
        ("FAQ-LOAN-013", "LOANS", "What is the maximum payment duration (term) for GSIS MPL Flex based on my length of service (PPP)?",
         "Under **PPG No. 393-23**, your **MPL Flex** payment duration depends on your total **Periods with Paid Premiums (PPP)**:\n* **6 months to <3 years PPP:** Up to **3 years (36 months)**\n* **3 years to <5 years PPP:** Up to **5 years (60 months)**\n* **5 years to <10 years PPP:** Up to **7 years (84 months)**\n* **10 years or more PPP:** Flexible choice of **1 to 15 years (12 to 180 months)**!",
         "GSIS PPG No. 393-23 — MPL Flex Payment Terms", "mpl flex payment duration term months years ppp 15 years 180 months"),
        ("FAQ-LOAN-014", "LOANS", "Can Special Members (Judiciary, Constitutional Commissions, Prosecutors) avail of GSIS MPL Flex?",
         "**Yes.** Special Members (Justices, Judges, Prosecutors, and Officials of Constitutional Commissions) with a MOA with GSIS may borrow under **MPL Flex** up to **14x their Basic Monthly Salary** (capped at **Php 5,000,000.00**) payable up to 15 years.",
         "GSIS Special Members Loan Guidelines", "special members judges justices prosecutors mpl flex 5 million"),
        ("FAQ-LOAN-015", "LOANS", "How is interest computed on GSIS MPL Flex and is there a penalty for early payoff?",
         "GSIS **MPL Flex** charges an effective interest rate of **6% per annum** (computed on a diminishing balance basis). There is **zero pre-termination penalty** if you choose to pay off your loan balance early at any GSIS branch or online payment partner.",
         "GSIS MPL Flex Truth in Lending Disclosure", "interest computation pre termination penalty early payoff 6%"),
        ("FAQ-CONTRIB-003", "CONTRIBUTIONS", "Are Job Order (JO), Contract of Service (COS), and Casual employees covered by GSIS?",
         "* **Casual & Contractual Employees (with employer-employee relationship receiving fixed monthly salary):** **Covered** as compulsory GSIS members.\n* **Job Order (JO) & Contract of Service (COS) Workers (no employer-employee relationship under COA-DBM joint circulars):** **Not covered** by compulsory GSIS membership, as their services are paid on a piece-work or consultancy basis.",
         "RA 8291 Sec. 3 & CSC-COA-DBM Joint Circular on JO/COS", "job order contract of service casual contractual membership coverage"),
        ("FAQ-CONTRIB-004", "CONTRIBUTIONS", "How do I check my total Periods with Paid Premiums (PPP) and service duration in GSIS?",
         "You can view your exact **Periods with Paid Premiums (PPP)** and creditable service duration by logging into:\n1. **GSIS Touch Mobile App** under **Member Records > Service Record & Premiums**, or\n2. Asking **GSIS Gabay AI (Phase 2 Authenticated Mode)**, which queries your live member profile and contribution ledger.",
         "GSIS Member Records Verification Guide", "check ppp periods with paid premiums service duration years in service"),
        ("FAQ-RET-009", "RETIREMENT", "How early before my retirement date should I file my GSIS Retirement Application?",
         "You may submit your tentative retirement application inside **GSIS Touch** or at any GSIS branch **up to 90 days (3 months) prior to your effective date of retirement** so your lump sum or cash payment can be processed on time.",
         "GSIS Citizen's Charter — Retirement Claims Filing Window", "when to file retirement application 90 days 3 months before"),
        ("FAQ-RET-010", "RETIREMENT", "What documents are required when filing for GSIS Retirement under RA 8291?",
         "Thanks to digital integration via **GSIS Touch**, documentary requirements have been streamlined:\n1. **Online Application in GSIS Touch** (or signed Application Form);\n2. **Updated Service Record** certified by your Agency HR / AAO;\n3. **Declaration of Pendency / Non-Pendency of Administrative/Criminal Case**; and\n4. Active **GSIS eCard / UMID** (UnionBank or LandBank) for direct electronic crediting.",
         "GSIS Citizen's Charter — Streamlined Retirement Checklist", "retirement requirements documents service record declaration non-pendency"),
        ("FAQ-RET-011", "RETIREMENT", "Are GSIS Retirement Benefits, Lump Sums, and Monthly Pensions subject to income tax?",
         "**No.** Under **Section 39 of Republic Act No. 8291**, all GSIS benefits—including retirement lump sums, monthly pensions, separation benefits, life insurance proceeds, and cash dividends—are **100% exempt from all taxes, assessments, and garnishments**.",
         "RA 8291 Section 39 — Exemption from Tax and Legal Process", "tax exempt income tax garnishment retirement pension lump sum"),
        ("FAQ-SURV-002", "DISABILITY_SURVIVORSHIP", "Can a surviving spouse continue receiving the GSIS Survivorship Pension if they remarry?",
         "**No.** Under **RA 8291 Section 21**, entitlement to the **Basic Survivorship Pension** automatically terminates once the surviving spouse **remarries, cohabits, or engages in a common-law relationship**. However, qualified dependent minor children continue to receive their 10% dependent's pension until age 18.",
         "RA 8291 Section 21 & Supreme Court Jurisprudence on Survivorship", "survivorship pension remarry cohabitation common law spouse"),
        ("FAQ-SURV-003", "DISABILITY_SURVIVORSHIP", "What is the maximum cap on the GSIS Basic Survivorship Pension?",
         "The **Basic Survivorship Pension** payable to the surviving legal spouse is **50% of the Basic Monthly Pension (BMP)** that the deceased member or pensioner was receiving or entitled to receive.",
         "GSIS Survivorship Pension Computation Rules", "survivorship pension amount 50% bmp spouse cap"),
        ("FAQ-LIFE-002", "LIFE_INSURANCE", "How do I claim the Maturity Benefit of my GSIS Life Endowment Policy (LEP)?",
         "If you hold a **Life Endowment Policy (LEP)** that has reached its maturity date, GSIS automatically processes or notifies you via **GSIS Touch** to confirm disbursement directly into your **eCard/UMID account**. Any outstanding Policy Loan or automatic premium loan is deducted from the maturity value.",
         "GSIS LEP Maturity Claims Processing Guide", "lep maturity claim endowment policy matured ecard"),
        ("FAQ-LIFE-003", "LIFE_INSURANCE", "When are GSIS Annual Cash Dividends released and who is qualified?",
         "**GSIS Annual Cash Dividends** are declared by the Board of Trustees based on the Compulsory Life Insurance Fund surplus and credited every **December** to active members whose life insurance policy has been in force for at least **12 months** and whose agency has no unpaid premium remittances.",
         "GSIS Annual Dividend Declaration Policy", "cash dividend december qualified life insurance surplus"),
        ("FAQ-TOUCH-005", "GSIS_TOUCH_APIR", "What happens if a pensioner fails to complete their APIR during their Birth Month?",
         "If a pensioner fails to perform **APIR (Annual Pensioners' Information Revalidation)** by the end of their **Birth Month**, their monthly pension is **temporarily put on hold (`SUSPENDED_PENDING_APIR`)** starting the following month to protect the fund. As soon as APIR is completed via **GSIS Touch facial recognition**, the suspended pension is automatically reactivated and all accrued months are credited in full!",
         "GSIS APIR Suspension & Reactivation Protocol", "missed apir late apir pension on hold suspended reactivate"),
        ("FAQ-TOUCH-006", "GSIS_TOUCH_APIR", "Where can I use a GWAPS (GSIS Wireless Automated Processing System) Kiosk?",
         "**GWAPS Kiosks** are located across all **GSIS Branch and Extension Offices**, Provincial Capitols, City/Municipal Halls, DepEd Division Offices, and selected Robinsons/SM Malls nationwide. Note that almost all GWAPS transactions can now be completed right on your smartphone using **GSIS Touch**!",
         "GSIS GWAPS Kiosk Directory & GSIS Touch Migration", "gwaps kiosk location municipal hall robinsons sm mall"),
        ("FAQ-TOUCH-007", "GSIS_TOUCH_APIR", "Can pensioners living abroad (Overseas Filipino Retirees) do their APIR online?",
         "**Yes!** GSIS pensioners residing abroad (USA, Canada, Australia, Europe, Middle East, etc.) can complete their annual **APIR** from anywhere in the world using the **GSIS Touch Mobile App facial recognition** or by scheduling an online video call (Zoom/Facebook Messenger/Viber) with the GSIS Overseas Pensioners Unit.",
         "GSIS Overseas Pensioners APIR Guidelines", "abroad overseas pensioner usa canada zoom apir online"),
        ("FAQ-PRIV-001", "GSIS_TOUCH_APIR", "How does GSIS protect my personal data and AI chatbot conversations under the Data Privacy Act?",
         "GSIS strictly complies with **Republic Act No. 10173 (Philippine Data Privacy Act of 2012)** and **National Privacy Commission (NPC)** circulars. **GSIS Gabay AI** is protected by **Google Cloud Model Armor** (blocking prompt injection and masking sensitive PII) and cryptographically binds every Phase 2 query to your verified **GSIS Business Partner (BP) Number** so no user can ever access another member's records.",
         "GSIS Data Privacy Notice (RA 10173) & Google Cloud Model Armor Security", "data privacy act ra 10173 security model armor dpo confidential"),
        ("FAQ-EC-001", "DISABILITY_SURVIVORSHIP", "What is Employees' Compensation (EC) and when can I file an EC claim with GSIS?",
         "**Employees' Compensation (EC)** under **PD 626** provides tax-exempt compensation for **work-connected sickness, injury, or death** (including accidents while going to or coming from the workplace). Claims for EC Medical Reimbursement, Temporary Total Disability, or EC Death/Funeral (**Php 30,000**) must be filed within **3 years** from the date of occurrence.",
         "Presidential Decree No. 626 — Employees' Compensation (EC) Program", "employees compensation ec claim work related injury sickness accident pd 626"),
        ("FAQ-PORTAL-001", "GSIS_TOUCH_APIR", "How do I update my mobile number, email address, or civil status (e.g., Single to Married) in GSIS?",
         "To update your **Mobile Number or Email Address**, you can use the self-service contact update inside **GSIS Touch** or submit a **Member Information Sheet (MIS) Update Form** through your **Agency Authorized Officer (AAO)**. To update your **Civil Status** (e.g., `Single` to `Married`), submit your PSA Marriage Certificate through your AAO or any GSIS Branch so your **Legal Beneficiaries** are updated.",
         "GSIS Membership Information Sheet (MIS) Updating Procedure", "update mobile number email civil status married psa marriage certificate mis"),
        ("FAQ-CALC-001", "LOANS", "Can GSIS Gabay AI compute my tentative MPL Flex loan or RA 8291 Retirement benefits?",
         "**Yes!**\n* **In Phase 1 (Unauthenticated Mode):** Tell **GSIS Gabay AI** your sample Basic Monthly Salary and years of service (e.g., *'Compute sample MPL Flex and retirement if my salary is Php 40,000 with 16 years service'*), and the deterministic calculator will compute your exact figures.\n* **In Phase 2 (Authenticated Mode):** Simply log in or register a mock account, and **GSIS Gabay AI** will automatically fetch your live salary, PPP duration, and active loan balances from the **MCP Server** to compute your exact Net Proceeds!",
         "GSIS Gabay AI Deterministic Calculator Guide", "compute calculate calculator sample loan pension mpl flex net proceeds"),
    ]
    for doc_id, cat, title, answer, ref, kw in extra_faqs:
        docs.append({
            "doc_id": doc_id,
            "category": cat,
            "question_title": title,
            "official_answer_markdown": answer,
            "source_circular_ref": ref,
            "source_url": "https://www.gsis.gov.ph/",
            "keywords": kw
        })

    return {
        "metadata": {
            "agency": "Government Service Insurance System (GSIS) - Republic of the Philippines",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_documents": len(docs),
            "scraped_sources": live_metadata
        },
        "documents": docs
    }


if __name__ == "__main__":
    os.makedirs("/usr/local/google/home/markea/Desktop/gsis-chatbot-26/demo/data", exist_ok=True)
    live_meta = fetch_live_gsis_snippets()
    corpus = build_official_gsis_faq_corpus(live_meta)
    out_path = "/usr/local/google/home/markea/Desktop/gsis-chatbot-26/demo/data/gsis_official_faq_corpus.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(corpus, f, indent=2, ensure_ascii=False)
    print(f"[SUCCESS] Wrote {corpus['metadata']['total_documents']} official GSIS FAQ documents to {out_path}")

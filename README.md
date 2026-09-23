# 🇵🇭 GSIS Omnichannel Multi-Agent AI Chatbot ("GSIS Gabay AI") — Executive Demo & Architecture Suite

> ⚠️ **STRICTLY FOR DEMO & EVALUATION PURPOSES ONLY:** The deployed application and synthetic database in `/demo` use **100% randomly generated synthetic mock data** and are **NOT** connected to live Government Service Insurance System (GSIS) production databases.

---

## 🌐 Live Deployed Cloud Run Executive Demo (`asia-southeast1`)

- **Live Cloud Run URL**: [**`https://gsis-gabay-ai-demo-jprf6uux5q-as.a.run.app`**](https://gsis-gabay-ai-demo-jprf6uux5q-as.a.run.app)
- **GCP Project**: `markea-testbed-dev` (`asia-southeast1`)
- **Container Image**: `asia-southeast1-docker.pkg.dev/markea-testbed-dev/gsis-demo-repo/gsis-gabay-ai-demo:latest`
- **Multi-Agent Model Tiers**:
  - **Fast Routing & RAG Tier**: `gemini-3.7-flash` (`GSIS_Concierge_Router`, `GSIS_Policy_FAQ_Agent`, `GSIS_Member_Records_Agent`)
  - **Deep Financial & Statutory Reasoning Tier**: `gemini-3.1-pro` (`GSIS_Loans_Computation_Agent`, `GSIS_Benefits_Transactions_Agent`)
  - **Runtime AI Security Guardrail**: **Google Cloud Model Armor** (`gsis-gabay-armor-v1`) + Identity-Bound MCP Tool Injection (`JWT + Simulated 6-Digit OTP`)

---

## 📂 Repository Structure

| File / Directory | Description |
| :--- | :--- |
| [`01_BRD_GSIS_OMNICHANNEL_AI_CHATBOT.md`](./01_BRD_GSIS_OMNICHANNEL_AI_CHATBOT.md) | **Business Requirements Document (`v1.2-ALIGNED`)**: Harmonized executive specification for Phase 1 (Public FAQ & Sample Calculators) and Phase 2 (Authenticated Multi-Agent Member Concierge). |
| [`02_TDD_GSIS_CHATBOT_DEMO_MOCK_ARCHITECTURE.md`](./02_TDD_GSIS_CHATBOT_DEMO_MOCK_ARCHITECTURE.md) | **Technical Design Document #1 (Executive Demo with Mock Data)**: Specifies the 5-agent Google ADK hierarchy (`Gemini 3.7 Flash` / `Gemini 3.1 Pro`), Identity-Bound Mock MCP Server, Age/Civil-Status-Consistent Seeder (`MAX_MOCK_USERS = 25`), and Terraform IaC. |
| [`03_TDD_GSIS_CHATBOT_PRODUCTION_ROLLOUT.md`](./03_TDD_GSIS_CHATBOT_PRODUCTION_ROLLOUT.md) | **Technical Design Document #2 (Enterprise Production Rollout)**: Dual-region (`asia-southeast1` + `asia-east1`) production blueprint with Apigee X, AlloyDB, SAP ERP / Core Banking adapters, and NPC RA 10173 compliance. |
| [`demo/`](./demo/) | **Complete Full-Stack Application**: FastAPI backend (`demo/main.py`, `demo/backend/*`), Official GSIS Website + GSIS Touch `390x844` Mobile Simulator (`demo/static/*`), and 50 scraped official GSIS policy documents (`demo/data/gsis_official_faq_corpus.json`). |
| [`demo/evals/EVAL_REPORT.md`](./demo/evals/EVAL_REPORT.md) | **Golden Dataset Evaluation Report (`28 / 28 — 100.0% Pass Rate`)**: Comprehensive evaluation across Phase 1 FAQ RAG, Phase 1 Unauthenticated Auth Gate, Phase 2 Multi-Agent Deterministic Math, Model Armor Security, and the 25-User Quota Cap. |
| [`demo/terraform/`](./demo/terraform/) | **Terraform Infrastructure-as-Code & 1-Command Teardown**: Provisions Artifact Registry, Secret Manager, least-privilege IAM Service Account, and Cloud Run v2 Service (`./teardown.sh` destroys all demo cloud resources in one command). |

---

## 👤 Pre-Seeded Executive Demo Personas (Password: `gsis2026`)

You can sign in with **1 click** directly from the top hero strip or the **Member Login / Register** modal:

1. **`maria.santos`** (`BP 2016041822`) — **Active Teacher III, DepEd-NCR (Age 39, Married, 15.0 yrs PPP)**
   - **Salary**: `PHP 46,725.00` | **Active Loans**: `MPL_FLEX` (`PHP 142,350.00` balance, 36 mos left) + `EMERGENCY_LOAN` (`PHP 8,150.00` balance)
   - **Deterministic MPL Flex Reloan Net Proceeds**: **`PHP 493,654.53`** (after `PHP 142,350.00` loan offset, `PHP 13,083.00` 2% service fee, and `PHP 5,062.47` MRI fee)
   - **Special Scenario**: Includes 1 unposted agency Electronic Remittance File (`2026-07 UNPOSTED_ERF_PENDING_AAO`).
2. **`juan.delacruz`** (`BP 2001089311`) — **Retiring Engineer IV, DPWH (Age 60, Widowed, 34.0 yrs PPP)**
   - **Salary**: `PHP 78,500.00` | **Deterministic RA 8291 Basic Monthly Pension (BMP)**: **`PHP 67,320.00 / month`**
   - **Option 1 (60-Month Lump Sum)**: **`PHP 4,039,200.00`** | **Option 2 (18-Month Cash + Immediate Pension)**: **`PHP 1,211,760.00`** + `PHP 67,320.00/mo`.
3. **`rosa.reyes`** (`BP 1992031409`) — **Old-Age Retiree Pensioner, DOF (Age 67, Single, 27.6 yrs PPP)**
   - **Monthly Pension**: `PHP 33,962.25` | **APIR Status**: **`DUE_OCTOBER_2026`** (`2026-10-31`, aligned to October birth month).

---

## ✨ Custom Mock Member Seeder & Hard Limit of 25 Users (`MAX_MOCK_USERS = 25`)

- Click **"🔐 Member Login / Register (Phase 2)" -> "✨ Create Custom Mock Member"** (and optionally **"🎲 1-Click Random Fill Persona"**) to dynamically seed a custom member across all 5 relational tables (`gsis_members`, `gsis_contributions`, `gsis_loans`, `gsis_benefits_claims`, `gsis_transactions`).
- **Age & Civil-Status Mathematical Consistency**:
  - **Service Duration (`PPP`)** is strictly bounded by `Age - 21` derived from the member's Birthday.
  - **APIR Due Month** is automatically aligned to the member's Birth Month.
  - **Recognized Legal Beneficiaries** are derived from Civil Status (`Married`, `Single`, `Widowed`, `Legally Separated`).
- **Hard Quota Enforcement (`25 / 25`)**:
  - Once `25` custom mock accounts are created, `POST /api/auth/register-mock` returns **`HTTP 429 Too Many Requests` (`DEMO_USER_LIMIT_REACHED`)** and displays a prominent red **Quota Exceeded Error Notification Banner** with 1-click sign-in buttons for the 3 pre-seeded personas. (You can also preview this alert at any time via the **"🧪 Preview 25-User Limit Error Alert"** button inside the modal).

---

## 🧹 1-Command Cloud Teardown

To destroy all Google Cloud resources provisioned for this demo (`Cloud Run`, `Secret Manager`, `Artifact Registry`, and `Service Account`):

```bash
cd demo/terraform && ./teardown.sh
```

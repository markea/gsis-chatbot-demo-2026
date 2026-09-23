# TECHNICAL DESIGN DOCUMENT (TDD #2): ENTERPRISE PRODUCTION ROLL-OUT
## Government Service Insurance System (GSIS) — Omnichannel Multi-Agent AI Assistant ("GSIS Gabay AI")
### Production Architecture for 3.2M+ Members & Pensioners: GSIS Touch Native Integration, SAP/MIS Enterprise MCP Gateway, AlloyDB HA & Model Armor Enterprise

| Metadata Attribute | Details |
| :--- | :--- |
| **Document Reference** | `GSIS-TDD-PROD-2026-v1.0` |
| **Companion Documents** | • [01_BRD_GSIS_OMNICHANNEL_AI_CHATBOT.md](./01_BRD_GSIS_OMNICHANNEL_AI_CHATBOT.md)<br>• [02_TDD_GSIS_CHATBOT_DEMO_MOCK_ARCHITECTURE.md](./02_TDD_GSIS_CHATBOT_DEMO_MOCK_ARCHITECTURE.md) |
| **Target Environment** | GSIS Production Landing Zone on Google Cloud (`asia-southeast1` Primary / `asia-east1` DR) |
| **Target Scale** | **2.6M+ Active Government Employees** + **600,000+ Pensioners** (`5,000+` concurrent peak sessions) |
| **Client Channels** | **GSIS Touch Mobile App** (Native Android & iOS) & **myGSIS Web Portal** |
| **Enterprise Integrations** | GSIS Core **SAP ERP**, **Member Information System (MIS)**, **Loan Management System (LMS)**, **ERF Billing Engine**, **APIR Facial Verification API** |
| **Security & Governance** | Cloud Armor Enterprise WAF, reCAPTCHA Enterprise, Apigee X, **Google Cloud Model Armor**, Cloud DLP, Cloud KMS HSM (CMEK), VPC Service Controls |
| **Author / Lead Architect** | Mark Earvin Sarmiento (Google Cloud Architecture Team) |
| **Date** | September 23, 2026 |

---

## Table of Contents
1. [Executive Summary & Production Architectural Thesis](#1-executive-summary--production-architectural-thesis)
2. [Delta Matrix: Demo Architecture (TDD #1) vs. Production Architecture (TDD #2)](#2-delta-matrix-demo-architecture-tdd-1-vs-production-architecture-tdd-2)
3. [End-to-End Enterprise Production Topology](#3-end-to-end-enterprise-production-topology)
4. [Omnichannel Client Integration: Native GSIS Touch (Android/iOS) & Web Portal](#4-omnichannel-client-integration-native-gsis-touch-androidios--web-portal)
5. [Enterprise Authentication, OAuth 2.0 / OIDC & Step-Up MFA Architecture](#5-enterprise-authentication-oauth-20--oidc--step-up-mfa-architecture)
6. [Production RAG Architecture & Policy Corpus Governance Lifecycle](#6-production-rag-architecture--policy-corpus-governance-lifecycle)
7. [Production MCP Gateway & GSIS Core SAP / MIS / LMS Integration](#7-production-mcp-gateway--gsis-core-sap--mis--lms-integration)
8. [Defense-in-Depth Security: Model Armor Enterprise, VPC-SC & RA 10173 Compliance](#8-defense-in-depth-security-model-armor-enterprise-vpc-sc--ra-10173-compliance)
9. [High Availability, Capacity Sizing, FinOps & Observability (OpenTelemetry)](#9-high-availability-capacity-sizing-finops--observability-opentelemetry)
10. [Phased Production Roll-Out & Cutover Runbook (Phases 1, 2 & 3)](#10-phased-production-roll-out--cutover-runbook-phases-1-2--3)

---

## 1. Executive Summary & Production Architectural Thesis

While **TDD #1** establishes a self-contained Cloud Run demonstration environment powered by synthetic member records in AlloyDB, **TDD #2** defines the target **Enterprise Production Architecture** for rolling out **GSIS Gabay AI** across the **GSIS Touch Mobile App (Android/iOS)** and the **GSIS Web Portal** for over **3.2 million Filipino civil servants and pensioners**.

### 1.1 Zero-Refactor Path from Demo (TDD #1) to Production (TDD #2)
Because the Multi-Agent system in TDD #1 is built on open **Model Context Protocol (MCP)** contracts and **Google Agent Development Kit (ADK)**:
* **The Multi-Agent Brain Remains Identical:** `GSIS_Concierge_Router`, `GSIS_Policy_FAQ_Agent`, `GSIS_Member_Records_Agent`, `GSIS_Loans_Computation_Agent`, and `GSIS_Benefits_Transactions_Agent` require **zero prompt or orchestration rewrites** when moving from Demo to Production.
* **Contract-Compatible Backend Swap:** Only the backing data providers behind the MCP Server and Auth Gateway change—swapping the **Synthetic Data Seeder & Mock AlloyDB Tables** for **GSIS Core SAP ERP / MIS / LMS APIs** via **Apigee X** and **Dedicated/Partner Cloud Interconnect**.

---

## 2. Delta Matrix: Demo Architecture (TDD #1) vs. Production Architecture (TDD #2)

| Architectural Layer | TDD #1: Executive Demo (Mock Environment) | TDD #2: Enterprise Production Roll-Out |
| :--- | :--- | :--- |
| **Client Channels** | Omnichannel Dual-View Web App (`GSIS Touch Mobile Simulator` + `Web Portal View`). | Native **GSIS Touch Android/iOS SDK** (WebView/SSE) + **myGSIS Web Portal** embeddable widget. |
| **Edge & Bot Protection** | Cloud Run managed TLS ingress. | **Global Cloud Load Balancer** + **Cloud Armor Enterprise WAF** + **reCAPTCHA Enterprise**. |
| **Identity & Authentication** | Username/Password + Mock Registration (Email, Birthday, Gender) + **Simulated On-Screen 6-Digit OTP**. | **GSIS Touch OAuth 2.0 / OIDC Biometric SSO Hand-Off** + Production SMS/Email OTP Gateway via **Apigee X**. |
| **Multi-Agent Orchestration** | Google ADK (`GSIS_Concierge_Router` + 4 Sub-Agents) on single Cloud Run service. | Google ADK deployed on **Multi-Zone Cloud Run Enterprise / GKE Autopilot** with horizontal autoscaling (`min-instances=5`, `max-instances=200`). |
| **AI Security Perimeter** | **Google Cloud Model Armor** (`sanitizeUserPrompt` / `sanitizeModelResponse`) + UI Trace Badge. | **Google Cloud Model Armor Enterprise** + **Cloud Sensitive Data Protection (SDP/DLP)** + **VPC Service Controls (VPC-SC)**. |
| **Phase 1 Policy RAG** | Pre-seeded GSIS FAQ vectors in AlloyDB (`pgvector`). | **AlloyDB HA `pgvector`** + **Vertex AI Search** indexing signed GSIS Board Resolutions, Circulars & Citizen's Charter with HITL approval workflow. |
| **Phase 2 Personal Data MCP** | **Mock MCP Server** querying synthetic member records in AlloyDB. | **Production Enterprise MCP Gateway** querying **GSIS Core SAP ERP / MIS / LMS** over **Private Service Connect (PSC) + Cloud Interconnect** with **Memorystore Redis** caching. |
| **Phase 3 Action Buttons** | Displays **"Coming Soon! (Phase 3 Transactional Execution)"** modal. | Executes signed deep-link hand-off into **GSIS Touch Loan / APIR Transaction Screens** with pre-populated application drafts. |

---

## 3. End-to-End Enterprise Production Topology

```mermaid
flowchart TB
    subgraph Channels["1. Omnichannel Member Touchpoints"]
        TouchApp["GSIS Touch Mobile App\n(Android & iOS Native App)"]
        WebPortal["GSIS Official Web Portal\n(gsis.gov.ph / myGSIS)"]
    end

    subgraph EdgePerimeter["2. Google Cloud Edge & Zero-Trust Perimeter"]
        GLB["Global External Application Load Balancer\n(TLS 1.3 + Managed SSL Certificates)"]
        CloudArmor["Google Cloud Armor Enterprise WAF\n(OWASP Top 10, Geo-Fencing PH/OFW, Rate Limiting)"]
        Recaptcha["reCAPTCHA Enterprise\n(Frictionless Bot & Credential Stuffing Defense)"]
        Apigee["Apigee X API Gateway\n(OAuth 2.0 / OIDC Validation, Spike Arrest, mTLS)"]
    end

    subgraph SecurityAndAI["3. AI Security & Multi-Agent Runtime (VPC-SC Perimeter)"]
        ModelArmor["Google Cloud Model Armor + Cloud SDP (DLP)\n(Prompt Injection, Jailbreak, PII Redaction, Safe URI)"]
        ADKCluster["Multi-Agent Runtime (Cloud Run Enterprise / GKE Autopilot)\n• GSIS_Concierge_Router (Supervisor)\n• GSIS_Policy_FAQ_Agent (Phase 1 & 2)\n• GSIS_Member_Records_Agent (Phase 2)\n• GSIS_Loans_Computation_Agent (Phase 2)\n• GSIS_Benefits_Transactions_Agent (Phase 2)"]
        VertexAI["Vertex AI Foundation Models\n(Gemini 3.7 Flash / Gemini 3.1 Pro + text-embedding-004)"]
    end

    subgraph DataAndKnowledge["4. High-Availability Knowledge & Session Tier"]
        Redis[("Memorystore for Redis Cluster\n(Conversation State & 60s Member Record Cache)")]
        AlloyDB_HA[("AlloyDB for PostgreSQL (Multi-Zone HA)\n• pgvector Policy RAG Store\n• Conversation Audit & Feedback Logs\n• CMEK Encrypted via Cloud KMS HSM")]
        BigQuery[("BigQuery Enterprise Analytics\n(Immutable NPC Audit Logs, Containment KPIs, Eval Flywheel)")]
    end

    subgraph CoreIntegration["5. Enterprise MCP Gateway & Hybrid Connectivity to GSIS Data Center"]
        ProdMCP["Production GSIS MCP Server (Cloud Run Internal)\n• Strict JWT BP-Number Scope Enforcement\n• Deterministic Loan/Pension Calculators\n• Circuit Breaker & Retry Policies"]
        Interconnect["Dedicated / Partner Cloud Interconnect\n(HA VPN + IPSec / BGP Encrypted Tunnel)"]
        GSIS_SAP[("GSIS Core Systems (Pasay Data Center / Private Cloud)\n• SAP ERP (Contributions & General Ledger)\n• Member Information System (MIS - BP/CRN)\n• Loan Management System (LMS - MPL Flex/Conso)\n• APIR & eCard/UMID Status API")]
    end

    TouchApp & WebPortal --> GLB --> CloudArmor --> Recaptcha --> Apigee
    Apigee --> ModelArmor
    ModelArmor <--> ADKCluster
    ADKCluster <--> VertexAI
    ADKCluster <--> Redis & AlloyDB_HA
    ADKCluster --> ProdMCP
    ProdMCP --> Redis
    ProdMCP --> Interconnect --> GSIS_SAP
    ADKCluster & ModelArmor -.->|"Async Audit Sink"| BigQuery
```

---

## 4. Omnichannel Client Integration: Native GSIS Touch (Android/iOS) & Web Portal

### 4.1 Native Mobile Integration Pattern (`GSIS Touch` Android & iOS)
To avoid maintaining duplicate conversational UI codebases across Android (Kotlin), iOS (Swift), and Web (React/HTML5), **GSIS Gabay AI** supports a dual integration pattern for the **GSIS Touch** mobile team:

1. **Pattern A — Authenticated Secure WebView Bridge (Fastest Rollout — 2 Weeks):**
   * The native GSIS Touch app embeds the Cloud Run Mobile-Optimized Chat UI inside a hardened `WKWebView` (iOS) / `AndroidWebView` (Android).
   * When the member is already logged into GSIS Touch (via password or biometrics), the native app passes the short-lived **OAuth 2.0 Bearer Token** to the WebView via an encrypted `postMessage` bridge (`window.GSISTouchBridge.injectSessionToken(jwt)`), automatically activating **Phase 2** without asking the user to log in a second time.
2. **Pattern B — Native UI over Server-Sent Events (`SSE` Streaming REST API):**
   * Native mobile screens invoke `POST https://api.gsis.gov.ph/gabay-ai/v1/chat/stream` directly with `Authorization: Bearer <gsis_touch_jwt>`, rendering streaming markdown tokens, structured summary cards, and deep-link buttons (`gsistouch://loans/mpl-flex/apply`) in native mobile components.

---

## 5. Enterprise Authentication, OAuth 2.0 / OIDC & Step-Up MFA Architecture

In production, authentication bridges two entry points:

| Entry Scenario | Authentication & Token Flow | Session & Scope Binding |
| :--- | :--- | :--- |
| **Scenario 1: User opens Chat from inside `GSIS Touch` Mobile App (Already Logged In)** | Native app exchanges the active GSIS Touch refresh/access token at **Apigee X** for a chat-scoped **OIDC JWT** (`aud: gsis-gabay-ai`, `ttl: 900s`) containing the member's verified `bp_number` and `crn`. | Zero secondary login prompt; immediately enters **Phase 2**. |
| **Scenario 2: User starts in Phase 1 (Public Web Portal or Pre-Login Mobile Screen) and asks a Personal Query** | Chatbot prompts user to sign in. User enters **GSIS Username & Password** $\rightarrow$ GSIS Identity Provider dispatches a real **6-Digit SMS/Email OTP** to their registered mobile/email $\rightarrow$ Upon OTP verification, Apigee issues the `bp_number`-bound JWT. | Transitions session seamlessly from **Phase 1** to **Phase 2** while preserving conversation history. |

---

## 6. Production RAG Architecture & Policy Corpus Governance Lifecycle

Because GSIS loan policies, dividend rates, emergency loan declarations (calamity areas), and retirement circulars are updated periodically by the **GSIS Board of Trustees**, the Phase 1/Phase 2 RAG pipeline enforces a governed **Human-in-the-Loop (HITL) Publishing Pipeline**:

```mermaid
flowchart LR
    Upload["1. GSIS Policy Team Uploads Signed Circular / PDF\n(gs://gsis-policy-staging-cmek)"] --> DocAI["2. Google Cloud Document AI Layout Parser\n(Preserves Tables, Salary Multiples & Formulas)"]
    DocAI --> Embed["3. Vertex AI Embeddings (text-embedding-004)\n+ Metadata Tagging (Circular No, Effective Date)"]
    Embed --> StagingDB[("4. AlloyDB HA Staging Vector Table\n(Tested in Sandbox Evaluator)")]
    StagingDB --> Approval{"5. GSIS Member Services\nSign-Off Approval"}
    Approval -->|"Approved"| ProdDB[("6. Atomic Swap to Production AlloyDB pgvector\n(Instant Zero-Downtime Policy Update)")]
```

* **Strict Version & Expiry Filtering:** Every vector chunk in AlloyDB carries `effective_start_date`, `effective_end_date`, and `superseded_by_circular`. The `search_gsis_faq_rag` query appends `WHERE status = 'PUBLISHED' AND CURRENT_DATE BETWEEN effective_start_date AND COALESCE(effective_end_date, '9999-12-31')` so obsolete loan policies are never retrieved.

---

## 7. Production MCP Gateway & GSIS Core SAP / MIS / LMS Integration

In Production Phase 2, the **Enterprise MCP Server** replaces the synthetic AlloyDB tables with read-only adapters to GSIS Core Systems over **Cloud Interconnect**:

| MCP Tool Name | Target GSIS Core System (Production) | Protocol / Adapter | Caching & Resiliency Strategy |
| :--- | :--- | :--- | :--- |
| `get_member_profile` | **GSIS Member Information System (MIS)** | REST / SOAP over Apigee Private Endpoint | Cached in **Memorystore Redis** (encrypted) for `300s` per `bp_number`. |
| `get_contributions_summary` | **SAP ERP Financials / ERF Remittance Ledger** | SAP OData / RFC via Apigee SAP Integration Connector | Cached for `180s`; circuit breaker returns cached snapshot if SAP is undergoing nightly batch posting. |
| `get_member_loans` | **GSIS Loan Management System (LMS)** | REST API (`/lms/v2/members/{bp_number}/loans`) | Real-time fetch (`60s` cache); timeout set to `2,500ms`. |
| `simulate_loan_application` | **LMS Tentative Computation Engine** + **MCP Deterministic Calculator** | Hybrid: Fetches live balances from LMS + executes verified Python/LMS computation rule. | Appends mandatory **RA 8291 / LMS Tentative Computation Disclaimer**. |
| `get_benefits_and_eligibility` | **GSIS Claims & Actuarial System** + **APIR Verification Database** | REST API (`/claims/v2/projections/{bp_number}`) | Computes BMP, Option 1/Option 2 lump sums, CSV, and APIR Birth-Month status. |
| `get_recent_transactions` | **SAP General Ledger & eCard Disbursement Gateway** | SAP OData (`/sap/opu/odata/gsis/MEMBER_TX_SRV`) | Returns top 10 posted remittances, loan deductions, and eCard disbursements. |

---

## 8. Defense-in-Depth Security: Model Armor Enterprise, VPC-SC & RA 10173 Compliance

To satisfy the **National Privacy Commission (NPC)** under **Republic Act No. 10173 (Data Privacy Act of 2012)** and **BSP / Government Information Security Standards**:

1. **Google Cloud Model Armor Enterprise (`Organization & Folder Policy`):**
   * Mandatory inline inspection (`sanitizeUserPrompt` and `sanitizeModelResponse`) on 100% of Phase 1 and Phase 2 turns.
   * **Prompt Injection & Jailbreak Protection:** Configured at `HIGH` sensitivity to block instruction overrides, system prompt extraction, and SQL/tool manipulation.
   * **Cloud Sensitive Data Protection (SDP / DLP):** Redacts any unmasked TIN, PhilSys National ID, bank account numbers, or cross-member BP numbers before logging or egress.
2. **Cryptographic Session Isolation (Anti-IDOR / Anti-Cross-Account Leakage):**
   * The `bp_number` parameter is **never** exposed in the LLM function schema. The Production MCP Server extracts `bp_number` exclusively from an mTLS-authenticated header signed by **Apigee X (`X-Apigee-Verified-BP-Number`)**.
3. **VPC Service Controls (VPC-SC) & Customer-Managed Encryption Keys (CMEK):**
   * Vertex AI, Cloud Run, AlloyDB HA, Memorystore, and BigQuery operate inside a unified **VPC Service Controls Perimeter**, preventing data exfiltration to unauthorized GCP projects or public internet endpoints.
   * All database volumes, backups, and BigQuery audit tables are encrypted using **Cloud KMS Hardware Security Modules (HSM — FIPS 140-2 Level 3)** with keys managed by the GSIS Information Security Office.
4. **Zero Model Training on GSIS Member Data:**
   * Under Google Cloud Vertex AI Data Governance guarantees, **zero GSIS member prompts, MCP payloads, or conversation logs** are ever used to train foundation models.

---

## 9. High Availability, Capacity Sizing, FinOps & Observability (OpenTelemetry)

### 9.1 Production Capacity Sizing (3.2M Members / Payday & Calamity Loan Surges)
* **Cloud Run Enterprise / GKE Autopilot:**
  * Configured with `min-instances: 5` (zero cold starts) and `max-instances: 250` (`80 concurrent requests per instance`), supporting up to **20,000 concurrent streaming connections** during peak payday or Emergency Loan openings.
* **AlloyDB for PostgreSQL High Availability:**
  * Primary instance (`8 vCPU, 64 GB RAM`) across 2 availability zones in `asia-southeast1` + Read Pool (`2 x 4 vCPU`) for high-throughput `pgvector` FAQ RAG similarity searches.
* **Vertex AI Provisioned Throughput / Dynamic Shared Quota (DSQ):**
  * Uses **Gemini 3.7 Flash** for ultra-low-latency (`<1.2s` TTFT) routing and sub-agent tool synthesis, paired with **Gemini 3.1 Pro** for complex multi-loan/retirement reasoning, with **Provisioned Throughput** reserved during peak announcement windows.

### 9.2 OpenTelemetry (OTel) & Cloud Monitoring Alerting
* Tracks four golden agent telemetry signals exported to **Google Cloud Monitoring**:
  1. **TTFT & End-to-End Turn Latency (`P50`, `P95`, `P99`)**
  2. **MCP Core System Tool Error Rate & Circuit-Breaker Trips**
  3. **Model Armor Block Rate (`piAndJailbreakFilter` & `sdpRedaction` counts)**
  4. **Task Containment Rate vs. Contact Center (8847-4747) Escalation Rate**

---

## 10. Phased Production Roll-Out & Cutover Runbook (Phases 1, 2 & 3)

| Rollout Stage | Target Timeline | Scope & Milestones | Exit / Go-Live Gate |
| :--- | :--- | :--- | :--- |
| **Stage 0: Executive Demo & Sandbox Validation** *(TDD #1)* | **Sprint 0 (Current)** | Deploy Cloud Run Omnichannel Demo + Age-Aware Synthetic Data Seeder + Mock MCP + Model Armor. | Executive sign-off by GSIS OPGM, ITSG, and Member Services. |
| **Stage 1: Phase 1 Production Roll-Out (Public FAQ RAG)** | **Weeks 1–4** | Ingest official GSIS Citizen's Charter & Circulars into AlloyDB HA `pgvector`; configure Cloud Armor WAF & Model Armor; embed Phase 1 widget on `gsis.gov.ph` and GSIS Touch pre-login screen. | $\ge 95\%$ RAG evaluation score on 300 Golden GSIS FAQ test cases; CISO security sign-off. |
| **Stage 2: Phase 2 Production Roll-Out (Authenticated Personal Queries)** | **Weeks 5–10** | Connect Production MCP Server to SAP/MIS/LMS over Cloud Interconnect + Apigee X; integrate GSIS Touch OAuth 2.0 / OTP MFA; enable live contributions, loans, benefits & transaction queries with *"Coming Soon!"* action buttons. | Zero cross-account leakage in penetration testing; $100\%$ numerical parity with GSIS Touch member screens. |
| **Stage 3: Phase 3 Transactional Execution Activation** | **Weeks 11–16** | Upgrade *"Coming Soon!"* CTA buttons into live transactional execution flows (1-tap MPL Flex Loan Application submission, APIR schedule booking, and automated ERF reconciliation ticket creation in SAP). | Full transactional audit sign-off and biometric step-up confirmation. |

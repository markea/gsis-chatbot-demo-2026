# GSIS Omnichannel Multi-Agent AI Chatbot (`gsis-chatbot-demo-2026`)

**Client / Agency:** Government Service Insurance System (GSIS) – Republic of the Philippines  
**Target Channels:** GSIS Touch Mobile App (Android / iOS) & GSIS Responsive Web Portal  
**Target Stack:** Google Cloud Run, Vertex AI (Gemini 2.5 Flash/Pro), **Google Cloud Model Armor**, Google Agent Development Kit (ADK), Model Context Protocol (MCP), AlloyDB for PostgreSQL (`pgvector`)

---

## 📚 Architecture & Engineering Documentation Suite

| # | Document | Purpose & Scope |
| :--- | :--- | :--- |
| **01** | **[01_BRD_GSIS_OMNICHANNEL_AI_CHATBOT.md](./01_BRD_GSIS_OMNICHANNEL_AI_CHATBOT.md)** | **Business Requirements Document (BRD) (`v1.2-ALIGNED`)**: Complete business context, KPIs, Phase 1 (Unauthenticated FAQ RAG) vs. Phase 2 (Authenticated Personal Queries via MCP + AlloyDB), Mock Registration (Email, Birthday, Gender, Civil Status, Mobile, Agency + Simulated 6-Digit OTP), Deterministic Calculators, *"Coming Soon!"* Phase 3 buttons, and **Google Cloud Model Armor** requirements. |
| **02** | **[02_TDD_GSIS_CHATBOT_DEMO_MOCK_ARCHITECTURE.md](./02_TDD_GSIS_CHATBOT_DEMO_MOCK_ARCHITECTURE.md)** | **Technical Design Document #1 — Demo with Mock Data**: Engineering blueprint for the **Google Cloud Run** Executive Demo (`markea-testbed-dev`), including the **Dual-Mode AlloyDB Connector**, SQL DDL & `pgvector` schema, **Age- & Civil-Status-Consistent Synthetic Member Data Generator**, Simulated 6-Digit OTP flow, Multi-Agent ADK + Mock MCP Server contracts, Deterministic Python Loan/Pension Calculators, **Model Armor** middleware, and the **Omnichannel Dual-View UI** (*GSIS Touch Mobile Frame* + *Web Portal View* + *Live DB/MCP Inspector*). |
| **03** | **[03_TDD_GSIS_CHATBOT_PRODUCTION_ROLLOUT.md](./03_TDD_GSIS_CHATBOT_PRODUCTION_ROLLOUT.md)** | **Technical Design Document #2 — Enterprise Production Roll-Out**: Production architecture for scaling **GSIS Gabay AI** to **3.2M+ members and pensioners** (`5,000+` concurrent users), covering the **Demo $\rightarrow$ Production Delta Matrix**, Native **GSIS Touch Android/iOS SDK & OAuth 2.0/OIDC Biometric SSO**, **Enterprise MCP Gateway to GSIS Core SAP ERP / MIS / LMS** via **Apigee X + Cloud Interconnect**, **AlloyDB Multi-Zone HA + Document AI Policy Governance**, **VPC Service Controls**, **Cloud KMS HSM (CMEK)**, and **RA 10173** compliance. |

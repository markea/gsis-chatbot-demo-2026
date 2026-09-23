# GSIS Omnichannel Multi-Agent AI Chatbot (`gsis-chatbot-demo-2026`)

**Client / Agency:** Government Service Insurance System (GSIS) – Republic of the Philippines  
**Target Channels:** GSIS Touch Mobile App (Android / iOS) & GSIS Responsive Web Portal  
**Target Stack:** Google Cloud Run, Vertex AI (Gemini 2.5 Flash/Pro), Google Agent Development Kit (ADK), Model Context Protocol (MCP), AlloyDB for PostgreSQL (`pgvector`)

---

## 📄 Documentation

* **[01_BRD_GSIS_OMNICHANNEL_AI_CHATBOT.md](./01_BRD_GSIS_OMNICHANNEL_AI_CHATBOT.md)** — Complete Business Requirements Document (BRD) & Technical Architecture Specification covering:
  * **Phase 1:** Unauthenticated Public & Member FAQ Assistant powered by **RAG** (Static GSIS FAQs, Loan Rules, Retirement Computation Guidelines, Digital Services).
  * **Phase 2:** Authenticated Personal Data & Transaction Assistant powered by a **Multi-Agent System** + **Mock MCP Server** + **AlloyDB** (Contributions, Service Durations, Loans, Benefits, and Transactions).
  * **Demo Onboarding & Synthetic Member Data Generator:** Username/Password login mirroring the GSIS website, plus self-service **Mock User Registration (Email required)** that automatically generates randomized, mathematically consistent member contributions, service durations, loans, benefits, and transaction records in AlloyDB.


# AI-Powered Automated Monitoring & Self-Healing Pipeline

## Phase 1: Jira Ticketing & Chatbot
A **AI powered automated error healing system** that ingests error logs, performs **vector similarity search**, generates or recalls **RCA (Root Cause Analysis)**, files **Jira tickets**, and exposes a **Teams chatbot** for natural‑language analytics.

## Phase 2: Self healing
TBD

---
## 📌 Table of Contents
1. [Overview](#overview)
2. [High-Level Architecture (Phase 1)](#high-level-architecture-phase-1)
3. [Repository Structure](#repository-structure)
4. [Key Components](#key-components)
5. [Configuration](#configuration)
6. [Environment Setup](#environment-setup)
7. [Secrets & Env Variables](#secrets--environment-variables)
8. [How to Run](#how-to-run)
9. [Core Workflows](#core-workflows)
10. [Data Storage & Schema](#data-storage--schema)
11. [Logging & Monitoring](#logging--monitoring)
12. [Extensibility](#extensibility)
13. [Troubleshooting](#troubleshooting)
14. [Glossary](#glossary)

---
## 1. Overview
This platform automates incident handling and auto fixing the failures and provides conversational analytics.

### 🔹 Error extraction
- Extracts the errors from the new error logs and inserts into SQL server database.

### 🔹 Error Intelligence
- Converts new error logs → **embeddings**
- Runs **similarity search** using **ChromaDB**
- Retrieves **existing RCA** or generates a **new RCA via AI**

### 🔹 Ticketing
- Automatically creates enriched **Jira tickets** with RCA & context

### 🔹 Chatbot
- A **Microsoft Teams bot** that:
  - Interprets user intent
  - Runs SQL queries or generates them using AI
  - Summarizes results in natural language

---
## 2. High‑Level Architecture (Phase 1)
### 🔧 Error Flow
```
Error Logs extraction  → Embedding → Similarity Search → RCA Retrieval / AI Generated → Jira Ticket
```

### 💬 Chatbot Flow
```
Teams → Bot → Intent Detection → SQL Execution → AI Summary → Response
```

---
## 3. Repository Structure
```
# error_handling_system

config/
   ├── features.yaml
   ├── schedule.yaml
   ├── settings.py
   ├── teams.yml
   └── projects/
       └── template.yaml

connections/        # Integration scripts
   ├── ai_connections.py
   ├── bitbucket_connections.py
   ├── database_connections.py
   └── jira_connections.py

database/           # DB operations and schema
   ├── database_operations.py
   └── schema/
       └── core_schema.sql

scripts/            # Entry points and utilities
   ├── run.py
   ├── run_self_heal.py
   ├── run_jira_ticketing.py
   ├── setup_project.py
   └── start_webhook_ngrok.sh

src/                # Core and plugins
   ├── core/
   └── plugins/
       ├── chatbot/
       ├── jira_ticketing/
       └── self_heal/
```

---
## 4. Key Components
### 4.1 Core
- **vector_embedding.py** – Encode logs
- **vector_similarity_search.py** – Query Chroma
- **jira_client.py** – Jira operations
- **error_detector.py** – Normalize & classify errors

### 4.2 Plugins
- **jira_ticketing** – Ticket lifecycle
- **chatbot** – Teams bot logic
- **Self healing** – Fixes the error

### 4.3 Runtime
- **run.py** – Orchestrator
- **scheduler.py** – Periodic tasks

### 4.4 Connections
- Database, AI, Jira, Bitbucket

---
## 5. Configuration
Stored under `config/`
- `settings.py` – Global settings
- `features.yaml` – Enable/disable plugins
- `schedule.yaml` – CRON-like tasks
- `projects/` – Team-specific overrides

---
## 6. Environment Setup
### Prerequisites
- **Python 3.11**
- **SQL Server**
- **ChromaDB (SQLite-backed)**
- **Ngrok (dev)**

### Create Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---
## 7. Secrets & Environment Variables
Use `.env` or shell exports. 

### Example
```bash
export DB_SERVER="tcp:sql:1433"
export DB_NAME="DB_NAME"
export JIRA_BASE_URL="https://your.atlassian.net"
export AI_API_KEY="***"
export BOT_PUBLIC_URL="https://xxxx.ngrok.io"
```

**Never commit secrets!**

---
## 8. How to Run
### Error Processing
```bash
python scripts/run_error_extractor.py
```
### Embeddings and Create Jira Tickets
```bash
python scripts/run_jira_ticketing.py
```
### Start Teams Webhook
```bash
./scripts/start_webhook_ngrok.sh
```
### Self-Heal
```bash
python scripts/run_self_heal.py
```
### Full Phase‑1 Pipeline
```bash
python -m scripts.run pipeline --skip-webhook
./scripts/start_webhook_ngrok.sh
```

---
## 9. Core Workflows
### Error → Embeddings → RCA → Ticket
1. Extract log → embeddings
2. Similarity search
3. Retrieve or generate RCA
4. Create ticket

### Chatbot
1. Receive Teams query
2. Detect intent → SQL
3. Execute & summarize via AI
4. Respond

---
## 10. Data Storage & Schema
### SQL Server
- Errors, RCA, Solutions, Tickets

### Vector Store
- ChromaDB SQLite store

---
## 11. Logging & Monitoring
- Structured logs
- Correlation IDs
- Optional push to telemetry

---
## 12. Extensibility
### Add new team/project
1. add to `config/teams.yaml`

### Add new prompts
Modify under `prompts/`

### Add new integrations
Add new client under `src/core` + plugin under `src/plugins`

---
## 13. Troubleshooting
- Check env vars
- Verify DB/Chroma connectivity
- Enable debug mode in logger

---
## 14. Glossary
- **RCA** – Root Cause Analysis
- **Embedding** – Semantic vector representation
- **ChromaDB** – Vector search engine
- **Adaptive Card** – Teams rich card UI

---

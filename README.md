# PolicyWatch — Privacy Policy & Terms Change Tracker

**PolicyWatch** is a unified, full-stack compliance and governance web application designed to track, store, analyze, and visually diff historical revisions of privacy policies and terms of service across the web.

Built with **Python**, **Flask**, **SQLite**, and custom **NLP Legal Clause Classification & Diffing Engines**, PolicyWatch integrates five independently engineered submodules into one cohesive, single-entrypoint application.

---

## 🚀 Quick Start (Windows)

### Option 1: 1-Click Batch Execution
1. Double-click `setup.bat` (first-time only: sets up `.venv`, installs requirements, and seeds the sample database).
2. Double-click `run.bat` (launches server on `http://127.0.0.1:5000`).

### Option 2: Manual Terminal Execution
```powershell
# 1. Activate virtual environment
.venv\Scripts\activate

# 2. Install requirements (if needed)
pip install -r requirements.txt

# 3. Launch application runner
python run.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in any modern web browser.

---

## 🔑 Demo Accounts

The database comes pre-seeded with tracked domains, version histories, classified changes, and notifications:

| Role | Username | Password | Notes |
|---|---|---|---|
| **Administrator** | `admin` | `admin123` | Full workspace access, 3 tracked sites, audit history |
| **Standard User** | `john_doe` | `password123` | Standard account with isolated monitored domains |

---

## 🧪 Master Test Suite (99+ Tests)

A unified test runner verifies all module test suites and end-to-end integration flows:

```powershell
python test_all.py
```

### Verified Test Breakdown:
- **Module 1 (Web Scraping)**: `ptct-scraper/tests/` (38/38 pytest tests passed)
- **Module 2 & 3 (DBMS & Auth)**: `models/test_app.py` (12/12 unittest tests passed)
- **Change Detection Engine**: `change_detection/tests/` (43/43 unittest tests passed)
- **Module 5 (Freshness & Notifications)**: `policywatch_module5/tests/` (5/5 unittest tests passed)
- **End-to-End Integration Flow**: `tests/test_integration.py` (Passed full lifecycle validation)

---

## 🏗️ Architecture & Integrated Modules

```
                           +----------------------------------------+
                           |       Unified Web App (run.py)         |
                           |   Flask + Jinja2 + Responsive SaaS UI  |
                           +-------------------+--------------------+
                                               |
         +--------------------+----------------+--------------------+--------------------+
         |                    |                                     |                    |
         v                    v                                     v                    v
+-----------------+  +-----------------+                   +-----------------+  +-----------------+
|   Module 1:     |  |   Module 2 & 3: |                   |   Module 4:     |  |   Module 5:     |
|   Web Scraping  |  |   DBMS & Auth   |                   |  Search, Filter |  |  Notifications  |
|  & Data Collect |  |  (tracker.db)   |                   |   & Diff View   |  |   & Freshness    |
| (ptct-scraper)  |  |  (models/db.py) |                   |  (diff_utils &  |  |  (m5 service)   |
|                 |  |                 |                   |  change_detect) |  |                 |
+-----------------+  +-----------------+                   +-----------------+  +-----------------+
         |                    |                                     |                    |
         +--------------------+-------------------------------------+--------------------+
                                               |
                                               v
                                   [ SQLite: tracker.db ]
```

### Module 1: Web Scraping and Data Collection (`ptct-scraper/` + `models/scraper_service.py`)
- **Ethical Safety Gate**: Enforces written mentor approval for live collection; synthetic "Acme" sources operate via offline HTML fixtures in `ptct-scraper/fixtures/`.
- **Snapshot Storage**: Captures content SHA-256 hashes, byte sizes, character/word counts, and HTTP status codes in `ScraperSnapshots`.
- **Offline Simulator**: Triggers 7-cycle simulated revision loops directly from the UI or CLI.

### Module 2: Database Management (`models/database.py` & `models/schema.sql`)
- Unified relational schema in SQLite (`models/tracker.db`) with Foreign Keys, indexed lookups, and auto-upgrades (`ensure_schema_upgrades`).
- Core entities: `Users`, `Websites`, `PrivacyPolicies`, `TermsConditions`, `ChangeHistory`, `m5_notifications`, `m5_source_freshness`, `ScraperSnapshots`.

### Module 3: User Authentication & Portal (`models/app.py` & `templates/`)
- User registration, login, logout, and protected session decorators (`@login_required`).
- Secure password hashing using PBKDF2:SHA256.
- Role-based domain ownership and user-specific compliance dashboards.

### Module 4: Search, Filter, and Diff View (COMPLETE IMPLEMENTATION)
- **Unified Search (`/search`)**: Full-text and metadata search querying website names, domains, document bodies, change summaries, and categories.
- **Multi-Criteria Filtering (`/changes`, `/search`)**: Filter across Website, Severity (Critical, Major, Moderate, Minor, None), Clause Category (Data Collection, User Rights, Third-Party Sharing, Security, Dispute), and Review Status.
- **Diff View Comparator (`/compare`)**:
  - **Side-by-Side Comparison**: Synchronized line-numbered table with green additions and red deletions.
  - **Line-by-Line Unified Diff**: Compact inline diff view with visual diff markers `[+]` and `[-]`.
  - **NLP Semantic Clause Classification**: Integrated with `change_detection.api.detect_changes()`, displaying categorizations, severity scoring, and legal rationale.
- **Review & Audit Workflow (`/changes/<id>`)**: Verification interface allowing legal analysts to mark detected changes as `Confirmed`, `Rejected`, or `Unreviewed`, accompanied by auditor notes.

### Module 5: Notifications & Source Freshness (`policywatch_module5/` + `templates/`)
- **Notification Hub (`/notifications`)**: Alert feed for newly detected changes and refresh failures, with unread counters, mark-as-read toggles, and direct links to diffs.
- **Source Freshness Tracker (`/freshness`)**:
  - **Fresh** (green): Verified within the last 24 hours.
  - **Aging** (amber): Verified between 24 and 72 hours ago.
  - **Stale** (red): Not verified for over 72 hours.
  - **Never Checked** (gray): Newly added source awaiting collection.

---

## 📂 Repository File Structure

```
PolicyWatch/
├── run.py                     # Primary Application Entrypoint
├── run.bat                    # 1-Click Windows Server Startup Script
├── setup.bat                  # 1-Click Windows Setup & Seed Script
├── test_all.py                # Master Test Runner (99+ Tests)
├── requirements.txt           # Unified Dependencies Manifest
├── .env.example               # Environment Configuration Template
├── README.md                  # Comprehensive Documentation & Architecture Guide
│
├── models/                    # Module 2 & 3: Database, Auth, Core Backend & Web Routes
│   ├── app.py                 # Unified Flask Web Application & Route Controllers
│   ├── database.py            # SQLite ORM Layer, Schema Migrations & Search Queries
│   ├── schema.sql             # Consolidated Relational Database Schema
│   ├── sample_data.py         # Seed Data Script (Users, Sites, Versions, Changes)
│   ├── diff_utils.py          # Diff Rendering (Side-by-Side & Inline Unified)
│   ├── scraper_service.py     # Bridge between Scraper Engine & Database
│   ├── test_app.py            # Models & Authentication Test Suite
│   └── tracker.db             # Consolidated SQLite Database
│
├── change_detection/          # Semantic NLP Clause Classifier & Change Engine
│   ├── api.py                 # Primary detect_changes() Interface
│   ├── classification.py      # Clause Categorization & Severity Heuristics
│   ├── detection.py           # AST / DOM Section & Sentence Differ
│   └── tests/                 # Change Detection Test Suite (43 tests)
│
├── policywatch_module5/       # Module 5: Freshness & Notification Service
│   ├── service.py             # FreshnessConfig, Notifications, SQLite Context Manager
│   └── tests/                 # Module 5 Test Suite (5 tests)
│
├── ptct-scraper/              # Module 1: Web Scraper & Snapshot Engine
│   ├── src/ptct/              # Fetcher, Parser, Pipeline, Storage, CLI
│   ├── fixtures/              # Offline Synthetic HTML Fixtures
│   └── tests/                 # Scraper Pytest Suite (38 tests)
│
├── templates/                 # Jinja2 Frontend Templates (Modern SaaS UI)
│   ├── base.html              # Layout, SaaS Navigation, Badges & Indicators
│   ├── dashboard.html         # Main Executive Compliance Dashboard
│   ├── search.html            # Module 4 Search & Multi-Criteria Filtering
│   ├── compare_versions.html  # Module 4 Side-by-Side & Unified Diff View
│   ├── changes.html           # Module 4 Detected Changes Exploration Feed
│   ├── change_detail.html     # Module 4 Change Detail & Review Decision Form
│   ├── notifications.html     # Module 5 Notification Center
│   ├── freshness.html         # Module 5 Freshness Monitor
│   ├── scraper.html           # Module 1 Scraper Hub & Snapshot Inspector
│   ├── website_details.html   # Website Hub with Policy/Terms Version History
│   ├── profile.html           # Module 3 User Account Profile
│   ├── login.html             # User Login
│   └── register.html          # User Registration
│
└── tests/
    └── test_integration.py    # End-to-End System Integration Flow Test
```

---

## 🎓 College Project Demonstration Script

When presenting this project:
1. **Launch**: Run `run.bat` or `python run.py` and open `http://127.0.0.1:5000`.
2. **Login**: Sign in with `admin` / `admin123`.
3. **Dashboard**: Point out real-time metrics, active compliance statuses, and monitored domains.
4. **Module 4 (Diff & NLP Classifier)**: Navigate to **Compare** or select a website -> Compare Versions. Show both **Side-by-Side Comparison** and **Line-by-Line Unified Diff**. Highlight the **Policy Change Analysis** panel displaying automatic clause classification (e.g. *User Rights*, *Third-Party Sharing*) and legal severity reasoning.
5. **Module 4 (Audit Workflow)**: Navigate to **Detected Changes**, inspect a change, and submit a review decision with audit commentary.
6. **Module 5 (Freshness & Alerts)**: Open **Freshness Tracker** to explain the 24h/72h SLA lifecycle, then click **Notifications** to demonstrate unread badges and marking as read.
7. **Module 1 (Scraper Engine)**: Visit **Scraper Hub**, demonstrate the ethical mentor approval gate, and click **Run Offline Demo Cycle** to collect fresh SHA-256 snapshots.
8. **Automated Verification**: Open terminal and run `python test_all.py` to show **99+ tests passing** across all modules.

# SchemaGuard AI

### AI-Assisted MongoDB Schema Evolution & Query Compatibility Analysis

**SchemaGuard AI** is a full-stack research prototype that helps developers understand how MongoDB schema changes affect existing application queries. It compares old and new document structures, suggests field mappings, adapts registered queries, verifies results, highlights risky changes, and produces reviewable migration reports.

> **Core idea:** Changing how data is stored should not silently change what an application returns.

**Project version:** 1.0.0  
**Status:** Working local research prototype  
**Research focus:** NoSQL databases, schema evolution, application compatibility, and ML-assisted risk analysis

---

## The Problem

MongoDB offers flexible document structures, but application code often depends on specific field names, paths, and data types. If an application expects a field called `department` and a new database version stores it as `academics.branch`, an unchanged query may return incorrect or empty results.

Other migrations can introduce type changes, missing values, or ambiguous mappings. Simply identifying structural differences does not tell developers whether their existing application queries still behave correctly.

## Our Solution

SchemaGuard AI provides a structured workflow:

```text
Original MongoDB Collection       Migrated MongoDB Collection
               \                    /
                Schema Comparison
                        |
             Intelligent Field Mapping
                        |
                Query Repair Proposal
                        |
             Query Result Verification
                        |
             Migration Impact Analysis
                        |
        Explainable Recommendations + ML Advice
                        |
              Human Review and Audit
                        |
                   PDF / JSON Report
```

### Simple Example

**Original document:**

```json
{
  "student_id": 101,
  "name": "Rahul",
  "department": "ECE",
  "cgpa": 8.5
}
```

**Migrated document:**

```json
{
  "student_id": 101,
  "profile": {"full_name": "Rahul"},
  "academics": {"branch": "ECE", "cgpa": "8.5"}
}
```

A query using `{"department": "ECE"}` may need to be adapted to `{"academics.branch": "ECE"}`. SchemaGuard suggests the mapping and compares the resulting records rather than assuming that a renamed field is automatically safe.

---

## Features

| Module | What it does |
| --- | --- |
| **MongoDB Explorer** | Lists database collections and document counts. |
| **Schema Comparison** | Detects added, removed, type-changed, and coverage-changed field paths. |
| **Intelligent Field Mapping** | Uses corresponding records and normalized values to suggest old-to-new field mappings. |
| **Query Repair** | Generates adapted versions of registered queries for supported schema changes. |
| **Compatibility Verification** | Compares expected and migrated query outputs; distinguishes exact, semantic, and review-required outcomes. |
| **Migration Impact** | Runs registered compatibility checks together and summarizes their impact. |
| **Explainable Recommendations** | Gives reasons and suggested actions for compatibility findings. |
| **ML Research Dashboard** | Displays evaluated risk-classification models and provides advisory scoring for supported historical synthetic scenarios. |
| **Human Review and Audit** | Stores reviewer decisions and notes in MongoDB without executing database migrations. |
| **Report Export** | Generates PDF migration-impact reports and structured result data. |

**Safety design:** Analysis and verification are read-only. Human-review submissions write audit records only; they do **not** execute migrations or automatically change application queries.

## Technology Stack

| Layer | Technology |
| --- | --- |
| Frontend | React, JavaScript (JSX), Vite, CSS |
| UI and Charts | Lucide React, Recharts |
| Backend API | Python, FastAPI |
| Database | MongoDB, PyMongo |
| Machine Learning | Scikit-learn, Pandas, NumPy, Joblib |
| PDF Export | ReportLab |
| Version Control | Git and GitHub |

## Project Structure

```text
SchemaGuard-AI/
├── backend/
│   ├── main.py
│   ├── analyzers/
│   │   ├── schema_inspector.py
│   │   ├── field_mapping.py
│   │   ├── query_repair.py
│   │   ├── migration_impact.py
│   │   ├── advisory_ml.py
│   │   └── report_pdf.py
│   └── database/
│       ├── seed_database.py
│       ├── create_schema_v2.py
│       └── create_schema_v3.py
├── experiments/
│   ├── train_ml_models.py
│   ├── expanded_benchmark_1800.json
│   ├── ml_evaluation_results.json
│   └── ...
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── MigrationImpact.jsx
│   │   └── DecisionCenter.jsx
│   └── package.json
├── requirements_v1.txt
└── README.md
```

The tree highlights major files; see the repository for all scripts and research artifacts.

---

## Research & Experimental Results

SchemaGuard AI was evaluated using **synthetically generated MongoDB migration scenarios**, not production deployments.

| Metric | Result |
| --- | ---: |
| Controlled migration scenarios | **18** |
| Query-scenario evaluations | **1,800** |
| Exact matches | **1,328** |
| Adapter-restored results | **317** |
| Review-required cases | **155** |

The 1,800 evaluations comprise 1,328 exact matches, 317 adapter-restored results, and 155 review-required cases. These are **compatibility outcome counts**, not a model-accuracy metric.

### Machine Learning Evaluation

We evaluated **Logistic Regression** and **Random Forest** on synthetic migration-risk labels, using leave-one-migration-family-out evaluation. Logistic Regression achieved approximately **78.1% recall for risky cases** in the recorded evaluation, but also missed risky cases. A development-set deterministic safety baseline achieved higher recall on known scenarios; this is not evidence of generalization to unseen production migrations.

**Interpretation:** Machine learning is an *advisory signal*. The current system does not claim that a risk score certifies migration safety, nor that ML improves upon every rule-based alternative.

Supporting experimental scripts, evaluation summaries, and datasets are under [`experiments/`](experiments/).

---

## Run Locally

### Prerequisites

- Python 3.11 or a compatible Python 3 environment
- Node.js and npm compatible with Vite 7
- A running MongoDB server (the prototype defaults to `localhost:27017`)
- Git

### 1. Clone the repository

```bash
git clone https://github.com/chauhanneev016-git/SchemaGuard-AI.git
cd SchemaGuard-AI
```

### 2. Set up Python dependencies

**Windows PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements_v1.txt
```

### 3. Configure the local database

Create a `.env` file in the repository root:

```dotenv
MONGO_URI=mongodb://localhost:27017/
DATABASE_NAME=schemaguard_research
```

**Never commit `.env` or database passwords to GitHub.** The application is configured for the research database `schemaguard_research`.

The dashboard's live comparison and verification modules require the **research collections and baseline data**. If starting with an empty MongoDB instance, inspect the scripts in `backend/database/` and the experiment generation scripts before reproducing the datasets. Data generation and schema migrations are separate from the read-only dashboard analysis.

### 4. Start the backend

From the repository root:

```powershell
python -m uvicorn backend.main:app --reload
```

Backend API: http://127.0.0.1:8000  
API documentation: http://127.0.0.1:8000/docs

### 5. Start the frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173/**.

### 6. Reproduce ML experiments when needed

Trained `.joblib` model files are intentionally excluded from the repository. Refer to [`experiments/train_ml_models.py`](experiments/train_ml_models.py) and the accompanying dataset/experiment scripts to recreate trained models. Saved evaluation reports can still be explored independently; do not assume that every feature can run before its prerequisite database or model artifacts are generated.

---

## Demo Workflow

1. Open **Schema Comparison** and compare `students` with `students_v3`.
2. Discover suggested field mappings such as `department → academics.branch`.
3. Open **Query Repair**, select a registered query, and inspect its original and adapted filters.
4. Open **Migration Impact** to review all registered query outcomes together.
5. Inspect **Review & Reports** for explanations, human-review actions, and PDF export.
6. Visit **Machine Learning** to explore historical experimental risk analysis.

## Limitations

- Tested on **controlled synthetic data** and registered queries; generalization to unseen real applications remains unproven.
- Field mapping depends on corresponding records and suitable evidence; ambiguous or missing values require manual investigation.
- Query equivalence is checked only within the supported query and normalization logic.
- A successful registered test does not prove all application behavior is compatible.
- The current ML interface is restricted to supported research scenarios and does not provide a universal risk predictor.
- The backend currently uses **localhost CORS settings** and has no production authentication/authorization layer. **Do not expose this backend publicly without additional security work.**

## Future Work

- Independent evaluation on real-world MongoDB migration workloads
- Broader query/operator support and more robust semantic-equivalence testing
- Improved mapping confidence and handling of ambiguous changes
- Stronger out-of-distribution ML validation
- Secure multi-user review, authentication, and production-ready deployment

## Related Research

Fedushko, S., Malyi, R., Syerov, Y., & Serdyuk, P. (2024). *NoSQL document data migration strategy in the context of schema evolution*. **Data & Knowledge Engineering, 154**, 102369. https://doi.org/10.1016/j.datak.2024.102369

The paper examines how to choose NoSQL migration strategies. SchemaGuard AI explores the complementary problem of **application query compatibility after schema changes**.

---

## Project Status

**Version:** 1.0.0 — completed academic research prototype, suitable for local demonstrations. This repository contains application code and synthetic research artifacts; publishing the repository does not automatically deploy the app as a hosted website.

**Repository:** https://github.com/chauhanneev016-git/SchemaGuard-AI

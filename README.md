# SC4021 Information Retrieval Project

A Django web application for searching and analysing political sentiment in Singapore, powered by Apache Solr.

## 📋 Table of Contents

- [Project Description](#project-description)
- [Prerequisites](#prerequisites)
- [Setup Instructions](#setup-instructions)
- [Running the Application](#running-the-application)
- [Solr — Common Commands](#solr--common-commands)
- [Project Structure](#project-structure)

## 🎯 Project Description

This Django web application provides a search and sentiment analysis interface for Singapore political discourse. Features:

- **Backend:** Django + Apache Solr for full-text search and faceted filtering
- **Frontend:** Django templates with Chart.js visualisations
- **Filters:** sentiment, party, key figure, date range, sort order

## 📦 Prerequisites

- **Python 3.11+** — [Download](https://www.python.org/downloads/)
- **Docker Desktop** — [Download](https://www.docker.com/products/docker-desktop/) (runs Solr, no local install needed)
- **Git** — [Download](https://git-scm.com/downloads)

## 🚀 Setup Instructions

### 1. Clone the repository

```bash
git clone <repo-url>
cd sc4021-ir
```

### 2. Create and activate a Python virtual environment

**macOS / Linux:**

```bash
python -m venv venv
source venv/bin/activate
```

**Windows:**

```cmd
python -m venv venv
venv\Scripts\activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Start Solr with Docker

```bash
docker compose up -d
```

This spins up a Solr container and **automatically creates the `political_opinions` core** using the schema checked into the repo (`solr/configsets/`). Everyone on the team gets the exact same schema, so there is no manual Solr core setup.

> First time only — seed the core with data:
>
> ```bash
> python data/cleaned/index_data.py
> ```

This script loads the cleaned inference dataset from `data/cleaned/singapore_wp_comments_display_inference_id.json`, converts the dates into Solr's expected format, and sends the documents to the `political_opinions` core.

### 5. Set up environment variables (optional)

Create a `.env` file in the project root:

```env
DJANGO_SECRET_KEY=your-dev-secret-key
```

## ▶️ Running the Application

```bash
cd sc4021_ir
python manage.py runserver
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

## 🐳 Solr — Common Commands

Think of `docker compose` like a power strip for the app:

| Command                  | What it does                              |
| ------------------------ | ----------------------------------------- |
| `docker compose up -d`   | Start Solr in the background              |
| `docker compose down`    | Stop Solr (your indexed data is **kept**) |
| `docker compose down -v` | Stop Solr **and wipe all indexed data**   |

> After a `down -v` (full reset), re-run `data/cleaned/index_data.py` to reseed.

Your indexed documents are stored in a Docker **named volume** (`solr_data`), so they survive normal `down`/`up` restarts. Only `-v` deletes them.

## 📁 Project Structure

```
sc4021-ir/
├── classification/                  # NLP pipelines and model notebooks
│   ├── ELECTRA/
│   └── svm/
├── data/                            # Raw and cleaned datasets
│   ├── raw/
│   └── cleaned/
│       ├── data_annotation_clean.csv
│       ├── index_data.py            # Seeds Solr with cleaned inference data
│       ├── singapore_wp_comments_display_inference.csv
│       ├── singapore_wp_comments_display_inference.json
│       └── singapore_wp_comments_display_inference_id.json
├── docker-compose.yaml              # Solr container config
├── requirements.txt
├── sc4021_ir/                       # Django project root
│   ├── db.sqlite3
│   ├── manage.py
│   ├── sc4021_ir/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── mock_data/               # Legacy mock data utilities
│   └── search/
│       ├── views.py
│       ├── urls.py
│       ├── static/
│       │   └── search/
│       │       └── style.css
│       └── templates/
│           └── search/
│               └── index.html
├── solr/
│   └── configsets/
│       └── political_opinions/
│           └── conf/
│               ├── schema.xml
│               └── solrconfig.xml
└── README.md
```

---

**Built with Django & Apache Solr**

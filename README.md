# SC4021 Information Retrieval Project

An opinion search engine for analysing Reddit sentiments toward Singapore's Workers' Party. The system crawls comments from r/Singapore, classifies them by sentiment, indexes them in Apache Solr, and serves an interactive search interface built with Django.

## Prerequisites

- **Python 3.11+** — [Download](https://www.python.org/downloads/)
- **Docker Desktop** — [Download](https://www.docker.com/products/docker-desktop/) (runs Solr)
- **Jupyter Notebook** — included with Anaconda, or `pip install notebook`

## Setup

```bash
git clone <repo-url>
cd sc4021-ir
python -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate          # Windows
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

## Project Structure

```
sc4021-ir/
├── Crawling & Scraping/
│   ├── scrape1.py                          # Reddit crawler (PullPush API)
│   ├── clean_wp_levels.ipynb               # Data cleaning and CSV export
│   └── fleiss_kappa_book1.ipynb            # Inter-annotator agreement (Fleiss' Kappa)
├── classification/
│   ├── svm/
│   │   ├── preprocess_pipeline.py          # Shared text preprocessing module
│   │   ├── 01_preprocess_training_data.ipynb
│   │   ├── 02_train_svm_model.ipynb
│   │   ├── 03_inference_new_data.ipynb
│   │   └── model_artifacts/                # Saved TF-IDF vectoriser and SVM model
│   └── ELECTRA/
│       ├── utils.py                        # Shared utilities and text normalisation
│       └── ELECTRA_pipeline.ipynb          # Fine-tuning, evaluation, and inference
├── data/
│   ├── raw/                                # Original crawled and annotated data
│   ├── output from crawling & scraping/    # Cleaned CSVs (display + training)
│   └── cleaned/                            # Classified data ready for indexing
│       └── index_data.py                   # Seeds Solr with classified data
├── sc4021_ir/                              # Django web application
│   ├── manage.py
│   ├── sc4021_ir/                          # Project settings and URL config
│   └── search/                             # Search app (views, templates, static)
├── solr/configsets/                        # Solr schema configuration
├── docker-compose.yaml
├── requirements.txt
└── README.md
```

## How to Run

### 1. Crawling

Crawls r/Singapore comments matching WP-related seed terms via the PullPush API. Outputs raw JSON (~14,000 comments).

```bash
cd "Crawling & Scraping"
python scrape1.py
```

### 2. Data Cleaning

Open `clean_wp_levels.ipynb` in Jupyter and run all cells. Cleans the raw JSON (HTML unescape, mojibake repair, timestamp conversion to SGT, removal of deleted/bot/short comments, deduplication) and produces two CSVs in `data/output from crawling & scraping/`:
- `singapore_wp_comments_display.csv` — URLs kept, for indexing
- `singapore_wp_comments_training.csv` — URLs removed, for classification

### 3. Inter-Annotator Agreement

Open `fleiss_kappa_book1.ipynb` to compute Fleiss' Kappa across three annotators. Requires `manual-labelling.xlsx` (the annotated evaluation dataset) in the same directory.

### 4. Classification

**SVM pipeline** — run the notebooks in order:

1. `classification/svm/01_preprocess_training_data.ipynb` — preprocesses the labelled data
2. `classification/svm/02_train_svm_model.ipynb` — trains LinearSVC with TF-IDF features, saves model to `model_artifacts/`
3. `classification/svm/03_inference_new_data.ipynb` — classifies the full corpus and outputs results for indexing

**ELECTRA pipeline:**

Run `classification/ELECTRA/ELECTRA_pipeline.ipynb`. Fine-tunes `google/electra-base-discriminator` for three-class sentiment classification. A GPU is recommended (configured for single GPU, BATCH_SIZE=8, dynamic padding).

### 5. Indexing and Web Application

Start Solr:

```bash
docker compose up -d
```

This spins up a Solr container and automatically creates the `political_opinions` core using the schema in `solr/configsets/`.

Seed Solr with the classified data (first time only):

```bash
python data/cleaned/index_data.py
```

Start the Django server:

```bash
cd sc4021_ir
python manage.py runserver
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

### Solr Commands

| Command                  | What it does                              |
| ------------------------ | ----------------------------------------- |
| `docker compose up -d`   | Start Solr in the background              |
| `docker compose down`    | Stop Solr (indexed data is kept)          |
| `docker compose down -v` | Stop Solr and wipe all indexed data       |

After a full reset (`down -v`), re-run `python data/cleaned/index_data.py` to reseed.

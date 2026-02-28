# SC4021 Information Retrieval Project

A Django web application for searching and visualizing Worker's Party opinions, powered by Apache Solr for advanced indexing and search capabilities.

> **Note:** This repository was initially built for MRT Opinions and later adapted for Worker's Party content. Docker Compose configuration is under development, and the Solr schema may undergo changes.

## 📋 Table of Contents

- [Project Description](#project-description)
- [Prerequisites](#prerequisites)
- [Setup Instructions](#setup-instructions)
- [Running the Application](#running-the-application)
- [Project Structure](#project-structure)

## 🎯 Project Description

This Django web application provides a search interface for exploring opinions and content related to the Worker's Party. The application features:

- **Backend:** Django framework with Apache Solr integration for powerful full-text search
- **Frontend:** Django template-based UI with custom styling
- **Search Engine:** Apache Solr for indexing and advanced search capabilities

## 📦 Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.11+** - [Download Python](https://www.python.org/downloads/)
- **pip** - Python package installer (usually included with Python)
- **Git** - [Download Git](https://git-scm.com/downloads)

### Optional (for Solr deployment):

- **Docker** - Required if running Solr in a container locally

## 🚀 Setup Instructions

### 1. Clone the Repository

```bash
git clone <repo-url>
cd sc4021-ir
```

### 2. Create a Python Virtual Environment

**Linux / macOS:**
```bash
python -m venv venv
source venv/bin/activate
```

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables (Optional)

Create a `.env` file in the project root for environment-specific configuration:

```env
DJANGO_SECRET_KEY=your-dev-secret-key
```

## ▶️ Running the Application

### Start the Django Development Server

```bash
cd sc4021_ir
python manage.py runserver
```

### Access the Application

Open your browser and navigate to: [http://127.0.0.1:8000](http://127.0.0.1:8000)

> You can also use http://localhost:8000 - both addresses point to the same local server.

## 📁 Project Structure

```
sc4021-ir/
├── sc4021_ir/              # Django project root
│   ├── manage.py           # Django management script
│   ├── sc4021_ir/          # Main project settings
│   │   ├── settings.py     # Django configuration
│   │   ├── urls.py         # URL routing
│   │   └── mock_data/      # Mock data for development
│   └── search/             # Search application
│       ├── views.py        # View logic
│       ├── models.py       # Data models
│       ├── urls.py         # App-specific URLs
│       ├── static/         # CSS and static files
│       └── templates/      # HTML templates
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

---

**Built with Django & Apache Solr**
# Document Generator

An application for automatically creating DOCX documents based on data from Excel files and Word templates. Allows you to upload an Excel template, apply customizable data transformation rules, and generate a batch of documents using Word templates with Jinja2 variable support.

**Stack:** Streamlit (web interface) + FastAPI (REST API) + Python

---

## Features

- **Excel Upload and Validation** — parsing templates with data validation, detection of missing fields and duplicates
- **Data Transformation** — application of customizable transformation rules (numbers to words, name declension, extraction of date parts, etc.)
- **DOCX Generation** — creation of documents from Word templates with Jinja2 variables
- **Web Interface** — convenient UI on Streamlit with a step-by-step workflow
- **REST API** — FastAPI backend for integration with external systems
- **Result Archiving** — automatic packaging of generated documents into ZIP

---

## Architecture

```
┌──────────────────┐      ┌──────────────────┐       ┌──────────────────────┐
│  Streamlit UI    │────▶│  FastAPI Backend  │─────▶│   Core Logic         │
│  (4 pages)       │      │  (REST endpoints)│       │  (business logic)    │
│                  │      │                  │       │                      │
│  1. Upload       │      │  /process-excel  │       │  data_loading        │
│  2. Transformation│     │  /transform-data │       │  data_transformation │
│  3. Generation   │      │  /generate-docs  │       │  document_generation │
│  4. Settings     │      │  /settings       │       │                      │
└──────────────────┘      │  /download       │       └──────────────────────┘
                          └──────────────────┘
```

---

## Project Structure

```
document-generator/
├── pyproject.toml              # Project configuration and dependencies
├── run-web.bat                 # Quick launch script (Windows)
├── config/
│   └── data_transformation_rules.json  # Transformation rules settings
├── examples/
│   ├── Table for filling.xlsx
│   └── Document templates.zip
├── archives/                   # Folder for saved ZIP archives
├── logs/
│   ├── fastapi/
│   └── streamlit/
└── src/
    ├── core/                   # Business logic
    │   ├── data_loading/       # Excel loading and validation
    │   ├── data_transformation/# Data transformation
    │   ├── document_generation/ # DOCX generation
    │   ├── exceptions/
    │   └── utils/
    ├── shared/
    │   └── settings/           # Shared application settings
    └── web/
        ├── api/                # FastAPI backend
        └── frontend/           # Streamlit frontend
            ├── app.py          # Streamlit entry point
            └── pages/          # Application pages
                ├── 1-load-data.py
                ├── 2-transform-data.py
                ├── 3-generate-documents.py
                └── 4-settings.py
```

---

## Installation

### Requirements

- **Python >= 3.14**

### Installing Dependencies

```bash
# Base dependencies + web mode
pip install -e ".[web]"
```

---

## Launch

### Method 1: BAT Script (Windows)

```bash
run-web.bat
```

### Method 2: Manual Launch

**Terminal 1 — FastAPI Backend:**

```bash
uvicorn src.web.api.main_api:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Streamlit Frontend:**

```bash
streamlit run src/web/frontend/app.py
```

The application will be available at: **http://localhost:8501**

---

## User Guide

### Step 1: 📥 Data Upload

1. Open the **"Load Data"** page
2. Upload an Excel file (`.xlsx` / `.xls`)
3. Click **"Analyze & Load"**
4. Check the results:
   - **📊 Loaded Data** — preview of loaded data
   - **🗺️ Variable Mapping** — variable mapping with readable names
   - **⚠️ Validation Errors** — validation errors and warnings

> **Excel Format:** the first row contains readable field names, the second row contains variable names (for use in templates), starting from the third row — data.

### Step 2: 🔄 Data Transformation

1. Go to the **"Transform Data"** page
2. Check the selected transformation rules (loaded from settings)
3. Click **"Transform Data"**
4. Check the results:
   - **🧩 Transformed Columns** — new transformed columns
   - **🗺️ Variable Mapping** — updated variable mapping
   - **⚠️ Issues** — transformation errors

### Step 3: 📄 Document Generation

1. Go to the **"Generate Documents"** page
2. Upload a ZIP archive with Word templates (`.docx`)
3. Click **"Generate Documents"**
4. Download the result with the **"Download Generated Documents (ZIP)"** button
5. Check the generation status and possible errors

> **Word templates** support Jinja2 variables in the format `{{variable_name}}`. The template file name and output file path can also contain variables for dynamic generation of names and folder structure.

### Step 4: ⚙️ Settings

1. Open the **"Settings"** page
2. Configure transformation rules:
   - Enable/disable rules with the **"Selected"** toggle
   - Configure parameters for each rule
   - Delete unnecessary rules with the **❌** button
   - Add new rules with **"Add Rule"**
3. Click **"Save All Settings"**

---

## API Endpoints

| Method | Endpoint            | Description                                      |
| ---------- | ----------------------- | ---------------------------------------------------- |
| `GET`    | `/settings`           | Get current settings                        |
| `POST`   | `/settings`           | Update settings                               |
| `POST`   | `/process-excel`      | Upload and process Excel file          |
| `POST`   | `/transform-data`     | Transform data according to rules    |
| `POST`   | `/generate-documents` | Generate DOCX documents                        |
| `GET`    | `/download/{archive}` | Download ZIP archive of documents     |

**API Documentation** is available at: `http://localhost:8000/docs` (Swagger UI)

---

## Transformation Rules

Available rule types:

| Rule                  | Description                                                        |
| ------------------------ | -------------------------------------------------------------------- |
| **NumToWordsRule**     | Convert numbers to text representation           |
| **NameDeclensionRule** | Name declension by cases                                   |
| **DatePartGetterRule** | Extract date parts (day, month, year)        |
| **NamePartGetterRule** | Extract parts of full name (last name, first name, patronymic) |
| **NameShortenerRule**  | Shorten names (initials, etc.)                        |

Rule settings are saved in `config/data_transformation_rules.json`.

---

## Configuration

### `config/data_transformation_rules.json`

File for storing transformation rule settings. Created automatically on first API launch. Structure:

```json
{
  "rules_list": [
    {
      "selected": true,
      "type": "numtowords",
      "rule_type": "NumToWordsRule",
      "old_var_name": "amount",
      "old_header_name": "Amount",
      "new_var_name": "amount_words",
      "new_header_name": "Amount in words"
    }
  ]
}
```

### Log Folders

- `logs/fastapi/` — FastAPI backend logs
- `logs/streamlit/` — Streamlit frontend logs

---

## Examples

The `examples/` folder contains demo files:

- **Table for filling.xlsx** — example of a filled Excel table with correct structure (dummy data)
- **Document templates.zip** — archive with Word templates for generation (dummy data)

---
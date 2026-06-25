from pathlib import Path

# PATH PARAMETERS
PROJECT_ROOT: Path = Path(__file__).parent.parent.parent

FASTAPI_LOGS_FOLDER = PROJECT_ROOT / "logs" / "fastapi"
FASTAPI_LATEST_LOG = PROJECT_ROOT / "fastapi_latest_log.txt"

STREAMLIT_LOGS_FOLDER = PROJECT_ROOT / "logs" / "streamlit"
STREAMLIT_LATEST_LOG = PROJECT_ROOT / "streamlit_latest_log.txt"

DATA_TRANSFORMATION_RULES_CONFIG = PROJECT_ROOT / "config" / "data_transformation_rules.json"

SAVED_ARCHIVES_FOLDER = PROJECT_ROOT / "generated_documents"
SAVED_TEMPLATES_FOLDER = PROJECT_ROOT / "saved_templates"

SAVED_ARCHIVES_FOLDER = PROJECT_ROOT / "archives"
MAX_ARCHIVES_ALLOWED = 20
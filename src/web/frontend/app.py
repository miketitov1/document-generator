from pathlib import Path

import streamlit as st

from src.web.settings import STREAMLIT_LOGS_FOLDER, STREAMLIT_LATEST_LOG
from src.web.frontend.logging.init_logging import init_logging

init_logging(STREAMLIT_LOGS_FOLDER, STREAMLIT_LATEST_LOG)

# Load README.md as the home page
readme_path = Path(__file__).parents[3] / "README.md"
if readme_path.exists():
    st.markdown(readme_path.read_text(encoding="utf-8"))
else:
    st.warning("README.md not found.")
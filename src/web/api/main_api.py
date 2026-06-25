import datetime
import logging
import shutil
import tempfile
import zipfile
import asyncio
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


from src.core.document_generation.document_generation_report import (
    DocumentGenerationReport,
)
from src.core.document_generation.document_generator import generate_documents
from src.core.utils.path_utils import cleanup_workspace
from src.web.api.logging.init_logging import init_logging
from src.core.utils.json_utils import load_json, save_json
from src.core.data_loading.data_loader import load_data
from src.core.data_transformation import data_transformer
from src.shared.settings.app_settings import AppSettings
from src.core.data_loading.data_loader_report import DataLoaderReport
from src.core.data_transformation.data_transformation_report import (
    DataTransformationReport,
)
from src.web.settings import (
    DATA_TRANSFORMATION_RULES_CONFIG,
    FASTAPI_LOGS_FOLDER,
    FASTAPI_LATEST_LOG,
    MAX_ARCHIVES_ALLOWED,
    SAVED_ARCHIVES_FOLDER,
)

LOGGER = logging.getLogger(__name__)

app = FastAPI()


class APIReportResponse(BaseModel):
    report: DocumentGenerationReport = Field(
        ...,
        description="The report generated from the document generation process.",
    )
    download_url: str = Field(
        ...,
        description="The URL to download the generated ZIP archive.",
    )


@app.on_event("startup")
def configure_logging() -> None:
    init_logging(FASTAPI_LOGS_FOLDER, FASTAPI_LATEST_LOG)


# @app.get("/")
# def read_root():
#     return {"Hello": "World"}


@app.get("/settings", response_model=AppSettings)
async def get_settings():
    """Fetches the application settings."""
    if (not DATA_TRANSFORMATION_RULES_CONFIG.exists()) or (
        DATA_TRANSFORMATION_RULES_CONFIG.stat().st_size == 0
    ):
        LOGGER.warning(
            "Creating settings file as it was not found at %s",
            DATA_TRANSFORMATION_RULES_CONFIG,
        )
        DATA_TRANSFORMATION_RULES_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        DATA_TRANSFORMATION_RULES_CONFIG.touch()
        save_json(
            str(DATA_TRANSFORMATION_RULES_CONFIG),
            AppSettings().model_dump(),
        )
    raw_data = await asyncio.to_thread(load_json, str(DATA_TRANSFORMATION_RULES_CONFIG))
    app_settings = AppSettings.model_validate(raw_data)
    return app_settings


@app.post("/settings")
async def update_settings(settings: AppSettings):
    """Updates the application settings."""
    await asyncio.to_thread(
        save_json,
        str(DATA_TRANSFORMATION_RULES_CONFIG),
        settings.model_dump(mode="json"),
    )
    return {"message": "Settings updated successfully"}


@app.post("/process-excel")
async def process_excel(file: UploadFile = File(...)):
    """Processes the uploaded Excel file and returns a data loading report."""
    content = await file.read()
    filename = file.filename or "unknown.xlsx"
    report = await asyncio.to_thread(load_data, BytesIO(content), filename)
    return report


@app.post("/transform-data")
async def transform_data(content: DataLoaderReport):
    """Transforms the uploaded Excel file based on the current settings."""
    # Load the current settings
    settings = await get_settings()

    # Perform the transformation based on the settings
    excel_data = content.loaded_data
    mapping = content.variable_to_readable_mapping
    transformation_rules = settings.rules_list
    transformed_report = await asyncio.to_thread(
        data_transformer.transform_data, excel_data, mapping, transformation_rules
    )
    return transformed_report


@app.post("/generate-documents")
def generate_documents_endpoint(
    background_tasks: BackgroundTasks,
    content: str = Form(...),
    template_files_zipped: UploadFile = File(...),
):
    """
    Generates documents based on the transformed data and uploaded templates.
    Saves the generated ZIP permanently on the server and streams it back.

    The transformed data report is sent as a JSON string in the `content` form field
    to avoid FastAPI's inability to parse complex Pydantic models from multipart form data.
    """
    try:
        report = DataTransformationReport.model_validate_json(content)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid DataTransformationReport JSON: {str(e)}",
        )

    transformed_data = report.enriched_data

    # 1. Create unique scratchpad workspace for the document generation process
    workspace_dir = Path(tempfile.mkdtemp(prefix="doc_gen_"))
    templates_folder = workspace_dir / "templates"
    output_folder = workspace_dir / "output"
    templates_folder.mkdir(parents=True, exist_ok=True)
    output_folder.mkdir(parents=True, exist_ok=True)

    # 2. Extract uploaded ZIP archive
    zip_temp_path = workspace_dir / "uploaded_templates.zip"
    try:
        with zip_temp_path.open("wb") as buffer:
            shutil.copyfileobj(template_files_zipped.file, buffer)

        with zipfile.ZipFile(zip_temp_path, "r") as zip_ref:
            zip_ref.extractall(templates_folder)
    except zipfile.BadZipFile:
        shutil.rmtree(workspace_dir)
        raise HTTPException(
            status_code=400,
            detail="The provided file is not a valid ZIP archive.",
        )
    except Exception as e:
        shutil.rmtree(workspace_dir)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process templates ZIP: {str(e)}",
        )

    # 3. Execute document generation and capture the returned report
    try:
        report = generate_documents(
            enriched_data=transformed_data,
            templates_folder=templates_folder,
            output_folder=output_folder,
        )
    except Exception as e:
        shutil.rmtree(workspace_dir)
        raise HTTPException(
            status_code=500,
            detail=f"Document generation failed: {str(e)}",
        )

    # 4. Generate timestamped name and save directly to persistent directory
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    final_zip_path = SAVED_ARCHIVES_FOLDER / f"generated_docs_{timestamp}.zip"
    try:
        shutil.make_archive(
            base_name=str(final_zip_path.with_suffix("")),
            format="zip",
            root_dir=output_folder,
        )
    except Exception as e:
        shutil.rmtree(workspace_dir)
        if final_zip_path.exists():
            final_zip_path.unlink()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to package generated files: {str(e)}",
        )

    # 5. Schedule background cleanup and retention policy
    background_tasks.add_task(
        cleanup_workspace, workspace_dir, SAVED_ARCHIVES_FOLDER, MAX_ARCHIVES_ALLOWED
    )

    # 6. Return the metadata JSON response immediately
    return APIReportResponse(
        report=report, download_url=f"/download/{final_zip_path.name}"
    )


@app.get("/download/{archive_name}")
def download_archive(archive_name: str):
    """
    Serves a previously generated ZIP archive securely.
    """
    safe_path = SAVED_ARCHIVES_FOLDER / archive_name
    try:
        resolved_path = safe_path.resolve()
        resolved_base = SAVED_ARCHIVES_FOLDER.resolve()
        if (not resolved_path.is_relative_to(resolved_base)) or (
            not resolved_path.exists()
        ):
            raise HTTPException(
                status_code=404, detail="Archive not found or has been pruned."
            )

    except Exception:
        raise HTTPException(status_code=404, detail="Archive not found.")

    return FileResponse(
        path=resolved_path,
        media_type="application/zip",
        filename=archive_name,
    )

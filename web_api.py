import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pathlib import Path
from typing import List, Dict, Any
import os # Added for path validation in file serving

from settings import Settings
import navigator

# Initialize FastAPI app and settings
app = FastAPI(title="Document Processing API", version="0.1.0")
settings = Settings()
OUTPUT_DIR = Path(settings.output_dir)

# Ensure output directory exists (though navigator functions handle non-existence gracefully)
if not OUTPUT_DIR.exists():
    print(f"Warning: Output directory {OUTPUT_DIR} does not exist. API might return empty results.")
    # Depending on requirements, you might want to create it:
    # OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    """Simple HTML root page with links to API docs."""
    return """
    <html>
        <head>
            <title>Document API</title>
        </head>
        <body>
            <h1>Document Processing API</h1>
            <p>Welcome to the Document Processing API.</p>
            <p>Swagger UI for API documentation: <a href="/docs">/docs</a></p>
            <p>ReDoc for API documentation: <a href="/redoc">/redoc</a></p>
        </body>
    </html>
    """

@app.get("/senders", response_model=List[str], tags=["Navigation"])
async def list_all_senders():
    """Lists all unique sender names based on folder structure."""
    return navigator.get_all_senders(OUTPUT_DIR)

@app.get("/senders/{sender_name}/letters", response_model=List[str], tags=["Navigation"])
async def list_letters_for_sender(sender_name: str):
    """Lists all document IDs for a given sender."""
    letters = navigator.get_letters_by_sender(OUTPUT_DIR, sender_name)
    if not letters and not (OUTPUT_DIR / sender_name).exists():
        raise HTTPException(status_code=404, detail=f"Sender '{sender_name}' not found.")
    return letters

@app.get("/senders/{sender_name}/letters/{doc_id}/details", response_model=Dict[str, Any], tags=["Document Access"])
async def get_document_details(sender_name: str, doc_id: str):
    """Retrieves the YAML details for a specific document."""
    details = navigator.get_letter_details_yaml(OUTPUT_DIR, sender_name, doc_id)
    if details is None:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' from sender '{sender_name}' not found or YAML missing.")
    return details

@app.get("/senders/{sender_name}/letters/{doc_id}/markdown", response_model=str, tags=["Document Access"])
async def get_document_markdown(sender_name: str, doc_id: str):
    """Retrieves the Markdown content for a specific document."""
    content = navigator.get_letter_markdown_content(OUTPUT_DIR, sender_name, doc_id)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' from sender '{sender_name}' not found or Markdown missing.")
    return content

def _get_filenames_from_paths(paths: List[Path]) -> List[str]:
    return [p.name for p in paths]

@app.get("/senders/{sender_name}/letters/{doc_id}/originals", response_model=List[str], tags=["File Listing"])
async def list_original_scans(sender_name: str, doc_id: str):
    """Lists filenames of original scans for a document."""
    doc_path = navigator._get_doc_path(OUTPUT_DIR, sender_name, doc_id)
    if not doc_path: 
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' from sender '{sender_name}' not found.")
    paths = navigator.get_letter_original_scans(OUTPUT_DIR, sender_name, doc_id)
    return _get_filenames_from_paths(paths)

@app.get("/senders/{sender_name}/letters/{doc_id}/previews", response_model=List[str], tags=["File Listing"])
async def list_previews(sender_name: str, doc_id: str):
    """Lists filenames of previews for a document."""
    doc_path = navigator._get_doc_path(OUTPUT_DIR, sender_name, doc_id)
    if not doc_path:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' from sender '{sender_name}' not found.")
    paths = navigator.get_letter_previews(OUTPUT_DIR, sender_name, doc_id)
    return _get_filenames_from_paths(paths)

@app.get("/senders/{sender_name}/letters/{doc_id}/llm_logs", response_model=List[str], tags=["File Listing"])
async def list_llm_interaction_logs(sender_name: str, doc_id: str):
    """Lists filenames of LLM interaction logs for a document."""
    doc_path = navigator._get_doc_path(OUTPUT_DIR, sender_name, doc_id)
    if not doc_path:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' from sender '{sender_name}' not found.")
    paths = navigator.get_letter_llm_interactions(OUTPUT_DIR, sender_name, doc_id)
    return _get_filenames_from_paths(paths)

@app.get("/senders/{sender_name}/letters/{doc_id}/file/{subfolder}/{filename}", tags=["File Access"])
async def get_document_file(sender_name: str, doc_id: str, subfolder: str, filename: str):
    """
    Serves a specific file (original, preview, or log) for a document.
    'subfolder' must be one of 'original_scans', 'previews', 'llm_interaction_logs'.
    """
    allowed_subfolders = ["original_scans", "previews", "llm_interaction_logs"]
    if subfolder not in allowed_subfolders:
        raise HTTPException(status_code=400, detail=f"Invalid subfolder. Must be one of: {allowed_subfolders}")

    doc_path = navigator._get_doc_path(OUTPUT_DIR, sender_name, doc_id)
    if not doc_path:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' from sender '{sender_name}' not found.")

    # Construct the full path to the requested file
    file_path = (doc_path / subfolder / filename).resolve()
    
    # Security check: Ensure the resolved path is within the intended subfolder
    # This helps prevent path traversal attacks (e.g., filename containing '..')
    intended_subfolder_path = (doc_path / subfolder).resolve()
    if not file_path.is_file() or not str(file_path).startswith(str(intended_subfolder_path)):
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found or access denied in '{subfolder}' for document '{doc_id}'.")
    
    return FileResponse(file_path)


if __name__ == "__main__":
    print(f"Starting API server. Output directory configured to: {OUTPUT_DIR}")
    uvicorn.run("web_api:app", host="0.0.0.0", port=8000, reload=True)

# To run this API:
# 1. Ensure FastAPI and Uvicorn are installed: pip install fastapi "uvicorn[standard]"
# 2. Save this file as web_api.py
# 3. Run from your terminal: python web_api.py
# 4. Access the API at http://localhost:8000 and docs at http://localhost:8000/docs

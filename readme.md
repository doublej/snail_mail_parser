# Snail Mail Parser

Snail Mail Parser is a Python-based document processing system for converting scanned paper mail into structured digital data. It performs OCR, detects QR codes, classifies content using an LLM, and outputs structured results in YAML and Markdown formats.

- Watches a specified directory for new scanned documents
- Groups related files into document sessions based on filename patterns
- Extracts and classifies text and metadata
- Outputs structured data for further processing or archival

---

## Core Capabilities

### 📥 Document Ingestion
- **File Monitoring**: Watches a directory using `watchdog`
- **Format Support**: `*.png`, `*.jpg`, `*.jpeg`, `*.tif`, `*.tiff`, `*.pdf`
- **Multi-page Grouping**: LLM judgement based.

### 🧠 Data Extraction & Classification
- **OCR Engine**: `pytesseract` + `pdf2image` or `PyMuPDF`
- **QR Detection**: `pyzbar`
- **LLM Analysis**: Calls GPT-4o via OpenAI API to classify and extract fields:
  - `sender`
  - `date`
  - `subject`
  - `document_type`
  - `content_summary`
  - `payment_info` (IBAN, amount, due date)
  - `suspected_qr`: boolean flag

### 🗃️ Output
- **YAML**: Machine-readable structured output
- **Markdown**: Human-readable summary document
- **Thumbnails**: Optional preview images of pages

---

## Architecture

- **Language**: Python 3.11+
- **Libraries**:
  - `watchdog`, `pytesseract`, `pyzbar`, `pdf2image`, `PyMuPDF`
  - `openai`, `pydantic`, `ruamel.yaml`, `markdown-it-py`
- **API**: Optional FastAPI service for document retrieval
- **Config**: `.env` or settings.py via `pydantic-settings`

---

## Security & Logging

- Logs all processing steps with timestamps
- Tracks file paths, OCR output, LLM prompts/responses
- Optionally run behind FastAPI with auth middleware
- Can be isolated from internet (except OpenAI endpoint)

---

## Deployment

- Clone repo and install dependencies:
  ```sh
  pip install -r requirements.txt
import openai
from typing import List
from pydantic import BaseModel, ValidationError

class Payment(BaseModel):
    iban: str
    amount: float
    due_date: str

class LetterLLMResponse(BaseModel):
    id: str
    sender: str
    date_sent: str
    subject: str
    type: str
    content: str
    qr_payloads: List[str]
    payment: Payment

def classify_document(text: str, qr_payloads: List[str], doc_id: str, settings) -> LetterLLMResponse:
    """
    Send OCR text and QR payloads to LLM and parse the JSON response into a LetterLLMResponse.
    """
    # Configure OpenAI (OpenRouter) API credentials
    openai.api_base = settings.llm_base_url
    openai.api_key = settings.llm_api_key

    # Build prompt for classification
    prompt = (
        "You are an AI assistant that classifies documents. "
        "Given the OCR-extracted text of a document, extract relevant information into a JSON object "
        "with the following fields: id, sender, date_sent, subject, type, content, qr_payloads (list of strings), "
        "and payment (an object with iban, amount, due_date). "
        "The qr_payloads should include any QR code content found in the document.\n\n"
        f"Document ID: {doc_id}\n"
        f"OCR Text: \"\"\"\n{text}\n\"\"\"\n"
        f"QR Payloads: {qr_payloads}\n\n"
        "Return a JSON object."
    )
    response = openai.ChatCompletion.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    content = response["choices"][0]["message"]["content"]
    # Parse JSON (it may come as a dict already, or a string)
    if isinstance(content, str):
        import json
        content = json.loads(content)

    try:
        result = LetterLLMResponse.parse_obj(content)
    except ValidationError:
        # If id was missing or invalid, insert our doc_id and retry parsing
        content['id'] = doc_id
        result = LetterLLMResponse.parse_obj(content)

    # Override any ID with our generated ID (ensuring consistency)
    result.id = doc_id
    return result

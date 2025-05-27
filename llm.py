from openai import OpenAI # Changed import
from typing import List
from pydantic import BaseModel, ValidationError
import json # Added for robust JSON parsing

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
    # Initialize OpenAI client (for v1.0.0+ SDK)
    client = OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )

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
    
    completion = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"} # Ensure your model/provider supports this
    )
    
    raw_content = completion.choices[0].message.content
    
    # Parse JSON content from the LLM response
    # The content should be a JSON string.
    parsed_json_content = {}
    if raw_content:
        try:
            parsed_json_content = json.loads(raw_content)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from LLM: {e}")
            print(f"Raw content from LLM: {raw_content}")
            # Handle error appropriately, e.g., by returning a default/error response
            # For now, we'll try to proceed with a potentially empty dict or raise error
            # Or, create a default error LetterLLMResponse
            # For simplicity, let's ensure 'id' is present and try to parse
            parsed_json_content = {'id': doc_id, 'subject': 'Error: Invalid LLM Response'}


    # Ensure our doc_id is used, overriding any ID from the LLM
    parsed_json_content['id'] = doc_id
    # Ensure qr_payloads is present if missing from LLM, and is a list
    if 'qr_payloads' not in parsed_json_content or not isinstance(parsed_json_content.get('qr_payloads'), list):
        parsed_json_content['qr_payloads'] = qr_payloads # Use the original qr_payloads if LLM doesn't provide valid ones

    try:
        # Using model_validate for Pydantic V2
        result = LetterLLMResponse.model_validate(parsed_json_content)
    except ValidationError as e:
        print(f"Pydantic validation error after attempting to parse LLM response: {e}")
        print(f"Content given to Pydantic: {parsed_json_content}")
        # Fallback or re-raise, here we create a minimal error response
        # This ensures the function always returns a LetterLLMResponse object
        # You might want to make this more robust based on requirements
        error_data = {
            "id": doc_id,
            "sender": "Unknown",
            "date_sent": "Unknown",
            "subject": f"Validation Error: {e.errors()[0]['msg'] if e.errors() else 'Unknown validation error'}",
            "type": "Error",
            "content": f"Failed to parse LLM response. Raw content: {raw_content}",
            "qr_payloads": qr_payloads,
            "payment": {"iban": "Unknown", "amount": 0.0, "due_date": "Unknown"}
        }
        result = LetterLLMResponse.model_validate(error_data)
        
    # Final override to ensure our doc_id is the one used.
    # This is redundant if parsed_json_content['id'] = doc_id was effective and not overwritten by model_validate
    # but good for safety.
    result.id = doc_id
    return result

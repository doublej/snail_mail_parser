from openai import OpenAI # Changed import
from typing import List, Optional # Added Optional
from pydantic import BaseModel, ValidationError
import json # Added for robust JSON parsing

class Payment(BaseModel):
    iban: Optional[str] = None
    amount: Optional[float] = None
    due_date: Optional[str] = None

class LetterLLMResponse(BaseModel):
    id: str
    sender: str
    date_sent: str
    subject: str
    type: str
    content: str
    qr_payloads: List[str]
    payment: Payment
    # New fields for multi-page document handling
    is_multipage_explicit: Optional[bool] = False # Does the page explicitly state it's part of a multi-page doc (e.g., "page 1 of 2")?
    is_information_complete: Optional[bool] = True # Does the page seem to contain a complete piece of information, or does it seem to be cut off?
    belongs_to_open_doc_id: Optional[str] = None # If this page belongs to an existing open document, what is its ID?

def classify_document(text: str, qr_payloads: List[str], doc_id: str, settings, open_docs_summary: Optional[List[dict]] = None) -> LetterLLMResponse:
    """
    Send OCR text and QR payloads to LLM and parse the JSON response into a LetterLLMResponse.
    """
    # Initialize OpenAI client (for v1.0.0+ SDK)
    client = OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )

    # Build prompt for classification
    prompt_parts = [
        "You are an AI assistant that classifies documents. "
        "Given the OCR-extracted text of a document, extract relevant information into a JSON object.",
        "The JSON object must include these fields: id, sender, date_sent, subject, type, content, qr_payloads (list of strings), "
        "payment (an object with iban, amount, due_date), is_multipage_explicit (boolean), "
        "is_information_complete (boolean), and belongs_to_open_doc_id (string or null).",
        
        f"\nDocument ID for the current page: {doc_id}",
        f"OCR Text: \"\"\"\n{text}\n\"\"\"",
        f"QR Payloads found on this page: {qr_payloads}",

        "\nMulti-page document considerations:",
        "- 'is_multipage_explicit': Set to true if the page explicitly mentions being part of a multi-page document (e.g., 'page 1 of 2', 'continued on next page'). Otherwise, false.",
        "- 'is_information_complete': Set to false if the text seems abruptly cut off or clearly incomplete. Otherwise, true.",
        "- 'belongs_to_open_doc_id': If this page belongs to one of the 'Currently Open Documents' listed below, set this to the ID of that document. Otherwise, set it to null."
    ]

    if open_docs_summary:
        prompt_parts.append("\nCurrently Open Documents (documents awaiting more pages):")
        if not open_docs_summary: # Ensure it's not an empty list causing issues
             prompt_parts.append("  (None)")
        for open_doc in open_docs_summary:
            prompt_parts.append(f"  - ID: {open_doc['id']}, Subject: {open_doc['subject']}, Snippet: {open_doc['content_snippet']}...")
    else:
        prompt_parts.append("\nNo documents are currently open and awaiting more pages.")

    prompt_parts.append("\nReturn ONLY the JSON object.")
    prompt = "\n".join(prompt_parts)
    
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
        # You might want to make this more robust based on requirements
        error_subject = f"Validation Error: {e.errors()[0]['msg'] if e.errors() else 'Unknown validation error'}"
        print(f"Creating fallback error response for doc_id {doc_id} due to: {error_subject}")
        error_data = {
            "id": doc_id,
            "sender": "Unknown",
            "date_sent": "Unknown",
            "subject": error_subject,
            "type": "Error",
            "content": f"Failed to parse LLM response. Raw content was: {raw_content}",
            "qr_payloads": qr_payloads, # Use original QR payloads
            "payment": {"iban": None, "amount": None, "due_date": None}, # Default to None for payment fields
            "is_multipage_explicit": False,
            "is_information_complete": True, # Assume complete on error, or could be False
            "belongs_to_open_doc_id": None
        }
        result = LetterLLMResponse.model_validate(error_data)
        
    # Final override to ensure our doc_id is the one used.
    # This is redundant if parsed_json_content['id'] = doc_id was effective and not overwritten by model_validate
    # but good for safety.
    result.id = doc_id
    return result

from openai import OpenAI
from typing import List, Optional
from pydantic import BaseModel, ValidationError
import json 
from enum import Enum
import os # Added for listing directories
from pathlib import Path # To ensure settings.output_dir is a Path object

# Define an Enum for document types
class DocumentType(str, Enum):
    LETTER = "letter"
    INVOICE = "invoice"
    TAXES = "taxes"
    STATEMENT = "statement"
    FORM = "form"
    RECEIPT = "receipt"
    REPORT = "report"
    OTHER = "other"
    ERROR = "Error" # For fallback cases

class Payment(BaseModel):
    iban: Optional[str] = None
    amount: Optional[float] = None
    due_date: Optional[str] = None

class LetterLLMResponse(BaseModel):
    id: str
    sender: str
    date_sent: str
    subject: str
    type: DocumentType # Changed to use the Enum
    content: str
    qr_payloads: List[str]
    payment: Optional[Payment] = None # Allow payment to be None if not applicable
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

    # List existing sender folders
    existing_sender_folders = []
    output_path = Path(settings.output_dir)
    if output_path.exists() and output_path.is_dir():
        try:
            existing_sender_folders = [d.name for d in output_path.iterdir() if d.is_dir()]
        except Exception as e:
            print(f"Warning: Could not list sender folders in {output_path}: {e}")

    # System prompt defining the AI's role and general instructions
    system_prompt_parts = [
        "You are an AI assistant expert at extracting structured information from documents. "
        "Analyze the provided OCR text and QR codes. Populate all fields of the LetterLLMResponse schema accurately. ",
        "For the 'sender' field, provide the sender's name in a simple, concise, and folder-friendly format (e.g., 'AcmeCorp' instead of 'Acme Corporation, Ltd. & Sons'). Avoid special characters that are problematic for directory names.",
        "The 'type' field must be one of the following: " + ", ".join([t.value for t in DocumentType if t != DocumentType.ERROR]) + ". ",
        "Pay close attention to the multi-page document instructions if provided.",
        "When asked to return the original content you can correct small OCR mistakes",
    ]
    system_prompt = "\n".join(system_prompt_parts)


    # User prompt parts
    user_prompt_parts = [
        f"Document ID for the current page: {doc_id}",
        f"OCR Text: \"\"\"\n{text}\n\"\"\"",
        f"QR Payloads found on this page: {qr_payloads}",
        "\nMulti-page document considerations:",
        "- 'is_multipage_explicit': Set to true if the page explicitly mentions being part of a multi-page document (e.g., 'page 1 of 2', 'continued on next page'). Otherwise, false.",
        "- 'is_information_complete': Set to false if the text seems abruptly cut off or clearly incomplete. Otherwise, true.",
        "- 'belongs_to_open_doc_id': If this page belongs to one of the 'Currently Open Documents' listed below, set this to the ID of that document. Otherwise, set it to null."
    ]

    if open_docs_summary:
        user_prompt_parts.append("\nCurrently Open Documents (documents awaiting more pages):")
        if not open_docs_summary:
            user_prompt_parts.append("  (None)")
        for open_doc in open_docs_summary:
            user_prompt_parts.append(f"  - ID: {open_doc['id']}, Subject: {open_doc['subject']}, Snippet: {open_doc['content_snippet']}...")
    else:
        user_prompt_parts.append("\nNo documents are currently open and awaiting more pages.")
    
    if existing_sender_folders:
        user_prompt_parts.append("\nConsider these existing sender names/folders when determining the sender (try to be consistent if a similar sender already exists):")
        for folder_name in existing_sender_folders:
            user_prompt_parts.append(f"  - {folder_name}")
    else:
        user_prompt_parts.append("\nNo existing sender folders found to consider for sender name consistency.")


    user_prompt = "\n".join(user_prompt_parts)

    raw_content_for_error = "" # Store raw text for error reporting if needed

    try:
        completion = client.beta.chat.completions.parse(
            model=settings.llm_model, # Ensure this model supports structured outputs (e.g., gpt-4o)
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format=LetterLLMResponse # Pass the Pydantic model directly
        )

        if completion.choices[0].message.refusal:
            print(f"LLM refused to process request for doc_id {doc_id}: {completion.choices[0].message.refusal}")
            # Create a fallback error response
            error_subject = f"LLM Refusal: {completion.choices[0].message.refusal}"
            # The raw_content might not be available or relevant in case of refusal before generation
            # We'll use the refusal message as the content.
            raw_content_for_error = f"Refusal: {completion.choices[0].message.refusal}"
            raise ValueError(error_subject) # Trigger the common error handling path

        result = completion.choices[0].message.parsed
        if not result: # Should not happen if no refusal and parse is successful
             raise ValueError("LLM returned no parsed data despite no refusal.")

        # Ensure our doc_id is used, overriding any ID from the LLM
        result.id = doc_id
        # Ensure qr_payloads are correctly set if LLM missed them or returned non-list
        if not isinstance(result.qr_payloads, list):
            result.qr_payloads = qr_payloads

        return result

    except Exception as e: # Catch OpenAI API errors, validation errors from .parse(), or our ValueError
        print(f"Error during LLM processing or Pydantic parsing for doc_id {doc_id}: {e}")
        # If raw_content_for_error is not set, it means error happened before/during API call,
        # so actual LLM output might not be available.
        # If 'e' is a Pydantic ValidationError, it might have more details.
        # If 'e' is an OpenAI API error, it will have its own structure.

        error_subject_detail = str(e)
        if isinstance(e, ValidationError):
            error_subject_detail = f"{e.errors()[0]['msg'] if e.errors() else 'Unknown validation issue'}"
        
        error_subject = f"LLM/Validation Error: {error_subject_detail}"
        
        # Try to get raw content if available from the exception (e.g. if it's a custom error that wrapped it)
        # For now, we rely on raw_content_for_error or a generic message.
        # If the error is from client.beta.chat.completions.parse, the raw response might be harder to get
        # than with the older client.chat.completions.create.
        # The 'raw_content' variable from the old code isn't directly available here.
        # We'll use a placeholder if specific raw output isn't captured.
        
        final_error_content = f"Failed to get valid structured response from LLM. Error: {str(e)}"
        if raw_content_for_error: # This would be set if it was a refusal
            final_error_content = f"LLM Refusal: {raw_content_for_error}"
        
        print(f"Creating fallback error response for doc_id {doc_id} due to: {error_subject}")
        error_data = {
            "id": doc_id,
            "sender": "Unknown",
            "date_sent": "Unknown",
            "subject": error_subject,
            "type": DocumentType.ERROR, # Use the Enum for error type
            "content": final_error_content,
            "qr_payloads": qr_payloads, 
            "payment": None, # Simpler fallback for payment
            "is_multipage_explicit": False,
            "is_information_complete": True, 
            "belongs_to_open_doc_id": None
        }
        # Validate the error data itself to ensure it conforms to LetterLLMResponse
        # This should always pass if error_data is structured correctly.
        return LetterLLMResponse.model_validate(error_data)

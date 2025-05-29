import traceback
from datetime import datetime
from queue import Queue
# import time # No longer needed for last_seen_timestamp
import shutil # Added for rmtree in merge operation
from pathlib import Path # Added for merge operation
from typing import List, Dict, Any # For type hints

from ocr import ocr_image, ocr_pdf
from qr import scan_qr
from llm import classify_document, LetterLLMResponse, DocumentType # Added DocumentType for Enum check
from output import save_output
import navigator # Added for merge operation
from enum import Enum # Added for Enum check

class Processor:
    def __init__(self, settings, queue: Queue):
        self.settings = settings
        self.queue = queue
        self.doc_seq = 0
        self.open_documents = {}  # Stores doc_id -> {'letter_data': LetterLLMResponse, 'page_paths': List[Path]}
        # self.document_timeout_s removed

    def get_new_doc_id(self) -> str:
        """Generate a new document ID: YYYYMMDD-XXXX sequence."""
        self.doc_seq += 1
        return f"{datetime.now().strftime('%Y%m%d')}-{self.doc_seq:04d}"

    def _prepare_open_documents_summary(self):
        summary = []
        for doc_id, data in self.open_documents.items():
            letter_data = data['letter_data']
            summary.append({
                'id': doc_id,
                'subject': letter_data.subject,
                'content_snippet': letter_data.content[:200] # First 200 chars as snippet
            })
        return summary

    def process_document_pages(self, pages):
        """
        Processes a list of pages (currently expected to be a single page/file path).
        Manages multi-page document assembly based on LLM feedback.
        """
        if not pages or not isinstance(pages, list) or len(pages) != 1:
            print(f"Processor: Expected a single page path in a list, but got: {pages}. Skipping.")
            return
        
        current_page_path = pages[0]
        print(f"Processor: Starting processing for page: {current_page_path}")

        try:
            text_all = ""
            qr_payloads = []
            
            if current_page_path.suffix.lower() == '.pdf':
                print(f"Processor: OCRing PDF page: {current_page_path}")
                text, _ = ocr_pdf(current_page_path)
                text_all += text + "\n"
                # QR scanning for PDFs could be added here if desired
            else: # Image
                print(f"Processor: OCRing image page: {current_page_path}")
                text, _ = ocr_image(current_page_path)
                text_all += text + "\n"
                print(f"Processor: Scanning QR codes for image page: {current_page_path}")
                qr_payloads.extend(scan_qr(current_page_path))
            
            if not text_all.strip() and not qr_payloads:
                print(f"Processor: No text or QR codes found for page {current_page_path}. Skipping.")
                return

            # Generate a candidate ID for this new page.
            # This ID will become the document's ID if it's a new document,
            # or it might be superseded if this page belongs to an existing open document.
            candidate_page_id = self.get_new_doc_id()
            
            open_docs_summary = self._prepare_open_documents_summary()
            
            print(f"Processor: Classifying page {candidate_page_id} with LLM. Open docs summary: {len(open_docs_summary)}")
            llm_response = classify_document(
                text_all, 
                qr_payloads, 
                candidate_page_id, # Pass the new page's candidate ID
                self.settings, 
                open_docs_summary
            )

            # Ensure the ID from LLM response is the one we manage, not one LLM might make up for the current page.
            # The llm_response.id should be the candidate_page_id we sent.
            # If belongs_to_open_doc_id is set, that takes precedence for document identity.
            
            final_doc_id_to_process = llm_response.id # This should be candidate_page_id

            if llm_response.belongs_to_open_doc_id and llm_response.belongs_to_open_doc_id in self.open_documents:
                existing_doc_id = llm_response.belongs_to_open_doc_id
                print(f"Processor: Page {candidate_page_id} (LLM ID: {llm_response.id}) belongs to open document {existing_doc_id}.")
                
                open_doc_entry = self.open_documents[existing_doc_id]
                existing_letter_data = open_doc_entry['letter_data']
                
                # Append current page path to the list of paths for this open document
                if 'page_paths' not in open_doc_entry: # Should have been initialized, but good practice
                    open_doc_entry['page_paths'] = []
                open_doc_entry['page_paths'].append(current_page_path)

                # Append content (ensure newline separation)
                existing_letter_data.content += f"\n\n--- Page Break (Original Page ID: {llm_response.id}) ---\n\n{llm_response.content}"
                # Merge QR payloads (avoid duplicates)
                for qr in llm_response.qr_payloads:
                    if qr not in existing_letter_data.qr_payloads:
                        existing_letter_data.qr_payloads.append(qr)
                
                # Update completeness based on the new page. If any page says it's not complete, the doc isn't.
                # Or, if the new page says it IS complete, and previous also thought so, it remains complete.
                # A more sophisticated logic might be needed if LLM gives conflicting "is_complete" for same doc.
                # For now, if the new page says it's not complete, the whole document is marked not complete.
                if not llm_response.is_information_complete:
                    existing_letter_data.is_information_complete = False
                # If the new page IS complete, but the existing doc was marked incomplete, it remains incomplete
                # unless this page explicitly completes it (e.g. "page 2 of 2").
                # The current Pydantic model doesn't capture "final page" explicitly, relies on is_information_complete.

                # open_doc_entry['last_seen_timestamp'] = time.time() # Removed
                
                if existing_letter_data.is_information_complete:
                    print(f"Processor: Document {existing_doc_id} now considered complete. Saving.")
                    # Pass the accumulated page paths for this multi-page document
                    save_output(existing_letter_data, open_doc_entry['page_paths'], self.settings)
                    del self.open_documents[existing_doc_id]
                    print(f"Successfully processed and closed multi-page document: {existing_doc_id}")
                else:
                    print(f"Processor: Document {existing_doc_id} updated, still awaiting more pages.")

            elif not llm_response.is_information_complete or llm_response.is_multipage_explicit:
                # This is a new multi-page document or the first page of one.
                # The llm_response.id (which is candidate_page_id) becomes the ID for this new open document.
                actual_doc_id = llm_response.id 
                print(f"Processor: Page {actual_doc_id} is part of a new multi-page document. Keeping it open.")
                self.open_documents[actual_doc_id] = {
                    'letter_data': llm_response, 
                    # 'last_seen_timestamp': time.time(), # Removed
                    'page_paths': [current_page_path] 
                }
            else:
                # This is a single, complete document.
                actual_doc_id = llm_response.id
                print(f"Processor: Page {actual_doc_id} is a complete single-page document. Saving.")
                # Pass the current page path as a list for this single-page document
                save_output(llm_response, [current_page_path], self.settings)
                print(f"Successfully processed single-page document: {actual_doc_id}")

        except Exception:
            # Use candidate_page_id if available, otherwise a generic error name
            doc_id_str = locals().get('candidate_page_id', f"error_page_{current_page_path.name}")
            error_filename = f"{doc_id_str}_{datetime.now().strftime('%Y%m%d%H%M%S')}.error"
            error_path = self.settings.output_dir / error_filename
            print(f"Processor: Error processing page {current_page_path}. Saving error to {error_path}")
            with open(error_path, 'w') as ef:
                ef.write(f"Error processing page: {current_page_path}\n")
                ef.write(traceback.format_exc())

    # def check_open_document_timeouts(self): # Method entirely removed

    def flush_open_documents(self):
        """Saves all currently open documents."""
        print(f"Processor: Flushing all {len(self.open_documents)} open documents...")
        if not self.open_documents:
            print("Processor: No open documents to flush.")
            return
            
        for doc_id in list(self.open_documents.keys()): 
            print(f"Processor: Flushing document {doc_id}.")
            open_doc_entry = self.open_documents[doc_id]
            data_to_save = open_doc_entry['letter_data']
            page_paths_to_save = open_doc_entry.get('page_paths', []) # Get page_paths

            data_to_save.is_information_complete = True 
            save_output(data_to_save, page_paths_to_save, self.settings)
            del self.open_documents[doc_id]
            print(f"Successfully flushed document: {doc_id}")
        print("Processor: All open documents flushed.")

    def get_open_documents_summary(self) -> List[Dict[str, Any]]:
        """Returns a summary of currently open multi-page documents."""
        summary_list = []
        for doc_id, data in self.open_documents.items():
            letter_data = data['letter_data']
            summary_list.append({
                "id": doc_id,
                "subject": letter_data.subject,
                "sender": letter_data.sender,
                "type": letter_data.type.value if isinstance(letter_data.type, Enum) else letter_data.type,
                "page_count": len(data.get('page_paths', [])),
                "is_information_complete_llm": letter_data.is_information_complete, # LLM's original assessment
                "is_multipage_explicit_llm": letter_data.is_multipage_explicit # LLM's original assessment
            })
        return summary_list

    def force_complete_open_document(self, doc_id: str) -> bool:
        """Forces a specific open document to be considered complete, saves, and closes it."""
        if doc_id in self.open_documents:
            print(f"Processor: Force completing document {doc_id}.")
            open_doc_entry = self.open_documents[doc_id]
            data_to_save = open_doc_entry['letter_data']
            page_paths_to_save = open_doc_entry.get('page_paths', [])

            data_to_save.is_information_complete = True # Mark as complete by user action
            save_output(data_to_save, page_paths_to_save, self.settings)
            del self.open_documents[doc_id]
            print(f"Successfully force-completed and closed document: {doc_id}")
            return True
        else:
            print(f"Processor: Cannot force complete. Document ID {doc_id} not found in open documents.")
            return False

    def merge_processed_document_into_open_document(
        self, 
        target_open_doc_id: str, 
        source_sender_name: str, 
        source_doc_id: str
    ) -> bool:
        """
        Merges an already processed and saved standalone document (source) 
        into an existing open multi-page document (target).
        The source document's folder will be deleted after successful merge.
        """
        output_base_dir = Path(self.settings.output_dir) # Use output_dir from settings

        if target_open_doc_id not in self.open_documents:
            print(f"Processor: Target open document {target_open_doc_id} not found.")
            return False

        source_yaml_data = navigator.get_letter_details_yaml(output_base_dir, source_sender_name, source_doc_id)
        if not source_yaml_data:
            print(f"Processor: Source document {source_doc_id} (sender: {source_sender_name}) YAML details not found.")
            return False
        
        # Reconstruct source LetterLLMResponse to easily access fields with correct types
        try:
            # Ensure 'type' from YAML is converted back to DocumentType Enum if needed
            source_type_str = source_yaml_data.get("type")
            if source_type_str:
                 source_yaml_data["type"] = DocumentType(source_type_str)
            # Same for payment if it's a dict
            if isinstance(source_yaml_data.get("payment"), dict):
                from llm import Payment # Local import for pydantic model if not globally available
                source_yaml_data["payment"] = Payment.model_validate(source_yaml_data["payment"])

            source_letter = LetterLLMResponse.model_validate(source_yaml_data)
        except Exception as e:
            print(f"Processor: Error reconstructing source document {source_doc_id} from YAML: {e}")
            return False
        
        source_content = source_letter.content
        source_qr_payloads = source_letter.qr_payloads
        source_original_scans_paths = navigator.get_letter_original_scans(output_base_dir, source_sender_name, source_doc_id)
        
        target_doc_entry = self.open_documents[target_open_doc_id]
        target_letter_data = target_doc_entry['letter_data']

        target_letter_data.content += f"\n\n--- Merged Page (Original Source ID: {source_doc_id}, Sender: {source_letter.sender}) ---\n\n{source_content}"
        
        if source_qr_payloads:
            for qr in source_qr_payloads:
                if qr not in target_letter_data.qr_payloads:
                    target_letter_data.qr_payloads.append(qr)
        
        if source_original_scans_paths:
            target_doc_entry.setdefault('page_paths', []).extend(source_original_scans_paths) # Ensure page_paths exists
        
        print(f"Processor: Merged source document {source_sender_name}/{source_doc_id} into {target_open_doc_id}.")

        source_doc_folder_path = navigator._get_doc_path(output_base_dir, source_sender_name, source_doc_id)
        if source_doc_folder_path and source_doc_folder_path.exists():
            try:
                shutil.rmtree(source_doc_folder_path)
                print(f"Processor: Deleted original folder for merged document {source_doc_folder_path}.")
            except Exception as e:
                print(f"Processor: Error deleting folder for merged document {source_doc_folder_path}: {e}")
        
        return True

    def process_next_item_from_queue(self):
        """
        Gets one item from the queue (if available without blocking) and processes it.
        Returns True if an item was processed, False otherwise.
        """
        if not self.queue.empty():
            pages_to_process = self.queue.get_nowait() # Get item without blocking
            if pages_to_process: # Check if it's not a None sentinel or empty list by mistake
                self.process_document_pages(pages_to_process)
                self.queue.task_done() # Signal that the item from queue is processed
                return True
        return False

    # The run() method and _worker() method are removed as processing is now driven by main.py

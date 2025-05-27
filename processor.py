import traceback
from datetime import datetime
from queue import Queue
import time # Added for timestamping open documents

from ocr import ocr_image, ocr_pdf
from qr import scan_qr
from llm import classify_document, LetterLLMResponse # Import LetterLLMResponse
from output import save_output

class Processor:
    def __init__(self, settings, queue: Queue):
        self.settings = settings
        self.queue = queue
        self.doc_seq = 0
        self.open_documents = {}  # Stores doc_id -> {'letter_data': LetterLLMResponse, 'last_seen_timestamp': float}
        # Assuming document_timeout_s will be in settings, e.g., settings.document_timeout_s = 300 (5 minutes)
        self.document_timeout_s = getattr(settings, 'document_timeout_s', 300) 

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

                open_doc_entry['last_seen_timestamp'] = time.time()
                
                if existing_letter_data.is_information_complete:
                    print(f"Processor: Document {existing_doc_id} now considered complete. Saving.")
                    save_output(existing_letter_data, self.settings)
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
                    'letter_data': llm_response, # llm_response already has the content of the first page
                    'last_seen_timestamp': time.time()
                }
            else:
                # This is a single, complete document.
                actual_doc_id = llm_response.id
                print(f"Processor: Page {actual_doc_id} is a complete single-page document. Saving.")
                save_output(llm_response, self.settings)
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

    def check_open_document_timeouts(self):
        """Checks for and flushes timed-out open documents."""
        now = time.time()
        timed_out_ids = []
        for doc_id, data in self.open_documents.items():
            if now - data['last_seen_timestamp'] > self.document_timeout_s:
                timed_out_ids.append(doc_id)
        
        for doc_id in timed_out_ids:
            print(f"Processor: Document {doc_id} timed out. Saving and closing.")
            data_to_save = self.open_documents[doc_id]['letter_data']
            # Mark as complete because it timed out, or LLM should have indicated if it's truly incomplete.
            data_to_save.is_information_complete = True # Override, as we are force-closing.
            save_output(data_to_save, self.settings)
            del self.open_documents[doc_id]
            print(f"Successfully processed and closed timed-out document: {doc_id}")

    def flush_open_documents(self):
        """Saves all currently open documents."""
        print(f"Processor: Flushing all {len(self.open_documents)} open documents...")
        if not self.open_documents:
            print("Processor: No open documents to flush.")
            return
            
        for doc_id in list(self.open_documents.keys()): # list() for safe iteration while modifying
            print(f"Processor: Flushing document {doc_id}.")
            data_to_save = self.open_documents[doc_id]['letter_data']
            data_to_save.is_information_complete = True # Mark as complete on flush
            save_output(data_to_save, self.settings)
            del self.open_documents[doc_id]
            print(f"Successfully flushed document: {doc_id}")
        print("Processor: All open documents flushed.")

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

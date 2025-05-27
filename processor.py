import traceback
from datetime import datetime
from queue import Queue # Queue is still used for communication

from ocr import ocr_image, ocr_pdf
from qr import scan_qr
from llm import classify_document
from output import save_output

class Processor:
    def __init__(self, settings, queue: Queue):
        self.settings = settings
        self.queue = queue # The queue is now polled by the main loop
        self.doc_seq = 0
        # self.lock = threading.Lock() # Lock for doc_seq might not be needed if all calls are sequential
                                     # Keeping it for now as it's low impact.
                                     # If main loop ensures sequential access, this can be removed.

    def get_new_doc_id(self) -> str:
        """Generate a new document ID: YYYYMMDD-XXXX sequence."""
        # with self.lock: # Assuming sequential calls from main loop
        self.doc_seq += 1
        return f"{datetime.now().strftime('%Y%m%d')}-{self.doc_seq:04d}"

    def process_document_pages(self, pages):
        """
        Processes a list of pages (a single document).
        This method was previously process_pages, renamed for clarity.
        """
        if not pages:
            print("Processor: Received empty list of pages, skipping.")
            return

        print(f"Processor: Starting processing for document with {len(pages)} page(s): {pages}")
        try:
            text_all = ""
            qr_payloads = []
            for page_path in pages: # Assuming 'pages' is a list of Path objects
                if page_path.suffix.lower() == '.pdf':
                    print(f"Processor: OCRing PDF page: {page_path}")
                    text, _ = ocr_pdf(page_path)
                    text_all += text + "\n"
                    # Optionally handle QR scanning inside PDFs if needed
                    # For simplicity, QR scanning is currently only for images.
                    # If PDFs can contain QR codes that need scanning, PyMuPDF can extract images
                    # from PDFs, which could then be passed to scan_qr.
                else:
                    print(f"Processor: OCRing image page: {page_path}")
                    text, _ = ocr_image(page_path)
                    text_all += text + "\n"
                    print(f"Processor: Scanning QR codes for image page: {page_path}")
                    qr_payloads.extend(scan_qr(page_path))
            
            if not text_all.strip() and not qr_payloads:
                print(f"Processor: No text or QR codes found for pages {pages}. Skipping LLM classification.")
                # Optionally create an empty output or a specific "empty" classification
                return

            doc_id = self.get_new_doc_id()
            print(f"Processor: Classifying document {doc_id} with LLM.")
            letter = classify_document(text_all, qr_payloads, doc_id, self.settings)
            print(f"Processor: Saving output for document {doc_id}.")
            save_output(letter, self.settings)
            print(f"Successfully processed document: {doc_id}")
        except Exception:
            doc_id_str = locals().get('doc_id', 'unknown_error_doc')
            error_filename = f"{doc_id_str}_{datetime.now().strftime('%Y%m%d%H%M%S')}.error"
            error_path = self.settings.output_dir / error_filename
            print(f"Processor: Error processing document. Saving error to {error_path}")
            with open(error_path, 'w') as ef:
                ef.write(f"Error processing pages: {pages}\n")
                ef.write(traceback.format_exc())

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

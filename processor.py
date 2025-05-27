import threading
import traceback
from datetime import datetime
from queue import Queue

from ocr import ocr_image, ocr_pdf
from qr import scan_qr
from llm import classify_document
from output import save_output

class Processor:
    def __init__(self, settings, queue: Queue):
        self.settings = settings
        self.queue = queue
        self.doc_seq = 0
        self.lock = threading.Lock()
        self.semaphore = threading.Semaphore(settings.max_inflight)

    def get_new_doc_id(self) -> str:
        """Generate a new document ID: YYYYMMDD-XXXX sequence."""
        with self.lock:
            self.doc_seq += 1
            return f"{datetime.now().strftime('%Y%m%d')}-{self.doc_seq:04d}"

    def process_pages(self, pages):
        try:
            text_all = ""
            qr_payloads = []
            for page in pages:
                if page.suffix.lower() == '.pdf':
                    text, _ = ocr_pdf(page)
                    text_all += text + "\n"
                    # Optionally handle QR scanning inside PDFs if needed
                else:
                    text, _ = ocr_image(page)
                    text_all += text + "\n"
                    qr_payloads.extend(scan_qr(page))
            doc_id = self.get_new_doc_id()
            letter = classify_document(text_all, qr_payloads, doc_id, self.settings)
            save_output(letter, self.settings)
        except Exception:
            # On error, write a .error file with full traceback
            doc_id = locals().get('doc_id', 'unknown')
            error_path = self.settings.output_dir / f"{doc_id}.error"
            with open(error_path, 'w') as ef:
                ef.write(traceback.format_exc())

    def _worker(self, pages):
        try:
            self.process_pages(pages)
        finally:
            self.semaphore.release()

    def run(self):
        """
        Continuously consume page lists from the queue and process them.
        Use a semaphore to limit concurrency.
        """
        while True:
            pages = self.queue.get()
            if pages is None:  # Sentinel to stop processing
                break
            self.semaphore.acquire()
            thread = threading.Thread(target=self._worker, args=(pages,), daemon=True)
            thread.start()

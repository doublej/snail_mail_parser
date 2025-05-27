import time
import re
# import threading # Removed
from pathlib import Path
from queue import Queue
# from watchdog.observers.polling import PollingObserver as Observer # Removed
# from watchdog.events import FileSystemEventHandler # Removed
import os # For manual scanning

class FolderWatcher: # No longer inherits from FileSystemEventHandler
    allowed_exts = {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.pdf'}

    def __init__(self, scan_dir: Path, queue: Queue, timeout: int):
        self.scan_dir = scan_dir
        self.queue = queue
        self.timeout = timeout
        self.sessions = {}  # prefix -> {'pages': [(num, Path)], 'last_seen': timestamp}
        self.pattern = re.compile(r"(.+)_([0-9]+)$")
        # self._lock = threading.Lock() # Removed, operations are sequential
        # self._running = False # Removed, no separate threads to manage state for
        self.known_files = set()

        # self.known_files is initialized as an empty set.
        # Files existing in scan_dir upon startup will be processed on the first scan.
        print(f"Watcher: Initializing. Existing files in {self.scan_dir} will be processed.")
        try:
            if not (self.scan_dir.exists() and self.scan_dir.is_dir()):
                print(f"Warning: Scan directory {self.scan_dir} does not exist or is not a directory.")
                # Optionally create it: self.scan_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            # This exception would likely be from self.scan_dir.exists() or .is_dir() if path is invalid
            print(f"Error checking scan directory {self.scan_dir}: {e}")
        print(f"Watcher: Initialized. known_files set is empty. All files in {self.scan_dir} will be scanned.")


    def start(self):
        # No observer to start, this method is for any initial setup if needed
        # or can be removed if __init__ handles all setup.
        print(f"Watcher: Manual scanning mode configured for {self.scan_dir}.")
        pass

    def stop(self):
        # No observer to stop
        print("Watcher: Stopped.")
        pass

    def _handle_new_file(self, path: Path):
        """Processes a single newly detected file."""
        print(f"Watcher: Handling new file: {path}")
        ext = path.suffix.lower()
        # Extension check is technically done by scan_for_new_files, but good for safety
        if ext not in self.allowed_exts: # Should not happen if called from scan_for_new_files
            return

        if ext == '.pdf':
            print(f"Watcher: PDF detected: {path}. Attempting to enqueue.")
            self._flush_pages([path]) # PDF is standalone - enqueue immediately
            return

        # Handle image page for aggregation
        stem = path.stem
        m = self.pattern.match(stem)
        if m:
            prefix = m.group(1)
            page_num = int(m.group(2))
        else:
            prefix = stem
            page_num = 0
        
        # Lock removed as calls are sequential
        if prefix not in self.sessions:
            self.sessions[prefix] = {'pages': [], 'last_seen': time.time()}
        session = self.sessions[prefix]
        session['pages'].append((page_num, path))
        session['last_seen'] = time.time()
        print(f"Watcher: Added {path} to session {prefix}. Pages: {len(session['pages'])}")

    def scan_for_new_files(self):
        """Scans the directory for new files and processes them."""
        # print(f"Watcher: Scanning {self.scan_dir} for new files...") # Can be noisy
        try:
            if not self.scan_dir.exists() or not self.scan_dir.is_dir():
                # print(f"Watcher: Scan directory {self.scan_dir} not found or not a directory. Skipping scan.")
                return

            current_files_on_disk = {self.scan_dir / item_name for item_name in os.listdir(self.scan_dir) if (self.scan_dir / item_name).is_file()}
        except Exception as e:
            print(f"Error listing files in {self.scan_dir}: {e}")
            return

        new_files = current_files_on_disk - self.known_files
        
        if new_files:
            # print(f"Watcher: Found {len(new_files)} new file(s).")
            for path in sorted(list(new_files)): # Sort for deterministic processing order
                if path.suffix.lower() in self.allowed_exts:
                    self._handle_new_file(path)
                # Add all new files to known_files, whether processed or not, to avoid re-evaluating
                self.known_files.add(path)
        # else:
            # print(f"Watcher: No new files found.") # Can be noisy

        # Optional: Clean up known_files if files are deleted from disk
        # self.known_files = self.known_files.intersection(current_files_on_disk)


    def check_session_timeouts(self):
        """
        Checks for and flushes timed-out image sessions.
        This replaces the _session_checker thread.
        """
        # print("Watcher: Checking for session timeouts...") # Can be noisy
        now = time.time()
        to_flush = []
        # Lock removed as calls are sequential
        for prefix, sess in list(self.sessions.items()): # list() for safe iteration if modifying
            if now - sess['last_seen'] >= self.timeout:
                print(f"Watcher: Session {prefix} timed out.")
                to_flush.append(prefix)
        
        if to_flush:
            for prefix in to_flush:
                sess = self.sessions.pop(prefix, None)
                if sess:
                    pages = [p for _, p in sorted(sess['pages'], key=lambda x: x[0])]
                    self._flush_pages(pages)

    def _flush_pages(self, pages):
        if pages:
            print(f"Watcher: Adding to queue: {pages}")
            self.queue.put(pages)
        # else: # This log might be too verbose if called often with no pages
            # print(f"Watcher: _flush_pages called with no pages. Nothing to queue.")

    def flush_all(self):
        """Manually flush all sessions (used by --flush flag)."""
        print("Watcher: Flushing all pending sessions...")
        # Lock removed as calls are sequential (assuming --flush is handled before main loop or carefully)
        for prefix, sess in list(self.sessions.items()):
            pages = [p for _, p in sorted(sess['pages'], key=lambda x: x[0])]
            self.queue.put(pages)
            self.sessions.pop(prefix, None)
        print("Watcher: All sessions flushed.")

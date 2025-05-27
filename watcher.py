import time
import re
import threading
from pathlib import Path
from queue import Queue
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class FolderWatcher(FileSystemEventHandler):
    allowed_exts = {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.pdf'}

    def __init__(self, scan_dir: Path, queue: Queue, timeout: int):
        self.scan_dir = scan_dir
        self.queue = queue
        self.timeout = timeout
        self.sessions = {}  # prefix -> {'pages': [(num, Path)], 'last_seen': timestamp}
        self.observer = Observer()
        self.pattern = re.compile(r"(.+)_([0-9]+)$")
        self._lock = threading.Lock()
        self._running = False

    def start(self):
        self.observer.schedule(self, str(self.scan_dir), recursive=False)
        self._running = True
        self.observer.start()
        # Start session timeout checker thread
        threading.Thread(target=self._session_checker, daemon=True).start()

    def stop(self):
        self._running = False
        self.observer.stop()
        self.observer.join()

    def on_created(self, event):
        self._handle_event(event)

    def on_moved(self, event):
        self._handle_event(event)

    def _handle_event(self, event):
        print(f"Watcher: Event received: {event.event_type} for src_path='{getattr(event, 'src_path', None)}', dest_path='{getattr(event, 'dest_path', None)}'")
        if event.is_directory:
            print(f"Watcher: Event for directory, ignoring.")
            return
        # Determine file path for created or moved
        path = Path(event.dest_path) if hasattr(event, 'dest_path') else Path(event.src_path)
        print(f"Watcher: Handling path: {path}")
        ext = path.suffix.lower()
        print(f"Watcher: File extension: {ext}")
        if ext not in self.allowed_exts:
            print(f"Watcher: Extension '{ext}' not in allowed_exts: {self.allowed_exts}. Ignoring.")
            return
        if ext == '.pdf':
            print(f"Watcher: PDF detected: {path}. Attempting to enqueue.")
            # PDF is standalone - enqueue immediately
            self._flush_pages([path])
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
        with self._lock:
            if prefix not in self.sessions:
                self.sessions[prefix] = {'pages': [], 'last_seen': time.time()}
            session = self.sessions[prefix]
            session['pages'].append((page_num, path))
            session['last_seen'] = time.time()

    def _session_checker(self):
        # Periodically flush sessions that have timed out
        while self._running:
            now = time.time()
            to_flush = []
            with self._lock:
                for prefix, sess in list(self.sessions.items()):
                    if now - sess['last_seen'] >= self.timeout:
                        to_flush.append(prefix)
                for prefix in to_flush:
                    sess = self.sessions.pop(prefix, None)
                    if sess:
                        # Sort pages by the trailing number and enqueue
                        pages = [p for _, p in sorted(sess['pages'], key=lambda x: x[0])]
                        self._flush_pages(pages)
            time.sleep(1)

    def _flush_pages(self, pages):
        if pages:
            print(f"Watcher: Adding to queue: {pages}")
            self.queue.put(pages)
        else:
            print(f"Watcher: _flush_pages called with no pages. Nothing to queue.")

    def flush_all(self):
        """Manually flush all sessions (used by --flush flag)."""
        with self._lock:
            for prefix, sess in list(self.sessions.items()):
                pages = [p for _, p in sorted(sess['pages'], key=lambda x: x[0])]
                self.queue.put(pages)
                self.sessions.pop(prefix, None)

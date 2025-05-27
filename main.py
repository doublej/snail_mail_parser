import argparse
import threading
import time
from queue import Queue

from settings import Settings
from watcher import FolderWatcher
from processor import Processor

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--flush', action='store_true', help='Flush all open sessions immediately')
    args = parser.parse_args()

    settings = Settings()

    # Create a queue for document sessions
    q = Queue()

    # Start folder watcher
    watcher = FolderWatcher(settings.scan_dir, q, settings.session_timeout_s)
    watcher.start()

    # Start processor in a separate thread
    processor = Processor(settings, q)
    proc_thread = threading.Thread(target=processor.run, daemon=True)
    proc_thread.start()

    # If flush flag is set, flush existing sessions
    if args.flush:
        watcher.flush_all()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
        watcher.stop()
        # Signal processor to exit by sending None
        q.put(None)
        proc_thread.join()

if __name__ == '__main__':
    main()

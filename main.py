import argparse
import logging
# import threading # Removed
import time
from queue import Queue

from settings import Settings
from watcher import FolderWatcher
from processor import Processor

def main():
    # Configure logging
    logging.basicConfig(level=logging.INFO, # Changed to INFO for less verbosity
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    parser = argparse.ArgumentParser()
    parser.add_argument('--flush', action='store_true', help='Flush all open sessions immediately')
    args = parser.parse_args()

    settings = Settings()

    # Create a queue for document sessions
    q = Queue()

    # Initialize FolderWatcher and Processor
    watcher = FolderWatcher(settings.scan_dir, q)
    processor = Processor(settings, q)

    # watcher.start() # Call start if it performs necessary setup, otherwise it can be removed
                      # In the new watcher, start() is mostly a placeholder.

    # If flush flag is set, call the processor's flush_open_documents method.
    if args.flush:
        print("Processor: --flush argument provided. Flushing all open documents...")
        processor.flush_open_documents() 
        print("Processor: Flushing of open documents by --flush argument is complete.")

    print(f"Application started successfully. Monitoring {settings.scan_dir} for new files.")
    print(f"Scan interval: {settings.scan_interval_s}s.")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            # 1. Scan for new files (watcher adds them to internal sessions)
            watcher.scan_for_new_files()

            # 2. Check for and flush timed-out image sessions from watcher to the queue
            watcher.check_session_timeouts()
            
            # 3. Process one item from the queue if available
            processed_item = processor.process_next_item_from_queue()

            # Sleep a bit to avoid busy-waiting if there's nothing to do.
            # If an item was processed, we might want a shorter or no sleep
            # to quickly process subsequent items. If not, sleep for the scan_interval.
            if not processed_item and q.empty(): # Only sleep full interval if no work was done AND queue is empty
                time.sleep(settings.scan_interval_s)
            else:
                # If work was done or queue still has items, sleep very briefly to yield
                # or allow quick succession of processing.
                time.sleep(0.1) 

    except KeyboardInterrupt:
        print("\nShutting down...")
        watcher.stop() # Call stop if it performs necessary cleanup
        
        # Process any remaining items in the queue before exiting
        print("Processing remaining items in queue...")
        while not q.empty():
            processor.process_next_item_from_queue()
        print("All items processed. Exiting.")

if __name__ == '__main__':
    main()

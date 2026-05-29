from rich.live import Live
#from rich.table import Table
import time 

#from storage import store_event
from watcher import LogHandler
from display import show_groups
from watcher import Observer


# 1. start the file watcher
#    Observer is already a background thread — calling .start() is enough
#    returns the observer so the caller can stop it cleanly on shutdown
def start_watcher():
    handler = LogHandler()
    observer = Observer()

    # watch the current directory, non-recursively
    observer.schedule(handler, path=".", recursive=False)

    # starts the watchdog thread — runs in background while dashboard renders
    observer.start()

    return observer


# 2. run the live dashboard in the main thread
def run_dashboard():
    # start the file watcher before entering the render loop
    start_watcher()
    with Live(refresh_per_second=1) as live:
        while True:
            table = show_groups()
            #updates the new table dashbaord to the 
            live.update(table)          
            time.sleep(1)

if __name__ == "__main__":
    run_dashboard()
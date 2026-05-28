import threading 

from rich.live import Live
from rich.table import Table
import time 

from storage import store_event
from watcher import LogHandler
from display import show_groups
from watcher import Observer


# 1. start the watcher in a background thread
#    so it keeps feeding the DB while we render
def start_watcher():

    handler = LogHandler()
    observer = Observer()
    observer.schedule(handler,path = ".",recursive= False)

#wrap this in the thread so it can work while the dashboard 
    thread = threading.Thread(target = observer.start,deamon = True)
    thread.start()


# 2. run the live dashboard in the main thread
def run_dashboard():
    # TODO: call start_watcher() here

     with Live(refresh_per_second=1) as live:
        while True:
        #table = show_groups()       # re-query DB
       # live.update(table)          # push new table to terminal
        #time.sleep(1)

#if __name__ == "__main__":
    # run_dashboard()
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .storage import store_event


class LogHandler(FileSystemEventHandler):
    def __init__(self):
        # required since we are inheriting from a class already in python
        super().__init__()

        # tracks how far into the file we have already read
        # so on_modified only processes new lines, not the whole file again
        self.last_position = 0

    def on_modified(self, event):
        if event.src_path.endswith("sample.jsonl"):
            with open("sample.jsonl") as file:
                # jump to where we last stopped reading
                file.seek(self.last_position)

                for line in file:
                    line = line.strip()
                    if line:
                        event_data = json.loads(line)
                        store_event(event_data)

                # save our position so next modification picks up from here
                self.last_position = file.tell()


if __name__ == "__main__":
    # set up the observer to watch the current directory
    handler = LogHandler()
    observer = Observer()
    observer.schedule(handler, path=".", recursive=False)
    observer.start()

    print("Watching sample.jsonl for new events... (Ctrl+C to stop)")

    try:
        while True:
            pass
    except KeyboardInterrupt:
        observer.stop()

    observer.join()

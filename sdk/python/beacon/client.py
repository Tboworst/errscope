import sys
import traceback
import datetime
import threading
import requests

# module-level config — set by init(), read by _send()
_endpoint = None
_service = None
_environment = None
_api_key = None


def init(endpoint="http://localhost:7000/ingest", service="app", environment="production", api_key=None):
    global _endpoint, _service, _environment, _api_key
    _endpoint = endpoint
    _service = service
    _environment = environment
    _api_key = api_key

    # install the global hook — from this point on every unhandled
    # exception in the user's app is automatically captured
    sys.excepthook = _handle_exception


def _handle_exception(exc_type, exc_value, exc_tb):
    # app is already crashing so send synchronously — no point in a background thread
    # that would be killed before the request finishes
    payload = _build_payload(exc_value, exc_tb)
    if payload:
        _post(payload)

    # still call the original hook so the error prints to the terminal
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def capture(exc):
    # manual capture for exceptions caught inside a try/except
    # send in a background thread so it never blocks the caller
    payload = _build_payload(exc, exc.__traceback__)
    if payload:
        thread = threading.Thread(target=_post, args=(payload,), daemon=True)
        thread.start()


def _build_payload(exc, tb):
    if not _endpoint:
        return None
    return {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "stack_trace": [
            {"function": frame.name, "file": frame.filename, "line": frame.lineno}
            for frame in traceback.extract_tb(tb)
        ],
        "service": _service,
        "environment": _environment,
    }


def _post(payload):
    try:
        headers = {"X-Api-Key": _api_key} if _api_key else {}
        requests.post(_endpoint, json=payload, headers=headers, timeout=5)
    except Exception:
        # if errscope is down the user's app must keep running
        pass

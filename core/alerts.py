import os
import requests

# load the webhook URL from the environment
URL = os.environ.get("SLACK_WEBHOOK_URL")


def check_and_alert(fingerprint, count):
    threshold = 50

    if count >= threshold:
        # skip silently if no webhook is configured
        if not URL:
            return
        message = f"[errscope] {fingerprint} has fired {count} times, reaching the threshold check on it"
        requests.post(URL, json={"text": message})
        
    
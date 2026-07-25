import os
from flask import Flask, request, jsonify
from .storage import store_event
from .llm_storage import store_llm_call
from .deploy_storage import store_deploy


app = Flask(__name__)

# if BEACON_API_KEY is set, all ingest requests must include it
# if not set, the server accepts all requests (local dev mode)
API_KEY = os.environ.get("BEACON_API_KEY")


@app.route('/ingest', methods=['POST'])
def handle_ingest():
    # check API key when one is configured
    if API_KEY and request.headers.get("X-Api-Key") != API_KEY:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json()

    # reject requests with no JSON body
    if not data:
        return jsonify({"error": "no JSON body"}), 400

    try:
        store_event(data)
        return jsonify({"status": "ok"}), 200
    except KeyError as e:
        # a required field was missing from the payload
        return jsonify({"error": f"missing field: {e}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/ingest/llm', methods=['POST'])
def handle_ingest_llm():
    if API_KEY and request.headers.get("X-Api-Key") != API_KEY:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json()

    if not data:
        return jsonify({"error": "no JSON body"}), 400

    try:
        store_llm_call(data)
        return jsonify({"status": "ok"}), 200
    except KeyError as e:
        return jsonify({"error": f"missing field: {e}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/deploy', methods=['POST'])
def handle_deploy():
    if API_KEY and request.headers.get("X-Api-Key") != API_KEY:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json()

    if not data:
        return jsonify({"error": "no JSON body"}), 400

    try:
        store_deploy(data)
        return jsonify({"status": "ok"}), 200
    except KeyError as e:
        return jsonify({"error": f"missing field: {e}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(port=7000)

from flask import Flask, request, jsonify
from storage import store_event


app = Flask(__name__)


@app.route('/ingest', methods=['POST'])
def handle_ingest():
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


if __name__ == "__main__":
    app.run(port=7000)

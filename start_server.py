from dotenv import load_dotenv
load_dotenv()

from core.server import app

if __name__ == "__main__":
    app.run(port=7000)

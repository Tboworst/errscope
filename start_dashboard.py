from dotenv import load_dotenv
load_dotenv()

from dashboard.dashboard import BeaconApp

if __name__ == "__main__":
    BeaconApp().run()

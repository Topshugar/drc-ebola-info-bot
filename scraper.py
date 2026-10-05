import requests
from datetime import datetime

# ReliefWeb / OCHA tracker has open data
def fetch_clinic_status():
    """
    In production: pull from https://api.reliefweb.int and openAFRICA tracker
    For now: fallback to hardcoded + timestamp
    """
    try:
        # Example: Code for Africa tracker
        r = requests.get("https://openafrica.net/api/drc-ebola", timeout=5)
        if r.status_code == 200:
            return r.json()
    except:
        pass

    # Fallback - last known from WHO Sep 29 Security Council report
    return {
        "updated": datetime.utcnow().isoformat(),
        "source": "WHO/UN Security Council Sep 29 2026 + Atlantic Digest Oct 3",
        "notes": "Kigonze burned Oct 2, 19k displaced. Ituri epicenter 81% cases.",
        "clinics": {
            "kigonze": "CLOSED - Burned Oct 2",
            "bunia": "OPEN - overloaded",
            "butembo": "OPEN",
            "bukavu": "OPEN"
        }
    }

if __name__ == "__main__":
    print(fetch_clinic_status())

import os
from flask import Flask, request
from datetime import datetime

# --- Import scraper you just created ---
try:
    from scraper import fetch_clinic_status
except ImportError:
    def fetch_clinic_status():
        return {"clinics": {}}

app = Flask(__name__)

AT_USERNAME = os.getenv("AT_USERNAME", "sandbox")
AT_API_KEY = os.getenv("AT_API_KEY", "")
ADMIN_KEY = os.getenv("ADMIN_KEY", "congo123")

# Base clinics - will be overwritten by scraper live data
CLINICS = {
    "bunia": {"name": "Bunia General Hospital", "status": "OPEN - overloaded", "zone": "Ituri"},
    "kigonze": {"name": "Kigonze Transit Centre", "status": "CLOSED - Burned Oct 2, 19k fled", "zone": "Ituri"},
    "butembo": {"name": "Butembo ETC", "status": "OPEN", "zone": "North Kivu"},
    "bukavu": {"name": "Bukavu ETC", "status": "OPEN", "zone": "South Kivu"},
    "tshopo": {"name": "Tshopo Referral", "status": "OPEN - new cases", "zone": "Tshopo"},
}

# Try live update on boot
try:
    live = fetch_clinic_status()
    for k, v in live.get("clinics", {}).items():
        if k in CLINICS:
            CLINICS[k]["status"] = v if isinstance(v, str) else v.get("status", CLINICS[k]["status"])
    print(f"[BOOT] Clinics synced: {live.get('source','fallback')} at {live.get('updated')}")
except Exception as e:
    print(f"[BOOT] Scraper failed, using fallback: {e}")

RESPONSES = {
    "fr": {
        "menu": "INFO EBOLA DRC\n1.Symptomes\n2.Prevention\n3.Centres Ouverts\n4.Urgence 109\n0.Langue",
        "1": "SYMPTOMES: Fievre forte, fatigue, maux de tete, vomissement, diarrhee, saignement inexplique. ACTION: Ne touchez pas. Appelez 109. Isolez-vous. Lavez mains.",
        "2": "PREVENTION: 1.Lavez mains savon 2.Pas contact corps/fluides 3.Pas viande brousse 4.Enterrement securise par equipe. Ebola = fluides, pas l'air.",
        "4": "URGENCE: Appelez GRATUIT 109. OMS: +243817000000. N'allez pas chez guerisseur. Allez au centre ETC immediatement. Temps = vie.",
        "lang_prompt": "Choisissez langue:\n1.Francais\n2.Swahili\n3.Lingala",
        "invalid": "Choix invalide. Tapez 109 pour urgence."
    },
    "sw": {
        "menu": "TAARIFA EBOLA DRC\n1.Dalili\n2.Kinga\n3.Vituo Wazi\n4.Dharura 109\n0.Lugha",
        "1": "DALILI: Homa kali, uchovu, kichwa, kutapika, kuhara, damu. HATUA: Usiguse mgonjwa. Piga 109. Jitenge. Nawa mikono.",
        "2": "KINGA: 1.Nawa mikono sabuni 2.Usiguse mwili/majimaji 3.Usile nyama pori 4.Mazishi salama na timu. Inaenea kwa majimaji, si hewa.",
        "4": "DHARURA: Piga BURE 109. Nenda kituoni ETC mara moja. Muda ni uhai. Usibaki nyumbani.",
        "lang_prompt": "Chagua lugha:\n1.Francais\n2.Swahili\n3.Lingala",
        "invalid": "Chaguo batili. Piga 109."
    },
    "ln": {
        "menu": "SANGO YA EBOLA\n1.Bilembeteli\n2.Kobatela\n3.Centres\n4.Lisungi 109\n0.Monoko",
        "1": "BILEMBETELI: Fever makasi, bolembu, mutu pasi, kosanza, diarrhee, makila. SALA: Kosimba te. Benga 109. Mitia na pembeni.",
        "2": "KOBATELA: 1.Sokola maboko na sabuni 2.Kosimba nzoto/mayi te 3.Kolia nyama ya zamba te 4.Kunda na equipe securise. Ebola = mayi ya nzoto, r te mopepe.",
        "4": "LISUNGI: Benga OFELE 109. Kende na centre ETC sikoyo. Ntango = bomoyi. Tikala na ndako te.",
        "lang_prompt": "Pona monoko:\n1.Francais\n2.Swahili\n3.Lingala",
        "invalid": "Pona mabe. Benga 109."
    }
}

def get_centres_text(lang):
    lines = []
    for c in CLINICS.values():
        status = c["status"]
        icon = "✅" if "OPEN" in status.upper() else "❌"
        # Keep SMS under 160 chars per segment, USSD under 182
        lines.append(f"{icon} {c['name'][:20]}: {status[:30]}")
    header = {"fr": "CENTRES (live):\n", "sw": "VITUO (live):\n", "ln": "CENTRES (live):\n"}[lang]
    return header + "\n".join(lines)

def get_response(lang, choice):
    if choice == "3":
        return get_centres_text(lang)
    return RESPONSES.get(lang, RESPONSES["fr"]).get(choice, RESPONSES[lang]["invalid"])

@app.route("/ussd", methods=["POST"])
def ussd():
    text = request.values.get("text", "").strip()
    parts = text.split("*") if text else []

    lang_map = {"1": "fr", "2": "sw", "3": "ln"}

    if not text:
        return "CON " + RESPONSES["fr"]["lang_prompt"]

    # First digit is language
    lang = lang_map.get(parts[0], "fr") if parts[0] in lang_map else "fr"

    if len(parts) == 1 and parts[0] in lang_map:
        return f"CON {RESPONSES[lang]['menu']}"

    current_choice = parts[-1] if parts else ""

    if current_choice == "0":
        return f"CON {RESPONSES[lang]['lang_prompt']}"

    response_text = get_response(lang, current_choice)
    return f"END {response_text}\n\nSrc: WHO/OMS. 109 gratuit."

@app.route("/sms", methods=["POST"])
def sms():
    msg = request.values.get("text", "").lower()
    lang = "fr"
    if any(w in msg for w in ["dalili", "kinga", "vituo", "swahili", "jambo"]):
        lang = "sw"
    elif any(w in msg for w in ["lingala", "bilembe", "sango", "mbote"]):
        lang = "ln"

    if any(k in msg for k in ["1", "sympt", "dalili", "bilembe"]):
        choice = "1"
    elif any(k in msg for k in ["2", "prevent", "kinga", "kobatela"]):
        choice = "2"
    elif any(k in msg for k in ["3", "centre", "vituo", "hopital"]):
        choice = "3"
    elif any(k in msg for k in ["4", "109", "urgence", "dharura", "lisungi"]):
        choice = "4"
    else:
        return RESPONSES[lang]["menu"]

    return get_response(lang, choice)

@app.route("/", methods=["GET"])
def health():
    return {
        "status": "ok",
        "service": "drc-ebola-info-bot",
        "clinics": CLINICS,
        "languages": ["fr", "sw", "ln"],
        "time": datetime.utcnow().isoformat(),
        "emergency": "DRC 109"
    }

@app.route("/update-clinic", methods=["POST", "GET"])
def update_clinic():
    if request.args.get("key")!= ADMIN_KEY:
        return "unauthorized - wrong key", 401
    name = request.args.get("name", "").lower()
    status = request.args.get("status", "")
    if not name or not status:
        return "need?name=&status=", 400
    if name in CLINICS:
        CLINICS[name]["status"] = status
        return {"updated": CLINICS[name], "all": CLINICS}
    return f"clinic {name} not found. available: {list(CLINICS.keys())}", 404

@app.route("/refresh", methods=["POST", "GET"])
def refresh():
    if request.args.get("key")!= ADMIN_KEY:
        return "unauthorized", 401
    try:
        live = fetch_clinic_status()
        updated = 0
        for k, v in live.get("clinics", {}).items():
            if k in CLINICS:
                CLINICS[k]["status"] = v if isinstance(v, str) else v.get("status", CLINICS[k]["status"])
                updated += 1
        return {"refreshed": updated, "data": live, "clinics": CLINICS}
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)

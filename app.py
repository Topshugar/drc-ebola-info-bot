import os
from flask import Flask, request
import requests
from datetime import datetime

app = Flask(__name__)

# --- CONFIG ---
# Set these in Render env vars
AT_USERNAME = os.getenv("AT_USERNAME", "sandbox")
AT_API_KEY = os.getenv("AT_API_KEY", "")

# Dynamic clinic status - update via OCHA/WHO daily
# In v2 we scrape this automatically
CLINICS = {
    "bunia": {"name": "Bunia General Hospital", "status": "OPEN", "zone": "Ituri"},
    "kigonze": {"name": "Kigonze Transit Centre", "status": "CLOSED - Burned Oct 2", "zone": "Ituri"},
    "butembo": {"name": "Butembo ETC", "status": "OPEN", "zone": "North Kivu"},
    "bukavu": {"name": "Bukavu ETC", "status": "OPEN", "zone": "South Kivu"},
}

RESPONSES = {
    "fr": {
        "menu": "INFO EBOLA DRC\n1.Symptomes\n2.Prevention\n3.Centres Ouverts\n4.Urgence 109\n0.Changer langue",
        "1": "SYMPTOMES: Fievre forte, fatigue, maux de tete, vomissement, diarrhee, saignement. ACTION: Ne touchez pas le malade. Appelez 109. Isolez-vous.",
        "2": "PREVENTION: 1.Lavez mains savon 2.Pas contact corps 3.Pas viande brousse 4.Enterrement securise. Ebola = fluides, pas l'air.",
        "3": "", # generated dynamic
        "4": "URGENCE: Appelez GRATUIT 109. OMS Bunia: +243817000000. Ne restez pas a la maison. Allez au centre ETC. Temps = vie.",
        "lang_prompt": "Choisissez langue:\n1.Francais\n2.Swahili\n3.Lingala"
    },
    "sw": {
        "menu": "TAARIFA EBOLA DRC\n1.Dalili\n2.Kinga\n3.Vituo Wazi\n4.Dharura 109\n0.Badilisha lugha",
        "1": "DALILI: Homa kali, uchovu, kichwa, kutapika, kuhara, damu. USIGUSE mgonjwa. Piga 109. Jitenge.",
        "2": "KINGA: 1.Nawa mikono 2.Usiguse mwili 3.Usile nyama pori 4.Mazishi salama. Inaenea kwa majimaji.",
        "3": "",
        "4": "DHARURA: Piga BURE 109. Nenda kituoni ETC mara moja. Muda ni uhai.",
        "lang_prompt": "Chagua lugha:\n1.Francais\n2.Swahili\n3.Lingala"
    },
    "ln": {
        "menu": "SANGO YA EBOLA\n1.Bilembeteli\n2.Kobatela\n3.Centres\n4.Lisungi 109\n0.Bongola monoko",
        "1": "BILEMBETELI: Fever makasi, bolembu, mutu pasi, kosanza, diarrhee, makila. KOSIMBA te. Benga 109.",
        "2": "KOBATELA: 1.Sokola maboko 2.Kosimba nzoto te 3.Kolia nyama ya zamba te. Ebola = mayi ya nzoto.",
        "3": "",
        "4": "LISUNGI: Benga OFELE 109. Kende na centre ETC. Ntango = bomoyi.",
        "lang_prompt": "Pona monoko:\n1.Francais\n2.Swahili\n3.Lingala"
    }
}

def get_centres_text(lang):
    lines = []
    for c in CLINICS.values():
        icon = "✅" if "OPEN" in c["status"] else "❌"
        lines.append(f"{icon} {c['name']}: {c['status']}")
    header = {"fr": "CENTRES:\n", "sw": "VITUO:\n", "ln": "CENTRES:\n"}[lang]
    return header + "\n".join(lines)

def get_response(lang, choice):
    if choice == "3":
        return get_centres_text(lang)
    return RESPONSES.get(lang, RESPONSES["fr"]).get(choice, "Choix invalide. Composez 109.")

@app.route("/ussd", methods=["POST"])
def ussd():
    text = request.values.get("text", "").strip()
    # text is like "1*2" or ""
    parts = text.split("*") if text else []

    # Session flow: first input is language if empty, we show lang menu
    # Simplified: if no text, show lang menu
    if not text:
        return "CON " + RESPONSES["fr"]["lang_prompt"]

    # If first part is language selection
    lang_map = {"1": "fr", "2": "sw", "3": "ln"}

    lang = "fr"
    current_choice = ""

    if parts[0] in lang_map:
        lang = lang_map[parts[0]]
        if len(parts) == 1:
            # just selected language, show main menu
            return f"CON {RESPONSES[lang]['menu']}"
        current_choice = parts[-1]
    else:
        # user directly typed menu number without lang step (fallback to fr)
        current_choice = parts[-1] if parts else ""
        lang = "fr"

    # Handle language change
    if current_choice == "0":
        return f"CON {RESPONSES[lang]['lang_prompt']}"

    response_text = get_response(lang, current_choice)
    return f"END {response_text}\n\nSource: WHO/OMS 2026. DRC 109."

@app.route("/sms", methods=["POST"])
def sms():
    msg = request.values.get("text", "").lower()
    lang = "fr"
    if any(w in msg for w in ["dalili", "kinga", "swahili"]):
        lang = "sw"
    if any(w in msg for w in ["lingala", "bilembe", "sango"]):
        lang = "ln"

    if "1" in msg or "sympt" in msg or "dalili" in msg or "bilembe" in msg:
        reply = get_response(lang, "1")
    elif "2" in msg or "prevent" in msg or "kinga" in msg:
        reply = get_response(lang, "2")
    elif "3" in msg or "centre" in msg or "vituo" in msg:
        reply = get_response(lang, "3")
    else:
        reply = RESPONSES[lang]["menu"]

    return reply

@app.route("/", methods=["GET"])
def health():
    return {"status": "ok", "clinics": CLINICS, "time": datetime.utcnow().isoformat()}

@app.route("/update-clinic", methods=["POST"])
def update_clinic():
    # Simple protected endpoint to update clinic status without redeploy
    # Call with?key=YOUR_SECRET&name=kigonze&status=OPEN
    if request.args.get("key")!= os.getenv("ADMIN_KEY", "congo123"):
        return "unauthorized", 401
    name = request.args.get("name")
    status = request.args.get("status")
    if name in CLINICS:
        CLINICS[name]["status"] = status
        return {"updated": CLINICS[name]}
    return "not found", 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

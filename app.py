import base64
from datetime import datetime
import io
import os
import sqlite3
from PIL import Image
import streamlit as st

st.set_page_config(page_title="Autohandel Inventaris", layout="wide")

# --- ULTIEME STYLING: VOLLEDIG GELIJKE BALKEN EN WITTE LETTERS ---
def zet_achtergrond(logo_path="logo.png"):
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            data = f.read()
        encoded = base64.b64encode(data).decode("utf-8")
        
        css = f"""
        <style>
        .stApp {{
            background-image: linear-gradient(rgba(255, 255, 255, 0.4), rgba(255, 255, 255, 0.4)), url("data:image/png;base64,{encoded}");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}
        
        h1, h2, h3, p, span, .streamlit-expanderHeader p, .streamlit-expanderHeader span {{
            color: white !important;
            text-shadow: 
                -1px -1px 0 #000,  
                 1px -1px 0 #000,
                -1px  1px 0 #000,
                 1px  1px 0 #000,
                -2px -2px 2px #000,
                 2px -2px 2px #000,
                -2px  2px 2px #000,
                 2px  2px 2px #000 !important;
        }}
        
        div[data-testid="stWidgetLabel"] p, label {{
            color: white !important;
            text-shadow: -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000 !important;
        }}
        
        div[data-testid="stForm"], .stDialog div[role="dialog"] {{
            background-color: rgba(20, 20, 20, 0.95) !important;
            padding: 25px !important;
            border-radius: 12px !important;
            border: 2px solid rgba(255, 255, 255, 0.2) !important;
        }}
        
        input, select, textarea, div[data-baseweb="input"], div[data-baseweb="select"], div[data-baseweb="input"] input, div[data-testid="stTextInput"] input {{
            background-color: #262730 !important;
            color: white !important;
            -webkit-text-fill-color: white !important;
            text-shadow: none !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
        }}

        .stButton button, .stButton button span, button[data-testid="stBaseButton-primary"] span {{
            text-shadow: none !important;
        }}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)

zet_achtergrond("logo.png")

# --- WACHTWOORDBEVEILIGING ---
if "ingelogd" not in st.session_state:
    st.session_state["ingelogd"] = False

if not st.session_state["ingelogd"]:
    st.title("🔒 Beveiligde Toegang")
    st.write("Voer het wachtwoord in om toegang te krijgen tot de autohandel inventaris.")
    wachtwoord_invoer = st.text_input("Wachtwoord", type="password")
    if st.button("Inloggen", type="primary"):
        if wachtwoord_invoer == "DONGEN123":
            st.session_state["ingelogd"] = True
            st.success("Succesvol ingelogd!")
            st.rerun()
        else:
            st.error("Onjuist wachtwoord, probeer het opnieuw.")
    st.stop()

# --- DATABASE VERBINDING ---
conn = sqlite3.connect("autohandel.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS autos_v3 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kenteken TEXT,
        km_stand INTEGER,
        inkoopprijs REAL,
        verkoopprijs REAL,
        apk_datum TEXT,
        extra_kosten REAL,
        afbeelding TEXT,
        naam TEXT
    )
"""
)
conn.commit()

# HULPFUNCTIE: Zet tekst veilig om naar getal, geeft 0 of 0.0 als het veld leeg is
def naar_getal(tekst_waarde, type_getal=float):
    if not tekst_waarde or str(tekst_waarde).strip() == "" or str(tekst_waarde).strip() == "0.00" or str(tekst_waarde).strip() == "0":
        return 0 if type_getal == int else 0.0
    schoon = "".join(c for c in str(tekst_waarde) if c.isdigit() or c in ".,-")
    schoon = schoon.replace(",", ".")
    try:
        return type_getal(float(schoon))
    except ValueError:
        return 0 if type_getal == int else 0.0

def formatteer_datum_nl(datum_str):
    try:
        dt = datetime.strptime(datum_str, "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except Exception:
        return datum_str

# Dialoogvenster om een auto te bewerken
@st.dialog("Auto Gegevens Bewerken")
def bewerk_auto_dialog(auto_id, ktk, km, inkoop, verkoop, apk, kosten, foto_huidig, naam_huidig):
    try:
        standaard_datum = datetime.strptime(apk, "%Y-%m-%d").date()
    except Exception:
        standaard_datum = datetime.date.today()

    v_naam = naam_huidig if naam_huidig and naam_huidig != "Nog niet ingevuld" else ""
    v_km = str(km) if km != 0 else ""
    v_inkoop = f"{inkoop:.2f}" if inkoop != 0.0 else ""
    v_verkoop = f"{verkoop:.2f}" if verkoop != 0.0 else ""
    v_kosten = f"{kosten:.2f}" if kosten != 0.0 else ""

    nieuw_naam = st.text_input("Naam / Omschrijving", value=v_naam, placeholder="Bijv. Volkswagen Golf Zwart")
    nieuw_kenteken = st.text_input("Kenteken (Verplicht)", value=ktk)
    nieuw_km_str = st.text_input("Kilometerstand", value=v_km, placeholder="Bijv. 145000")
    nieuwe_apk = st.date_input("APK Datum", value=standaard_datum)
    n_inkoop_str = st.text_input("Inkoopprijs (€)", value=v_inkoop, placeholder="Bijv. 2500")
    n_verkoop_str = st.text_input("Verkoopprijs (€)", value=v_verkoop, placeholder="Bijv. 3950")
    n_kosten_str = st.text_input("Extra kosten (€)", value=v_kosten, placeholder="Bijv. 150")

    nieuwe_foto = st.file_uploader("Voeg een nieuwe foto toe", type=["jpg", "jpeg", "png"], key=f"upload_edit_{auto_id}")

    if st.button("Wijzigingen Opslaan"):
        if not nieuw_kenteken:
            st.error("Het kenteken is verplicht om de auto op te slaan.")
        else:
            n_naam_opslaan = nieuw_naam.strip() if nieuw_naam.strip() else "Nog niet ingevuld"
            n_km = naar_getal(nieuw_km_str, int)
            n_inkoop = naar_getal(n_inkoop_str, float)
            n_verkoop = naar_getal(n_verkoop_str, float)
            n_kosten = naar_getal(n_kosten_str, float)

            if nieuwe_foto is not None:
                img = Image.open(nieuwe_foto)
                img.thumbnail((800, 800))
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=70)
                foto_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
                cursor.execute("UPDATE autos_v3 SET naam=?, kenteken=?, km_stand=?, inkoopprijs=?, verkoopprijs=?, apk_datum=?, extra_kosten=?, afbeelding=? WHERE id=?", (n_naam_opslaan, nieuw_kenteken.upper(), n_km, n_inkoop, n_verkoop, str(nieuwe_apk), n_kosten, foto_data, auto_id))
            else:
                cursor.execute("UPDATE autos_v3 SET naam=?, kenteken=?, km_stand=?, inkoopprijs=?, verkoopprijs=?, apk_datum=?, extra_kosten=? WHERE id=?", (n_naam_opslaan, nieuw_kenteken.upper(), n_km, n_inkoop, n_verkoop, str(nieuwe_apk), n_kosten, auto_id))
            conn.commit()
            st.success("Gegevens succesvol bijgewerkt!")
            st.rerun()

# --- HEADER ---
st.title("🚗 Autohandel Inventaris")
st.write("Beheer je voorraad, pas gegevens aan en bekijk je marges.")
if st.button("🚪 Uitloggen"):
    st.session_state["ingelogd"] = False
    st.rerun()

# --- TOEVOEGEN FORMULIER ---
st.subheader("Nieuwe auto toevoegen")
with st.form("auto_form", clear_on_submit=True):
    naam = st.text_input("Naam / Omschrijving", placeholder="Bijv. Volkswagen Golf Zwart (Optioneel)")
    kenteken = st.text_input("Kenteken (Verplicht)")
    inkoopprijs_str = st.text_input("Inkoopprijs (€)", placeholder="Optioneel")
    km_stand_str = st.text_input("Kilometerstand", placeholder="Optioneel")
    verkoopprijs_str = st.text_input("Verkoopprijs (€)", placeholder="Optioneel")
    apk_datum = st.date_input("APK Datum")
    extra_kosten_str = st.text_input("Extra kosten (€)", placeholder="Optioneel")
    gevoegde_foto = st.file_uploader("Kies een foto van de auto (Optioneel)", type=["jpg", "jpeg", "png"])
    submit = st.form_submit_button("Voeg toe aan inventaris")

if submit:
    if kenteken.strip():
        naam_opslaan = naam.strip() if naam.strip() else "Nog niet ingevuld"
        km_stand = naar_getal(km_stand_str, int)
        inkoopprijs = naar_getal(inkoopprijs_str, float)
        verkoopprijs = naar_getal(verkoopprijs_str, float)
        extra_kosten = naar_getal(extra_kosten_str, float)
        
        foto_data = ""
        if gevoegde_foto is not None:
            img = Image.open(gevoegde_foto)
            img.thumbnail((800, 800))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=70)
            foto_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
            
        cursor.execute("INSERT INTO autos_v3 (naam, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (naam_opslaan, kenteken.upper().strip(), km_stand, inkoopprijs, verkoopprijs, str(apk_datum), extra_kosten, foto_data))
        conn.commit()
        st.success(f"Auto met kenteken {kenteken.upper().strip()} succesvol toegevoegd!")
        st.rerun()
    else:
        st.error("Vul tenminste een geldig kenteken in om de auto toe te voegen.")

# --- INVENTARIS SECTIE ---
st.subheader("Huidige inventaris")
zoekterm = st.text_input("🔍 Zoek op kenteken of omschrijving...").upper()

cursor.execute("SELECT id, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, naam FROM autos_v3")
alle_autos = cursor.fetchall()

if alle_autos:
    for auto in alle_autos:
        auto_id, ktk, km, inkoop, verkoop, apk, kosten, foto_string, auto_naam = auto
        winst = verkoop - (inkoop + kosten)
        apk_nl = formatteer_datum_nl(apk)
        weergave_naam = auto_naam if auto_naam else "Nog niet ingevuld"


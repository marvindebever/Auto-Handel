import base64
from datetime import datetime
import io
import os
import sqlite3
from PIL import Image
import streamlit as st

st.set_page_config(page_title="Autohandel Inventaris", layout="wide")

# --- ULTIEME STYLING: RECHTE BALKEN EN WITTE LETTERS ---
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
        
        h1, h2, h3, p, span {{
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

        /* Styling voor de onverwoestbare HTML Dropdown container */
        summary {{
            padding: 15px;
            background-color: rgba(30, 30, 30, 0.95);
            color: white;
            font-size: 1.1rem;
            font-weight: bold;
            border-radius: 8px;
            cursor: pointer;
            border: 1px solid rgba(255, 255, 255, 0.3);
            text-shadow: -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000;
            margin-top: 12px;
        }}
        details {{
            background-color: rgba(15, 15, 15, 0.95);
            border-radius: 8px;
            margin-bottom: 12px;
            padding: 5px;
        }}
        .dropdown-inhoud {{
            padding: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
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
        naam TEXT,
        transmissie TEXT
    )
"""
)
conn.commit()

try:
    cursor.execute("ALTER TABLE autos_v3 ADD COLUMN transmissie TEXT")
    conn.commit()
except sqlite3.OperationalError:
    pass

def naar_getal(tekst_waarde, type_getal=float):
    if not tekst_waarde:
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
def bewerk_auto_dialog(auto_id, ktk, km, inkoop, verkoop, apk, kosten, foto_huidig, naam_huidig, trans_huidig):
    try:
        standaard_datum = datetime.strptime(apk, "%Y-%m-%d").date()
    except Exception:
        standaard_datum = datetime.date.today()

    nieuw_naam = st.text_input("Naam / Omschrijving", value=naam_huidig if naam_huidig else "")
    nieuw_kenteken = st.text_input("Kenteken", value=ktk)
    nieuw_km_str = st.text_input("Kilometerstand", value=str(km))
    nieuwe_apk = st.date_input("APK Datum", value=standaard_datum)
    
    opties = ["Handgeschakeld", "Automaat"]
    index_standaard = opties.index(trans_huidig) if trans_huidig in opties else 0
    nieuw_transmissie = st.selectbox("Transmissie", options=opties, index=index_standaard)
    
    n_inkoop_str = st.text_input("Inkoopprijs (€)", value=str(inkoop))
    n_verkoop_str = st.text_input("Verkoopprijs (€)", value=str(verkoop))
    n_kosten_str = st.text_input("Extra kosten (€)", value=str(kosten))

    nieuwe_foto = st.file_uploader("Voeg een nieuwe foto toe", type=["jpg", "jpeg", "png"], key=f"upload_edit_{auto_id}")

    if st.button("Wijzigingen Opslaan"):
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
            cursor.execute("UPDATE autos_v3 SET naam=?, kenteken=?, km_stand=?, inkoopprijs=?, verkoopprijs=?, apk_datum=?, extra_kosten=?, afbeelding=?, transmissie=? WHERE id=?", (nieuw_naam, nieuw_kenteken.upper(), n_km, n_inkoop, n_verkoop, str(nieuwe_apk), n_kosten, foto_data, nieuw_transmissie, auto_id))
        else:
            cursor.execute("UPDATE autos_v3 SET naam=?, kenteken=?, km_stand=?, inkoopprijs=?, verkoopprijs=?, apk_datum=?, extra_kosten=?, transmissie=? WHERE id=?", (nieuw_naam, nieuw_kenteken.upper(), n_km, n_inkoop, n_verkoop, str(nieuwe_apk), n_kosten, nieuw_transmissie, auto_id))
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
    naam = st.text_input("Naam / Omschrijving (Bijv. Volkswagen Golf Zwart)")
    kenteken = st.text_input("Kenteken")
    km_stand_str = st.text_input("Kilometerstand", value="0")
    apk_datum = st.date_input("APK Datum")
    transmissie = st.selectbox("Transmissie", options=["Handgeschakeld", "Automaat"])
    inkoopprijs_str = st.text_input("Inkoopprijs (€)", value="0.00")
    verkoopprijs_str = st.text_input("Verkoopprijs (€)", value="0.00")
    extra_kosten_str = st.text_input("Extra kosten (€)", value="0.00")
    gevoegde_foto = st.file_uploader("Kies een foto van de auto", type=["jpg", "jpeg", "png"])
    submit = st.form_submit_button("Voeg toe aan inventaris")

if submit:
    if kenteken:
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
        cursor.execute("INSERT INTO autos_v3 (naam, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, transmissie) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (naam, kenteken.upper(), km_stand, inkoopprijs, verkoopprijs, str(apk_datum), extra_kosten, foto_data, transmissie))
        conn.commit()
        st.success(f"Auto '{naam}' succesvol toegevoegd!")
        st.rerun()
    else:
        st.error("Vul een geldig kenteken in.")

# --- INVENTARIS SECTIE ---
st.subheader("Huidige inventaris")
zoekterm = st.text_input("🔍 Zoek op kenteken of omschrijving...").upper()

cursor.execute("SELECT id, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, naam, transmissie FROM autos_v3")
alle_autos = cursor.fetchall()

if not alle_autos:
    st.info("Er staan momenteel geen auto's in de database. Voeg hierboven een auto toe om de inventaris te bekijken!")


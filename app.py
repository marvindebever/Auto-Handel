import base64
from datetime import datetime
import io
import os
import sqlite3
from PIL import Image
import streamlit as st
import pandas as pd

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
# 🚨 DE GOUDEN REDDING: Een volledig schone database-naam om interne kolom-conflicten op te lossen!
conn = sqlite3.connect("autohandel_definitief.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS autos_final (
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

def naar_getal(tekst_waarde, type_getal=float):
    if not tekst_waarde:
        return 0 if type_getal == int else 0.0
    schoon = "".join(c for c in str(tekst_waarde) if c.isdigit() or c in ".,-")
    schoon = schoon.replace(",", ".")
    try:
        return type_getal(float(schoon))
    except ValueError:
        return 0 if type_getal == int else 0.0

# ✏️ GERASSUREERD BEWERKEN VENSTER
@st.dialog("Auto Gegevens Aanpassen")
def bewerk_auto_sneller_dialog():
    id_invoer = st.text_input("Voer het ID-nummer in van de auto die je wilt aanpassen:")
    target_id = naar_getal(id_invoer, int)
    
    if target_id > 0:
        cursor.execute("SELECT kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, naam, transmissie FROM autos_final WHERE id=?", (target_id,))
        bestaande_auto = cursor.fetchone()
        
        if bestaande_auto:
            ktk, km, inkoop, verkoop, apk, kosten, auto_naam, trans_huidig = bestaande_auto
            st.write("---")
            
            nieuw_naam = st.text_input("Naam / Omschrijving", value=auto_naam if auto_naam else "")
            nieuw_kenteken = st.text_input("Kenteken (Verplicht)", value=ktk)
            nieuw_km_str = st.text_input("Kilometerstand", value=str(km))
            nieuwe_apk = st.date_input("APK Datum", value=datetime.strptime(apk, "%Y-%m-%d").date() if apk else datetime.today().date())
            
            opties = ["Handgeschakeld", "Automaat"]
            index_standaard = opties.index(trans_huidig) if trans_huidig in opties else 0
            nieuw_transmissie = st.selectbox("Transmissie", options=opties, index=index_standaard)
            
            n_inkoop_str = st.text_input("Inkoopprijs (€)", value=str(inkoop))
            n_verkoop_str = st.text_input("Verkoopprijs (€)", value=str(verkoop))
            n_kosten_str = st.text_input("Extra kosten (€)", value=str(kosten))
            
            nieuwe_foto = st.file_uploader("Optioneel: Vervang de huidige foto", type=["jpg", "jpeg", "png"])
            
            if st.button("Wijzigingen Live Opslaan", type="primary"):
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
                    cursor.execute("UPDATE autos_final SET naam=?, kenteken=?, km_stand=?, inkoopprijs=?, verkoopprijs=?, apk_datum=?, extra_kosten=?, afbeelding=?, transmissie=? WHERE id=?", (nieuw_naam, nieuw_kenteken.upper(), n_km, n_inkoop, n_verkoop, str(nieuwe_apk), n_kosten, foto_data, nieuw_transmissie, target_id))
                else:
                    cursor.execute("UPDATE autos_final SET naam=?, kenteken=?, km_stand=?, inkoopprijs=?, verkoopprijs=?, apk_datum=?, extra_kosten=?, transmissie=? WHERE id=?", (nieuw_naam, nieuw_kenteken.upper(), n_km, n_inkoop, n_verkoop, str(nieuwe_apk), n_kosten, nieuw_transmissie, target_id))
                
                conn.commit()
                st.success("Auto succesvol bijgewerkt!")
                st.rerun()

# --- DISKREET VERWIJDEREN VENSTER ---
@st.dialog("Auto Definitief Verwijderen")
def verwijder_auto_dialog():
    id_invoer = st.text_input("Voer het ID-nummer in van de auto die je wilt WISSEN:")
    target_id = naar_getal(id_invoer, int)
    
    if target_id > 0:
        cursor.execute("DELETE FROM autos_final WHERE id=?", (target_id,))
        conn.commit()
        st.success("Auto succesvol gewist!")
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
        cursor.execute("INSERT INTO autos_final (naam, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, transmissie) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (naam, kenteken.upper(), km_stand, inkoopprijs, verkoopprijs, str(apk_datum), extra_kosten, foto_data, transmissie))
        conn.commit()
        st.success(f"Auto '{naam}' succesvol toegevoegd!")
        st.rerun()
    else:
        st.error("Vul een geldig kenteken in.")

# --- INVENTARIS SECTIE ---
st.subheader("Huidige inventaris")

# We lezen direct en sluitend uit de gloednieuwe tabel 'autos_final'

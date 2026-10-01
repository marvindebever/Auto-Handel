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

def naar_getal(tekst_waarde, type_getal=float):
    if not tekst_waarde or str(tekst_waarde).strip() == "":
        return 0 if type_getal == int else 0.0
    schoon = "".join(c for c in str(tekst_waarde) if c.isdigit() or c in ".,-")
    schoon = schoon.replace(",", ".")
    try:
        return type_getal(float(schoon))
    except ValueError:
        return 0 if type_getal == int else 0.0

# ✏️ VEILIG BEWERKEN VENSTER ZONDER ELSE
@st.dialog("Auto Gegevens Aanpassen")
def bewerk_auto_sneller_dialog():
    id_invoer = st.text_input("Voer het ID-nummer in van de auto die je wilt aanpassen:")
    target_id = naar_getal(id_invoer, int)
    
    if target_id <= 0:
        return
        
    cursor.execute("SELECT kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, naam FROM autos_v3 WHERE id=?", (target_id,))
    bestaande_auto = cursor.fetchone()
    
    if not bestaande_auto:
        st.warning("Geen auto gevonden met dit ID-nummer.")
        return
        
    ktk, km, inkoop, verkoop, apk, kosten, auto_naam = bestaande_auto
    st.write("---")
    
    nieuw_naam = st.text_input("Naam / Omschrijving", value=auto_naam if auto_naam else "")
    nieuw_kenteken = st.text_input("Kenteken (Verplicht)", value=ktk)
    nieuw_km_str = st.text_input("Kilometerstand", value=str(km))
    nieuwe_apk = st.date_input("APK Datum", value=datetime.strptime(apk, "%Y-%m-%d").date() if apk else datetime.today().date())
    n_inkoop_str = st.text_input("Inkoopprijs (€)", value=str(inkoop))
    n_verkoop_str = st.text_input("Verkoopprijs (€)", value=str(verkoop))
    n_kosten_str = st.text_input("Extra kosten (€) - Optioneel", value="" if kosten == 0.0 else str(kosten), placeholder="Laat leeg voor 0.00")
    
    nieuwe_foto = st.file_uploader("Optioneel: Vervang de huidige foto", type=["jpg", "jpeg", "png"])
    
    if st.button("Wijzigingen Live Opslaan", type="primary"):
        if not nieuw_kenteken.strip():
            st.error("Kenteken is verplicht.")
        else:
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
                cursor.execute("UPDATE autos_v3 SET naam=?, kenteken=?, km_stand=?, inkoopprijs=?, verkoopprijs=?, apk_datum=?, extra_kosten=?, afbeelding=? WHERE id=?", (nieuw_naam, nieuw_kenteken.upper().strip(), n_km, n_inkoop, n_verkoop, str(nieuwe_apk), n_kosten, foto_data, target_id))
            else:
                cursor.execute("UPDATE autos_v3 SET naam=?, kenteken=?, km_stand=?, inkoopprijs=?, verkoopprijs=?, apk_datum=?, extra_kosten=? WHERE id=?", (nieuw_naam, nieuw_kenteken.upper().strip(), n_km, n_inkoop, n_verkoop, str(nieuwe_apk), n_kosten, target_id))
            
            conn.commit()
            st.success("Auto succesvol bijgewerkt!")
            st.rerun()

# 🗑️ VEILIG VERWIJDEREN VENSTER ZONDER ELSE
@st.dialog("Auto Definitief Verwijderen")
def verwijder_auto_dialog():
    id_invoer = st.text_input("Voer het ID-nummer in van de auto die je wilt WISSEN:")
    target_id = naar_getal(id_invoer, int)
    
    if target_id <= 0:
        return
        
    cursor.execute("SELECT naam, kenteken FROM autos_v3 WHERE id=?", (target_id,))
    check_auto = cursor.fetchone()
    
    if not check_auto:
        st.warning("Geen auto gevonden met dit ID-nummer.")
        return
        
    st.warning(f"Weet je zeker dat je de auto met kenteken {check_auto[1]} wilt verwijderen?")
    if st.button("Ja, Definitief Wissen", type="primary"):
        cursor.execute("DELETE FROM autos_v3 WHERE id=?", (target_id,))
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
    kenteken = st.text_input("Kenteken (Verplicht)")
    inkoopprijs_str = st.text_input("Inkoopprijs (€)", value="0.00")
    km_stand_str = st.text_input("Kilometerstand", value="0")
    verkoopprijs_str = st.text_input("Verkoopprijs (€)", value="0.00")
    apk_datum = st.date_input("APK Datum")
    extra_kosten_str = st.text_input("Extra kosten (€) - Optioneel", placeholder="Laat leeg als er nog geen kosten zijn")
    gevoegde_foto = st.file_uploader("Kies een foto van de auto (Optioneel)", type=["jpg", "jpeg", "png"])
    submit = st.form_submit_button("Voeg toe aan inventaris")

if submit:
    if kenteken.strip():
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
            
        cursor.execute("INSERT INTO autos_v3 (naam, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (naam, kenteken.upper().strip(), km_stand, inkoopprijs, verkoopprijs, str(apk_datum), extra_kosten, foto_data))
        conn.commit()
        st.success(f"Auto met kenteken {kenteken.upper().strip()} succesvol toegevoegd!")
        st.rerun()
    else:
        st.error("Vul tenminste een kenteken in om de auto toe te voegen.")

# --- INVENTARIS SECTIE ---
st.subheader("Huidige inventaris")


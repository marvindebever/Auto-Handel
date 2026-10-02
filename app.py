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
        
        div[data-testid="stForm"], div[data-testid="stVerticalBlockBorderContainer"] {{
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
conn = sqlite3.connect("autohandel_v4.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS voorraad (
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
    km_stand_str = st.text_input("Kilometerstand", value="0")
    apk_datum = st.date_input("APK Datum")
    transmissie = st.selectbox("Transmissie", options=["Handgeschakeld", "Automaat"])
    inkoopprijs_str = st.text_input("Inkoopprijs (€)", value="0.00")
    verkoopprijs_str = st.text_input("Verkoopprijs (€)", value="0.00")
    extra_kosten_str = st.text_input("Extra kosten (€) - Optioneel", value="")
    gevoegde_foto = st.file_uploader("Kies een foto van de auto (Optioneel)", type=["jpg", "jpeg", "png"])
    submit = st.form_submit_button("Voeg toe aan voorraad")

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
            
        cursor.execute("INSERT INTO voorraad (naam, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, transmissie) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (naam, kenteken.upper().strip(), km_stand, inkoopprijs, verkoopprijs, str(apk_datum), extra_kosten, foto_data, transmissie))
        conn.commit()
        st.success(f"Auto met kenteken {kenteken.upper().strip()} succesvol toegevoegd!")
        st.rerun()
    if not kenteken.strip():
        st.error("Vul tenminste een kenteken in om de auto toe te voegen.")

# --- INVENTARIS SECTIE ---
st.subheader("Huidige inventaris")

df = pd.read_sql_query("SELECT id AS ID, naam AS Omschrijving, kenteken AS Kenteken, km_stand AS [KM Stand], transmissie AS Transmissie, inkoopprijs AS Inkoop, extra_kosten AS [Extra Kosten], verkoopprijs AS Verkoop, apk_datum AS [APK Datum] FROM voorraad", conn)
df["Verwachte Winst"] = df["Verkoop"] - (df["Inkoop"] + df["Extra Kosten"])

st.dataframe(df, use_container_width=True, hide_index=True)

# --- DIRECT ACTIEBLOK ONDERAAN ---
st.write("")
st.subheader("🛠️ Auto Aanpassen of Verwijderen")

actie_id_str = st.text_input("Voer het ID-nummer van de auto in om te openen:")
actie_id = naar_getal(actie_id_str, int)

if actie_id > 0:
    cursor.execute("SELECT kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, naam, transmissie, afbeelding FROM voorraad WHERE id=?", (actie_id,))
    bestaande_auto = cursor.fetchone()
    
    if bestaande_auto:
        ktk, km, inkoop, verkoop, apk, kosten, auto_naam, trans_huidig, foto_huidig = bestaande_auto
        st.write(f"Je bewerkt nu de auto: **{auto_naam if auto_naam else 'Onbekend'} ({ktk})**")
        
        with st.form("edit_form", clear_on_submit=False):
            edit_naam = st.text_input("Pas Naam / Omschrijving aan", value=auto_naam if auto_naam else "")
            edit_ktk = st.text_input("Pas Kenteken aan", value=ktk)
            edit_km = st.text_input("Pas Kilometerstand aan", value=str(km))
            edit_apk = st.date_input("Pas APK Datum aan", value=datetime.strptime(apk, "%Y-%m-%d").date() if apk else datetime.today().date())
            
            opties = ["Handgeschakeld", "Automaat"]
            index_standaard = opties.index(trans_huidig) if trans_huidig in opties else 0
            edit_trans = st.selectbox("Pas Transmissie aan", options=opties, index=index_standaard)
            
            edit_inkoop = st.text_input("Pas Inkoopprijs aan (€)", value=str(inkoop))
            edit_verkoop = st.text_input("Pas Verkoopprijs aan (€)", value=str(verkoop))
            edit_kosten = st.text_input("Pas Extra kosten aan (€)", value=str(kosten))
            edit_foto = st.file_uploader("Voeg een foto toe of vervang de huidige foto", type=["jpg", "jpeg", "png"])
            
            col_save, col_del = st.columns(2)
            with col_save:
                save_submit = st.form_submit_button("💾 Wijzigingen Live Opslaan", use_container_width=True)
            with col_del:
                del_submit = st.form_submit_button("🗑️ Auto Definitief Wissen", type="primary", use_container_width=True)
                
        if save_submit:
            if not edit_ktk.strip():
                st.error("Kenteken is verplicht.")
            if edit_ktk.strip():
                n_km = naar_getal(edit_km, int)
                n_inkoop = naar_getal(edit_inkoop, float)
                n_verkoop = naar_getal(edit_verkoop, float)
                n_kosten = naar_getal(edit_kosten, float)
                
                # 🚨 DE GOUDEN FIX: Geen if/else splitsing meer voor queries. We bepalen de fotostring eerst! [sqlite3]
                foto_opslaan = foto_huidig
                if edit_foto is not None:
                    img = Image.open(edit_foto)
                    img.thumbnail((800, 800))
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=70)
                    foto_opslaan = base64.b64encode(buffer.getvalue()).decode("utf-8")
                
                # Één enkele rechte, foutloze query [sqlite3]

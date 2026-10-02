import base64
from datetime import datetime
import io
import os
import sqlite3
from PIL import Image
import streamlit as st

st.set_page_config(page_title="Autohandel Inventaris", layout="wide")

# --- VEILIGE STYLING: MET VERPLICHTE SCROLBALK VOOR DE ZIJEBALK ---
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
        
        /* Outline voor perfecte leesbaarheid van teksten */
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
        
        div[data-baseweb="input"] input, div[data-testid="stTextInput"] input {{
            color: white !important;
            -webkit-text-fill-color: white !important;
        }}
        
        /* DE GOUDEN FIX: Zorgt dat de zijbalk ALTIJD kan scrollen als velden buiten het scherm vallen */
        [data-testid="stSidebarUserContent"] {{
            padding-top: 20px !important;
            max-height: 100vh !important;
            overflow-y: auto !important;
        }}
        
        [data-testid="stSidebar"] button {{
            background-color: #ff4b4b !important;
            color: white !important;
            opacity: 1 !important;
            visibility: visible !important;
            display: inline-block !important;
            margin-top: 15px !important;
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

def formatteer_datum_nl(datum_str):
    try:
        dt = datetime.strptime(datum_str, "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except Exception:
        return datum_str

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
    extra_kosten_str = st.text_input("Extra kosten (€) - Optioneel", value="0.00")
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
    else:
        st.error("Vul tenminste een kenteken in om de auto toe te voegen.")

# --- INVENTARIS SECTIE ---
st.subheader("Huidige inventaris")
zoekterm = st.text_input("🔍 Zoek op kenteken of omschrijving...").upper()

cursor.execute("SELECT id, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, naam, transmissie FROM voorraad")
alle_autos = cursor.fetchall()

if alle_autos:
    for auto in alle_autos:
        auto_id, ktk, km, inkoop, verkoop, apk, kosten, foto_string, auto_naam, trans = auto
        winst = verkoop - (inkoop + kosten)
        apk_nl = formatteer_datum_nl(apk)
        weergave_naam = auto_naam if auto_naam else "Onbekende auto"

        if zoekterm and (zoekterm not in ktk) and (zoekterm not in weergave_naam.upper()):
            continue

        with st.expander(f"🚗 {weergave_naam} ({ktk})  |  Verkoopprijs: €{verkoop:,.2f}  |  ID: {auto_id}"):
            col1, col2 = st.columns(2)
            
            with col1:
                if foto_string:
                    try:
                        st.image(base64.b64decode(foto_string), use_container_width=True)
                    except Exception:
                        st.error("Fout bij het laden van de afbeelding.")
                else:
                    st.info("Geen afbeelding beschikbaar.")
            
            with col2:
                st.write(f"**ID Nummer:** {auto_id}")
                st.write(f"**Kilometerstand:** {km:,} km")
                st.write(f"**Transmissie:** {trans if trans else 'Niet opgegeven'}")
                st.write(f"**APK Datum:** {apk_nl}")
                st.write(f"**Inkoopprijs:** €{inkoop:,.2f}")
                st.write(f"**Extra kosten:** €{kosten:,.2f}")
                st.write(f"**Verkoopprijs:** €{verkoop:,.2f}")
                st.write(f"**Verwachte Winst:** €{winst:,.2f}")
                
                if st.button("🗑️ Deze auto definitief verwijderen", key=f"del_inv_{auto_id}", type="primary"):
                    cursor.execute("DELETE FROM voorraad WHERE id=?", (auto_id,))
                    conn.commit()
                    st.success(f"Auto met ID {auto_id} succesvol verwijderd!")
                    st.rerun()

# --- DIRECT ACTIEBLOK ONDERAAN ---
st.write("")
st.subheader("🛠️ Auto Gegevens Aanpassen via ID")

actie_id_str = st.text_input("Voer het ID-nummer van de auto in om te openen:")
actie_id = naar_getal(actie_id_str, int)

if actie_id > 0:
    cursor.execute("SELECT kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, naam, transmissie, afbeelding FROM voorraad WHERE id=?", (actie_id,))
    bestaande_auto = cursor.fetchone()
    
    if bestaande_auto:
        ktk, km, inkoop, verkoop, apk, kosten, auto_naam, trans_huidig, foto_huidig = bestaande_auto
        
        st.sidebar.markdown(f"### ✏️ Auto Aanpassen (ID: {actie_id})")
        st.sidebar.write(f"Je bewerkt nu: **{auto_naam if auto_naam else 'Onbekend'}**")
        
        edit_naam = st.sidebar.text_input("Pas Naam / Omschrijving aan", value=auto_naam if auto_naam else "")
        edit_ktk = st.sidebar.text_input("Pas Kenteken aan", value=ktk)
        edit_km = st.sidebar.text_input("Pas Kilometerstand aan", value=str(km))
        
        try:
            standaard_datum = datetime.strptime(apk, "%Y-%m-%d").date()
        except Exception:
            standaard_datum = datetime.today().date()
            
        edit_apk = st.sidebar.date_input("Pas APK Datum aan", value=standard_datum)
        edit_trans = st.sidebar.selectbox("Pas Transmissie aan", options=["Handgeschakeld", "Automaat"], index=["Handgeschakeld", "Automaat"].index(trans_huidig) if trans_huidig in ["Handgeschakeld", "Automaat"] else 0)

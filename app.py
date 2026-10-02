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

# Dialoogvenster om een auto te verwijderen via ID invoer (voorkomt weergave-conflicten)
@st.dialog("Auto Verwijderen of Aanpassen")
def beheer_actie_dialog():
    auto_id_invoer = st.text_input("Voer het ID-nummer van de auto in:")
    actie = st.radio("Kies actie:", ["Verwijderen", "Gegevens Aanpassen"])
    
    if st.button("Uitvoeren", type="primary"):
        target_id = naar_getal(auto_id_invoer, int)
        if target_id > 0:
            if actie == "Verwijderen":
                cursor.execute("DELETE FROM autos_v3 WHERE id=?", (target_id,))
                conn.commit()
                st.success("Auto succesvol verwijderd!")
                st.rerun()
            else:
                st.info("Functie opengezet. Pas de waarden aan in de database.")

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
    inkoopprijs_str = st.text_input("Inkoopprijs (€)", value="0.00")
    km_stand_str = st.text_input("Kilometerstand", value="0")
    verkoopprijs_str = st.text_input("Verkoopprijs (€)", value="0.00")
    apk_datum = st.date_input("APK Datum")
    extra_kosten_str = st.text_input("Extra kosten (€) - Optioneel", placeholder="Laat leeg als er nog geen kosten zijn")
    gevoegde_foto = st.file_uploader("Kies een foto van de auto", type=["jpg", "jpeg", "png"])
    submit = st.form_submit_button("Voeg toe aan inventaris")

if submit:
    if kenteken and inkoopprijs_str != "0.00" and verkoopprijs_str != "0.00" and km_stand_str != "0":
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
        cursor.execute("INSERT INTO autos_v3 (naam, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (naam, kenteken.upper(), km_stand, inkoopprijs, verkoopprijs, str(apk_datum), extra_kosten, foto_data))
        conn.commit()
        st.success(f"Auto '{naam}' succesvol toegevoegd!")
        st.rerun()
    else:
        st.error("Vul tenminste een kenteken, kilometerstand, inkoop- en verkoopprijs in.")

# --- INVENTARIS SECTIE (VOLLEDIG LINEAIR VIA DATAFRAME) ---
st.subheader("Huidige inventaris")

# 🚨 DE ULTIEME REDDING: We laden de tabel in één klap in een DataFrame via Pandas. Dit heft alle lussen op!
df = pd.read_sql_query("SELECT id, naam AS Omschrijving, kenteken AS Kenteken, km_stand AS [KM Stand], inkoopprijs AS Inkoop, extra_kosten AS [Extra Kosten], verkoopprijs AS Verkoop, apk_datum AS [APK Datum] FROM autos_v3", conn)

# Bereken de winst direct veilig over de hele tabel kolommen
df["Verwachte Winst"] = df["Verkoop"] - (df["Inkoop"] + df["Extra Kosten"])

# Toon de inventaris in een prachtige, interactieve tabel
st.dataframe(df, use_container_width=True, hide_index=True)

st.write("")
if st.button("✏️ / 🗑️ Auto Aanpassen of Verwijderen"):
    beheer_actie_dialog()

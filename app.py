import base64
from datetime import datetime
import io
import os
import sqlite3
from PIL import Image
import streamlit as st

st.set_page_config(page_title="Autohandel Inventaris", layout="wide")

# --- VOLLEDIG GEOPTIMALISEERDE STYLING: TEKSTEN GEGARANDEERD WIT EN IN DE JUISTE BOX ---
def zet_achtergrond(logo_path="logo.png"):
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            data = f.read()
        encoded = base64.b64encode(data).decode("utf-8")
        
        css = f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background-image: linear-gradient(rgba(0, 0, 0, 0.4), rgba(0, 0, 0, 0.4)), url("data:image/png;base64,{encoded}");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}
        
        [data-testid="stMain"] {{
            background-color: transparent !important;
        }}
        
        /* Dwingt formulieren EN de nieuwe statistieken container in exact dezelfde donkere boxen */
        div[data-testid="stForm"], div[data-testid="stVerticalBlockBorderContainer"], .stat-box {{
            background-color: rgba(25, 25, 25, 0.90) !important;
            padding: 25px !important;
            border-radius: 12px !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            height: auto !important;
            max-height: none !important;
            overflow: visible !important;
        }}
        
        h1, h2, h3, p, span, label, li, td, th, div, .streamlit-expanderHeader p, .streamlit-expanderHeader span, [data-testid="stMarkdownContainer"] p {{
            color: white !important;
            text-shadow: 
                -1px -1px 0 #000,  
                 1px -1px 0 #000,
                -1px  1px 0 #000,
                 1px  1px 0 #000 !important;
        }}
        
        div[data-baseweb="input"] input, div[data-testid="stTextInput"] input, select {{
            background-color: #1e1e24 !important;
            color: white !important;
            -webkit-text-fill-color: white !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            text-shadow: none !important;
        }}
        
        /* Getallen in de statistiekenboxen ook perfect helder wit maken */
        div[data-testid="stMetricValue"] div {{
            color: white !important;
            font-weight: bold !important;
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

# --- GOUDEN ID HERNUMMERING FIX ---
def hernummer_database_ids():
    cursor.execute("SELECT kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, naam, transmissie FROM voorraad ORDER BY id ASC")
    rijen = cursor.fetchall()
    
    cursor.execute("DELETE FROM voorraad")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='voorraad'")
    
    for rij in rijen:
        cursor.execute(
            """
            INSERT INTO voorraad (kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, naam, transmissie)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rij
        )
    conn.commit()

hernummer_database_ids()

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
# --- MODERNE DIALOG BOX VOOR VOLLEDIG AANPASSEN (MET MEERDERE FOTO'S) ---
@st.dialog("✏️ Auto Gegevens Bewerken")
def bewerk_auto_dialog(actie_id, ktk, km, inkoop, verkoop, apk, kosten, foto_huidig, auto_naam, trans_huidig):
    try:
        standaard_datum = datetime.strptime(apk, "%Y-%m-%d").date()
    except Exception:
        standaard_datum = datetime.today().date()

    edit_naam = st.text_input("Pas Naam / Omschrijving aan", value=auto_naam if auto_naam else "")
    edit_ktk = st.text_input("Pas Kenteken aan", value=ktk)
    edit_km = st.text_input("Pas Kilometerstand aan", value=str(km))
    edit_apk = st.date_input("Pas APK Datum aan", value=standaard_datum)
    
    opties = ["Handgeschakeld", "Automaat"]
    index_standaard = opties.index(trans_huidig) if trans_huidig in opties else 0
    edit_trans = st.selectbox("Pas Transmissie aan", options=opties, index=index_standaard)
    
    edit_inkoop = st.text_input("Pas Inkoopprijs aan (€)", value=str(inkoop))
    edit_verkoop = st.text_input("Pas Verkoopprijs aan (€)", value=str(verkoop))
    edit_kosten = st.text_input("Pas Extra kosten aan (€)", value=str(kosten))
    
    edit_fotos = st.file_uploader("Upload nieuwe foto's (Laat leeg om huidige foto's te behouden)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    
    st.write("")
    if st.button("💾 Wijzigingen Live Opslaan", type="primary", use_container_width=True):
        if not edit_ktk.strip():
            st.error("Kenteken is verplicht.")
        else:
            n_km = naar_getal(edit_km, int)
            n_inkoop = naar_getal(edit_inkoop, float)
            n_verkoop = naar_getal(edit_verkoop, float)
            n_kosten = naar_getal(edit_kosten, float)
            
            foto_opslaan = foto_huidig
            if edit_fotos:
                foto_lijst = []
                for f in edit_fotos:
                    img = Image.open(f)
                    img.thumbnail((800, 800))
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=70)
                    encoded_foto = base64.b64encode(buffer.getvalue()).decode("utf-8")
                    foto_lijst.append(encoded_foto)
                foto_opslaan = "||".join(foto_lijst)
            
            cursor.execute(
                """
                UPDATE voorraad 
                SET naam=?, kenteken=?, km_stand=?, apk_datum=?, transmissie=?, inkoopprijs=?, verkoopprijs=?, extra_kosten=?, afbeelding=? 
                WHERE id=?
                """, 
                (edit_naam, edit_ktk.upper().strip(), n_km, str(edit_apk), edit_trans, n_inkoop, n_verkoop, n_kosten, foto_opslaan, actie_id)
            )
            conn.commit()
            st.success("Auto succesvol bijgewerkt!")
            st.rerun()

# --- HEADER SPREADING ---
head_col1, head_col2 = st.columns(2)
with head_col1:
    st.title("🚗 Autohandel Inventaris")
    st.write("Beheer je voorraad, pas gegevens aan en bekijk je marges.")
with head_col2:
    st.write("")  
    if st.button("🚪 Uitloggen", use_container_width=True):
        st.session_state["ingelogd"] = False
        st.rerun()

# --- DATA BEREKENEN VOOR STATISTIEKEN ---
cursor.execute("SELECT inkoopprijs, verkoopprijs, extra_kosten FROM voorraad")
stat_rijen = cursor.fetchall()

totaal_autos = len(stat_rijen)
totale_voorraadwaarde = 0.0
totale_verwachte_winst = 0.0

for r in stat_rijen:
    ink, verk, kost = r
    totale_voorraadwaarde += (ink + kost)
    totale_verwachte_winst += (verk - (ink + kost))

# --- LIVE DASHBOARD STATISTIEKEN IN DEZELFDE DONKERE STIJLBOX ---
st.write("")
st.subheader("📊 Actuele Status")

# We openen een native streamlit container die via de CSS (.stat-box) exact dezelfde styling krijgt als de rest van de formulieren
with st.container(border=True):
    stat_col1, stat_col2, stat_col3 = st.columns(3)
    with stat_col1:
        st.metric(label="Voorraad Aantal", value=f"{totaal_autos} stuks")
    with stat_col2:
        st.metric(label="Totale Investeringswaarde", value=f"€ {totale_voorraadwaarde:,.2f}")
    with stat_col3:
        st.metric(label="Totale Verwachte Winst", value=f"€ {totale_verwachte_winst:,.2f}")
st.write("---")

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
    
    gevoegde_fotos = st.file_uploader("Kies foto's van de auto (Optioneel)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    submit = st.form_submit_button("Voeg toe aan voorraad")

if submit:
    if kenteken.strip():
        km_stand = naar_getal(km_stand_str, int)
        inkoopprijs = naar_getal(inkoopprijs_str, float)
        verkoopprijs = naar_getal(verkoopprijs_str, float)
        extra_kosten = naar_getal(extra_kosten_str, float)
        
        foto_data = ""
        if gevoegde_fotos:
            foto_lijst = []
            for f in gevoegde_fotos:
                img = Image.open(f)
                img.thumbnail((800, 800))
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=70)
                encoded_foto = base64.b64encode(buffer.getvalue()).decode("utf-8")
                foto_lijst.append(encoded_foto)
            foto_data = "||".join(foto_lijst)
            
        cursor.execute("INSERT INTO voorraad (naam, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, transmissie) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (naam, kenteken.upper().strip(), km_stand, inkoopprijs, verkoopprijs, str(apk_datum), extra_kosten, foto_data, transmissie))
        conn.commit()
        st.success(f"Auto met kenteken {kenteken.upper().strip()} succesvol toegevoegd!")
        st.rerun()
    else:
        st.error("Vul tenminste een kenteken in om de auto toe te voegen.")

# --- INVENTARIS SECTIE ---
st.subheader("Huidige inventaris")

# REFRESH INDELING
inv_col1, inv_col2 = st.columns(2)
with inv_col1:
    zoekterm = st.text_input("🔍 Zoek op kenteken of omschrijving...").upper()
with inv_col2:
    st.write("")  
    if st.button("🔄 Inventaris Verversen", use_container_width=True, type="secondary"):
        st.rerun()

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

        with st.expander(f"🚗 {weergave_naam} ({ktk}) - Verkoopprijs: €{verkoop:,.2f}"):
            col1, col2 = st.columns(2)
            
            with col1:
                if foto_string:
                    alle_fotos = foto_string.split("||")
                    if len(alle_fotos) > 1:
                        foto_cols = st.columns(min(len(alle_fotos), 3))
                        for idx, f_data in enumerate(alle_fotos):
                            with foto_cols[idx % min(len(alle_fotos), 3)]:
                                try:
                                    st.image(base64.b64decode(f_data), use_container_width=True)
                                except Exception:
                                    st.error("Fout bij laden foto.")
                    else:
                        try:
                            st.image(base64.b64decode(alle_fotos), use_container_width=True)
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
                
                st.write("")
                btn_edit, btn_del = st.columns(2)
                with btn_edit:
                    if st.button("✏️ Gegevens Aanpassen", key=f"edit_inv_{auto_id}", use_container_width=True, type="primary"):
                        bewerk_auto_dialog(auto_id, ktk, km, inkoop, verkoop, apk, kosten, foto_string, auto_naam, trans)
                with btn_del:
                    if st.button("🗑️ Auto Verwijderen", key=f"del_inv_{auto_id}", use_container_width=True):
                        cursor.execute("DELETE FROM voorraad WHERE id=?", (auto_id,))
                        conn.commit()
                        st.success(f"Auto succesvol verwijderd!")
                        st.rerun()

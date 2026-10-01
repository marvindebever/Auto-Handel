import base64
from datetime import datetime
import io
import os
import sqlite3
from PIL import Image
import streamlit as st

st.set_page_config(page_title="Autohandel Inventaris", layout="wide")

# --- ACHTERGROND INSTELLEN MET EEN LICHTERE WAAS ---
def zet_achtergrond(logo_path="logo.png"):
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            data = f.read()
        encoded = base64.b64encode(data).decode("utf-8")
        # De waarde 0.4 zorgt nu voor een veel minder heftige witte waas
        css = f"""
        <style>
        .stApp {{
            background-image: linear-gradient(rgba(255, 255, 255, 0.4), rgba(255, 255, 255, 0.4)), url("data:image/png;base64,{encoded}");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)

# Roep de achtergrond direct aan
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
    CREATE TABLE IF NOT EXISTS autos (
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

try:
    cursor.execute("ALTER TABLE autos ADD COLUMN naam TEXT")
    conn.commit()
except sqlite3.OperationalError:
    pass

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

    nieuw_naam = st.text_input("Naam / Omschrijving", value=naam_huidig if naam_huidig else "")
    nieuw_kenteken = st.text_input("Kenteken", value=ktk)
    nieuw_km = st.number_input("Kilometerstand", min_value=0, step=1000, value=int(km))
    nieuwe_apk = st.date_input("APK Datum", value=standaard_datum)
    n_inkoop = st.number_input("Inkoopprijs (€)", min_value=0.0, step=50.0, value=float(inkoop))
    n_verkoop = st.number_input("Verkoopprijs (€)", min_value=0.0, step=50.0, value=float(verkoop))
    n_kosten = st.number_input("Extra kosten (€)", min_value=0.0, step=10.0, value=float(kosten))

    nieuwe_foto = st.file_uploader(
        "Voeg een nieuwe foto toe (Vervangt de huidige foto)", 
        type=["jpg", "jpeg", "png"],
        key=f"upload_edit_{auto_id}"
    )

    if st.button("Wijzigingen Opslaan"):
        if nieuwe_foto is not None:
            img = Image.open(nieuwe_foto)
            img.thumbnail((800, 800))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=70)
            foto_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
            
            cursor.execute(
                """
                UPDATE autos 
                SET naam=?, kenteken=?, km_stand=?, inkoopprijs=?, verkoopprijs=?, apk_datum=?, extra_kosten=?, afbeelding=?
                WHERE id=?
            """,
                (nieuw_naam, nieuw_kenteken.upper(), nieuw_km, n_inkoop, n_verkoop, str(nieuwe_apk), n_kosten, foto_data, auto_id),
            )
        else:
            cursor.execute(
                """
                UPDATE autos 
                SET naam=?, kenteken=?, km_stand=?, inkoopprijs=?, verkoopprijs=?, apk_datum=?, extra_kosten=?
                WHERE id=?
            """,
                (nieuw_naam, nieuw_kenteken.upper(), nieuw_km, n_inkoop, n_verkoop, str(nieuwe_apk), n_kosten, auto_id),
            )
            
        conn.commit()
        st.success("Gegevens succesvol bijgewerkt!")
        st.rerun()

# --- HEADER ---
col_titel, col_logout = st.columns([0.85, 0.15])
with col_titel:
    st.title("🚗 Autohandel Inventaris")
with col_logout:
    if st.button("🚪 Uitloggen"):
        st.session_state["ingelogd"] = False
        st.rerun()

st.write("Beheer je voorraad, pas gegevens aan en bekijk je marges.")

# --- TOEVOEGEN FORMULIER ---
st.subheader("Nieuwe auto toevoegen")
with st.form("auto_form", clear_on_submit=True):
    naam = st.text_input("Naam / Omschrijving (Bijv. Volkswagen Golf Zwart)")
    
    col1, col2 = st.columns(2)
    with col1:
        kenteken = st.text_input("Kenteken")
        km_stand = st.number_input("Kilometerstand", min_value=0, step=1000)
        apk_datum = st.date_input("APK Datum")
    with col2:
        inkoopprijs = st.number_input("Inkoopprijs (€)", min_value=0.0, step=50.0)
        verkoopprijs = st.number_input("Verkoopprijs (€)", min_value=0.0, step=50.0)
        extra_kosten = st.number_input("Extra kosten (€)", min_value=0.0, step=10.0)

    gevoegde_foto = st.file_uploader(
        "Kies een foto van de auto", type=["jpg", "jpeg", "png"]
    )
    submit = st.form_submit_button("Voeg toe aan inventaris")

if submit:
    if kenteken:
        foto_data = ""
        if gevoegde_foto is not None:
            img = Image.open(gevoegde_foto)
            img.thumbnail((800, 800))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=70)
            foto_data = base64.b64encode(buffer.getvalue()).decode("utf-8")

        cursor.execute(
            """
            INSERT INTO autos (naam, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (naam, kenteken.upper(), km_stand, inkoopprijs, verkoopprijs, str(apk_datum), extra_kosten, foto_data),
        )
        conn.commit()
        st.success(f"Auto '{naam}' met kenteken {kenteken.upper()} toegevoegd!")
        st.rerun()
    else:
        st.error("Vul een geldig kenteken in.")

# --- INVENTARIS MET ZOEKBALK ---
st.subheader("Huidige inventaris")
zoekterm = st.text_input("🔍 Zoek op kenteken of omschrijving...").upper()

if zoekterm:
    cursor.execute(
        "SELECT id, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, naam FROM autos WHERE kenteken LIKE ? OR naam LIKE ?",
        (f"%{zoekterm}%", f"%{zoekterm}%"),
    )
else:
    cursor.execute(
        "SELECT id, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, naam FROM autos"
    )

autos = cursor.fetchall()

if autos:
    for auto in autos:
        auto_id, ktk, km, inkoop, verkoop, apk, kosten, foto_string, auto_naam = auto
        winst = verkoop - (inkoop + kosten)
        apk_nl = formatteer_datum_nl(apk)
        
        weergave_naam = auto_naam if auto_naam else "Onbekende auto"

        with st.expander(f"🚗 {weergave_naam} ({ktk})  |  Verkoopprijs: €{verkoop:,.2f}"):
            kolom_links, kolom_rechts = st.columns(2)

            with kolom_links:
                if foto_string:
                    foto_bytes = base64.b64decode(foto_string)
                    st.image(foto_bytes, use_container_width=True)
                else:
                    st.info("Geen afbeelding beschikbaar.")

            with kolom_rechts:
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric(label="Kilometerstand", value=f"{km:,} km")
                    st.metric(label="APK Datum", value=apk_nl)
                with c2:
                    st.metric(label="Inkoopprijs", value=f"€{inkoop:,.2f}")
                    st.metric(label="Extra kosten", value=f"€{kosten:,.2f}")
                with c3:
                    st.metric(label="Verkoopprijs", value=f"€{verkoop:,.2f}")
                    st.metric(label="Verwachte Winst", value=f"€{winst:,.2f}")

                st.write("")
                btn_col1, btn_col2 = st.columns(2)

                with btn_col1:
                    if st.button("✏️ Gegevens Aanpassen", key=f"edit_{auto_id}"):
                        bewerk_auto_dialog(auto_id, ktk, km, inkoop, verkoop, apk, kosten, foto_string, auto_naam)

                with btn_col2:
                    if st.button("🗑️ Auto Verwijderen", key=f"delete_{auto_id}", type="primary"):
                        cursor.execute("DELETE FROM autos WHERE id=?", (auto_id,))
                        conn.commit()
                        st.success("Auto succesvol verwijderd!")
                        st.rerun()
else:
    st.info("Er staan nog geen auto's in de database.")

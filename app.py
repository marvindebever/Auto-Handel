import base64
from datetime import datetime
import io
import sqlite3
from PIL import Image
import streamlit as st

st.set_page_config(page_title="Autohandel Inventaris", layout="wide")

# --- WACHTWOORDBEVEILIGING ---
if "ingelogd" not in st.session_state:
    st.session_state["ingelogd"] = False


def controleer_wachtwoord():
    if st.session_state["wachtwoord_invoer"] == "DONGEN123":
        st.session_state["ingelogd"] = True
        st.success("Succesvol ingelogd!")
    else:
        st.error("Onjuist wachtwoord, probeer het opnieuw.")


if not st.session_state["ingelogd"]:
    st.title("🔒 Beveiligde Toegang")
    st.text_input(
        "Wachtwoord",
        type="password",
        key="wachtwoord_invoer",
        on_change=controleer_wachtwoord,
    )
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

# Automatische database update: voeg de kolom 'naam' toe als deze nog niet bestaat
try:
    cursor.execute("ALTER TABLE autos ADD COLUMN naam TEXT")
    conn.commit()
except sqlite3.OperationalError:
    pass  # Kolom bestaat al, geen actie nodig!


def formatteer_datum_nl(datum_str):
    try:
        dt = datetime.strptime(datum_str, "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except Exception:
        return datum_str


@st.dialog("Auto Gegevens Bewerken")
def bewerk_auto_dialog(auto_data):
    auto_id, ktk, km, inkoop, verkoop, apk, kosten, foto, naam_huidig = auto_data
    try:
        standaard_datum = datetime.strptime(apk, "%Y-%m-%d").date()
    except Exception:
        standaard_datum = datetime.date.today()

    nieuw_naam = st.text_input("Naam / Omschrijving", value=naam_huidig if naam_huidig else "")
    nieuw_kenteken = st.text_input("Kenteken", value=ktk)
    nieuw_km = st.number_input("Kilometerstand", min_value=0, step=1000, value=km)
    nieuwe_apk = st.date_input("APK Datum", value=standaard_datum)
    n_inkoop = st.number_input("Inkoopprijs (€)", min_value=0.0, step=50.0, value=inkoop)
    n_verkoop = st.number_input(
        "Verkoopprijs (€)", min_value=0.0, step=50.0, value=verkoop
    )
    n_kosten = st.number_input(
        "Extra kosten (€)", min_value=0.0, step=10.0, value=kosten
    )

    if st.button("Wijzigingen Opslaan"):
        cursor.execute(
            """
            UPDATE autos 
            SET naam=?, kenteken=?, km_stand=?, inkoopprijs=?, verkoopprijs=?, apk_datum=?, extra_kosten=?
            WHERE id=?
        """,
            (
                nieuw_naam,
                nieuw_kenteken.upper(),
                nieuw_km,
                n_inkoop,
                n_verkoop,
                str(nieuwe_apk),
                n_kosten,
                auto_id,
            ),
        )
        conn.commit()
        st.success("Gegevens succesvol bijgewerkt!")
        st.rerun()


# --- KOPPELING BOVENAAN ---
col_titel, col_logout = st.columns([0.85, 0.15])
with col_titel:
    st.title("🚗 Autohandel Inventaris")
with col_logout:
    if st.button("🚪 Uitloggen"):
        st.session_state["ingelogd"] = False
        st.rerun()

# --- TOEVOEGEN FORMULIER ---
st.subheader("Nieuwe auto toevoegen")
with st.form("auto_form", clear_on_submit=True):
    # Nieuw invoerveld voor de naam van de auto helemaal bovenaan het formulier
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
            (
                naam,
                kenteken.upper(),
                km_stand,
                inkoopprijs,
                verkoopprijs,
                str(apk_datum),
                extra_kosten,
                foto_data,
            ),
        )
        conn.commit()
        st.success(f"Auto '{naam}' met kenteken {kenteken.upper()} toegevoegd!")
        st.rerun()
    else:
        st.error("Vul een geldig kenteken in.")

# --- INVENTARIS MET ZOEKBALK ---
st.subheader("Huidige inventaris")

# De Zoekbalk (zoekt nu zowel op Kenteken als op Naam)
zoekterm = st.text_input("🔍 Zoek op kenteken of naam...").upper()

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
        
        # Geef de auto een standaardnaam als er geen naam is ingevuld (voor oude data)
        weergave_naam = auto_naam if auto_naam else "Onbekende auto"

        # De titel van de expander toont nu direct de Naam en het Kenteken
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
                        bewerk_auto_dialog(auto)

                with btn_col2:
                    if st.button(
                        "🗑️ Auto Verwijderen",
                        key=f"delete_{auto_id}",
                        type="primary",
                    ):
                        cursor.execute("DELETE FROM autos WHERE id=?", (auto_id,))
                        conn.commit()
                        st.success("Auto succesvol verwijderd!")
                        st.rerun()
else:
    st.info("Geen auto's gevonden.")

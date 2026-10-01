import base64
from datetime import datetime
import sqlite3
import streamlit as st

st.set_page_config(page_title="Autohandel Inventaris", layout="wide")

conn = sqlite3.connect("autohandel.db", check_same_thread=False)
cursor = conn.cursor()

# Tabel aanmaken
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
        afbeelding TEXT
    )
"""
)
conn.commit()


# Functie om datum om te zetten van YYYY-MM-DD naar DD-MM-YYYY voor het oog
def formatteer_datum_nl(datum_str):
    try:
        dt = datetime.strptime(datum_str, "%Y-%m-%d")
        return dt.strftime("%d-%m-%f")[0:10]  # Geeft dd-mm-yyyy
    except Exception:
        return datum_str


# Dialoogvenster om een auto te bewerken
@st.dialog("Auto Gegevens Bewerken")
def bewerk_auto_dialog(auto_data):
    auto_id, ktk, km, inkoop, verkoop, apk, kosten, foto = auto_data

    # Zet de opgeslagen datum string om naar een echt datum-object voor de invoer
    try:
        standaard_datum = datetime.strptime(apk, "%Y-%m-%d").date()
    except Exception:
        standaard_datum = datetime.date.today()

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
            SET kenteken=?, km_stand=?, inkoopprijs=?, verkoopprijs=?, apk_datum=?, extra_kosten=?
            WHERE id=?
        """,
            (
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


st.title("🚗 Autohandel Inventaris")
st.write("Beheer je voorraad, pas gegevens aan en bekijk je marges.")

# --- Formulierensectie ---
st.subheader("Nieuwe auto toevoegen")
with st.form("auto_form", clear_on_submit=True):
    col1, col2 = st.columns(2)

    with col1:
        kenteken = st.text_input("Kenteken")
        km_stand = st.number_input("Kilometerstand", min_value=0, step=1000)
        apk_datum = st.date_input("APK Datum")

    with col2:
        inkoopprijs = st.number_input("Inkoopprijs (€)", min_value=0.0, step=50.0)
        verkoopprijs = st.number_input("Verkoopprijs (€)", min_value=0.0, step=50.0)
        extra_kosten = st.number_input(
            "Extra kosten (Poetsen/Opknappen) (€)", min_value=0.0, step=10.0
        )

    gevoegde_foto = st.file_uploader(
        "Kies een foto van de auto", type=["jpg", "jpeg", "png"]
    )
    submit = st.form_submit_button("Voeg toe aan inventaris")

if submit:
    if kenteken:
        foto_data = ""
        if gevoegde_foto is not None:
            foto_bytes = gevoegde_foto.read()
            foto_data = base64.b64encode(foto_bytes).decode("utf-8")

        cursor.execute(
            """
            INSERT INTO autos (kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
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
        st.success(f"Auto met kenteken {kenteken.upper()} toegevoegd!")
        st.rerun()
    else:
        st.error("Vul een geldig kenteken in.")

# --- Inventarissectie ---
st.subheader("Huidige inventaris")
cursor.execute(
    "SELECT id, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding FROM autos"
)
autos = cursor.fetchall()

if autos:
    for auto in autos:
        auto_id, ktk, km, inkoop, verkoop, apk, kosten, foto_string = auto
        winst = verkoop - (inkoop + kosten)
        apk_nl = formatteer_datum_nl(apk)

        with st.expander(f"🚗 Kenteken: {ktk}  |  Verkoopprijs: €{verkoop:,.2f}"):
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

                # Bewerkknop toevoegen onder de statistieken
                st.write("")
                if st.button("✏️ Gegevens Aanpassen", key=f"edit_{auto_id}"):
                    bewerk_auto_dialog(auto)
else:
    st.info("Er staan nog geen auto's in de database.")

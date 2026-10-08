import base64
from datetime import datetime
import io
import os
import sqlite3
from PIL import Image
import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Autohandel Inventaris", layout="wide")
DB_NAME = "autohandel_v5.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS voorraad (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kenteken TEXT, km_stand INTEGER, inkoopprijs REAL, verkoopprijs REAL,
                apk_datum TEXT, extra_kosten REAL, afbeelding TEXT, naam TEXT, transmissie TEXT,
                status TEXT DEFAULT 'In voorraad',
                brandstof TEXT, vermogen INTEGER, kleur TEXT, cataloguswaarde REAL,
                bouwjaar INTEGER
            )
        """)
        cursor.execute("PRAGMA table_info(voorraad)")
        bestaande_kolommen = [k[1] for k in cursor.fetchall()]
        if "status" not in bestaande_kolommen:
            cursor.execute("ALTER TABLE voorraad ADD COLUMN status TEXT DEFAULT 'In voorraad'")
        if "brandstof" not in bestaande_kolommen:
            cursor.execute("ALTER TABLE voorraad ADD COLUMN brandstof TEXT")
        if "vermogen" not in bestaande_kolommen:
            cursor.execute("ALTER TABLE voorraad ADD COLUMN vermogen INTEGER")
        if "kleur" not in bestaande_kolommen:
            cursor.execute("ALTER TABLE voorraad ADD COLUMN kleur TEXT")
        if "cataloguswaarde" not in bestaande_kolommen:
            cursor.execute("ALTER TABLE voorraad ADD COLUMN cataloguswaarde REAL")
        if "bouwjaar" not in bestaande_kolommen:
            cursor.execute("ALTER TABLE voorraad ADD COLUMN bouwjaar INTEGER")
            
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agenda (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                datum TEXT,
                titel TEXT,
                notitie TEXT,
                status TEXT DEFAULT 'Open'
            )
        """)
        conn.commit()


init_db()

# --- STYLING & ACHTERGROND ---
def zet_achtergrond(logo_path="logo.png"):
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            data = f.read()
        encoded = base64.b64encode(data).decode("utf-8")
        
        css = f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background-image: linear-gradient(rgba(0, 0, 0, 0.4), rgba(0, 0, 0, 0.4)), url("data:image/png;base64,{encoded}");
            background-size: cover; background-position: center; background-repeat: no-repeat; background-attachment: fixed;
        }}
        [data-testid="stMain"] {{ background-color: transparent !important; }}
        div[data-testid="stForm"], div[data-testid="stVerticalBlockBorderContainer"], .streamlit-expanderContent {{
            background-color: rgba(25, 25, 25, 0.90) !important; padding: 25px !important;
            border-radius: 12px !important; border: 1px solid rgba(255, 255, 255, 0.1) !important;
            height: auto !important; max-height: none !important; overflow: visible !important;
        }}
        h1, h2, h3, p, span, label, li, td, th, div, .streamlit-expanderHeader p, .streamlit-expanderHeader span, [data-testid="stMarkdownContainer"] p {{
            color: white !important; text-shadow: -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, -1px 1px 0 #000 !important;
        }}
        div[data-baseweb="input"] input, div[data-testid="stTextInput"] input, select {{
            background-color: #1e1e24 !important; color: white !important; -webkit-text-fill-color: white !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important; text-shadow: none !important;
        }}
        div[data-testid="stMetricValue"] div {{ color: white !important; font-weight: bold !important; }}
        
        .stSidebar [data-testid="stFileUploadDropzone"],
        .stSidebar div[data-testid="stFileUploadDropzone"] > div,
        .stSidebar .stFileUploader section {{
            background-color: transparent !important;
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0px !important;
        }}
        
        .stSidebar [data-testid="stFileUploadDropzone"] button {{
            width: 100% !important;
            min-width: 100% !important;
            background-color: transparent !important;
            color: white !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            border-radius: 8px !important;
            padding: 0.5rem 1rem !important;
            height: auto !important;
            font-size: 1rem !important;
        }}
        .stSidebar [data-testid="stFileUploadDropzone"] button:hover {{
            border-color: rgb(255, 75, 75) !important;
            color: rgb(255, 75, 75) !important;
        }}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)

zet_achtergrond("logo.png")

# --- BEVEILIGING ---
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
    
# --- ROBUUSTE RDW KOPPELING ---

def overheid_rdw_lookup_krachtig(kenteken_str):
    """Haalt voertuiggegevens én brandstofgegevens rechtstreeks op uit het openbare RDW-register."""
    schoon = kenteken_str.replace("-", "").upper().strip()
    if not schoon:
        return None
    
    # 1. Basisvoertuig gegevens ophalen
    url_voertuig = f"https://opendata.rdw.nl/resource/m9d7-ebf2.json?kenteken={schoon}"
    # 2. Brandstof gegevens ophalen (andere dataset!)
    url_brandstof = f"https://rdw.nl{schoon}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    try:
        res_v = requests.get(url_voertuig, headers=headers, timeout=8)
        
        if res_v.status_code == 200:
            if "application/json" not in res_v.headers.get("Content-Type", ""):
                return {"fout": "RDW stuurde een onverwacht antwoordformaat (HTML). Probeer het over een moment opnieuw."}
                
            data_v = res_v.json()
            if isinstance(data_v, list) and len(data_v) > 0:
                voertuig = data_v[0]  
                
                merk = voertuig.get("merk", "").title()
                model = voertuig.get("handelsbenaming", "").title()
                volledige_naam = f"{merk} {model}".strip()
                
                kleur = voertuig.get("eerste_kleur", "Onbekend").title()
                cataloguswaarde = naar_getal(voertuig.get("catalogusprijs", 0.0))
                
                # --- GEOPTIMALISEERDE BRANDSTOF LOGICA (GEFIXT!) ---
                brandstof = "Benzine" # Standaard fallback
                try:
                    res_b = requests.get(url_brandstof, headers=headers, timeout=5)
                    if res_b.status_code == 200:
                        data_b = res_b.json()
                        # Controleer of de lijst gevuld is en pak het eerste element [0]
                        if isinstance(data_b, list) and len(data_b) > 0:
                            brandstof = data_b[0].get("brandstof_omschrijving", "Benzine").title()
                except Exception:
                    pass # Als de brandstof-call faalt, valt hij terug op de default
                # ----------------------------------------------------


                # --- LIVE RDW BOUWJAAR EXTRACTION ---
                bouwjaar = 0
                datum_toelating = voertuig.get("datum_eerste_toelating", "")
                if datum_toelating and len(str(datum_toelating)) >= 4:
                    try:
                        bouwjaar = int(str(datum_toelating)[:4])
                    except:
                        pass

                apk_verval = voertuig.get("vervaldatum_apk", "")
                apk_formatted = datetime.today().date()
                if apk_verval:
                    try: 
                        apk_formatted = datetime.strptime(str(apk_verval), "%Y%m%d").date()
                    except Exception: 
                        pass
                        
                return {
                    "naam": volledige_naam if volledige_naam else "Onbekend voertuig",
                    "apk": apk_formatted,
                    "brandstof": brandstof,
                    "bouwjaar": bouwjaar,
                    "kleur": kleur,
                    "cataloguswaarde": cataloguswaarde,
                    "fout": None
                }
            else:
                return {"fout": "Kenteken niet gevonden in het openbare RDW-register."}
        elif res_v.status_code == 403:
            return {"fout": "Toegang geweigerd (403) door RDW. Server blokkeert mogelijk tijdelijk je IP."}
        elif res_v.status_code == 429:
            return {"fout": "Te veel aanvragen achter elkaar (429). Wacht 10 seconden."}
        else:
            return {"fout": f"RDW Server gaf een foutmelding. Statuscode: {res_v.status_code}."}
            
    except requests.exceptions.Timeout:
        return {"fout": "De verbinding met de RDW duurde te lang. Controleer je internet."}
    except Exception as e:
        return {"fout": f"Fout bij ophalen RDW-gegevens: {str(e)}"}


# --- HELPER FUNCTIES VOOR FORMATTERING ---
def naar_getal(tekst_waarde, type_getal=float):
    if not tekst_waarde: return 0 if type_getal == int else 0.0
    schoon = "".join(c for c in str(tekst_waarde) if c.isdigit() or c in ".,-").replace(",", ".")
    try: return type_getal(float(schoon))
    except: return 0 if type_getal == int else 0.0

def formatteer_datum_nl(datum_str):
    try: return datetime.strptime(datum_str, "%Y-%m-%d").strftime("%d-%m-%Y")
    except: return datum_str

def formatteer_euro_nl(bedrag):
    return f"{bedrag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- DATA IMPORT & EXPORT FUNCTIES ---
def exporteer_database_naar_json():
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row  
        cursor = conn.cursor()
        
        cursor.execute("SELECT kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, naam, transmissie, status, brandstof, bouwjaar, kleur, cataloguswaarde FROM voorraad")
        voorraad_rijen = cursor.fetchall()
        voorraad_data = [dict(rij) for rij in voorraad_rijen]
        
        cursor.execute("SELECT datum, titel, notitie, status FROM agenda")
        agenda_rijen = cursor.fetchall()
        agenda_data = [dict(rij) for rij in agenda_rijen]
        
        actueel_startbudget = st.session_state.get("startbudget", 10000.0)
        
        volledige_backup = {
            "startbudget": actueel_startbudget,
            "voorraad": voorraad_data,
            "agenda": agenda_data
        }
    import json
    return json.dumps(volledige_backup, indent=4)


def importeer_json_naar_database(json_data):
    import json
    try:
        backup_pakket = json.loads(json_data)
        if isinstance(backup_pakket, dict):
            voertuigen = backup_pakket.get("voorraad", [])
            afspraken = backup_pakket.get("agenda", [])
            st.session_state["startbudget"] = float(backup_pakket.get("startbudget", 10000.0))
        else:
            voertuigen = backup_pakket
            afspraken = []
            st.session_state["startbudget"] = 10000.0
            
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM voorraad")
            cursor.execute("DELETE FROM agenda")
            
            for v in voertuigen:
                cursor.execute("""
                    INSERT INTO voorraad (kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, naam, transmissie, status, brandstof, bouwjaar, kleur, cataloguswaarde)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (v.get("kenteken"), v.get("km_stand"), v.get("inkoopprijs"), v.get("verkoopprijs"), v.get("apk_datum"), v.get("extra_kosten"), v.get("afbeelding"), v.get("naam"), v.get("transmissie"), v.get("status"), v.get("brandstof"), v.get("bouwjaar"), v.get("kleur"), v.get("cataloguswaarde")))
            
            for a in afspraken:
                cursor.execute("""
                    INSERT INTO agenda (datum, titel, notitie, status)
                    VALUES (?, ?, ?, ?)
                """, (a.get("datum"), a.get("titel"), a.get("notitie"), a.get("status", "Open")))
            conn.commit()
        return True
    except Exception as e:
        st.sidebar.error(f"Import mislukt: {str(e)}")
        return False


# --- DIALOGS (BEWERKEN POP-UP) ---
@st.dialog("✏️ Auto Gegevens Bewerken")
def bewerk_auto_dialog(actie_id, ktk, km, inkoop, verkoop, apk, kosten, foto_huidig, auto_naam, trans_huidig, status_huidig, brandstof_h, bouwjaar_h, kleur_h, cat_h):
    try: standaard_datum = datetime.strptime(apk, "%Y-%m-%d").date()
    except: standaard_datum = datetime.today().date()

    uploader_key = f"fotos_upload_{actie_id}"

    edit_naam = st.text_input("Pas Naam / Omschrijving aan", value=auto_naam if auto_naam else "")
    edit_ktk = st.text_input("Pas Kenteken aan", value=ktk)
    status_opties = ["In voorraad", "Gereserveerd", "Verkocht"]
    edit_status = st.selectbox("Status", options=status_opties, index=status_opties.index(status_huidig) if status_huidig in status_opties else 0)
    
    col_e1, col_e2 = st.columns(2)
    edit_km = col_e1.text_input("Pas Kilometerstand aan", value=str(km))
    edit_apk = col_e2.date_input("Pas APK Datum aan", value=standaard_datum)
    
    col_e3, col_e4 = st.columns(2)
    edit_brandstof = col_e3.text_input("Pas Brandstof aan", value=str(brandstof_h if brandstof_h else "Benzine"))
    edit_bouwjaar = col_e4.text_input("Pas Bouwjaar aan", value=str(bouwjaar_h if bouwjaar_h else 0))
    
    col_e5, col_e6 = st.columns(2)
    edit_kleur = col_e5.text_input("Pas Kleur aan", value=str(kleur_h if kleur_h else ""))
    edit_cat = col_e6.text_input("Pas Cataloguswaarde aan (€)", value=str(cat_h if cat_h else 0.0))

    trans_opties = ["Handgeschakeld", "Automaat"]
    edit_trans = st.selectbox("Pas Transmissie aan", options=trans_opties, index=trans_opties.index(trans_huidig) if trans_huidig in trans_opties else 0)
    
    col_e7, col_e8, col_e9 = st.columns(3)
    edit_inkoop = col_e7.text_input("Pas Inkoopprijs aan", value=str(inkoop))
    edit_verkoop = col_e8.text_input("Pas Verkoopprijs aan", value=str(verkoop))
    edit_kosten = col_e9.text_input("Pas Extra kosten aan", value=str(kosten))
    
    if foto_huidig:
        st.write("🟢 Deze auto heeft momenteel opgeslagen foto's.")
        if st.button("🗑️ Wis alle bestaande foto's", type="secondary", use_container_width=True):
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE voorraad SET afbeelding='' WHERE id=?", (actie_id,))
                conn.commit()
            st.toast("⚡ Bestaande foto's succesvol gewist!", icon="🗑️")
            st.rerun()
    else:
        st.write("⚪ Deze auto heeft momenteel geen foto's.")

    edit_fotos = st.file_uploader("Upload nieuwe foto's", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key=uploader_key)
    
    if st.button("💾 Wijzigingen Live Opslaan", type="primary", use_container_width=True):
        if edit_ktk.strip():
            foto_opslaan = foto_huidig
            geuploade_bestanden = st.session_state.get(uploader_key)
            
            if geuploade_bestanden:
                foto_lijst = []
                for f in geuploade_bestanden:
                    img = Image.open(f)
                    img.thumbnail((800, 800))
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=70)
                    foto_lijst.append(base64.b64encode(buffer.getvalue()).decode("utf-8"))
                foto_opslaan = "||".join(foto_lijst)
            
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE voorraad 
                    SET naam=?, kenteken=?, km_stand=?, apk_datum=?, transmissie=?, inkoopprijs=?, verkoopprijs=?, extra_kosten=?, afbeelding=?, status=?, brandstof=?, bouwjaar=?, kleur=?, cataloguswaarde=?
                    WHERE id=?
                """, (edit_naam, edit_ktk.upper().replace("-", "").strip(), naar_getal(edit_km, int), str(edit_apk), edit_trans, naar_getal(edit_inkoop), naar_getal(edit_verkoop), naar_getal(edit_kosten), foto_opslaan, edit_status, edit_brandstof, naar_getal(edit_bouwjaar, int), edit_kleur, naar_getal(edit_cat), actie_id))
                conn.commit()
            
            if uploader_key in st.session_state:
                del st.session_state[uploader_key]
            st.rerun()


# --- DIALOG & PDF GENERATOR VOOR KOOPOVEREENKOMST ---
@st.dialog("📄 Particuliere Koopovereenkomst Genereren")
def genereer_contract_dialog(auto_id, merk_model, kenteken, km, verkoop, apk):
    st.write("Vul de gegevens van de koper in om de officiële koopovereenkomst te genereren.")
    
    koper_naam = st.text_input("Naam Koper")
    koper_adres = st.text_input("Adres & Huisnummer Koper")
    koper_postcode = st.text_input("Postcode & Woonplaats Koper")
    koper_tel = st.text_input("Telefoonnummer Koper")
    koper_legit = st.text_input("Legitimatie Koper (Type/Nr)", placeholder="Bijv. Rijbewijs / Nummer")
    
    st.markdown("---")
    st.write("**Financiële Afspraken:**")
    betaalwijze = st.radio("Wijze van betaling:", ["Contant", "Per bankoverschrijving"], horizontal=True)
    bijzondere_afspraken = st.text_area("Eventuele aanvullende afspraken of opmerkingen")

    if st.button("🔥 PDF Contract Downloaden", type="primary", use_container_width=True):
        if not koper_naam.strip():
            st.error("Vul tenminste de naam van de koper in.")
            return

        contant_vink = "[X]" if betaalwijze == "Contant" else "[  ]"
        bank_vink = "[X]" if betaalwijze == "Per bankoverschrijving" else "[  ]"
        huidige_datum = datetime.today().strftime('%d-%m-%Y')

        html_content = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; color: #000; padding: 20px; line-height: 1.4; }}
                h2 {{ text-align: center; border-bottom: 2px solid #000; padding-bottom: 5px; }}
                h3 {{ background-color: #f2f2f2; padding: 5px; margin-top: 15px; border: 1px solid #000; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; }}
                td {{ padding: 4px; vertical-align: top; }}
                .label {{ font-weight: bold; width: 180px; }}
                .footnote {{ font-size: 8px; color: #555; text-align: center; margin-top: 30px; border-top: 1px solid #ccc; padding-top: 5px; }}
            </style>
        </head>
        <body>
            <h2>PARTICULIERE KOOPOVEREENKOMST AUTO</h2>
            <p style="font-size: 11px; font-style: italic;">(Margevoertuig / Zonder Garantie)<br>
            Ondergetekenden komen overeen dat de verkoper het hieronder omschreven voertuig verkoopt aan de koper tegen de overengekomen prijs. Deze verkoop geschiedt tussen twee particulieren.</p>
            
            <h3>1. Gegevens van de Verkoper</h3>
            <table>
                <tr><td class="label">Naam / Bedrijfsnaam:</td><td>Autohandel Dongen</td></tr>
                <tr><td class="label">Adres & Huisnummer:</td><td>De Volger 2B</td></tr>
                <tr><td class="label">Postcode & Woonplaats:</td><td>5051 CX Dongen</td></tr>
            </table>

            <h3>2. Gegevens van de Koper</h3>
            <table>
                <tr><td class="label">Naam:</td><td>{koper_naam}</td></tr>
                <tr><td class="label">Adres & Huisnummer:</td><td>{koper_adres}</td></tr>
                <tr><td class="label">Postcode & Woonplaats:</td><td>{koper_postcode}</td></tr>
                <tr><td class="label">Telefoonnummer:</td><td>{koper_tel if koper_tel else '-'}</td></tr>
                <tr><td class="label">Legitimatie (Type/Nr):</td><td>{koper_legit if koper_legit else '-'}</td></tr>
            </table>

            <h3>3. Voertuiggegevens</h3>
            <table>
                <tr><td class="label">Merk & Model:</td><td>{merk_model}</td><td class="label">Kenteken:</td><td>{kenteken}</td></tr>
                <tr><td class="label">Tellerstand:</td><td>{km:,} km</td><td class="label">APK geldig tot:</td><td>{formatteer_datum_nl(apk)}</td></tr>
            </table>

            <h3>4. Financiële Afspraken & Levering</h3>
            <table>
                <tr><td class="label">Overeengekomen prijs:</td><td>&euro; {formatteer_euro_nl(verkoop)}</td></tr>
                <tr><td class="label">Wijze van betaling:</td><td>{contant_vink} Contant &nbsp;&nbsp;&nbsp; {bank_vink} Per bankoverschrijving</td></tr>
                <tr><td class="label">Datum van levering:</td><td>{huidige_datum}</td></tr>
            </table>

            <h3>5. Bijzondere Afspraken</h3>
            <p style="font-size: 11px;">{bijzondere_afspraken if bijzondere_afspraken.strip() else 'Geen.'}</p>

            <h3>6. Handtekening voor Akkoord</h3>
            <table style="margin-top: 20px;">
                <tr>
                    <td style="border: 1px solid #000; width: 50%; height: 80px; padding: 5px;">Handtekening Verkoper:<br><br><br>Datum: {huidige_datum}</td>
                    <td style="border: 1px solid #000; width: 50%; height: 80px; padding: 5px;">Handtekening Koper:<br><br><br>Datum: {huidige_datum}</td>
                </tr>
            </table>
        </body>
        </html>
        """
        b64 = base64.b64encode(html_content.encode('utf-8')).decode()
        filename = f"Koopovereenkomst_{kenteken}_{huidige_datum}.html"
        href = f'<a href="data:text/html;base64,{b64}" download="{filename}" style="display:block; text-align:center; background-color:#28a745; color:white; padding:10px; border-radius:8px; text-decoration:none; font-weight:bold;">📥 Download Overeenkomst (Open & Print)</a>'
        st.markdown(href, unsafe_allow_html=True)

# --- SIDEBAR NAVIGATIE, DATA CALCULATIE & BACKUP ---
with st.sidebar:
    st.title("⚙️ Navigatie")
    menu_optie = st.radio(
        "Kies een functie:",
        ["🆕 Nieuwe auto toevoegen", "🟢 Actuele Voorraad", "🔴 Verkochte Voertuigen", "📅 Agenda & Notities", "📊 Actuele Status Dashboard", "💰 Financieel Overzicht"]
    )
    
    st.markdown("---")
    st.subheader("💾 Backup & Herstel")
    
    try:
        json_string = exporteer_database_naar_json()
        st.download_button(
            label="📤 Exporteer Data (Backup)",
            data=json_string,
            file_name=f"autohandel_backup_{datetime.today().strftime('%Y-%m-%d')}.json",
            mime="application/json",
            use_container_width=True
        )
    except Exception as e:
        st.error("Export mislukt")

    geimporteerd_bestand = st.file_uploader("📥 Importeer Data (Herstel)", type=["json"])
    if geimporteerd_bestand is not None:
        json_data = geimporteerd_bestand.getvalue().decode("utf-8")
        if st.button("🔄 Herstel database nu", type="primary", use_container_width=True):
            if importeer_json_naar_database(json_data):
                st.toast("⚡ Database succesvol hersteld!", icon="✅")
                st.rerun()

    st.markdown("---")
    if st.button("🚪 Uitloggen", use_container_width=True):
        st.session_state["ingelogd"] = False
        st.rerun()

# Financiële cijfers live en veilig laden uit de database
with sqlite3.connect(DB_NAME) as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT inkoopprijs, verkoopprijs, extra_kosten, status FROM voorraad")
    stat_rijen = cursor.fetchall()

autos_in_voorraad = [r for r in stat_rijen if r[3] != 'Verkocht']
autos_verkocht = [r for r in stat_rijen if r[3] == 'Verkocht']

totale_voorraadwaarde = sum(r[0] + r[2] for r in autos_in_voorraad)
gerealiseerde_winst = sum(r[1] - (r[0] + r[2]) for r in autos_verkocht)

if "startbudget" not in st.session_state:
    st.session_state["startbudget"] = 10000.0

actueel_vrij_budget = st.session_state["startbudget"] - totale_voorraadwaarde + gerealiseerde_winst

# --- INTERFACE STRUCTUUR ---
if menu_optie == "🆕 Nieuwe auto toevoegen":
    st.title("🆕 Nieuwe auto toevoegen")
    
    rdw_col1, rdw_col2 = st.columns(2, vertical_alignment="bottom")
    rdw_kenteken = rdw_col1.text_input("Snel RDW via kenteken", placeholder="Bijv. 47-LV-JV").upper().replace("-", "")

    with rdw_col2:
        klik_rdw = st.button("🔍 RDW Gegevens Ophalen", use_container_width=True)

    if klik_rdw and rdw_kenteken:
        rdw_data = overheid_rdw_lookup_krachtig(rdw_kenteken)
        if rdw_data and rdw_data.get("fout") is None:
            st.session_state["rdw_naam"] = rdw_data["naam"]
            st.session_state["rdw_apk"] = rdw_data["apk"]
            st.session_state["rdw_brandstof"] = rdw_data["brandstof"]
            st.session_state["rdw_bouwjaar"] = rdw_data["bouwjaar"]
            st.session_state["rdw_kleur"] = rdw_data["kleur"]
            st.session_state["rdw_cataloguswaarde"] = rdw_data["cataloguswaarde"]
            st.session_state["rdw_ktk"] = rdw_kenteken
            st.toast("⚡ RDW succesvol geladen!", icon="✅")
        elif rdw_data and rdw_data.get("fout"): 
            st.error(rdw_data["fout"])

    with st.form("auto_form", clear_on_submit=False):
        naam = st.text_input("Naam / Omschrijving", value=st.session_state.get("rdw_naam", ""))
        kenteken = st.text_input("Kenteken (Verplicht)", value=st.session_state.get("rdw_ktk", ""))
        
        c_form1, c_form2 = st.columns(2)
        km_stand_str = c_form1.text_input("Kilometerstand", value="0")
        apk_datum = c_form2.date_input("APK Datum", value=st.session_state.get("rdw_apk", datetime.today().date()), format="DD-MM-YYYY")

        
        c_form3, c_form4 = st.columns(2)
        brandstof_invoer = c_form3.text_input("Brandstof", value=st.session_state.get("rdw_brandstof", "Benzine"))
        bouwjaar_invoer = c_form4.text_input("Bouwjaar", value=str(st.session_state.get("rdw_bouwjaar", 0)))

        c_form5, c_form6 = st.columns(2)
        kleur_invoer = c_form5.text_input("Kleur", value=st.session_state.get("rdw_kleur", ""))
        cat_invoer = c_form6.text_input("Oorspronkelijke Cataloguswaarde (€)", value=str(st.session_state.get("rdw_cataloguswaarde", 0.0)))

        transmissie = st.selectbox("Transmissie", options=["Handgeschakeld", "Automaat"])
        status_invoer = st.selectbox("Status bij instroom", options=["In voorraad", "Gereserveerd"])
        
        c_form7, c_form8, c_form9 = st.columns(3)
        inkoopprijs_str = c_form7.text_input("Inkoopprijs (€)", value="0.00")
        verkoopprijs_str = rdw_col1 = c_form8.text_input("Verkoopprijs (€)", value="0.00")
        extra_kosten_str = c_form9.text_input("Extra kosten (€)", value="0.00")
        gevoegde_fotos = st.file_uploader("Kies foto's (Optioneel)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
        submit = st.form_submit_button("Voeg toe aan voorraad")

    if submit and kenteken.strip():
        foto_data = ""
        if gevoegde_fotos:
            foto_lijst = []
            for f in gevoegde_fotos:
                img = Image.open(f)
                img.thumbnail((800, 800))
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=70)
                foto_lijst.append(base64.b64encode(buffer.getvalue()).decode("utf-8"))
            foto_data = "||".join(foto_lijst)
            
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO voorraad (naam, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, transmissie, status, brandstof, bouwjaar, kleur, cataloguswaarde) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (naam, kenteken.upper().replace("-", "").strip(), naar_getal(km_stand_str, int), naar_getal(inkoopprijs_str), naar_getal(verkoopprijs_str), str(apk_datum), naar_getal(extra_kosten_str), foto_data, transmissie, status_invoer, brandstof_invoer, naar_getal(bouwjaar_invoer, int), kleur_invoer, naar_getal(cat_invoer)))
            conn.commit()
            
        for sleutel in ["rdw_naam", "rdw_ktk", "rdw_apk", "rdw_brandstof", "rdw_bouwjaar", "rdw_kleur", "rdw_cataloguswaarde"]:
            if sleutel in st.session_state: del st.session_state[sleutel]
        st.success("Auto succesvol toegevoegd!")
        st.rerun()


elif menu_optie == "📊 Actuele Status Dashboard":
    st.title("📊 Actuele Status Dashboard")
    st.subheader("Financiële kerncijfers & Budgetbeheer")
    
    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    stat_col1.metric(label="Huidige Voorraad", value=f"{len(autos_in_voorraad)} stuks")
    stat_col2.metric(label="Investeringswaarde (Vast in auto's)", value=f"€ {formatteer_euro_nl(totale_voorraadwaarde)}")
    
    if actueel_vrij_budget < 0:
        stat_col3.metric(label="🚨 Besteedbaar Budget (KAS)", value=f"€ {formatteer_euro_nl(actueel_vrij_budget)}", delta="TE WEINIG BUDGET!", delta_color="inverse")
    else:
        stat_col3.metric(label="💰 Besteedbaar Budget (KAS)", value=f"€ {formatteer_euro_nl(actueel_vrij_budget)}")
        
    stat_col4.metric(label="Gerealiseerde Winst (Netto)", value=f"€ {formatteer_euro_nl(gerealiseerde_winst)}")

elif menu_optie in ["🟢 Actuele Voorraad", "🔴 Verkochte Voertuigen"]:
    st.title(menu_optie)
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, naam, transmissie, status, brandstof, bouwjaar, kleur, cataloguswaarde FROM voorraad")
        alle_autos = cursor.fetchall()

    verwerkte_autos = []
    if alle_autos:
        for auto in alle_autos:
            winst = auto[4] - (auto[3] + auto[6])
            verwerkte_autos.append({
                "id": auto[0], "kenteken": auto[1], "km_stand": auto[2], "inkoopprijs": auto[3], "verkoopprijs": auto[4],
                "apk_datum": auto[5], "extra_kosten": auto[6], "afbeelding": auto[7], "naam": auto[8], "transmissie": auto[9], 
                "status": auto[10], "brandstof": auto[11] if auto[11] else "Onbekend", "bouwjaar": auto[12] if auto[12] else 0,
                "kleur": auto[13] if auto[13] else "Onbekend", "cataloguswaarde": auto[14] if auto[14] else 0.0, "winst": winst
            })

        if menu_optie == "🟢 Actuele Voorraad":
            verwerkte_autos = [x for x in verwerkte_autos if x["status"] != "Verkocht"]
        else:
            verwerkte_autos = [x for x in verwerkte_autos if x["status"] == "Verkocht"]

        st.markdown("### 🔍 Filters & Sortering")
        
        inv_col1, inv_col2, inv_col3 = st.columns([2, 1.5, 1], vertical_alignment="bottom")
        zoekterm = inv_col1.text_input("Zoek op kenteken of omschrijving...").upper()
        sorteer_optie = inv_col2.selectbox("Sorteren op", options=["ID Nummer (Oplopend)", "ID Nummer (Aflopend)", "Verwachte Winst (Hoog naar laag)", "Kilometerstand (Laag naar hoog)", "APK Datum"])
        
        if zoekterm: 
            verwerkte_autos = [x for x in verwerkte_autos if zoekterm in x["kenteken"] or zoekterm in (x["naam"] or "").upper()]
        
        if "Aflopend" in sorteer_optie: verwerkte_autos.reverse()
        elif "Winst" in sorteer_optie: verwerkte_autos = sorted(verwerkte_autos, key=lambda x: x["winst"], reverse=True)
        elif "Kilometerstand" in sorteer_optie: verwerkte_autos = sorted(verwerkte_autos, key=lambda x: x["km_stand"])
        elif "APK" in sorteer_optie: verwerkte_autos = sorted(verwerkte_autos, key=lambda x: x["apk_datum"] if x["apk_datum"] else "9999-12-31")

        try:
            df = pd.DataFrame(verwerkte_autos).drop(columns=['afbeelding'])
            towrite = io.BytesIO()
            df.to_excel(towrite, index=False, engine='openpyxl')
            towrite.seek(0)
            inv_col3.download_button(label="📊 Excel Export", data=towrite, file_name="inventaris.xlsx", use_container_width=True)
        except: pass

        if not verwerkte_autos:
            st.info("Geen auto's gevonden.")
        else:
            for auto in verwerkte_autos:
                status_icoon = "🟢" if auto["status"] == "In voorraad" else "🟡" if auto["status"] == "Gereserveerd" else "🔴"
                apk_waarschuwing = ""
                try:
                    dagen = (datetime.strptime(auto["apk_datum"], "%Y-%m-%d").date() - datetime.today().date()).days
                    if auto["status"] != "Verkocht":
                        if 0 <= dagen <= 30: apk_waarschuwing = " ⚠️ (APK bijna verlopen!)"
                        elif dagen < 0: apk_waarschuwing = " 🚨 (APK VERLOPEN!)"
                except: pass

                with st.expander(f"{status_icoon} [{auto['status']}] {auto['naam'] or 'Onbekend'} ({auto['kenteken']}) - € {formatteer_euro_nl(auto['verkoopprijs'])}{apk_waarschuwing}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        if auto["afbeelding"]:
                            alle_fotos = auto["afbeelding"].split("||")
                            foto_cols = st.columns(min(len(alle_fotos), 3))
                            for idx, f_data in enumerate(alle_fotos):
                                with foto_cols[idx % min(len(alle_fotos), 3)]:
                                    try: 
                                        st.markdown(
                                            f"""
                                            <div style="width:100%; aspect-ratio: 4/3; overflow:hidden; border-radius:8px; background-color: transparent; border: 1px solid rgba(255,255,255,0.1); margin-bottom:10px; display:flex; align-items:center; justify-content:center;">
                                                <img src="data:image/jpeg;base64,{f_data}" style="max-width:100%; max-height:100%; object-fit:contain;">
                                            </div>
                                            """, 
                                            unsafe_allow_html=True
                                        )
                                    except: 
                                        st.error("Fout foto")
                        else: 
                            st.info("Geen afbeelding beschikbaar.")

                    with c2:
                        st.write(f"**Kilometerstand:** {auto['km_stand']:,} km".replace(",", "."))
                        st.write(f"**Brandstof:** {auto['brandstof']} | **Bouwjaar:** {auto['bouwjaar'] if auto['bouwjaar'] > 0 else 'Onbekend'}")
                        st.write(f"**Kleur:** {auto['kleur']} | **Cataloguswaarde:** € {formatteer_euro_nl(auto['cataloguswaarde'])}")
                        st.write(f"**Transmissie:** {auto['transmissie']} | **APK Datum:** {formatteer_datum_nl(auto['apk_datum'])}")
                        st.markdown("---")
                        st.write(f"**Inkoopprijs:** € {formatteer_euro_nl(auto['inkoopprijs'])} | **Extra kosten:** € {formatteer_euro_nl(auto['extra_kosten'])}")
                        st.write(f"**Marge / Winst:** € {formatteer_euro_nl(auto['winst'])}")
                        
                        b_edit, b_del = st.columns(2)
                        if b_edit.button("✏️ Aanpassen", key=f"ed_{auto['id']}", use_container_width=True):
                            bewerk_auto_dialog(auto["id"], auto["kenteken"], auto["km_stand"], auto["inkoopprijs"], auto["verkoopprijs"], auto["apk_datum"], auto["extra_kosten"], auto["afbeelding"], auto["naam"], auto["transmissie"], auto["status"], auto["brandstof"], auto["bouwjaar"], auto["kleur"], auto["cataloguswaarde"])
                        if b_del.button("🗑️ Verwijderen", key=f"dl_{auto['id']}", use_container_width=True):
                            with sqlite3.connect(DB_NAME) as conn:
                                cursor = conn.cursor()
                                cursor.execute("DELETE FROM voorraad WHERE id=?", (auto["id"],))
                                conn.commit()
                            st.rerun()
                        
                        st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
                        if st.button("📄 Koopcontract / Factuur", key=f"contract_{auto['id']}", type="secondary", use_container_width=True):
                            genereer_contract_dialog(auto["id"], auto["naam"], auto["kenteken"], auto["km_stand"], auto["verkoopprijs"], auto["apk_datum"])


elif menu_optie == "💰 Financieel Overzicht":
    st.title("💰 Financieel Overzicht & Budget")
    
    st.markdown("### ⚙️ Budget Instellingen")
    nieuw_budget = st.number_input("Stel je totale startbudget / werkkapitaal in (€):", value=float(st.session_state["startbudget"]), step=500.0)
    if nieuw_budget != st.session_state["startbudget"]:
        st.session_state["startbudget"] = nieuw_budget
        st.rerun()
        
    st.markdown("---")
    st.markdown("### 📊 Balans Overzicht")
    
    col_f1, col_f2, col_f3 = st.columns(3)
    col_f1.metric("Totale Startkapitaal", f"€ {formatteer_euro_nl(st.session_state['startbudget'])}")
    col_f2.metric("Vastgelegd in Voorraad", f"€ {formatteer_euro_nl(totale_voorraadwaarde)}")
    
    if actueel_vrij_budget < 0:
        col_f3.metric("Besteedbaar Cashgeld", f"€ {formatteer_euro_nl(actueel_vrij_budget)}", "Negatieve kasstroom!", delta_color="inverse")
    else:
        col_f3.metric("Besteedbaar Cashgeld (Ruimte voor inkoop)", f"€ {formatteer_euro_nl(actueel_vrij_budget)}")

    st.markdown("---")
    st.markdown("### 📊 Rendement")
    st.metric("Gerealiseerde Netto Winst (Verkochte auto's)", f"€ {formatteer_euro_nl(gerealiseerde_winst)}")

elif menu_optie == "📅 Agenda & Notities":
    st.title("📅 Agenda & Notities")
    
    try:
        from streamlit_calendar import calendar
    except ImportError:
        st.error("Installeer eerst de kalender-module via je requirements.txt: streamlit-calendar")
        st.stop()

    @st.dialog("📌 Nieuwe afspraak / notitie toevoegen")
    def nieuwe_afspraak_dialog(gekozen_datum_str):
        with st.form("agenda_toevoeg_form", clear_on_submit=True):
            # Hier is formatteer_datum_nl toegepast voor de juiste NL weergave:
            st.write(f"**Geselecteerde datum:** {formatteer_datum_nl(gekozen_datum_str)}")
            hele_dag = st.checkbox("📅 Deze afspraak duurt de gehele dag")
            
            tijd_col1, tijd_col2 = st.columns(2)
            if not hele_dag:
                ag_tijd_van = tijd_col1.time_input("Begintijd", value=datetime.strptime("10:00", "%H:%M").time())
                ag_tijd_tot = tijd_col2.time_input("Eindtijd", value=datetime.strptime("11:00", "%H:%M").time())
            
            ag_titel = st.text_input("Titel (bijv. Proefrit Golf, APK Keuring)")
            ag_notitie = st.text_area("Aanvullende informatie / opmerkingen")
            ag_submit = st.form_submit_button("💾 Opslaan in Agenda", type="primary", use_container_width=True)
            
        if ag_submit and ag_titel.strip():
            if hele_dag:
                opslag_datum = str(gekozen_datum_str)
            else:
                start_volledig = f"{gekozen_datum_str}T{ag_tijd_van.strftime('%H:%M:%S')}"
                end_volledig = f"{gekozen_datum_str}T{ag_tijd_tot.strftime('%H:%M:%S')}"
                opslag_datum = f"{start_volledig}||{end_volledig}"
            
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO agenda (datum, titel, notitie, status)
                    VALUES (?, ?, ?, 'Open')
                """, (opslag_datum, ag_titel.strip(), ag_notitie.strip()))
                conn.commit()
            st.toast("⚡ Afspraak succesvol toegevoegd!", icon="✅")
            st.rerun()


    @st.dialog("🔍 Afspraak Beheren")
    def bekijk_afspraak_dialog(event_id, titel_ruw, start_veld, eind_veld, notitie_veld, status_veld):
        bewerk_modus_key = f"edit_mode_{event_id}"
        if bewerk_modus_key not in st.session_state:
            st.session_state[bewerk_modus_key] = False

        is_voorheen_hele_dag = "T" not in str(start_veld)
        pure_datum_huidig = start_veld.split("T")[0] if "T" in str(start_veld) else start_veld
        
        try: standaard_datum = datetime.strptime(pure_datum_huidig, "%Y-%m-%d").date()
        except: standaard_datum = datetime.today().date()

        try:
            huidig_van = datetime.strptime(start_veld.split("T")[1][:5], "%H:%M").time() if "T" in str(start_veld) else datetime.strptime("10:00", "%H:%M").time()
            huidig_tot = datetime.strptime(eind_veld.split("T")[1][:5], "%H:%M").time() if "T" in str(eind_veld) else datetime.strptime("11:00", "%H:%M").time()
        except:
            huidig_van = datetime.strptime("10:00", "%H:%M").time()
            huidig_tot = datetime.strptime("11:00", "%H:%M").time()

        pure_titel_origineel = titel_ruw.replace("[Open] ", "").replace("[Voltooid] ", "")

        if not st.session_state[bewerk_modus_key]:
            st.markdown(f"### **{pure_titel_origineel}**")
            # Zorg dat deze regel de formatteer_datum_nl functie gebruikt:
            st.write(f"📅 **Datum:** {formatteer_datum_nl(pure_datum_huidig)}")

            
            if not is_voorheen_hele_dag:
                st.write(f"⏱️ **Tijd:** {huidig_van.strftime('%H:%M')} tot {huidig_tot.strftime('%H:%M')} uur")
            else:
                st.write("📅 **Tijd:** Gehele dag")
                
            st.write(f"📊 **Status:** {status_veld}")
            if notitie_veld:
                st.write(f"📝 **Opmerkingen:**  \n{notitie_veld}")
                
            st.markdown("---")
            col_b1, col_b2, col_b3 = st.columns(3)
            
            if status_veld == "Open":
                if col_b1.button("✅ Voltooid", key=f"btn_done_{event_id}", type="primary", use_container_width=True):
                    with sqlite3.connect(DB_NAME) as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE agenda SET status='Voltooid' WHERE id=?", (event_id,))
                        conn.commit()
                    st.rerun()
            else:
                if col_b1.button("🔄 Heropenen", key=f"btn_re_{event_id}", use_container_width=True):
                    with sqlite3.connect(DB_NAME) as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE agenda SET status='Open' WHERE id=?", (event_id,))
                        conn.commit()
                    st.rerun()
            
            if col_b2.button("✏️ Bewerken", key=f"btn_edit_act_{event_id}", use_container_width=True):
                st.session_state[bewerk_modus_key] = True
                st.rerun()
                    
            if col_b3.button("🗑️ Wissen", key=f"btn_del_{event_id}", type="secondary", use_container_width=True):
                with sqlite3.connect(DB_NAME) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM agenda WHERE id=?", (event_id,))
                    conn.commit()
                st.rerun()
        else:
            st.markdown("### ✏️ Afspraak Wijzigen")
            edit_datum = st.date_input("Pas Datum aan", value=standaard_datum, key=f"edit_dat_{event_id}")
            edit_hele_dag = st.checkbox("📅 Deze afspraak duurt de gehele dag", value=is_voorheen_hele_dag, key=f"edit_hd_{event_id}")
            
            tijd_edit_col1, tijd_edit_col2 = st.columns(2)
            if not edit_hele_dag:
                edit_tijd_van = tijd_edit_col1.time_input("Pas Begintijd aan", value=huidig_van, key=f"edit_v_{event_id}")
                edit_tijd_tot = tijd_edit_col2.time_input("Pas Eindtijd aan", value=huidig_tot, key=f"edit_t_{event_id}")
            
            edit_titel = st.text_input("Pas Titel aan", value=pure_titel_origineel, key=f"edit_ttl_{event_id}")
            edit_notitie = st.text_area("Pas Aanvullende informatie aan", value=notitie_veld if notitie_veld else "", key=f"edit_not_{event_id}")
            
            st.markdown("---")
            col_save1, col_save2 = st.columns(2)
            
            if col_save1.button("💾 Wijzigingen Opslaan", type="primary", use_container_width=True, key=f"btn_save_{event_id}"):
                if edit_titel.strip():
                    if edit_hele_dag:
                        nieuw_datum_format = str(edit_datum)
                    else:
                        nieuw_datum_format = f"{edit_datum}T{edit_tijd_van.strftime('%H:%M:%S')}||{edit_datum}T{edit_tijd_tot.strftime('%H:%M:%S')}"
                    
                    with sqlite3.connect(DB_NAME) as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE agenda 
                            SET datum=?, titel=?, notitie=? 
                            WHERE id=?
                        """, (nieuw_datum_format, edit_titel.strip(), edit_notitie.strip(), event_id))
                        conn.commit()
                    st.session_state[bewerk_modus_key] = False
                    st.rerun()
                    
            if col_save2.button("❌ Annuleren", use_container_width=True, key=f"btn_can_{event_id}"):
                st.session_state[bewerk_modus_key] = False
                st.rerun()

    st.markdown("""
        <style>
        .fc .fc-toolbar { display: flex !important; flex-direction: row !important; flex-wrap: wrap !important; gap: 6px !important; justify-content: space-between !important; margin-bottom: 15px !important; }
        .fc .fc-toolbar-title { font-size: 1.3rem !important; color: white !important; }
        .fc .fc-button { padding: 6px 10px !important; font-size: 0.9rem !important; }
        .fc .fc-daygrid-day-number { font-size: 0.95rem !important; font-weight: bold !important; color: white !important; }
        .fc-daygrid-event { font-size: 0.8rem !important; padding: 3px !important; border-radius: 4px !important; }
        </style>
    """, unsafe_allow_html=True)

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, datum, titel, notitie, status FROM agenda")
        notities = cursor.fetchall()
    
    calendar_events = []
    for item in notities:
        n_id, n_datum_veld, n_titel, n_notitie, n_status = item
        if "||" in str(n_datum_veld):
            start_tijd, eind_tijd = n_datum_veld.split("||")
            is_hele_dag = False
        else:
            start_tijd = n_datum_veld
            eind_tijd = n_datum_veld
            is_hele_dag = True
        
        kleur = "#28a745" if n_status == "Voltooid" else "#ff4b4b"
        calendar_events.append({
            "id": str(n_id), "title": f"[{n_status}] {n_titel}", "start": start_tijd, "end": eind_tijd,
            "backgroundColor": kleur, "borderColor": kleur, "allDay": is_hele_dag,
            "extendedProps": {"notitie": n_notitie, "status": n_status, "start_tijd": start_tijd, "eind_tijd": eind_tijd}
        })
        
    calendar_options = {
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,timeGridWeek,timeGridDay"},
        "initialView": "dayGridMonth", "locale": "nl", "timeZone": "local", "selectable": False, "height": "auto", "contentHeight": 550,
        "buttonText": {"today": "vandaag", "month": "maand", "week": "week", "day": "dag"},
        "slotMinTime": "07:00:00", "slotMaxTime": "21:00:00"
    }
    
    custom_css = """
        .fc-theme-standard td, .fc-theme-standard th { border: 1px solid rgba(255,255,255,0.1) !important; }
        .fc .fc-button-primary { background-color: #1e1e24 !important; border: 1px solid rgba(255,255,255,0.2) !important; }
        .fc .fc-button-primary:hover { background-color: rgb(255, 75, 75) !important; }
        .fc-theme-standard .fc-scrollgrid { border: 1px solid rgba(255,255,255,0.1) !important; }
    """
    
    state = calendar(events=calendar_events, options=calendar_options, custom_css=custom_css, key="agenda_volledige_breedte")
    
    if state.get("eventClick"):
        ev = state["eventClick"]["event"]
        props = ev.get("extendedProps", {})
        bekijk_afspraak_dialog(event_id=ev["id"], titel_ruw=ev["title"], start_veld=props.get("start_tijd"), eind_veld=props.get("eind_tijd"), notitie_veld=props.get("notitie"), status_veld=props.get("status"))
    elif state.get("dateClick"):
        ruwe_datum_str = state["dateClick"]["date"]
        try:
            if "T" in ruwe_datum_str:
                datum_deel, tijd_deel = ruwe_datum_str.split("T")
                pure_dt = datetime.strptime(datum_deel, "%Y-%m-%d")
                uurs_check = int(tijd_deel.split(":")[0])
                if uurs_check >= 20:
                    from datetime import timedelta
                    pure_dt = pure_dt + timedelta(days=1)
                puur_datum = pure_dt.strftime("%Y-%m-%d")
            else:
                puur_datum = ruwe_datum_str.split("Z")[0]
        except:
            puur_datum = ruwe_datum_str.split("T")[0]
        nieuwe_afspraak_dialog(puur_datum)

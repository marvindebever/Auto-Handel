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
                status TEXT DEFAULT 'In voorraad'
            )
        """)
        cursor.execute("PRAGMA table_info(voorraad)")
        bestaande_kolommen = [k[1] for k in cursor.fetchall()]
        if "status" not in bestaande_kolommen:
            cursor.execute("ALTER TABLE voorraad ADD COLUMN status TEXT DEFAULT 'In voorraad'")
            
        # ZET DIT ERONDER: Maakt automatisch de agenda-tabel aan
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
        
        /* SCHONE INDELING VOOR DE DROPZONE */
        .stSidebar [data-testid="stFileUploadDropzone"],
        .stSidebar div[data-testid="stFileUploadDropzone"] > div,
        .stSidebar .stFileUploader section {{
            background-color: transparent !important;
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0px !important;
        }}
        
        /* MAAK DE INTERNAL UPLOAD KNOP VISUEEL SOWIESO GELIJK AAN DE EXPORT KNOP */
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
    
# --- ROBUUSTE RDW KOPPELING (GEFIXT) ---
def overheid_rdw_lookup_krachtig(kenteken_str):
    """Haalt voertuiggegevens rechtstreeks op uit het openbare RDW-register via de directe URI structure."""
    # RDW eist ALTIJD hoofdletters en GEEN streepjes in de API-aanroep
    schoon = kenteken_str.replace("-", "").upper().strip()
    if not schoon:
        return None
    
    # HIER GING HET MIS: De URL is nu weer hersteld naar het officiële opendata RDW endpoint
    # Dit omzeilt de Tyler/Socrata HTML-foutpagina's bij anonieme queries.
    url = f"https://opendata.rdw.nl/resource/m9d7-ebf2.json?kenteken={schoon}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=8)
        
        if res.status_code == 200:
            # Controleer of we daadwerkelijk data hebben gekregen
            if "application/json" not in res.headers.get("Content-Type", ""):
                return {"fout": "RDW stuurde een onverwacht antwoordformaat (HTML). Probeer het over een moment opnieuw."}
                
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                # Pakt expliciet het eerste voertuig-object [0] uit de lijst
                voertuig = data[0]  
                
                merk = voertuig.get("merk", "").title()
                model = voertuig.get("handelsbenaming", "").title()
                volledige_naam = f"{merk} {model}".strip()
                
                apk_verval = voertuig.get("vervaldatum_apk", "")
                apk_formatted = datetime.today().date()
                if apk_verval:
                    try: 
                        # RDW datums converteren van 'YYYYMMDD' naar een Date-object
                        apk_formatted = datetime.strptime(str(apk_verval), "%Y%m%d").date()
                    except: 
                        pass
                        
                return {
                    "naam": volledige_naam if volledige_naam else "Onbekend voertuig",
                    "apk": apk_formatted,
                    "fout": None
                }
            else:
                return {"fout": "Kenteken niet gevonden in het openbare RDW-register."}
        elif res.status_code == 403:
            return {"fout": "Toegang geweigerd (403) door RDW. Server blokkeert mogelijk tijdelijk je IP."}
        elif res.status_code == 429:
            return {"fout": "Te veel aanvragen achter elkaar (429). Wacht 10 seconden."}
        else:
            return {"fout": f"RDW Server gaf een foutmelding. Statuscode: {res.status_code}."}
            
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

# --- DATA IMPORT & EXPORT FUNCTIES VOOR BACKUP (GEFIXT) ---
def exporteer_database_naar_json():
    """Haalt alle data uit de SQLite database en zet het om naar een downloadbare JSON-tekst."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row  # Zorgt ervoor dat we kolommen op naam kunnen uitlezen
        cursor = conn.cursor()
        cursor.execute("SELECT kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, naam, transmissie, status FROM voorraad")
        rijen = cursor.fetchall()
        # GEFIXT: rrij is veranderd naar rij zodat de variabele correct matcht!
        data_lijst = [dict(rij) for rij in rijen]
        
    import json
    return json.dumps(data_lijst, indent=4)


def importeer_json_naar_database(json_data):
    """Wist de huidige tabel en voegt alle voertuigen uit het JSON-bestand opnieuw toe."""
    import json
    try:
        voertuigen = json.loads(json_data)
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            # Maak de huidige voorraad leeg om dubbele invoer te voorkomen
            cursor.execute("DELETE FROM voorraad")
            # Voeg elk voertuig netjes toe
            for v in voertuigen:
                cursor.execute("""
                    INSERT INTO voorraad (kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, naam, transmissie, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (v.get("kenteken"), v.get("km_stand"), v.get("inkoopprijs"), v.get("verkoopprijs"), v.get("apk_datum"), v.get("extra_kosten"), v.get("afbeelding"), v.get("naam"), v.get("transmissie"), v.get("status")))
            conn.commit()
        return True
    except Exception as e:
        st.sidebar.error(f"Import mislukt: {str(e)}")
        return False

# --- DIALOGS (BEWERKEN POP-UP - NU MET WIS-FOTOKNOP) ---
@st.dialog("✏️ Auto Gegevens Bewerken")
def bewerk_auto_dialog(actie_id, ktk, km, inkoop, verkoop, apk, kosten, foto_huidig, auto_naam, trans_huidig, status_huidig):
    try: standaard_datum = datetime.strptime(apk, "%Y-%m-%d").date()
    except: standaard_datum = datetime.today().date()

    uploader_key = f"fotos_upload_{actie_id}"

    edit_naam = st.text_input("Pas Naam / Omschrijving aan", value=auto_naam if auto_naam else "")
    edit_ktk = st.text_input("Pas Kenteken aan", value=ktk)
    status_opties = ["In voorraad", "Gereserveerd", "Verkocht"]
    edit_status = st.selectbox("Status", options=status_opties, index=status_opties.index(status_huidig) if status_huidig in status_opties else 0)
    edit_km = st.text_input("Pas Kilometerstand aan", value=str(km))
    edit_apk = st.date_input("Pas APK Datum aan", value=standaard_datum)
    trans_opties = ["Handgeschakeld", "Automaat"]
    edit_trans = st.selectbox("Pas Transmissie aan", options=trans_opties, index=trans_opties.index(trans_huidig) if trans_huidig in trans_opties else 0)
    edit_inkoop = st.text_input("Pas Inkoopprijs aan", value=str(inkoop))
    edit_verkoop = st.text_input("Pas Verkoopprijs aan", value=str(verkoop))
    edit_kosten = st.text_input("Pas Extra kosten aan", value=str(kosten))
    
    # Toon de status van de huidige afbeeldingen
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
                    SET naam=?, kenteken=?, km_stand=?, apk_datum=?, transmissie=?, inkoopprijs=?, verkoopprijs=?, extra_kosten=?, afbeelding=?, status=? 
                    WHERE id=?
                """, (edit_naam, edit_ktk.upper().replace("-", "").strip(), naar_getal(edit_km, int), str(edit_apk), edit_trans, naar_getal(edit_inkoop), naar_getal(edit_verkoop), naar_getal(edit_kosten), foto_opslaan, edit_status, actie_id))
                conn.commit()
            
            if uploader_key in st.session_state:
                del st.session_state[uploader_key]
                
            st.rerun()

# --- SIDEBAR NAVIGATIE, DATA CALCULATIE & BACKUP ---
with st.sidebar:
    st.title("⚙️ Navigatie")
    menu_optie = st.radio(
        "Kies een functie:",
        ["🆕 Nieuwe auto toevoegen", "📊 Actuele Status Dashboard", "🟢 Actuele Voorraad", "🔴 Verkochte Voertuigen", "📅 Agenda & Notities", "💰 Financieel Overzicht"]
    )

    
    st.markdown("---")
    st.subheader("💾 Backup & Herstel")
    
    # 1. EXPORT KNOP
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

    # 2. IMPORT INVOERVELD
    geimporteerd_bestand = st.file_uploader("📥 Importeer Data (Herstel)", type=["json"])
    if geimporteerd_bestand is not None:
        # Lees het geüploade bestand uit
        json_data = geimporteerd_bestand.getvalue().decode("utf-8")
        if st.button("🔄 Herstel database nu", type="primary", use_container_width=True):
            if importeer_json_naar_database(json_data):
                st.toast("⚡ Database succesvol hersteld!", icon="✅")
                st.rerun()

    st.markdown("---")
    if st.button("🚪 Uitloggen", use_container_width=True):
        st.session_state["ingelogd"] = False
        st.rerun()

# Financiële cijfers live en veilig laden
with sqlite3.connect(DB_NAME) as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT inkoopprijs, verkoopprijs, extra_kosten, status FROM voorraad")
    stat_rijen = cursor.fetchall()

autos_in_voorraad = [r for r in stat_rijen if r[3] != 'Verkocht']
autos_verkocht = [r for r in stat_rijen if r[3] == 'Verkocht']

totale_voorraadwaarde = sum(r[0] + r[2] for r in autos_in_voorraad)
totale_verwachte_winst = sum(r[1] - (r[0] + r[2]) for r in autos_in_voorraad)
gerealiseerde_winst = sum(r[1] - (r[0] + r[2]) for r in autos_verkocht)
# --- INTERFACE STRUCTUUR ---
if menu_optie == "🆕 Nieuwe auto toevoegen":
    st.title("🆕 Nieuwe auto toevoegen")
    
    # GEFIXT: vertical_alignment toegevoegd zodat het invoerveld en de knop onderaan gelijk uitlijnen
    rdw_col1, rdw_col2 = st.columns(2, vertical_alignment="bottom")
    rdw_kenteken = rdw_col1.text_input("Snel RDW via kenteken", placeholder="Bijv. 47-LV-JV").upper().replace("-", "")

    with rdw_col2:
        # GEFIXT: De oude handmatige st.markdown padding is hier nu weg!
        klik_rdw = st.button("🔍 RDW Gegevens Ophalen", use_container_width=True)

    if klik_rdw and rdw_kenteken:
        rdw_data = overheid_rdw_lookup_krachtig(rdw_kenteken)
        if rdw_data and rdw_data.get("fout") is None:
            st.session_state["rdw_naam"] = rdw_data["naam"]
            st.session_state["rdw_apk"] = rdw_data["apk"]
            st.session_state["rdw_ktk"] = rdw_kenteken
            st.toast("⚡ RDW succesvol geladen!", icon="✅")
        elif rdw_data and rdw_data.get("fout"): 
            st.error(rdw_data["fout"])

    with st.form("auto_form", clear_on_submit=False):
        naam = st.text_input("Naam / Omschrijving", value=st.session_state.get("rdw_naam", ""))
        kenteken = st.text_input("Kenteken (Verplicht)", value=st.session_state.get("rdw_ktk", ""))
        km_stand_str = st.text_input("Kilometerstand", value="0")
        apk_datum = st.date_input("APK Datum", value=st.session_state.get("rdw_apk", datetime.today().date()))
        transmissie = st.selectbox("Transmissie", options=["Handgeschakeld", "Automaat"])
        status_invoer = st.selectbox("Status bij instroom", options=["In voorraad", "Gereserveerd"])
        inkoopprijs_str = st.text_input("Inkoopprijs (€)", value="0.00")
        verkoopprijs_str = st.text_input("Verkoopprijs (€)", value="0.00")
        extra_kosten_str = st.text_input("Extra kosten (€)", value="0.00")
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
                INSERT INTO voorraad (naam, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, transmissie, status) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (naam, kenteken.upper().replace("-", "").strip(), naar_getal(km_stand_str, int), naar_getal(inkoopprijs_str), naar_getal(verkoopprijs_str), str(apk_datum), naar_getal(extra_kosten_str), foto_data, transmissie, status_invoer))
            conn.commit()
            
        st.session_state["rdw_naam"] = ""
        st.session_state["rdw_ktk"] = ""
        if "rdw_apk" in st.session_state: del st.session_state["rdw_apk"]
        st.success("Auto succesvol toegevoegd!")
        st.rerun()

elif menu_optie == "📊 Actuele Status Dashboard":
    st.title("📊 Actuele Status Dashboard")
    st.subheader("Financiële kerncijfers van de huidige voorraad")
    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    stat_col1.metric(label="Huidige Voorraad", value=f"{len(autos_in_voorraad)} stuks")
    stat_col2.metric(label="Investeringswaarde", value=f"€ {formatteer_euro_nl(totale_voorraadwaarde)}")
    stat_col3.metric(label="Verwachte Winst (Voorraad)", value=f"€ {formatteer_euro_nl(totale_verwachte_winst)}")
    stat_col4.metric(label="Gerealiseerde Winst (Verkocht)", value=f"€ {formatteer_euro_nl(gerealiseerde_winst)}")
elif menu_optie in ["🟢 Actuele Voorraad", "🔴 Verkochte Voertuigen"]:
    st.title(menu_optie)
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, naam, transmissie, status FROM voorraad")
        alle_autos = cursor.fetchall()

    verwerkte_autos = []
    if alle_autos:
        for auto in alle_autos:
            winst = auto[4] - (auto[3] + auto[6])
            verwerkte_autos.append({
                "id": auto[0], "kenteken": auto[1], "km_stand": auto[2], "inkoopprijs": auto[3], "verkoopprijs": auto[4],
                "apk_datum": auto[5], "extra_kosten": auto[6], "afbeelding": auto[7], "naam": auto[8], "transmissie": auto[9], 
                "status": auto[10], "winst": winst
            })

        if menu_optie == "🟢 Actuele Voorraad":
            verwerkte_autos = [x for x in verwerkte_autos if x["status"] != "Verkocht"]
        else:
            verwerkte_autos = [x for x in verwerkte_autos if x["status"] == "Verkocht"]

        st.markdown("### 🔍 Filters & Sortering")
        
        # GEFIXT: vertical_alignment toegevoegd voor de filterrij zodat Excel Export knop strak staat
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
            
            # GEFIXT: De handmatige st.markdown padding-top is hier nu weg!
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
                        st.write(f"**Transmissie:** {auto['transmissie']}")
                        st.write(f"**APK Datum:** {formatteer_datum_nl(auto['apk_datum'])}")
                        st.write(f"**Inkoopprijs:** € {formatteer_euro_nl(auto['inkoopprijs'])}")
                        st.write(f"**Extra kosten:** € {formatteer_euro_nl(auto['extra_kosten'])}")
                        st.write(f"**Marge / Winst:** € {formatteer_euro_nl(auto['winst'])}")
                        
                        b_edit, b_del = st.columns(2)
                        if b_edit.button("✏️ Aanpassen", key=f"ed_{auto['id']}", use_container_width=True):
                            bewerk_auto_dialog(auto["id"], auto["kenteken"], auto["km_stand"], auto["inkoopprijs"], auto["verkoopprijs"], auto["apk_datum"], auto["extra_kosten"], auto["afbeelding"], auto["naam"], auto["transmissie"], auto["status"])
                        if b_del.button("🗑️ Verwijderen", key=f"dl_{auto['id']}", use_container_width=True):
                            with sqlite3.connect(DB_NAME) as conn:
                                cursor = conn.cursor()
                                cursor.execute("DELETE FROM voorraad WHERE id=?", (auto["id"],))
                                conn.commit()
                            st.rerun()

elif menu_optie == "💰 Financieel Overzicht":
    st.title("💰 Financieel Overzicht")
    col_f1, col_f2 = st.columns(2)
    col_f1.metric("Totale Investering (Voorraad)", f"€ {formatteer_euro_nl(totale_voorraadwaarde)}")
    col_f2.metric("Gerealiseerde Netto Winst", f"€ {formatteer_euro_nl(gerealiseerde_winst)}")
# --- AGENDA & NOTITIES PAGINA INTERFACE ---
elif menu_optie == "📅 Agenda & Notities":
    st.title("📅 Agenda & Notities")
    
    col_ag1, col_ag2 = st.columns(2)
    
    with col_ag1:
        st.subheader("📌 Nieuwe notitie / afspraak")
        with st.form("agenda_form", clear_on_submit=True):
            ag_datum = st.date_input("Datum", value=datetime.today().date())
            ag_titel = st.text_input("Titel (bijv. Proefrit Golf, APK Keuring)")
            ag_notitie = st.text_area("Aanvullende informatie / opmerkingen")
            ag_submit = st.form_submit_button("Opslaan in Agenda")
            
        if ag_submit and ag_titel.strip():
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO agenda (datum, titel, notitie, status)
                    VALUES (?, ?, ?, 'Open')
                """, (str(ag_datum), ag_titel.strip(), ag_notitie.strip()))
                conn.commit()
            st.toast("⚡ Notitie succesvol toegevoegd!", icon="✅")
            st.rerun()

    with col_ag2:
        st.subheader("📋 Overzicht")
        
        # Interactieve kalender om een specifieke dag te kiezen
        gekozen_datum = st.date_input("📅 Filter op datum (Kalender):", value=datetime.today().date())
        
        # Filter opties voor de status en de datum
        col_f_status, col_f_date = st.columns([2, 1])
        status_filter = col_f_status.radio("Filter op status:", ["Openstaande taken/afspraken", "Voltooide taken", "Alles"], horizontal=True)
        
        # Sessie-state aanmaken voor de datumfilter-modus
        if "datum_filter_actief" not in st.session_state:
            st.session_state["datum_filter_actief"] = True
            
        if col_f_date.button("📅 Toon Alle Dagen", use_container_width=True):
            st.session_state["datum_filter_actief"] = False
        
        # Als de gebruiker een nieuwe datum kiest, zetten we de filter automatisch weer aan
        if "laatste_datum" not in st.session_state or st.session_state["laatste_datum"] != gekozen_datum:
            st.session_state["laatste_datum"] = gekozen_datum
            st.session_state["datum_filter_actief"] = True

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            
            # Basis query opbouwen
            query = "SELECT id, datum, titel, notitie, status FROM agenda WHERE 1=1"
            parameters = []
            
            # 1. Filteren op Status
            if status_filter == "Openstaande taken/afspraken":
                query += " AND status='Open'"
            elif status_filter == "Voltooide taken":
                query += " AND status='Voltooid'"
                
            # 2. Filteren op de gekozen kalenderdatum (indien actief)
            if st.session_state["datum_filter_actief"]:
                query += " AND datum=?"
                parameters.append(str(gekozen_datum))
                st.caption(f"*Toont resultaten voor:* **{formatteer_datum_nl(str(gekozen_datum))}**")
            else:
                st.caption("*Toont resultaten voor:* **Alle dagen**")
                
            # Sortering bepalen
            if status_filter == "Voltooide taken":
                query += " ORDER BY datum DESC"
            else:
                query += " ORDER BY datum ASC"
                
            cursor.execute(query, parameters)
            notities = cursor.fetchall()
            
        if not notities:
            st.info("Geen notities of afspraken gevonden voor deze selectie.")
        else:
            for item in notities:
                n_id, n_datum, n_titel, n_notitie, n_status = item
                status_kleur = "⏳" if n_status == "Open" else "✅"
                
                # Als we alle dagen tonen, zetten we de datum ook in de titel van de expander
                expander_titel = f"{status_kleur} [{formatteer_datum_nl(n_datum)}] - {n_titel}"
                
                with st.expander(expander_titel):
                    if n_notitie:
                        st.write(f"**Details:**  \n{n_notitie}")
                    else:
                        st.write("*Geen aanvullende details.*")
                    
                    st.markdown("---")
                    btn_col1, btn_col2 = st.columns(2)
                    
                    if n_status == "Open":
                        if btn_col1.button("✅ Vink af als voltooid", key=f"comp_{n_id}", use_container_width=True):
                            with sqlite3.connect(DB_NAME) as conn:
                                cursor = conn.cursor()
                                cursor.execute("UPDATE agenda SET status='Voltooid' WHERE id=?", (n_id,))
                                conn.commit()
                            st.rerun()
                    else:
                        if btn_col1.button("🔄 Heropen taak", key=f"reopen_{n_id}", use_container_width=True):
                            with sqlite3.connect(DB_NAME) as conn:
                                cursor = conn.cursor()
                                cursor.execute("UPDATE agenda SET status='Open' WHERE id=?", (n_id,))
                                conn.commit()
                            st.rerun()
                            
                    if btn_col2.button("🗑️ Verwijder definitief", key=f"del_ag_{n_id}", use_container_width=True):
                        with sqlite3.connect(DB_NAME) as conn:
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM agenda WHERE id=?", (n_id,))
                            conn.commit()
                        st.rerun()

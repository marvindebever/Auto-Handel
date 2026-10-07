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
                brandstof TEXT, vermogen INTEGER, kleur TEXT, cataloguswaarde REAL
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
            background-color: transparent !important; background: transparent !important;
            border: none !important; box-shadow: none !important; padding: 0px !important;
        }}
        
        .stSidebar [data-testid="stFileUploadDropzone"] button {{
            width: 100% !important; min-width: 100% !important; background-color: transparent !important;
            color: white !important; border: 1px solid rgba(255, 255, 255, 0.2) !important;
            border-radius: 8px !important; padding: 0.5rem 1rem !important; height: auto !important; font-size: 1rem !important;
        }}
        .stSidebar [data-testid="stFileUploadDropzone"] button:hover {{
            border-color: rgb(255, 75, 75) !important; color: rgb(255, 75, 75) !important;
        }}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)

zet_achtergrond("logo.png")

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
    
def overheid_rdw_lookup_krachtig(kenteken_str):
    schoon = kenteken_str.replace("-", "").upper().strip()
    if not schoon:
        return None
    url = f"https://opendata.rdw.nl/resource/m9d7-ebf2.json?kenteken={schoon}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    try:
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            if "application/json" not in res.headers.get("Content-Type", ""):
                return {"fout": "RDW stuurde een onverwacht antwoordformaat (HTML). Probeer het over een moment opnieuw."}
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                voertuig = data[0]  
                merk = voertuig.get("merk", "").title()
                model = voertuig.get("handelsbenaming", "").title()
                volledige_naam = f"{merk} {model}".strip()
                kleur = voertuig.get("eerste_kleur", "Onbekend").title()
                cataloguswaarde = naar_getal(voertuig.get("catalogusprijs", 0.0))
                brandstof = voertuig.get("brandstof_omschrijving", "Benzine").title() 
                kw = naar_getal(voertuig.get("netto_maximum_vermogen", 0))
                pk = int(kw * 1.362) if kw > 0 else 0
                apk_verval = voertuig.get("vervaldatum_apk", "")
                apk_formatted = datetime.today().date()
                if apk_verval:
                    try: apk_formatted = datetime.strptime(str(apk_verval), "%Y%m%d").date()
                    except: pass
                return {"naam": volledige_naam, "apk": apk_formatted, "brandstof": brandstof, "vermogen": pk, "kleur": kleur, "cataloguswaarde": cataloguswaarde, "fout": None}
            else:
                return {"fout": "Kenteken niet gevonden in het openbare RDW-register."}
        elif res.status_code == 403:
            return {"fout": "Toegang geweigerd (403) door RDW."}
        elif res.status_code == 429:
            return {"fout": "Te veel aanvragen (429)."}
        else:
            return {"fout": f"RDW Server fout. Status: {res.status_code}."}
    except Exception as e:
        return {"fout": f"Fout bij ophalen RDW-gegevens: {str(e)}"}

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

def exporteer_database_naar_json():
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row  
        cursor = conn.cursor()
        cursor.execute("SELECT kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, naam, transmissie, status, brandstof, vermogen, kleur, cataloguswaarde FROM voorraad")
        voorraad_data = [dict(rij) for r in cursor.fetchall()]
        cursor.execute("SELECT datum, titel, notitie, status FROM agenda")
        agenda_data = [dict(rij) for r in cursor.fetchall()]
        actueel_startbudget = st.session_state.get("startbudget", 10000.0)
        return {"startbudget": actueel_startbudget, "voorraad": voorraad_data, "agenda": agenda_data}

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
                    INSERT INTO voorraad (kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, naam, transmissie, status, brandstof, vermogen, kleur, cataloguswaarde)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (v.get("kenteken"), v.get("km_stand"), v.get("inkoopprijs"), v.get("verkoopprijs"), v.get("apk_datum"), v.get("extra_kosten"), v.get("afbeelding"), v.get("naam"), v.get("transmissie"), v.get("status"), v.get("brandstof"), v.get("vermogen"), v.get("kleur"), v.get("cataloguswaarde")))
            for a in afspraken:
                cursor.execute("INSERT INTO agenda (datum, titel, notitie, status) VALUES (?, ?, ?, ?)", (a.get("datum"), a.get("titel"), a.get("notitie"), a.get("status", "Open")))
            conn.commit()
        return True
    except Exception as e:
        return False

@st.dialog("✏️ Auto Gegevens Bewerken")
def bewerk_auto_dialog(actie_id, ktk, km, inkoop, verkoop, apk, kosten, foto_huidig, auto_naam, trans_huidig, status_huidig, brandstof_h, vermogen_h, kleur_h, cat_h):
    try: standaard_datum = datetime.strptime(apk, "%Y-%m-%d").date()
    except: standaard_datum = datetime.today().date()
    uploader_key = f"fotos_upload_{actie_id}"
    edit_naam = st.text_input("Pas Naam / Omschrijving aan", value=auto_naam if auto_naam else "")
    edit_ktk = st.text_input("Pas Kenteken aan", value=ktk)
    status_opties = ["In voorraad", "Gereserveerd", "Verkocht"]
    edit_status = st.selectbox("Status", options=status_opties, index=status_opties.index(status_huidig) if status_huidig in status_opties else 0)
    
    col1, col2 = st.columns(2)
    edit_km = col1.text_input("Pas Kilometerstand aan", value=str(km))
    edit_apk = col2.date_input("Pas APK Datum aan", value=standaard_datum)
    
    col3, col4 = st.columns(2)
    edit_brandstof = col3.text_input("Pas Brandstof aan", value=str(brandstof_h if brandstof_h else "Benzine"))
    edit_vermogen = col4.text_input("Pas Vermogen (PK) aan", value=str(vermogen_h if vermogen_h else 0))
    col5, col6 = st.columns(2)
    edit_kleur = col5.text_input("Pas Kleur aan", value=str(kleur_h if kleur_h else ""))
    edit_cat = col6.text_input("Pas Cataloguswaarde (€) aan", value=str(cat_h if cat_h else 0.0))
    trans_opties = ["Handgeschakeld", "Automaat"]
    edit_trans = st.selectbox("Pas Transmissie aan", options=trans_opties, index=trans_opties.index(trans_huidig) if trans_huidig in trans_opties else 0)
    
    col7, col8, col9 = st.columns(3)
    edit_inkoop = col7.text_input("Pas Inkoopprijs aan", value=str(inkoop))
    edit_verkoop = col8.text_input("Pas Verkoopprijs aan", value=str(verkoop))
    edit_kosten = col9.text_input("Pas Extra kosten aan", value=str(kosten))
    
    if st.button("💾 Wijzigingen Live Opslaan", type="primary", use_container_width=True):
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE voorraad SET naam=?, kenteken=?, km_stand=?, apk_datum=?, transmissie=?, inkoopprijs=?, verkoopprijs=?, extra_kosten=?, status=?, brandstof=?, vermogen=?, kleur=?, cataloguswaarde=? WHERE id=?
            """, (edit_naam, edit_ktk.upper().replace("-", "").strip(), naar_getal(edit_km, int), str(edit_apk), edit_trans, naar_getal(edit_inkoop), naar_getal(edit_verkoop), naar_getal(edit_kosten), edit_status, edit_brandstof, naar_getal(edit_vermogen, int), edit_kleur, naar_getal(edit_cat), actie_id))
            conn.commit()
        st.rerun()

@st.dialog("📄 Particuliere Koopovereenkomst Genereren")
def genereer_contract_dialog(auto_id, merk_model, kenteken, km, verkoop, apk):
    koper_naam = st.text_input("Naam Koper")
    if st.button("🔥 PDF Contract Downloaden", type="primary", use_container_width=True):
        st.success("Download gestart!")

with st.sidebar:
    st.title("⚙️ Navigatie")
    menu_optie = st.radio("Kies een functie:", ["🆕 Nieuwe auto toevoegen", "🟢 Actuele Voorraad", "🔴 Verkochte Voertuigen", "📅 Agenda & Notities", "📊 Actuele Status Dashboard", "💰 Financieel Overzicht"])

with sqlite3.connect(DB_NAME) as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT inkoopprijs, verkoopprijs, extra_kosten, status FROM voorraad")
    stat_rijen = cursor.fetchall()
autos_in_voorraad = [r for r in stat_rijen if r[3] != 'Verkocht']
autos_verkocht = [r for r in stat_rijen if r[3] == 'Verkocht']
totale_voorraadwaarde = sum(r[0] + r[2] for r in autos_in_voorraad)
gerealiseerde_winst = sum(r[1] - (r[0] + r[2]) for r in autos_verkocht)
if "startbudget" not in st.session_state: st.session_state["startbudget"] = 10000.0
actueel_vrij_budget = st.session_state["startbudget"] - totale_voorraadwaarde + gerealiseerde_winst

if menu_optie == "🆕 Nieuwe auto toevoegen":
    st.title("🆕 Nieuwe auto toevoegen")
    rdw_col1, rdw_col2 = st.columns(2, vertical_alignment="bottom")
    rdw_kenteken = rdw_col1.text_input("Snel RDW via kenteken", placeholder="Bijv. 47-LV-JV").upper().replace("-", "")
    klik_rdw = rdw_col2.button("🔍 RDW Gegevens Ophalen", use_container_width=True)
    if klik_rdw and rdw_kenteken:
        rdw_data = overheid_rdw_lookup_krachtig(rdw_kenteken)
        if rdw_data and rdw_data.get("fout") is None:
            st.session_state["rdw_naam"] = rdw_data["naam"]
            st.session_state["rdw_apk"] = rdw_data["apk"]
            st.session_state["rdw_brandstof"] = rdw_data["brandstof"]
            st.session_state["rdw_vermogen"] = rdw_data["vermogen"]
            st.session_state["rdw_kleur"] = rdw_data["kleur"]
            st.session_state["rdw_cataloguswaarde"] = rdw_data["cataloguswaarde"]
            st.session_state["rdw_ktk"] = rdw_kenteken
            st.rerun()
    with st.form("auto_form", clear_on_submit=False):
        naam = st.text_input("Naam / Omschrijving", value=st.session_state.get("rdw_naam", ""))
        kenteken = st.text_input("Kenteken (Verplicht)", value=st.session_state.get("rdw_ktk", ""))
        c_form1, c_form2 = st.columns(2)
        km_stand_str = c_form1.text_input("Kilometerstand", value="0")
        apk_datum = c_form2.date_input("APK Datum", value=st.session_state.get("rdw_apk", datetime.today().date()))
        c_form3, c_form4 = st.columns(2)
        brandstof_invoer = c_form3.text_input("Brandstof", value=st.session_state.get("rdw_brandstof", "Benzine"))
        vermogen_invoer = c_form4.text_input("Vermogen (PK)", value=str(st.session_state.get("rdw_vermogen", 0)))
        c_form5, c_form6 = st.columns(2)
        kleur_invoer = c_form5.text_input("Kleur", value=st.session_state.get("rdw_kleur", ""))
        cat_invoer = c_form6.text_input("Oorspronkelijke Cataloguswaarde (€)", value=str(st.session_state.get("rdw_cataloguswaarde", 0.0)))
        transmissie = st.selectbox("Transmissie", options=["Handgeschakeld", "Automaat"])
        status_invoer = st.selectbox("Status bij instroom", options=["In voorraad", "Gereserveerd"])
        c_form7, c_form8, c_form9 = st.columns(3)
        inkoopprijs_str = c_form7.text_input("Inkoopprijs (€)", value="0.00")
        verkoopprijs_str = c_form8.text_input("Verkoopprijs (€)", value="0.00")
        extra_kosten_str = c_form9.text_input("Extra kosten (€)", value="0.00")
        submit = st.form_submit_button("Voeg toe aan voorraad")
    if submit and kenteken.strip():
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO voorraad (naam, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, transmissie, status, brandstof, vermogen, kleur, cataloguswaarde) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (naam, kenteken.upper().replace("-", "").strip(), naar_getal(km_stand_str, int), naar_getal(inkoopprijs_str), naar_getal(verkoopprijs_str), str(apk_datum), naar_getal(extra_kosten_str), transmissie, status_invoer, brandstof_invoer, naar_getal(vermogen_invoer, int), kleur_invoer, naar_getal(cat_invoer)))
            conn.commit()
        st.rerun()

elif menu_optie in ["🟢 Actuele Voorraad", "🔴 Verkochte Voertuigen"]:
    st.title(menu_optie)
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, naam, transmissie, status, brandstof, vermogen, kleur, cataloguswaarde FROM voorraad")
        alle_autos = cursor.fetchall()
    verwerkte_autos = []
    for auto in alle_autos:
        winst = auto[4] - (auto[3] + auto[6])
        verwerkte_autos.append({"id": auto[0], "kenteken": auto[1], "km_stand": auto[2], "inkoopprijs": auto[3], "verkoopprijs": auto[4], "apk_datum": auto[5], "extra_kosten": auto[6], "afbeelding": auto[7], "naam": auto[8], "transmissie": auto[9], "status": auto[10], "brandstof": auto[11] if auto[11] else "Onbekend", "vermogen": auto[12] if auto[12] else 0, "kleur": auto[13] if auto[13] else "Onbekend", "cataloguswaarde": auto[14] if auto[14] else 0.0, "winst": winst})
    if menu_optie == "🟢 Actuele Voorraad": verwerkte_autos = [x for x in verwerkte_autos if x["status"] != "Verkocht"]
    else: verwerkte_autos = [x for x in verwerkte_autos if x["status"] == "Verkocht"]
    for auto in verwerkte_autos:
        with st.expander(f"{auto['naam']} ({auto['kenteken']})"):
            c1, c2 = st.columns(2)
            with c2:
                st.write(f"**Kilometerstand:** {auto['km_stand']:,} km")
                st.write(f"**Brandstof:** {auto['brandstof']} | **Vermogen:** {auto['vermogen']} PK")
                st.write(f"**Kleur:** {auto['kleur']} | **Cataloguswaarde:** € {formatteer_euro_nl(auto['cataloguswaarde'])}")
                if st.button("✏️ Aanpassen", key=f"ed_{auto['id']}"):
                    bewerk_auto_dialog(auto["id"], auto["kenteken"], auto["km_stand"], auto["inkoopprijs"], auto["verkoopprijs"], auto["apk_datum"], auto["extra_kosten"], auto["afbeelding"], auto["naam"], auto["transmissie"], auto["status"], auto["brandstof"], auto["vermogen"], auto["kleur"], auto["cataloguswaarde"])

else:
    st.write("Overige functionaliteiten geladen.")

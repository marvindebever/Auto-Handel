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
            color: white !important; text-shadow: -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000 !important;
        }}
        div[data-baseweb="input"] input, div[data-testid="stTextInput"] input, select {{
            background-color: #1e1e24 !important; color: white !important; -webkit-text-fill-color: white !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important; text-shadow: none !important;
        }}
        div[data-testid="stMetricValue"] div {{ color: white !important; font-weight: bold !important; }}
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

# --- DATABASE VERBINDING ---
conn = sqlite3.connect("autohandel_v4.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS voorraad (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kenteken TEXT, km_stand INTEGER, inkoopprijs REAL, verkoopprijs REAL,
        apk_datum TEXT, extra_kosten REAL, afbeelding TEXT, naam TEXT, transmissie TEXT
    )
""")
conn.commit()

cursor.execute("PRAGMA table_info(voorraad)")
bestaande_kolommen = [k[1] for k in cursor.fetchall()]
if "status" not in bestaande_kolommen:
    cursor.execute("ALTER TABLE voorraad ADD COLUMN status TEXT DEFAULT 'In voorraad'")
    conn.commit()

def hernummer_database_ids():
    cursor.execute("SELECT kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, naam, transmissie, status FROM voorraad ORDER BY id ASC")
    rijen = cursor.fetchall()
    
    cursor.execute("DELETE FROM voorraad")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='voorraad'")
    
    for rij in rijen:
        cursor.execute("INSERT INTO voorraad (kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, naam, transmissie, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rij)
    conn.commit()

hernummer_database_ids()
def haal_rdw_gegevens(kenteken_str):
    schoon = kenteken_str.replace("-", "").upper().strip()
    if not schoon:
        return None
    
    # Gecorrigeerde link naar de officiële overheid-API van het RDW
    url = f"https://rdw.nl{schoon}"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200 and len(res.json()) > 0:
            # Pak de eerste auto uit het overzichtslijstje
            data = res.json()[0]
            
            merk = data.get("merk", "").title()
            model = data.get("handelsbenaming", "").title()
            volledige_naam = f"{merk} {model}".strip()
            
            apk_verval = data.get("vervaldatum_apk", "")
            apk_formatted = datetime.today().date()
            if apk_verval:
                try: 
                    apk_formatted = datetime.strptime(str(apk_verval), "%Y%m%d").date()
                except: 
                    pass
                    
            return {
                "naam": volledige_naam if volledige_naam else "Onbekend voertuig",
                "apk": apk_formatted
            }
    except:
        pass
    return None

def naar_getal(tekst_waarde, type_getal=float):
    if not tekst_waarde:
        return 0 if type_getal == int else 0.0
    schoon = "".join(c for c in str(tekst_waarde) if c.isdigit() or c in ".,-").replace(",", ".")
    try:
        return type_getal(float(schoon))
    except:
        return 0 if type_getal == int else 0.0

def formatteer_datum_nl(datum_str):
    try:
        return datetime.strptime(datum_str, "%Y-%m-%d").strftime("%d-%m-%Y")
    except:
        return datum_str

def formatteer_euro_nl(bedrag):
    return f"{bedrag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
@st.dialog("✏️ Auto Gegevens Bewerken")
def bewerk_auto_dialog(actie_id, ktk, km, inkoop, verkoop, apk, kosten, foto_huidig, auto_naam, trans_huidig, status_huidig):
    try: standaard_datum = datetime.strptime(apk, "%Y-%m-%d").date()
    except: standaard_datum = datetime.today().date()

    edit_naam = st.text_input("Pas Naam / Omschrijving aan", value=auto_naam if auto_naam else "")
    edit_ktk = st.text_input("Pas Kenteken aan", value=ktk)
    edit_status = st.selectbox("Status", options=["In voorraad", "Gereserveerd", "Verkocht"], index=["In voorraad", "Gereserveerd", "Verkocht"].index(status_huidig) if status_huidig in ["In voorraad", "Gereserveerd", "Verkocht"] else 0)
    edit_km = st.text_input("Pas Kilometerstand aan", value=str(km))
    edit_apk = st.date_input("Pas APK Datum aan", value=standaard_datum)
    edit_trans = st.selectbox("Pas Transmissie aan", options=["Handgeschakeld", "Automaat"], index=["Handgeschakeld", "Automaat"].index(trans_huidig) if trans_huidig in ["Handgeschakeld", "Automaat"] else 0)
    edit_inkoop = st.text_input("Pas Inkoopprijs aan (€)", value=str(inkoop))
    edit_verkoop = st.text_input("Pas Verkoopprijs aan (€)", value=str(verkoop))
    edit_kosten = st.text_input("Pas Extra kosten aan (€)", value=str(kosten))
    edit_fotos = st.file_uploader("Upload nieuwe foto's", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    
    if st.button("💾 Wijzigingen Live Opslaan", type="primary", use_container_width=True):
        if edit_ktk.strip():
            foto_opslaan = foto_huidig
            if edit_fotos:
                foto_lijst = []
                for f in edit_fotos:
                    img = Image.open(f)
                    img.thumbnail((800, 800))
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=70)
                    foto_lijst.append(base64.b64encode(buffer.getvalue()).decode("utf-8"))
                foto_opslaan = "||".join(foto_lijst)
            
            cursor.execute("""
                UPDATE voorraad 
                SET naam=?, kenteken=?, km_stand=?, apk_datum=?, transmissie=?, inkoopprijs=?, verkoopprijs=?, extra_kosten=?, afbeelding=?, status=? 
                WHERE id=?
            """, (edit_naam, edit_ktk.upper().strip(), naar_getal(edit_km, int), str(edit_apk), edit_trans, naar_getal(edit_inkoop), naar_getal(edit_verkoop), naar_getal(edit_kosten), foto_opslaan, edit_status, actie_id))
            conn.commit()
            st.rerun()

# --- HEADER & STATUS DASHBOARD BEREKENING ---
head_col1, head_col2 = st.columns(2)
head_col1.title("🚗 Autohandel Inventaris")
if head_col2.button("🚪 Uitloggen", use_container_width=True):
    st.session_state["ingelogd"] = False
    st.rerun()

cursor.execute("SELECT inkoopprijs, verkoopprijs, extra_kosten, status FROM voorraad")
stat_rijen = cursor.fetchall()

autos_in_voorraad = [r for r in stat_rijen if r[3] != 'Verkocht']
autos_verkocht = [r for r in stat_rijen if r[3] == 'Verkocht']

totale_voorraadwaarde = sum(r[0] + r[2] for r in autos_in_voorraad)
totale_verwachte_winst = sum(r[1] - (r[0] + r[2]) for r in autos_in_voorraad)
gerealiseerde_winst = sum(r[1] - (r[0] + r[2]) for r in autos_verkocht)

st.write("")
with st.expander("📊 Actuele Status Dashboard", expanded=True):
    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    stat_col1.metric(label="Huidige Voorraad", value=f"{len(autos_in_voorraad)} stuks")
    stat_col2.metric(label="Investeringswaarde", value=f"€ {formatteer_euro_nl(totale_voorraadwaarde)}")
    stat_col3.metric(label="Verwachte Winst (Voorraad)", value=f"€ {formatteer_euro_nl(totale_verwachte_winst)}")
    stat_col4.metric(label="Gerealiseerde Winst (Verkocht)", value=f"€ {formatteer_euro_nl(gerealiseerde_winst)}")
# --- TOEVOEGEN FORMULIER ---
st.subheader("Nieuwe auto toevoegen")
rdw_col1, rdw_col2 = st.columns(2)
rdw_kenteken = rdw_col1.text_input("Optioneel: Snel RDW Gegevens ophalen via kenteken", placeholder="Bijv. 47-LV-JV").upper().replace("-", "")

with rdw_col2:
    st.markdown('<p style="margin-bottom: 0px; padding-bottom: 24px;"></p>', unsafe_allow_html=True)
    klik_rdw = st.button("🔍 RDW Gegevens Ophalen", use_container_width=True)

if klik_rdw:
    rdw_data = haal_rdw_gegevens(rdw_kenteken)
    if rdw_data:
        st.session_state["rdw_naam"] = rdw_data["naam"]
        st.session_state["rdw_apk"] = rdw_data["apk"]
        st.session_state["rdw_ktk"] = rdw_kenteken
        st.toast("⚡ RDW Gegevens succesvol geladen!", icon="✅")
    else: 
        st.error("Kenteken niet gevonden bij het RDW of API-fout.")

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
    gevoegde_fotos = st.file_uploader("Kies foto's van de auto (Optioneel)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    submit = st.form_submit_button("Voeg toe aan voorraad")

if submit and kenteken.strip():
    foto_data = ""
    if gevoegde_fotos:
        foto_lijst = []
        for f in gevoegde_fotos:
            img = Image.open(f); img.thumbnail((800, 800)); buffer = io.BytesIO(); img.save(buffer, format="JPEG", quality=70)
            foto_lijst.append(base64.b64encode(buffer.getvalue()).decode("utf-8"))
        foto_data = "||".join(foto_lijst)
        
    cursor.execute("""
        INSERT INTO voorraad (naam, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, transmissie, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (naam, kenteken.upper().strip(), naar_getal(km_stand_str, int), naar_getal(inkoopprijs_str), naar_getal(verkoopprijs_str), str(apk_datum), naar_getal(extra_kosten_str), foto_data, transmissie, status_invoer))
    conn.commit()
    for k in ["rdw_naam", "rdw_apk", "rdw_ktk"]: st.session_state.pop(k, None)
    st.success("Auto succesvol toegevoegd!"); st.rerun()

# --- INVENTARIS FILTERS EN WEERGAVE ---
st.subheader("Huidige inventaris")
inv_col1, inv_col2, inv_col2_5, inv_col3, inv_col4 = st.columns([2, 1.5, 1, 0.8, 1])
zoekterm = inv_col1.text_input("🔍 Zoek op kenteken of omschrijving...").upper()
sorteer_optie = inv_col2.selectbox("🔀 Sorteren op", options=["ID Nummer (Oplopend)", "ID Nummer (Aflopend)", "Verwachte Winst (Hoog naar laag)", "Kilometerstand (Laag naar hoog)", "APK Datum (Kortste eerst)"])
filter_status = inv_col2_5.selectbox("🚦 Filter Status", options=["Alle", "In voorraad", "Gereserveerd", "Verkocht"])

if inv_col3.button("🔄 Verversen", use_container_width=True): st.rerun()

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

    if filter_status != "Alle": verwerkte_autos = [x for x in verwerkte_autos if x["status"] == filter_status]
    if zoekterm: verwerkte_autos = [x for x in verwerkte_autos if zoekterm in x["kenteken"] or zoekterm in (x["naam"] or "").upper()]

    if "Aflopend" in sorteer_optie: verwerkte_autos.reverse()
    elif "Winst" in sorteer_optie: verwerkte_autos = sorted(verwerkte_autos, key=lambda x: x["winst"], reverse=True)
    elif "Kilometerstand" in sorteer_optie: verwerkte_autos = sorted(verwerkte_autos, key=lambda x: x["km_stand"])
    elif "APK" in sorteer_optie: verwerkte_autos = sorted(verwerkte_autos, key=lambda x: x["apk_datum"] if x["apk_datum"] else "9999-12-31")

    if verwerkte_autos:
        df = pd.DataFrame(verwerkte_autos).drop(columns=['afbeelding'])
        towrite = io.BytesIO(); df.to_excel(towrite, index=False); towrite.seek(0)
        inv_col4.download_button(label="📊 Download Excel", data=towrite, file_name="inventaris.xlsx", use_container_width=True)

    for auto in verwerkte_autos:
        weergave_naam = auto["naam"] if auto["naam"] else "Onbekende auto"
        status_icoon = "🟢" if auto["status"] == "In voorraad" else "🟡" if auto["status"] == "Gereserveerd" else "🔴"
        
        apk_waarschuwing = ""
        try:
            dagen = (datetime.strptime(auto["apk_datum"], "%Y-%m-%d").date() - datetime.today().date()).days
            if 0 <= dagen <= 30: apk_waarschuwing = " ⚠️ (APK bijna verlopen!)"
            elif dagen < 0: apk_waarschuwing = " 🚨 (APK VERLOPEN!)"
        except: pass

        with st.expander(f"{status_icoon} [{auto['status']}] {weergave_naam} ({auto['kenteken']}) - Prijs: € {formatteer_euro_nl(auto['verkoopprijs'])}{apk_waarschuwing}"):
            col1, col2 = st.columns(2)
            with col1:
                if auto["afbeelding"]:
                    alle_fotos = auto["afbeelding"].split("||")
                    foto_cols = st.columns(min(len(alle_fotos), 3))
                    for idx, f_data in enumerate(alle_fotos):
                        with foto_cols[idx % min(len(alle_fotos), 3)]:
                            try: st.image(base64.b64decode(f_data), use_container_width=True)
                            except: st.error("Fout laden foto")
                else: st.info("Geen afbeelding beschikbaar.")
            with col2:
                st.write(f"**Kilometerstand:** {auto['km_stand']:,} km".replace(",", "."))
                st.write(f"**Transmissie:** {auto['transmissie'] if auto['transmissie'] else 'Niet opgegeven'}")
                st.write(f"**APK Datum:** {formatteer_datum_nl(auto['apk_datum'])}{apk_waarschuwing}")
                st.write(f"**Inkoopprijs:** € {formatteer_euro_nl(auto['inkoopprijs'])}")
                st.write(f"**Extra kosten:** € {formatteer_euro_nl(auto['extra_kosten'])}")
                st.write(f"**Marge / Winst:** € {formatteer_euro_nl(auto['winst'])}")
                
                b_edit, b_del = st.columns(2)
                if b_edit.button("✏️ Aanpassen", key=f"ed_{auto['id']}", use_container_width=True, type="primary"):
                    bewerk_auto_dialog(auto["id"], auto["kenteken"], auto["km_stand"], auto["inkoopprijs"], auto["verkoopprijs"], auto["apk_datum"], auto["extra_kosten"], auto["afbeelding"], auto["naam"], auto["transmissie"], auto["status"])
                if b_del.button("🗑️ Verwijderen", key=f"dl_{auto['id']}", use_container_width=True):
                    cursor.execute("DELETE FROM voorraad WHERE id=?", (auto["id"],)); conn.commit(); st.rerun()

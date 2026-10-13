import base64
from datetime import datetime
import io
import os
import json
from PIL import Image
import streamlit as st
import pandas as pd
import requests
from supabase import create_client

st.set_page_config(page_title="Autohandel Inventaris", layout="wide")

# --- SUPABASE VERBINDING INSTELLEN ---
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()
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
        veilig_wachtwoord = st.secrets.get("PASSWORD", "DONGEN123")
        if wachtwoord_invoer == veilig_wachtwoord:
            st.session_state["ingelogd"] = True
            st.success("Succesvol ingelogd!")
            st.rerun()
        else:
            st.error("Onjuist wachtwoord, probeer het opnieuw.")
    st.stop()
    
# --- RDW KOPPELING ---
def overheid_rdw_lookup_krachtig(kenteken_str):
    schoon = kenteken_str.replace("-", "").upper().strip()
    if not schoon:
        return None
    
    url_voertuig = f"https://opendata.rdw.nl/resource/m9d7-ebf2.json?kenteken={schoon}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json"
    }
    
    try:
        res_v = requests.get(url_voertuig, headers=headers, timeout=8)
        if res_v.status_code == 200:
            if "application/json" not in res_v.headers.get("Content-Type", ""):
                return {"fout": "RDW stuurde een onverwacht antwoordformaat (HTML). Probeer het opnieuw."}
                
            data_v = res_v.json()
            if isinstance(data_v, list) and len(data_v) > 0:
                voertuig = data_v[0]  
                
                merk = voertuig.get("merk", "").title()
                model = voertuig.get("handelsbenaming", "").title()
                volledige_naam = f"{merk} {model}".strip()
                kleur = voertuig.get("eerste_kleur", "Onbekend").title()
                cataloguswaarde = naar_getal(voertuig.get("catalogusprijs", 0.0))
                brandstof = voertuig.get("brandstof_omschrijving", "Benzine").title()

                bouwjaar = 0
                datum_toelating = voertuig.get("datum_eerste_toelating", "")
                if datum_toelating and len(str(datum_toelating)) >= 4:
                    try: bouwjaar = int(str(datum_toelating)[:4])
                    except: pass

                apk_verval = voertuig.get("vervaldatum_apk", "")
                apk_formatted = datetime.today().date()
                if apk_verval:
                    try: apk_formatted = datetime.strptime(str(apk_verval), "%Y%m%d").date()
                    except: pass
                        
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
            return {"fout": "Toegang geweigerd (403) door RDW."}
        elif res_v.status_code == 429:
            return {"fout": "Te veel aanvragen achter elkaar (429). Wacht 10 seconden."}
        else:
            return {"fout": f"RDW Server foutmelding. Statuscode: {res_v.status_code}."}
    except requests.exceptions.Timeout:
        return {"fout": "De verbinding met de RDW duurde te lang."}
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
    try:
        # Als het bedrag als tekst uit de database komt, maken we er eerst een getal van
        veilig_bedrag = float(bedrag) if bedrag is not None else 0.0
    except:
        veilig_bedrag = 0.0
        
    return f"{veilig_bedrag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# --- DATA IMPORT & EXPORT MET SUPABASE ---
def exporteer_database_naar_json():
    voorraad_data = supabase.table("voorraad").select("kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, naam, transmissie, status, brandstof, bouwjaar, kleur, cataloguswaarde").execute().data
    agenda_data = supabase.table("agenda").select("datum, titel, notitie, status").execute().data
    
    actueel_startbudget = st.session_state.get("startbudget", 10000.0)
    volledige_backup = {
        "startbudget": actueel_startbudget,
        "voorraad": voorraad_data,
        "agenda": agenda_data
    }
    return json.dumps(volledige_backup, indent=4)

def importeer_json_naar_database(json_data):
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
            
        supabase.table("voorraad").delete().gt("id", 0).execute()
        supabase.table("agenda").delete().gt("id", 0).execute()
        
        if voertuigen:
            supabase.table("voorraad").insert(voertuigen).execute()
        if afspraken:
            supabase.table("agenda").insert(afspraken).execute()
        return True
    except Exception as e:
        st.sidebar.error(f"Import cloud mislukt: {str(e)}")
        return False

# --- DIALOGS (BEWERKEN POP-UP) ---
@st.dialog("✏️ Auto Gegevens Bewerken")
def bewerk_auto_dialog(actie_id, ktk, km, inkoop, verkoop, apk, kosten, foto_huidig, auto_naam, trans_huidig, status_huidig, brandstof_h, bouwjaar_h, kleur_h, cat_h):
    try: standaard_datum = datetime.strptime(apk, "%Y-%m-%d").date()
    except: standaard_datum = datetime.today().date()

    uploader_key = f"fotos_upload_{actie_id}"

    with st.form(f"edit_form_{actie_id}", clear_on_submit=False):
        edit_naam = st.text_input("Pas Naam / Omschrijving aan", value=auto_naam if auto_naam else "")
        edit_ktk = st.text_input("Pas Kenteken aan", value=ktk)
        status_opties = ["In voorraad", "Gereserveerd", "Verkocht"]
        edit_status = st.selectbox("Status", options=status_opties, index=status_opties.index(status_huidig) if status_huidig in status_opties else 0)
        
        col_e1, col_e2 = st.columns(2)
        edit_km = col_e1.number_input("Pas Kilometerstand aan", value=int(km), step=1)
        edit_apk = col_e2.date_input("Pas APK Datum aan", value=standaard_datum)
        
        col_e3, col_e4 = st.columns(2)
        edit_brandstof_opties = ["Benzine", "Diesel", "Hybride", "Elektrisch", "Lpg"]
        if brandstof_h not in edit_brandstof_opties and brandstof_h:
            edit_brandstof_opties.append(brandstof_h)
            
        edit_brandstof = col_e3.selectbox("Pas Brandstof aan", options=edit_brandstof_opties, index=edit_brandstof_opties.index(brandstof_h) if brandstof_h in edit_brandstof_opties else 0)
        edit_bouwjaar = col_e4.number_input("Pas Bouwjaar aan", value=int(bouwjaar_h) if bouwjaar_h else 0, step=1)
        
        col_e5, col_e6 = st.columns(2)
        edit_kleur = col_e5.text_input("Pas Kleur aan", value=str(kleur_h if kleur_h else ""))
        edit_cat = col_e6.number_input("Pas Cataloguswaarde aan (€)", value=float(cat_h) if cat_h else 0.0, step=50.0)

        trans_opties = ["Handgeschakeld", "Automaat"]
        edit_trans = st.selectbox("Pas Transmissie aan", options=trans_opties, index=trans_opties.index(trans_huidig) if trans_huidig in trans_opties else 0)
        
        col_e7, col_e8, col_e9 = st.columns(3)
        edit_inkoop = col_e7.number_input("Pas Inkoopprijs aan (€)", value=float(inkoop), step=50.0)
        edit_verkoop = col_e8.number_input("Pas Verkoopprijs aan (€)", value=float(verkoop), step=50.0)
        edit_kosten = col_e9.number_input("Pas Extra kosten aan (€)", value=float(kosten), step=10.0)
        
        # --- FLEXIBELE FOTO LOGICA ---
        verwijder_fotos = st.checkbox("🗑️ Alle huidige foto's permanent wissen", value=False)
        edit_fotos = st.file_uploader("Nieuwe foto's toevoegen", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key=uploader_key)
        
        submit_edit = st.form_submit_button("💾 Wijzigingen Live Opslaan", type="primary", use_container_width=True)
        
        if submit_edit:
            if edit_ktk.strip():
                # 1. Bepaal de basis (huidige foto's behouden óf leegmaken als de checkbox aan staat)
                if verwijder_fotos:
                    basis_fotos = []
                else:
                    basis_fotos = foto_huidig.split("||") if foto_huidig else []

                # 2. Als er nieuwe foto's zijn geüpload, verwerk deze en voeg ze toe aan de lijst
                if edit_fotos:
                    for f in edit_fotos:
                        img = Image.open(f)
                        
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")
                            
                        img.thumbnail((800, 800))
                        buffer = io.BytesIO()
                        img.save(buffer, format="JPEG", quality=70)
                        basis_fotos.append(base64.b64encode(buffer.getvalue()).decode("utf-8"))
                
                # 3. Voeg alles weer netjes samen tot één string (of leeg als er geen foto's zijn)
                foto_opslaan = "||".join(basis_fotos) if basis_fotos else ""

                update_data = {
                    "naam": edit_naam, "kenteken": edit_ktk.upper().replace("-", "").strip(),
                    "km_stand": int(edit_km), "apk_datum": str(edit_apk), "transmissie": edit_trans,
                    "inkoopprijs": float(edit_inkoop), "verkoopprijs": float(edit_verkoop),
                    "extra_kosten": float(edit_kosten), "afbeelding": foto_opslaan, "status": edit_status,
                    "brandstof": edit_brandstof, "bouwjaar": int(edit_bouwjaar), "kleur": edit_kleur,
                    "cataloguswaarde": float(edit_cat)
                }
                supabase.table("voorraad").update(update_data).eq("id", actie_id).execute()
                st.rerun()

# --- DIALOG KOOPOVEREENKOMST ---
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

    if st.button("🔥 Contract Downloaden", type="primary", use_container_width=True):
        if not koper_naam.strip():
            st.error("Vul tenminste de naam van de koper in.")
            return

        contant_vink = "[X]" if betaalwijze == "Contant" else "[  ]"
        bank_vink = "[X]" if betaalwijze == "Per bankoverschrijving" else "[  ]"
        huidige_datum = datetime.today().strftime('%d-%m-%Y')

        # --- VEILIGHEIDSFIX: Zet km stand om naar een geldig heel getal ---
        try:
            km_veilig = int(float(str(km).replace(".", "").replace(",", "")))
        except:
            km_veilig = 0

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
            </style>
        </head>
        <body>
            <h2>PARTICULIERE KOOPOVEREENKOMST AUTO</h2>
            <p style="font-size: 11px; font-style: italic;">(Margevoertuig / Zonder Garantie)</p>
            <h3>1. Gegevens van de Verkoper</h3>
            <table>
                <tr><td class="label">Naam:</td><td>Autohandel Dongen</td></tr>
                <tr><td class="label">Adres:</td><td>De Volger 2B, 5051 CX Dongen</td></tr>
            </table>
            <h3>2. Gegevens van de Koper</h3>
            <table>
                <tr><td class="label">Naam:</td><td>{koper_naam}</td></tr>
                <tr><td class="label">Adres:</td><td>{koper_adres} {koper_postcode}</td></tr>
                <tr><td class="label">Legitimatie:</td><td>{koper_legit}</td></tr>
            </table>
            <h3>3. Voertuiggegevens</h3>
            <table>
                <tr><td class="label">Merk & Model:</td><td>{merk_model}</td><td class="label">Kenteken:</td><td>{kenteken}</td></tr>
                <tr><td class="label">Tellerstand:</td><td>{km_veilig:,} km</td><td class="label">APK tot:</td><td>{formatteer_datum_nl(apk)}</td></tr>
            </table>
            <h3>4. Financiële Afspraken</h3>
            <table>
                <tr><td class="label">Prijs:</td><td>&euro; {formatteer_euro_nl(verkoop)}</td></tr>
                <tr><td class="label">Betaling:</td><td>{contant_vink} Contant &nbsp;&nbsp; {bank_vink} Bank</td></tr>
            </table>
            <h3>5. Bijzondere Afspraken</h3>
            <p>{bijzondere_afspraken if bijzondere_afspraken.strip() else 'Geen.'}</p>
        </body>
        </html>
        """
        b64 = base64.b64encode(html_content.encode('utf-8')).decode()
        filename = f"Koopovereenkomst_{kenteken}_{huidige_datum}.html"
        href = f'<a href="data:text/html;base64,{b64}" download="{filename}" style="display:block; text-align:center; background-color:#28a745; color:white; padding:10px; border-radius:8px; text-decoration:none; font-weight:bold;">📥 Download Overeenkomst</a>'
        st.markdown(href, unsafe_allow_html=True)


# --- SIDEBAR NAVIGATIE ---
with st.sidebar:
    st.title("⚙️ Navigatie")
    menu_optie = st.radio(
        "Kies een functie:",
        ["🆕 Nieuwe auto toevoegen", "🟢 Actuele Voorraad", "🔴 Verkochte Voertuigen", "📅 Agenda & Notities", "📊 Actuele Status Dashboard", "💰 Financieel Overzicht"]
    )
    
    st.markdown("---")
    st.subheader("💾 Cloud Backup & Herstel")
    
    try:
        json_string = exporteer_database_naar_json()
        st.download_button(
            label="📤 Exporteer Cloud-Data (Backup)",
            data=json_string,
            file_name=f"autohandel_cloud_backup_{datetime.today().strftime('%Y-%m-%d')}.json",
            mime="application/json",
            use_container_width=True
        )
    except:
        st.error("Export mislukt")

    geimporteerd_bestand = st.file_uploader("📥 Importeer Data naar Cloud", type=["json"])
    if geimporteerd_bestand is not None:
        json_data = geimporteerd_bestand.getvalue().decode("utf-8")
        if st.button("🔄 Herstel cloud-database nu", type="primary", use_container_width=True):
            if importeer_json_naar_database(json_data):
                st.toast("⚡ Cloud-database succesvol hersteld!", icon="✅")
                st.rerun()

    st.markdown("---")
    if st.button("🚪 Uitloggen", use_container_width=True):
        st.session_state["ingelogd"] = False
        st.rerun()

# --- VEILIGE BALANS BEREKENING (LIVE CLOUD) ---
stat_rijen = supabase.table("voorraad").select("inkoopprijs, verkoopprijs, extra_kosten, status").execute().data

autos_in_voorraad = [r for r in stat_rijen if r['status'] != 'Verkocht']
autos_verkocht = [r for r in stat_rijen if r['status'] == 'Verkocht']

totale_voorraadwaarde = sum(float(r['inkoopprijs'] or 0) + float(r['extra_kosten'] or 0) for r in autos_in_voorraad)
gerealiseerde_winst = sum(float(r['verkoopprijs'] or 0) - (float(r['inkoopprijs'] or 0) + float(r['extra_kosten'] or 0)) for r in autos_verkocht)

if "startbudget" not in st.session_state:
    st.session_state["startbudget"] = 10000.0

actueel_vrij_budget = st.session_state["startbudget"] - totale_voorraadwaarde + gerealiseerde_winst
# --- NIEUWE AUTO TOEVOEGEN ---
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
        km_stand_str = c_form1.number_input("Kilometerstand", value=0, step=1)
        apk_datum = c_form2.date_input("APK Datum", value=st.session_state.get("rdw_apk", datetime.today().date()), format="DD-MM-YYYY")
        
        c_form3, c_form4 = st.columns(2)
        brandstof_opties = ["Benzine", "Diesel", "Hybride", "Elektrisch", "Lpg"]
        rdw_brandstof = st.session_state.get("rdw_brandstof", "Benzine")
        if rdw_brandstof not in brandstof_opties and rdw_brandstof:
            brandstof_opties.append(rdw_brandstof)
            
        brandstof_invoer = c_form3.selectbox("Brandstof", options=brandstof_opties, index=brandstof_opties.index(rdw_brandstof) if rdw_brandstof in brandstof_opties else 0)
        bouwjaar_invoer = c_form4.number_input("Bouwjaar", value=int(st.session_state.get("rdw_bouwjaar", 0)), step=1)

        c_form5, c_form6 = st.columns(2)
        kleur_invoer = c_form5.text_input("Kleur", value=st.session_state.get("rdw_kleur", ""))
        cat_invoer = c_form6.number_input("Oorspronkelijke Cataloguswaarde (€)", value=float(st.session_state.get("rdw_cataloguswaarde", 0.0)), step=50.0)

        transmissie = st.selectbox("Transmissie", options=["Handgeschakeld", "Automaat"])
        status_invoer = st.selectbox("Status bij instroom", options=["In voorraad", "Gereserveerd"])
        
        c_form7, c_form8, c_form9 = st.columns(3)
        inkoopprijs_val = c_form7.number_input("Inkoopprijs (€)", value=0.0, step=50.0)
        verkoopprijs_val = c_form8.number_input("Verkoopprijs (€)", value=0.0, step=50.0)
        extra_kosten_val = c_form9.number_input("Extra kosten (€)", value=0.0, step=10.0)
        
        gevoegde_fotos = st.file_uploader("Kies foto's (Optioneel)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
        submit = st.form_submit_button("Voeg toe aan cloud voorraad")

    if submit and kenteken.strip():
        foto_data = ""
        if gevoegde_fotos:
            foto_lijst = []
            for f in gevoegde_fotos:
                img = Image.open(f)
                
                # ---> HIER STAAT DE FIX VOOR TRANSPARANTIE / COLOR MODES <---
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                    
                img.thumbnail((800, 800))
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=70)
                foto_lijst.append(base64.b64encode(buffer.getvalue()).decode("utf-8"))
            foto_data = "||".join(foto_lijst)

            
        # Zorg dat dit dictionary-blok netjes op hetzelfde niveau staat
        nieuw_voertuig = {
            "naam": naam, 
            "kenteken": kenteken.upper().replace("-", "").strip(), 
            "km_stand": int(km_stand_str),
            "inkoopprijs": float(inkoopprijs_val), 
            "verkoopprijs": float(verkoopprijs_val), 
            "apk_datum": str(apk_datum),
            "extra_kosten": float(extra_kosten_val), 
            "afbeelding": foto_data, 
            "transmissie": transmissie,
            "status": status_invoer, 
            "brandstof": brandstof_invoer, 
            "bouwjaar": int(bouwjaar_invoer),
            "kleur": kleur_invoer, 
            "cataloguswaarde": float(cat_invoer)
        }

        # Deze regel stond te ver naar rechts en staat nu exact goed uitgelijnd!
        supabase.table("voorraad").insert(nieuw_voertuig).execute()
            
        for sleutel in ["rdw_naam", "rdw_ktk", "rdw_apk", "rdw_brandstof", "rdw_bouwjaar", "rdw_kleur", "rdw_cataloguswaarde"]:
            if sleutel in st.session_state: del st.session_state[sleutel]
        st.success("Auto succesvol toegevoegd aan de Cloud!")
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
    
    alle_autos = supabase.table("voorraad").select("*").execute().data

    verwerkte_autos = []
    if alle_autos:
        for auto in alle_autos:
            # Prijzen veilig omzetten naar getallen voor de winstberekening
            try: vk_prijs = float(auto["verkoopprijs"] or 0)
            except: vk_prijs = 0.0
            try: ik_prijs = float(auto["inkoopprijs"] or 0)
            except: ik_prijs = 0.0
            try: ex_kosten = float(auto["extra_kosten"] or 0)
            except: ex_kosten = 0.0
                
            winst = vk_prijs - (ik_prijs + ex_kosten)
            
            verwerkte_autos.append({
                "id": auto["id"], "kenteken": auto["kenteken"], "km_stand": auto["km_stand"], "inkoopprijs": auto["inkoopprijs"], "verkoopprijs": auto["verkoopprijs"],
                "apk_datum": auto["apk_datum"], "extra_kosten": auto["extra_kosten"], "afbeelding": auto["afbeelding"], "naam": auto["naam"], "transmissie": auto["transmissie"], 
                "status": auto["status"], "brandstof": auto["brandstof"] if auto["brandstof"] else "Onbekend", "bouwjaar": auto["bouwjaar"] if auto["bouwjaar"] else 0,
                "kleur": auto["kleur"] if auto["kleur"] else "Onbekend", "cataloguswaarde": auto["cataloguswaarde"] if auto["cataloguswaarde"] else 0.0, "winst": winst
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
            verwerkte_autos = [x for x in verwerkte_autos if zoekterm in str(x["kenteken"]) or zoekterm in (x["naam"] or "").upper()]
        
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
                                        st.markdown(f'<div style="width:100%; aspect-ratio: 4/3; overflow:hidden; border-radius:8px; display:flex; align-items:center; justify-content:center;"><img src="data:image/jpeg;base64,{f_data}" style="max-width:100%; max-height:100%; object-fit:contain;"></div>', unsafe_allow_html=True)
                                    except: st.error("Fout foto")
                        else: st.info("Geen afbeelding beschikbaar.")

                    with c2:
                        # Zorg dat de kilometerstand veilig als getal wordt ingeladen
                        try: km_veilig = int(float(auto['km_stand']))
                        except: km_veilig = 0
                            
                        try: bouwjaar_veilig = int(float(auto['bouwjaar']))
                        except: bouwjaar_veilig = 0
                            
                        try: cat_veilig = float(auto['cataloguswaarde'])
                        except: cat_veilig = 0.0

                        st.write(f"**Kilometerstand:** {km_veilig:,} km".replace(",", "."))
                        st.write(f"**Brandstof:** {auto['brandstof']} | **Bouwjaar:** {bouwjaar_veilig if bouwjaar_veilig > 0 else 'Onbekend'}")
                        st.write(f"**Kleur:** {auto['kleur']} | **Cataloguswaarde:** € {formatteer_euro_nl(cat_veilig)}")
                        st.write(f"**Transmissie:** {auto['transmissie']} | **APK Datum:** {formatteer_datum_nl(auto['apk_datum'])}")
                        st.markdown("---")
                        
                        # Prijzen veilig inladen
                        try: inkoop_veilig = float(auto['inkoopprijs'])
                        except: inkoop_veilig = 0.0
                            
                        try: kosten_veilig = float(auto['extra_kosten'])
                        except: kosten_veilig = 0.0
                            
                        try: winst_veilig = float(auto['winst'])
                        except: winst_veilig = 0.0

                        st.write(f"**Inkoopprijs:** € {formatteer_euro_nl(inkoop_veilig)} | **Extra kosten:** € {formatteer_euro_nl(kosten_veilig)}")
                        st.write(f"**Marge / Winst:** € {formatteer_euro_nl(winst_veilig)}")
                        
                        # ---> HIER STAAT HET NIEUWE STUK NU EXACT GOED INGESPRONGEN <---
                        b_edit, b_del = st.columns(2)
                        
                        try: km_int = int(float(auto['km_stand']))
                        except: km_int = 0
                            
                        if b_edit.button("✏️ Aanpassen", key=f"ed_{auto['id']}", use_container_width=True):
                            bewerk_auto_dialog(auto["id"], auto["kenteken"], km_int, auto["inkoopprijs"], auto["verkoopprijs"], auto["apk_datum"], auto["extra_kosten"], auto["afbeelding"], auto["naam"], auto["transmissie"], auto["status"], auto["brandstof"], auto["bouwjaar"], auto["kleur"], auto["cataloguswaarde"])
                        
                        if b_del.button("🗑️ Verwijderen", key=f"dl_{auto['id']}", use_container_width=True):
                            supabase.table("voorraad").delete().eq("id", auto["id"]).execute()
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
    def nieuwe_afspraak_popup(gekozen_datum_str):
        with st.form("agenda_toevoeg_form", clear_on_submit=True):
            st.write(f"**Geselecteerde begindatum:** {formatteer_datum_nl(gekozen_datum_str)}")
            hele_dag = st.checkbox("📅 Deze afspraak duurt de gehele dag(en)", value=True)
            
            if hele_dag:
                tot_datum = st.date_input("Einddatum (t/m)", value=datetime.strptime(gekozen_datum_str, "%Y-%m-%d").date(), format="DD-MM-YYYY")
            else:
                tijd_col1, tijd_col2 = st.columns(2)
                ag_tijd_van = tijd_col1.time_input("Begintijd", value=datetime.strptime("10:00", "%H:%M").time())
                ag_tijd_tot = tijd_col2.time_input("Eindtijd", value=datetime.strptime("11:00", "%H:%M").time())
            
            ag_titel = st.text_input("Titel (bijv. Auto verhuurd, Vakantie, Showroom dicht)")
            ag_notitie = st.text_area("Aanvullende informatie / opmerkingen")
            ag_submit = st.form_submit_button("💾 Opslaan in Agenda", type="primary", use_container_width=True)
            
        if ag_submit and ag_titel.strip():
            opslag_datum = f"{gekozen_datum_str}||{str(tot_datum)}" if hele_dag else f"{gekozen_datum_str}T{ag_tijd_van.strftime('%H:%M:%S')}||{gekozen_datum_str}T{ag_tijd_tot.strftime('%H:%M:%S')}"
            supabase.table("agenda").insert({"datum": opslag_datum, "titel": ag_titel.strip(), "notitie": ag_notitie.strip(), "status": "Open"}).execute()
            st.toast("⚡ Afspraak succesvol toegevoegd!", icon="✅")
            st.rerun()

    @st.dialog("🔍 Afspraak Beheren")
    def bekijk_afspraak_popup(ev_data):
        event_id, titel_ruw, start_veld, eind_veld, notitie_veld, status_veld = ev_data["id"], ev_data["title"], ev_data["start_tijd"], ev_data["eind_tijd"], ev_data["notitie"], ev_data["status"]
        bewerk_modus_key = f"edit_mode_{event_id}"
        if bewerk_modus_key not in st.session_state: st.session_state[bewerk_modus_key] = False

        is_voorheen_hele_dag = "T" not in str(start_veld)
        pure_datum_van = str(start_veld).split("T")[0]
        pure_datum_tot = str(eind_veld).split("T")[0]
        
        try: standaard_van = datetime.strptime(pure_datum_van, "%Y-%m-%d").date()
        except: standaard_van = datetime.today().date()
        try: standaard_tot = datetime.strptime(pure_datum_tot, "%Y-%m-%d").date()
        except: standaard_tot = standaard_van

        pure_titel_origineel = titel_ruw.replace("[Open] ", "").replace("[Voltooid] ", "")

        if not st.session_state[bewerk_modus_key]:
            st.markdown(f"### **{pure_titel_origineel}**")
            if is_voorheen_hele_dag:
                if pure_datum_van == pure_datum_tot: st.write(f"📅 **Datum:** {formatteer_datum_nl(pure_datum_van)} (Gehele dag)")
                else: st.write(f"📅 **Periode:** {formatteer_datum_nl(pure_datum_van)} t/m {formatteer_datum_nl(pure_datum_tot)} (Gehele dagen)")
            else:
                st.write(f"📅 **Datum:** {formatteer_datum_nl(pure_datum_van)} (Met tijden)")
                
            st.write(f"📊 **Status:** {status_veld}")
            if notitie_veld: st.write(f"📝 **Opmerkingen:**  \n{notitie_veld}")
            st.markdown("---")
            
            col_b1, col_b2, col_b3 = st.columns(3)
            if col_b1.button("✅ Voltooid" if status_veld == "Open" else "🔄 Heropenen", use_container_width=True):
                nieuwe_status = "Voltooid" if status_veld == "Open" else "Open"
                supabase.table("agenda").update({"status": nieuwe_status}).eq("id", event_id).execute()
                st.rerun()
            if col_b2.button("✏️ Bewerken", use_container_width=True):
                st.session_state[bewerk_modus_key] = True
                st.rerun()
            if col_b3.button("🗑️ Wissen", type="secondary", use_container_width=True):
                supabase.table("agenda").delete().eq("id", event_id).execute()
                st.rerun()
        else:
            st.markdown("### ✏️ Afspraak Wijzigen")
            edit_hele_dag = st.checkbox("📅 Deze afspraak duurt de gehele dag(en)", value=is_voorheen_hele_dag, key=f"edit_hd_{event_id}")
            if edit_hele_dag:
                col_d1, col_d2 = st.columns(2)
                edit_datum_van = col_d1.date_input("Pas Begindatum aan", value=standaard_van, key=f"edit_dat_v_{event_id}")
                edit_datum_tot = col_d2.date_input("Pas Einddatum aan", value=standaard_tot, key=f"edit_dat_t_{event_id}")
            else:
                edit_datum_van = st.date_input("Pas Datum aan", value=standaard_van, key=f"edit_dat_{event_id}")
            
            edit_titel = st.text_input("Pas Titel aan", value=pure_titel_origineel, key=f"edit_ttl_{event_id}")
            edit_notitie = st.text_area("Pas Aanvullende informatie aan", value=notitie_veld if notitie_veld else "", key=f"edit_not_{event_id}")
            
            st.markdown("---")
            col_save1, col_save2 = st.columns(2)
            if col_save1.button("💾 Opslaan", type="primary", use_container_width=True):
                nieuw_datum_format = f"{edit_datum_van}||{edit_datum_tot}" if edit_hele_dag else f"{edit_datum_van}T10:00:00||{edit_datum_van}T11:00:00"
                supabase.table("agenda").update({"datum": nieuw_datum_format, "titel": edit_titel.strip(), "notitie": edit_notitie.strip()}).eq("id", event_id).execute()
                st.session_state[bewerk_modus_key] = False
                st.rerun()
            if col_save2.button("❌ Annuleren", use_container_width=True):
                st.session_state[bewerk_modus_key] = False
                st.rerun()

    st.markdown("""
        <style>
        .fc .fc-toolbar { display: flex !important; justify-content: space-between !important; margin-bottom: 15px !important; }
        .fc .fc-toolbar-title { font-size: 1.3rem !important; color: white !important; }
        .fc .fc-daygrid-day-number { font-size: 0.95rem !important; font-weight: bold !important; color: white !important; }
        .fc-daygrid-event { font-size: 0.8rem !important; padding: 3px !important; border-radius: 4px !important; }
        .fc-theme-standard td, .fc-theme-standard th, .fc-theme-standard .fc-scrollgrid { border: 1px solid rgba(255, 255, 255, 0.15) !important; }
        .fc .fc-button-primary { background-color: #1e1e24 !important; border: 1px solid rgba(255, 255, 255, 0.2) !important; color: white !important; }
        .fc .fc-button-primary:hover { background-color: rgb(255, 75, 75) !important; }
        .fc .fc-button-active { background-color: rgb(255, 75, 75) !important; border-color: rgb(255, 75, 75) !important; }
        </style>
    """, unsafe_allow_html=True)

    notities = supabase.table("agenda").select("*").execute().data
    calendar_events = []
    
    if notities:
        from datetime import timedelta
        for item in notities:
            n_id, n_datum_veld, n_titel, n_notitie, n_status = item["id"], item["datum"], item["titel"], item["notitie"], item["status"]
            db_start = db_eind = start_tijd = eind_tijd = n_datum_veld
            
            if "||" in str(n_datum_veld):
                start_tijd, eind_tijd = n_datum_veld.split("||")
                db_start, db_eind = start_tijd, eind_tijd
                is_hele_dag = "T" not in str(start_tijd)
                if is_hele_dag:
                    try: eind_tijd = (datetime.strptime(eind_tijd, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                    except: pass
            else:
                is_hele_dag = True
                try: eind_tijd = (datetime.strptime(eind_tijd, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                except: pass
            
            kleur = "#28a745" if n_status == "Voltooid" else "#ff4b4b"
            calendar_events.append({
                "id": str(n_id), "title": f"[{n_status}] {n_titel}", "start": start_tijd, "end": eind_tijd,
                "backgroundColor": kleur, "borderColor": kleur, "allDay": is_hele_dag,
                "extendedProps": {"notitie": n_notitie, "status": n_status, "start_tijd": db_start, "eind_tijd": db_eind}
            })
        
    calendar_options = {
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,timeGridWeek,timeGridDay"},
        "initialView": "dayGridMonth", "locale": "nl", "timeZone": "local", "height": "auto", "contentHeight": 550,
        "buttonText": {"today": "vandaag", "month": "maand", "week": "week", "day": "dag"}
    }
    
    state = calendar(events=calendar_events, options=calendar_options, key="agenda_strakke_kalender")
    
    if state.get("eventClick"):
        ev = state["eventClick"]["event"]
        props = ev.get("extendedProps", {})
        bekijk_afspraak_popup({"id": ev["id"], "title": ev["title"], "notitie": props.get("notitie"), "status": props.get("status"), "start_tijd": props.get("start_tijd"), "eind_tijd": props.get("eind_tijd")})
        
    elif state.get("dateClick"):
        ruwe_str = str(state["dateClick"]["date"])
        # TIMEZONE FIX: Als de kalender door UTC-tijd 22:00 uur doorgeeft, schuiven we hem direct 4 uur door naar de volgende dag
        if "T" in ruwe_str:
            try:
                dt = datetime.fromisoformat(ruwe_str.replace("Z", ""))
                puur_datum = (dt + timedelta(hours=4) if dt.hour >= 20 else dt).strftime("%Y-%m-%d")
            except:
                puur_datum = ruwe_str.split("T")[0]
        else:
            puur_datum = ruwe_str.strip()
            
        nieuwe_afspraak_popup(puur_datum)

import base64
from datetime import datetime
import io
import os
import sqlite3
from PIL import Image
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Autohandel Inventaris", layout="wide")

# --- ULTIEME UNIFORME STYLING EN REFRESH-KNOP FIX ---
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
        
        /* Zorgt dat alle formulieren, containers EN expanders er exact hetzelfde uitzien */
        div[data-testid="stForm"], div[data-testid="stVerticalBlockBorderContainer"], .streamlit-expanderContent {{
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
cursor.execute("SELECT id, kenteken, km_stand, inkoopprijs, verkoopprijs, apk_datum, extra_kosten, afbeelding, naam, transmissie FROM voorraad")
alle_autos = cursor.fetchall()

if alle_autos:
    verwerkte_autos = []
    for auto in alle_autos:
        auto_id, ktk, km, inkoop, verkoop, apk, kosten, foto_string, auto_naam, trans = auto
        winst = verkoop - (inkoop + kosten)
        verwerkte_autos.append({
            "id": auto_id, "kenteken": ktk, "km_stand": km, "inkoopprijs": inkoop,
            "verkoopprijs": verkoop, "apk_datum": apk, "extra_kosten": kosten,
            "afbeelding": foto_string, "naam": auto_naam, "transmissie": trans, "winst": winst
        })

    # SORTEER LOGICA ACTIVATIE
    if sorteer_optie == "ID Nummer (Oplopend)":
        verwerkte_autos = sorted(verwerkte_autos, key=lambda x: x["id"])
    elif sorteer_optie == "ID Nummer (Aflopend)":
        verwerkte_autos = sorted(verwerkte_autos, key=lambda x: x["id"], reverse=True)
    elif sorteer_optie == "Verwachte Winst (Hoog naar laag)":
        verwerkte_autos = sorted(verwerkte_autos, key=lambda x: x["winst"], reverse=True)
    elif sorteer_optie == "Verwachte Winst (Laag naar hoog)":
        verwerkte_autos = sorted(verwerkte_autos, key=lambda x: x["winst"])
    elif sorteer_optie == "Kilometerstand (Laag naar hoog)":
        verwerkte_autos = sorted(verwerkte_autos, key=lambda x: x["km_stand"])
    elif sorteer_optie == "Kilometerstand (Hoog naar laag)":
        verwerkte_autos = sorted(verwerkte_autos, key=lambda x: x["km_stand"], reverse=True)
    elif sorteer_optie == "APK Datum (Kortste eerst)":
        verwerkte_autos = sorted(verwerkte_autos, key=lambda x: x["apk_datum"] if x["apk_datum"] else "9999-12-31")
    elif sorteer_optie == "APK Datum (Langste eerst)":
        verwerkte_autos = sorted(verwerkte_autos, key=lambda x: x["apk_datum"] if x["apk_datum"] else "0000-00-00", reverse=True)

    # --- PROFESSIONELE EN MET STIJLEN AANGEKLEEDDE EXCEL GENERATOR ---
    export_lijst = []
    for auto in verwerkte_autos:
        weergave_naam = auto["naam"] if auto["naam"] else "Onbekende auto"
        if zoekterm and (zoekterm not in auto["kenteken"]) and (zoekterm not in weergave_naam.upper()):
            continue
        export_lijst.append({
            "ID": auto["id"], "Naam / Omschrijving": weergave_naam, "Kenteken": auto["kenteken"],
            "KM Stand": auto["km_stand"], "Transmissie": auto["transmissie"], "APK Datum": formatteer_datum_nl(auto["apk_datum"]),
            "Inkoopprijs": auto["inkoopprijs"], "Extra Kosten": auto["extra_kosten"],
            "Verkoopprijs": auto["verkoopprijs"], "Verwachte Winst": auto["winst"]
        })
        
    if export_lijst:
        df = pd.DataFrame(export_lijst)
        towrite = io.BytesIO()
        
        with pd.ExcelWriter(towrite, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Voorraad Inventaris')
            workbook = writer.book
            worksheet = writer.sheets['Voorraad Inventaris']
            
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            
            header_fill = PatternFill(start_color="1E1E24", end_color="1E1E24", fill_type="solid")
            header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
            data_font = Font(name="Arial", size=10, color="000000")
            center_alignment = Alignment(horizontal="center", vertical="center")
            left_alignment = Alignment(horizontal="left", vertical="center")
            right_alignment = Alignment(horizontal="right", vertical="center")
            
            thin_border = Border(
                left=Side(style='thin', color='DDDDDD'), right=Side(style='thin', color='DDDDDD'),
                top=Side(style='thin', color='DDDDDD'), bottom=Side(style='thin', color='DDDDDD')
            )
            
            # Geef de titels een professionele look
            for col_idx in range(1, worksheet.max_column + 1):
                cell = worksheet.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = center_alignment
            worksheet.row_dimensions.height = 26

            # Loop door alle data-cellen voor styling en valuta-opmaak
            for row_idx in range(2, worksheet.max_row + 1):
                worksheet.row_dimensions[row_idx].height = 20
                for col_idx in range(1, worksheet.max_column + 1):
                    cell = worksheet.cell(row=row_idx, column=col_idx)
                    cell.font = data_font
                    cell.border = thin_border
                    
                    # VOLLEDIG GECORRIGEERDE KOLOM-INDEXERING (Vaste lijsten ingevuld!)
                    if col_idx in:  # ID, Kenteken, Transmissie, APK Datum
                        cell.alignment = center_alignment
                    elif col_idx in:         # Naam / Omschrijving
                        cell.alignment = left_alignment
                    elif col_idx in:         # KM Stand
                        cell.alignment = right_alignment
                        cell.number_format = '#,##0" km"'
                    elif col_idx in: # Financiële kolommen
                        cell.alignment = right_alignment
                        cell.number_format = '"€ " #,##0.00'
            
            # Automatische kolombreedte bepaling zodat er nooit meer '###' of afgekapte tekst staat
            for col in worksheet.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = col.column_letter
                worksheet.column_dimensions[col_letter].width = max(max_len + 4, 13)
                
        towrite.seek(0)
        
        with inv_col4:
            st.markdown('<p style="margin-bottom: 0px; padding-bottom: 23px;"></p>', unsafe_allow_html=True)
            st.download_button(
                label="📊 Download Excel", data=towrite, file_name=f"inventaris_{datetime.now().strftime('%d-%m-%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True
            )

    # --- UITROL INVENTARIS ---
    for auto in verwerkte_autos:
        weergave_naam = auto["naam"] if auto["naam"] else "Onbekende auto"
        if zoekterm and (zoekterm not in auto["kenteken"]) and (zoekterm not in weergave_naam.upper()):
            continue
        apk_nl = formatteer_datum_nl(auto["apk_datum"])

        with st.expander(f"🚗 {weergave_naam} ({auto['kenteken']}) - Verkoopprijs: €{auto['verkoopprijs']:,.2f}"):
            col1, col2 = st.columns(2)
            
            with col1:
                if auto["afbeelding"]:
                    alle_fotos = auto["afbeelding"].split("||")
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
                            st.image(base64.b64decode(auto["afbeelding"]), use_container_width=True)
                        except Exception:
                            st.error("Fout bij het laden van de afbeelding.")
                else:
                    st.info("Geen afbeelding beschikbaar.")
            
            with col2:
                st.write(f"**ID Nummer:** {auto['id']}")
                st.write(f"**Kilometerstand:** {auto['km_stand']:,} km")
                st.write(f"**Transmissie:** {auto['transmissie'] if auto['transmissie'] else 'Niet opgegeven'}")
                st.write(f"**APK Datum:** {apk_nl}")
                st.write(f"**Inkoopprijs:** €{auto['inkoopprijs']:,.2f}")
                st.write(f"**Extra kosten:** €{auto['extra_kosten']:,.2f}")
                st.write(f"**Verkoopprijs:** €{auto['verkoopprijs']:,.2f}")
                st.write(f"**Verwachte Winst:** €{auto['winst']:,.2f}")
                
                st.write("")
                btn_edit, btn_del = st.columns(2)
                with btn_edit:
                    if st.button("✏️ Gegevens Aanpassen", key=f"edit_inv_{auto['id']}", use_container_width=True, type="primary"):
                        bewerk_auto_dialog(auto["id"], auto["kenteken"], auto["km_stand"], auto["inkoopprijs"], auto["verkoopprijs"], auto["apk_datum"], auto["extra_kosten"], auto["afbeelding"], auto["naam"], auto["transmissie"])
                with btn_del:
                    if st.button("🗑️ Auto Verwijderen", key=f"del_inv_{auto['id']}", use_container_width=True):
                        cursor.execute("DELETE FROM voorraad WHERE id=?", (auto["id"],))
                        conn.commit()
                        st.success(f"Auto succesvol verwijderd!")
                        st.rerun()

import base64
import hmac
import re
import unicodedata
import time
from datetime import datetime, timedelta
import io
import os
import json
import tempfile
from PIL import Image, ImageOps
try:
    # Optioneel: zorgt dat iPhone-foto's (HEIC) ook werken
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
from supabase import create_client

st.set_page_config(page_title="Autohandel Inventaris", layout="wide")


# --- CAMERA-FOTO'S (alternatief voor de bestandskiezer, handig op Android) ---
# Eigen camera-onderdeel dat standaard de ACHTERcamera pakt en die ook na elke foto aan laat staan.
_ACHTER_CAMERA_HTML = r"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  html, body { margin: 0; padding: 0; background: transparent; color: #fff;
               font-family: "Source Sans Pro", -apple-system, "Segoe UI", sans-serif; }
  #wrap { width: 100%; padding: 2px 0 6px 0; }
  #kader { display: none; position: relative; margin: 0 auto; background: #000; border-radius: 8px; overflow: hidden; }
  video { display: block; width: 100%; height: 100%; object-fit: cover; background: #000; }
  canvas { display: none; }
  button { font-size: 16px; border-radius: 8px; cursor: pointer; color: #fff;
           background: rgba(20, 20, 28, 0.92); border: 1px solid rgba(255,255,255,0.3); }
  #b_start { width: 100%; padding: 16px 10px; background: #ff4b4b; border-color: #ff4b4b; font-weight: 600; }
  /* Knoppen liggen OVER het beeld, zodat je altijd het beeld en de knop tegelijk ziet */
  #boven { position: absolute; top: 8px; right: 8px; display: flex; gap: 8px; }
  #boven button { width: 46px; height: 46px; padding: 0; font-size: 20px; background: rgba(0,0,0,0.55); }
  #onder { position: absolute; left: 0; right: 0; bottom: 0; display: flex; justify-content: center;
           padding: 10px; background: linear-gradient(rgba(0,0,0,0), rgba(0,0,0,0.55)); }
  #b_foto { min-width: 190px; padding: 14px 22px; font-weight: 600; background: #ff4b4b; border-color: #ff4b4b; }
  #toast { position: absolute; top: 10px; left: 10px; padding: 6px 10px; border-radius: 8px; font-size: 14px;
           background: rgba(0,0,0,0.6); display: none; }
  #melding { margin-top: 8px; font-size: 14px; min-height: 0; }
  #info { margin-top: 4px; font-size: 11px; color: rgba(255,255,255,0.55); text-align: center; }
</style>
</head>
<body>
<div id="wrap">
  <button id="b_start">📷 Camera starten (achterkant)</button>
  <div id="kader">
    <video id="video" playsinline muted autoplay></video>
    <div id="toast"></div>
    <div id="boven">
      <button id="b_wissel" title="Wissel camera">🔄</button>
      <button id="b_stop" title="Stop camera">✖</button>
    </div>
    <div id="onder"><button id="b_foto">📸 Maak foto</button></div>
  </div>
  <canvas id="canvas"></canvas>
  <div id="info"></div>
  <div id="melding"></div>
</div>
<script>
  function send(type, data) {
    window.parent.postMessage(Object.assign({ isStreamlitMessage: true, type: type }, data || {}), "*");
  }
  var video = document.getElementById("video");
  var kader = document.getElementById("kader");
  var canvas = document.getElementById("canvas");
  var melding = document.getElementById("melding");
  var toast = document.getElementById("toast");
  var bStart = document.getElementById("b_start");
  var stream = null;
  var facing = "environment";   // standaard de camera op de achterkant
  var teller = 0;
  var toastTimer = null;

  function hoogte() { send("streamlit:setFrameHeight", { height: document.documentElement.scrollHeight }); }
  if (window.ResizeObserver) { new ResizeObserver(hoogte).observe(document.body); }

  // Hoogte van het zichtbare scherm van de app (niet van dit kleine kader, om een lus te voorkomen)
  function schermHoogte() {
    var h = 0;
    try { h = window.parent.innerHeight; } catch (e) { h = 0; }
    if (!h) {
      var s = window.screen || {};
      var landschap = window.matchMedia && window.matchMedia("(orientation: landscape)").matches;
      var lang = Math.max(s.width || 0, s.height || 0), kort = Math.min(s.width || 0, s.height || 0);
      h = Math.round((landschap ? kort : lang) * 0.85) || 600;
    }
    return h;
  }

  // Maak het beeldvak precies zo gevormd als het camerabeeld, en bewust klein zodat alles in beeld past
  var laatsteMaat = "";
  function pasFormaatAan() {
    var vw = video.videoWidth, vh = video.videoHeight;
    if (!vw || !vh) { return; }
    var ar = vw / vh;
    var wrapB = document.getElementById("wrap").clientWidth || 300;
    var scherm = schermHoogte();
    var sleutel = vw + "x" + vh + "|" + wrapB + "|" + scherm;
    if (sleutel === laatsteMaat) { return; }   // niets veranderd
    laatsteMaat = sleutel;
    var maxH = Math.max(150, Math.round(scherm * 0.5));   // hoogstens de helft van het scherm
    var maxB = Math.round(wrapB * 0.75);                   // en hoogstens 75% van de breedte
    var b = Math.min(maxB, Math.round(maxH * ar));
    kader.style.width = b + "px";
    kader.style.height = Math.round(b / ar) + "px";
    document.getElementById("info").textContent = "Beeld " + vw + "×" + vh;
    hoogte();
  }
  video.addEventListener("loadedmetadata", pasFormaatAan);
  video.addEventListener("resize", pasFormaatAan);
  window.addEventListener("resize", pasFormaatAan);
  window.addEventListener("orientationchange", pasFormaatAan);
  // Vangnet: controleer elk kwartsecond of de maat nog klopt (telefoons melden draaien niet altijd netjes)
  setInterval(function () { if (stream) { pasFormaatAan(); } }, 250);

  function toon(actief) {
    bStart.style.display = actief ? "none" : "block";
    kader.style.display = actief ? "block" : "none";
    setTimeout(hoogte, 50);
  }

  function stopStream() {
    if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; }
    video.srcObject = null;
  }

  async function start() {
    stopStream();
    melding.textContent = "";
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: facing }, width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false
      });
      video.srcObject = stream;
      laatsteMaat = "";
      toon(true);
      await video.play();
      pasFormaatAan();
    } catch (e) {
      toon(false);
      melding.textContent = "Camera niet beschikbaar: " + ((e && (e.message || e.name)) || e) +
                            ". Geef toestemming voor de camera, of gebruik de reservecamera.";
      hoogte();
    }
  }

  function toonToast(tekst) {
    toast.textContent = tekst;
    toast.style.display = "block";
    if (toastTimer) { clearTimeout(toastTimer); }
    toastTimer = setTimeout(function () { toast.style.display = "none"; }, 1500);
  }

  function maakFoto() {
    var w = video.videoWidth, h = video.videoHeight;
    if (!w || !h) { toonToast("Camera is nog niet klaar"); return; }
    var schaal = Math.min(1, 1920 / Math.max(w, h));
    canvas.width = Math.round(w * schaal);
    canvas.height = Math.round(h * schaal);
    canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
    var data = canvas.toDataURL("image/jpeg", 0.85);
    teller += 1;
    send("streamlit:setComponentValue", { value: { ts: Date.now() + "-" + teller, data: data }, dataType: "json" });
    toonToast("✅ Foto " + teller + " gemaakt");
  }

  bStart.onclick = start;
  document.getElementById("b_foto").onclick = maakFoto;
  document.getElementById("b_wissel").onclick = function () {
    facing = (facing === "environment") ? "user" : "environment";
    start();
  };
  document.getElementById("b_stop").onclick = function () { stopStream(); toon(false); melding.textContent = ""; };
  document.addEventListener("visibilitychange", function () { if (document.hidden && stream) { stopStream(); toon(false); } });

  send("streamlit:componentReady", { apiVersion: 1 });
  hoogte();
</script>
</body>
</html>
"""


@st.cache_resource
def _laad_achtercamera_component():
    """Zet het camera-onderdeel klaar. Geeft None terug als dat niet lukt (dan gebruiken we de standaardcamera)."""
    try:
        map_pad = os.path.join(tempfile.gettempdir(), "autohandel_achtercamera_v1")
        os.makedirs(map_pad, exist_ok=True)
        with open(os.path.join(map_pad, "index.html"), "w", encoding="utf-8") as f:
            f.write(_ACHTER_CAMERA_HTML)
        return components.declare_component("achtercamera_v1", path=map_pad)
    except Exception:
        return None


def _bewaar_camera_foto(prefix):
    """Reservecamera (standaard van Streamlit): bewaar de foto in de lijst."""
    n = st.session_state.get(f"{prefix}_cam_n", 0)
    foto = st.session_state.get(f"{prefix}_cam_{n}")
    if foto is not None:
        st.session_state.setdefault(f"{prefix}_cam_fotos", []).append(foto.getvalue())
        st.session_state[f"{prefix}_cam_n"] = n + 1  # nieuwe, lege camera-widget


def camera_fotos_widget(prefix):
    """Toont een camera-optie en geeft de genomen foto's terug als lijst met bestandsobjecten."""
    st.session_state.setdefault(f"{prefix}_cam_n", 0)
    st.session_state.setdefault(f"{prefix}_cam_fotos", [])
    with st.expander("📸 Foto maken met de camera (werkt het kiezen van foto's niet? Gebruik dit)"):
        crop_16_9 = st.checkbox(
            "Liggende camerafoto's bijsnijden naar 16:9 (houd je telefoon horizontaal)",
            value=True,
            key=f"{prefix}_cam_crop",
        )
        achter_camera = _laad_achtercamera_component()
        reserve = st.checkbox(
            "Reservecamera gebruiken (als de achtercamera niet laadt)",
            value=achter_camera is None,
            key=f"{prefix}_cam_reserve",
        )

        if reserve or achter_camera is None:
            st.camera_input(
                "Maak een foto",
                key=f"{prefix}_cam_{st.session_state[f'{prefix}_cam_n']}",
                on_change=_bewaar_camera_foto,
                args=(prefix,),
            )
        else:
            waarde = achter_camera(key=f"{prefix}_achtercam", default=None)
            if isinstance(waarde, dict) and waarde.get("data") and waarde.get("ts") != st.session_state.get(f"{prefix}_cam_laatste"):
                try:
                    st.session_state[f"{prefix}_cam_fotos"].append(base64.b64decode(waarde["data"].split(",", 1)[1]))
                    st.session_state[f"{prefix}_cam_laatste"] = waarde["ts"]
                except Exception as e:
                    st.error(f"Foto kon niet worden verwerkt: {e}")

        aantal = len(st.session_state[f"{prefix}_cam_fotos"])
        if aantal:
            st.caption(f"✅ {aantal} camerafoto('s) klaar om op te slaan. Maak er nog een of sla op.")
            st.button("🗑️ Camerafoto's wissen", key=f"{prefix}_cam_wis", on_click=camera_fotos_wissen, args=(prefix,))
    bestanden = []
    for b in st.session_state[f"{prefix}_cam_fotos"]:
        bio = io.BytesIO(b)
        bio.crop_16_9 = crop_16_9
        bestanden.append(bio)
    return bestanden


def camera_fotos_wissen(prefix):
    st.session_state[f"{prefix}_cam_fotos"] = []


def veilige_bestandsnaam(tekst, reserve="AUTO"):
    """Maakt van een kenteken/tekst een naam die Supabase Storage accepteert.
    Storage staat alleen simpele tekens toe: letters, cijfers, - en _ (geen accenten zoals Ë)."""
    tekst = unicodedata.normalize("NFKD", str(tekst or ""))
    tekst = tekst.encode("ascii", "ignore").decode("ascii")  # Ë -> E, é -> e, andere tekens vervallen
    tekst = re.sub(r"[^A-Za-z0-9_-]+", "_", tekst).strip("_").upper()
    return tekst or reserve

def foto_naar_jpeg(bestand):
    """Zet een geuploade foto (ook van mobiel) om naar een verkleinde JPEG.
    Geeft bytes terug. Past de camera-rotatie (EXIF) toe zodat foto's niet kantelen."""
    bestand.seek(0)
    img = Image.open(bestand)
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    # Camerafoto's: liggende foto's in het midden bijsnijden naar 16:9 (staande foto's blijven heel)
    if getattr(bestand, "crop_16_9", False) and img.width > img.height:
        breedte, hoogte = img.size
        if breedte / hoogte < 16 / 9:
            nieuwe_hoogte = round(breedte * 9 / 16)
            boven = (hoogte - nieuwe_hoogte) // 2
            img = img.crop((0, boven, breedte, boven + nieuwe_hoogte))
        else:
            nieuwe_breedte = round(hoogte * 16 / 9)
            links = (breedte - nieuwe_breedte) // 2
            img = img.crop((links, 0, links + nieuwe_breedte, hoogte))
    img.thumbnail((1000, 1000))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=75)
    return buffer.getvalue()


# --- SUPABASE VERBINDING INSTELLEN ---
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()
# --- GECACHED DATA OPHALEN (NIEUW & SNELLER) ---
@st.cache_data(ttl=300)  # Slaat data 5 minuten op in het geheugen, tenzij handmatig geleegd
def haal_voorraad_op():
    return supabase.table("voorraad").select("*").execute().data

@st.cache_data(ttl=300)
def haal_agenda_op():
    return supabase.table("agenda").select("*").execute().data

@st.cache_data(ttl=300)
def haal_stat_rijen_op():
    return supabase.table("voorraad").select("inkoopprijs, verkoopprijs, extra_kosten, status").execute().data

# --- STYLING & ACHTERGROND ---
@st.cache_data(show_spinner=False)
def _logo_als_base64(logo_path, wijzigingstijd):
    """Leest het logo één keer in en bewaart de base64-tekst in het geheugen.
    De wijzigingstijd zorgt dat een vervangen logo.png meteen opnieuw wordt ingelezen."""
    with open(logo_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def zet_achtergrond(logo_path="logo.png"):
    if os.path.exists(logo_path):
        encoded = _logo_als_base64(logo_path, os.path.getmtime(logo_path))
        
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
        /* Zorgt dat tabellen de volledige containerbreedte benutten */
        .stTable, div[data-testid="stTable"] {{ width: 100% !important; }}
        .stTable table {{ width: 100% !important; }}
        
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
        
        /* Zorgt dat de agenda-sectie een strak frame krijgt met een scrollbalk */
        #agenda-container {{
            max-height: 900px !important;
            overflow-y: auto !important;
            padding-right: 5px;
        }}
        iframe[title="streamlit_calendar.calendar"] {{
            height: 850px !important;
        }}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)

zet_achtergrond("logo.png")

# --- BEVEILIGING ---
MAX_FOUTE_POGINGEN = 5
BLOKKADE_SECONDEN = 300  # 5 minuten

@st.cache_resource
def _login_status():
    """Wordt gedeeld door alle bezoekers, zodat een nieuw tabblad de blokkade niet omzeilt."""
    return {"fouten": 0, "geblokkeerd_tot": 0.0}

if "ingelogd" not in st.session_state:
    st.session_state["ingelogd"] = False

if not st.session_state["ingelogd"]:
    st.title("🔒 Beveiligde Toegang")
    st.write("Voer het wachtwoord in om toegang te krijgen tot de autohandel inventaris.")

    login_status = _login_status()
    nu = time.time()
    if nu < login_status["geblokkeerd_tot"]:
        minuten = int((login_status["geblokkeerd_tot"] - nu) // 60) + 1
        st.error(f"🚫 Te veel foute pogingen. Inloggen is tijdelijk geblokkeerd. Probeer het over ongeveer {minuten} minuut opnieuw.")
        st.stop()

    wachtwoord_invoer = st.text_input("Wachtwoord", type="password")
    if st.button("Inloggen", type="primary"):
        veilig_wachtwoord = st.secrets.get("PASSWORD")

        if not veilig_wachtwoord:
            st.error("🚨 Systeemfout: Geen wachtwoord ingesteld in Streamlit Secrets.")
        elif hmac.compare_digest(wachtwoord_invoer.encode("utf-8"), str(veilig_wachtwoord).encode("utf-8")):
            login_status["fouten"] = 0
            st.session_state["ingelogd"] = True
            st.success("Succesvol ingelogd!")
            st.rerun()
        else:
            login_status["fouten"] += 1
            if login_status["fouten"] >= MAX_FOUTE_POGINGEN:
                login_status["fouten"] = 0
                login_status["geblokkeerd_tot"] = time.time() + BLOKKADE_SECONDEN
                st.error("🚫 Te veel foute pogingen. Inloggen is 5 minuten geblokkeerd.")
            else:
                over = MAX_FOUTE_POGINGEN - login_status["fouten"]
                st.error(f"Onjuist wachtwoord. Nog {over} poging(en) over voordat inloggen tijdelijk wordt geblokkeerd.")
    st.stop()

    
# --- RDW TRANSMISSIE VIA TYPEGOEDKEURING ---
def rdw_transmissie_via_typegoedkeuring(voertuig, headers):
    """Zoekt de transmissie op in de RDW-dataset 'TGK Versnelling Uitvoering' (7rjk-eycs).
    Koppeling: typegoedkeuringsnummer + variant + uitvoering uit de basistabel.
    Codes volgens RDW: H = handgeschakeld, A = automaat, C = continu variabel (CVT).
    Geeft (transmissie, toelichting) terug. Bij twijfel: 'Onbekend'."""
    tgk = str(voertuig.get("typegoedkeuringsnummer", "")).strip()
    variant = str(voertuig.get("variant", "")).strip()
    uitvoering = str(voertuig.get("uitvoering", "")).strip()
    if not (tgk and variant and uitvoering):
        return "Onbekend", "Geen typegoedkeuringsgegevens bij dit kenteken"

    try:
        res = requests.get(
            "https://opendata.rdw.nl/resource/7rjk-eycs.json",
            params={
                "typegoedkeuringsnummer": tgk,
                "codevarianttgk": variant,
                "codeuitvoeringtgk": uitvoering,
            },
            headers=headers,
            timeout=8,
        )
        if res.status_code != 200:
            return "Onbekend", f"RDW typegoedkeuring-tabel gaf status {res.status_code}"
        rijen = res.json()
    except Exception as e:
        return "Onbekend", f"Typegoedkeuring-tabel niet bereikbaar ({e})"

    if not isinstance(rijen, list) or not rijen:
        return "Onbekend", "Geen versnellingsbak-gegevens gevonden bij de typegoedkeuring"

    codes = {str(r.get("codetypeversnellingsbak", "")).strip().upper() for r in rijen}
    codes.discard("")

    vertaling = {"H": "Handgeschakeld", "A": "Automaat", "C": "Automaat"}
    soorten = {vertaling[c] for c in codes if c in vertaling}

    if len(soorten) == 1 and codes <= set(vertaling):
        return soorten.pop(), f"RDW typegoedkeuring (code {', '.join(sorted(codes))})"
    if len(soorten) > 1:
        return "Onbekend", "Typegoedkeuring omvat zowel handgeschakeld als automaat"
    return "Onbekend", f"Onbekende RDW-code(s): {', '.join(sorted(codes)) or 'leeg'}"


# --- RDW KOPPELING ---
def overheid_rdw_lookup_krachtig(kenteken_str):
    schoon = kenteken_str.replace("-", "").upper().strip()
    if not schoon:
        return None
    
    veilig_kenteken = requests.utils.quote(schoon)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json"
    }
    
    # 1. API URL voor de basis voertuiggegevens
    url_voertuig = f"https://opendata.rdw.nl/resource/m9d7-ebf2.json?kenteken={veilig_kenteken}"
    # 2. API URL voor de brandstofgegevens (Aparte RDW tabel)
    url_brandstof = f"https://opendata.rdw.nl/resource/8ys7-d773.json?kenteken={veilig_kenteken}"
    
    try:
        # Haal eerst de basisgegevens op
        res_v = requests.get(url_voertuig, headers=headers, timeout=8)
        if res_v.status_code != 200:
            return {"fout": f"RDW Server foutmelding basisgegevens. Statuscode: {res_v.status_code}."}
            
        if "application/json" not in res_v.headers.get("Content-Type", ""):
            return {"fout": "RDW stuurde een onverwacht antwoordformaat. Probeer het opnieuw."}
            
        data_v = res_v.json()
        if not (isinstance(data_v, list) and len(data_v) > 0):
            return {"fout": "Kenteken niet gevonden in het openbare RDW-register."}
            
        voertuig = data_v[0]
        merk = voertuig.get("merk", "").title()
        model = voertuig.get("handelsbenaming", "").title()
        volledige_naam = f"{merk} {model}".strip()
        kleur = voertuig.get("eerste_kleur", "Onbekend").title()
        cataloguswaarde = naar_getal(voertuig.get("catalogusprijs", 0.0))

        # --- NIEUW: TRANSMISSIE UITLEZEN UIT DE HOOFDTABEL ---
        # De RDW gebruikt vaak verschillende veldnamen per voertuigtype voor de versnellingsbak
        # --- SLIMMERE TRANSMISSIE-CHECK (INCLUSIEF INRICHTING EN TYPEVOERTUIG) ---
        # We halen alle mogelijke plekken op waar de RDW de transmissie kan verstoppen
        # De transmissie staat niet in de basistabel, maar wel in de typegoedkeuring-gegevens.
        transmissie_gevonden, transmissie_bron = rdw_transmissie_via_typegoedkeuring(voertuig, headers)
        # ------------------------------------------------------------------------


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

        # NU: Haal de brandstofgegevens op uit de tweede tabel
        brandstof = "Benzine"  # Standaard fallback
        res_b = requests.get(url_brandstof, headers=headers, timeout=8)
        if res_b.status_code == 200:
            data_b = res_b.json()
            if isinstance(data_b, list) and len(data_b) > 0:
                brandstof = data_b[0].get("brandstof_omschrijving", "Benzine").title()
                if brandstof == "Elektriciteit":
                    brandstof = "Elektrisch"
                    transmissie_gevonden = "Automaat" # Elektrische auto's zijn altijd automaat
                    transmissie_bron = "Elektrische auto"
                        
        return {
            "naam": volledige_naam if volledige_naam else "Onbekend voertuig",
            "apk": apk_formatted,
            "brandstof": brandstof,
            "transmissie": transmissie_gevonden, # <-- DIT STUURT DE TRANSMISSIE MEE
            "transmissie_bron": transmissie_bron,
            "bouwjaar": bouwjaar,
            "kleur": kleur,
            "cataloguswaarde": cataloguswaarde,
            "fout": None
        }

        
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
            
        st.cache_data.clear()  # Wist de cache netjes na het importeren van een back-up
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

    # --- INGEBOUWDE VEILIGHEIDSCHECK VOOR DE SPLIT ---
    standaard_aankoopdatum = datetime.today().date()
    if foto_huidig and "AANKOOPDATUM:" in str(foto_huidig):
        try:
            # OUD: deel_datum = onderdelen[1].split("||").strip()
            # NIEUW (Gecorrigeerd met de missende split):
            onderdelen = str(foto_huidig).split("AANKOOPDATUM:")
            if len(onderdelen) > 1:
                deel_datum = onderdelen[1].split("||")[0].strip()
                standaard_aankoopdatum = datetime.strptime(deel_datum, "%Y-%m-%d").date()
        except:
            pass

    # --- FOTO'S: bewust BUITEN het formulier, zodat de selectie op mobiel bewaard blijft ---
    if uploader_key not in st.session_state:
        st.session_state[uploader_key] = 0

    edit_fotos = st.file_uploader(
        "📷 Nieuwe foto's toevoegen (kies ze eerst hier)",
        accept_multiple_files=True,
        key=f"{uploader_key}_{st.session_state[uploader_key]}"
    )
    if edit_fotos:
        st.caption(f"✅ {len(edit_fotos)} foto('s) geselecteerd. Ze worden opgeslagen als je op 'Wijzigingen Live Opslaan' drukt.")
    camera_edit_fotos = camera_fotos_widget(f"edit_{actie_id}")

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

        # --- TRANSMISSIE: begint bij de opgeslagen waarde van deze auto ---
        trans_opties = ["Onbekend", "Handgeschakeld", "Automaat"]
        if trans_huidig and trans_huidig not in trans_opties:
            trans_opties.append(trans_huidig)
        edit_trans = st.selectbox(
            "Pas Transmissie aan",
            options=trans_opties,
            index=trans_opties.index(trans_huidig) if trans_huidig in trans_opties else 0,
            key=f"edit_trans_{actie_id}"
        )

        edit_aankoopdatum = st.date_input("Pas Datum aankoop aan", value=standaard_aankoopdatum, format="DD-MM-YYYY")
        
        col_e7, col_e8, col_e9 = st.columns(3)
        edit_inkoop = col_e7.number_input("Pas Inkoopprijs aan (€)", value=float(inkoop), step=50.0)
        edit_verkoop = col_e8.number_input("Pas Verkoopprijs aan (€)", value=float(verkoop), step=50.0)
        edit_kosten = col_e9.number_input("Pas Extra kosten aan (€)", value=float(kosten), step=10.0)
        
        verwijder_fotos = st.checkbox("🗑️ Alle huidige foto's permanent wissen", value=False)
        
        submit_edit = st.form_submit_button("💾 Wijzigingen Live Opslaan", type="primary", width="stretch")
        
        if submit_edit:
            if edit_ktk.strip():
                basis_fotos = []
                if not verwijder_fotos and foto_huidig:
                    for element in foto_huidig.split("||"):
                        if element and "AANKOOPDATUM:" not in element and element.startswith("http"):
                            basis_fotos.append(element)

                alle_edit_fotos = list(edit_fotos or []) + camera_edit_fotos
                if alle_edit_fotos:
                    for idx, f in enumerate(alle_edit_fotos):
                        try:
                            jpeg_bytes = foto_naar_jpeg(f)
                            
                            bestandsnaam = f"{veilige_bestandsnaam(edit_ktk)}_edit_{idx}_{int(datetime.today().timestamp())}.jpg"
                            supabase.storage.from_("autofotos").upload(path=bestandsnaam, file=jpeg_bytes, file_options={"content-type": "image/jpeg"})
                            openbare_url = supabase.storage.from_("autofotos").get_public_url(bestandsnaam)
                            basis_fotos.append(openbare_url)
                        except Exception as e:
                            # STOP DIRECT EN TOON DE FOUTMELDING (Geen st.rerun)
                            st.error(f"🚨 Cloud Upload Mislukt: {str(e)}")
                            return
                
                datum_prefix = f"AANKOOPDATUM:{edit_aankoopdatum.strftime('%Y-%m-%d')}"
                basis_fotos.insert(0, datum_prefix)
                foto_opslaan = "||".join(basis_fotos)

                update_data = {
                    "naam": edit_naam, "kenteken": edit_ktk.upper().replace("-", "").strip(),
                    "km_stand": int(edit_km), "apk_datum": str(edit_apk), "transmissie": edit_trans,
                    "inkoopprijs": float(edit_inkoop), "verkoopprijs": float(edit_verkoop),
                    "extra_kosten": float(edit_kosten), "afbeelding": foto_opslaan, "status": edit_status,
                    "brandstof": edit_brandstof, "bouwjaar": int(edit_bouwjaar), "kleur": edit_kleur,
                    "cataloguswaarde": float(edit_cat)
                }

                supabase.table("voorraad").update(update_data).eq("id", actie_id).execute()
                
                # Hoog de teller op om de uploader-state netjes te resetten na succesvolle opslag
                st.session_state[uploader_key] += 1
                camera_fotos_wissen(f"edit_{actie_id}")
                
                st.cache_data.clear()
                st.rerun()


# --- DIALOG KOOPOVEREENKOMST ---

@st.dialog("📄 Particuliere Koopovereenkomst Genereren")
def genereer_contract_dialog(auto_id, merk_model, kenteken, km, verkoop, apk):
    st.write("Vul de gegevens van de koper in om de officiële koopovereenkomst te genereren.")
    koper_naam = st.text_input("Naam / Bedrijfsnaam Koper")
    koper_adres = st.text_input("Adres & Huisnummer Koper")
    koper_postcode = st.text_input("Postcode & Woonplaats Koper")
    koper_tel = st.text_input("Telefoonnummer Koper")
    koper_legit = st.text_input("Legitimatie Koper (Type/Nr)", placeholder="Bijv. Rijbewijs / Nummer")
    
    st.markdown("---")
    st.write("**Financiële Afspraken & Levering:**")
    betaalwijze = st.radio("Wijze van betaling:", ["Contant", "Per bankoverschrijving"], horizontal=True)
    datum_levering = st.date_input("Datum van levering", value=datetime.today().date(), format="DD-MM-YYYY")
    bijzondere_afspraken = st.text_area("Aanvullende afspraken (Bijv. inruil, extra onderdelen)", value="Geen.")

    if st.button("🔥 Contract Downloaden", type="primary", width="stretch"):
        if not koper_naam.strip():
            st.error("Vul tenminste de naam van de koper in.")
            return

        try:
            km_veilig_getal = int(float(km))
        except:
            km_veilig_getal = 0

        contant_vink = "[X]" if betaalwijze == "Contant" else "[  ]"
        bank_vink = "[X]" if betaalwijze == "Per bankoverschrijving" else "[  ]"
        huidige_datum_formatted = datetime.today().strftime('%d-%m-%Y')
        levering_formatted = datum_levering.strftime('%d-%m-%Y')

        html_content = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; color: #000; padding: 10px; line-height: 1.4; font-size: 13px; }}
                h2 {{ text-align: center; font-size: 18px; margin-bottom: 5px; text-transform: uppercase; letter-spacing: 0.5px; }}
                .sub-header {{ text-align: center; font-size: 11px; font-style: italic; margin-bottom: 15px; color: #444; }}
                h3 {{ font-size: 14px; border: 1px solid #000; padding: 4px 8px; margin-top: 15px; margin-bottom: 8px; background-color: #fcfcfc; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 5px; }}
                td {{ padding: 4px 0; vertical-align: top; }}
                .label {{ width: 180px; font-weight: bold; }}
                .juridisch-text {{ font-size: 11px; color: #222; text-align: justify; margin-top: 5px; margin-bottom: 5px; }}
                .signature-table {{ width: 100%; margin-top: 15px; }}
                .signature-table td {{ border: 1px solid #ccc; padding: 10px; width: 50%; }}
                .footer-notice {{ text-align: center; font-size: 9px; color: #777; margin-top: 25px; border-top: 1px solid #eee; padding-top: 5px; }}
            </style>
        </head>
        <body>
            <h2>PARTICULIERE KOOPOVEREENKOMST AUTO</h2>
            <div class="sub-header">(Margevoertuig / Zonder Garantie)</div>
            <div class="juridisch-text">Ondergetekenden komen overeen dat de verkoper het hieronder omschreven voertuig verkoopt aan de koper tegen de overengekomen prijs. Deze verkoop geschiedt tussen twee particulieren. De koper verklaart het voertuig te hebben geïnspecteerd en te accepteren in de huidige staat.</div>
            
            <h3>1. Gegevens van de Verkoper</h3>
            <table>
                <tr><td class="label">Naam / Bedrijfsnaam:</td><td>MT Automotive</td></tr>
                <tr><td class="label">Adres & Huisnummer:</td><td>Kanaalstraat 83</td></tr>
                <tr><td class="label">Postcode & Woonplaats:</td><td>5104 AB Dongen</td></tr>
            </table>
            
            <h3>2. Gegevens van de Koper</h3>
            <table>
                <tr><td class="label">Naam:</td><td>{koper_naam}</td></tr>
                <tr><td class="label">Adres & Huisnummer:</td><td>{koper_adres}</td></tr>
                <tr><td class="label">Postcode & Woonplaats:</td><td>{koper_postcode}</td></tr>
                <tr><td class="label">Telefoonnummer:</td><td>{koper_tel}</td></tr>
                <tr><td class="label">Legitimatie (Type/Nr):</td><td>{koper_legit}</td></tr>
            </table>
            
            <h3>3. Voertuiggegevens</h3>
            <table style="width: 100%;">
                <tr>
                    <td class="label">Merk & Model:</td><td>{merk_model}</td>
                    <td class="label" style="padding-left: 20px;">Kenteken:</td><td>{kenteken}</td>
                </tr>
                <tr>
                    <td class="label">Tellerstand:</td><td>{km_veilig_getal:,} km</td>
                    <td class="label" style="padding-left: 20px;">APK geldig tot:</td><td>{formatteer_datum_nl(apk)}</td>
                </tr>
            </table>
            
            <h3>4. Financiële Afspraken & Levering</h3>
            <table>
                <tr><td class="label">Overengekomen prijs:</td><td>&euro;&nbsp;{formatteer_euro_nl(verkoop)}</td></tr>
                <tr><td class="label">Wijze van betaling:</td><td>{contant_vink} Contant &nbsp;&nbsp; {bank_vink} Per bankoverschrijving</td></tr>
                <tr><td class="label">Datum van levering:</td><td>{levering_formatted}</td></tr>
            </table>
            <div class="juridisch-text">De verkoper verklaart dat het voertuig vrij is van beslagen, boetes en/of andere financiële claims tot het hierboven genoemde tijdstip van overdracht. Eventuele boetes of belastingen na dit tijdstip komen volledig voor rekening van de koper.</div>
            
            <h3>5. Bijzondere Afspraken & Garantie-uitsluiting</h3>
            <div class="juridisch-text" style="font-weight: bold;">Garantieclausule (Gekocht in de huidige staat):</div>
            <div class="juridisch-text">Het voertuig wordt door de koper gekocht in de staat waarin het zich op de datum van verkoop bevindt ("as is, where is"). Beide partijen verklaren nadrukkelijk dat er sprake is van een particuliere transactie. De verkoper verleent geen enkele vorm van garantie op mechanische, elektrische of optische onderdelen, noch op verborgen gebreken, tenzij hieronder schriftelijk anders is overengekomen.</div>
            <div class="juridisch-text"><b>Aanvullende afspraken:</b> {bijzondere_afspraken if bijzondere_afspraken.strip() else 'Geen.'}</div>
            
            <h3>6. Handtekening voor Akkoord</h3>
            <table class="signature-table">
                <tr>
                    <td>
                        <b>Handtekening Verkoper:</b><br><br><br><br>
                        Datum: {levering_formatted}
                    </td>
                    <td>
                        <b>Handtekening Koper:</b><br><br><br><br>
                        Datum: {levering_formatted}
                    </td>
                </tr>
            </table>
            
            <div class="footer-notice">This contract is generated for informational purposes. Financial terms should comply with local guidelines. AI systems may generate unexpected outputs; check physical details before signing.</div>
        </body>
        </html>
        """
        b64 = base64.b64encode(html_content.encode('utf-8')).decode()
        filename = f"Koopovereenkomst_{veilige_bestandsnaam(kenteken)}_{huidige_datum_formatted}.html"
        href = f'<a href="data:text/html;base64,{b64}" download="{filename}" style="display:block; text-align:center; background-color:#28a745; color:white; padding:10px; border-radius:8px; text-decoration:none; font-weight:bold;">📥 Download Overeenkomst</a>'
        st.markdown(href, unsafe_allow_html=True)


# --- SIDEBAR NAVIGATIE ---
with st.sidebar:
    st.title("⚙️ Navigatie")
    menu_optie = st.sidebar.radio(
        "Kies een functie:",
        ["🆕 Nieuwe auto toevoegen", "🟢 Actuele Voorraad", "🔴 Verkochte Voertuigen", "📦 Artikelen", "📅 Agenda & Notities", "💰 Financieel Overzicht"]
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
            width="stretch"
        )
    except:
        st.error("Export mislukt")

    geimporteerd_bestand = st.file_uploader("📥 Importeer Data naar Cloud", type=["json"])
    if geimporteerd_bestand is not None:
        json_data = geimporteerd_bestand.getvalue().decode("utf-8")
        if st.button("🔄 Herstel cloud-database nu", type="primary", width="stretch"):
            if importeer_json_naar_database(json_data):
                st.toast("⚡ Cloud-database succesvol hersteld!", icon="✅")
                st.rerun()

    st.markdown("---")
    if st.button("🚪 Uitloggen", width="stretch"):
        st.session_state["ingelogd"] = False
        st.rerun()

# --- VEILIGE BALANS BEREKENING (LIVE CLOUD) ---
stat_rijen = haal_stat_rijen_op()

autos_in_voorraad = [r for r in stat_rijen if r['status'] != 'Verkocht']
autos_verkocht = [r for r in stat_rijen if r['status'] == 'Verkocht']

totale_voorraadwaarde = sum(float(r['inkoopprijs'] or 0) + float(r['extra_kosten'] or 0) for r in autos_in_voorraad)
gerealiseerde_winst = sum(float(r['verkoopprijs'] or 0) - (float(r['inkoopprijs'] or 0) + float(r['extra_kosten'] or 0)) for r in autos_verkocht)

if "startbudget" not in st.session_state:
    st.session_state["startbudget"] = 10000.0

# Haal de artikelen op om de totale investering hierin te berekenen
try:
    artikelen_res = supabase.table("artikelen").select("aantal, prijs_per_stuk").execute().data
    totale_waarde_artikelen = sum(int(item["aantal"] or 0) * float(item["prijs_per_stuk"] or 0) for item in artikelen_res)
except:
    totale_waarde_artikelen = 0.0

# Trek nu OOK de waarde van de losse artikelen af van het vrije budget
actueel_vrij_budget = st.session_state["startbudget"] - totale_voorraadwaarde + gerealiseerde_winst - totale_waarde_artikelen

# --- NIEUWE AUTO TOEVOEGEN ---
if menu_optie == "🆕 Nieuwe auto toevoegen":
    st.title("🆕 Nieuwe auto toevoegen")
    
    rdw_col1, rdw_col2 = st.columns(2, vertical_alignment="bottom")
    rdw_kenteken = rdw_col1.text_input("Snel RDW via kenteken", placeholder="Bijv. 47-LV-JV").upper().replace("-", "")

    with rdw_col2:
        klik_rdw = st.button("🔍 RDW Gegevens Ophalen", width="stretch")

    if klik_rdw and rdw_kenteken:
        rdw_data = overheid_rdw_lookup_krachtig(rdw_kenteken)
        if rdw_data and rdw_data.get("fout") is None:
            st.session_state["rdw_naam"] = rdw_data["naam"]
            st.session_state["rdw_apk"] = rdw_data["apk"]
            st.session_state["rdw_brandstof"] = rdw_data["brandstof"]
            st.session_state["rdw_transmissie"] = rdw_data["transmissie"]
            st.session_state["rdw_transmissie_bron"] = rdw_data.get("transmissie_bron", "")
            st.session_state["rdw_bouwjaar"] = rdw_data["bouwjaar"]
            st.session_state["rdw_kleur"] = rdw_data["kleur"]
            st.session_state["rdw_cataloguswaarde"] = rdw_data["cataloguswaarde"]
            st.session_state["rdw_ktk"] = rdw_kenteken
            st.toast("⚡ RDW succesvol geladen!", icon="✅")
        elif rdw_data and rdw_data.get("fout"): 
            st.error(rdw_data["fout"])

    # --- FOTO'S: bewust BUITEN het formulier, zodat de selectie op mobiel bewaard blijft ---
    if "nieuw_auto_uploader_key" not in st.session_state:
        st.session_state["nieuw_auto_uploader_key"] = 0

    gevoegde_fotos = st.file_uploader(
        "📷 Foto's (optioneel, kies ze eerst hier)",
        accept_multiple_files=True,
        key=f"nieuwe_auto_fotos_{st.session_state['nieuw_auto_uploader_key']}"
    )
    if gevoegde_fotos:
        st.caption(f"✅ {len(gevoegde_fotos)} foto('s) geselecteerd. Ze worden opgeslagen als je op 'Voeg toe aan huidige voorraad' drukt.")
    camera_nieuwe_fotos = camera_fotos_widget("nieuw")

    with st.form("auto_form", clear_on_submit=False):
        naam = st.text_input("Naam / Omschrijving", value=st.session_state.get("rdw_naam", ""))
        kenteken = st.text_input("Kenteken (Verplicht)", value=st.session_state.get("rdw_ktk", ""))
        
        # --- DIT STUK STOND ER VOORHEEN EN IS NU TERUGGEZET ---
        c_form1, c_form2 = st.columns(2)
        km_stand_str = c_form1.number_input("Kilometerstand", value=0, step=1)
        apk_datum = c_form2.date_input("APK Datum", value=st.session_state.get("rdw_apk", datetime.today().date()), format="DD-MM-YYYY")

        # --- JOUW SCHONE BRANDSTOFBLOK (RECHTSTREEKS GEKOPPELD AAN DE RDW KEY) ---
        c_form3, c_form4 = st.columns(2)
        brandstof_opties = ["Benzine", "Diesel", "Hybride", "Elektrisch", "Lpg"]
        
        # 1. Zorg dat de sleutel altijd bestaat in de session state om fouten te voorkomen
        if "rdw_brandstof" not in st.session_state:
            st.session_state["rdw_brandstof"] = "Benzine"
            
        # 2. Als de RDW een waarde stuurt die niet in de basijst staat, voegen we deze toe
        rdw_waarde = st.session_state["rdw_brandstof"]
        if rdw_waarde and rdw_waarde not in brandstof_opties:
            brandstof_opties.append(rdw_waarde)
            
        standaard_index = brandstof_opties.index(rdw_waarde) if rdw_waarde in brandstof_opties else 0
            
        # 3. Door key="rdw_brandstof" te gebruiken, luistert deze dropdown LIVE naar de RDW-knop!
        c_form3.selectbox(
            "Brandstof", 
            options=brandstof_opties, 
            index=standaard_index,
            key="rdw_brandstof"  # <-- DIT IS DE CRUCIALE LINK MET DE RDW KNOP
        )
        
        # 4. Koppel de variabele voor de database-insert (regel 299) aan de actuele widgetwaarde
        brandstof_invoer = st.session_state["rdw_brandstof"]
        
        # 5. Sluit direct aan met het bouwjaar
        bouwjaar_invoer = c_form4.number_input("Bouwjaar", value=int(st.session_state.get("rdw_bouwjaar", 0)), step=1)
        # --- EINDE VAN DE RECENTE GEGEVENS ---


        c_form5, c_form6 = st.columns(2)
        kleur_invoer = c_form5.text_input("Kleur", value=st.session_state.get("rdw_kleur", ""))

        cat_invoer = c_form6.number_input("Oorspronkelijke Cataloguswaarde (€)", value=float(st.session_state.get("rdw_cataloguswaarde", 0.0)), step=50.0)

        # --- TRANSMISSIE DROPDOWN LIVE KOPPELEN AAN DE RDW KEY ---
        trans_opties = ["Onbekend", "Handgeschakeld", "Automaat"]
        
        # 1. Zorg dat de sleutel altijd bestaat in de session state om fouten te voorkomen
        if "rdw_transmissie" not in st.session_state:
            st.session_state["rdw_transmissie"] = "Onbekend"
            
        actuele_trans = st.session_state["rdw_transmissie"]
        trans_index = trans_opties.index(actuele_trans) if actuele_trans in trans_opties else 0
        
        # 2. De dropdown luistert nu live via de key naar de RDW-knop!
        transmissie = st.selectbox(
            "Transmissie", 
            options=trans_opties, 
            index=trans_index,
            key="rdw_transmissie" # <-- DIT KOPPELT HEM VISUEEL
        )
        if st.session_state.get("rdw_transmissie_bron"):
            st.caption(f"ℹ️ Transmissie: {st.session_state['rdw_transmissie_bron']}. Controleer dit altijd even bij de auto zelf.")
        # --- EINDE VAN DE TRANSMISSIE CORRECTIE ---

        status_invoer = st.selectbox("Status bij instroom", options=["In voorraad", "Gereserveerd"])
        
        # --- NIEUW: Handmatige datumkiezer voor aankoop (staat standaard op vandaag) ---
        aankoop_datum_invoer = st.date_input("Datum aankoop", value=datetime.today().date(), format="DD-MM-YYYY")
        
        c_form7, c_form8, c_form9 = st.columns(3)
        inkoopprijs_val = c_form7.number_input("Inkoopprijs (€)", value=0.0, step=50.0)

        verkoopprijs_val = c_form8.number_input("Verkoopprijs (€)", value=0.0, step=50.0)
        extra_kosten_val = c_form9.number_input("Extra kosten (€)", value=0.0, step=10.0)
        
        submit = st.form_submit_button("Voeg toe aan huidige voorraad")

    if submit and kenteken.strip():
        foto_urls = []
        upload_fouten = []
        alle_nieuwe_fotos = list(gevoegde_fotos or []) + camera_nieuwe_fotos
        if alle_nieuwe_fotos:
            for idx, f in enumerate(alle_nieuwe_fotos):
                try:
                    jpeg_bytes = foto_naar_jpeg(f)
                    
                    # Maak een unieke bestandsnaam voor de cloud-map
                    bestandsnaam = f"{veilige_bestandsnaam(kenteken)}_{idx}_{int(datetime.today().timestamp())}.jpg"
                    
                    # Upload het bestand rechtstreeks naar de Supabase Storage Bucket
                    supabase.storage.from_("autofotos").upload(
                        path=bestandsnaam,
                        file=jpeg_bytes,
                        file_options={"content-type": "image/jpeg"}
                    )
                    
                    # Haal de openbare internetlink (URL) op
                    openbare_url = supabase.storage.from_("autofotos").get_public_url(bestandsnaam)
                    foto_urls.append(openbare_url)
                except Exception as e:
                    upload_fouten.append(f"Foto {idx + 1}: {str(e)}")

        if upload_fouten:
            # Stop hier: anders wordt de auto zonder foto's opgeslagen en verdwijnt de foutmelding door de rerun
            st.error("🚨 Cloud upload mislukt, de auto is NIET opgeslagen. " + " | ".join(upload_fouten))
            st.stop()

        foto_string_data = "||".join(foto_urls)
        datum_prefix = f"AANKOOPDATUM:{aankoop_datum_invoer.strftime('%Y-%m-%d')}"
        totaal_opslaan_string = f"{datum_prefix}||{foto_string_data}" if foto_string_data else datum_prefix

        nieuw_voertuig = {
            "naam": naam, "kenteken": kenteken.upper().replace("-", "").strip(), "km_stand": int(km_stand_str),
            "inkoopprijs": float(inkoopprijs_val), "verkoopprijs": float(verkoopprijs_val), "apk_datum": str(apk_datum),
            "extra_kosten": float(extra_kosten_val), "afbeelding": totaal_opslaan_string, "transmissie": transmissie,
            "status": status_invoer, "brandstof": brandstof_invoer, "bouwjaar": int(bouwjaar_invoer), "kleur": kleur_invoer, "cataloguswaarde": float(cat_invoer)
        }


        supabase.table("voorraad").insert(nieuw_voertuig).execute()
        st.session_state["nieuw_auto_uploader_key"] += 1
        camera_fotos_wissen("nieuw")
        st.cache_data.clear()
        for sleutel in ["rdw_naam", "rdw_ktk", "rdw_apk", "rdw_brandstof", "rdw_bouwjaar", "rdw_kleur", "rdw_cataloguswaarde"]:
            if sleutel in st.session_state: del st.session_state[sleutel]
        st.success("Auto succesvol toegevoegd met cloud-foto's!")
        st.rerun()


elif menu_optie in ["🟢 Actuele Voorraad", "🔴 Verkochte Voertuigen"]:
    st.title(menu_optie)
    
    alle_autos = haal_voorraad_op()

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
            inv_col3.download_button(label="📊 Excel Export", data=towrite, file_name="inventaris.xlsx", width="stretch")
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

                with st.expander(f"{status_icoon} [{auto['status']}] {auto['naam'] or 'Onbekend'} ({auto['kenteken']}) - €\u00a0{formatteer_euro_nl(auto['verkoopprijs'])}{apk_waarschuwing}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        if auto["afbeelding"]:
                            alle_elementen = auto["afbeelding"].split("||")
                            # Filter de datum eruit, de rest zijn pure internet-URL's naar je bucket
                            alle_foto_links = [x for x in alle_elementen if "AANKOOPDATUM:" not in x and x.startswith("http")]
                            
                            if alle_foto_links:
                                foto_cols = st.columns(min(len(alle_foto_links), 3))
                                for idx, url in enumerate(alle_foto_links):
                                    with foto_cols[idx % min(len(alle_foto_links), 3)]:
                                        # Laad de foto bliksemsnel in rechtstreeks vanaf de Supabase CDN link
                                        st.markdown(f'<img src="{url}" style="width:100%; aspect-ratio:16/9; object-fit:contain; background-color:rgba(15,15,20,0.85); border-radius:8px; display:block;">', unsafe_allow_html=True)
                            else:
                                st.info("Geen afbeelding beschikbaar.")
                        else:
                            st.info("Geen afbeelding beschikbaar.")

                    with c2:
                        try: km_veilig = int(float(auto['km_stand']))
                        except: km_veilig = 0
                        try: bouwjaar_veilig = int(float(auto['bouwjaar']))
                        except: bouwjaar_veilig = 0
                        try: cat_veilig = float(auto['cataloguswaarde'])
                        except: cat_veilig = 0.0

                        aankoop_datum_tekst = "Onbekend"
                        if auto["afbeelding"] and "AANKOOPDATUM:" in str(auto["afbeelding"]):
                            try:
                                ruwe_datum = str(auto["afbeelding"]).split("AANKOOPDATUM:")[1].split("||")[0].strip()
                                aankoop_datum_tekst = datetime.strptime(ruwe_datum, "%Y-%m-%d").strftime("%d-%m-%Y")
                            except: pass

                        try: inkoop_veilig = float(auto['inkoopprijs'])
                        except: inkoop_veilig = 0.0
                        try: kosten_veilig = float(auto['extra_kosten'])
                        except: kosten_veilig = 0.0
                        try: winst_veilig = float(auto['winst'])
                        except: winst_veilig = 0.0

                        # --- NIEUW: Alle voertuiggegevens strak uitgelijnd in een kolommen-tabel ---
                        voertuig_tabel_html = f"""
                        <div style="background-color: rgba(30, 30, 35, 0.4); padding: 12px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.05); margin-bottom: 15px;">
                            <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 14px;">
                                <tbody>
                                    <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05);">
                                        <td style="padding: 6px 5px; color: rgba(255, 255, 255, 0.6);">Kilometerstand</td>
                                        <td style="padding: 6px 5px; color: white; font-weight: bold; text-align: right;">{km_veilig:,} km</td>
                                    </tr>
                                    <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05);">
                                        <td style="padding: 6px 5px; color: rgba(255, 255, 255, 0.6);">Brandstof / Bouwjaar</td>
                                        <td style="padding: 6px 5px; color: white; font-weight: bold; text-align: right;">{auto['brandstof']} | {bouwjaar_veilig if bouwjaar_veilig > 0 else 'Onbekend'}</td>
                                    </tr>
                                    <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05);">
                                        <td style="padding: 6px 5px; color: rgba(255, 255, 255, 0.6);">Kleur / Cataloguswaarde</td>
                                        <td style="padding: 6px 5px; color: white; font-weight: bold; text-align: right;">{auto['kleur']} | €\u00a0{formatteer_euro_nl(cat_veilig)}</td>
                                    </tr>
                                    <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05);">
                                        <td style="padding: 6px 5px; color: rgba(255, 255, 255, 0.6);">Transmissie / APK Datum</td>
                                        <td style="padding: 6px 5px; color: white; font-weight: bold; text-align: right;">{auto['transmissie']} | {formatteer_datum_nl(auto['apk_datum'])}</td>
                                    </tr>
                                    <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.2);">
                                        <td style="padding: 6px 5px; color: rgba(255, 255, 255, 0.6);">Aankoopdatum</td>
                                        <td style="padding: 6px 5px; color: #28a745; font-weight: bold; text-align: right;">📅 {aankoop_datum_tekst}</td>
                                    </tr>
                                    <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05);">
                                        <td style="padding: 8px 5px; color: rgba(255, 255, 255, 0.6);">Inkoopprijs + Extra kosten</td>
                                        <td style="padding: 8px 5px; color: white; font-weight: bold; text-align: right;">€\u00a0{formatteer_euro_nl(inkoop_veilig)} + €\u00a0{formatteer_euro_nl(kosten_veilig)}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 8px 5px; color: rgba(255, 255, 255, 0.6); font-size: 15px;">Verwachte Marge / Winst</td>
                                        <td style="padding: 8px 5px; color: #28a745; font-size: 16px; font-weight: bold; text-align: right;">€\u00a0{formatteer_euro_nl(winst_veilig)}</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        """
                        st.markdown(voertuig_tabel_html, unsafe_allow_html=True)

                        # Hieronder lopen je bestaande kolommen voor de knoppen direct weer verder
                        b_edit, b_del = st.columns(2)
                        
                        try: km_int = int(float(auto['km_stand']))
                        except: km_int = 0
                            
                        if b_edit.button("✏️ Aanpassen", key=f"ed_{auto['id']}", width="stretch"):
                            bewerk_auto_dialog(auto["id"], auto["kenteken"], km_int, auto["inkoopprijs"], auto["verkoopprijs"], auto["apk_datum"], auto["extra_kosten"], auto["afbeelding"], auto["naam"], auto["transmissie"], auto["status"], auto["brandstof"], auto["bouwjaar"], auto["kleur"], auto["cataloguswaarde"])
                        
                        if b_del.button("🗑️ Verwijderen", key=f"dl_{auto['id']}", width="stretch"):
                            supabase.table("voorraad").delete().eq("id", auto["id"]).execute()
                            st.cache_data.clear()
                            st.rerun()
                        
                        st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
                        if st.button("📄 Koopcontract / Factuur", key=f"contract_{auto['id']}", type="secondary", width="stretch"):
                            genereer_contract_dialog(auto["id"], auto["naam"], auto["kenteken"], auto["km_stand"], auto["verkoopprijs"], auto["apk_datum"])

elif menu_optie == "💰 Financieel Overzicht":
    st.title("💰 Financieel Overzicht & Rendement")
    
    st.markdown("### ⚙️ Budget Instellingen")
    nieuw_budget = st.number_input("Stel je totale startbudget / werkkapitaal in (€):", value=float(st.session_state["startbudget"]), step=500.0)
    if nieuw_budget != st.session_state["startbudget"]:
        st.session_state["startbudget"] = nieuw_budget
        st.rerun()
        
    st.markdown("---")
    
    # --- EXACTE RENDEMENT & STATIEDAGEN BEREKENING ---
    alle_voorraad_data = haal_voorraad_op()
    
    totale_inkoop_verkocht = 0.0
    max_statiedagen_voertuig = 0  
    
    # --- NIEUWE VARIABELEN OM DE OUDSTE AUTO TE ONTHOUDEN ---
    oudste_auto_naam = ""
    oudste_auto_kenteken = ""
    oudste_auto_data = None
    
    totale_kosten_verkocht = 0.0
    totale_omzet_verkocht = 0.0
    
    oude_autos_teller = 0
    totale_statiedagen_voorraad = 0
    aantal_auto_in_voorraad = 0
    
    if alle_voorraad_data:
        for auto in alle_voorraad_data:
            ik = float(auto.get("inkoopprijs") or 0.0)
            ex = float(auto.get("extra_kosten") or 0.0)
            vk = float(auto.get("verkoopprijs") or 0.0)
            status = auto.get("status", "")
            
            statiedagen = 0
            if auto.get("afbeelding") and "AANKOOPDATUM:" in str(auto.get("afbeelding")):
                try:
                    datum_str = str(auto.get("afbeelding")).split("AANKOOPDATUM:")[1].split("||")[0].strip()
                    aankoop_datum = datetime.strptime(datum_str, "%Y-%m-%d").date()
                    statiedagen = (datetime.today().date() - aankoop_datum).days
                except:
                    statiedagen = 0

            if status == "Verkocht":
                totale_inkoop_verkocht += ik
                totale_kosten_verkocht += ex
                totale_omzet_verkocht += vk
            elif status == "In voorraad":
                aantal_auto_in_voorraad += 1
                totale_statiedagen_voorraad += max(0, statiedagen)
                
                # Update de maximale statiedagen en onthoud WELKE auto dit is
                if statiedagen >= max_statiedagen_voertuig and statiedagen > 0:
                    max_statiedagen_voertuig = statiedagen
                    oudste_auto_naam = auto.get("naam", "Onbekend")
                    oudste_auto_kenteken = auto.get("kenteken", "")
                    oudste_auto_data = auto # We bewaren alle gegevens om de tabel te kunnen tekenen
                    
                if statiedagen > 30:
                    oude_autos_teller += 1

    # ROI en Marge berekeningen
    totale_investering_verkocht = totale_inkoop_verkocht + totale_kosten_verkocht
    gemiddelde_roi = (gerealiseerde_winst / totale_investering_verkocht * 100) if totale_investering_verkocht > 0 else 0.0
    gemiddelde_marge = (gerealiseerde_winst / totale_omzet_verkocht * 100) if totale_omzet_verkocht > 0 else 0.0
    gemiddelde_statiedagen = (totale_statiedagen_voorraad / aantal_auto_in_voorraad) if aantal_auto_in_voorraad > 0 else 0


    # --- VISUELE LAY-OUT (ALLES IN STRAKKE KOLOMMENTABELLEN) ---
    
    # 1. Balans Overzicht Tabel
    st.markdown("### 📊 Balans Overzicht")

    # EERST DEFINIËREN:
    balans_html = f"""
    <div style="background-color: rgba(25, 25, 25, 0.6); padding: 15px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.1); margin-bottom: 20px;">
        <table style="width: 100%; border-collapse: collapse; text-align: left;">
            <thead>
                <tr style="border-bottom: 2px solid rgba(255, 255, 255, 0.2);">
                    <th style="padding: 10px; color: rgba(255, 255, 255, 0.7) !important; font-size: 14px; font-weight: normal;">Balans Post</th>
                    <th style="padding: 10px; color: rgba(255, 255, 255, 0.7) !important; font-size: 14px; font-weight: normal; text-align: right;">Waarde (€)</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
                    <td style="padding: 15px 10px; color: white !important; font-size: 18px;">Totale Startkapitaal</td>
                    <td style="padding: 15px 10px; color: white !important; font-size: 24px; font-weight: bold; text-align: right; white-space: nowrap;">&euro;&nbsp;{formatteer_euro_nl(st.session_state['startbudget'])}</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
                    <td style="padding: 15px 10px; color: white !important; font-size: 18px;">Vastgelegd in Autovoorraad</td>
                    <td style="padding: 15px 10px; color: white !important; font-size: 24px; font-weight: bold; text-align: right; white-space: nowrap;">&euro;&nbsp;{formatteer_euro_nl(totale_voorraadwaarde)}</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
                    <td style="padding: 15px 10px; color: white !important; font-size: 18px;">Vastgelegd in Losse Artikelen</td>
                    <td style="padding: 15px 10px; color: white !important; font-size: 24px; font-weight: bold; text-align: right; white-space: nowrap;">&euro;&nbsp;{formatteer_euro_nl(totale_waarde_artikelen)}</td>
                </tr>
                <tr>
                    <td style="padding: 15px 10px; color: white !important; font-size: 18px;">Besteedbaar Cashgeld (Vrij budget)</td>
                    <td style="padding: 15px 10px; color: {'#ff4b4b' if actueel_vrij_budget < 0 else 'white'} !important; font-size: 24px; font-weight: bold; text-align: right; white-space: nowrap;">&euro;&nbsp;{formatteer_euro_nl(actueel_vrij_budget)}</td>
                </tr>
            </tbody>
        </table>
    </div>
    """

    # DAARNA PAS MET MARKDOWN TONEN:
    st.markdown(balans_html, unsafe_allow_html=True)
    st.markdown("---")

    
    # 2. Rendement & Performance Tabel
    st.markdown("### 📈 Rendement & Performance")
    rendement_html = f"""
    <div style="background-color: rgba(25, 25, 25, 0.6); padding: 15px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.1); margin-bottom: 20px;">
        <table style="width: 100%; border-collapse: collapse; text-align: left;">
            <thead>
                <tr style="border-bottom: 2px solid rgba(255, 255, 255, 0.2);">
                    <th style="padding: 10px; color: rgba(255, 255, 255, 0.7) !important; font-size: 14px; font-weight: normal;">Prestatie Cijfer</th>
                    <th style="padding: 10px; color: rgba(255, 255, 255, 0.7) !important; font-size: 14px; font-weight: normal; text-align: right;">Resultaat</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
                    <td style="padding: 15px 10px; color: white !important; font-size: 18px;">Gerealiseerde Netto Winst</td>
                    <td style="padding: 15px 10px; color: white !important; font-size: 24px; font-weight: bold; text-align: right; white-space: nowrap;">&euro;&nbsp;{formatteer_euro_nl(gerealiseerde_winst)}</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
                    <td style="padding: 15px 10px; color: white !important; font-size: 18px;">Gemiddelde Marge per Deal</td>
                    <td style="padding: 15px 10px; color: white !important; font-size: 24px; font-weight: bold; text-align: right; white-space: nowrap;">{gemiddelde_marge:.1f}%</td>
                </tr>
                <tr>
                    <td style="padding: 15px 10px; color: white !important; font-size: 18px;">Return on Investment (ROI)</td>
                    <td style="padding: 15px 10px; color: white !important; font-size: 24px; font-weight: bold; text-align: right; white-space: nowrap;">{gemiddelde_roi:.1f}%</td>
                </tr>
            </tbody>
        </table>
    </div>
    """
    st.markdown(rendement_html, unsafe_allow_html=True)

    st.markdown("---")
    
    # 3. Financieel KPI Overzicht Tabel
    st.markdown("### 📋 Financieel KPI Overzicht")
    kpi_html = f"""
    <div style="background-color: rgba(25, 25, 25, 0.6); padding: 15px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.1); margin-bottom: 20px;">
        <table style="width: 100%; border-collapse: collapse; text-align: left;">
            <thead>
                <tr style="border-bottom: 2px solid rgba(255, 255, 255, 0.2);">
                    <th style="padding: 10px; color: rgba(255, 255, 255, 0.7) !important; font-size: 14px; font-weight: normal;">Financieel Cijfer</th>
                    <th style="padding: 10px; color: rgba(255, 255, 255, 0.7) !important; font-size: 14px; font-weight: normal; text-align: right;">Bedrag (€)</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
                    <td style="padding: 15px 10px; color: white !important; font-size: 18px;">Totale Omzet (Verkocht)</td>
                    <td style="padding: 15px 10px; color: white !important; font-size: 24px; font-weight: bold; text-align: right; white-space: nowrap;">&euro;&nbsp;{formatteer_euro_nl(totale_omzet_verkocht)}</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
                    <td style="padding: 15px 10px; color: white !important; font-size: 18px;">Investeringswaarde Verkocht</td>
                    <td style="padding: 15px 10px; color: white !important; font-size: 24px; font-weight: bold; text-align: right; white-space: nowrap;">&euro;&nbsp;{formatteer_euro_nl(totale_investering_verkocht)}</td>
                </tr>
                <tr>
                    <td style="padding: 15px 10px; color: white !important; font-size: 18px;">Besteedbaar Werkkapitaal</td>
                    <td style="padding: 15px 10px; color: white !important; font-size: 24px; font-weight: bold; text-align: right; white-space: nowrap;">&euro;&nbsp;{formatteer_euro_nl(actueel_vrij_budget)}</td>
                </tr>
            </tbody>
        </table>
    </div>
    """
    st.markdown(kpi_html, unsafe_allow_html=True)

    st.markdown("---")
    
    # 4. Omloopanalyse Tabel (Nu met de langststaande auto)
    st.markdown("### ⏱️ Omloopanalyse")
    omloop_html = f"""
    <div style="background-color: rgba(25, 25, 25, 0.6); padding: 15px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.1); margin-bottom: 20px;">
        <table style="width: 100%; border-collapse: collapse; text-align: left;">
            <thead>
                <tr style="border-bottom: 2px solid rgba(255, 255, 255, 0.2);">
                    <th style="padding: 10px; color: rgba(255, 255, 255, 0.7) !important; font-size: 14px; font-weight: normal;">Omloop Parameter</th>
                    <th style="padding: 10px; color: rgba(255, 255, 255, 0.7) !important; font-size: 14px; font-weight: normal; text-align: right;">Status</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
                    <td style="padding: 15px 10px; color: white !important; font-size: 18px;">Gemiddelde statiedagen van huidige voorraad</td>
                    <td style="padding: 15px 10px; color: white !important; font-size: 24px; font-weight: bold; text-align: right; white-space: nowrap;">{int(gemiddelde_statiedagen)} dagen</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
                    <td style="padding: 15px 10px; color: white !important; font-size: 18px;">Aantal auto's > 30 dagen in voorraad</td>
                    <td style="padding: 15px 10px; color: {'#ff4b4b' if oude_autos_teller > 0 else 'white'} !important; font-size: 24px; font-weight: bold; text-align: right; white-space: nowrap;">{oude_autos_teller} stuks</td>
                </tr>
                <tr>
                    <!-- NIEUWE RIJ -->
                    <td style="padding: 15px 10px; color: white !important; font-size: 18px;">Aantal dagen van het langststaande voertuig</td>
                    <td style="padding: 15px 10px; color: {'#ff4b4b' if max_statiedagen_voertuig > 45 else 'white'} !important; font-size: 24px; font-weight: bold; text-align: right; white-space: nowrap;">{int(max_statiedagen_voertuig)} dagen</td>
                </tr>
            </tbody>
        </table>
    </div>
    """
    
    st.markdown(omloop_html, unsafe_allow_html=True)
    # --- NIEUW: DROPDOWN MENU VOOR DE LANGSTSTAANDE AUTO ---
    if max_statiedagen_voertuig > 0 and oudste_auto_data:
        # Bereken de winst/marge specifiek voor deze auto om in de tabel te tonen
        try:
            v_vk = float(oudste_auto_data.get("verkoopprijs") or 0)
            v_ik = float(oudste_auto_data.get("inkoopprijs") or 0)
            v_ex = float(oudste_auto_data.get("extra_kosten") or 0)
            v_winst = v_vk - (v_ik + v_ex)
            v_km = int(float(oudste_auto_data.get("km_stand") or 0))
            v_cat = float(oudste_auto_data.get("cataloguswaarde") or 0)
        except:
            v_winst = 0.0
            v_km = 0
            v_cat = 0.0

        # We bouwen een expander (dropdown) die exact matcht met je voorraad-styling
        with st.expander(f"🚗 Bekijk langststaande voertuig: {oudste_auto_naam} ({oudste_auto_kenteken})"):
            c_pop1, c_pop2 = st.columns(2)
            
            with c_pop1:
                # Toon de foto's van deze specifieke auto direct uit je Supabase storage link
                if oudste_auto_data.get("afbeelding"):
                    alle_elementen = oudste_auto_data["afbeelding"].split("||")
                    alle_foto_links = [x for x in alle_elementen if "AANKOOPDATUM:" not in x and x.startswith("http")]
                    
                    if alle_foto_links:
                        foto_cols = st.columns(min(len(alle_foto_links), 3))
                        for idx, url in enumerate(alle_foto_links):
                            with foto_cols[idx % min(len(alle_foto_links), 3)]:
                                st.markdown(f'<img src="{url}" style="width:100%; aspect-ratio:16/9; object-fit:contain; background-color:rgba(15,15,20,0.85); border-radius:8px; display:block;">', unsafe_allow_html=True)
                    else:
                        st.info("Geen afbeelding beschikbaar in cloud storage.")
                else:
                    st.info("Geen afbeelding beschikbaar.")
            
            with c_pop2:
                # De exacte tabel lay-out zoals getoond in je screenshot, maar nu op je financieel overzicht!
                oudste_tabel_html = f"""
                <div style="background-color: rgba(30, 30, 35, 0.4); padding: 12px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.05); margin-bottom: 15px;">
                    <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 14px;">
                        <tbody>
                            <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05);">
                                <td style="padding: 6px 5px; color: rgba(255, 255, 255, 0.6);">Kilometerstand</td>
                                <td style="padding: 6px 5px; color: white; font-weight: bold; text-align: right;">{v_km:,} km</td>
                            </tr>
                            <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05);">
                                <td style="padding: 6px 5px; color: rgba(255, 255, 255, 0.6);">Brandstof / Bouwjaar</td>
                                <td style="padding: 6px 5px; color: white; font-weight: bold; text-align: right;">{oudste_auto_data.get('brandstof', 'Onbekend')} | {oudste_auto_data.get('bouwjaar', 'Onbekend')}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05);">
                                <td style="padding: 6px 5px; color: rgba(255, 255, 255, 0.6);">Kleur / Cataloguswaarde</td>
                                <td style="padding: 6px 5px; color: white; font-weight: bold; text-align: right;">{oudste_auto_data.get('kleur', 'Onbekend')} | €\u00a0{formatteer_euro_nl(v_cat)}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05);">
                                <td style="padding: 6px 5px; color: rgba(255, 255, 255, 0.6);">Transmissie / APK Datum</td>
                                <td style="padding: 6px 5px; color: white; font-weight: bold; text-align: right;">{oudste_auto_data.get('transmissie', 'Onbekend')} | {formatteer_datum_nl(oudste_auto_data.get('apk_datum'))}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05);">
                                <td style="padding: 8px 5px; color: rgba(255, 255, 255, 0.6);">Inkoopprijs + Extra kosten</td>
                                <td style="padding: 8px 5px; color: white; font-weight: bold; text-align: right;">€\u00a0{formatteer_euro_nl(v_ik)} + €\u00a0{formatteer_euro_nl(v_ex)}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 5px; color: rgba(255, 255, 255, 0.6); font-size: 15px;">Verwachte Marge / Winst</td>
                                <td style="padding: 8px 5px; color: #ff4b4b; font-size: 16px; font-weight: bold; text-align: right;">€\u00a0{formatteer_euro_nl(v_winst)}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                """
                st.markdown(oudste_tabel_html, unsafe_allow_html=True)    
    st.markdown("<br>", unsafe_allow_html=True)
    if oude_autos_teller > 0 or gemiddelde_statiedagen > 60:
        st.warning(f"⚠️ **Financieel Advies:** Je hebt momenteel {oude_autos_teller} auto('s) die al langer dan een maand stilstaan. Je langststaande voertuig staat al {int(max_statiedagen_voertuig)} dagen op voorraad. Overweeg om deze gerichte pluk voorraad met een korting te verkopen om snel werkkapitaal vrij te maken.")
    else:
        st.success("✅ **Financieel Advies:** Je omloopsnelheid ziet er gezond uit! Je verkoopt je auto's snel achter elkaar waardoor je werkkapitaal efficiënt blijft rollen.")


elif menu_optie == "📅 Agenda & Notities":
    st.title("📅 Agenda & Notities")
    
    try:
        from streamlit_calendar import calendar
    except ImportError:
        st.error("Installeer eerst de kalender-module via je requirements.txt: streamlit-calendar")
        st.stop()

    @st.dialog("📌 Nieuwe afspraak / notitie toevoegen")
    def nieuwe_afspraak_popup(gekozen_datum_str):
        # 1. Zet de checkbox BUITEN het formulier zodat Streamlit direct live reageert
        st.write(f"**Geselecteerde begindatum:** {formatteer_datum_nl(gekozen_datum_str)}")
        hele_dag = st.checkbox("📅 Deze afspraak duurt de gehele dag(en)", value=True, key="nieuwe_afspraak_hele_dag")
        
        # 2. Start hier pas het formulier voor de invoervelden
        with st.form("agenda_toevoeg_form", clear_on_submit=True):
            if hele_dag:
                tot_datum = st.date_input("Einddatum (t/m)", value=datetime.strptime(gekozen_datum_str, "%Y-%m-%d").date(), format="DD-MM-YYYY")
            else:
                tot_datum = datetime.strptime(gekozen_datum_str, "%Y-%m-%d").date()
                
                tijd_col1, tijd_col2 = st.columns(2)
                ag_tijd_van = tijd_col1.time_input("Begintijd", value=datetime.strptime("10:00", "%H:%M").time())
                ag_tijd_tot = tijd_col2.time_input("Eindtijd", value=datetime.strptime("11:00", "%H:%M").time())
           
            ag_titel = st.text_input("Titel (bijv. Auto verhuurd, Vakantie, Showroom dicht)")
            ag_notitie = st.text_area("Aanvullende informatie / opmerkingen")
            ag_submit = st.form_submit_button("💾 Opslaan in Agenda", type="primary", width="stretch")
            
        if ag_submit and ag_titel.strip():
            opslag_datum = f"{gekozen_datum_str}||{str(tot_datum)}" if hele_dag else f"{gekozen_datum_str}T{ag_tijd_van.strftime('%H:%M:%S')}||{gekozen_datum_str}T{ag_tijd_tot.strftime('%H:%M:%S')}"
            supabase.table("agenda").insert({"datum": opslag_datum, "titel": ag_titel.strip(), "notitie": ag_notitie.strip(), "status": "Open"}).execute()
            st.cache_data.clear()
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
            if col_b1.button("✅ Voltooid" if status_veld == "Open" else "🔄 Heropenen", width="stretch"):
                nieuwe_status = "Voltooid" if status_veld == "Open" else "Open"
                supabase.table("agenda").update({"status": nieuwe_status}).eq("id", event_id).execute()
                st.cache_data.clear()
                st.rerun()
            if col_b2.button("✏️ Bewerken", width="stretch"):
                st.session_state[bewerk_modus_key] = True
                st.rerun()
            if col_b3.button("🗑️ Wissen", type="secondary", width="stretch"):
                supabase.table("agenda").delete().eq("id", event_id).execute()
                st.cache_data.clear()
                st.rerun()
        else:
            st.markdown("### ✏️ Afspraak Wijzigen")
            edit_hele_dag = st.checkbox("📅 Deze afspraak duurt de gehele dag(en)", value=is_voorheen_hele_dag, key=f"edit_hd_{event_id}")
            
            # Nieuwe tijdsvelden toevoegen voor de bewerkmodus:
            if edit_hele_dag:
                col_d1, col_d2 = st.columns(2)
                edit_datum_van = col_d1.date_input("Pas Begindatum aan", value=standaard_van, key=f"edit_dat_v_{event_id}")
                edit_datum_tot = col_d2.date_input("Pas Einddatum aan", value=standaard_tot, key=f"edit_dat_t_{event_id}")
            else:
                col_d1, col_t1, col_t2 = st.columns([2, 1, 1])
                edit_datum_van = col_d1.date_input("Pas Datum aan", value=standaard_van, key=f"edit_dat_{event_id}")
                
                # Haal de huidige opgeslagen tijden op om als standaardwaarde te tonen
                huidige_tijd_van = datetime.strptime(str(start_veld).split("T")[1][:5], "%H:%M").time() if "T" in str(start_veld) else datetime.strptime("10:00", "%H:%M").time()
                huidige_tijd_tot = datetime.strptime(str(eind_veld).split("T")[1][:5], "%H:%M").time() if "T" in str(eind_veld) else datetime.strptime("11:00", "%H:%M").time()
                
                edit_tijd_van = col_t1.time_input("Pas Begintijd aan", value=huidige_tijd_van, key=f"edit_tijd_v_{event_id}")
                edit_tijd_tot = col_t2.time_input("Pas Eindtijd aan", value=huidige_tijd_tot, key=f"edit_tijd_t_{event_id}")
            
            edit_titel = st.text_input("Pas Titel aan", value=pure_titel_origineel, key=f"edit_ttl_{event_id}")
            edit_notitie = st.text_area("Pas Aanvullende informatie aan", value=notitie_veld if notitie_veld else "", key=f"edit_not_{event_id}")
            
            st.markdown("---")
            col_save1, col_save2 = st.columns(2)
            if col_save1.button("💾 Opslaan", type="primary", width="stretch"):
                # Sla de gewijzigde live tijden op in de database!
                nieuw_datum_format = f"{edit_datum_van}||{edit_datum_tot}" if edit_hele_dag else f"{edit_datum_van}T{edit_tijd_van.strftime('%H:%M:%S')}||{edit_datum_van}T{edit_tijd_tot.strftime('%H:%M:%S')}"
                supabase.table("agenda").update({"datum": nieuw_datum_format, "titel": edit_titel.strip(), "notitie": edit_notitie.strip()}).eq("id", event_id).execute()
                st.cache_data.clear()
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

    notities = haal_agenda_op()
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
        "initialView": "dayGridMonth", 
        "locale": "nl", 
        "timeZone": "local", 
        "height": 850,             # Hoog genoeg om 07:00 t/m 22:00 in de week/dag-weergave zonder scrollen te tonen
        "slotMinTime": "07:00:00", # Slaat de nacht over en begint de dag overzichtelijk om 07:00
        "slotMaxTime": "22:00:00", # Laat de dag doorlopen tot 22:00
        "buttonText": {"today": "vandaag", "month": "maand", "week": "week", "day": "dag"}
    }


    
    # Dit is het "jasje" dat zorgt dat de scrollbalk om de kalender heen komt:
    with st.container(border=False):
        st.markdown('<div id="agenda-container">', unsafe_allow_html=True)
        state = calendar(events=calendar_events, options=calendar_options, key="agenda_strakke_kalender")
        st.markdown('</div>', unsafe_allow_html=True)

    
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
elif menu_optie == "📦 Artikelen":
    st.title("📦 Losse Artikelen & Benodigdheden")
    st.write("Hier kun je artikelen bijhouden die losstaan van de auto's, zoals schoonmaakspullen of gereedschap.")

    # 1. ARTIKELEN OPHALEN UIT SUPABASE
    try:
        response = supabase.table("artikelen").select("*").order("naam").execute()
        artikelen_data = response.data
    except Exception as e:
        st.error(f"Fout bij ophalen artikelen: {e}")
        artikelen_data = []

    # 2. FORMULIER: NIEUW ARTIKEL TOEVOEGEN
    with st.expander("➕ Nieuw artikel toevoegen"):
        with st.form("nieuw_artikel_form", clear_on_submit=True):
            art_naam = st.text_input("Naam artikel", placeholder="Bijv. Dashboard spray, Microvezeldoeken")
            art_cat = st.selectbox("Categorie", ["Schoonmaak", "Gereedschap", "Kantoor", "Overig"])
            
            col_aantal, col_prijs = st.columns(2)
            with col_aantal:
                art_aantal = st.number_input("Aantal", min_value=1, value=1, step=1)
            with col_prijs:
                art_prijs = st.number_input("Prijs per stuk (€)", min_value=0.0, value=0.0, step=0.50)
            
            art_notitie = st.text_area("Notitie / Opmerking", placeholder="Optioneel: waar gekocht of voor wie?")
            
            submit_artikel = st.form_submit_button("Artikel opslaan")
            
            if submit_artikel:
                if not art_naam.strip():
                    st.warning("Vul tenminste een naam in.")
                else:
                    nieuw_item = {
                        "naam": art_naam.strip(),
                        "categorie": art_cat,
                        "aantal": int(art_aantal),
                        "prijs_per_stuk": float(art_prijs),
                        "notitie": art_notitie.strip()
                    }
                    try:
                        supabase.table("artikelen").insert(nieuw_item).execute()
                        st.success(f"✔️ {art_naam} succesvol toegevoegd!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Databasefout bij opslaan: {e}")

    # 3. OVERZICHT
    if artikelen_data:
        totale_waarde = sum(item["aantal"] * float(item["prijs_per_stuk"] or 0) for item in artikelen_data)
        st.metric(label="Totale waarde artikelen op voorraad", value=f"€\u00a0{totale_waarde:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        # Toon de artikelen netjes in een tabel
        df_artikelen = pd.DataFrame(artikelen_data)
        df_weergave = df_artikelen[["naam", "categorie", "aantal", "prijs_per_stuk", "notitie"]].copy()
        df_weergave.columns = ["Naam", "Categorie", "Aantal", "Prijs p/s", "Notitie"]
        
        st.dataframe(df_weergave, width="stretch", hide_index=True)
        
        # --- NIEUW: ARTIKEL AANPASSEN ---
        with st.expander("✏️ Artikel aanpassen / bewerken"):
            # Maak een woordenboek om makkelijk de ID en huidige gegevens op te halen op basis van de naam
            artikel_dict = {item["naam"]: item for item in artikelen_data}
            te_bewerken_naam = st.selectbox("Selecteer het artikel dat je wilt aanpassen", options=list(artikel_dict.keys()), key="select_bewerk_art")
            
            if te_bewerken_naam:
                gekozen_art = artikel_dict[te_bewerken_naam]
                
                # Formulier met de huidige waarden al ingevuld
                with st.form("bewerk_artikel_form", clear_on_submit=False):
                    bewerk_naam = st.text_input("Pas Naam aan", value=gekozen_art["naam"])
                    
                    categorie_opties = ["Schoonmaak", "Gereedschap", "Kantoor", "Overig"]
                    huidige_cat = gekozen_art["categorie"]
                    if huidige_cat not in categorie_opties:
                        categorie_opties.append(huidige_cat)
                    bewerk_cat = st.selectbox("Pas Categorie aan", options=categorie_opties, index=categorie_opties.index(huidige_cat))
                    
                    col_b_aantal, col_b_prijs = st.columns(2)
                    with col_b_aantal:
                        bewerk_aantal = col_b_aantal.number_input("Pas Aantal aan", min_value=1, value=int(gekozen_art["aantal"]), step=1)
                    with col_b_prijs:
                        bewerk_prijs = col_b_prijs.number_input("Pas Prijs per stuk aan (€)", min_value=0.0, value=float(gekozen_art["prijs_per_stuk"] or 0.0), step=0.50)
                    
                    bewerk_notitie = st.text_area("Pas Notitie / Opmerking aan", value=gekozen_art["notitie"] if gekozen_art["notitie"] else "")
                    
                    submit_wijziging = st.form_submit_button("💾 Wijzigingen Live Opslaan", width="stretch")
                    
                    if submit_wijziging:
                        if not bewerk_naam.strip():
                            st.warning("De naam mag niet leeg zijn.")
                        else:
                            geüpdatet_item = {
                                "naam": bewerk_naam.strip(),
                                "categorie": bewerk_cat,
                                "aantal": int(bewerk_aantal),
                                "prijs_per_stuk": float(bewerk_prijs),
                                "notitie": bewerk_notitie.strip()
                            }
                            try:
                                supabase.table("artikelen").update(geüpdatet_item).eq("id", gekozen_art["id"]).execute()
                                st.success(f"✔️ {bewerk_naam} succesvol aangepast!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Databasefout bij updaten: {e}")

        # OPTIE: Artikel verwijderen knop
        with st.expander("🗑️ Artikel verwijderen"):
            artikel_opties = {item["naam"]: item["id"] for item in artikelen_data}
            te_verwijderen = st.selectbox("Selecteer artikel om te wissen", options=list(artikel_opties.keys()))
            
            if st.button("Definitief verwijderen", type="primary"):
                try:
                    artikel_id = artikel_opties[te_verwijderen]
                    supabase.table("artikelen").delete().eq("id", artikel_id).execute()
                    st.success(f"Artikel '{te_verwijderen}' is verwijderd.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Fout bij verwijderen: {e}")
    else:
        st.info("Er zijn nog geen losse artikelen toegevoegd.")



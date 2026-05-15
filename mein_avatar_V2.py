import streamlit as st
import requests
import base64
import time
import io
import json
import re
import html
from datetime import datetime

# Optional imports mit Fallback
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# ─────────────────────────────────────────────
# KONFIGURATION
# ─────────────────────────────────────────────
DID_API_KEY = "dnV4dWFudGllcEBnb29nbGVtYWlsLmNvbQ:diNrSDQmRkb8agDPCbPSW"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma:2b"  # Oder llama3, mistral, etc.
MAX_CV_CHARS = 12000
CV_CONTEXT_CHARS = 8000

# ─────────────────────────────────────────────
# SEITEN-KONFIGURATION
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Smart Coach Pro v2",
    layout="wide",
    page_icon="🎯",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');
    
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    
    .stApp { background: #0f1117; color: #e8eaf0; }
    
    .coach-header {
        background: linear-gradient(135deg, #1a1f2e 0%, #0f1117 100%);
        border: 1px solid #2a3045;
        border-radius: 16px;
        padding: 20px 28px;
        margin-bottom: 20px;
    }
    
    .metric-card {
        background: #1a1f2e;
        border: 1px solid #2a3045;
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }
    
    .metric-score {
        font-size: 2.2rem;
        font-weight: 700;
        line-height: 1;
    }
    
    .score-high { color: #4ade80; }
    .score-mid  { color: #facc15; }
    .score-low  { color: #f87171; }
    
    .analysis-block {
        background: #1a1f2e;
        border-left: 3px solid #6366f1;
        border-radius: 0 12px 12px 0;
        padding: 14px 18px;
        margin: 8px 0;
    }
    
    .analysis-block.strength { border-left-color: #4ade80; }
    .analysis-block.weakness { border-left-color: #f87171; }
    .analysis-block.tip      { border-left-color: #facc15; }
    .analysis-block.keyword  { border-left-color: #818cf8; }
    
    .chat-bubble-user {
        background: #2a3045;
        border-radius: 16px 16px 4px 16px;
        padding: 12px 16px;
        margin: 8px 0 8px 60px;
        color: #e8eaf0;
    }
    
    .chat-bubble-coach {
        background: #1e2535;
        border: 1px solid #2a3045;
        border-radius: 16px 16px 16px 4px;
        padding: 12px 16px;
        margin: 8px 60px 8px 0;
        color: #e8eaf0;
    }
    
    .tag-pill {
        display: inline-block;
        background: #2a3045;
        border: 1px solid #3d4a6a;
        border-radius: 20px;
        padding: 3px 12px;
        margin: 3px;
        font-size: 0.82rem;
        color: #a5b4fc;
        font-family: 'DM Mono', monospace;
    }
    
    .section-label {
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #6b7280;
        margin-bottom: 8px;
    }
    
    .stButton > button {
        background: #4f46e5 !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 500 !important;
        transition: all 0.2s !important;
    }
    .stButton > button:hover {
        background: #4338ca !important;
        transform: translateY(-1px);
    }
    
    div[data-testid="stTabs"] button {
        font-family: 'DM Sans', sans-serif;
        font-weight: 500;
    }
    
    .optimized-cv {
        background: #111827;
        border: 1px solid #2a3045;
        border-radius: 12px;
        padding: 20px 24px;
        font-family: 'DM Mono', monospace;
        font-size: 0.85rem;
        line-height: 1.7;
        white-space: pre-wrap;
        color: #d1d5db;
        max-height: 500px;
        overflow-y: auto;
    }
    
    .progress-ring {
        font-size: 3rem;
        text-align: center;
    }
    
    hr { border-color: #2a3045 !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SESSION STATE INITIALISIERUNG
# ─────────────────────────────────────────────
def init_state():
    defaults = {
        "chat_history":     [],
        "cv_text":          "",
        "cv_filename":      "",
        "cv_analysis":      None,
        "optimized_cv":     "",
        "ikigai_step":      0,
        "ikigai_answers":   {},
        "ikigai_result":    "",
        "coach_mode":       "chat",
        "ollama_available": None,
        "ollama_model":     OLLAMA_MODEL,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ─────────────────────────────────────────────
# HILFSFUNKTIONEN
# ─────────────────────────────────────────────

def extract_pdf_text(file_bytes: bytes) -> str:
    """Extrahiert Text aus PDF mit pdfplumber."""
    if not PDF_AVAILABLE:
        return "[pdfplumber nicht installiert. Bitte: pip install pdfplumber]"
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
        return "\n".join(pages)
    except Exception as e:
        return f"[PDF-Fehler: {e}]"


def extract_docx_text(file_bytes: bytes) -> str:
    """Extrahiert Text aus DOCX."""
    if not DOCX_AVAILABLE:
        return "[python-docx nicht installiert. Bitte: pip install python-docx]"
    try:
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        return f"[DOCX-Fehler: {e}]"


def clean_cv_text(text: str) -> str:
    """Bereinigt extrahierten CV-Text, ohne wichtige Inhalte zu verlieren."""
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clip_text(text: str, limit: int = MAX_CV_CHARS) -> str:
    """Kuerzt lange Dokumente mit Hinweis, statt still Informationen abzuschneiden."""
    text = clean_cv_text(text)
    if len(text) <= limit:
        return text
    head = text[: int(limit * 0.7)].strip()
    tail = text[-int(limit * 0.3):].strip()
    return (
        f"{head}\n\n[... Lebenslauf gekuerzt: {len(text) - limit} Zeichen ausgelassen ...]\n\n{tail}"
    )


def strip_json_fences(raw: str) -> str:
    """Entfernt haeufige Markdown-Huellen um JSON-Antworten."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
    raw = re.sub(r"```$", "", raw).strip()
    return raw


def as_list(value, max_items: int = 5) -> list:
    """Normalisiert LLM-Ausgaben zu einer kurzen Liste von Strings."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip(" -•\t") for p in re.split(r"\n|;", value) if p.strip()]
        return parts[:max_items]
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()][:max_items]
    return [str(value).strip()][:max_items]


def safe_int(value, default: int = 0, minimum: int = 0, maximum: int = 100) -> int:
    """Konvertiert Scores robust in einen begrenzten Integer."""
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def cv_quality_heuristics(cv_text: str) -> dict:
    """Einfache lokale Checks, die auch ohne perfektes LLM-JSON helfen."""
    lower = cv_text.lower()
    sections = {
        "Kontakt": any(k in lower for k in ["email", "e-mail", "@", "telefon", "phone", "linkedin"]),
        "Profil": any(k in lower for k in ["profil", "summary", "kurzprofil", "about me"]),
        "Berufserfahrung": any(k in lower for k in ["berufserfahrung", "work experience", "experience", "praktikum"]),
        "Ausbildung": any(k in lower for k in ["ausbildung", "education", "studium", "university", "schule"]),
        "Skills": any(k in lower for k in ["skills", "kompetenzen", "kenntnisse", "technologien"]),
        "Sprachen": any(k in lower for k in ["sprachen", "languages", "deutsch", "englisch"]),
    }
    missing_sections = [name for name, present in sections.items() if not present]
    weak_signals = []
    if len(cv_text.split()) < 180:
        weak_signals.append("Der Lebenslauf wirkt sehr kurz; konkrete Projekte, Ergebnisse und Technologien fehlen wahrscheinlich.")
    if not re.search(r"\d+[%+]|\b\d{2,}\b", cv_text):
        weak_signals.append("Es fehlen messbare Ergebnisse wie Zahlen, Zeitraeume, Volumen oder Verbesserungen.")
    if not re.search(r"20\d{2}|19\d{2}", cv_text):
        weak_signals.append("Zeitangaben sind schwer erkennbar; das kann fuer Recruiter und ATS problematisch sein.")
    return {"sections": sections, "missing_sections": missing_sections, "weak_signals": weak_signals}


def normalize_cv_analysis(data: dict, cv_text: str, raw: str = "") -> dict:
    """Sichert die erwartete Datenstruktur fuer die UI ab."""
    heuristics = cv_quality_heuristics(cv_text)
    normalized = {
        "score": safe_int(data.get("score"), 65),
        "ats_score": safe_int(data.get("ats_score"), 55),
        "erfahrung_jahre": safe_int(data.get("erfahrung_jahre"), 0, 0, 60),
        "berufsfeld": str(data.get("berufsfeld") or "Nicht eindeutig erkannt").strip(),
        "zielrollen": as_list(data.get("zielrollen"), 4),
        "staerken": as_list(data.get("staerken"), 5),
        "schwaechen": as_list(data.get("schwaechen"), 5),
        "keywords_fehlen": as_list(data.get("keywords_fehlen"), 8),
        "keywords_vorhanden": as_list(data.get("keywords_vorhanden"), 8),
        "format_tipps": as_list(data.get("format_tipps"), 5),
        "inhalt_tipps": as_list(data.get("inhalt_tipps"), 5),
        "konkrete_rewrites": as_list(data.get("konkrete_rewrites"), 5),
        "interview_fragen": as_list(data.get("interview_fragen"), 5),
        "top_empfehlung": str(data.get("top_empfehlung") or "Ergaenze messbare Erfolge und richte den Lebenslauf klar auf die Zielstelle aus.").strip(),
        "naechste_schritte": as_list(data.get("naechste_schritte"), 5),
        "missing_sections": heuristics["missing_sections"],
        "weak_signals": heuristics["weak_signals"],
    }

    if not normalized["format_tipps"] and heuristics["missing_sections"]:
        normalized["format_tipps"] = [f"Ergaenze den Abschnitt: {name}" for name in heuristics["missing_sections"][:3]]
    if not normalized["schwaechen"] and heuristics["weak_signals"]:
        normalized["schwaechen"] = heuristics["weak_signals"][:3]
    if raw:
        normalized["_raw"] = raw[:800]
    return normalized


def check_ollama() -> bool:
    """Prüft ob Ollama erreichbar ist."""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except:
        return False


def call_ollama(prompt: str, system: str = "", max_tokens: int = 800) -> str:
    """Generiert Antwort über Ollama."""
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    try:
        model_name = st.session_state.get("ollama_model", OLLAMA_MODEL)
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": model_name,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.35,
                    "top_p": 0.9,
                    "num_predict": max_tokens,
                },
            },
            timeout=90
        )
        resp.raise_for_status()
        return resp.json().get("response", "Keine Antwort erhalten.")
    except requests.exceptions.ConnectionError:
        return "⚠️ Ollama nicht erreichbar. Bitte starte: `ollama serve`"
    except Exception as e:
        return f"⚠️ Fehler: {e}"


def build_coach_system(user_name: str, cv_context: str = "") -> str:
    """Erstellt den System-Prompt für den Coach."""
    base = (
        f"Du bist ein erfahrener Karriere- und Integrationscoach. "
        f"Dein Gesprächspartner heißt {user_name}. "
        "Du sprichst professionell, empathisch und direkt. "
        "Antworte immer in der Sprache der Anfrage (Deutsch oder Vietnamesisch). "
        "Halte Antworten fokussiert (3–5 Sätze), außer bei detaillierter Analyse. "
        "Nutze konkrete, umsetzbare Empfehlungen und stelle Rueckfragen, wenn Informationen fehlen. "
        "Wenn du Stärken und Schwächen nennst, sei ehrlich aber konstruktiv."
    )
    if cv_context:
        base += (
            f"\n\nLebenslauf des Nutzers (analysiere und beziehe dich darauf):\n"
            f"---\n{clip_text(cv_context, CV_CONTEXT_CHARS)}\n---"
        )
    return base


def build_chat_context(history: list, max_turns: int = 6) -> str:
    """Konvertiert Chat-Verlauf in Kontext-String."""
    if not history:
        return ""
    recent = history[-max_turns*2:]
    lines = []
    for msg in recent:
        role = "Nutzer" if msg["role"] == "user" else "Coach"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)


def analyze_cv_structured(cv_text: str, user_name: str, target_role: str = "") -> dict:
    """Analysiert den Lebenslauf und gibt strukturierte Ergebnisse zurück."""
    system = (
        "Du bist ein professioneller CV-Analytiker für den deutschsprachigen Jobmarkt. "
        "Du bewertest Lebenslaeufe wie ein erfahrener Recruiter, ATS-Spezialist und Karrierecoach. "
        "Analysiere ehrlich, konkret und faktenbasiert. "
        "Erfinde keine Qualifikationen. Wenn Angaben fehlen, benenne die Luecke. "
        "Antworte NUR mit einem validen JSON-Objekt. Kein Markdown, keine Erklaerungen."
    )
    target_hint = (
        f"Zielstelle/Zielrolle: {target_role}\nBewerte Passung, fehlende Keywords und Optimierung explizit fuer diese Zielrolle."
        if target_role.strip()
        else "Keine Zielstelle angegeben. Leite passende Zielrollen aus dem Lebenslauf ab."
    )
    cv_excerpt = clip_text(cv_text, MAX_CV_CHARS)
    prompt = f"""Analysiere diesen Lebenslauf fuer {user_name}.
{target_hint}

Gib ein JSON-Objekt mit genau diesen Feldern zurueck:

{{
  "score": <Zahl 0-100, Gesamtbewertung>,
  "ats_score": <ATS-Kompatibilitaet 0-100>,
  "erfahrung_jahre": <geschaetzte relevante Berufserfahrung in Jahren als Zahl>,
  "berufsfeld": "<erkanntes Berufsfeld/Branche>",
  "zielrollen": ["<passende Zielrolle 1>", "<passende Zielrolle 2>", "<passende Zielrolle 3>"],
  "staerken": ["<konkrete Staerke mit Beleg aus CV>", "<...>", "<...>"],
  "schwaechen": ["<konkrete Luecke/Risiko>", "<...>", "<...>"],
  "keywords_vorhanden": ["<ATS Keyword>", "<...>"],
  "keywords_fehlen": ["<fehlendes Keyword passend zur Zielrolle>", "<...>"],
  "format_tipps": ["<Format/Struktur-Tipp>", "<...>"],
  "inhalt_tipps": ["<Inhaltlicher Verbesserungstipp>", "<...>"],
  "konkrete_rewrites": ["<Original schwach -> bessere Formulierung>", "<...>"],
  "interview_fragen": ["<wahrscheinliche Interviewfrage>", "<...>"],
  "top_empfehlung": "<wichtigste konkrete Massnahme>",
  "naechste_schritte": ["<Schritt 1>", "<Schritt 2>", "<Schritt 3>"]
}}

Lebenslauf:
{cv_excerpt}"""

    raw = call_ollama(prompt, system, max_tokens=600)
    
    # JSON extrahieren
    try:
        # Versuche direkt zu parsen
        cleaned = strip_json_fences(raw)
        match = re.search(r'\{[\s\S]+\}', cleaned)
        if match:
            return normalize_cv_analysis(json.loads(match.group()), cv_text)
    except:
        pass
    
    # Fallback
    return normalize_cv_analysis({
        "score": 65,
        "staerken": ["Dokument vorhanden", "Struktur erkennbar"],
        "schwaechen": ["Analyse konnte nicht vollständig durchgeführt werden"],
        "keywords_fehlen": ["Bitte Analyse erneut starten"],
        "keywords_vorhanden": [],
        "format_tipps": ["Nutze ein ATS-freundliches Format"],
        "top_empfehlung": "Versuche die Analyse erneut oder prüfe das Modell.",
        "berufsfeld": "Unbekannt",
        "erfahrung_jahre": 0,
        "ats_score": 50,
    }, cv_text, raw=raw)


def optimize_cv(cv_text: str, user_name: str, target_role: str = "", analysis: dict | None = None) -> str:
    """Erstellt eine optimierte Version des Lebenslaufs."""
    system = (
        "Du bist ein professioneller CV-Schreiber für den deutschsprachigen Markt. "
        "Optimiere den Lebenslauf: bessere Formulierungen, starke Action-Verben, "
        "ATS-Keywords, klare Struktur. Behalte alle echten Fakten bei, "
        "aber formuliere professioneller und wirkungsvoller. "
        "Erfinde keine Abschluesse, Arbeitgeber, Technologien oder Zahlen. "
        "Wenn eine Kennzahl fehlt, markiere sie als [Kennzahl ergaenzen]."
    )
    analysis_hint = ""
    if analysis:
        analysis_hint = (
            "\nBeruecksichtige diese Analysepunkte:\n"
            f"- Fehlende Keywords: {', '.join(analysis.get('keywords_fehlen', [])[:8])}\n"
            f"- Wichtigste Empfehlung: {analysis.get('top_empfehlung', '')}\n"
        )
    target_hint = f"\nZielstelle/Zielrolle: {target_role}" if target_role.strip() else ""
    prompt = (
        f"Optimiere diesen Lebenslauf fuer den deutschen Jobmarkt.{target_hint}{analysis_hint}\n\n"
        "Ausgabe-Struktur:\n"
        "1. Kurzprofil\n"
        "2. Kernkompetenzen / Tech-Stack / Keywords\n"
        "3. Berufserfahrung mit wirkungsorientierten Bulletpoints\n"
        "4. Projekte, Ausbildung, Zertifikate, Sprachen soweit im Original vorhanden\n"
        "5. Am Ende: 'Noch zu ergaenzen' mit fehlenden Informationen\n\n"
        f"Lebenslauf:\n{clip_text(cv_text, MAX_CV_CHARS)}"
    )
    return call_ollama(prompt, system, max_tokens=1800)


def get_avatar_video(text: str):
    """D-ID Video Generation."""
    url = "https://api.d-id.com/talks"
    auth = base64.b64encode(DID_API_KEY.encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
    payload = {
        "script": {
            "type": "text",
            "input": text[:400],  # D-ID Limit
            "provider": {"type": "microsoft", "voice_id": "de-DE-KatjaNeural"}
        },
        "presenter_id": "amy-j_9uz7X6Yv",
        "driver_id": "V97S9N7996"
    }
    try:
        res = requests.post(url, json=payload, headers=headers)
        talk_id = res.json().get("id")
        if talk_id:
            for _ in range(30):
                check = requests.get(f"{url}/{talk_id}", headers=headers).json()
                if check.get("status") == "done":
                    return check.get("result_url")
                time.sleep(3)
    except:
        pass
    return None


def play_audio_tts(text: str, lang: str = "de"):
    """Erstellt Audio über gTTS."""
    if not GTTS_AVAILABLE:
        st.warning("gTTS nicht installiert: `pip install gTTS`")
        return
    try:
        tts = gTTS(text=text[:500], lang=lang)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        st.audio(fp, format="audio/mp3")
    except Exception as e:
        st.warning(f"Audio-Fehler: {e}")


IKIGAI_FRAGEN = [
    ("Was liebst du?", "Was machst du gerne, auch ohne Bezahlung? Womit verlierst du das Zeitgefühl?"),
    ("Worin bist du gut?", "Welche Fähigkeiten und Talente hast du? Was loben andere an dir?"),
    ("Was braucht die Welt?", "Welches Problem möchtest du lösen? Welchen Beitrag möchtest du leisten?"),
    ("Wofür wirst du bezahlt?", "Welche deiner Fähigkeiten hat wirtschaftlichen Wert? Womit verdienst du Geld?"),
]


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎯 Smart Coach Pro")
    st.markdown('<div class="section-label">Benutzerprofil</div>', unsafe_allow_html=True)
    user_name = st.text_input("Name / Tên:", value="Gast", key="user_name_input")
    
    lang_choice = st.selectbox("Sprache / Ngôn ngữ:", ["🇩🇪 Deutsch", "🇻🇳 Tiếng Việt"], key="lang")
    tts_lang = "de" if "Deutsch" in lang_choice else "vi"
    
    st.divider()
    st.markdown('<div class="section-label">Lebenslauf hochladen</div>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader(
        "CV hochladen (PDF, DOCX, TXT)",
        type=["pdf", "docx", "txt"],
        key="cv_uploader"
    )
    
    if uploaded_file:
        file_bytes = uploaded_file.read()
        fname = uploaded_file.name
        
        if fname != st.session_state.cv_filename:
            with st.spinner("📄 Lese Dokument..."):
                if fname.endswith(".pdf"):
                    text = extract_pdf_text(file_bytes)
                elif fname.endswith(".docx"):
                    text = extract_docx_text(file_bytes)
                else:
                    text = file_bytes.decode("utf-8", errors="ignore")
            
            st.session_state.cv_text = clean_cv_text(text)
            st.session_state.cv_filename = fname
            st.session_state.cv_analysis = None  # Reset bei neuem CV
            st.success(f"✅ {fname} geladen ({len(st.session_state.cv_text)} Zeichen)")
    
    if st.session_state.cv_text:
        words = len(st.session_state.cv_text.split())
        st.caption(f"📊 ~{words} Wörter im CV")
    
    st.divider()
    st.markdown('<div class="section-label">Einstellungen</div>', unsafe_allow_html=True)
    st.session_state.ollama_model = st.text_input(
        "Ollama-Modell:",
        value=st.session_state.ollama_model,
        help="Für bessere CV-Analysen nutze, falls installiert, z.B. llama3.1, mistral oder qwen2.5.",
    )
    audio_on = st.toggle("🔊 Ton-Ausgabe", value=True)
    video_on = st.toggle("🎬 Video-Modus (D-ID Credits)", value=False)
    
    st.divider()
    
    # Ollama Status
    if st.button("🔌 Ollama-Verbindung prüfen"):
        ok = check_ollama()
        st.session_state.ollama_available = ok
        if ok:
            st.success("Ollama erreichbar ✓")
        else:
            st.error("Ollama nicht erreichbar. Starte: `ollama serve`")
    
    st.divider()
    st.caption("Smart Coach Pro v2.0 | Powered by Ollama + D-ID")


# ─────────────────────────────────────────────
# HAUPTBEREICH
# ─────────────────────────────────────────────
st.markdown(f"""
<div class="coach-header">
    <h2 style="margin:0; color:#e8eaf0;">🎯 Smart Coach Pro <span style="font-size:0.6em; color:#6b7280; font-weight:400;">v2.0</span></h2>
    <p style="margin:4px 0 0; color:#9ca3af; font-size:0.9rem;">Dein KI-Karriereberater · Lebenslauf-Analyse · IKIGAI Coach</p>
</div>
""", unsafe_allow_html=True)

# TABS
tab_chat, tab_analyse, tab_optimierung, tab_ikigai = st.tabs([
    "💬 Coach Chat", "🔍 CV Analyse", "✨ CV Optimierung", "🌸 IKIGAI"
])


# ══════════════════════════════════════════════
# TAB 1: CHAT
# ══════════════════════════════════════════════
with tab_chat:
    # Chat-Verlauf anzeigen
    chat_container = st.container()
    with chat_container:
        if not st.session_state.chat_history:
            st.markdown(f"""
            <div class="chat-bubble-coach">
                👋 Hallo <strong>{user_name}</strong>! Ich bin dein persönlicher Smart Coach.<br><br>
                Ich kann dir helfen bei:<br>
                • <strong>Karriereplanung</strong> und Bewerbungsstrategien<br>
                • <strong>Lebenslauf-Feedback</strong> (lade deinen CV hoch!)<br>
                • <strong>Stärken & Schwächen</strong> erkennen<br>
                • <strong>Deutschen Jobmarkt</strong> und IT-Karrierewege<br><br>
                Was beschäftigt dich gerade?
            </div>
            """, unsafe_allow_html=True)
        else:
            for msg in st.session_state.chat_history:
                safe_msg = html.escape(msg["content"]).replace("\n", "<br>")
                if msg["role"] == "user":
                    st.markdown(f'<div class="chat-bubble-user">👤 {safe_msg}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="chat-bubble-coach">🎯 {safe_msg}</div>', unsafe_allow_html=True)
    
    st.markdown("")
    
    col_input, col_btn = st.columns([5, 1])
    with col_input:
        user_input = st.text_input(
            "Nachricht:",
            placeholder="z.B. 'Analysiere meinen Lebenslauf' oder 'Ich suche einen Job im IT-Bereich'...",
            key="chat_input",
            label_visibility="collapsed"
        )
    with col_btn:
        send_btn = st.button("Senden →", use_container_width=True)
    
    col_c1, col_c2, col_c3, col_c4 = st.columns(4)
    with col_c1:
        if st.button("💡 Stärken analysieren", use_container_width=True):
            user_input = "Analysiere meine Stärken basierend auf meinem Lebenslauf"
            send_btn = True
    with col_c2:
        if st.button("🎯 Karrieretipps", use_container_width=True):
            user_input = "Welche Karrieremöglichkeiten passen zu meinem Profil?"
            send_btn = True
    with col_c3:
        if st.button("📝 Bewerbung tipps", use_container_width=True):
            user_input = "Gib mir Tipps für meine Bewerbung im deutschen Jobmarkt"
            send_btn = True
    with col_c4:
        if st.button("🗑️ Chat leeren", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()
    
    if send_btn and user_input and user_input.strip():
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        with st.spinner("Coach antwortet..."):
            history_ctx = build_chat_context(st.session_state.chat_history[:-1])
            system = build_coach_system(user_name, st.session_state.cv_text)
            
            full_prompt = user_input
            if history_ctx:
                full_prompt = f"Bisheriger Gesprächsverlauf:\n{history_ctx}\n\nAktuelle Frage: {user_input}"
            
            response = call_ollama(full_prompt, system)
        
        st.session_state.chat_history.append({"role": "assistant", "content": response})
        
        if audio_on and not video_on:
            play_audio_tts(response, lang=tts_lang)
        
        if video_on:
            with st.spinner("🎬 Video wird generiert..."):
                video_url = get_avatar_video(response)
                if video_url:
                    st.video(video_url)
        
        st.rerun()


# ══════════════════════════════════════════════
# TAB 2: CV ANALYSE
# ══════════════════════════════════════════════
with tab_analyse:
    if not st.session_state.cv_text:
        st.info("📄 Bitte zuerst einen Lebenslauf in der Seitenleiste hochladen.")
    else:
        st.markdown(f"**Geladener Lebenslauf:** `{st.session_state.cv_filename}`")
        analyse_zielstelle = st.text_input(
            "🎯 Zielstelle / Zielrolle für die Analyse (optional):",
            placeholder="z.B. IAM Consultant, IT Support, Data Analyst, Projektmanager",
            key="analyse_zielstelle",
        )
        
        if st.button("🔍 Vollständige Analyse starten", use_container_width=True):
            with st.spinner("🧠 KI analysiert deinen Lebenslauf... (30–60 Sekunden)"):
                result = analyze_cv_structured(st.session_state.cv_text, user_name, analyse_zielstelle)
            st.session_state.cv_analysis = result
        
        if st.session_state.cv_analysis:
            data = st.session_state.cv_analysis
            
            st.markdown("---")
            
            # Score-Karten
            col1, col2, col3, col4 = st.columns(4)
            
            score = data.get("score", 0)
            ats = data.get("ats_score", 0)
            jahre = data.get("erfahrung_jahre", 0)
            
            def score_class(s):
                return "score-high" if s >= 70 else ("score-mid" if s >= 50 else "score-low")
            
            with col1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="section-label">Gesamtscore</div>
                    <div class="metric-score {score_class(score)}">{score}</div>
                    <div style="color:#6b7280; font-size:0.8rem;">/100</div>
                </div>""", unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="section-label">ATS Score</div>
                    <div class="metric-score {score_class(ats)}">{ats}</div>
                    <div style="color:#6b7280; font-size:0.8rem;">Automatisch lesbar</div>
                </div>""", unsafe_allow_html=True)
            with col3:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="section-label">Erfahrung</div>
                    <div class="metric-score" style="color:#c084fc;">{jahre}</div>
                    <div style="color:#6b7280; font-size:0.8rem;">Jahre (geschätzt)</div>
                </div>""", unsafe_allow_html=True)
            with col4:
                field = html.escape(str(data.get("berufsfeld", "—")))
                st.markdown(f"""
                <div class="metric-card">
                    <div class="section-label">Berufsfeld</div>
                    <div style="color:#60a5fa; font-size:1.1rem; font-weight:600; margin-top:8px;">{field}</div>
                </div>""", unsafe_allow_html=True)
            
            st.markdown("---")
            
            col_l, col_r = st.columns(2)
            
            with col_l:
                # Stärken
                st.markdown('<div class="section-label">✅ Stärken</div>', unsafe_allow_html=True)
                for s in data.get("staerken", []):
                    st.markdown(f'<div class="analysis-block strength">💪 {html.escape(str(s))}</div>', unsafe_allow_html=True)
                
                st.markdown('<br><div class="section-label">🔑 Vorhandene Keywords</div>', unsafe_allow_html=True)
                kws = data.get("keywords_vorhanden", [])
                if kws:
                    pills = "".join(f'<span class="tag-pill">{html.escape(str(k))}</span>' for k in kws)
                    st.markdown(pills, unsafe_allow_html=True)
                else:
                    st.caption("Keine Keywords erkannt")

                zielrollen = data.get("zielrollen", [])
                if zielrollen:
                    st.markdown('<br><div class="section-label">🎯 Passende Zielrollen</div>', unsafe_allow_html=True)
                    pills = "".join(f'<span class="tag-pill">{html.escape(str(k))}</span>' for k in zielrollen)
                    st.markdown(pills, unsafe_allow_html=True)
            
            with col_r:
                # Schwächen
                st.markdown('<div class="section-label">⚠️ Verbesserungspotenzial</div>', unsafe_allow_html=True)
                for w in data.get("schwaechen", []):
                    st.markdown(f'<div class="analysis-block weakness">🔧 {html.escape(str(w))}</div>', unsafe_allow_html=True)
                
                st.markdown('<br><div class="section-label">➕ Fehlende Keywords</div>', unsafe_allow_html=True)
                missing = data.get("keywords_fehlen", [])
                if missing:
                    pills = "".join(f'<span class="tag-pill" style="border-color:#f87171; color:#fca5a5;">{html.escape(str(k))}</span>' for k in missing)
                    st.markdown(pills, unsafe_allow_html=True)

                missing_sections = data.get("missing_sections", [])
                if missing_sections:
                    st.markdown('<br><div class="section-label">📌 Fehlende Abschnitte</div>', unsafe_allow_html=True)
                    pills = "".join(f'<span class="tag-pill" style="border-color:#facc15; color:#fde68a;">{html.escape(str(k))}</span>' for k in missing_sections)
                    st.markdown(pills, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Format-Tipps
            st.markdown('<div class="section-label">📐 Format & Struktur Tipps</div>', unsafe_allow_html=True)
            for tip in data.get("format_tipps", []):
                st.markdown(f'<div class="analysis-block tip">💡 {html.escape(str(tip))}</div>', unsafe_allow_html=True)

            inhalt_tipps = data.get("inhalt_tipps", [])
            if inhalt_tipps:
                st.markdown('<br><div class="section-label">🧠 Inhaltliche Verbesserungen</div>', unsafe_allow_html=True)
                for tip in inhalt_tipps:
                    st.markdown(f'<div class="analysis-block keyword">🧩 {html.escape(str(tip))}</div>', unsafe_allow_html=True)

            rewrites = data.get("konkrete_rewrites", [])
            if rewrites:
                st.markdown('<br><div class="section-label">✍️ Konkrete Rewrite-Vorschläge</div>', unsafe_allow_html=True)
                for rewrite in rewrites:
                    st.markdown(f'<div class="analysis-block">✍️ {html.escape(str(rewrite))}</div>', unsafe_allow_html=True)

            interview_questions = data.get("interview_fragen", [])
            if interview_questions:
                st.markdown('<br><div class="section-label">🎤 Mögliche Interviewfragen</div>', unsafe_allow_html=True)
                for question in interview_questions:
                    st.markdown(f'<div class="analysis-block keyword">🎤 {html.escape(str(question))}</div>', unsafe_allow_html=True)

            steps = data.get("naechste_schritte", [])
            if steps:
                st.markdown('<br><div class="section-label">✅ Nächste Schritte</div>', unsafe_allow_html=True)
                for step_item in steps:
                    st.markdown(f'<div class="analysis-block tip">➡️ {html.escape(str(step_item))}</div>', unsafe_allow_html=True)
            
            # Top-Empfehlung
            top = data.get("top_empfehlung", "")
            if top:
                st.markdown("---")
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #312e81, #1e1b4b); border-radius: 12px; padding: 16px 20px;">
                    <div class="section-label" style="color:#a5b4fc;">🚀 Wichtigste Maßnahme</div>
                    <p style="color:#e8eaf0; margin:0; font-size:1rem;">{html.escape(str(top))}</p>
                </div>""", unsafe_allow_html=True)
            
            # CV-Text Vorschau
            with st.expander("📄 Roher CV-Text (Vorschau)"):
                st.text(st.session_state.cv_text[:2000] + ("..." if len(st.session_state.cv_text) > 2000 else ""))

            report_lines = [
                f"CV-Analyse fuer {user_name}",
                f"Datei: {st.session_state.cv_filename}",
                f"Gesamtscore: {score}/100",
                f"ATS-Score: {ats}/100",
                f"Berufsfeld: {data.get('berufsfeld', 'Nicht erkannt')}",
                "",
                "Staerken:",
                *[f"- {x}" for x in data.get("staerken", [])],
                "",
                "Verbesserungspotenzial:",
                *[f"- {x}" for x in data.get("schwaechen", [])],
                "",
                "Fehlende Keywords:",
                *[f"- {x}" for x in data.get("keywords_fehlen", [])],
                "",
                "Top-Empfehlung:",
                data.get("top_empfehlung", ""),
                "",
                "Naechste Schritte:",
                *[f"- {x}" for x in data.get("naechste_schritte", [])],
            ]
            st.download_button(
                label="⬇️ Analysebericht als TXT herunterladen",
                data="\n".join(report_lines),
                file_name=f"CV_Analyse_{user_name}_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain",
                use_container_width=True,
            )


# ══════════════════════════════════════════════
# TAB 3: CV OPTIMIERUNG
# ══════════════════════════════════════════════
with tab_optimierung:
    if not st.session_state.cv_text:
        st.info("📄 Bitte zuerst einen Lebenslauf in der Seitenleiste hochladen.")
    else:
        st.markdown(f"**Geladener Lebenslauf:** `{st.session_state.cv_filename}`")
        st.markdown("""
        Der Coach überarbeitet deinen Lebenslauf mit:  
        - Stärkeren Action-Verben und professionelleren Formulierungen  
        - ATS-optimierten Keywords für Bewerbermanagementsysteme  
        - Klarerer Struktur für den deutschen Jobmarkt  
        """)
        
        # Zielstelle (optional)
        zielstelle = st.text_input(
            "🎯 Zielstelle (optional):",
            placeholder="z.B. 'Senior IT Auditor bei einer deutschen Bank' oder 'IAM Consultant'",
            key="zielstelle"
        )
        
        if st.button("✨ Lebenslauf jetzt optimieren", use_container_width=True):
            with st.spinner("🧠 Optimiere deinen Lebenslauf... (bis zu 60 Sekunden)"):
                result = optimize_cv(
                    st.session_state.cv_text,
                    user_name,
                    zielstelle,
                    st.session_state.cv_analysis,
                )
            st.session_state.optimized_cv = result
        
        if st.session_state.optimized_cv:
            st.markdown("---")
            st.markdown('<div class="section-label">✅ Optimierter Lebenslauf</div>', unsafe_allow_html=True)
            
            st.markdown(
                f'<div class="optimized-cv">{html.escape(st.session_state.optimized_cv)}</div>',
                unsafe_allow_html=True
            )
            
            # Download-Button
            st.download_button(
                label="⬇️ Als TXT herunterladen",
                data=st.session_state.optimized_cv,
                file_name=f"Optimierter_Lebenslauf_{user_name}_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain",
                use_container_width=True
            )
            
            # Direkt als Chat-Kontext speichern
            if st.button("💬 Im Chat besprechen", use_container_width=True):
                msg = "Ich habe meinen Lebenslauf gerade optimiert. Kannst du mir die wichtigsten Verbesserungen erklären und weitere Tipps geben?"
                st.session_state.chat_history.append({"role": "user", "content": msg})
                with st.spinner("Coach antwortet..."):
                    response = call_ollama(
                        msg,
                        build_coach_system(user_name, st.session_state.optimized_cv)
                    )
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.info("Antwort im Chat gespeichert → wechsle zum 'Coach Chat' Tab")


# ══════════════════════════════════════════════
# TAB 4: IKIGAI
# ══════════════════════════════════════════════
with tab_ikigai:
    st.markdown("""
    <div style="text-align:center; padding: 10px 0 20px;">
        <div style="font-size: 2.5rem;">🌸</div>
        <h3 style="color:#e8eaf0; margin:8px 0 4px;">IKIGAI-Analyse</h3>
        <p style="color:#9ca3af; font-size:0.9rem;">Finde deine Lebensaufgabe: Was liebst du, worin bist du gut,<br>was braucht die Welt, und wofür wirst du bezahlt?</p>
    </div>
    """, unsafe_allow_html=True)
    
    step = st.session_state.ikigai_step
    answers = st.session_state.ikigai_answers
    
    if step < len(IKIGAI_FRAGEN):
        # Fortschrittsanzeige
        progress = step / len(IKIGAI_FRAGEN)
        st.progress(progress)
        st.caption(f"Schritt {step + 1} von {len(IKIGAI_FRAGEN)}")
        
        frage, hinweis = IKIGAI_FRAGEN[step]
        
        st.markdown(f"""
        <div style="background:#1a1f2e; border-radius:12px; padding:20px; margin:10px 0;">
            <div style="color:#a5b4fc; font-size:0.8rem; margin-bottom:8px;">FRAGE {step+1}</div>
            <h4 style="color:#e8eaf0; margin:0 0 8px;">{frage}</h4>
            <p style="color:#9ca3af; font-size:0.9rem; margin:0;">{hinweis}</p>
        </div>
        """, unsafe_allow_html=True)
        
        antwort = st.text_area(
            "Deine Antwort:",
            height=100,
            key=f"ikigai_q{step}",
            placeholder="Schreibe frei und ehrlich..."
        )
        
        col_back, col_next = st.columns([1, 3])
        with col_back:
            if step > 0 and st.button("← Zurück"):
                st.session_state.ikigai_step -= 1
                st.rerun()
        with col_next:
            if st.button("Weiter →" if step < 3 else "🌸 Analyse erstellen", use_container_width=True):
                if antwort.strip():
                    st.session_state.ikigai_answers[IKIGAI_FRAGEN[step][0]] = antwort
                    st.session_state.ikigai_step += 1
                    st.rerun()
                else:
                    st.warning("Bitte beantworte die Frage.")
    
    elif step == len(IKIGAI_FRAGEN) and not st.session_state.ikigai_result:
        with st.spinner("🌸 Erstelle deine IKIGAI-Analyse..."):
            answers_text = "\n".join(f"**{q}**: {a}" for q, a in answers.items())
            system = (
                "Du bist ein IKIGAI-Coach und Karriereberater. "
                "Analysiere die Antworten und erstelle eine tiefgründige, "
                "persönliche IKIGAI-Analyse. Sei konkret, inspirierend und ehrlich. "
                "Identifiziere Überschneidungen und schlage 2-3 konkrete Berufsfelder vor."
            )
            prompt = (
                f"Erstelle eine vollständige IKIGAI-Analyse für {user_name} "
                f"basierend auf diesen Antworten:\n\n{answers_text}\n\n"
                "Struktur: 1) IKIGAI-Überschneidungen, 2) Mein Kernpotenzial, "
                "3) Konkrete Karriereempfehlungen, 4) Nächste Schritte"
            )
            result = call_ollama(prompt, system, max_tokens=1000)
        st.session_state.ikigai_result = result
        st.rerun()
    
    elif st.session_state.ikigai_result:
        st.markdown("### 🌸 Deine IKIGAI-Analyse")
        
        st.markdown(f"""
        <div style="background:#1a1f2e; border-radius:12px; padding:20px; line-height:1.8; color:#d1d5db;">
            {st.session_state.ikigai_result.replace(chr(10), '<br>')}
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "⬇️ Analyse speichern",
                data=st.session_state.ikigai_result,
                file_name=f"IKIGAI_{user_name}_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain",
                use_container_width=True
            )
        with col2:
            if st.button("🔄 Neu starten", use_container_width=True):
                st.session_state.ikigai_step = 0
                st.session_state.ikigai_answers = {}
                st.session_state.ikigai_result = ""
                st.rerun()
        
        if audio_on:
            st.markdown("**🔊 Analyse vorlesen:**")
            play_audio_tts(st.session_state.ikigai_result[:500], lang=tts_lang)

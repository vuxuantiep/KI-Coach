import streamlit as st
import requests
import base64
import time
import io
import json
import re
import html
from datetime import datetime
from groq import Groq

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

# Groq Setup (Ersetzt Ollama vollständig)
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)
GROQ_MODEL = "llama3-8b-8192" 

MAX_CV_CHARS = 12000
CV_CONTEXT_CHARS = 8000

# ─────────────────────────────────────────────
# KI FUNKTION (GROQ)
# ─────────────────────────────────────────────
def call_groq(prompt, system_prompt="Du bist ein hilfreicher Coach.", max_tokens=1000):
    """Nutzt Groq Cloud API"""
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Fehler bei der KI-Anfrage: {str(e)}"

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
        line-height: 1.2;
        background: linear-gradient(90deg, #6366f1, #a855f7);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .metric-label { font-size: 0.85rem; color: #94a3b8; margin-top: 4px; }
    [data-testid="stSidebar"] { background-color: #111827; border-right: 1px solid #1f2937; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "cv_text" not in st.session_state:
    st.session_state.cv_text = None
if "ikigai_step" not in st.session_state:
    st.session_state.ikigai_step = 0
if "ikigai_answers" not in st.session_state:
    st.session_state.ikigai_answers = {}
if "ikigai_result" not in st.session_state:
    st.session_state.ikigai_result = None

# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────
def extract_text_from_pdf(file):
    if not PDF_AVAILABLE: return "PDF Reader nicht installiert."
    with pdfplumber.open(file) as pdf:
        return "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])

def extract_text_from_docx(file):
    if not DOCX_AVAILABLE: return "Word Reader nicht installiert."
    doc = Document(file)
    return "\n".join([p.text for p in doc.paragraphs])

# ─────────────────────────────────────────────
# HEADER & SIDEBAR
# ─────────────────────────────────────────────
st.markdown('<div class="coach-header"><h1>🎯 Smart Coach Pro <span style="font-size:0.5em; color:#6366f1;">v2.0</span></h1><p style="color:#94a3b8; margin:0;">Dein persönlicher KI-Karrierebegleiter</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3940/3940403.png", width=80)
    st.title("Settings")
    user_name = st.text_input("Dein Name", value="Gast")
    st.divider()
    uploaded_file = st.file_uploader("CV hochladen", type=["pdf", "docx"])
    if uploaded_file:
        if uploaded_file.type == "application/pdf":
            st.session_state.cv_text = extract_text_from_pdf(uploaded_file)
        else:
            st.session_state.cv_text = extract_text_from_docx(uploaded_file)
        st.success("CV geladen!")

# ─────────────────────────────────────────────
# MAIN LAYOUT
# ─────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["💬 Chat", "🌸 IKIGAI", "📈 Dashboard"])

with tab1:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Schreibe etwas..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        context = f"Lebenslauf: {st.session_state.cv_text[:2000]}" if st.session_state.cv_text else ""
        full_prompt = f"{context}\nNutzer: {prompt}"
        
        with st.chat_message("assistant"):
            # Korrigierter Aufruf
            response = call_groq(full_prompt) 
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

with tab2:
    st.subheader("IKIGAI Analyse")
    questions = ["Was liebst du?", "Was kannst du?", "Was braucht die Welt?", "Was bringt Geld?"]
    
    if st.session_state.ikigai_step < 4:
        ans = st.text_area(questions[st.session_state.ikigai_step])
        if st.button("Weiter"):
            st.session_state.ikigai_answers[st.session_state.ikigai_step] = ans
            st.session_state.ikigai_step += 1
            st.rerun()
    elif not st.session_state.ikigai_result:
        with st.spinner("Analysiere..."):
            # Korrigierter Aufruf von call_ollama zu call_groq
            st.session_state.ikigai_result = call_groq(str(st.session_state.ikigai_answers))
            st.rerun()
    else:
        st.markdown(st.session_state.ikigai_result)
        if st.button("Reset"):
            st.session_state.ikigai_step = 0
            st.session_state.ikigai_result = None
            st.rerun()

with tab3:
    st.info("Statistiken folgen bald.")
import streamlit as st
import requests
import pandas as pd
from datetime import datetime

try:
    from supabase import create_client
except ImportError:
    st.error("Instale supabase no requirements.txt")
    st.stop()

from ao_vivo import tela_ao_vivo
from pre_jogo import tela_pre_jogo
from alavancagem import tela_alavancagem
from bilhete_especial import tela_bilhete_especial
from shadow_lab import tela_shadow_lab
from painel_do_dia import tela_painel_do_dia

# =====================================================
# CONFIG
# =====================================================
st.set_page_config(
    page_title="REI-DO-RED",
    page_icon="🏆",
    layout="wide"
)

# =====================================================
# CSS PREMIUM
# =====================================================
st.markdown("""
<style>
.stApp {
    background:
        radial-gradient(circle at 10% 0%, rgba(124,58,237,.18), transparent 28%),
        radial-gradient(circle at 90% 10%, rgba(37,99,235,.14), transparent 24%),
        linear-gradient(180deg,#07111f 0%,#0b1020 50%,#0a0f1d 100%);
}
.block-container { padding-top: 1rem; max-width: 1500px; }
h1, h2, h3 { color: white; letter-spacing: -0.02em; }
.stMetric {
    background: linear-gradient(145deg,rgba(20,27,45,.96),rgba(29,40,64,.92));
    border-radius: 18px;
    padding: 15px;
    border: 1px solid rgba(124,58,237,.72);
    box-shadow: 0 10px 35px rgba(0,0,0,.22);
}
div[data-testid="stMetricValue"] { font-weight: 800; }
.stButton>button {
    width: 100%;
    border-radius: 10px;
    background: linear-gradient(90deg,#7a3cff,#4f46e5);
    color: white;
    font-weight: bold;
    border: none;
    padding: 12px;
}
.stButton>button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 20px rgba(122,60,255,0.4);
}
.stExpander {
    border: 1px solid #252f48;
    border-radius: 15px;
    background: #121a2b;
}
div[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#0b1220,#0d1117);
    border-right: 1px solid rgba(148,163,184,.12);
}
.stTabs [data-baseweb="tab-list"] {
    gap: .45rem;
    background: rgba(15,23,42,.72);
    border: 1px solid rgba(148,163,184,.12);
    padding: .45rem;
    border-radius: 16px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 12px;
    padding: .55rem .8rem;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(90deg,rgba(124,58,237,.28),rgba(79,70,229,.24));
}
.signal-card {
    background: linear-gradient(145deg,rgba(18,26,43,.98),rgba(13,20,34,.96));
    border: 1px solid rgba(148,163,184,.14);
    border-radius: 18px;
    padding: 14px 16px;
    margin: 8px 0;
    box-shadow: 0 10px 30px rgba(0,0,0,.18);
}
.signal-title { font-weight: 800; font-size: 1rem; color: #f8fafc; }
.signal-meta { color: #94a3b8; font-size: .88rem; margin-top: 4px; }
.badge {
    display: inline-block;
    padding: 3px 9px;
    border-radius: 999px;
    font-size: .75rem;
    font-weight: 800;
    margin-left: 8px;
}
.badge-signal { background: rgba(34,197,94,.16); color: #86efac; border: 1px solid rgba(34,197,94,.35); }
.badge-watch { background: rgba(234,179,8,.14); color: #fde68a; border: 1px solid rgba(234,179,8,.35); }
.badge-no { background: rgba(239,68,68,.12); color: #fca5a5; border: 1px solid rgba(239,68,68,.30); }
.badge-data { background: rgba(59,130,246,.14); color: #93c5fd; border: 1px solid rgba(59,130,246,.30); }
.api-counter {
    background: linear-gradient(135deg,#1a1a0a,#2a2a1a);
    border: 1px solid #eab308;
    border-radius: 12px;
    padding: 10px 16px;
    text-align: center;
    margin: 6px 0;
}
.api-counter span { color: #eab308; font-weight: bold; font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# CONTADOR DE API
# =====================================================
LIMITE_DIARIO_API = 7500

def get_api_usage_key():
    return "api_calls_" + datetime.now().strftime("%Y-%m-%d")

def registrar_chamada_api():
    key = get_api_usage_key()
    if key not in st.session_state:
        st.session_state[key] = 0
    st.session_state[key] += 1

def get_chamadas_hoje():
    return st.session_state.get(get_api_usage_key(), 0)

# =====================================================
# INICIALIZAR SUPABASE
# =====================================================
@st.cache_resource
def init_supabase():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        st.error("Erro Supabase: " + str(e))
        return None

supabase = init_supabase()

# =====================================================
# API FOOTBALL
# =====================================================
API_KEY = st.secrets["API_KEY"]
HEADERS = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}

@st.cache_data(ttl=60)
def fetch_api(endpoint):
    try:
        url = "https://v3.football.api-sports.io/" + endpoint
        r = requests.get(url, headers=HEADERS, timeout=15)
        registrar_chamada_api()
        if r.status_code != 200:
            return []
        return r.json().get("response", [])
    except Exception:
        return []

# =====================================================
# TELEGRAM
# =====================================================
TELEGRAM_TOKEN   = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

def enviar_telegram(msg):
    try:
        r = requests.post(
            "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
        return r.status_code == 200
    except Exception:
        return False

# =====================================================
# SALVAR RESULTADO
# =====================================================
def salvar_resultado(jogo, resultado, confianca):
    try:
        supabase.table("historico").insert({
            "data": datetime.now().isoformat(),
            "jogo": jogo,
            "resultado": resultado,
            "confianca": confianca
        }).execute()
        st.success(resultado + " registrado!")
    except Exception as e:
        st.error("Erro ao salvar: " + str(e))

# =====================================================
# SIDEBAR
# =====================================================
st.sidebar.title("🏆 REI-DO-RED")
st.sidebar.markdown("**Painel Premium**")
st.sidebar.markdown("---")

chamadas_hoje = get_chamadas_hoje()
restantes = max(0, LIMITE_DIARIO_API - chamadas_hoje)
pct_uso = min(100, int((chamadas_hoje / LIMITE_DIARIO_API) * 100))

st.sidebar.markdown("### 📡 Uso da API Hoje")
st.sidebar.markdown(
    "<div class='api-counter'>"
    "<span>" + str(restantes) + " chamadas restantes</span><br>"
    "<small style='color:#94a3b8'>Usadas: " + str(chamadas_hoje) + " / " + str(LIMITE_DIARIO_API) + "</small>"
    "<div style='background:#1e293b;border-radius:999px;height:8px;margin-top:6px'>"
    "<div style='width:" + str(pct_uso) + "%;height:100%;background:linear-gradient(90deg,#22c55e,#ef4444);border-radius:999px'></div>"
    "</div></div>",
    unsafe_allow_html=True
)
st.sidebar.markdown("---")

greens = reds = winrate = 0
try:
    hdata = supabase.table("historico").select("*").execute()
    if hdata.data:
        df_h = pd.DataFrame(hdata.data)
        greens = len(df_h[df_h["resultado"] == "GREEN"])
        reds   = len(df_h[df_h["resultado"] == "RED"])
        total  = greens + reds
        if total > 0:
            winrate = round((greens / total) * 100, 1)
except Exception:
    pass

col_g, col_r = st.sidebar.columns(2)
col_g.metric("✅ Greens", greens)
col_r.metric("❌ Reds", reds)
st.sidebar.metric("📈 Winrate", str(winrate) + "%")
st.sidebar.markdown("---")

if st.sidebar.button("📲 Testar Telegram"):
    ok = enviar_telegram("<b>🏆 REI-DO-RED</b> - Telegram OK!")
    st.sidebar.success("✅ OK!") if ok else st.sidebar.error("❌ Falha.")

# =====================================================
# HEADER
# =====================================================
st.title("🏆 REI-DO-RED")
st.caption("Radar inteligente para traders esportivos")
st.markdown("---")

# =====================================================
# TABS
# =====================================================
aba0, aba1, aba2, aba3, aba4, aba5 = st.tabs([
    "📊 PAINEL DO DIA",
    "🔴 AO VIVO",
    "⚽ PRÉ-JOGO",
    "🚀 ALAVANCAGEM",
    "💎 BILHETE ESPECIAL",
    "🧪 SHADOW LAB",
])

with aba0:
    tela_painel_do_dia()

with aba1:
    tela_ao_vivo(fetch_api, enviar_telegram, salvar_resultado)

with aba2:
    tela_pre_jogo(enviar_telegram, salvar_resultado, supabase=supabase)

with aba3:
    tela_alavancagem(supabase=supabase)

with aba4:
    tela_bilhete_especial()

with aba5:
    tela_shadow_lab(supabase)

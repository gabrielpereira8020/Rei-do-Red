import streamlit as st
from pre_jogo import tela_pre_jogo
from ao_vivo import tela_ao_vivo

st.set_page_config(
    page_title="Rei do Red",
    page_icon="🔥",
    layout="wide"
)

st.title("🔥 REI DO RED")

modo = st.sidebar.selectbox(
    "Escolha o modo",
    ["Pré Jogo", "Ao Vivo"]
)

if modo == "Pré Jogo":
    tela_pre_jogo()

elif modo == "Ao Vivo":
    tela_ao_vivo()

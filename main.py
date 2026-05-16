import streamlit as st
from google import genai

st.title("🔍 Diagnóstico Gemini")

try:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    
    st.success("✅ Conexão com a API OK!")
    
    # Versão da SDK instalada
    import google.genai as g
    st.info(f"📦 Versão da SDK google-genai: {g.__version__}")
    
    st.subheader("📋 Modelos disponíveis para sua chave:")
    
    modelos = client.models.list()
    
    count = 0
    for modelo in modelos:
        st.write(f"✅ `{modelo.name}`")
        count += 1
    
    if count == 0:
        st.warning("Nenhum modelo encontrado para esta chave.")
    else:
        st.success(f"Total: {count} modelos encontrados")

except Exception as e:
    st.error(f"❌ Erro: {str(e)}")

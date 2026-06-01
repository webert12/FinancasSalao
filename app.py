import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import json
import time
import hashlib

# --- CONFIGURAÇÃO ---
SALT = "salao_fio_caixa_2026_security"
TZ = ZoneInfo("America/Sao_Paulo")
USUARIOS_FILE = "usuarios.json"
ADMIN_CONFIG_FILE = "admin_config.json"

# --- FUNÇÕES DE SEGURANÇA E ARQUIVOS ---
def hash_password(password):
    return hashlib.sha256((password + SALT).encode()).hexdigest()

def carregar_admin_hash():
    if os.path.exists(ADMIN_CONFIG_FILE):
        try:
            with open(ADMIN_CONFIG_FILE, "r") as f:
                return json.load(f).get("hash")
        except: return None
    return None

def salvar_admin_hash(password):
    with open(ADMIN_CONFIG_FILE, "w") as f:
        json.dump({"hash": hash_password(password)}, f)

def carregar_usuarios():
    if os.path.exists(USUARIOS_FILE):
        try:
            with open(USUARIOS_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def salvar_usuarios(usuarios):
    with open(USUARIOS_FILE, "w") as f: json.dump(usuarios, f, indent=4)

def obter_nomes_arquivos():
    usuario = st.session_state.get("usuario_logado", "padrao")
    return f"servicos_{usuario}.json", f"fluxo_caixa_{usuario}.csv"

def carregar_servicos():
    servicos_file, _ = obter_nomes_arquivos()
    if os.path.exists(servicos_file):
        try:
            with open(servicos_file, "r") as f: return json.load(f)
        except: pass
    return {"Corte de Cabelo": 25.00, "Barba": 25.00, "Combo Cabelo e Barba": 50.00}

def salvar_servicos(servicos):
    servicos_file, _ = obter_nomes_arquivos()
    with open(servicos_file, "w") as f: json.dump(servicos, f, indent=4)

def carregar_fluxo():
    _, fluxo_file = obter_nomes_arquivos()
    if os.path.exists(fluxo_file):
        try:
            df = pd.read_csv(fluxo_file)
            df['Data'] = pd.to_datetime(df['Data'])
            return df
        except: return pd.DataFrame(columns=["Data", "Tipo", "Descrição", "Valor"])
    return pd.DataFrame(columns=["Data", "Tipo", "Descrição", "Valor"])

def salvar_fluxo(df):
    _, fluxo_file = obter_nomes_arquivos()
    df.to_csv(fluxo_file, index=False)

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Financeira - Salão", layout="wide", page_icon="✂️")

st.markdown("""
<style>
    body, .stApp { background-color: #121212; color: white; }
    .sim-header { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #333; margin-bottom: 20px; }
    .sim-header-title { color: #d4af37; font-weight: bold; font-size: 1.2rem; }
    .fast-actions-header { display: flex; align-items: center; margin-bottom: 15px; }
    .fast-actions-title { color: white; font-weight: bold; font-size: 1rem; margin-right: 10px; }
    .fast-actions-line { flex-grow: 1; height: 2px; background-color: #d4af37; }
    .is-action-card { display: none; }
    div[data-testid="stColumn"]:has(.is-action-card) button {
        background-color: #22252a !important; color: white !important; border: 1px solid #333 !important;
        border-radius: 8px !important; padding: 18px 15px !important; min-height: 75px !important;
        width: 100% !important; display: flex !important; align-items: center !important;
        justify-content: flex-start !important; gap: 10px !important; transition: all 0.2s ease-in-out !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.15) !important; cursor: pointer !important;
    }
    div[data-testid="stColumn"]:has(.is-action-card) button:hover { background-color: #2a2e35 !important; border-color: #d4af37 !important; transform: translateY(-2px) !important; box-shadow: 0 6px 12px rgba(212, 175, 55, 0.1) !important; }
    .embedded-form-container { margin-top: 15px; background-color: #1a1d21; padding: 15px; border-radius: 8px; border: 1px solid #d4af37; }
    .confirmacao-dourada { background-color: #1e1e1e; border: 2px solid #d4af37; padding: 12px 15px; border-radius: 6px; color: #fff; font-weight: 500; margin-bottom: 15px; display: flex; align-items: center; gap: 10px; }
</style>
""", unsafe_allow_html=True)

# --- INICIALIZAÇÃO DE ESTADOS ---
if 'formulario_ativo' not in st.session_state: st.session_state.formulario_ativo = 'none'
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'usuario_logado' not in st.session_state: st.session_state.usuario_logado = None
if 'eh_admin' not in st.session_state: st.session_state.eh_admin = False

# --- FLUXO DE LOGIN ---
admin_hash = carregar_admin_hash()
usuarios_cadastrados = carregar_usuarios()

if not st.session_state.autenticado:
    if not admin_hash:
        st.title("⚠️ Configuração Inicial")
        st.write("Defina a senha do Administrador:")
        with st.form("primeiro_acesso"):
            nova_adm_pass = st.text_input("Definir senha de ADMIN:", type="password")
            if st.form_submit_button("Criar Acesso"):
                salvar_admin_hash(nova_adm_pass)
                st.success("Administrador criado! Reiniciando...")
                st.rerun()
        st.stop()

    st.title("✂️ Sistema de Gestão - Login")
    with st.form("form_login"):
        usuario_input = st.text_input("Usuário:").strip().lower()
        senha_input = st.text_input("Senha:", type="password")
        if st.form_submit_button("Entrar"):
            if usuario_input == "admin" and hash_password(senha_input) == admin_hash:
                st.session_state.update({'autenticado': True, 'usuario_logado': "Administrador", 'eh_admin': True})
                st.rerun()
            elif usuario_input in usuarios_cadastrados and usuarios_cadastrados[usuario_input]["senha"] == hash_password(senha_input):
                dados = usuarios_cadastrados[usuario_input]
                if datetime.now(TZ).date() > datetime.strptime(dados["vencimento"], "%Y-%m-%d").date() or dados.get("status") == "Suspenso":
                    st.error("❌ Acesso Bloqueado: Licença vencida.")
                    st.stop()
                st.session_state.update({'autenticado': True, 'usuario_logado': usuario_input, 'eh_admin': False})
                st.rerun()
            else: st.error("Usuário ou senha incorretos.")
    st.stop()

# --- INTERFACE ADMINISTRADOR ---
if st.session_state.eh_admin:
    st.title("👑 Central do Administrador")
    tab_cad, tab_ger = st.tabs(["➕ Cadastrar/Renovar", "⚙️ Gerenciar Salões"])
    with tab_cad:
        with st.form("form_cadastro_cliente"):
            novo_usuario = st.text_input("Usuário do Salão:").strip().lower()
            nova_senha = st.text_input("Senha de Acesso:", type="password").strip()
            dias_validade = st.number_input("Dias de Validade:", min_value=1, value=30)
            if st.form_submit_button("Salvar Salão"):
                if novo_usuario and nova_senha:
                    usuarios_cadastrados[novo_usuario] = {"senha": hash_password(nova_senha), "vencimento": (datetime.now(TZ) + timedelta(days=dias_validade)).strftime("%Y-%m-%d"), "status": "Ativo"}
                    salvar_usuarios(usuarios_cadastrados); st.success("Salão configurado!"); st.rerun()
    with tab_ger:
        salao_sel = st.selectbox("Selecione o Salão:", list(usuarios_cadastrados.keys()))
        if st.button("Excluir Salão"):
            del usuarios_cadastrados[salao_sel]; salvar_usuarios(usuarios_cadastrados); st.rerun()
        if st.button("🚪 Sair do Modo ADM"): st.session_state.autenticado = False; st.rerun()
    st.stop()

# --- INTERFACE CLIENTE ---
df_fluxo_caixa = carregar_fluxo()
servicos = carregar_servicos()

hoje = pd.Timestamp(datetime.now(TZ).date())
df_fluxo_caixa['Data'] = pd.to_datetime(df_fluxo_caixa['Data'])
df_diario = df_fluxo_caixa[df_fluxo_caixa['Data'].dt.date == hoje.date()]
ent_dia = df_diario[df_diario['Tipo'] == 'Entrada']['Valor'].sum()
sai_dia = df_diario[df_diario['Tipo'] == 'Saída']['Valor'].sum()
lucro_dia = ent_dia + sai_dia

tab1, tab0, tab2 = st.tabs(["📊 Dashboard", "🚀 Início / Ações", "📜 Histórico"])

with tab1:
    st.subheader("📊 Resumo do Dia")
    st.metric("Líquido Diário", f"R$ {lucro_dia:.2f}")

with tab0:
    st.markdown('<div class="sim-header"><span class="sim-header-title">Fio&Caixa</span></div>', unsafe_allow_html=True)
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown('<div class="is-action-card"></div>', unsafe_allow_html=True)
        if st.button("✂️ Novo Atendimento"): st.session_state.formulario_ativo = 'atend'
        if st.session_state.formulario_ativo == 'atend':
            serv = st.selectbox("Serviço:", list(servicos.keys()))
            valor = st.number_input("Valor:", value=float(servicos[serv]))
            if st.button("Lançar"):
                nova_l = pd.DataFrame([{"Data": pd.to_datetime(datetime.now(TZ).date()), "Tipo": "Entrada", "Descrição": f"Atendimento: {serv}", "Valor": valor}])
                df_fluxo_caixa = pd.concat([df_fluxo_caixa, nova_l], ignore_index=True); salvar_fluxo(df_fluxo_caixa); st.rerun()
    with col_b:
        if st.button("🚪 Sair"): st.session_state.autenticado = False; st.rerun()

with tab2:
    st.subheader("📜 Histórico")
    df_vis = df_fluxo_caixa.sort_index(ascending=False).copy()
    st.dataframe(df_vis, use_container_width=True)

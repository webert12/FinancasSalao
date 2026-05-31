import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time
import hashlib
from supabase import create_client, Client

# --- CONFIGURAÇÃO SUPABASE ---
@st.cache_resource
def init_supabase():
    # Carrega credenciais do arquivo secrets.toml
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- CONFIGURAÇÃO DE SEGURANÇA E FUSO ---
SALT = "salao_fio_caixa_2026_security"
TZ = ZoneInfo("America/Sao_Paulo")
ADMIN_MESTRE_USER = "admin"
ADMIN_MESTRE_HASH = hashlib.sha256(("master2026" + SALT).encode()).hexdigest()

def hash_password(password):
    return hashlib.sha256((password + SALT).encode()).hexdigest()

# --- FUNÇÕES DE BANCO DE DADOS (SUPABASE) ---

def carregar_usuarios_db():
    """Carrega todos os usuários do Supabase e converte para o formato do app."""
    response = supabase.table("perfis_salao").select("*").execute()
    users_dict = {}
    for item in response.data:
        users_dict[item["username"]] = {
            "senha": item["password_hash"], 
            "tipo": item["tipo"], 
            "vencimento": item["expiry_date"], 
            "status": item["status"]
        }
    return users_dict

def carregar_servicos_db(username):
    response = supabase.table("servicos").select("*").eq("username", username).execute()
    if not response.data:
        return {"Corte de Cabelo": 25.00, "Barba": 25.00, "Combo Cabelo e Barba": 50.00}
    return {item["nome_servico"]: float(item["preco"]) for item in response.data}

def salvar_servicos_db(username, servicos_dict):
    # Limpa serviços antigos do usuário
    supabase.table("servicos").delete().eq("username", username).execute()
    # Insere novos
    rows = [{"username": username, "nome_servico": k, "preco": v} for k, v in servicos_dict.items()]
    supabase.table("servicos").insert(rows).execute()

def carregar_fluxo_db(username):
    response = supabase.table("fluxo_caixa").select("*").eq("username", username).execute()
    if not response.data:
        return pd.DataFrame(columns=["Data", "Tipo", "Descrição", "Valor"])
    df = pd.DataFrame(response.data)
    # Ajuste dos nomes das colunas para bater com o front-end
    df = df.rename(columns={"data_transacao": "Data", "tipo": "Tipo", "descricao": "Descrição", "valor": "Valor"})
    df['Data'] = pd.to_datetime(df['Data'])
    return df

def salvar_fluxo_db(username, df):
    # Para simplicidade, vamos deletar e inserir tudo ou apenas inserir o último
    # Aqui vamos focar na funcionalidade de inserir novos registros
    pass # No seu app, você já está chamando a inserção direta.

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Financeira - Salão", layout="wide", page_icon="✂️")

# Estilização CSS mantida
st.markdown("""<style>
    body, .stApp { background-color: #121212; color: white; }
    .sim-header { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #333; margin-bottom: 20px; }
    .sim-header-title { color: #d4af37; font-weight: bold; font-size: 1.2rem; }
    .is-action-card { display: none; }
    div[data-testid="stColumn"]:has(.is-action-card) button { background-color: #22252a !important; color: white !important; border: 1px solid #333 !important; border-radius: 8px !important; padding: 18px 15px !important; min-height: 75px !important; width: 100% !important; display: flex !important; align-items: center !important; justify-content: flex-start !important; gap: 10px !important; }
    .embedded-form-container { margin-top: 15px; background-color: #1a1d21; padding: 15px; border-radius: 8px; border: 1px solid #d4af37; }
    .confirmacao-dourada { background-color: #1e1e1e; border: 2px solid #d4af37; padding: 12px 15px; border-radius: 6px; color: #fff; font-weight: 500; margin-bottom: 15px; }
</style>""", unsafe_allow_html=True)

# --- INICIALIZAÇÃO DE ESTADOS ---
if 'formulario_ativo' not in st.session_state: st.session_state.formulario_ativo = 'none'
if 'autenticado' not in st.session_state: st.session_state.autenticado = False

# --- CONTROLE DE LOGIN ---
if not st.session_state.autenticado:
    st.title("✂️ Sistema de Gestão - Login")
    with st.form("form_login"):
        usuario_input = st.text_input("Usuário:").strip().lower()
        senha_input = st.text_input("Senha:", type="password")
        if st.form_submit_button("Entrar"):
            # Lógica ADMIN
            if usuario_input == ADMIN_MESTRE_USER and hash_password(senha_input) == ADMIN_MESTRE_HASH:
                st.session_state.update({'autenticado': True, 'usuario_logado': "Administrador", 'eh_admin': True})
                st.rerun()
            # Lógica CLIENTE (Supabase)
            else:
                users = carregar_usuarios_db()
                if usuario_input in users and users[usuario_input]["senha"] == hash_password(senha_input):
                    dados = users[usuario_input]
                    if datetime.now(TZ).date() > datetime.strptime(dados["vencimento"], "%Y-%m-%d").date() or dados["status"] == "Suspenso":
                        st.error("❌ Acesso Bloqueado: Licença vencida.")
                    else:
                        st.session_state.update({'autenticado': True, 'usuario_logado': usuario_input, 'eh_admin': False})
                        st.session_state.servicos = carregar_servicos_db(usuario_input)
                        st.session_state.fluxo_caixa = carregar_fluxo_db(usuario_input)
                        st.rerun()
                else: st.error("Usuário ou senha inválidos.")
    st.stop()

# --- INTERFACE ADMIN ---
if st.session_state.eh_admin:
    st.title("👑 Central do Administrador")
    # ... (Mantenha seu código de Admin aqui, apenas substitua as chamadas de 'salvar_usuarios' pela inserção no Supabase)
    if st.button("Sair"): st.session_state.autenticado = False; st.rerun()
    st.stop()

# --- INTERFACE CLIENTE (Fluxo Principal) ---
# (Aqui você mantém o layout, apenas garantindo que quando salvar, use as funções _db)
# Exemplo de salvamento de fluxo:
# supabase.table("fluxo_caixa").insert({"username": st.session_state.usuario_logado, ...}).execute()

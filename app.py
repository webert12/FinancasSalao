import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import hashlib
from supabase import create_client, Client

# --- CONFIGURAÇÃO SUPABASE ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- CONFIGURAÇÕES ---
SALT = "salao_fio_caixa_2026_security"
TZ = ZoneInfo("America/Sao_Paulo")

def hash_password(password):
    return hashlib.sha256((password + SALT).encode()).hexdigest()

# --- FUNÇÕES DE BANCO DE DADOS (Substituindo JSON/CSV) ---

def carregar_usuarios():
    # Retorna dicionário formatado como o sistema espera
    response = supabase.table("perfis_salao").select("*").execute()
    usuarios = {}
    for item in response.data:
        usuarios[item["username"]] = {
            "senha": item["password_hash"],
            "tipo": item.get("tipo", "Cliente"),
            "vencimento": item["expiry_date"],
            "status": item["status"]
        }
    return usuarios

def carregar_servicos():
    username = st.session_state.usuario_logado
    response = supabase.table("servicos").select("*").eq("username", username).execute()
    if not response.data:
        return {"Corte de Cabelo": 25.00, "Barba": 25.00, "Combo Cabelo e Barba": 50.00}
    return {item["nome_servico"]: float(item["preco"]) for item in response.data}

def salvar_servicos(servicos):
    username = st.session_state.usuario_logado
    # Deleta antigos e insere novos (simplificado)
    supabase.table("servicos").delete().eq("username", username).execute()
    rows = [{"username": username, "nome_servico": k, "preco": v} for k, v in servicos.items()]
    supabase.table("servicos").insert(rows).execute()

def carregar_fluxo():
    username = st.session_state.usuario_logado
    response = supabase.table("fluxo_caixa").select("*").eq("username", username).execute()
    if not response.data:
        return pd.DataFrame(columns=["Data", "Tipo", "Descrição", "Valor"])
    
    df = pd.DataFrame(response.data)
    df = df.rename(columns={"data_transacao": "Data", "tipo": "Tipo", "descricao": "Descrição", "valor": "Valor"})
    df['Data'] = pd.to_datetime(df['Data'])
    return df

def salvar_fluxo(df):
    # Nota: Em produção, o ideal é salvar linha a linha. 
    # Aqui, para manter compatibilidade, inserimos o último registro ou atualizamos.
    # O seu código original adicionava uma linha por vez. Vamos garantir isso:
    ultima_linha = df.iloc[-1]
    supabase.table("fluxo_caixa").insert({
        "username": st.session_state.usuario_logado,
        "data_transacao": ultima_linha['Data'].isoformat(),
        "tipo": ultima_linha['Tipo'],
        "descricao": ultima_linha['Descrição'],
        "valor": float(ultima_linha['Valor'])
    }).execute()

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

# --- FLUXO DE LOGIN ---
if not st.session_state.autenticado:
    st.title("✂️ Sistema de Gestão - Login")
    with st.form("form_login"):
        usuario_input = st.text_input("Usuário:").strip().lower()
        senha_input = st.text_input("Senha:", type="password")
        if st.form_submit_button("Entrar"):
            # Lógica ADMIN
            if usuario_input == "admin":
                # Verificação simplificada de admin (você pode colocar no banco se quiser)
                if hash_password(senha_input) == hash_password("master2026"): 
                    st.session_state.update({'autenticado': True, 'usuario_logado': "Administrador", 'eh_admin': True})
                    st.rerun()
            
            # Lógica CLIENTE (Banco de Dados)
            usuarios_cadastrados = carregar_usuarios()
            if usuario_input in usuarios_cadastrados and usuarios_cadastrados[usuario_input]["senha"] == hash_password(senha_input):
                dados = usuarios_cadastrados[usuario_input]
                if datetime.now(TZ).date() > datetime.strptime(dados["vencimento"], "%Y-%m-%d").date() or dados.get("status") == "Suspenso":
                    st.error("❌ Acesso Bloqueado: Licença vencida.")
                else:
                    st.session_state.update({'autenticado': True, 'usuario_logado': usuario_input, 'eh_admin': False})
                    st.rerun()
            else: st.error("Usuário ou senha incorretos.")
    st.stop()

# --- INTERFACE ADMINISTRADOR ---
if st.session_state.get('eh_admin', False):
    st.title("👑 Central do Administrador")
    tab_cad, tab_ger = st.tabs(["➕ Cadastrar/Renovar", "⚙️ Gerenciar Salões"])
    with tab_cad:
        with st.form("form_cadastro_cliente"):
            novo_usuario = st.text_input("Usuário do Salão:").strip().lower()
            nova_senha = st.text_input("Senha de Acesso:", type="password").strip()
            dias_validade = st.number_input("Dias de Validade:", min_value=1, value=30)
            if st.form_submit_button("Salvar Salão"):
                # Insere no Supabase
                supabase.table("perfis_salao").insert({
                    "username": novo_usuario,
                    "password_hash": hash_password(nova_senha),
                    "expiry_date": (datetime.now(TZ) + timedelta(days=dias_validade)).strftime("%Y-%m-%d"),
                    "status": "Ativo"
                }).execute()
                st.success("Salão configurado!"); st.rerun()
    with tab_ger:
        if st.button("🚪 Sair do Modo ADM"): st.session_state.autenticado = False; st.rerun()
    st.stop()

# --- INTERFACE CLIENTE ---
df_fluxo_caixa = carregar_fluxo()
servicos = carregar_servicos()

# Lógica de Dash
if not df_fluxo_caixa.empty:
    hoje = pd.Timestamp(datetime.now(TZ).date())
    df_diario = df_fluxo_caixa[df_fluxo_caixa['Data'].dt.date == hoje.date()]
    lucro_dia = df_diario['Valor'].sum()
else:
    lucro_dia = 0

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
                df_fluxo_caixa = pd.concat([df_fluxo_caixa, nova_l], ignore_index=True)
                salvar_fluxo(df_fluxo_caixa); st.rerun()
    with col_b:
        if st.button("🚪 Sair"): st.session_state.autenticado = False; st.rerun()

with tab2:
    st.subheader("📜 Histórico")
    st.dataframe(df_fluxo_caixa.sort_index(ascending=False), use_container_width=True)

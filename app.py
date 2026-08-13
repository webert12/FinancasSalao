import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import json
import hashlib
import hmac
from io import BytesIO
import urllib.parse
import re
import decimal
import base64
import requests
import streamlit.components.v1 as components

# --- Bibliotecas de Conexão Direta SQL ---
from sqlalchemy import create_engine, text

# --- Relatórios e Segurança ---
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- CONFIGURAÇÃO DE SEGURANÇA E HORÁRIO ---
SALT = st.secrets.get("SECURITY_SALT", "salao_fio_caixa_secure_default_2026")
TZ = ZoneInfo("America/Sao_Paulo")

# URL OFICIAL NO RENDER
RENDER_BASE_URL = "https://agendamentos-doy4.onrender.com/"

def gerar_hash(password: str) -> str:
    """Gera o hash da senha compatível com o padrão do projeto."""
    if not password:
        return ""
    salt_bytes = str(SALT).encode('utf-8')
    senha_bytes = str(password).encode('utf-8')
    return hmac.new(salt_bytes, senha_bytes, hashlib.sha256).hexdigest()

def hash_password(password):
    return gerar_hash(password)

def verificar_senha(senha_digitada, senha_no_banco):
    if not senha_no_banco or not senha_digitada:
        return False
    if hmac.compare_digest(str(senha_digitada), str(senha_no_banco)):
        return True
    hash_calc = gerar_hash(senha_digitada)
    return hmac.compare_digest(hash_calc, str(senha_no_banco))

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Fio&Caixa - Gestão & Agendamento", layout="wide", page_icon="✂️")

# --- PERSISTÊNCIA DE SESSÃO VIA URL ---
query_params = st.query_params

# ESTADOS DE SESSÃO INICIAIS
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'usuario_logado' not in st.session_state: st.session_state.usuario_logado = None
if 'eh_admin' not in st.session_state: st.session_state.eh_admin = False
if 'recuperando_senha' not in st.session_state: st.session_state.recuperando_senha = False
if 'tema_escuro' not in st.session_state: st.session_state.tema_escuro = True
if 'meta_mensal' not in st.session_state: st.session_state.meta_mensal = 5000.00

# Recupera sessão persistida pela URL se houver
if not st.session_state.autenticado and "token_sessao" in query_params:
    token_val = query_params["token_sessao"]
    if token_val == "admin_master_session":
        st.session_state.autenticado = True
        st.session_state.usuario_logado = "Administrador"
        st.session_state.eh_admin = True
    elif token_val:
        st.session_state.autenticado = True
        st.session_state.usuario_logado = str(token_val).strip().lower()
        st.session_state.eh_admin = False

# --- OTIMIZAÇÃO DE VELOCIDADE: CACHE DA IMAGEM DE FUNDO ---
@st.cache_data
def get_image_base64(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    return ""

# --- DESIGN & CSS ULTRA PREMIUM ---
def set_background_com_logo(image_path):
    encoded_string = get_image_base64(image_path)

    if st.session_state.tema_escuro:
        bg_style = f'background-image: radial-gradient(circle at 50% 0%, rgba(14, 23, 42, 0.95) 0%, rgba(6, 9, 15, 0.98) 100%), url("data:image/png;base64,{encoded_string}") !important;'
        app_bg = "#06090f"
        input_bg = "rgba(10, 15, 26, 0.85)"
    else:
        bg_style = 'background: radial-gradient(circle at 50% 0%, #1e293b 0%, #0f172a 60%, #020617 100%) !important;'
        app_bg = "#0f172a"
        input_bg = "rgba(10, 15, 26, 0.85)"

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');
        @import url('https://fonts.googleapis.com/icon?family=Material+Icons');

        /* REMOÇÃO DEFINITIVA DO BOTÃO STOP E DO BONECO DE CARREGAMENTO */
        [data-testid="stStatusWidget"], div[data-testid="stStatusWidget"] {{
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }}

        .stApp {{
            {bg_style}
            background-color: {app_bg} !important;
            background-size: cover !important;
            background-position: center !important;
            background-attachment: fixed !important;
            color: #f8fafc !important;
            font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif !important;
        }}

        html, body, p, label, div {{
            color: #f8fafc;
            font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
        }}

        span[data-testid="stIconMaterial"], 
        [data-testid="stIconMaterial"],
        i.material-icons {{
            font-family: 'Material Symbols Outlined', 'Material Icons' !important;
            font-weight: normal !important;
            font-style: normal !important;
            font-size: 1.25rem !important;
            line-height: 1 !important;
            display: inline-block !important;
            text-transform: none !important;
            letter-spacing: normal !important;
            word-wrap: normal !important;
            white-space: nowrap !important;
            direction: ltr !important;
            -webkit-font-smoothing: antialiased !important;
        }}

        h1, h2, h3, h4, h5, h6 {{
            color: #ffffff !important;
            font-weight: 700 !important;
            letter-spacing: -0.5px !important;
        }}

        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-track {{ background: rgba(6, 9, 15, 0.5); }}
        ::-webkit-scrollbar-thumb {{ background: rgba(255, 255, 255, 0.15); border-radius: 999px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: #38bdf8; }}

        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        input, select, textarea,
        [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input,
        [data-testid="stDateInput"] input {{
            background-color: {input_bg} !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 14px !important;
            padding: 12px 16px !important;
            font-size: 0.95rem !important;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
            backdrop-filter: blur(10px) !important;
        }}

        input:focus, div[data-baseweb="input"] > div:focus-within, div[data-baseweb="select"] > div:focus-within {{
            border-color: #38bdf8 !important;
            box-shadow: 0 0 16px rgba(56, 189, 248, 0.25) !important;
            background-color: {input_bg} !important;
        }}

        div[data-testid="stForm"] {{
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 20px !important;
            padding: 24px !important;
            background: rgba(13, 19, 31, 0.6) !important;
            backdrop-filter: blur(12px) !important;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3) !important;
        }}

        div[data-testid="stPopoverBody"] {{
            background-color: rgba(13, 19, 31, 0.98) !important;
            border: 1px solid rgba(56, 189, 248, 0.3) !important;
            border-radius: 20px !important;
            box-shadow: 0 20px 50px rgba(0,0,0,0.8) !important;
            backdrop-filter: blur(16px) !important;
            z-index: 999999 !important;
            padding: 18px !important;
        }}
        div[data-testid="stPopoverBody"] * {{ color: #ffffff !important; }}

        div[data-testid="stPopover"] button,
        [data-testid="stPopoverButton"] button {{
            background: rgba(17, 24, 39, 0.85) !important;
            border: 1px solid rgba(56, 189, 248, 0.4) !important;
            border-radius: 14px !important;
            padding: 10px 16px !important;
            color: #ffffff !important;
            font-weight: 700 !important;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2) !important;
            transition: all 0.25s ease !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: space-between !important;
            gap: 8px !important;
            width: auto !important;
            min-height: 44px !important;
        }}

        ul[data-baseweb="menu"],
        li[role="option"],
        div[data-testid="stSelectboxVirtualDropdown"] {{
            background-color: #0d131f !important;
            color: #ffffff !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            border-radius: 14px !important;
        }}
        li[role="option"]:hover, [data-baseweb="menu"] li:hover {{
            background-color: rgba(56, 189, 248, 0.15) !important;
            color: #38bdf8 !important;
        }}

        .kpi-card-v2 {{ 
            background: linear-gradient(145deg, rgba(15, 23, 42, 0.8) 0%, rgba(10, 15, 26, 0.9) 100%); 
            border: 1px solid rgba(255, 255, 255, 0.07); 
            border-radius: 20px; 
            padding: 22px; 
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5); 
            backdrop-filter: blur(12px);
            height: 100%; 
            display: flex; 
            flex-direction: column; 
            justify-content: space-between; 
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            position: relative;
            overflow: hidden;
        }}
        .kpi-title-v2 {{ font-size: 0.88rem; color: #94a3b8 !important; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; letter-spacing: 0.2px; }}
        .kpi-value-v2 {{ font-size: 1.85rem; font-weight: 800; margin-bottom: 8px; letter-spacing: -0.8px; }}
        .kpi-val-green {{ color: #10b981 !important; }}
        .kpi-val-red {{ color: #f43f5e !important; }}
        .kpi-val-blue {{ color: #38bdf8 !important; }}
        .kpi-val-purple {{ color: #a855f7 !important; }}
        .kpi-val-orange {{ color: #f59e0b !important; }}
        .kpi-perc {{ font-size: 0.82rem; font-weight: 700; display: flex; align-items: center; gap: 4px; }}
        .perc-up {{ color: #10b981 !important; }}
        .perc-down {{ color: #f43f5e !important; }}
        .perc-neutral {{ color: #94a3b8 !important; }}

        .ui-card {{ 
            background: linear-gradient(145deg, rgba(15, 23, 42, 0.75) 0%, rgba(10, 15, 26, 0.85) 100%); 
            border: 1px solid rgba(255, 255, 255, 0.07); 
            border-radius: 22px; 
            padding: 26px; 
            margin-bottom: 20px; 
            box-shadow: 0 12px 30px -5px rgba(0, 0, 0, 0.5); 
            backdrop-filter: blur(12px);
            transition: all 0.3s ease;
        }}

        .login-card {{ 
            background: linear-gradient(180deg, rgba(15, 23, 42, 0.85) 0%, rgba(8, 12, 20, 0.95) 100%); 
            border: 1px solid rgba(56, 189, 248, 0.25); 
            border-radius: 28px; 
            padding: 48px 38px; 
            box-shadow: 0 30px 70px -15px rgba(0, 0, 0, 0.9), 0 0 35px rgba(56, 189, 248, 0.12); 
            max-width: 480px; 
            margin: 0 auto; 
            backdrop-filter: blur(20px);
        }}
        .login-brand-wrapper {{ text-align: center; margin-bottom: 28px; }}
        .login-badge-icon {{
            display: inline-flex; align-items: center; justify-content: center;
            width: 70px; height: 70px;
            background: linear-gradient(135deg, #0284c7 0%, #38bdf8 100%);
            border-radius: 22px; font-size: 32px; margin-bottom: 18px;
            box-shadow: 0 12px 28px rgba(56, 189, 248, 0.4);
        }}
        .login-title {{ 
            color: #ffffff !important; font-size: 2.4rem !important; font-weight: 800 !important; 
            letter-spacing: -1.2px !important; margin-bottom: 8px !important; line-height: 1.1; text-align: center; 
            background: linear-gradient(90deg, #ffffff 0%, #38bdf8 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }}
        .login-subtitle {{ color: #94a3b8 !important; font-size: 0.95rem !important; text-align: center; margin-bottom: 30px; font-weight: 500; }}

        .stButton > button, [data-testid="stDownloadButton"] > button {{
            background: rgba(255, 255, 255, 0.05) !important;
            color: #ffffff !important;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
            border-radius: 14px !important;
            font-weight: 700 !important;
            padding: 10px 14px !important;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
            width: 100% !important;
            min-height: 46px !important;
            height: auto !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 8px !important;
            font-size: 0.92rem !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2) !important;
        }}

        .stButton > button[kind="primary"] {{ 
            background: linear-gradient(135deg, #0284c7 0%, #38bdf8 100%) !important; 
            color: #ffffff !important; border: none !important; 
            box-shadow: 0 6px 20px rgba(56, 189, 248, 0.35) !important; 
        }}

        .stTabs [data-baseweb="tab-list"] {{ 
            gap: 12px; background: rgba(15, 23, 42, 0.6); padding: 8px; border-radius: 18px;
            border: 1px solid rgba(255, 255, 255, 0.06); backdrop-filter: blur(12px);
            display: flex; justify-content: center; margin-bottom: 24px;
        }}
        .stTabs [data-baseweb="tab"] {{ 
            background-color: transparent !important; border-radius: 12px !important; border: none !important; 
            padding: 12px 24px !important; color: #94a3b8 !important; font-size: 0.98rem; font-weight: 600;
        }}
        .stTabs [aria-selected="true"] {{ 
            background: linear-gradient(135deg, rgba(56, 189, 248, 0.15) 0%, rgba(2, 132, 199, 0.25) 100%) !important; 
            color: #38bdf8 !important; font-weight: 700; border: 1px solid rgba(56, 189, 248, 0.3) !important; 
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

set_background_com_logo("logo.png")

st.markdown("""
    <style>
        footer, [data-testid="stFooter"], .stFooter, #MainMenu, [data-testid="stToolbar"], [data-testid="stDecoration"], .stDeployButton { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        .main .block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; }
    </style>
""", unsafe_allow_html=True)

# --- CONEXÃO BANCO DE DADOS ---
if "DB_URL" in st.secrets:
    DB_URL = st.secrets["DB_URL"]
else:
    st.error("❌ ERRO CRÍTICO: Variável 'DB_URL' não encontrada nos Secrets.")
    st.stop()

@st.cache_resource
def init_connection(url):
    return create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20, pool_recycle=1800)

try:
    engine = init_connection(DB_URL)
except Exception as e:
    st.error(f"Erro de conexão com o banco de dados: {e}")
    st.stop()

# --- INICIALIZAÇÃO DO BANCO ---
@st.cache_resource
def inicializar_banco():
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS admin_config (id INT PRIMARY KEY, hash1 TEXT NOT NULL, hash2 TEXT NOT NULL, url_sistema TEXT);"))
        conn.execute(text("ALTER TABLE admin_config ADD COLUMN IF NOT EXISTS url_sistema TEXT;"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS usuarios (id TEXT PRIMARY KEY, senha TEXT NOT NULL, email TEXT, tipo TEXT, vencimento TEXT, status TEXT, whatsapp TEXT);"))
        conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS whatsapp TEXT;"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS servicos (id SERIAL PRIMARY KEY, usuario_id TEXT NOT NULL, nome TEXT NOT NULL, preco NUMERIC NOT NULL);"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS fluxo_caixa (id SERIAL PRIMARY KEY, usuario_id TEXT NOT NULL, data TEXT NOT NULL, tipo TEXT NOT NULL, descricao TEXT NOT NULL, valor NUMERIC NOT NULL);"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS agendamentos (id SERIAL PRIMARY KEY, usuario_id TEXT NOT NULL, cliente_nome TEXT NOT NULL, cliente_contato TEXT, servico_nome TEXT NOT NULL, data TEXT NOT NULL, hora TEXT NOT NULL);"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS clientes_mensais (
                id SERIAL PRIMARY KEY,
                usuario_id TEXT NOT NULL,
                nome_cliente TEXT NOT NULL,
                telefone TEXT,
                servicos_feitos INT DEFAULT 0,
                valor_devido NUMERIC DEFAULT 0.0,
                status_divida TEXT DEFAULT 'Pendente'
            );
        """))
    return True

try:
    inicializar_banco()
except Exception as e:
    st.error(f"Erro na criação de tabelas: {e}")
    st.stop()

# --- FUNÇÕES DE PERSISTÊNCIA & CACHE ---
def limpar_cache_sessao():
    if "dados_carregados_sessao" in st.session_state:
        del st.session_state["dados_carregados_sessao"]

@st.cache_data(ttl=600)
def carregar_admin_hashes():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT hash1, hash2, url_sistema FROM admin_config WHERE id = 1")).fetchone()
            if result: return result[0], result[1], result[2]
    except Exception: pass
    return None, None, None

def salvar_admin_hashes(password1, password2, url=""):
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
            conn.execute(text("""
                INSERT INTO admin_config (id, hash1, hash2, url_sistema) VALUES (1, :h1, :h2, :url)
                ON CONFLICT (id) DO UPDATE SET hash1 = EXCLUDED.hash1, hash2 = EXCLUDED.hash2, url_sistema = EXCLUDED.url_sistema
            """), {"h1": password1, "h2": password2, "url": url})
        carregar_admin_hashes.clear()
    except Exception as e: st.error(f"Erro: {e}")

def atualizar_url_sistema(url):
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
            conn.execute(text("UPDATE admin_config SET url_sistema = :url WHERE id = 1"), {"url": url})
        carregar_admin_hashes.clear()
    except Exception: pass

@st.cache_data(ttl=300)
def carregar_usuarios():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, senha, email, tipo, vencimento, status, whatsapp FROM usuarios"))
            rows = result.fetchall()
            if rows: 
                return {
                    str(row[0]).strip().lower(): {
                        "id": str(row[0]).strip().lower(), 
                        "senha": row[1], 
                        "email": row[2], 
                        "tipo": row[3], 
                        "vencimento": row[4], 
                        "status": row[5],
                        "whatsapp": row[6] if len(row) > 6 and row[6] is not None else ""
                    } for row in rows
                }
    except Exception: pass
    return {}

def salvar_usuarios(usuarios_dict):
    if not usuarios_dict: return
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        for k, v in usuarios_dict.items():
            user_clean = str(k).strip().lower()
            venc_val = v["vencimento"]
            if hasattr(venc_val, 'strftime'):
                venc_str = venc_val.strftime('%Y-%m-%d')
            else:
                venc_str = str(venc_val) if venc_val else datetime.now(TZ).strftime('%Y-%m-%d')

            senha_val = str(v["senha"])
            if not senha_val.startswith("pbkdf2_sha256$") and len(senha_val) < 60:
                senha_val = gerar_hash(senha_val)

            conn.execute(text("""
                INSERT INTO usuarios (id, senha, email, tipo, vencimento, status, whatsapp) 
                VALUES (:id, :senha, :email, :tipo, :vencimento, :status, :whatsapp)
                ON CONFLICT (id) DO UPDATE SET 
                    senha = EXCLUDED.senha, 
                    email = EXCLUDED.email, 
                    tipo = EXCLUDED.tipo, 
                    vencimento = EXCLUDED.vencimento, 
                    status = EXCLUDED.status,
                    whatsapp = EXCLUDED.whatsapp
            """), {
                "id": user_clean, 
                "senha": senha_val, 
                "email": v.get("email", ""), 
                "tipo": v["tipo"], 
                "vencimento": venc_str, 
                "status": v["status"],
                "whatsapp": v.get("whatsapp", "")
            })
    carregar_usuarios.clear()

@st.cache_data(ttl=300)
def carregar_servicos_por_salao(salao_id):
    salao_id_clean = urllib.parse.unquote(str(salao_id)).strip().lower() if salao_id else "padrao"
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT nome, preco FROM servicos WHERE usuario_id = :user ORDER BY nome ASC"), {"user": salao_id_clean})
            rows = result.fetchall()
            if rows: return {row[0]: float(row[1]) for row in rows}
    except Exception: pass
    return {"Corte de Cabelo": 30.00, "Barba": 30.00, "Combo Cabelo e Barba": 50.00, "Mensalidade": 100.00}

def carregar_servicos(usuario_logado=None):
    usuario = usuario_logado or st.session_state.get("usuario_logado", "padrao")
    return carregar_servicos_por_salao(usuario)

def salvar_ou_atualizar_servico(nome_antigo, nome_novo, preco):
    usuario = str(st.session_state.get("usuario_logado", "padrao")).strip().lower()
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        if nome_antigo and nome_antigo != "➕ Cadastrar Novo Serviço":
            conn.execute(text("UPDATE servicos SET nome = :novo, preco = :preco WHERE usuario_id = :user AND nome = :antigo"), {"novo": nome_novo, "preco": float(preco), "user": usuario, "antigo": nome_antigo})
        else:
            conn.execute(text("INSERT INTO servicos (usuario_id, nome, preco) VALUES (:user, :nome, :preco)"), {"user": usuario, "nome": nome_novo, "preco": float(preco)})
    carregar_servicos_por_salao.clear()
    limpar_cache_sessao()

def deletar_servico_banco(nome):
    usuario = str(st.session_state.get("usuario_logado", "padrao")).strip().lower()
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        conn.execute(text("DELETE FROM servicos WHERE usuario_id = :user AND nome = :nome"), {"user": usuario, "nome": nome})
    carregar_servicos_por_salao.clear()
    limpar_cache_sessao()

@st.cache_data(ttl=180)
def carregar_fluxo_por_usuario(usuario):
    usuario_clean = str(usuario).strip().lower()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, data, tipo, descricao, valor FROM fluxo_caixa WHERE usuario_id = :user ORDER BY id DESC"), {"user": usuario_clean})
            rows = result.fetchall()
            if rows:
                df = pd.DataFrame(rows, columns=['id', 'Data', 'Tipo', 'Descrição', 'Valor'])
                df['Data'] = pd.to_datetime(df['Data'])
                return df
    except Exception: pass
    return pd.DataFrame(columns=["id", "Data", "Tipo", "Descrição", "Valor"])

def carregar_fluxo(usuario_logado=None):
    usuario = usuario_logado or st.session_state.get("usuario_logado", "padrao")
    return carregar_fluxo_por_usuario(usuario)

def inserir_movimentacao_direta(tipo, descricao, valor, data_input):
    usuario = str(st.session_state.get("usuario_logado", "padrao")).strip().lower()
    data_str = data_input.strftime('%Y-%m-%d') if hasattr(data_input, 'strftime') else str(data_input)
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        conn.execute(text("INSERT INTO fluxo_caixa (usuario_id, data, tipo, descricao, valor) VALUES (:user, :data, :tipo, :descricao, :valor)"), {"user": usuario, "data": data_str, "tipo": tipo, "descricao": descricao, "valor": float(valor)})
    carregar_fluxo_por_usuario.clear()
    limpar_cache_sessao()

def dar_baixa_fiado_direta(id_registro, nova_descricao):
    usuario = str(st.session_state.get("usuario_logado", "padrao")).strip().lower()
    data_hoje = datetime.now(TZ).strftime('%Y-%m-%d')
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        conn.execute(text("UPDATE fluxo_caixa SET tipo = 'Entrada', data = :data, descricao = :desc WHERE id = :id AND usuario_id = :user"), {"data": data_hoje, "desc": nova_descricao, "id": int(id_registro), "user": usuario})
    carregar_fluxo_por_usuario.clear()
    limpar_cache_sessao()

def deletar_movimentacao_fluxo(id_registro):
    usuario = str(st.session_state.get("usuario_logado", "padrao")).strip().lower()
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        conn.execute(text("DELETE FROM fluxo_caixa WHERE id = :id AND usuario_id = :user"), {"id": int(id_registro), "user": usuario})
    carregar_fluxo_por_usuario.clear()
    limpar_cache_sessao()

@st.cache_data(ttl=120)
def carregar_agendamentos_por_usuario_direto(usuario):
    usuario_clean = str(usuario).strip().lower()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, cliente_nome, cliente_contato, servico_nome, data, hora FROM agendamentos WHERE usuario_id = :user ORDER BY data ASC, hora ASC"), {"user": usuario_clean})
            rows = result.fetchall()
            if rows: return pd.DataFrame(rows, columns=["id", "Cliente", "Contato/WhatsApp", "Serviço", "Data", "Horário"])
    except Exception: pass
    return pd.DataFrame(columns=["id", "Cliente", "Contato/WhatsApp", "Serviço", "Data", "Horário"])

def carregar_agendamentos(usuario_logado=None):
    usuario = usuario_logado or st.session_state.get("usuario_logado", "padrao")
    return carregar_agendamentos_por_usuario_direto(usuario)

def deletar_agendamento(id_agendamento):
    usuario = str(st.session_state.get("usuario_logado", "padrao")).strip().lower()
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        conn.execute(text("DELETE FROM agendamentos WHERE id = :id AND usuario_id = :user"), {"id": int(id_agendamento), "user": usuario})
    carregar_agendamentos_por_usuario_direto.clear()
    limpar_cache_sessao()

def enviar_alerta_servidor_whatsapp(numero_barbeiro, texto_mensagem):
    wa_api_url = st.secrets.get("WA_API_URL", "")
    wa_api_token = st.secrets.get("WA_API_TOKEN", "")
    
    if wa_api_url and wa_api_token and numero_barbeiro:
        try:
            num_limpo = re.sub(r'\D', '', str(numero_barbeiro))
            if not num_limpo.startswith('55') and len(num_limpo) <= 11:
                num_limpo = '55' + num_limpo
                
            payload = { "number": num_limpo, "message": texto_mensagem }
            headers = { "Content-Type": "application/json", "apikey": wa_api_token }
            requests.post(wa_api_url, json=payload, headers=headers, timeout=5)
        except Exception:
            pass

@st.cache_data(ttl=180)
def carregar_clientes_mensais_banco(usuario_logado=None):
    usuario = usuario_logado or st.session_state.get("usuario_logado", "padrao")
    usuario_clean = str(usuario).strip().lower()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, nome_cliente, telefone, servicos_feitos, valor_devido, status_divida FROM clientes_mensais WHERE usuario_id = :user ORDER BY id DESC"), {"user": usuario_clean})
            rows = result.fetchall()
            if rows:
                return pd.DataFrame(rows, columns=["id", "Cliente", "Telefone", "Serviços Feitos", "Valor Devido", "Status"])
    except Exception: pass
    return pd.DataFrame(columns=["id", "Cliente", "Telefone", "Serviços Feitos", "Valor Devido", "Status"])

def cadastrar_cliente_mensal_banco(nome, telefone):
    usuario = str(st.session_state.get("usuario_logado", "padrao")).strip().lower()
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        conn.execute(text("""
            INSERT INTO clientes_mensais (usuario_id, nome_cliente, telefone, servicos_feitos, valor_devido, status_divida)
            VALUES (:user, :nome, :tel, 0, 0.0, 'Pendente')
        """), {"user": usuario, "nome": nome.strip(), "tel": telefone.strip()})
    carregar_clientes_mensais_banco.clear()
    limpar_cache_sessao()

def atualizar_cortes_cliente_mensal(id_cliente, qtd_adicionar, valor_por_servico):
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        res = conn.execute(text("SELECT servicos_feitos, valor_devido FROM clientes_mensais WHERE id = :id"), {"id": int(id_cliente)}).fetchone()
        if res:
            novos_servicos = int(res[0]) + int(qtd_adicionar)
            novo_valor = float(res[1]) + (float(qtd_adicionar) * float(valor_por_servico))
            conn.execute(text("""
                UPDATE clientes_mensais 
                SET servicos_feitos = :s, valor_devido = :v, status_divida = 'Pendente'
                WHERE id = :id
            """), {"s": novos_servicos, "v": novo_valor, "id": int(id_cliente)})
    carregar_clientes_mensais_banco.clear()
    limpar_cache_sessao()

def dar_baixa_divida_mensalista(id_cliente, valor_baixa):
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        res = conn.execute(text("SELECT valor_devido FROM clientes_mensais WHERE id = :id"), {"id": int(id_cliente)}).fetchone()
        if res:
            devido_atual = float(res[0])
            novo_valor_devido = max(0.0, devido_atual - float(valor_baixa))
            novo_status = 'Quitado' if novo_valor_devido == 0 else 'Pendente'
            conn.execute(text("""
                UPDATE clientes_mensais 
                SET valor_devido = :v, status_divida = :st
                WHERE id = :id
            """), {"v": novo_valor_devido, "st": novo_status, "id": int(id_cliente)})
    carregar_clientes_mensais_banco.clear()
    limpar_cache_sessao()

def gerar_backup_json_completo(usuario_logado=None):
    usuario = usuario_logado or st.session_state.get("usuario_logado", "padrao")
    df_f = carregar_fluxo(usuario)
    fluxo_dict = []
    if not df_f.empty:
        df_copy = df_f.copy()
        if 'Data' in df_copy.columns: df_copy['Data'] = df_copy['Data'].dt.strftime('%Y-%m-%d')
        fluxo_dict = df_copy.to_dict(orient="records")
    def custom_serializer(obj):
        if isinstance(obj, (decimal.Decimal, float)): return float(obj)
        if isinstance(obj, (datetime, pd.Timestamp)): return obj.strftime('%Y-%m-%d')
        return str(obj)
    dados_backup = {"sistema": "Fio&Caixa", "usuario_dono": usuario, "data_geracao": datetime.now(TZ).strftime('%d/%m/%Y %H:%M:%S'), "catalogo_servicos": carregar_servicos(usuario), "historico_financeiro": fluxo_dict}
    return json.dumps(dados_backup, indent=4, ensure_ascii=False, default=custom_serializer)

def gerar_pdf_contabilidade(df, mes_ref):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor("#38bdf8"), spaceAfter=15)
    story.append(Paragraph(f"Fio&Caixa - Relatório Contábil ({mes_ref})", title_style))
    table_data = [["Data", "Tipo", "Descrição", "Valor"]]
    for _, row in df.iterrows():
        dt_str = row['Data'].strftime('%d/%m/%Y') if hasattr(row['Data'], 'strftime') else str(row['Data'])
        table_data.append([dt_str, str(row['Tipo']), str(row['Descrição']), f"R$ {row['Valor']:.2f}"])
    t = Table(table_data, colWidths=[75, 60, 265, 80])
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0d131f")), ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#38bdf8")), ('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('FONTSIZE', (0,0), (-1,-1), 9)]))
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def renderizar_botao_download_apk(dados_bytes, nome_arquivo, mime_type, label_botao):
    st.download_button(
        label=label_botao,
        data=dados_bytes,
        file_name=nome_arquivo,
        mime=mime_type,
        use_container_width=True
    )

def renderizar_whatsapp_flutuante():
    wa_msg = urllib.parse.quote("Olá, preciso de suporte ou tenho dúvidas sobre o sistema Fio&Caixa.")
    support_phone = st.secrets.get("SUPPORT_PHONE", "5537991598179")
    st.markdown(f"""
        <style>
        .floating-wa {{ position: fixed; width: 55px; height: 55px; bottom: 30px; right: 30px; background: linear-gradient(135deg, #10b981 0%, #059669 100%); border-radius: 50px; text-align: center; box-shadow: 0px 8px 25px rgba(16,185,129,0.4); z-index: 9999999; display: flex; align-items: center; justify-content: center; text-decoration: none; transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); }}
        .floating-wa:hover {{ transform: scale(1.1) translateY(-3px); box-shadow: 0px 12px 30px rgba(16,185,129,0.6); }}
        .floating-wa svg {{ width: 30px; height: 30px; fill: white; }}
        </style>
        <a href="https://api.whatsapp.com/send?phone={support_phone}&text={wa_msg}" class="floating-wa" target="_blank" title="Falar com Suporte">
            <svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg"><path d="M16 2a13 13 0 0 0-10.85 20.24L3.6 28.5l6.43-1.5A13 13 0 1 0 16 2zm0 24a10.9 10.9 0 0 1-5.54-1.5l-.4-.24-4.14 1 .97-4.04-.26-.4A11 11 0 1 1 16 26zm6-8.2c-.33-.16-1.95-.96-2.25-1.07-.3-.1-.52-.16-.74.17-.22.33-.85 1.07-1.04 1.28-.2.22-.39.25-.72.09-.33-.16-1.4-.52-2.65-1.64-1-1-1.68-2.22-1.88-2.55-.2-.33-.02-.51.15-.67.15-.15.33-.39.5-.59.16-.2.22-.33.32-.55.1-.22.05-.42-.03-.58-.08-.16-.74-1.78-1-2.43-.27-.64-.53-.55-.74-.56h-.63c-.22 0-.58.08-.88.42-.3.33-1.15 1.12-1.15 2.73s1.18 3.16 1.34 3.37c.16.22 2.3 3.51 5.56 4.92 2.22.95 3.02 1.02 4.1 1.02s1.95-.8 2.25-1.57c.3-.77.3-1.43.22-1.57-.1-.13-.33-.2-.66-.36z"/></svg>
        </a>
    """, unsafe_allow_html=True)

# ==============================================================================
# ROTA PÚBLICA DE AGENDAMENTO CLIENTE (?salao=nome)
# ==============================================================================
salao_url = query_params.get("salao", None)

if salao_url:
    st.markdown('<style>[data-testid="stSidebar"] {display: none !important;} [data-testid="collapsedControl"] {display: none !important;}</style>', unsafe_allow_html=True)
    salao_id_clean = urllib.parse.unquote(str(salao_url)).strip().lower()
    nome_salao_formatado = salao_id_clean.replace('_', ' ').replace('-', ' ').title()
    HORARIOS_DISPONIVEIS = ["08:00", "09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00"]
    servicos_salao = carregar_servicos_por_salao(salao_id_clean)

    todos_usuarios = carregar_usuarios()
    dados_dono = todos_usuarios.get(salao_id_clean, {})
    wa_dono = dados_dono.get("whatsapp", "")

    st.markdown(f'<div style="text-align: center; margin-bottom: 25px;"><h1 style="margin: 0; color: #ffffff; font-size: 2.2rem;">✂️ {nome_salao_formatado}</h1><p style="color: #38bdf8 !important; font-weight: 600; margin-top: 6px; font-size: 0.95rem;">Agendamento Online Rápido e Simples</p></div>', unsafe_allow_html=True)

    if st.session_state.get("agendamento_sucesso"):
        dados_ag = st.session_state.agendamento_sucesso
        st.success(f"🎉 Agendado com sucesso para {dados_ag['nome']} às {dados_ag['hora']} dia {dados_ag['data_formatada']}!")
        st.balloons()

        wa_dono_clean = re.sub(r'\D', '', str(dados_ag.get("wa_dono", "")))
        if wa_dono_clean:
            if not wa_dono_clean.startswith('55') and len(wa_dono_clean) <= 11:
                wa_dono_clean = '55' + wa_dono_clean
            
            msg_wa = urllib.parse.quote(
                f"🚨 *NOVO AGENDAMENTO RECEBIDO!*\n\n"
                f"👤 *Cliente:* {dados_ag['nome']}\n"
                f"📱 *Contato:* {dados_ag['contato']}\n"
                f"✂️ *Serviço:* {dados_ag['servico']}\n"
                f"📅 *Data:* {dados_ag['data_formatada']}\n"
                f"⏰ *Horário:* {dados_ag['hora']}"
            )
            link_wa_dono = f"https://api.whatsapp.com/send?phone={wa_dono_clean}&text={msg_wa}"
            
            components.html(f'''
                <script>
                    setTimeout(function() {{
                        window.top.location.href = "{link_wa_dono}";
                    }}, 800);
                </script>
            ''', height=0, width=0)

            st.markdown(f'''
                <a href="{link_wa_dono}" target="_top" style="display:flex; align-items:center; justify-content:center; gap:10px; width:100%; text-align:center; background: linear-gradient(135deg, #10b981 0%, #059669 100%); color:#ffffff; padding:1.1rem; border-radius:16px; text-decoration:none; font-weight:800; font-size:1.05rem; margin-top:18px; margin-bottom:18px; box-shadow: 0 8px 25px rgba(16, 185, 129, 0.4); transition: all 0.3s ease;">
                    <svg viewBox="0 0 32 32" width="24" height="24" fill="white" xmlns="http://www.w3.org/2000/svg"><path d="M16 2a13 13 0 0 0-10.85 20.24L3.6 28.5l6.43-1.5A13 13 0 1 0 16 2zm0 24a10.9 10.9 0 0 1-5.54-1.5l-.4-.24-4.14 1 .97-4.04-.26-.4A11 11 0 1 1 16 26zm6-8.2c-.33-.16-1.95-.96-2.25-1.07-.3-.1-.52-.16-.74.17-.22.33-.85 1.07-1.04 1.28-.2.22-.39.25-.72.09-.33-.16-1.4-.52-2.65-1.64-1-1-1.68-2.22-1.88-2.55-.2-.33-.02-.51.15-.67.15-.15.33-.39.5-.59.16-.2.22-.33.32-.55.1-.22.05-.42-.03-.58-.08-.16-.74-1.78-1-2.43-.27-.64-.53-.55-.74-.56h-.63c-.22 0-.58.08-.88.42-.3.33-1.15 1.12-1.15 2.73s1.18 3.16 1.34 3.37c.16.22 2.3 3.51 5.56 4.92 2.22.95 3.02 1.02 4.1 1.02s1.95-.8 2.25-1.57c.3-.77.3-1.43.22-1.57-.1-.13-.33-.2-.66-.36z"/></svg>
                    Clique aqui se não abrir o WhatsApp automaticamente
                </a>
            ''', unsafe_allow_html=True)

        if st.button("Fazer Outro Agendamento", use_container_width=True):
            del st.session_state.agendamento_sucesso
            st.rerun()
        st.stop()

    with st.form("form_agendamento_cliente", clear_on_submit=True):
        nome_cliente = st.text_input("Seu Nome Completo:")
        telefone_cliente = st.text_input("Seu WhatsApp (com DDD):")
        servico_escolhido = st.selectbox("Escolha o Serviço:", list(servicos_salao.keys())) if servicos_salao else None
        data_escolhida = st.date_input("Escolha a Data:", min_value=datetime.now(TZ).date())
        data_str = data_escolhida.strftime("%Y-%m-%d")
        data_formatada = data_escolhida.strftime("%d/%m/%Y")
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT hora FROM agendamentos WHERE usuario_id = :user AND data = :dt"), {"user": salao_id_clean, "dt": data_str})
                ocupados = [r[0] for r in result.fetchall()]
        except Exception: ocupados = []
        horarios_livres = [h for h in HORARIOS_DISPONIVEIS if h not in ocupados]
        horario_escolhido = st.selectbox("Horário Disponível:", horarios_livres) if horarios_livres else None
        if not horarios_livres: st.warning("⚠️ Todos os horários estão preenchidos nesta data.")
        enviar_agendamento = st.form_submit_button("Confirmar Agendamento 🚀", type="primary", use_container_width=True)

    if enviar_agendamento:
        try:
            if not nome_cliente or not telefone_cliente:
                st.warning("⚠️ Por favor, informe seu nome e telefone.")
            elif not horario_escolhido or not servico_escolhido:
                st.error("⚠️ Selecione um horário válido.")
            else:
                with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                    conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
                    conn.execute(text("INSERT INTO agendamentos (usuario_id, cliente_nome, cliente_contato, servico_nome, data, hora) VALUES (:user, :nome, :contato, :servico, :data, :hora)"), {"user": salao_id_clean, "nome": nome_cliente.strip(), "contato": telefone_cliente.strip(), "servico": servico_escolhido, "data": data_str, "hora": horario_escolhido})
                
                if wa_dono:
                    texto_alerta_api = f"🚨 NOVO AGENDAMENTO RECEBIDO!\n\nCliente: {nome_cliente.strip()}\nContato: {telefone_cliente.strip()}\nServiço: {servico_escolhido}\nData: {data_formatada}\nHorário: {horario_escolhido}"
                    enviar_alerta_servidor_whatsapp(wa_dono, texto_alerta_api)

                st.session_state.agendamento_sucesso = {
                    "nome": nome_cliente.strip(),
                    "contato": telefone_cliente.strip(),
                    "servico": servico_escolhido,
                    "hora": horario_escolhido,
                    "data_formatada": data_formatada,
                    "wa_dono": wa_dono
                }
                limpar_cache_sessao()
                st.rerun()
        except Exception as e: st.error(f"Erro ao registrar agendamento: {e}")
    st.stop()

# ==============================================================================
# TELA DE AUTENTICAÇÃO E LOGIN
# ==============================================================================
if not st.session_state.autenticado:
    admin_hash1, admin_hash2, url_sistema_salva = carregar_admin_hashes()
    usuarios_cadastrados = carregar_usuarios()

    if not admin_hash1 or not admin_hash2:
        st.title("⚠️ Configuração Inicial de Segurança")
        with st.form("primeiro_acesso"):
            nova_adm_pass1 = st.text_input("Senha Principal Admin:", type="password")
            nova_adm_pass2 = st.text_input("Senha Secundária Admin:", type="password")
            url_padrao_app = st.text_input("URL Base do App:", value=RENDER_BASE_URL)
            if st.form_submit_button("Salvar Inicialização"):
                if nova_adm_pass1 and nova_adm_pass2:
                    salvar_admin_hashes(nova_adm_pass1, nova_adm_pass2, url_padrao_app.strip())
                    st.success("Administração inicializada!")
                    st.rerun()
        st.stop()

    if st.session_state.recuperando_senha:
        st.markdown('<br><br>', unsafe_allow_html=True)
        _, col_rec_centro, _ = st.columns([1, 2, 1])
        with col_rec_centro:
            st.markdown('<div class="login-card"><div class="login-brand-wrapper"><div class="login-badge-icon">🔐</div><h1 class="login-title">Recuperação</h1><p class="login-subtitle">Redefina a senha da sua conta</p></div>', unsafe_allow_html=True)
            with st.form("form_recuperacao"):
                user_recup = st.text_input("Usuário:").strip().lower()
                email_recup = st.text_input("E-mail Cadastrado:").strip().lower()
                nova_senha_recup = st.text_input("Nova Senha:", type="password")
                conf_senha_recup = st.text_input("Confirme a Nova Senha:", type="password")
                if st.form_submit_button("Atualizar Senha", type="primary", use_container_width=True):
                    if user_recup in usuarios_cadastrados and usuarios_cadastrados[user_recup].get("email") == email_recup:
                        if nova_senha_recup == conf_senha_recup and nova_senha_recup:
                            usuarios_cadastrados[user_recup]["senha"] = hash_password(nova_senha_recup)
                            salvar_usuarios(usuarios_cadastrados)
                            st.success("✅ Senha alterada com sucesso!")
                            st.session_state.recuperando_senha = False
                            st.rerun()
                        else: st.error("As senhas não conferem.")
                    else: st.error("Usuário ou e-mail incorretos.")
            if st.button("Voltar ao Login", use_container_width=True):
                st.session_state.recuperando_senha = False
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        st.stop()

    col_vazia, col_btn_tema = st.columns([8, 1])
    with col_btn_tema:
        if st.button("🌑 Escuro" if not st.session_state.tema_escuro else "☀️ Claro", use_container_width=True):
            st.session_state.tema_escuro = not st.session_state.tema_escuro
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    _, col_login_centro, _ = st.columns([1, 2, 1])

    with col_login_centro:
        st.markdown('''
            <div class="login-card">
                <div class="login-brand-wrapper">
                    <div class="login-badge-icon">✂️</div>
                    <h1 class="login-title">Fio & Caixa</h1>
                    <p class="login-subtitle">Plataforma Profissional de Gestão & Agendamentos</p>
                </div>
        ''', unsafe_allow_html=True)
        
        tipo_acesso = st.radio("Acesso como:", ["Salão", "Admin"], horizontal=True, label_visibility="collapsed")

        with st.form("form_login_moderno"):
            usuario_input = st.text_input("Usuário / Login").strip().lower()
            senha_input = st.text_input("Senha", type="password")
            senha2_input = st.text_input("Senha Secundária Admin", type="password") if tipo_acesso == "Admin" else ""
            st.markdown("<br>", unsafe_allow_html=True)
            submit_login = st.form_submit_button("Acessar Sistema", type="primary", use_container_width=True)
            if submit_login:
                if tipo_acesso == "Admin":
                    if usuario_input == "admin" and verificar_senha(senha_input, admin_hash1) and verificar_senha(senha2_input, admin_hash2):
                        st.session_state.autenticado = True
                        st.session_state.usuario_logado = "Administrador"
                        st.session_state.eh_admin = True
                        st.query_params["token_sessao"] = "admin_master_session"
                        st.rerun()
                    else: st.error("Credenciais inválidas.")
                else:
                    if usuario_input in usuarios_cadastrados and verificar_senha(senha_input, usuarios_cadastrados[usuario_input]["senha"]):
                        dados_user = usuarios_cadastrados[usuario_input]
                        try:
                            data_venc = datetime.strptime(str(dados_user["vencimento"]), "%Y-%m-%d").date()
                        except Exception:
                            data_venc = datetime.now(TZ).date() + timedelta(days=30)

                        if datetime.now(TZ).date() > data_venc or dados_user.get("status") == "Suspenso":
                            st.error("❌ Acesso bloqueado. Licença expirada.")
                            st.stop()
                        st.session_state.autenticado = True
                        st.session_state.usuario_logado = usuario_input
                        st.session_state.eh_admin = False
                        st.query_params["token_sessao"] = usuario_input
                        st.rerun()
                    else: st.error("Usuário ou senha incorretos.")

        st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 20px 0;'>", unsafe_allow_html=True)

        support_phone = st.secrets.get("SUPPORT_PHONE", "5537991598179")
        col_esqueci, col_whats = st.columns(2)
        with col_esqueci:
            if st.button("Esqueci minha senha", use_container_width=True):
                st.session_state.recuperando_senha = True
                st.rerun()
        with col_whats:
            wa_login_msg = urllib.parse.quote("Olá! Gostaria de falar sobre o sistema Fio&Caixa.")
            st.markdown(f'<a href="https://api.whatsapp.com/send?phone={support_phone}&text={wa_login_msg}" target="_blank" style="display: flex; align-items: center; justify-content: center; gap: 8px; background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 10px; border-radius: 12px; text-decoration: none; font-weight: bold; height: 46px; box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);"><svg viewBox="0 0 32 32" width="20" height="20" fill="white" xmlns="http://www.w3.org/2000/svg"><path d="M16 2a13 13 0 0 0-10.85 20.24L3.6 28.5l6.43-1.5A13 13 0 1 0 16 2zm0 24a10.9 10.9 0 0 1-5.54-1.5l-.4-.24-4.14 1 .97-4.04-.26-.4A11 11 0 1 1 16 26zm6-8.2c-.33-.16-1.95-.96-2.25-1.07-.3-.1-.52-.16-.74.17-.22.33-.85 1.07-1.04 1.28-.2.22-.39.25-.72.09-.33-.16-1.4-.52-2.65-1.64-1-1-1.68-2.22-1.88-2.55-.2-.33-.02-.51.15-.67.15-.15.33-.39.5-.59.16-.2.22-.33.32-.55.1-.22.05-.42-.03-.58-.08-.16-.74-1.78-1-2.43-.27-.64-.53-.55-.74-.56h-.63c-.22 0-.58.08-.88.42-.3.33-1.15 1.12-1.15 2.73s1.18 3.16 1.34 3.37c.16.22 2.3 3.51 5.56 4.92 2.22.95 3.02 1.02 4.1 1.02s1.95-.8 2.25-1.57c.3-.77.3-1.43.22-1.57-.1-.13-.33-.2-.66-.36z"/></svg>Suporte</a>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

renderizar_whatsapp_flutuante()

# ==============================================================================
# MODO ADMINISTRADOR MESTRE
# ==============================================================================
if st.session_state.eh_admin:
    col_adm_title, col_adm_logout = st.columns([3, 1])
    with col_adm_title:
        st.title("👑 Gestão Geral de Salões (Admin)")
    with col_adm_logout:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚪 Sair do Sistema", type="secondary", use_container_width=True, key="admin_top_logout_btn"):
            st.session_state.clear()
            if "token_sessao" in st.query_params:
                del st.query_params["token_sessao"]
            st.rerun()

    tab_cad, tab_ger, tab_assinantes, tab_config = st.tabs(["➕ Cadastrar / Renovar", "⚙️ Salões Cadastrados", "📊 Painel de Assinantes", "🔧 Configurações Mestre"])
    admin_hash1, admin_hash2, url_sistema_salva = carregar_admin_hashes()
    usuarios_cadastrados = carregar_usuarios()

    with tab_cad:
        with st.form("form_cadastro_cliente"):
            novo_usuario = st.text_input("Usuário do Salão (sem espaços):").strip().lower()
            novo_email = st.text_input("E-mail de Contato:").strip().lower()
            novo_whatsapp = st.text_input("WhatsApp do Salão (com DDD, ex: 5537999999999):").strip()
            nova_senha = st.text_input("Senha de Acesso:", type="password").strip()
            tipo_conta = st.selectbox("Perfil:", ["Teste", "Cliente"])
            dias_validade = st.number_input("Dias de Acesso:", min_value=1, value=30)
            if st.form_submit_button("Cadastrar Salão", type="primary"):
                if novo_usuario and nova_senha and novo_email:
                    venc = (datetime.now(TZ) + timedelta(days=dias_validade)).strftime("%Y-%m-%d")
                    usuarios_cadastrados[novo_usuario] = {
                        "senha": hash_password(nova_senha), 
                        "email": novo_email, 
                        "whatsapp": novo_whatsapp,
                        "tipo": tipo_conta, 
                        "vencimento": venc, 
                        "status": "Ativo"
                    }
                    salvar_usuarios(usuarios_cadastrados)
                    st.success("Salão cadastrado com sucesso!")
                    st.rerun()
    with tab_ger:
        if usuarios_cadastrados:
            salao_sel = st.selectbox("Selecione um Salão:", list(usuarios_cadastrados.keys()))
            dados = usuarios_cadastrados[salao_sel]
            with st.expander("📝 Editar Conta", expanded=True):
                e_email = st.text_input("E-mail:", value=dados.get("email", ""))
                e_whatsapp = st.text_input("WhatsApp (com DDD):", value=dados.get("whatsapp", ""))
                e_senha_nova = st.text_input("Alterar Senha (opcional):", type="password")
                e_tipo = st.selectbox("Tipo:", ["Teste", "Cliente"], index=0 if dados['tipo'] == "Teste" else 1)

                try:
                    data_venc_atual = datetime.strptime(str(dados['vencimento']), "%Y-%m-%d").date()
                except Exception:
                    data_venc_atual = datetime.now(TZ).date()

                e_venc = st.date_input("Vencimento:", data_venc_atual)
                e_status = st.selectbox("Status:", ["Ativo", "Suspenso"], index=0 if dados['status'] == "Ativo" else 1)
                if st.button("Salvar Modificações"):
                    senha_f = hash_password(e_senha_nova) if e_senha_nova else dados['senha']
                    venc_str_save = e_venc.strftime("%Y-%m-%d") if hasattr(e_venc, 'strftime') else str(e_venc)
                    usuarios_cadastrados[salao_sel] = {
                        "senha": senha_f, 
                        "email": e_email.strip().lower(), 
                        "whatsapp": e_whatsapp.strip(),
                        "tipo": e_tipo, 
                        "vencimento": venc_str_save, 
                        "status": e_status
                    }
                    salvar_usuarios(usuarios_cadastrados)
                    st.success("Conta atualizada!")
                    st.rerun()
            if st.checkbox(f"Confirmar exclusão de {salao_sel}"):
                if st.button("EXCLUIR PERMANENTEMENTE", type="primary"):
                    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
                        conn.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": salao_sel})
                    carregar_usuarios.clear()
                    st.rerun()

    with tab_assinantes:
        st.markdown("### 📊 Painel de Monitoramento de Assinantes")
        st.markdown("<p style='color: #94a3b8;'>Acompanhe o status das assinaturas, verifique quem está em dia ou vencido, e bloqueie ou desbloqueie acessos automaticamente ou manualmente.</p>", unsafe_allow_html=True)

        if usuarios_cadastrados:
            data_hoje = datetime.now(TZ).date()
            
            houve_alteracao_auto = False
            for u_id, u_info in usuarios_cadastrados.items():
                try:
                    dt_venc = datetime.strptime(str(u_info.get("vencimento")), "%Y-%m-%d").date()
                except Exception:
                    dt_venc = data_hoje
                
                if dt_venc < data_hoje and u_info.get("status") == "Ativo":
                    usuarios_cadastrados[u_id]["status"] = "Suspenso"
                    houve_alteracao_auto = True

            if houve_alteracao_auto:
                salvar_usuarios(usuarios_cadastrados)
                usuarios_cadastrados = carregar_usuarios()

            total_clientes = len(usuarios_cadastrados)
            ativos_count = sum(1 for u in usuarios_cadastrados.values() if u.get("status") == "Ativo" and datetime.strptime(str(u.get("vencimento")), "%Y-%m-%d").date() >= data_hoje)
            vencidos_count = sum(1 for u in usuarios_cadastrados.values() if datetime.strptime(str(u.get("vencimento")), "%Y-%m-%d").date() < data_hoje or u.get("status") == "Suspenso")
            
            kpi1, kpi2, kpi3 = st.columns(3)
            with kpi1:
                st.markdown(f'<div class="kpi-card-v2"><div class="kpi-title-v2">Total de Assinantes</div><div class="kpi-value-v2 kpi-val-blue">{total_clientes}</div></div>', unsafe_allow_html=True)
            with kpi2:
                st.markdown(f'<div class="kpi-card-v2"><div class="kpi-title-v2">Assinantes em Dia (Ativos)</div><div class="kpi-value-v2 kpi-val-green">{ativos_count}</div></div>', unsafe_allow_html=True)
            with kpi3:
                st.markdown(f'<div class="kpi-card-v2"><div class="kpi-title-v2">Assinantes Vencidos / Bloqueados</div><div class="kpi-value-v2 kpi-val-red">{vencidos_count}</div></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("#### Gerenciamento de Acessos Individuais")

            for u_id, u_info in usuarios_cadastrados.items():
                try:
                    dt_venc = datetime.strptime(str(u_info.get("vencimento")), "%Y-%m-%d").date()
                except Exception:
                    dt_venc = data_hoje

                status_atual = u_info.get("status", "Ativo")
                esta_vencido = dt_venc < data_hoje

                cor_status = "#10b981" if (status_atual == "Ativo" and not esta_vencido) else "#f43f5e"
                texto_status = "Em Dia (Ativo)" if (status_atual == "Ativo" and not esta_vencido) else "Vencido / Bloqueado"

                with st.container():
                    st.markdown('<div class="ui-card" style="padding: 16px 20px; margin-bottom: 12px;">', unsafe_allow_html=True)
                    c_info, c_venc, c_status_lbl, c_btn = st.columns([2.5, 1.5, 2, 2])
                    with c_info:
                        st.markdown(f"**👤 Salão:** `{u_id}`<br><span style='color: #94a3b8; font-size: 0.85rem;'>{u_info.get('email', 'Sem e-mail')}</span>", unsafe_allow_html=True)
                    with c_venc:
                        st.markdown(f"**Vencimento:**<br>{dt_venc.strftime('%d/%m/%Y')}", unsafe_allow_html=True)
                    with c_status_lbl:
                        st.markdown(f"**Status:**<br><span style='color: {cor_status}; font-weight: 700;'>● {texto_status}</span>", unsafe_allow_html=True)
                    with c_btn:
                        if status_atual == "Ativo" and not esta_vencido:
                            if st.button("🔒 Bloquear", key=f"bloquear_{u_id}", use_container_width=True):
                                usuarios_cadastrados[u_id]["status"] = "Suspenso"
                                salvar_usuarios(usuarios_cadastrados)
                                st.success(f"Acesso de {u_id} bloqueado!")
                                st.rerun()
                        else:
                            if st.button("🔓 Desbloquear", key=f"desbloquear_{u_id}", type="primary", use_container_width=True):
                                novo_venc_renovado = (data_hoje + timedelta(days=30)).strftime("%Y-%m-%d")
                                usuarios_cadastrados[u_id]["status"] = "Ativo"
                                usuarios_cadastrados[u_id]["vencimento"] = novo_venc_renovado
                                salvar_usuarios(usuarios_cadastrados)
                                st.success(f"Acesso de {u_id} desbloqueado e renovado!")
                                st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("Nenhum assinante cadastrado no momento.")

    with tab_config:
        nova_url_input = st.text_input("URL Principal do Sistema:", value=url_sistema_salva if url_sistema_salva else RENDER_BASE_URL)
        if st.button("Salvar URL Global"):
            atualizar_url_sistema(nova_url_input.strip())
            st.success("URL Salva!")
            st.rerun()
    with st.sidebar:
        st.markdown("---")
        if st.button("🚪 Sair do Mestre", use_container_width=True):
            st.session_state.clear()
            if "token_sessao" in st.query_params:
                del st.query_params["token_sessao"]
            st.rerun()
    st.stop()

# ==============================================================================
# PAINEL PRINCIPAL DO SALÃO (USUÁRIO LOGADO - COM OTIMIZAÇÃO DE MEMÓRIA)
# ==============================================================================
usuario_logado_atual = st.session_state.usuario_logado

if "dados_carregados_sessao" not in st.session_state:
    st.session_state["df_fluxo_caixa"] = carregar_fluxo(usuario_logado_atual)
    st.session_state["servicos"] = carregar_servicos(usuario_logado_atual)
    st.session_state["df_agendamentos_all"] = carregar_agendamentos(usuario_logado_atual)
    st.session_state["df_clientes_m"] = carregar_clientes_mensais_banco(usuario_logado_atual)
    st.session_state["dados_carregados_sessao"] = True

df_fluxo_caixa = st.session_state["df_fluxo_caixa"]
servicos = st.session_state["servicos"]
df_agendamentos_all = st.session_state["df_agendamentos_all"]
df_clientes_m = st.session_state["df_clientes_m"]

_, _, url_sistema_salva = carregar_admin_hashes()

hoje = pd.Timestamp(datetime.now(TZ).date())
mes_atual = hoje.month
ano_atual = hoje.year
mes_passado = mes_atual - 1 if mes_atual > 1 else 12
ano_passado = ano_atual if mes_atual > 1 else ano_atual - 1

if not df_fluxo_caixa.empty:
    df_limpo = df_fluxo_caixa.dropna(subset=['Data']).copy()
    df_mes_atual = df_limpo[(df_limpo['Data'].dt.month == mes_atual) & (df_limpo['Data'].dt.year == ano_atual)]
    df_mes_passado = df_limpo[(df_limpo['Data'].dt.month == mes_passado) & (df_limpo['Data'].dt.year == ano_passado)]
    df_ano_atual = df_limpo[df_limpo['Data'].dt.year == ano_atual]
else:
    df_limpo = pd.DataFrame(columns=['id', 'Data', 'Tipo', 'Descrição', 'Valor'])
    df_mes_atual = pd.DataFrame(columns=['id', 'Data', 'Tipo', 'Descrição', 'Valor'])
    df_mes_passado = pd.DataFrame(columns=['id', 'Data', 'Tipo', 'Descrição', 'Valor'])
    df_ano_atual = pd.DataFrame(columns=['id', 'Data', 'Tipo', 'Descrição', 'Valor'])

base_url = RENDER_BASE_URL.rstrip('/')
link_clientes = f"{base_url}/?salao={st.session_state.usuario_logado}"
nome_salao_titulo = str(st.session_state.usuario_logado).replace('_', ' ').replace('-', ' ').title()
wa_url_geral = f"https://api.whatsapp.com/send?text={urllib.parse.quote(f'Olá! 👋 Agende seu horário no *{nome_salao_titulo}* de forma prática: {link_clientes}')}"

col_top_left, _ = st.columns([1, 4])
with col_top_left:
    with st.popover("⚙️ Configurações", use_container_width=False):
        st.subheader("⚙️ Configurar Salão")
        st.markdown("---")
        opcoes_gerenciamento_pop = ["➕ Cadastrar Novo Serviço"] + list(servicos.keys())
        servico_sel_pop = st.selectbox("Ação / Serviço:", opcoes_gerenciamento_pop, key="top_select_servico")
        nome_p_pop = "" if servico_sel_pop == "➕ Cadastrar Novo Serviço" else servico_sel_pop
        preco_p_pop = 0.0 if servico_sel_pop == "➕ Cadastrar Novo Serviço" else float(servicos[servico_sel_pop])
        novo_servico_pop = st.text_input("Nome do Serviço:", value=nome_p_pop, key=f"top_nome_{servico_sel_pop}")
        novo_preco_pop = st.number_input("Valor do Serviço (R$):", min_value=0.0, value=preco_p_pop, step=5.0, key=f"top_prc_{servico_sel_pop}")

        col_tp1, col_tp2 = st.columns(2)
        with col_tp1:
            if st.button("💾 Salvar", type="primary", use_container_width=True, key="top_save_btn"):
                if novo_servico_pop.strip():
                    salvar_ou_atualizar_servico(servico_sel_pop, novo_servico_pop.strip(), novo_preco_pop)
                    st.success("Serviço atualizado com sucesso!")
                    st.rerun()
                else: st.error("Informe o nome do serviço.")
        with col_tp2:
            if servico_sel_pop != "➕ Cadastrar Novo Serviço":
                if st.button("🗑️ Excluir", use_container_width=True, key="top_del_btn"):
                    deletar_servico_banco(servico_sel_pop)
                    st.warning("Serviço excluído com sucesso!")
                    st.rerun()

        st.markdown("---")
        renderizar_botao_download_apk(gerar_backup_json_completo(usuario_logado_atual).encode('utf-8'), f"backup_{st.session_state.usuario_logado}_{datetime.now(TZ).strftime('%d_%m_%Y')}.json", "application/json", "📥 Baixar Backup JSON")
        st.markdown("---")
        if st.button("🚪 Sair do Sistema", use_container_width=True, type="secondary", key="top_logout_btn"):
            st.session_state.clear()
            if "token_sessao" in st.query_params:
                del st.query_params["token_sessao"]
            st.rerun()

st.markdown(f'''
    <div style="display: flex; justify-content: space-between; align-items: center; padding: 18px 28px; background: linear-gradient(145deg, rgba(15, 23, 42, 0.7) 0%, rgba(10, 15, 26, 0.8) 100%); border: 1px solid rgba(255,255,255,0.06); border-radius: 22px; margin-bottom: 24px; backdrop-filter: blur(12px);">
        <div>
            <h2 style="margin: 0; color: #ffffff; font-size: 1.8rem; font-weight: 800;">✂️ {nome_salao_titulo}</h2>
            <p style="margin: 4px 0 0 0; color: #38bdf8 !important; font-size: 0.9rem; font-weight: 500;">Painel de Controle Financeiro & Agendamentos</p>
        </div>
    </div>
''', unsafe_allow_html=True)

# ==============================================================================
# FUNÇÕES DE DIÁLOGO (MODAIS PARA AÇÕES RÁPIDAS)
# ==============================================================================

@st.dialog("✂️ Registrar Novo Atendimento")
def dialog_novo_atendimento(servicos_dict):
    if list(servicos_dict.keys()):
        servico_selecionado = st.selectbox("Serviço Realizado:", list(servicos_dict.keys()), key="f_atend_serv_modal")
        preco_final = st.number_input("Valor Recebido (R$):", value=float(servicos_dict[servico_selecionado]), step=1.0, key=f"prc_atend_din_{servico_selecionado}_modal")
        data_entrada = st.date_input("Data do Atendimento:", datetime.now(TZ).date(), key="f_atend_dt_modal")
        if st.button("✅ Confirmar Entrada", type="primary", use_container_width=True):
            inserir_movimentacao_direta("Entrada", f"Atendimento: {servico_selecionado}", preco_final, data_entrada)
            st.success("Atendimento registrado no caixa!")
            st.rerun()

@st.dialog("🛍️ Registrar Nova Despesa")
def dialog_nova_despesa():
    descricao_saida = st.text_input("Descrição da Despesa:", key="f_venda_desc_modal", placeholder="Ex: Produto de limpeza, conta de luz...")
    valor_saida = st.number_input("Valor Pago (R$):", min_value=0.0, step=5.0, key="f_venda_val_modal")
    data_saida = st.date_input("Data do Pagamento:", datetime.now(TZ).date(), key="f_venda_dt_modal")
    if st.button("🔴 Lançar Saída", type="primary", use_container_width=True):
        if descricao_saida and valor_saida > 0:
            inserir_movimentacao_direta("Saída", descricao_saida, -valor_saida, data_saida)
            st.success("Despesa lançada!")
            st.rerun()
        else:
            st.warning("Preencha a descrição e um valor válido.")

@st.dialog("💰 Registrar Atendimento Fiado")
def dialog_anotar_fiado(servicos_dict):
    if list(servicos_dict.keys()):
        nome_devedor = st.text_input("Nome do Cliente Devedor:", key="f_fiado_nome_modal")
        servico_pendente = st.selectbox("Serviço Realizado:", list(servicos_dict.keys()), key="f_fiado_serv_modal")
        preco_final_p = st.number_input("Valor a Pagar (R$):", value=float(servicos_dict[servico_pendente]), key=f"prc_fiado_din_{servico_pendente}_modal")
        data_pendencia = st.date_input("Data do Serviço:", datetime.now(TZ).date(), key="f_fiado_dt_modal")
        if st.button("⚠️ Anotar Pendência", type="primary", use_container_width=True):
            if nome_devedor:
                inserir_movimentacao_direta("Pendência", f"Fiado de: {nome_devedor} ({servico_pendente})", preco_final_p, data_pendencia)
                st.success("Fiado registrado!")
                st.rerun()
            else:
                st.warning("Informe o nome do cliente devedor.")

@st.dialog("💸 Dar Baixa em Fiado")
def dialog_baixar_fiado(df_fluxo):
    df_pendencias = df_fluxo[df_fluxo['Tipo'] == 'Pendência']
    if not df_pendencias.empty:
        opcoes_pendentes = {f"{row['Descrição']} - R$ {abs(row['Valor']):.2f}": row['id'] for _, row in df_pendencias.iterrows()}
        pendencia_selecionada = st.selectbox("Selecione o Fiado a Baixar:", list(opcoes_pendentes.keys()), key="f_pago_sel_modal")
        if st.button("💰 Confirmar Recebimento", type="primary", use_container_width=True):
            id_alterar = opcoes_pendentes[pendencia_selecionada]
            row_atual = df_pendencias[df_pendencias['id'] == id_alterar].iloc[0]
            nova_desc = row_atual['Descrição'].replace("Fiado de:", "Recebido Fiado:") + " [PAGO]"
            dar_baixa_fiado_direta(id_alterar, nova_desc)
            st.success("Pagamento registrado no caixa!")
            st.rerun()
    else:
        st.info("Nenhum fiado pendente no momento.")

# ==============================================================================
# ABAS DO PAINEL PRINCIPAL
# ==============================================================================
tab_dashboard, tab_servicos, tab_mensais, tab_agend, tab_historico = st.tabs(["📊 Dashboard Premium", "🚀 Serviços", "👥 Clientes Mensais", "📅 Agendamentos", "💸 Fluxo de Caixa"])

# ==============================================================================
# TAB 1: DASHBOARD PREMIUM
# ==============================================================================
with tab_dashboard:
    def calc_perc(atual, anterior):
        if anterior == 0: return 0 if atual == 0 else 100
        return ((atual - anterior) / anterior) * 100

    def render_perc(val, reverse_colors=False):
        if val == 0: return f'<span class="kpi-perc perc-neutral">0% vs mês anterior</span>'
        seta = "▲" if val > 0 else "▼"
        cor = "perc-up" if (val > 0 and not reverse_colors) or (val < 0 and reverse_colors) else "perc-down"
        return f'<span class="kpi-perc {cor}">{seta} {abs(val):.1f}% vs mês ant.</span>'

    dt_hoje = hoje.date()
    dt_hoje_str = dt_hoje.strftime('%Y-%m-%d')

    rec_dia = df_limpo[(df_limpo['Data'].dt.date == dt_hoje) & (df_limpo['Tipo'].isin(['Entrada', 'Pendência']))]['Valor'].sum() if not df_limpo.empty else 0.0
    rec_mes = df_mes_atual[df_mes_atual['Tipo'].isin(['Entrada', 'Pendência'])]['Valor'].sum() if not df_mes_atual.empty else 0.0
    rec_ano = df_ano_atual[df_ano_atual['Tipo'].isin(['Entrada', 'Pendência'])]['Valor'].sum() if not df_ano_atual.empty else 0.0
    
    ent_mes = df_mes_atual[df_mes_atual['Tipo'] == 'Entrada']['Valor'].sum() if not df_mes_atual.empty else 0.0
    sai_mes = abs(df_mes_atual[df_mes_atual['Tipo'] == 'Saída']['Valor'].sum()) if not df_mes_atual.empty else 0.0
    lucro_mes = ent_mes - sai_mes

    rec_mes_passado = df_mes_passado[df_mes_passado['Tipo'].isin(['Entrada', 'Pendência'])]['Valor'].sum() if not df_mes_passado.empty else 0.0
    ent_mes_passado = df_mes_passado[df_mes_passado['Tipo'] == 'Entrada']['Valor'].sum() if not df_mes_passado.empty else 0.0
    sai_mes_passado = abs(df_mes_passado[df_mes_passado['Tipo'] == 'Saída']['Valor'].sum()) if not df_mes_passado.empty else 0.0
    lucro_mes_passado = ent_mes_passado - sai_mes_passado

    p_rec = calc_perc(rec_mes, rec_mes_passado)
    p_sai = calc_perc(sai_mes, sai_mes_passado)
    p_luc = calc_perc(lucro_mes, lucro_mes_passado)

    # BARRA DE AÇÕES RÁPIDAS COM MODAIS
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("✂️ Atendimento", use_container_width=True, type="primary"):
            dialog_novo_atendimento(servicos)
    with c2:
        if st.button("🛍️ Nova Despesa", use_container_width=True):
            dialog_nova_despesa()
    with c3:
        if st.button("💰 Anotar Fiado", use_container_width=True):
            dialog_anotar_fiado(servicos)
    with c4:
        if st.button("💸 Baixar Fiado", use_container_width=True):
            dialog_baixar_fiado(df_fluxo_caixa)

    st.markdown("<br>", unsafe_allow_html=True)

    # METRIC CARDS SUPERIORES
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f'''
            <div class="kpi-card-v2">
                <div>
                    <div class="kpi-title-v2">📅 Faturamento Hoje</div>
                    <div class="kpi-value-v2 kpi-val-blue">R$ {rec_dia:,.2f}</div>
                </div>
                <div style="font-size: 0.8rem; color: #94a3b8;">Data: {dt_hoje.strftime('%d/%m/%Y')}</div>
            </div>
        ''', unsafe_allow_html=True)
    with k2:
        st.markdown(f'''
            <div class="kpi-card-v2">
                <div>
                    <div class="kpi-title-v2">📈 Receita Mensal (Bruta)</div>
                    <div class="kpi-value-v2 kpi-val-green">R$ {rec_mes:,.2f}</div>
                </div>
                <div>{render_perc(p_rec)}</div>
            </div>
        ''', unsafe_allow_html=True)
    with k3:
        st.markdown(f'''
            <div class="kpi-card-v2">
                <div>
                    <div class="kpi-title-v2">📉 Saídas / Despesas</div>
                    <div class="kpi-value-v2 kpi-val-red">R$ {sai_mes:,.2f}</div>
                </div>
                <div>{render_perc(p_sai, reverse_colors=True)}</div>
            </div>
        ''', unsafe_allow_html=True)
    with k4:
        st.markdown(f'''
            <div class="kpi-card-v2">
                <div>
                    <div class="kpi-title-v2">💎 Lucro Líquido do Mês</div>
                    <div class="kpi-value-v2 kpi-val-purple">R$ {lucro_mes:,.2f}</div>
                </div>
                <div>{render_perc(p_luc)}</div>
            </div>
        ''', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # META MENSAL & BARRA DE PROGRESSO
    col_meta, col_link = st.columns([2, 1])
    with col_meta:
        st.markdown('<div class="ui-card">', unsafe_allow_html=True)
        st.subheader("🎯 Meta de Faturamento Mensal")
        meta_valor = st.number_input("Sua Meta para Este Mês (R$):", min_value=100.0, value=float(st.session_state.meta_mensal), step=500.0, key="inp_meta_dashboard")
        st.session_state.meta_mensal = meta_valor
        
        perc_meta = min(100.0, (rec_mes / meta_valor) * 100) if meta_valor > 0 else 0.0
        st.progress(perc_meta / 100.0)
        st.markdown(f"<p style='text-align: right; color: #38bdf8; font-weight: 700; margin-top: 5px;'>{perc_meta:.1f}% Atingido (R$ {rec_mes:,.2f} / R$ {meta_valor:,.2f})</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_link:
        st.markdown('<div class="ui-card" style="text-align: center;">', unsafe_allow_html=True)
        st.subheader("🔗 Link de Agendamentos")
        st.markdown("<p style='color: #94a3b8; font-size: 0.88rem;'>Compartilhe com seus clientes para receber agendamentos diretos.</p>", unsafe_allow_html=True)
        st.code(link_clientes, language=None)
        st.markdown(f'<a href="{wa_url_geral}" target="_blank" style="display: inline-flex; align-items: center; justify-content: center; gap: 8px; width: 100%; background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 12px; border-radius: 12px; font-weight: bold; text-decoration: none; box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);">📲 Divulgar no WhatsApp</a>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # GRÁFICOS ANALÍTICOS (PLOTLY)
    g1, g2 = st.columns(2)
    with g1:
        st.markdown('<div class="ui-card">', unsafe_allow_html=True)
        st.markdown("#### 📊 Desempenho Diário do Mês")
        if not df_mes_atual.empty:
            df_agrup_dia = df_mes_atual.groupby([df_mes_atual['Data'].dt.date, 'Tipo'])['Valor'].sum().unstack(fill_value=0).reset_index()
            fig_bar = px.bar(df_agrup_dia, x='Data', y=[c for c in ['Entrada', 'Saída', 'Pendência'] if c in df_agrup_dia.columns],
                             barmode='group',
                             color_discrete_map={'Entrada': '#10b981', 'Saída': '#f43f5e', 'Pendência': '#f59e0b'},
                             template='plotly_dark')
            fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=10, r=10, t=10, b=10), legend_title_text='')
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Nenhuma movimentação registrada neste mês.")
        st.markdown('</div>', unsafe_allow_html=True)

    with g2:
        st.markdown('<div class="ui-card">', unsafe_allow_html=True)
        st.markdown("#### 🍕 Distribuição do Faturamento por Serviço")
        if not df_mes_atual.empty:
            df_entradas = df_mes_atual[df_mes_atual['Tipo'] == 'Entrada'].copy()
            if not df_entradas.empty:
                df_entradas['Serviço_Clean'] = df_entradas['Descrição'].apply(lambda x: x.replace("Atendimento: ", "").replace("Recebido Fiado: ", "").split(" [")[0])
                df_serv_sum = df_entradas.groupby('Serviço_Clean')['Valor'].sum().reset_index()
                fig_pie = px.pie(df_serv_sum, values='Valor', names='Serviço_Clean', hole=0.5, template='plotly_dark',
                                 color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_pie.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Nenhuma entrada registrada para gerar gráfico de serviços.")
        else:
            st.info("Nenhuma movimentação registrada neste mês.")
        st.markdown('</div>', unsafe_allow_html=True)

# ==============================================================================
# TAB 2: CATÁLOGO DE SERVIÇOS
# ==============================================================================
with tab_servicos:
    st.markdown('<div class="ui-card">', unsafe_allow_html=True)
    st.subheader("🚀 Gerenciamento de Serviços e Preços")
    st.markdown("<p style='color: #94a3b8;'>Cadastre os serviços oferecidos no seu salão. Eles ficarão disponíveis automaticamente para seus clientes no link de agendamento e no seu caixa.</p>", unsafe_allow_html=True)

    if servicos:
        cols_serv = st.columns(3)
        idx = 0
        for nome_s, preco_s in servicos.items():
            with cols_serv[idx % 3]:
                st.markdown(f'''
                    <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 18px; margin-bottom: 15px;">
                        <h4 style="margin: 0; color: #ffffff;">{nome_s}</h4>
                        <p style="font-size: 1.4rem; font-weight: 800; color: #38bdf8; margin: 8px 0 0 0;">R$ {preco_s:.2f}</p>
                    </div>
                ''', unsafe_allow_html=True)
            idx += 1
    else:
        st.info("Nenhum serviço cadastrado ainda. Use o botão ⚙️ Configurações no topo para adicionar seus serviços!")

    st.markdown('</div>', unsafe_allow_html=True)

# ==============================================================================
# TAB 3: CLIENTES MENSAIS / MENSSALISTAS
# ==============================================================================
with tab_mensais:
    st.markdown('<div class="ui-card">', unsafe_allow_html=True)
    st.subheader("👥 Controle de Clientes Mensalistas / Pacotes")
    st.markdown("<p style='color: #94a3b8;'>Gerencie clientes recorrentes, registre cortes acumulados e acerte o pagamento de mensalidades.</p>", unsafe_allow_html=True)

    with st.expander("➕ Cadastrar Novo Mensalista", expanded=False):
        with st.form("form_cad_mensalista"):
            m_nome = st.text_input("Nome Completo do Cliente:")
            m_tel = st.text_input("WhatsApp (com DDD):")
            if st.form_submit_button("Cadastrar Cliente", type="primary"):
                if m_nome.strip():
                    cadastrar_cliente_mensal_banco(m_nome, m_tel)
                    st.success("Cliente mensalista cadastrado com sucesso!")
                    st.rerun()
                else:
                    st.warning("Informe o nome do cliente.")

    if not df_clientes_m.empty:
        st.markdown("<br>", unsafe_allow_html=True)
        for _, row in df_clientes_m.iterrows():
            c_id = row['id']
            c_nome = row['Cliente']
            c_tel = row['Telefone']
            c_serv = row['Serviços Feitos']
            c_val = row['Valor Devido']
            c_status = row['Status']

            cor_st = "#f43f5e" if c_status == "Pendente" and c_val > 0 else "#10b981"

            with st.container():
                st.markdown('<div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255,255,255,0.08); border-radius: 18px; padding: 20px; margin-bottom: 15px;">', unsafe_allow_html=True)
                col_m1, col_m2, col_m3, col_m4 = st.columns([2.5, 2, 2, 2.5])
                with col_m1:
                    st.markdown(f"### 👤 {c_nome}")
                    if c_tel: st.markdown(f"📱 {c_tel}")
                with col_m2:
                    st.markdown(f"**Cortes/Serviços:**<br><span style='font-size: 1.3rem; font-weight: 800; color: #38bdf8;'>{c_serv}</span>", unsafe_allow_html=True)
                with col_m3:
                    st.markdown(f"**Valor Acumulado:**<br><span style='font-size: 1.3rem; font-weight: 800; color: {cor_st};'>R$ {c_val:.2f}</span>", unsafe_allow_html=True)
                with col_m4:
                    with st.popover("⚙️ Gerenciar"):
                        st.markdown(f"**Ações para {c_nome}**")
                        add_qtd = st.number_input("Adicionar Serviços:", min_value=1, value=1, key=f"m_qtd_{c_id}")
                        serv_base = st.selectbox("Valor Base do Serviço:", list(servicos.keys()), key=f"m_serv_{c_id}") if servicos else None
                        val_base = float(servicos[serv_base]) if serv_base else 30.0
                        
                        if st.button("➕ Registrar Corte", key=f"btn_add_corte_{c_id}", type="primary", use_container_width=True):
                            atualizar_cortes_cliente_mensal(c_id, add_qtd, val_base)
                            st.success("Corte registrado!")
                            st.rerun()

                        st.markdown("---")
                        val_baixa = st.number_input("Valor Recebido (R$):", min_value=0.0, value=float(c_val), step=10.0, key=f"m_baixa_{c_id}")
                        if st.button("💰 Registrar Pagamento", key=f"btn_baixa_m_{c_id}", use_container_width=True):
                            if val_baixa > 0:
                                dar_baixa_divida_mensalista(c_id, val_baixa)
                                inserir_movimentacao_direta("Entrada", f"Pagamento Mensalista: {c_nome}", val_baixa, datetime.now(TZ).date())
                                st.success("Pagamento registrado no caixa!")
                                st.rerun()

                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Nenhum cliente mensalista cadastrado ainda.")

    st.markdown('</div>', unsafe_allow_html=True)

# ==============================================================================
# TAB 4: AGENDAMENTOS ONLINE
# ==============================================================================
with tab_agend:
    st.markdown('<div class="ui-card">', unsafe_allow_html=True)
    st.subheader("📅 Agendamentos Recebidos")
    st.markdown("<p style='color: #94a3b8;'>Visualize e gerencie os horários marcados pelos seus clientes através do link online.</p>", unsafe_allow_html=True)

    if not df_agendamentos_all.empty:
        col_filtro_dt, _ = st.columns([2, 2])
        with col_filtro_dt:
            data_filtro_ag = st.date_input("Filtrar por Data:", datetime.now(TZ).date(), key="filtro_dt_ag")

        df_ag_filtrado = df_agendamentos_all[df_agendamentos_all['Data'] == data_filtro_ag.strftime('%Y-%m-%d')]

        if not df_ag_filtrado.empty:
            for _, ag in df_ag_filtrado.iterrows():
                ag_id = ag['id']
                ag_cli = ag['Cliente']
                ag_ct = ag['Contato/WhatsApp']
                ag_srv = ag['Serviço']
                ag_hr = ag['Horário']

                with st.container():
                    st.markdown('<div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255,255,255,0.08); border-radius: 18px; padding: 18px; margin-bottom: 12px;">', unsafe_allow_html=True)
                    ca1, ca2, ca3, ca4 = st.columns([1.5, 2.5, 2.5, 2])
                    with ca1:
                        st.markdown(f"<span style='font-size: 1.4rem; font-weight: 800; color: #38bdf8;'>⏰ {ag_hr}</span>", unsafe_allow_html=True)
                    with ca2:
                        st.markdown(f"**👤 {ag_cli}**<br>📱 {ag_ct if ag_ct else 'Não informado'}", unsafe_allow_html=True)
                    with ca3:
                        st.markdown(f"**✂️ Serviço:**<br>{ag_srv}", unsafe_allow_html=True)
                    with ca4:
                        if st.button("🗑️ Concluir / Cancelar", key=f"del_ag_{ag_id}", use_container_width=True):
                            deletar_agendamento(ag_id)
                            st.success("Agendamento removido!")
                            st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info(f"Nenhum agendamento para a data {data_filtro_ag.strftime('%d/%m/%Y')}.")
    else:
        st.info("Nenhum agendamento registrado até o momento.")

    st.markdown('</div>', unsafe_allow_html=True)

# ==============================================================================
# TAB 5: FLUXO DE CAIXA COMPLETO & RELATÓRIOS CONTÁBEIS
# ==============================================================================
with tab_historico:
    st.markdown('<div class="ui-card">', unsafe_allow_html=True)
    st.subheader("💸 Histórico Completo do Fluxo de Caixa")
    st.markdown("<p style='color: #94a3b8;'>Consulte todas as entradas, saídas e pendências. Exporte relatórios contábeis em PDF ou Excel.</p>", unsafe_allow_html=True)

    if not df_fluxo_caixa.empty:
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            tipo_filtro = st.selectbox("Filtrar por Tipo:", ["Todos", "Entrada", "Saída", "Pendência"], key="flt_tipo_caixa")
        with col_f2:
            mes_relatorio = st.selectbox("Mês de Referência:", ["Todos os Meses"] + [f"{m:02d}/{ano_atual}" for m in range(1, 13)], key="flt_mes_caixa")

        df_exibir = df_fluxo_caixa.copy()
        if tipo_filtro != "Todos":
            df_exibir = df_exibir[df_exibir['Tipo'] == tipo_filtro]

        if mes_relatorio != "Todos os Meses":
            m_num = int(mes_relatorio.split('/')[0])
            df_exibir = df_exibir[(df_exibir['Data'].dt.month == m_num) & (df_exibir['Data'].dt.year == ano_atual)]

        st.markdown("<br>", unsafe_allow_html=True)

        for _, row_c in df_exibir.iterrows():
            r_id = row_c['id']
            r_dt = row_c['Data'].strftime('%d/%m/%Y') if hasattr(row_c['Data'], 'strftime') else str(row_c['Data'])
            r_tp = row_c['Tipo']
            r_desc = row_c['Descrição']
            r_val = row_c['Valor']

            cor_tp = "#10b981" if r_tp == "Entrada" else ("#f43f5e" if r_tp == "Saída" else "#f59e0b")

            with st.container():
                st.markdown('<div style="background: rgba(15, 23, 42, 0.5); border: 1px solid rgba(255,255,255,0.06); border-radius: 14px; padding: 14px 20px; margin-bottom: 8px;">', unsafe_allow_html=True)
                cx1, cx2, cx3, cx4, cx5 = st.columns([1.5, 1.5, 4, 2, 1])
                with cx1:
                    st.markdown(f"📅 **{r_dt}**")
                with cx2:
                    st.markdown(f"<span style='color: {cor_tp}; font-weight: 700;'>● {r_tp}</span>", unsafe_allow_html=True)
                with cx3:
                    st.markdown(f"{r_desc}")
                with cx4:
                    st.markdown(f"<span style='color: {cor_tp}; font-weight: 800; font-size: 1.05rem;'>R$ {r_val:,.2f}</span>", unsafe_allow_html=True)
                with cx5:
                    if st.button("🗑️", key=f"del_flx_{r_id}"):
                        deletar_movimentacao_fluxo(r_id)
                        st.success("Removido!")
                        st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("---")

        # BOTÃO EXPORTAÇÃO PDF CONTÁBIL
        if not df_exibir.empty:
            pdf_data = gerar_pdf_contabilidade(df_exibir, mes_relatorio)
            st.download_button(
                label="📄 Baixar Relatório Contábil (PDF)",
                data=pdf_data,
                file_name=f"relatorio_contabil_{st.session_state.usuario_logado}_{datetime.now(TZ).strftime('%d_%m_%Y')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
    else:
        st.info("Nenhuma movimentação no fluxo de caixa cadastrada.")

    st.markdown('</div>', unsafe_allow_html=True)

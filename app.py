import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import json
import hashlib
from io import BytesIO
import urllib.parse
import re
import decimal
import base64
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

def hash_password(password):
    return hashlib.sha256((password + SALT).encode()).hexdigest()

# LÓGICA HÍBRIDA DE SENHA: Aceita texto puro ou hash criptografado
def verificar_senha(senha_digitada, senha_no_banco):
    if not senha_no_banco:
        return False
    if senha_digitada == senha_no_banco:
        return True
    if hash_password(senha_digitada) == senha_no_banco:
        return True
    return False

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Fio&Caixa - Gestão & Agendamento", layout="wide", page_icon="✂️")

# --- PERSISTÊNCIA DE SESSÃO VIA URL (Evita logout no F5) ---
query_params = st.query_params

# ESTADOS DE SESSÃO INICIAIS
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'usuario_logado' not in st.session_state: st.session_state.usuario_logado = None
if 'eh_admin' not in st.session_state: st.session_state.eh_admin = False
if 'recuperando_senha' not in st.session_state: st.session_state.recuperando_senha = False
if 'tema_escuro' not in st.session_state: st.session_state.tema_escuro = True

# Recupera sessão persistida pela URL se houver
if not st.session_state.autenticado and "token_sessao" in query_params:
    token_val = query_params["token_sessao"]
    if token_val == "admin_master_session":
        st.session_state.autenticado = True
        st.session_state.usuario_logado = "Administrador"
        st.session_state.eh_admin = True
    elif token_val:
        st.session_state.autenticado = True
        st.session_state.usuario_logado = token_val
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
        bg_style = f'background-image: linear-gradient(135deg, rgba(8, 12, 20, 0.96) 0%, rgba(3, 5, 8, 0.99) 100%), url("data:image/png;base64,{encoded_string}") !important;'
        app_bg = "#030508"
        card_bg = "#0d131f"
        input_bg = "#080c14"
    else:
        bg_style = 'background: radial-gradient(circle at top, #1e293b 0%, #0f172a 60%, #020617 100%) !important;'
        app_bg = "#0f172a"
        card_bg = "#1e293b"
        input_bg = "#0f172a"

    st.markdown(
        f"""
        <style>
        .stApp {{
            {bg_style}
            background-color: {app_bg} !important;
            background-size: cover !important;
            background-position: center !important;
            background-attachment: fixed !important;
            color: #f8fafc !important;
        }}

        html, body, p, span, label, div, [class*="css"] {{
            color: #f8fafc !important;
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
        }}

        h1, h2, h3, h4, h5, h6 {{
            color: #ffffff !important;
            font-weight: 700 !important;
            letter-spacing: -0.5px;
        }}

        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        input, select, textarea,
        [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input,
        [data-testid="stDateInput"] input {{
            background-color: {input_bg} !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            border: 1.5px solid #1e293b !important;
            border-radius: 12px !important;
            padding: 12px 14px !important;
            font-size: 1rem !important;
            transition: all 0.2s ease-in-out !important;
        }}

        input:focus, div[data-baseweb="input"] > div:focus-within, div[data-baseweb="select"] > div:focus-within {{
            border-color: #38bdf8 !important;
            box-shadow: 0 0 12px rgba(56, 189, 248, 0.25) !important;
            background-color: {input_bg} !important;
        }}

        div[data-testid="stPopoverBody"] {{
            background-color: {card_bg} !important;
            border: 2px solid #38bdf8 !important;
            border-radius: 16px !important;
            box-shadow: 0 20px 45px rgba(0,0,0,0.85) !important;
            z-index: 999999 !important;
        }}
        div[data-testid="stPopoverBody"] * {{
            color: #ffffff !important;
        }}

        div[data-testid="stPopover"] button,
        [data-testid="stPopoverButton"] {{
            background-color: #111827 !important;
            border: 1.5px solid #38bdf8 !important;
            border-radius: 12px !important;
            padding: 8px 18px !important;
            color: #ffffff !important;
            font-weight: 800 !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
        }}

        div[data-testid="stPopover"] button:hover {{
            background-color: #1f2937 !important;
            box-shadow: 0 0 15px rgba(56, 189, 248, 0.5) !important;
        }}

        ul[data-baseweb="menu"],
        li[role="option"],
        div[data-testid="stSelectboxVirtualDropdown"] {{
            background-color: {card_bg} !important;
            color: #ffffff !important;
            border: 1px solid #1e293b !important;
        }}
        li[role="option"]:hover, [data-baseweb="menu"] li:hover {{
            background-color: #111827 !important;
            color: #38bdf8 !important;
        }}

        div[data-baseweb="calendar"],
        div[data-baseweb="calendar"] > div,
        div[role="application"] {{
            background-color: {input_bg} !important;
            color: #ffffff !important;
            border: 1px solid #1e293b !important;
        }}
        div[data-baseweb="calendar"] * {{ color: #ffffff !important; background-color: transparent !important; }}
        div[data-baseweb="calendar"] [aria-selected="true"] {{ background-color: #38bdf8 !important; color: #ffffff !important; border-radius: 50% !important; }}

        .kpi-card-v2 {{ background-color: {card_bg}; border: 1px solid #1e293b; border-radius: 14px; padding: 20px; box-shadow: 0 6px 16px rgba(0,0,0,0.4); height: 100%; display: flex; flex-direction: column; justify-content: space-between; }}
        .kpi-title-v2 {{ font-size: 0.95rem; color: #94a3b8 !important; font-weight: 600; margin-bottom: 5px; }}
        .kpi-value-v2 {{ font-size: 1.9rem; font-weight: 800; margin-bottom: 10px; }}
        .kpi-val-green {{ color: #22c55e !important; }}
        .kpi-val-red {{ color: #ef4444 !important; }}
        .kpi-val-blue {{ color: #38bdf8 !important; }}
        .kpi-perc {{ font-size: 0.85rem; font-weight: 700; display: flex; align-items: center; gap: 5px; }}
        .perc-up {{ color: #22c55e !important; }}
        .perc-down {{ color: #ef4444 !important; }}
        .perc-neutral {{ color: #94a3b8 !important; }}

        .ui-card {{ background: {card_bg}; border: 1px solid #1e293b; border-radius: 16px; padding: 24px; margin-bottom: 20px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5); }}
        .ui-card-highlight {{ background: linear-gradient(145deg, {card_bg} 0%, #111827 100%); border: 1px solid #38bdf8; border-radius: 16px; padding: 24px; box-shadow: 0 0 20px rgba(56, 189, 248, 0.15); }}

        .login-card {{ 
            background: linear-gradient(180deg, rgba(17, 24, 39, 0.95) 0%, rgba(11, 17, 32, 0.98) 100%); 
            border: 1px solid rgba(56, 189, 248, 0.25); 
            border-radius: 24px; 
            padding: 45px 36px; 
            box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.85), 0 0 30px rgba(56, 189, 248, 0.1); 
            max-width: 480px; 
            margin: 0 auto; 
            backdrop-filter: blur(12px);
        }}
        .login-brand-wrapper {{
            text-align: center;
            margin-bottom: 25px;
        }}
        .login-badge-icon {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 64px;
            height: 64px;
            background: linear-gradient(135deg, #0284c7 0%, #38bdf8 100%);
            border-radius: 18px;
            font-size: 30px;
            margin-bottom: 16px;
            box-shadow: 0 10px 25px rgba(56, 189, 248, 0.4);
        }}
        .login-title {{ 
            color: #ffffff !important; 
            font-size: 2.3rem !important; 
            font-weight: 800 !important; 
            letter-spacing: -1px;
            margin-bottom: 8px !important; 
            line-height: 1.1; 
            text-align: center; 
            background: linear-gradient(90deg, #ffffff 0%, #38bdf8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .login-subtitle {{
            color: #94a3b8 !important;
            font-size: 0.95rem !important;
            text-align: center;
            margin-bottom: 30px;
            font-weight: 500;
        }}

        .stButton > button, [data-testid="stDownloadButton"] > button {{
            background-color: #111827 !important;
            color: #ffffff !important;
            border: 1px solid #1f2937 !important;
            border-radius: 12px !important;
            font-weight: 700 !important;
            padding: 12px 20px !important;
            transition: all 0.2s ease !important;
            width: 100% !important;
        }}
        .stButton > button:hover, [data-testid="stDownloadButton"] > button:hover {{
            background-color: #1f2937 !important;
            border-color: #38bdf8 !important;
            color: #38bdf8 !important;
        }}
        .stButton > button[kind="primary"] {{ background: linear-gradient(135deg, #0284c7 0%, #38bdf8 100%) !important; color: #ffffff !important; border: none !important; box-shadow: 0 6px 20px rgba(56,189,248,0.4) !important; }}
        .stButton > button[kind="primary"]:hover {{ background: linear-gradient(135deg, #0369a1 100%, #0284c7 0%) !important; color: #ffffff !important; box-shadow: 0 8px 25px rgba(56,189,248,0.6) !important; }}

        .stTabs [data-baseweb="tab-list"] {{ 
            gap: 15px; 
            background-color: transparent; 
            display: flex; 
            justify-content: center; 
        }}
        .stTabs [data-baseweb="tab"] {{ 
            background-color: {card_bg}; 
            border-radius: 12px 12px 0 0; 
            border: 1px solid #1e293b; 
            padding: 14px 28px; 
            color: #94a3b8 !important; 
            font-size: 1.05rem;
            font-weight: 600;
        }}
        .stTabs [aria-selected="true"] {{ 
            background-color: #111827 !important; 
            color: #38bdf8 !important; 
            font-weight: bold; 
            border-top: 3px solid #38bdf8 !important; 
            box-shadow: 0 -4px 15px rgba(56, 189, 248, 0.15);
        }}
        
        @media screen and (max-width: 1024px) {{
            .stTabs [data-baseweb="tab-list"] {{
                gap: 10px !important;
                overflow-x: auto !important;
                justify-content: flex-start !important;
                padding-bottom: 5px !important;
            }}
            .stTabs [data-baseweb="tab"] {{
                font-size: 1.15rem !important;
                padding: 14px 22px !important;
                margin-right: 10px !important;
                flex-shrink: 0 !important;
            }}
        }}

        @media(min-width: 1024px) {{
            .main .block-container {{
                max-width: 82% !important;
                padding-left: 3rem !important;
                padding-right: 3rem !important;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

set_background_com_logo("logo.png")

st.markdown("""
    <style>
        footer, [data-testid="stFooter"], .stFooter,
        #MainMenu, [data-testid="stToolbar"], [data-testid="stDecoration"], .stDeployButton { display: none !important; }
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

# --- FUNÇÕES DE PERSISTÊNCIA ---
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
                    row[0]: {
                        "id": row[0], 
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
            venc_val = v["vencimento"]
            if hasattr(venc_val, 'strftime'):
                venc_str = venc_val.strftime('%Y-%m-%d')
            else:
                venc_str = str(venc_val) if venc_val else datetime.now(TZ).strftime('%Y-%m-%d')

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
                "id": k, 
                "senha": v["senha"], 
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
            result = conn.execute(text("SELECT nome, preco FROM servicos WHERE usuario_id = :user"), {"user": salao_id_clean})
            rows = result.fetchall()
            if rows: return {row[0]: float(row[1]) for row in rows}
    except Exception: pass
    return {"Corte de Cabelo": 30.00, "Barba": 30.00, "Combo Cabelo e Barba": 50.00, "Mensalidade": 100.00}

def carregar_servicos():
    usuario = st.session_state.usuario_logado if st.session_state.get("usuario_logado") else "padrao"
    return carregar_servicos_por_salao(usuario)

def salvar_ou_atualizar_servico(nome_antigo, nome_novo, preco):
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        if nome_antigo and nome_antigo != "➕ Cadastrar Novo Serviço":
            conn.execute(text("UPDATE servicos SET nome = :novo, preco = :preco WHERE usuario_id = :user AND nome = :antigo"), {"novo": nome_novo, "preco": float(preco), "user": usuario, "antigo": nome_antigo})
        else:
            conn.execute(text("INSERT INTO servicos (usuario_id, nome, preco) VALUES (:user, :nome, :preco)"), {"user": usuario, "nome": nome_novo, "preco": float(preco)})
    carregar_servicos_por_salao.clear()

def deletar_servico_banco(nome):
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        conn.execute(text("DELETE FROM servicos WHERE usuario_id = :user AND nome = :nome"), {"user": usuario, "nome": nome})
    carregar_servicos_por_salao.clear()

@st.cache_data(ttl=60)
def carregar_fluxo_por_usuario(usuario):
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, data, tipo, descricao, valor FROM fluxo_caixa WHERE usuario_id = :user ORDER BY id DESC"), {"user": usuario})
            rows = result.fetchall()
            if rows:
                df = pd.DataFrame(rows, columns=['id', 'Data', 'Tipo', 'Descrição', 'Valor'])
                df['Data'] = pd.to_datetime(df['Data'])
                return df
    except Exception: pass
    return pd.DataFrame(columns=["id", "Data", "Tipo", "Descrição", "Valor"])

def carregar_fluxo():
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    return carregar_fluxo_por_usuario(usuario)

def inserir_movimentacao_direta(tipo, descricao, valor, data_input):
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    data_str = data_input.strftime('%Y-%m-%d') if hasattr(data_input, 'strftime') else str(data_input)
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        conn.execute(text("INSERT INTO fluxo_caixa (usuario_id, data, tipo, descricao, valor) VALUES (:user, :data, :tipo, :descricao, :valor)"), {"user": usuario, "data": data_str, "tipo": tipo, "descricao": descricao, "valor": float(valor)})
    carregar_fluxo_por_usuario.clear()

def dar_baixa_fiado_direta(id_registro, nova_descricao):
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    data_hoje = datetime.now(TZ).strftime('%Y-%m-%d')
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        conn.execute(text("UPDATE fluxo_caixa SET tipo = 'Entrada', data = :data, descricao = :desc WHERE id = :id AND usuario_id = :user"), {"data": data_hoje, "desc": nova_descricao, "id": int(id_registro), "user": usuario})
    carregar_fluxo_por_usuario.clear()

def deletar_movimentacao_fluxo(id_registro):
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        conn.execute(text("DELETE FROM fluxo_caixa WHERE id = :id AND usuario_id = :user"), {"id": int(id_registro), "user": usuario})
    carregar_fluxo_por_usuario.clear()

def carregar_agendamentos_por_usuario_direto(usuario):
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, cliente_nome, cliente_contato, servico_nome, data, hora FROM agendamentos WHERE usuario_id = :user ORDER BY data ASC, hora ASC"), {"user": usuario})
            rows = result.fetchall()
            if rows: return pd.DataFrame(rows, columns=["id", "Cliente", "Contato/WhatsApp", "Serviço", "Data", "Horário"])
    except Exception: pass
    return pd.DataFrame(columns=["id", "Cliente", "Contato/WhatsApp", "Serviço", "Data", "Horário"])

def carregar_agendamentos():
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    return carregar_agendamentos_por_usuario_direto(usuario)

def deletar_agendamento(id_agendamento):
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        conn.execute(text("DELETE FROM agendamentos WHERE id = :id AND usuario_id = :user"), {"id": int(id_agendamento), "user": usuario})

# --- FUNÇÕES PARA CLIENTES MENSAIS / MENSALIDADE ---
def carregar_clientes_mensais_banco():
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, nome_cliente, telefone, servicos_feitos, valor_devido, status_divida FROM clientes_mensais WHERE usuario_id = :user ORDER BY id DESC"), {"user": usuario})
            rows = result.fetchall()
            if rows:
                return pd.DataFrame(rows, columns=["id", "Cliente", "Telefone", "Serviços Feitos", "Valor Devido", "Status"])
    except Exception: pass
    return pd.DataFrame(columns=["id", "Cliente", "Telefone", "Serviços Feitos", "Valor Devido", "Status"])

def cadastrar_cliente_mensal_banco(nome, telefone):
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        conn.execute(text("""
            INSERT INTO clientes_mensais (usuario_id, nome_cliente, telefone, servicos_feitos, valor_devido, status_divida)
            VALUES (:user, :nome, :tel, 0, 0.0, 'Pendente')
        """), {"user": usuario, "nome": nome.strip(), "tel": telefone.strip()})

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

def gerar_backup_json_completo():
    usuario = st.session_state.usuario_logado
    df_f = carregar_fluxo()
    fluxo_dict = []
    if not df_f.empty:
        df_copy = df_f.copy()
        if 'Data' in df_copy.columns: df_copy['Data'] = df_copy['Data'].dt.strftime('%Y-%m-%d')
        fluxo_dict = df_copy.to_dict(orient="records")
    def custom_serializer(obj):
        if isinstance(obj, (decimal.Decimal, float)): return float(obj)
        if isinstance(obj, (datetime, pd.Timestamp)): return obj.strftime('%Y-%m-%d')
        return str(obj)
    dados_backup = {"sistema": "Fio&Caixa", "usuario_dono": usuario, "data_geracao": datetime.now(TZ).strftime('%d/%m/%Y %H:%M:%S'), "catalogo_servicos": carregar_servicos(), "historico_financeiro": fluxo_dict}
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
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0d131f")), ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#38bdf8")), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#1e293b"))]))
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# --- TELA DE LOGIN ---
if not st.session_state.autenticado:
    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
    with st.container():
        st.markdown("""
            <div class="login-card">
                <div class="login-brand-wrapper">
                    <div class="login-badge-icon">✂️</div>
                    <div class="login-title">Fio&Caixa</div>
                    <div class="login-subtitle">Plataforma Profissional de Gestão & Agendamento</div>
                </div>
        """, unsafe_allow_html=True)

        tab_login_user, tab_login_admin, tab_rec = st.tabs(["👤 Profissional", "⚙️ Administrador", "🔑 Recuperar"])

        with tab_login_user:
            with st.form("form_login_user"):
                usuario_input = st.text_input("Usuário / Salão", placeholder="Ex: barbearia_central").strip().lower()
                senha_input = st.text_input("Senha", type="password", placeholder="Sua senha de acesso")
                btn_entrar = st.form_submit_button("Entrar no Sistema", use_container_width=True, type="primary")

                if btn_entrar:
                    usuarios_db = carregar_usuarios()
                    if usuario_input in usuarios_db:
                        dados_user = usuarios_db[usuario_input]
                        if verificar_senha(senha_input, dados_user["senha"]):
                            if dados_user.get("status") == "Inativo":
                                st.error("❌ Sua conta está desativada. Entre em contato com o suporte do sistema.")
                            else:
                                st.session_state.autenticado = True
                                st.session_state.usuario_logado = usuario_input
                                st.session_state.eh_admin = False
                                st.query_params["token_sessao"] = usuario_input
                                st.rerun()
                        else:
                            st.error("❌ Senha incorreta.")
                    else:
                        st.error("❌ Usuário não encontrado.")

        with tab_login_admin:
            with st.form("form_login_admin"):
                senha_admin_input = st.text_input("Senha Master / Administrador", type="password", placeholder="Digite a senha master")
                btn_entrar_admin = st.form_submit_button("Acessar Painel Master", use_container_width=True, type="primary")

                if btn_entrar_admin:
                    h1, h2, url_sis = carregar_admin_hashes()
                    if h1 and h2 and (verificar_senha(senha_admin_input, h1) or verificar_senha(senha_admin_input, h2)):
                        st.session_state.autenticado = True
                        st.session_state.usuario_logado = "Administrador"
                        st.session_state.eh_admin = True
                        st.query_params["token_sessao"] = "admin_master_session"
                        st.rerun()
                    else:
                        st.error("❌ Senha Master incorreta.")

        with tab_rec:
            st.markdown("<p style='font-size:0.9rem; color:#94a3b8; margin-bottom:15px;'>Digite seu usuário para receber orientações de recuperação de acesso:</p>", unsafe_allow_html=True)
            usuario_rec = st.text_input("Usuário Cadastrado", placeholder="Ex: barbearia_central", key="rec_user_input").strip().lower()
            if st.button("Enviar Solicitação", use_container_width=True):
                usuarios_db = carregar_usuarios()
                if usuario_rec in usuarios_db:
                    st.success("✅ Solicitação enviada! O administrador entrará em contato com as instruções.")
                else:
                    st.error("❌ Usuário não encontrado no sistema.")

        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# --- PAINEL DO ADMINISTRADOR MASTER ---
if st.session_state.eh_admin:
    st.markdown("""
        <div style="display: flex; justify-content: space-between; align-items: center; background: #0d131f; padding: 20px 25px; border-radius: 16px; border: 1px solid #1e293b; margin-bottom: 25px;">
            <div>
                <h1 style="margin: 0; font-size: 1.8rem; background: linear-gradient(90deg, #ffffff 0%, #38bdf8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Painel de Controle - Master</h1>
                <p style="margin: 5px 0 0 0; color: #94a3b8; font-size: 0.95rem;">Gerenciamento completo de salões, assinaturas e licenças do Fio&Caixa</p>
            </div>
    """, unsafe_allow_html=True)
    if st.button("🚪 Sair", type="primary"):
        st.session_state.autenticado = False
        st.session_state.usuario_logado = None
        st.session_state.eh_admin = False
        st.query_params.clear()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    tab_admin_geral, tab_admin_clientes, tab_admin_seguranca = st.tabs(["📊 Visão Geral", "👥 Gerenciar Salões/Usuários", "🔒 Configurações & Segurança"])

    with tab_admin_geral:
        usuarios_db = carregar_usuarios()
        total_saloes = len(usuarios_db)
        ativos = sum(1 for u in usuarios_db.values() if u.get("status") == "Ativo")
        inativos = total_saloes - ativos

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
                <div class="kpi-card-v2">
                    <div class="kpi-title-v2">Total de Salões / Contas</div>
                    <div class="kpi-value-v2 kpi-val-blue">{total_saloes}</div>
                    <div class="kpi-perc perc-neutral">Base cadastrada ativa</div>
                </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
                <div class="kpi-card-v2">
                    <div class="kpi-title-v2">Assinaturas Ativas</div>
                    <div class="kpi-value-v2 kpi-val-green">{ativos}</div>
                    <div class="kpi-perc perc-up"><span>▲</span> Em dia com o sistema</div>
                </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
                <div class="kpi-card-v2">
                    <div class="kpi-title-v2">Contas Inativas / Vencidas</div>
                    <div class="kpi-value-v2 kpi-val-red">{inativos}</div>
                    <div class="kpi-perc perc-down"><span>▼</span> Requer renovação</div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
        st.markdown("### 🔗 Links Rápidos para Salões Cadastrados")
        if usuarios_db:
            dados_links = []
            for uid in usuarios_db.keys():
                link_salao = f"{RENDER_BASE_URL}?salao={uid}"
                dados_links.append({"Usuário": uid, "Link Personalizado": link_salao})
            df_links = pd.DataFrame(dados_links)
            st.dataframe(df_links, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum salão cadastrado no momento.")

    with tab_admin_clientes:
        st.markdown("### 👥 Gerenciamento de Salões & Usuários")
        usuarios_db = carregar_usuarios()

        with st.expander("➕ Cadastrar Novo Salão / Usuário", expanded=False):
            with st.form("form_novo_salao"):
                novo_id = st.text_input("Identificador do Salão (Sem espaços, ex: barbearia_leste)").strip().lower()
                nova_senha = st.text_input("Senha de Acesso", type="password")
                novo_email = st.text_input("E-mail de Contato")
                novo_whatsapp = st.text_input("WhatsApp (Ex: 37991598179)")
                novo_venc = st.date_input("Data de Vencimento da Assinatura", value=datetime.now(TZ).date() + timedelta(days=30))
                novo_status = st.selectbox("Status da Conta", ["Ativo", "Inativo"])
                
                btn_salvar_novo = st.form_submit_button("Cadastrar Salão", type="primary")
                if btn_salvar_novo:
                    if novo_id and nova_senha:
                        if novo_id in usuarios_db:
                            st.error("❌ Este identificador de usuário já existe.")
                        else:
                            usuarios_db[novo_id] = {
                                "id": novo_id,
                                "senha": hash_password(nova_senha),
                                "email": novo_email,
                                "tipo": "Salão",
                                "vencimento": novo_venc.strftime('%Y-%m-%d'),
                                "status": novo_status,
                                "whatsapp": novo_whatsapp
                            }
                            salvar_usuarios(usuarios_db)
                            st.success(f"✅ Salão '{novo_id}' cadastrado com sucesso!")
                            st.rerun()
                    else:
                        st.error("❌ Preencha o identificador e a senha.")

        st.markdown("---")
        st.markdown("### 📋 Salões Cadastrados Atualmente")
        if usuarios_db:
            for uid, info in list(usuarios_db.items()):
                with st.container():
                    st.markdown(f"""
                        <div class="ui-card" style="padding: 18px; margin-bottom: 12px;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <h4 style="margin: 0; color: #38bdf8;">🏪 {uid}</h4>
                                    <p style="margin: 4px 0 0 0; font-size: 0.9rem; color: #94a3b8;">
                                        E-mail: {info.get('email', 'Não informado')} | WhatsApp: {info.get('whatsapp', 'Não informado')} | Vencimento: {info.get('vencimento')} | Status: <b>{info.get('status')}</b>
                                    </p>
                                </div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    col_e1, col_e2, col_e3 = st.columns([2, 2, 1])
                    with col_e1:
                        novo_status_alt = st.selectbox("Alterar Status", ["Ativo", "Inativo"], index=0 if info.get('status') == "Ativo" else 1, key=f"status_{uid}")
                    with col_e2:
                        nova_venc_alt = st.date_input("Novo Vencimento", value=datetime.strptime(info.get('vencimento', datetime.now(TZ).strftime('%Y-%m-%d')), '%Y-%m-%d').date(), key=f"venc_{uid}")
                    with col_e3:
                        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                        if st.button("Salvar Alterações", key=f"btn_salv_{uid}", use_container_width=True):
                            usuarios_db[uid]["status"] = novo_status_alt
                            usuarios_db[uid]["vencimento"] = nova_venc_alt.strftime('%Y-%m-%d')
                            salvar_usuarios(usuarios_db)
                            st.success("Atualizado!")
                            st.rerun()
        else:
            st.info("Nenhum usuário cadastrado.")

    with tab_admin_seguranca:
        st.markdown("### 🔒 Configurações de Senhas e Segurança Master")
        h1, h2, url_sis = carregar_admin_hashes()

        with st.form("form_alt_admin_senha"):
            st.markdown("#### Alterar Senhas Master")
            senha_atual_master = st.text_input("Senha Master Atual", type="password")
            nova_senha_master_1 = st.text_input("Nova Senha Master Principal", type="password")
            nova_senha_master_2 = st.text_input("Nova Senha Master de Backup (Opcional)", type="password")
            
            btn_alt_master = st.form_submit_button("Atualizar Senhas Master", type="primary")
            if btn_alt_master:
                if h1 and verificar_senha(senha_atual_master, h1):
                    novo_h1 = hash_password(nova_senha_master_1) if nova_senha_master_1 else h1
                    novo_h2 = hash_password(nova_senha_master_2) if nova_senha_master_2 else h2
                    salvar_admin_hashes(novo_h1, novo_h2, RENDER_BASE_URL)
                    st.success("✅ Senhas Master atualizadas com sucesso!")
                else:
                    st.error("❌ Senha master atual incorreta.")

    st.stop()

# --- PAINEL DO SALÃO / USUÁRIO LOGADO ---
usuario_atual = st.session_state.usuario_logado

st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; background: #0d131f; padding: 20px 25px; border-radius: 16px; border: 1px solid #1e293b; margin-bottom: 25px;">
        <div>
            <h1 style="margin: 0; font-size: 1.8rem; background: linear-gradient(90deg, #ffffff 0%, #38bdf8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Fio&Caixa • {usuario_atual.upper()}</h1>
            <p style="margin: 5px 0 0 0; color: #94a3b8; font-size: 0.95rem;">Painel de Gestão Financeira, Agendamento e Serviços</p>
        </div>
""", unsafe_allow_html=True)

col_topo_1, col_topo_2 = st.columns([1, 1])
with col_topo_2:
    col_btn_t1, col_btn_t2 = st.columns(2)
    with col_btn_t1:
        tema_txt = "☀️ Modo Claro" if st.session_state.tema_escuro else "🌙 Modo Escuro"
        if st.button(tema_txt, use_container_width=True):
            st.session_state.tema_escuro = not st.session_state.tema_escuro
            st.rerun()
    with col_btn_t2:
        if st.button("🚪 Sair da Conta", type="primary", use_container_width=True):
            st.session_state.autenticado = False
            st.session_state.usuario_logado = None
            st.session_state.eh_admin = False
            st.query_params.clear()
            st.rerun()

st.markdown("</div>", unsafe_allow_html=True)

# --- SISTEMA DE ABAS PRINCIPAIS ---
abas_principais = st.tabs([
    "📊 Fluxo de Caixa", 
    "📅 Agendamentos", 
    "💳 Mensalistas", 
    "⚙️ Serviços & Preços", 
    "📈 Relatórios & Contabilidade", 
    "💾 Backup & Dados"
])

# ==========================================
# 1. ABA: FLUXO DE CAIXA
# ==========================================
with abas_principais[0]:
    st.markdown("### 💰 Gestão do Fluxo de Caixa")
    
    col_fc1, col_fc2 = st.columns([1, 1])
    with col_fc1:
        with st.form("form_novo_lancamento", clear_on_submit=True):
            st.markdown("#### ➕ Nova Movimentação")
            tipo_mov = st.selectbox("Tipo de Movimentação", ["Entrada", "Saída", "Fiado / Pendente"])
            desc_mov = st.text_input("Descrição (Ex: Corte + Barba, Aluguel, Produto)")
            valor_mov = st.number_input("Valor (R$)", min_value=0.0, step=5.0, format="%.2f")
            data_mov = st.date_input("Data", value=datetime.now(TZ).date())
            
            btn_add_mov = st.form_submit_button("Adicionar Lançamento", type="primary", use_container_width=True)
            if btn_add_mov:
                if desc_mov and valor_mov > 0:
                    inserir_movimentacao_direta(tipo_mov, desc_mov, valor_mov, data_mov)
                    st.success("✅ Lançamento registrado com sucesso!")
                    st.rerun()
                else:
                    st.error("❌ Preencha a descrição e um valor válido.")

    with col_fc2:
        st.markdown("#### 📊 Resumo Rápido do Caixa")
        df_fluxo_atual = carregar_fluxo()
        if not df_fluxo_atual.empty:
            total_entradas = df_fluxo_atual[df_fluxo_atual['Tipo'] == 'Entrada']['Valor'].sum()
            total_saidas = df_fluxo_atual[df_fluxo_atual['Tipo'] == 'Saída']['Valor'].sum()
            total_fiado = df_fluxo_atual[df_fluxo_atual['Tipo'] == 'Fiado / Pendente']['Valor'].sum()
            saldo_liquido = total_entradas - total_saidas

            st.markdown(f"""
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                    <div class="kpi-card-v2">
                        <div class="kpi-title-v2">Total Entradas</div>
                        <div class="kpi-value-v2 kpi-val-green">R$ {total_entradas:.2f}</div>
                    </div>
                    <div class="kpi-card-v2">
                        <div class="kpi-title-v2">Total Saídas</div>
                        <div class="kpi-value-v2 kpi-val-red">R$ {total_saidas:.2f}</div>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                    <div class="kpi-card-v2">
                        <div class="kpi-title-v2">Fiados / Pendentes</div>
                        <div class="kpi-value-v2" style="color: #facc15 !important;">R$ {total_fiado:.2f}</div>
                    </div>
                    <div class="kpi-card-v2">
                        <div class="kpi-title-v2">Saldo Líquido</div>
                        <div class="kpi-value-v2 kpi-val-blue">R$ {saldo_liquido:.2f}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Nenhuma movimentação registrada ainda.")

    st.markdown("---")
    st.markdown("### 📋 Histórico Completo de Lançamentos")
    
    if not df_fluxo_atual.empty:
        # Filtros e formatação em cores para Entradas, Saídas e Pendências
        def colorir_linhas_fluxo(row):
            if row['Tipo'] == 'Entrada':
                return ['background-color: rgba(34, 197, 94, 0.15); color: #22c55e !important'] * len(row)
            elif row['Tipo'] == 'Saída':
                return ['background-color: rgba(239, 68, 68, 0.15); color: #ef4444 !important'] * len(row)
            else:
                return ['background-color: rgba(250, 204, 21, 0.15); color: #facc15 !important'] * len(row)

        df_exibicao = df_fluxo_atual.copy()
        df_exibicao['Valor Formatado'] = df_exibicao['Valor'].apply(lambda x: f"R$ {x:.2f}")
        df_exibicao['Data'] = pd.to_datetime(df_exibicao['Data']).dt.strftime('%d/%m/%Y')

        st.dataframe(
            df_exibicao.style.apply(colorir_linhas_fluxo, axis=1),
            use_container_width=True,
            hide_index=True,
            column_order=["id", "Data", "Tipo", "Descrição", "Valor Formatado"]
        )

        st.markdown("#### ⚡ Ações Rápidas (Baixa de Fiado ou Exclusão)")
        col_act1, col_act2 = st.columns(2)
        with col_act1:
            with st.form("form_baixa_fiado"):
                st.markdown("**Dar Baixa em Fiado / Pendência**")
                fiados_pendentes = df_fluxo_atual[df_fluxo_atual['Tipo'] == 'Fiado / Pendente']
                if not fiados_pendentes.empty:
                    opcoes_fiado = {f"ID {row['id']} - {row['Descrição']} (R$ {row['Valor']:.2f})": row['id'] for _, row in fiados_pendentes.iterrows()}
                    escolha_fiado = st.selectbox("Selecione o Fiado", options=list(opcoes_fiado.keys()))
                    nova_desc_baixa = st.text_input("Descrição da Baixa", value="Pagamento de Fiado Recebido")
                    btn_exec_baixa = st.form_submit_button("Confirmar Recebimento (Converter em Entrada)", type="primary")
                    if btn_exec_baixa:
                        id_alvo = opcoes_fiado[escolha_fiado]
                        dar_baixa_fiado_direta(id_alvo, nova_desc_baixa)
                        st.success("✅ Fiado baixado e convertido em Entrada com sucesso!")
                        st.rerun()
                else:
                    st.info("Nenhum fiado pendente no momento.")

        with col_act2:
            with st.form("form_excluir_mov"):
                st.markdown("**Excluir Lançamento do Caixa**")
                opcoes_mov = {f"ID {row['id']} - {row['Tipo']} | {row['Descrição']} (R$ {row['Valor']:.2f})": row['id'] for _, row in df_fluxo_atual.iterrows()}
                escolha_mov = st.selectbox("Selecione o Lançamento", options=list(opcoes_mov.keys()))
                btn_exec_del = st.form_submit_button("Excluir Movimentação", type="primary")
                if btn_exec_del:
                    id_alvo_del = opcoes_mov[escolha_mov]
                    deletar_movimentacao_fluxo(id_alvo_del)
                    st.success("✅ Lançamento excluído com sucesso!")
                    st.rerun()
    else:
        st.info("Nenhum dado financeiro para exibir no histórico.")

# ==========================================
# 2. ABA: AGENDAMENTOS
# ==========================================
with abas_principais[1]:
    st.markdown("### 📅 Gestão de Agendamentos")
    
    col_ag1, col_ag2 = st.columns([1, 1])
    with col_ag1:
        with st.form("form_novo_agendamento", clear_on_submit=True):
            st.markdown("#### ➕ Novo Agendamento")
            cli_nome = st.text_input("Nome do Cliente")
            cli_contato = st.text_input("Contato / WhatsApp (Ex: 37991598179)")
            
            servicos_disponiveis = carregar_servicos()
            serv_escolhido = st.selectbox("Serviço", options=list(servicos_disponiveis.keys()))
            
            data_ag = st.date_input("Data do Agendamento", value=datetime.now(TZ).date())
            hora_ag = st.time_input("Horário", value=datetime.now(TZ).time())
            
            btn_add_ag = st.form_submit_button("Salvar Agendamento", type="primary", use_container_width=True)
            if btn_add_ag:
                if cli_nome and serv_escolhido:
                    usuario = str(st.session_state.usuario_logado).strip().lower()
                    data_str = data_ag.strftime('%Y-%m-%d')
                    hora_str = hora_ag.strftime('%H:%M')
                    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
                        conn.execute(text("""
                            INSERT INTO agendamentos (usuario_id, cliente_nome, cliente_contato, servico_nome, data, hora)
                            VALUES (:user, :nome, :contato, :servico, :data, :hora)
                        """), {"user": usuario, "nome": cli_nome, "contato": cli_contato, "servico": serv_escolhido, "data": data_str, "hora": hora_str})
                    st.success("✅ Agendamento salvo com sucesso!")
                    st.rerun()
                else:
                    st.error("❌ Preencha o nome do cliente.")

    with col_ag2:
        st.markdown("#### 📋 Agendamentos Futuros e Atuais")
        df_agendamentos = carregar_agendamentos()
        if not df_agendamentos.empty:
            st.dataframe(df_agendamentos, use_container_width=True, hide_index=True)

            with st.form("form_del_agendamento"):
                st.markdown("**Remover Agendamento Concluído ou Cancelado**")
                opcoes_ag = {f"ID {row['id']} - {row['Cliente']} ({row['Data']} às {row['Horário']})": row['id'] for _, row in df_agendamentos.iterrows()}
                escolha_ag = st.selectbox("Selecione o Agendamento", options=list(opcoes_ag.keys()))
                btn_del_ag = st.form_submit_button("Excluir Agendamento", type="primary")
                if btn_del_ag:
                    deletar_agendamento(opcoes_ag[escolha_ag])
                    st.success("✅ Agendamento removido!")
                    st.rerun()
        else:
            st.info("Nenhum agendamento cadastrado.")

# ==========================================
# 3. ABA: MENSALISTAS
# ==========================================
with abas_principais[2]:
    st.markdown("### 💳 Gestão de Clientes Mensais (Mensalistas)")
    
    col_m1, col_m2 = st.columns([1, 1])
    with col_m1:
        with st.form("form_novo_mensalista", clear_on_submit=True):
            st.markdown("#### ➕ Cadastrar Novo Mensalista")
            nome_m = st.text_input("Nome do Cliente Mensal")
            tel_m = st.text_input("Telefone / WhatsApp")
            btn_cad_m = st.form_submit_button("Cadastrar Mensalista", type="primary", use_container_width=True)
            if btn_cad_m:
                if nome_m:
                    cadastrar_cliente_mensal_banco(nome_m, tel_m)
                    st.success("✅ Mensalista cadastrado com sucesso!")
                    st.rerun()
                else:
                    st.error("❌ Digite o nome do cliente.")

    with col_m2:
        with st.form("form_lancar_corte_mensalista", clear_on_submit=True):
            st.markdown("#### ✂️ Registrar Serviço Realizado (Mensalista)")
            df_mensalistas = carregar_clientes_mensais_banco()
            if not df_mensalistas.empty:
                opcoes_mensalistas = {f"{row['Cliente']} (Devido: R$ {row['Valor Devido']:.2f})": row['id'] for _, row in df_mensalistas.iterrows()}
                escolha_mensalista = st.selectbox("Selecione o Mensalista", options=list(opcoes_mensalistas.keys()))
                qtd_servicos = st.number_input("Quantidade de Serviços Realizados", min_value=1, value=1, step=1)
                
                servs = carregar_servicos()
                preco_padrao_servico = list(servs.values())[0] if servs else 30.0
                valor_por_servico = st.number_input("Valor Cobrado por Serviço (R$)", value=float(preco_padrao_servico), step=5.0)

                btn_lanc_serv = st.form_submit_button("Adicionar ao Saldo Devedor", type="primary")
                if btn_lanc_serv:
                    id_c = opcoes_mensalistas[escolha_mensalista]
                    atualizar_cortes_cliente_mensal(id_c, qtd_servicos, valor_por_servico)
                    st.success("✅ Serviços adicionados à conta do mensalista!")
                    st.rerun()
            else:
                st.info("Nenhum mensalista cadastrado.")

    st.markdown("---")
    st.markdown("### 📋 Lista de Mensalistas e Saldos")
    df_mensalistas_atual = carregar_clientes_mensais_banco()
    if not df_mensalistas_atual.empty:
        st.dataframe(df_mensalistas_atual, use_container_width=True, hide_index=True)

        with st.form("form_baixa_mensalista"):
            st.markdown("**Quitar ou Dar Baixa em Mensalista**")
            opcoes_mensalistas_baixa = {f"{row['Cliente']} - Devido: R$ {row['Valor Devido']:.2f}": row['id'] for _, row in df_mensalistas_atual.iterrows()}
            escolha_m_baixa = st.selectbox("Selecione para Baixa", options=list(opcoes_mensalistas_baixa.keys()))
            valor_baixa_m = st.number_input("Valor Recebido na Baixa (R$)", min_value=0.0, step=10.0, format="%.2f")
            btn_exec_baixa_m = st.form_submit_button("Confirmar Baixa / Pagamento", type="primary")
            if btn_exec_baixa_m:
                id_cli_alvo = opcoes_mensalistas_baixa[escolha_m_baixa]
                dar_baixa_divida_mensalista(id_cli_alvo, valor_baixa_m)
                
                # Registra entrada no fluxo de caixa automaticamente
                cliente_nome_txt = escolha_m_baixa.split(" - ")[0]
                inserir_movimentacao_direta("Entrada", f"Mensalidade / Acerto - {cliente_nome_txt}", valor_baixa_m, datetime.now(TZ).date())
                
                st.success("✅ Baixa realizada com sucesso e registrada no Caixa!")
                st.rerun()
    else:
        st.info("Nenhum mensalista cadastrado.")

# ==========================================
# 4. ABA: SERVIÇOS & PREÇOS
# ==========================================
with abas_principais[3]:
    st.markdown("### ⚙️ Catálogo de Serviços & Preços")
    
    col_s1, col_s2 = st.columns([1, 1])
    with col_s1:
        with st.form("form_cad_servico", clear_on_submit=True):
            st.markdown("#### ➕ Cadastrar ou Atualizar Serviço")
            servicos_atuais = carregar_servicos()
            lista_nomes = ["➕ Cadastrar Novo Serviço"] + list(servicos_atuais.keys())
            servico_selecionado = st.selectbox("Serviço Existente (para alterar) ou Novo", options=lista_nomes)
            
            novo_nome_serv = st.text_input("Nome do Serviço")
            novo_preco_serv = st.number_input("Preço (R$)", min_value=0.0, step=5.0, format="%.2f")
            
            btn_salvar_serv = st.form_submit_button("Salvar Serviço", type="primary", use_container_width=True)
            if btn_salvar_serv:
                nome_final = novo_nome_serv.strip() if servico_selecionado == "➕ Cadastrar Novo Serviço" else servico_selecionado
                if servico_selecionado != "➕ Cadastrar Novo Serviço" and novo_nome_serv.strip():
                    nome_final = novo_nome_serv.strip()
                
                if nome_final and novo_preco_serv > 0:
                    salvar_ou_atualizar_servico(servico_selecionado if servico_selecionado != "➕ Cadastrar Novo Serviço" else "", nome_final, novo_preco_serv)
                    st.success("✅ Serviço salvo com sucesso!")
                    st.rerun()
                else:
                    st.error("❌ Preencha o nome e o preço do serviço.")

    with col_s2:
        st.markdown("#### 📋 Serviços Cadastrados Atualmente")
        servicos_atuais = carregar_servicos()
        if servicos_atuais:
            df_serv = pd.DataFrame(list(servicos_atuais.items()), columns=["Serviço", "Preço (R$)"])
            df_serv['Preço (R$)'] = df_serv['Preço (R$)'].apply(lambda x: f"R$ {x:.2f}")
            st.dataframe(df_serv, use_container_width=True, hide_index=True)

            with st.form("form_del_servico"):
                st.markdown("**Remover Serviço**")
                serv_a_deletar = st.selectbox("Selecione o Serviço para Excluir", options=list(servicos_atuais.keys()))
                btn_exec_del_serv = st.form_submit_button("Excluir Serviço", type="primary")
                if btn_exec_del_serv:
                    deletar_servico_banco(serv_a_deletar)
                    st.success("✅ Serviço excluído!")
                    st.rerun()
        else:
            st.info("Nenhum serviço cadastrado.")

# ==========================================
# 5. ABA: RELATÓRIOS & CONTABILIDADE
# ==========================================
with abas_principais[4]:
    st.markdown("### 📈 Relatórios & Contabilidade")
    
    df_fluxo_rel = carregar_fluxo()
    if not df_fluxo_rel.empty:
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            mes_ref_rel = st.selectbox("Mês de Referência", options=["Todos os Registros", "Mês Atual", "Últimos 30 dias"])
        
        df_filtrado = df_fluxo_rel.copy()
        if mes_ref_rel == "Mês Atual":
            hoje = datetime.now(TZ)
            df_filtrado = df_filtrado[(df_filtrado['Data'].dt.month == hoje.month) & (df_filtrado['Data'].dt.year == hoje.year)]
        elif mes_ref_rel == "Últimos 30 dias":
            limite_data = datetime.now(TZ) - timedelta(days=30)
            df_filtrado = df_filtrado[df_filtrado['Data'] >= pd.Timestamp(limite_data.date())]

        st.markdown("#### 📊 Gráfico de Movimentações")
        if not df_filtrado.empty:
            fig = px.bar(df_filtrado, x='Data', y='Valor', color='Tipo', barmode='group', color_discrete_map={'Entrada': '#22c55e', 'Saída': '#ef4444', 'Fiado / Pendente': '#facc15'})
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#ffffff')
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### 📄 Gerar Relatório em PDF")
        pdf_bytes = gerar_pdf_contabilidade(df_filtrado, mes_ref_rel)
        st.download_button(
            label="📥 Baixar Relatório Contábil (PDF)",
            data=pdf_bytes,
            file_name=f"relatorio_contabil_{usuario_atual}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    else:
        st.info("Nenhum dado financeiro para gerar relatórios.")

# ==========================================
# 6. ABA: BACKUP & DADOS
# ==========================================
with abas_principais[5]:
    st.markdown("### 💾 Backup e Exportação de Dados")
    st.markdown("<p style='color: #94a3b8;'>Faça o backup de todos os seus registros financeiros e serviços em formato JSON para total segurança.</p>", unsafe_allow_html=True)

    json_data_str = gerar_backup_json_completo()
    st.download_button(
        label="📥 Baixar Backup Completo (JSON)",
        data=json_data_str,
        file_name=f"backup_fiocaixa_{usuario_atual}_{datetime.now(TZ).strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        use_container_width=True
    )

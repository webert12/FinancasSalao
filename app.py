import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from calendar import monthrange
import os
import json
import hashlib
from io import BytesIO
import urllib.parse
import re
from decimal import Decimal, ROUND_HALF_UP
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
        
        /* CORREÇÃO DO TAMANHO DAS ABAS E ESPAÇAMENTO PARA DISPOSITIVOS MÓVEIS */
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
            if rows: return {row[0]: Decimal(str(row[1])) for row in rows}
    except Exception: pass
    return {
        "Corte de Cabelo": Decimal("30.00"),
        "Barba": Decimal("30.00"),
        "Combo Cabelo e Barba": Decimal("50.00"),
        "Mensalidade": Decimal("100.00")
    }

def carregar_servicos():
    usuario = st.session_state.usuario_logado if st.session_state.get("usuario_logado") else "padrao"
    return carregar_servicos_por_salao(usuario)

def salvar_ou_atualizar_servico(nome_antigo, nome_novo, preco):
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    preco_dec = Decimal(str(preco))
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        if nome_antigo and nome_antigo != "➕ Cadastrar Novo Serviço":
            conn.execute(text("UPDATE servicos SET nome = :novo, preco = :preco WHERE usuario_id = :user AND nome = :antigo"), {"novo": nome_novo, "preco": float(preco_dec), "user": usuario, "antigo": nome_antigo})
        else:
            conn.execute(text("INSERT INTO servicos (usuario_id, nome, preco) VALUES (:user, :nome, :preco)"), {"user": usuario, "nome": nome_novo, "preco": float(preco_dec)})
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
                processed_rows = [[r[0], r[1], r[2], r[3], Decimal(str(r[4]))] for r in rows]
                df = pd.DataFrame(processed_rows, columns=['id', 'Data', 'Tipo', 'Descrição', 'Valor'])
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
    valor_dec = Decimal(str(valor))
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        conn.execute(text("INSERT INTO fluxo_caixa (usuario_id, data, tipo, descricao, valor) VALUES (:user, :data, :tipo, :descricao, :valor)"), {"user": usuario, "data": data_str, "tipo": tipo, "descricao": descricao, "valor": float(valor_dec)})
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
                processed_rows = [[r[0], r[1], r[2], r[3], Decimal(str(r[4])), r[5]] for r in rows]
                return pd.DataFrame(processed_rows, columns=["id", "Cliente", "Telefone", "Serviços Feitos", "Valor Devido", "Status"])
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
            valor_atual = Decimal(str(res[1]))
            acrescentar = Decimal(str(qtd_adicionar)) * Decimal(str(valor_por_servico))
            novo_valor = valor_atual + acrescentar
            conn.execute(text("""
                UPDATE clientes_mensais 
                SET servicos_feitos = :s, valor_devido = :v, status_divida = 'Pendente'
                WHERE id = :id
            """), {"s": novos_servicos, "v": float(novo_valor), "id": int(id_cliente)})

def dar_baixa_divida_mensalista(id_cliente, valor_baixa):
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE;"))
        res = conn.execute(text("SELECT valor_devido FROM clientes_mensais WHERE id = :id"), {"id": int(id_cliente)}).fetchone()
        if res:
            devido_atual = Decimal(str(res[0]))
            valor_baixa_dec = Decimal(str(valor_baixa))
            novo_valor_devido = max(Decimal("0.00"), devido_atual - valor_baixa_dec)
            novo_status = 'Quitado' if novo_valor_devido == Decimal("0.00") else 'Pendente'
            conn.execute(text("""
                UPDATE clientes_mensais 
                SET valor_devido = :v, status_divida = :st
                WHERE id = :id
            """), {"v": float(novo_valor_devido), "st": novo_status, "id": int(id_cliente)})

# --- RENDERIZADOR DE CLIENTES MENSAIS ---
def render_clientes_mensais():
    st.markdown("### 👥 Clientes Mensais / Mensalistas")

    df_cli = carregar_clientes_mensais_banco()
    if df_cli.empty:
        st.info("Nenhum cliente mensalista cadastrado.")
    else:
        st.dataframe(df_cli, use_container_width=True)

    st.markdown("---")
    st.markdown("#### ➕ Cadastrar Novo Cliente Mensalista")
    with st.form("form_novo_cliente_mensal"):
        nome = st.text_input("Nome do Cliente")
        telefone = st.text_input("Telefone / WhatsApp")
        submitted = st.form_submit_button("Salvar Cliente")
        if submitted:
            if nome:
                try:
                    cadastrar_cliente_mensal_banco(nome, telefone)
                    st.success("Cliente mensalista cadastrado com sucesso.")
                    carregar_clientes_mensais_banco.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar cliente: {e}")
            else:
                st.error("Informe o nome do cliente.")

    st.markdown("---")
    st.markdown("#### ✂️ Atualizar Serviços / Cortes")
    if not df_cli.empty:
        cliente_sel = st.selectbox("Selecione Cliente", df_cli["Cliente"].tolist())
        qtd = st.number_input("Quantidade de serviços/cortes a adicionar", min_value=1, step=1)
        valor_servico = st.number_input("Valor por serviço (R$)", min_value=0.0, step=1.0, format="%.2f")
        if st.button("Adicionar Serviços"):
            try:
                id_cliente = int(df_cli[df_cli["Cliente"] == cliente_sel]["id"].iloc[0])
                atualizar_cortes_cliente_mensal(id_cliente, qtd, valor_servico)
                st.success("Serviços adicionados com sucesso.")
                carregar_clientes_mensais_banco.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao atualizar: {e}")

    st.markdown("---")
    st.markdown("#### 💵 Dar Baixa em Dívida")
    if not df_cli.empty:
        cliente_sel2 = st.selectbox("Selecione Cliente para baixa", df_cli["Cliente"].tolist(), key="baixa")
        valor_baixa = st.number_input("Valor da baixa (R$)", min_value=0.0, step=1.0, format="%.2f")
        if st.button("Dar Baixa"):
            try:
                id_cliente = int(df_cli[df_cli["Cliente"] == cliente_sel2]["id"].iloc[0])
                dar_baixa_divida_mensalista(id_cliente, valor_baixa)
                st.success("Baixa registrada com sucesso.")
                carregar_clientes_mensais_banco.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao dar baixa: {e}")

def gerar_backup_json_completo():
    usuario = st.session_state.usuario_logado
    df_f = carregar_fluxo()
    fluxo_dict = []
    if not df_f.empty:
        df_copy = df_f.copy()
        if 'Data' in df_copy.columns: df_copy['Data'] = df_copy['Data'].dt.strftime('%Y-%m-%d')
        fluxo_dict = df_copy.to_dict(orient="records")
    def custom_serializer(obj):
        if isinstance(obj, Decimal): return float(obj)
        if isinstance(obj, float): return obj
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
        val_dec = Decimal(str(row['Valor']))
        table_data.append([dt_str, str(row['Tipo']), str(row['Descrição']), f"R$ {val_dec:.2f}"])
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
        .floating-wa {{ position: fixed; width: 55px; height: 55px; bottom: 30px; right: 30px; background-color: #22c55e; border-radius: 50px; text-align: center; box-shadow: 0px 4px 15px rgba(0,0,0,0.5); z-index: 9999999; display: flex; align-items: center; justify-content: center; text-decoration: none; transition: transform 0.3s ease; }}
        .floating-wa:hover {{ transform: scale(1.1); }}
        .floating-wa svg {{ width: 32px; height: 32px; fill: white; }}
        </style>
        <a href="https://api.whatsapp.com/send?phone={support_phone}&text={wa_msg}" class="floating-wa" target="_blank" title="Falar com Suporte">
            <svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg"><path d="M16 2a13 13 0 0 0-10.85 20.24L3.6 28.5l6.43-1.5A13 13 0 1 0 16 2zm0 24a10.9 10.9 0 0 1-5.54-1.5l-.4-.24-4.14 1 .97-4.04-.26-.4A11 11 0 1 1 16 26zm6-8.2c-.33-.16-1.95-.96-2.25-1.07-.3-.1-.52-.16-.74.17-.22.33-.85 1.07-1.04 1.28-.2.22-.39.25-.72.09-.33-.16-1.4-.52-2.65-1.64-1-1-1.68-2.22-1.88-2.55-.2-.33-.02-.51.15-.67.15-.15.33-.39.5-.59.16-.2.22-.33.32-.55.1-.22.05-.42-.03-.58-.08-.16-.74-1.78-1-2.43-.27-.64-.53-.55-.74-.56h-.63c-.22 0-.58.08-.88.42-.3.33-1.15 1.12-1.15 2.73s1.18 3.16 1.34 3.37c.16.22 2.3 3.51 5.56 4.92 2.22.95 3.02 1.02 4.1 1.02s1.95-.8 2.25-1.57c.3-.77.3-1.43.22-1.57-.1-.13-.33-.2-.66-.36z"/></svg>
        </a>
    """, unsafe_allow_html=True)

# --- FINANCEIRO PREMIUM (FLUXO DE CAIXA) ---
def _format_currency(v):
    try:
        return f"R$ {float(v):,.2f}"
    except Exception:
        return str(v)

def render_financeiro_painel():
    st.markdown("### 💰 Financeiro — Fluxo de Caixa")
    df_fluxo = carregar_fluxo()
    hoje = datetime.now(TZ).date()

    # Resumo rápido
    total_entradas = 0.0
    total_saidas = 0.0
    if not df_fluxo.empty:
        entradas = df_fluxo[df_fluxo['Tipo'].str.lower().str.contains('entrada', na=False)]
        saidas = df_fluxo[df_fluxo['Tipo'].str.lower().str.contains('saida|saída|despesa', na=False)]
        total_entradas = float(entradas['Valor'].sum()) if not entradas.empty else 0.0
        total_saidas = float(saidas['Valor'].sum()) if not saidas.empty else 0.0

    r1, r2, r3 = st.columns(3)
    with r1:
        st.markdown("**Entradas (total)**")
        st.markdown(f"<div class='kpi-value-v2 kpi-val-green'>{_format_currency(total_entradas)}</div>", unsafe_allow_html=True)
    with r2:
        st.markdown("**Saídas (total)**")
        st.markdown(f"<div class='kpi-value-v2 kpi-val-red'>{_format_currency(total_saidas)}</div>", unsafe_allow_html=True)
    with r3:
        saldo = total_entradas - total_saidas
        color = "kpi-val-green" if saldo >= 0 else "kpi-val-red"
        st.markdown("**Saldo**")
        st.markdown(f"<div class='kpi-value-v2 {color}'>{_format_currency(saldo)}</div>", unsafe_allow_html=True)

    st.markdown("---")

    # Formulário rápido para nova movimentação
    st.markdown("#### ➕ Adicionar Movimentação")
    with st.form("form_nova_mov"):
        tipo = st.selectbox("Tipo", ["Entrada", "Saída", "Fiado"], index=0)
        descricao = st.text_input("Descrição")
        valor = st.number_input("Valor (R$)", min_value=0.0, format="%.2f", step=1.0)
        data_mov = st.date_input("Data", value=hoje)
        submitted = st.form_submit_button("Salvar Movimentação")
        if submitted:
            if descricao and valor > 0:
                try:
                    inserir_movimentacao_direta(tipo, descricao, float(valor), data_mov)
                    st.success("Movimentação adicionada com sucesso.")
                    carregar_fluxo_por_usuario.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar movimentação: {e}")
            else:
                st.error("Preencha descrição e valor maior que zero.")

    st.markdown("---")

    # Tabela interativa com ações
    st.markdown("#### 📋 Histórico (últimas 200 entradas)")
    if df_fluxo.empty:
        st.info("Nenhuma movimentação registrada.")
        return

    df_show = df_fluxo.copy().sort_values(by="Data", ascending=False).head(200)
    df_show['Data_str'] = pd.to_datetime(df_show['Data']).dt.strftime('%d/%m/%Y')
    df_show_display = df_show[['id', 'Data_str', 'Tipo', 'Descrição', 'Valor']].rename(columns={'Data_str':'Data'})

    # Render tabela simples com botões de ação por linha
    for _, row in df_show_display.iterrows():
        with st.container():
            cols = st.columns([2,2,3,3,1])
            cols[0].markdown(f"**{row['Data']}**")
            cols[1].markdown(f"**{row['Tipo']}**")
            cols[2].markdown(f"{row['Descrição']}")
            cols[3].markdown(f"<b>{_format_currency(row['Valor'])}</b>", unsafe_allow_html=True)
            btn_col = cols[4]
            if btn_col.button("🗑️", key=f"del_{row['id']}"):
                try:
                    deletar_movimentacao_fluxo(row['id'])
                    st.success("Movimentação removida.")
                    carregar_fluxo_por_usuario.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao deletar: {e}")

    st.markdown("---")

    # Ações em lote e relatórios rápidos
    a1, a2, a3 = st.columns([2,2,2])
    with a1:
        if st.button("Marcar Fiados como Recebidos (hoje)"):
            df_fiados = df_fluxo[df_fluxo['Tipo'].str.lower().str.contains('fiado', na=False)]
            if df_fiados.empty:
                st.info("Nenhum fiado encontrado.")
            else:
                count = 0
                for idx, r in df_fiados.iterrows():
                    try:
                        dar_baixa_fiado_direta(int(r['id']), f"Baixa automática {datetime.now(TZ).strftime('%d/%m/%Y')}")
                        count += 1
                    except Exception:
                        pass
                carregar_fluxo_por_usuario.clear()
                st.success(f"{count} fiados marcados como recebidos.")
                st.rerun()
    with a2:
        if st.button("Limpar entradas antigas (mais de 2 anos)"):
            cutoff = (datetime.now(TZ) - timedelta(days=365*2)).strftime('%Y-%m-%d')
            try:
                with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                    res = conn.execute(text("DELETE FROM fluxo_caixa WHERE data < :cutoff"), {"cutoff": cutoff})
                carregar_fluxo_por_usuario.clear()
                st.success("Movimentações antigas removidas.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao limpar: {e}")
    with a3:
        st.write("")

# --- TELA INICIAL (BOAS-VINDAS + RESUMO DO DIA) ---
def render_tela_inicial():
    usuario = st.session_state.usuario_logado if st.session_state.get("usuario_logado") else "Usuário"
    st.markdown(f"## 👋 Olá, **{usuario.replace('_', ' ').replace('-', ' ').title()}**")
    st.markdown("Bem-vindo ao painel de gestão. Aqui está um resumo rápido do seu dia e das métricas importantes.")

    # Resumo financeiro do dia
    df_fluxo = carregar_fluxo()
    hoje = datetime.now(TZ).date()
    receita_dia = Decimal("0.00")
    despesas_dia = Decimal("0.00")
    if not df_fluxo.empty:
        df_fluxo['Data_dt'] = pd.to_datetime(df_fluxo['Data']).dt.date
        df_hoje = df_fluxo[df_fluxo['Data_dt'] == hoje]
        if not df_hoje.empty:
            receita_dia = sum(df_hoje[df_hoje['Tipo'].str.lower().str.contains('entrada', na=False)]['Valor'], Decimal("0.00"))
            despesas_dia = sum(df_hoje[df_hoje['Tipo'].str.lower().str.contains('saida|saída|despesa', na=False)]['Valor'], Decimal("0.00"))

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Receita Hoje**")
        st.markdown(f"<div class='kpi-value-v2 kpi-val-green'>R$ {receita_dia:,.2f}</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("**Despesas Hoje**")
        st.markdown(f"<div class='kpi-value-v2 kpi-val-red'>R$ {despesas_dia:,.2f}</div>", unsafe_allow_html=True)
    with c3:
        saldo = receita_dia - despesas_dia
        color = "kpi-val-green" if saldo >= Decimal("0.00") else "kpi-val-red"
        st.markdown("**Saldo do Dia**")
        st.markdown(f"<div class='kpi-value-v2 {color}'>R$ {saldo:,.2f}</div>", unsafe_allow_html=True)

    st.markdown("---")

    # Próximos agendamentos do dia
    df_ag = carregar_agendamentos()
    if not df_ag.empty:
        df_ag['Data_dt'] = pd.to_datetime(df_ag['Data']).dt.date
        proximos = df_ag[df_ag['Data_dt'] >= hoje].sort_values(by=['Data', 'Horário']).head(8)
    else:
        proximos = pd.DataFrame()

    st.markdown("### 📌 Próximos Agendamentos")
    if proximos.empty:
        st.info("Nenhum agendamento futuro encontrado.")
    else:
        for _, row in proximos.iterrows():
            data_str = pd.to_datetime(row['Data']).strftime('%d/%m/%Y')
            hora = row.get('Horário', '')
            st.markdown(f"- **{data_str} {hora}** — **{row.get('Cliente','')}** · _{row.get('Serviço','')}_ · {row.get('Contato/WhatsApp','')}")

    st.markdown("---")

    # Atalhos rápidos
    st.markdown("### ⚡ Atalhos Rápidos")
    a1, a2, a3 = st.columns(3)
    with a1:
        if st.button("Abrir Agenda", key="btn_at_agenda"):
            st.session_state._open_page = "agenda"
    with a2:
        if st.button("Novo Agendamento", key="btn_at_novo_ag"):
            st.session_state._show_novo_agendamento = True
    with a3:
        if st.button("Exportar Backup JSON", key="btn_at_backup"):
            json_data = gerar_backup_json_completo()
            b64 = base64.b64encode(json_data.encode()).decode()
            href = f'<a href="data:application/json;base64,{b64}" download="backup_fio_caixa_{datetime.now(TZ).strftime("%Y%m%d_%H%M%S")}.json" style="color:#38bdf8; font-weight:bold;">Clique para baixar backup</a>'
            st.markdown(href, unsafe_allow_html=True)

    st.markdown("---")

    # Pequeno painel de serviços e ticket médio
    servs = carregar_servicos()
    total_servicos = len(servs)
    ticket_medio = Decimal("0.00")
    if not df_fluxo.empty and total_servicos > 0:
        entradas = df_fluxo[df_fluxo['Tipo'].str.lower().str.contains('entrada', na=False)]
        if not entradas.empty:
            soma_tot = sum(entradas['Valor'], Decimal("0.00"))
            ticket_medio = soma_tot / Decimal(str(len(entradas)))

    s1, s2 = st.columns([2,1])
    with s1:
        st.markdown(f"**Serviços cadastrados:** {total_servicos}")
        st.markdown("**Catálogo (exemplo):** " + (", ".join(list(servs.keys())[:6]) if servs else "Nenhum serviço cadastrado."))
    with s2:
        st.markdown("**Ticket Médio**")
        st.markdown(f"<div class='kpi-value-v2'>R$ {ticket_medio:,.2f}</div>", unsafe_allow_html=True)

# --- AGENDA PREMIUM (VISUAL DIÁRIO / SEMANAL) ---
def _format_hora(h):
    try:
        return datetime.strptime(str(h), "%H:%M").strftime("%H:%M")
    except Exception:
        return str(h)

def render_agenda_painel():
    st.markdown("### 📅 Agenda Premium")
    if "agenda_data_ref" not in st.session_state:
        st.session_state.agenda_data_ref = datetime.now(TZ).date()

    col_a, col_b, col_c = st.columns([1,2,1])
    with col_a:
        if st.button("◀️ Dia Anterior"):
            st.session_state.agenda_data_ref = st.session_state.agenda_data_ref - timedelta(days=1)
            st.rerun()
    with col_b:
        if st.button("📍 Hoje"):
            st.session_state.agenda_data_ref = datetime.now(TZ).date()
            st.rerun()
        st.markdown(f"**Data selecionada:** {st.session_state.agenda_data_ref.strftime('%d/%m/%Y')}")
    with col_c:
        if st.button("Dia Seguinte ▶️"):
            st.session_state.agenda_data_ref = st.session_state.agenda_data_ref + timedelta(days=1)
            st.rerun()

    view = st.radio("Visualização", ["Diária", "Semanal"], horizontal=True)

    df_ag = carregar_agendamentos()
    if df_ag.empty:
        st.info("Nenum agendamento encontrado.")
    else:
        if "Data" in df_ag.columns:
            df_ag["Data_dt"] = pd.to_datetime(df_ag["Data"]).dt.date
        else:
            df_ag["Data_dt"] = pd.NaT

        if view == "Diária":
            data_ref = st.session_state.agenda_data_ref
            st.markdown(f"#### Agenda do dia — {data_ref.strftime('%d/%m/%Y')}")
            df_dia = df_ag[df_ag["Data_dt"] == data_ref].copy()
            if df_dia.empty:
                st.write("Nenhum horário agendado para este dia.")
            else:
                df_dia = df_dia.sort_values(by="Horário")
                for _, row in df_dia.iterrows():
                    hora = _format_hora(row.get("Horário",""))
                    with st.container():
                        st.markdown(f"""
                            <div class="ui-card">
                                <div style="display:flex; justify-content:space-between; align-items:center;">
                                    <div>
                                        <div style="font-weight:800; font-size:1.05rem; color:#38bdf8;">{hora} — {row.get('Cliente','')}</div>
                                        <div style="color:#94a3b8; margin-top:6px;">Serviço: {row.get('Serviço','')} · Contato: {row.get('Contato/WhatsApp','')}</div>
                                    </div>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)

        else:
            ref = st.session_state.agenda_data_ref
            start_week = ref - timedelta(days=ref.weekday())
            days = [start_week + timedelta(days=i) for i in range(7)]
            st.markdown(f"#### Semana de {start_week.strftime('%d/%m/%Y')} a {(start_week+timedelta(days=6)).strftime('%d/%m/%Y')}")
            cols = st.columns(7)
            for i, d in enumerate(days):
                with cols[i]:
                    st.markdown(f"**{d.strftime('%a %d/%m')}**")
                    df_day = df_ag[df_ag["Data_dt"] == d].sort_values(by="Horário")
                    if df_day.empty:
                        st.write("—")
                    else:
                        for _, row in df_day.iterrows():
                            hora = _format_hora(row.get("Horário",""))
                            st.markdown(f"- **{hora}** — {row.get('Cliente','')}  \n  _{row.get('Serviço','')}_")

    st.markdown("---")
    st.markdown("#### Ações rápidas")
    a_col1, a_col2, a_col3 = st.columns([2,2,1])
    with a_col1:
        if st.button("➕ Novo Agendamento"):
            st.session_state._show_novo_agendamento = True
    with a_col2:
        if st.button("🗑️ Limpar agendamentos do dia"):
            data_ref = st.session_state.agenda_data_ref
            if not df_ag.empty:
                ids = df_ag[df_ag["Data_dt"] == data_ref]["id"].tolist()
                if ids:
                    for _id in ids:
                        deletar_agendamento(_id)
                    st.success(f"Removidos {len(ids)} agendamentos de {data_ref.strftime('%d/%m/%Y')}.")
                    st.rerun()
                else:
                    st.info("Nenhum agendamento para remover nesta data.")
            else:
                st.info("Nenhum agendamento cadastrado.")
    with a_col3:
        st.write("")

    if st.session_state.get("_show_novo_agendamento"):
        st.markdown("### Novo Agendamento")
        with st.form("form_novo_ag"):
            cliente = st.text_input("Nome do Cliente")
            contato = st.text_input("Contato / WhatsApp")
            servicos = list(carregar_servicos().keys())
            serv = st.selectbox("Serviço", ["Selecione"] + servicos)
            data_n = st.date_input("Data", value=st.session_state.agenda_data_ref)
            hora_n = st.text_input("Horário (HH:MM)", value="09:00")
            submitted = st.form_submit_button("Salvar Agendamento", type="primary")
            if submitted:
                if cliente and serv != "Selecione":
                    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
                    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                        conn.execute(text("INSERT INTO agendamentos (usuario_id, cliente_nome, cliente_contato, servico_nome, data, hora) VALUES (:user, :cliente, :contato, :serv, :data, :hora)"),
                                     {"user": usuario, "cliente": cliente.strip(), "contato": contato.strip(), "serv": serv, "data": data_n.strftime('%Y-%m-%d'), "hora": hora_n})
                    st.session_state._show_novo_agendamento = False
                    st.success("Agendamento salvo.")
                    st.rerun()
                else:
                    st.error("Preencha o nome do cliente e selecione um serviço.")

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

    st.markdown(f'<div style="text-align: center; margin-bottom: 20px;"><h1 style="margin: 0; color: #ffffff;">✂️ {nome_salao_formatado}</h1><p style="color: #38bdf8 !important; font-weight: 600; margin-top: 5px;">Agendamento Online Rápido e Simples</p></div>', unsafe_allow_html=True)

    if st.session_state.get("agendamento_sucesso"):
        dados_ag = st.session_state.agendamento_sucesso
        st.success(f"🎉 Agendado com sucesso para {dados_ag['nome']} às {dados_ag['hora']} dia {dados_ag['data_formatada']}!")
        st.balloons()

        wa_dono_clean = re.sub(r'\D', '', str(dados_ag.get("wa_dono", "")))
        if wa_dono_clean:
            if not wa_dono_clean.startswith('55') and len(wa_dono_clean) <= 11:
                wa_dono_clean = '55' + wa_dono_clean
            
            msg_wa = urllib.parse.quote(
                f"Olá! Acabei de realizar um agendamento pelo site:\n\n"
                f"👤 *Cliente:* {dados_ag['nome']}\n"
                f"📱 *Contato:* {dados_ag['contato']}\n"
                f"✂️ *Serviço:* {dados_ag['servico']}\n"
                f"📅 *Data:* {dados_ag['data_formatada']}\n"
                f"⏰ *Horário:* {dados_ag['hora']}"
            )
            link_wa_dono = f"https://api.whatsapp.com/send?phone={wa_dono_clean}&text={msg_wa}"
            
            st.markdown(f'''
                <a href="{link_wa_dono}" target="_blank" style="display:flex; align-items:center; justify-content:center; gap:10px; width:100%; text-align:center; background-color:#22c55e; color:#ffffff; padding:1rem; border-radius:12px; text-decoration:none; font-weight:800; font-size:1.1rem; margin-top:15px; margin-bottom:15px; box-shadow: 0 4px 15px rgba(34, 197, 94, 0.4);">
                    <svg viewBox="0 0 32 32" width="24" height="24" fill="white" xmlns="http://www.w3.org/2000/svg"><path d="M16 2a13 13 0 0 0-10.85 20.24L3.6 28.5l6.43-1.5A13 13 0 1 0 16 2zm0 24a10.9 10.9 0 0 1-5.54-1.5l-.4-.24-4.14 1 .97-4.04-.26-.4A11 11 0 1 1 16 26zm6-8.2c-.33-.16-1.95-.96-2.25-1.07-.3-.1-.52-.16-.74.17-.22.33-.85 1.07-1.04 1.28-.2.22-.39.25-.72.09-.33-.16-1.4-.52-2.65-1.64-1-1-1.68-2.22-1.88-2.55-.2-.33-.02-.51.15-.67.15-.15.33-.39.5-.59.16-.2.22-.33.32-.55.1-.22.05-.42-.03-.58-.08-.16-.74-1.78-1-2.43-.27-.64-.53-.55-.74-.56h-.63c-.22 0-.58.08-.88.42-.3.33-1.15 1.12-1.15 2.73s1.18 3.16 1.34 3.37c.16.22 2.3 3.51 5.56 4.92 2.22.95 3.02 1.02 4.1 1.02s1.95-.8 2.25-1.57c.3-.77.3-1.43.22-1.57-.1-.13-.33-.2-.66-.36z"/></svg>
                    Confirmar e Enviar no WhatsApp do Salão
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
                
                st.session_state.agendamento_sucesso = {
                    "nome": nome_cliente.strip(),
                    "contato": telefone_cliente.strip(),
                    "servico": servico_escolhido,
                    "hora": horario_escolhido,
                    "data_formatada": data_formatada,
                    "wa_dono": wa_dono
                }
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
            st.markdown(f'<a href="https://api.whatsapp.com/send?phone={support_phone}&text={wa_login_msg}" target="_blank" style="display: flex; align-items: center; justify-content: center; gap: 8px; background-color: #22c55e; color: white; padding: 10px; border-radius: 12px; text-decoration: none; font-weight: bold; height: 46px;"><svg viewBox="0 0 32 32" width="20" height="20" fill="white" xmlns="http://www.w3.org/2000/svg"><path d="M16 2a13 13 0 0 0-10.85 20.24L3.6 28.5l6.43-1.5A13 13 0 1 0 16 2zm0 24a10.9 10.9 0 0 1-5.54-1.5l-.4-.24-4.14 1 .97-4.04-.26-.4A11 11 0 1 1 16 26zm6-8.2c-.33-.16-1.95-.96-2.25-1.07-.3-.1-.52-.16-.74.17-.22.33-.85 1.07-1.04 1.28-.2.22-.39.25-.72.09-.33-.16-1.4-.52-2.65-1.64-1-1-1.68-2.22-1.88-2.55-.2-.33-.02-.51.15-.67.15-.15.33-.39.5-.59.16-.2.22-.33.32-.55.1-.22.05-.42-.03-.58-.08-.16-.74-1.78-1-2.43-.27-.64-.53-.55-.74-.56h-.63c-.22 0-.58.08-.88.42-.3.33-1.15 1.12-1.15 2.73s1.18 3.16 1.34 3.37c.16.22 2.3 3.51 5.56 4.92 2.22.95 3.02 1.02 4.1 1.02s1.95-.8 2.25-1.57c.3-.77.3-1.43.22-1.57-.1-.13-.33-.2-.66-.36z"/></svg>Suporte</a>', unsafe_allow_html=True)
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
        st.markdown("Acompanhe o status das assinaturas, verifique quem está em dia ou vencido, e bloqueie ou desbloqueie acessos automaticamente ou manualmente.")

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

                cor_status = "#22c55e" if (status_atual == "Ativo" and not esta_vencido) else "#ef4444"
                texto_status = "Em Dia (Ativo)" if (status_atual == "Ativo" and not esta_vencido) else "Vencido / Bloqueado"

                with st.container():
                    c_info, c_venc, c_status_lbl, c_btn = st.columns([2.5, 1.5, 2, 2])
                    with c_info:
                        st.markdown(f"**👤 Salão:** `{u_id}`<br><span style='color: #94a3b8; font-size: 0.85rem;'>{u_info.get('email', 'Sem e-mail')}</span>", unsafe_allow_html=True)
                    with c_venc:
                        st.markdown(f"**Vencimento:**<br>{dt_venc.strftime('%d/%m/%Y')}", unsafe_allow_html=True)
                    with c_status_lbl:
                        st.markdown(f"**Status:**<br><span style='color: {cor_status}; font-weight: bold;'>● {texto_status}</span>", unsafe_allow_html=True)
                    with c_btn:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if status_atual == "Ativo" and not esta_vencido:
                            if st.button("🔒 Bloquear Acesso", key=f"bloquear_{u_id}", use_container_width=True):
                                usuarios_cadastrados[u_id]["status"] = "Suspenso"
                                salvar_usuarios(usuarios_cadastrados)
                                st.success(f"Acesso de {u_id} bloqueado!")
                                st.rerun()
                        else:
                            if st.button("🔓 Desbloquear / Renovar", key=f"desbloquear_{u_id}", type="primary", use_container_width=True):
                                novo_venc_renovado = (data_hoje + timedelta(days=30)).strftime("%Y-%m-%d")
                                usuarios_cadastrados[u_id]["status"] = "Ativo"
                                usuarios_cadastrados[u_id]["vencimento"] = novo_venc_renovado
                                salvar_usuarios(usuarios_cadastrados)
                                st.success(f"Acesso de {u_id} desbloqueado e renovado!")
                                st.rerun()
                    st.markdown("<hr style='margin: 10px 0; border-color: #1e293b;'>", unsafe_allow_html=True)
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
# PAINEL PRINCIPAL DO SALÃO (USUÁRIO LOGADO)
# ==============================================================================
df_fluxo_caixa = carregar_fluxo()
servicos = carregar_servicos()
_, _, url_sistema_salva = carregar_admin_hashes()

hoje = pd.Timestamp(datetime.now(TZ).date())
mes_atual = hoje.month
ano_atual = hoje.year

base_url = RENDER_BASE_URL.rstrip('/')
link_clientes = f"{base_url}/?salao={st.session_state.usuario_logado}"
nome_salao_titulo = st.session_state.usuario_logado.replace('_', ' ').replace('-', ' ').title()
wa_url_geral = f"https://api.whatsapp.com/send?text={urllib.parse.quote(f'Olá! 👋 Agende seu horário no *{nome_salao_titulo}* de forma prática: {link_clientes}')}"

col_top_left, _ = st.columns([1, 4])
with col_top_left:
    with st.popover("⚙️ Configurações", use_container_width=False):
        st.subheader("⚙️ Configurar Salão")
        st.markdown("---")
        opcoes_gerenciamento_pop = ["➕ Cadastrar Novo Serviço"] + list(servicos.keys())
        servico_sel_pop = st.selectbox("Ação / Serviço:", opcoes_gerenciamento_pop, key="top_select_servico")
        nome_p_pop = "" if servico_sel_pop == "➕ Cadastrar Novo Serviço" else servico_sel_pop
        preco_p_pop = Decimal("0.00") if servico_sel_pop == "➕ Cadastrar Novo Serviço" else Decimal(str(servicos[servico_sel_pop]))
        novo_servico_pop = st.text_input("Nome do Serviço:", value=nome_p_pop, key=f"top_nome_{servico_sel_pop}")
        novo_preco_pop = Decimal(str(st.number_input("Valor do Serviço (R$):", min_value=0.0, value=float(preco_p_pop), step=5.0, key=f"top_prc_{servico_sel_pop}")))

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
        renderizar_botao_download_apk(gerar_backup_json_completo().encode('utf-8'), f"backup_{st.session_state.usuario_logado}_{datetime.now(TZ).strftime('%d_%m_%Y')}.json", "application/json", "📥 Baixar Backup JSON")
        st.markdown("---")
        if st.button("🚪 Sair do Sistema", use_container_width=True, type="secondary", key="top_logout_btn"):
            st.session_state.clear()
            if "token_sessao" in st.query_params:
                del st.query_params["token_sessao"]
            st.rerun()

st.markdown(f'<div style="display: flex; justify-content: space-between; align-items: center; padding: 15px 25px; margin-bottom: 20px;"><div><h2 style="margin: 0; color: #ffffff;">✂️ {nome_salao_titulo}</h2><p style="margin: 0; color: #38bdf8 !important; font-size: 0.9rem;">Painel de Controle Financeiro & Agendamentos</p></div></div>', unsafe_allow_html=True)

# ==============================================================================
# FUNÇÕES DE DIÁLOGO (MODAIS PARA AÇÕES RÁPIDAS)
# ==============================================================================

@st.dialog("✂️ Registrar Novo Atendimento")
def dialog_novo_atendimento(servicos_dict):
    if list(servicos_dict.keys()):
        servico_selecionado = st.selectbox("Serviço Realizado:", list(servicos_dict.keys()), key="f_atend_serv_modal")
        preco_padrao = float(servicos_dict[servico_selecionado])
        preco_input = st.number_input("Valor Recebido (R$):", value=preco_padrao, step=1.0, key=f"prc_atend_din_{servico_selecionado}_modal")
        preco_final = Decimal(str(preco_input))
        data_entrada = st.date_input("Data do Atendimento:", datetime.now(TZ).date(), key="f_atend_dt_modal")
        if st.button("Confirmar Entrada", type="primary", icon=":material/check_circle:", use_container_width=True):
            inserir_movimentacao_direta("Entrada", f"Atendimento: {servico_selecionado}", preco_final, data_entrada)
            st.success("Atendimento registrado no caixa!")
            st.rerun()

@st.dialog("🛍️ Registrar Nova Despesa")
def dialog_nova_despesa():
    descricao_saida = st.text_input("Descrição da Despesa:", key="f_venda_desc_modal", placeholder="Ex: Produto de limpeza, conta de luz...")
    valor_input = st.number_input("Valor Pago (R$):", min_value=0.0, step=5.0, key="f_venda_val_modal")
    valor_saida = Decimal(str(valor_input))
    data_saida = st.date_input("Data do Pagamento:", datetime.now(TZ).date(), key="f_venda_dt_modal")
    if st.button("Lançar Saída", type="primary", icon=":material/remove_circle:", use_container_width=True):
        if descricao_saida and valor_saida > Decimal("0.00"):
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
        preco_padrao = float(servicos_dict[servico_pendente])
        preco_input = st.number_input("Valor a Pagar (R$):", value=preco_padrao, key=f"prc_fiado_din_{servico_pendente}_modal")
        preco_final_p = Decimal(str(preco_input))
        data_pendencia = st.date_input("Data do Serviço:", datetime.now(TZ).date(), key="f_fiado_dt_modal")
        if st.button("Anotar Pendência", type="primary", icon=":material/warning:", use_container_width=True):
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
        opcoes_pendentes = {f"{row['Descrição']} - R$ {abs(Decimal(str(row['Valor']))):.2f}": row['id'] for _, row in df_pendencias.iterrows()}
        pendencia_selecionada = st.selectbox("Selecione o Fiado a Baixar:", list(opcoes_pendentes.keys()), key="f_pago_sel_modal")
        if st.button("Confirmar Recebimento", type="primary", icon=":material/payments:", use_container_width=True):
            id_alterar = opcoes_pendentes[pendencia_selecionada]
            row_atual = df_pendencias[df_pendencias['id'] == id_alterar].iloc[0]
            nova_desc = row_atual['Descrição'].replace("Fiado de:", "Recebido Fiado:") + " [PAGO]"
            dar_baixa_fiado_direta(id_alterar, nova_desc)
            st.success("Pagamento registrado no caixa!")
            st.rerun()
    else:
        st.info("Nenhum fiado pendente no momento.")

# ==============================================================================
# ABAS ATUALIZADAS
# ==============================================================================
tab_inicio, tab_dashboard, tab_servicos, tab_mensais, tab_agend, tab_historico = st.tabs([
    "🏠 Início", 
    "📊 Dashboard", 
    "🚀 Serviços", 
    "👥 Clientes Mensais", 
    "📅 Agendamentos", 
    "💸 Fluxo de Caixa"
])

# ==============================================================================
# TAB 0: TELA INICIAL DE BOAS-VINDAS
# ==============================================================================
with tab_inicio:
    try:
        render_tela_inicial()
    except Exception as e:
        st.error(f"Erro ao renderizar Tela Inicial: {e}")

# ==============================================================================
# TAB 1: DASHBOARD PREMIUM
# ==============================================================================
with tab_dashboard:
    st.title("📊 Dashboard Premium")

    # Cálculos Dinâmicos com base nos dados do banco
    df_fluxo = carregar_fluxo()
    df_agendamentos = carregar_agendamentos()

    # Data de Referência
    dt_hoje = datetime.now(TZ).date()
    dt_ontem = dt_hoje - timedelta(days=1)
    mes_atual_str = dt_hoje.strftime("%Y-%m")
    
    # Cálculo mês anterior
    primeiro_dia_mes_atual = dt_hoje.replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
    mes_anterior_str = ultimo_dia_mes_anterior.strftime("%Y-%m")

    # Inicialização das variáveis
    rec_dia_atual = Decimal("0.00")
    rec_dia_anterior = Decimal("0.00")
    rec_mes_atual = Decimal("0.00")
    rec_mes_anterior = Decimal("0.00")
    ticket_medio = Decimal("0.00")
    total_clientes_ativos = 0

    if not df_fluxo.empty:
        df_fluxo_calc = df_fluxo.copy()
        df_fluxo_calc['Data_dt'] = pd.to_datetime(df_fluxo_calc['Data']).dt.date
        df_fluxo_calc['Mes_str'] = pd.to_datetime(df_fluxo_calc['Data']).dt.strftime("%Y-%m")
        
        # Filtra apenas entradas/receitas
        entradas = df_fluxo_calc[df_fluxo_calc['Tipo'] == 'Entrada']
        
        # Receita Hoje e Ontem
        rec_dia_atual = sum(entradas[entradas['Data_dt'] == dt_hoje]['Valor'], Decimal("0.00"))
        rec_dia_anterior = sum(entradas[entradas['Data_dt'] == dt_ontem]['Valor'], Decimal("0.00"))
        
        # Receita Mês Atual e Mês Anterior
        rec_mes_atual = sum(entradas[entradas['Mes_str'] == mes_atual_str]['Valor'], Decimal("0.00"))
        rec_mes_anterior = sum(entradas[entradas['Mes_str'] == mes_anterior_str]['Valor'], Decimal("0.00"))
        
        # Ticket Médio Mês Atual
        qtd_atendimentos = len(entradas[entradas['Mes_str'] == mes_atual_str])
        ticket_medio = (rec_mes_atual / Decimal(str(qtd_atendimentos))) if qtd_atendimentos > 0 else Decimal("0.00")

    # Clientes Ativos (Base de dados de Clientes Mensais)
    df_cli_m = carregar_clientes_mensais_banco()
    total_clientes_ativos = len(df_cli_m) if not df_cli_m.empty else 0

    # Variações Porcentuais
    perc_dia = Decimal(str(((rec_dia_atual - rec_dia_anterior) / rec_dia_anterior * Decimal("100.00")))) if rec_dia_anterior > Decimal("0.00") else Decimal("0.00")
    perc_mes = Decimal(str(((rec_mes_atual - rec_mes_anterior) / rec_mes_anterior * Decimal("100.00")))) if rec_mes_anterior > Decimal("0.00") else Decimal("0.00")

    # KPIs principais em cards modernos
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        txt_perc_dia = f"▲ +{perc_dia:.0f}%" if perc_dia >= Decimal("0.00") else f"▼ {perc_dia:.0f}%"
        cls_perc_dia = "perc-up" if perc_dia >= Decimal("0.00") else "perc-down"
        st.markdown(f'<div class="kpi-card-v2"><div class="kpi-title-v2">Receita do Dia</div><div class="kpi-value-v2 kpi-val-green">R$ {rec_dia_atual:,.2f}</div><div class="kpi-perc {cls_perc_dia}">{txt_perc_dia}</div></div>', unsafe_allow_html=True)
    with col2:
        txt_perc_mes = f"▲ +{perc_mes:.0f}%" if perc_mes >= Decimal("0.00") else f"▼ {perc_mes:.0f}%"
        cls_perc_mes = "perc-up" if perc_mes >= Decimal("0.00") else "perc-down"
        st.markdown(f'<div class="kpi-card-v2"><div class="kpi-title-v2">Receita do Mês</div><div class="kpi-value-v2 kpi-val-blue">R$ {rec_mes_atual:,.2f}</div><div class="kpi-perc {cls_perc_mes}">{txt_perc_mes}</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="kpi-card-v2"><div class="kpi-title-v2">Ticket Médio</div><div class="kpi-value-v2">R$ {ticket_medio:,.2f}</div><div class="kpi-perc perc-neutral">≈ estável</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="kpi-card-v2"><div class="kpi-title-v2">Clientes Ativos</div><div class="kpi-value-v2">{total_clientes_ativos}</div><div class="kpi-perc perc-up">▲ Ativos</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Gráfico de evolução mensal da receita
    if not df_fluxo.empty:
        df_entradas_grafico = df_fluxo[df_fluxo['Tipo'] == 'Entrada'].copy()
        if not df_entradas_grafico.empty:
            df_entradas_grafico['Valor_Float'] = df_entradas_grafico['Valor'].astype(float)
            receita_mensal = df_entradas_grafico.groupby(df_entradas_grafico['Data'].dt.to_period("M"))['Valor_Float'].sum().reset_index()
            receita_mensal['Data'] = receita_mensal['Data'].dt.strftime('%b/%Y')
            fig = px.line(receita_mensal, x="Data", y="Valor_Float", markers=True,
                          title="📈 Evolução da Receita Mensal",
                          color_discrete_sequence=["#38bdf8"],
                          labels={"Valor_Float": "Valor (R$)"})
            fig.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Ainda não há receitas registradas para exibir a evolução mensal.")
    else:
        st.info("Nenhuma movimentação registrada no caixa.")

    # Ranking de serviços mais vendidos
    df_servicos = carregar_agendamentos()
    if not df_servicos.empty and 'Serviço' in df_servicos.columns:
        ranking_servicos = df_servicos['Serviço'].value_counts().reset_index()
        ranking_servicos.columns = ['Serviço', 'Quantidade']
        fig2 = px.bar(ranking_servicos, x="Quantidade", y="Serviço", orientation="h",
                      title="💇 Serviços Mais Vendidos",
                      color="Quantidade", color_continuous_scale="Blues")
        fig2.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Sem dados de agendamentos para exibir o ranking de serviços.")

    # Barra de progresso da meta mensal
    meta_mensal = Decimal("15000.00")
    progresso_meta = float(min(Decimal("1.00"), rec_mes_atual / meta_mensal)) if meta_mensal > Decimal("0.00") else 0.0
    st.markdown(f"#### 🎯 Meta do Mês: R$ {rec_mes_atual:,.2f} / R$ {meta_mensal:,.2f}")
    st.progress(progresso_meta)

# ==============================================================================
# TAB 2: SERVIÇOS
# ==============================================================================
with tab_servicos:
    st.markdown("### 🚀 Ações Rápidas & Catálogo de Serviços")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("✂️ Novo Atendimento", use_container_width=True, type="primary"):
            dialog_novo_atendimento(servicos)
    with c2:
        if st.button("🛍️ Nova Despesa", use_container_width=True):
            dialog_nova_despesa()
    with c3:
        if st.button("💰 Anotar Fiado", use_container_width=True):
            dialog_anotar_fiado(servicos)
    with c4:
        if st.button("💸 Dar Baixa Fiado", use_container_width=True):
            dialog_baixar_fiado(df_fluxo_caixa)

    st.markdown("---")
    st.markdown("#### 📋 Serviços Cadastrados")
    if servicos:
        df_serv = pd.DataFrame([{"Serviço": k, "Preço (R$)": f"R$ {v:.2f}"} for k, v in servicos.items()])
        st.dataframe(df_serv, use_container_width=True)
    else:
        st.info("Nenhum serviço cadastrado.")

# ==============================================================================
# TAB 3: CLIENTES MENSAIS
# ==============================================================================
with tab_mensais:
    try:
        render_clientes_mensais()
    except Exception as e:
        st.error(f"Erro ao renderizar Clientes Mensais: {e}")

# ==============================================================================
# TAB 4: AGENDAMENTOS
# ==============================================================================
with tab_agend:
    try:
        render_agenda_painel()
    except Exception as e:
        st.error(f"Erro ao renderizar Agenda: {e}")

# ==============================================================================
# TAB 5: FLUXO DE CAIXA (HISTÓRICO)
# ==============================================================================
with tab_historico:
    try:
        render_financeiro_painel()
    except Exception as e:
        st.error(f"Erro ao renderizar Financeiro: {e}")

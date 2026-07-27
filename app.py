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
SALT = "salao_fio_caixa_2026_security"
TZ = ZoneInfo("America/Sao_Paulo")

def hash_password(password):
    return hashlib.sha256((password + SALT).encode()).hexdigest()

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Fio&Caixa - Gestão & Agendamento", layout="wide", page_icon="✂️")

# --- DESIGN & CSS ULTRA PREMIUM ---
def set_background_com_logo(image_path):
    encoded_string = ""
    if os.path.exists(image_path):
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        bg_style = f'background-image: linear-gradient(180deg, rgba(30, 5, 8, 0.85) 0%, rgba(10, 13, 18, 0.96) 100%), url("data:image/png;base64,{encoded_string}") !important;'
    else:
        bg_style = 'background: radial-gradient(circle at top, #2b080c 0%, #0d1117 60%, #080a0f 100%) !important;'

    st.markdown(
        f"""
        <style>
        .stApp {{
            {bg_style}
            background-size: cover !important;
            background-position: center !important;
            background-attachment: fixed !important;
            color: #f0f6fc !important;
        }}

        html, body, p, span, label, div, [class*="css"] {{
            color: #f0f6fc !important;
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
        }}

        h1, h2, h3, h4, h5, h6 {{
            color: #ffffff !important;
            font-weight: 700 !important;
            letter-spacing: -0.5px;
        }}

        input[type="text"], input[type="password"], input[type="number"], textarea, 
        div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {{
            background-color: #0b1017 !important;
            color: #ffffff !important;
            border: 1.5px solid #222e3e !important;
            border-radius: 12px !important;
            padding: 12px 14px !important;
            font-size: 1rem !important;
            transition: all 0.2s ease-in-out !important;
        }}
        
        input:focus, div[data-baseweb="input"] > div:focus-within {{
            border-color: #00a8ff !important;
            box-shadow: 0 0 10px rgba(0, 168, 255, 0.25) !important;
        }}

        button[data-testid="stNumberInputStepDown"], button[data-testid="stNumberInputStepUp"] {{
            background-color: #1a2332 !important;
            color: #ffffff !important;
            border: 1px solid #222e3e !important;
        }}
        button[data-testid="stNumberInputStepDown"]:hover, button[data-testid="stNumberInputStepUp"]:hover {{
            background-color: #243044 !important;
            color: #00a8ff !important;
        }}

        div[data-baseweb="popover"], div[data-baseweb="calendar"], div[role="dialog"] {{
            background-color: #0b1017 !important;
            border: 1px solid #222e3e !important;
            border-radius: 12px !important;
            color: #ffffff !important;
            box-shadow: 0 10px 30px rgba(0,0,0,0.8) !important;
        }}

        div[data-baseweb="calendar"] * {{
            color: #ffffff !important;
            background-color: transparent !important;
        }}
        div[data-baseweb="calendar"] header {{
            background-color: #0b1017 !important;
        }}
        div[data-baseweb="calendar"] button {{
            color: #ffffff !important;
            background-color: transparent !important;
            border-radius: 8px !important;
        }}
        div[data-baseweb="calendar"] button:hover {{
            background-color: #1a2332 !important;
            color: #00a8ff !important;
        }}
        div[data-baseweb="calendar"] [aria-selected="true"] {{
            background-color: #00a8ff !important;
            color: #ffffff !important;
            font-weight: bold !important;
            border-radius: 50% !important;
        }}

        div[data-baseweb="menu"], ul[data-baseweb="menu"], [data-baseweb="popover"] ul {{
            background-color: #0b1017 !important;
            border: 1px solid #222e3e !important;
            border-radius: 8px !important;
        }}
        li[data-baseweb="option"], [data-baseweb="menu"] li, [role="option"] {{
            background-color: #0b1017 !important;
            color: #ffffff !important;
            padding: 10px 14px !important;
        }}
        li[data-baseweb="option"]:hover, [data-baseweb="menu"] li:hover, [role="option"]:hover {{
            background-color: #1a2332 !important;
            color: #00a8ff !important;
        }}

        [data-testid="stRadio"] label, [data-testid="stCheckbox"] label, [data-testid="stWidgetLabel"] p {{
            color: #cbd5e1 !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
            margin-bottom: 4px !important;
        }}

        .login-card {{
            background: #111823;
            border: 1px solid #1f2937;
            border-radius: 20px;
            padding: 40px 32px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.75);
            max-width: 460px;
            margin: 0 auto;
        }}

        .login-tag {{
            color: #00a8ff !important;
            font-size: 0.8rem;
            font-weight: 800;
            letter-spacing: 1.8px;
            text-transform: uppercase;
            margin-bottom: 8px;
            display: block;
        }}

        .login-title {{
            color: #ffffff !important;
            font-size: 2.2rem;
            font-weight: 800;
            margin-bottom: 8px;
            line-height: 1.1;
        }}

        .login-subtitle {{
            color: #94a3b8 !important;
            font-size: 0.95rem;
            margin-bottom: 28px;
            line-height: 1.4;
        }}

        .ui-card {{
            background: #111823;
            border: 1px solid #1f2937;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        }}

        .ui-card-highlight {{
            background: linear-gradient(145deg, #111823 0%, #172233 100%);
            border: 1px solid #00a8ff;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 0 20px rgba(0, 168, 255, 0.15);
        }}

        .kpi-card {{
            background-color: #111823;
            border: 1px solid #1f2937;
            border-top: 4px solid #00E676;
            border-radius: 14px;
            padding: 18px;
            text-align: center;
            box-shadow: 0 6px 16px rgba(0,0,0,0.4);
        }}
        .kpi-card-expense {{ border-top-color: #FF5252 !important; }}
        .kpi-card-neutral {{ border-top-color: #00a8ff !important; }}

        .kpi-title {{
            font-size: 0.82rem;
            color: #94a3b8 !important;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            font-weight: 700;
        }}
        .kpi-value {{
            font-size: 1.8rem;
            font-weight: 800;
            color: #ffffff !important;
            margin-top: 6px;
        }}

        .stButton > button, 
        .stDownloadButton > button, 
        div[data-testid="stDownloadButton"] > button {{
            background-color: #1a2332 !important;
            color: #ffffff !important;
            border: 1px solid #2a364f !important;
            border-radius: 12px !important;
            font-weight: 700 !important;
            padding: 12px 20px !important;
            transition: all 0.2s ease !important;
            width: 100% !important;
        }}

        .stButton > button:hover, 
        .stDownloadButton > button:hover, 
        div[data-testid="stDownloadButton"] > button:hover {{
            background-color: #243044 !important;
            border-color: #00a8ff !important;
            color: #00a8ff !important;
            box-shadow: 0 0 12px rgba(0, 168, 255, 0.3) !important;
        }}

        .stButton > button[kind="primary"], 
        .stDownloadButton > button[kind="primary"], 
        div[data-testid="stDownloadButton"] > button[kind="primary"] {{
            background: linear-gradient(135deg, #00a8ff 0%, #0077ff 100%) !important;
            color: #ffffff !important;
            border: none !important;
            box-shadow: 0 6px 20px rgba(0, 168, 255, 0.35) !important;
        }}

        .stButton > button[kind="primary"]:hover, 
        .stDownloadButton > button[kind="primary"]:hover, 
        div[data-testid="stDownloadButton"] > button[kind="primary"]:hover {{
            background: linear-gradient(135deg, #1ab0ff 0%, #1a85ff 100%) !important;
            box-shadow: 0 8px 25px rgba(0, 168, 255, 0.5) !important;
            color: #ffffff !important;
        }}

        [data-testid="stDataFrame"] {{
            background-color: #111823 !important;
            border: 1px solid #1f2937 !important;
            border-radius: 12px !important;
            padding: 8px !important;
        }}

        [data-testid="stSidebar"] {{
            background-color: #0e141d !important;
            border-right: 1px solid #1f2937 !important;
        }}
        
        .stTabs [data-baseweb="tab-list"] {{
            gap: 10px;
            background-color: transparent;
        }}
        .stTabs [data-baseweb="tab"] {{
            background-color: #111823;
            border-radius: 10px 10px 0 0;
            border: 1px solid #1f2937;
            border-bottom: none;
            padding: 12px 24px;
            color: #94a3b8 !important;
        }}
        .stTabs [aria-selected="true"] {{
            background-color: #1a2332 !important;
            color: #00a8ff !important;
            font-weight: bold;
            border-top: 3px solid #00a8ff !important;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

set_background_com_logo("logo.png")

# Oculta menus padrão do Streamlit
st.markdown("""
    <style>
        footer, [data-testid="stFooter"], .stFooter, 
        #MainMenu, [data-testid="stToolbar"], [data-testid="stDecoration"], .stDeployButton {
            display: none !important;
        }
        [data-testid="collapsedControl"] {
            display: flex !important;
            visibility: visible !important;
            position: fixed !important;
            top: 12px !important;       
            right: 15px !important;     
            left: auto !important;      
            z-index: 9999999 !important; 
            background-color: #111823 !important;
            border: 1px solid #00a8ff !important;
            border-radius: 50% !important;
            padding: 8px !important;
            width: 45px !important;
            height: 45px !important;
        }
        .main .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 2rem !important;
            max-width: 96% !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- CONEXÃO BANCO DE DADOS OTIMIZADA ---
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

# Cache do schema para rodar APENAS UMA VEZ na inicialização do servidor
@st.cache_resource
def inicializar_banco():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS admin_config (
                id INT PRIMARY KEY,
                hash1 TEXT NOT NULL,
                hash2 TEXT NOT NULL,
                url_sistema TEXT
            );
        """))
        try:
            conn.execute(text("ALTER TABLE admin_config ADD COLUMN IF NOT EXISTS url_sistema TEXT;"))
        except Exception:
            pass

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id TEXT PRIMARY KEY,
                senha TEXT NOT NULL,
                email TEXT,
                tipo TEXT,
                vencimento TEXT,
                status TEXT
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS servicos (
                id SERIAL PRIMARY KEY,
                usuario_id TEXT NOT NULL,
                nome TEXT NOT NULL,
                preco NUMERIC NOT NULL
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS fluxo_caixa (
                id SERIAL PRIMARY KEY,
                usuario_id TEXT NOT NULL,
                data TEXT NOT NULL,
                tipo TEXT NOT NULL,
                descricao TEXT NOT NULL,
                valor NUMERIC NOT NULL
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS agendamentos (
                id SERIAL PRIMARY KEY,
                usuario_id TEXT NOT NULL,
                cliente_nome TEXT NOT NULL,
                cliente_contato TEXT,
                servico_nome TEXT NOT NULL,
                data TEXT NOT NULL,
                hora TEXT NOT NULL
            );
        """))
    return True

try:
    inicializar_banco()
except Exception as e:
    st.error(f"Erro na criação de tabelas: {e}")
    st.stop()

# --- FUNÇÕES DE PERSISTÊNCIA E CACHE CIRÚRGICO ---

@st.cache_data(ttl=600)
def carregar_admin_hashes():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT hash1, hash2, url_sistema FROM admin_config WHERE id = 1")).fetchone()
            if result:
                return result[0], result[1], result[2]
    except Exception:
        pass
    return None, None, None

def salvar_admin_hashes(password1, password2, url=""):
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO admin_config (id, hash1, hash2, url_sistema)
                VALUES (1, :h1, :h2, :url)
                ON CONFLICT (id) DO UPDATE SET
                    hash1 = EXCLUDED.hash1,
                    hash2 = EXCLUDED.hash2,
                    url_sistema = EXCLUDED.url_sistema
            """), {"h1": hash_password(password1), "h2": hash_password(password2), "url": url})
        carregar_admin_hashes.clear()
    except Exception as e:
        st.error(f"Erro ao salvar configurações administrativas: {e}")

def atualizar_url_sistema(url):
    try:
        with engine.begin() as conn:
            conn.execute(text("UPDATE admin_config SET url_sistema = :url WHERE id = 1"), {"url": url})
        carregar_admin_hashes.clear()
    except Exception as e:
        st.error(f"Erro ao atualizar URL: {e}")

@st.cache_data(ttl=300)
def carregar_usuarios():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, senha, email, tipo, vencimento, status FROM usuarios"))
            rows = result.fetchall()
            if rows:
                return {row[0]: {"id": row[0], "senha": row[1], "email": row[2], "tipo": row[3], "vencimento": row[4], "status": row[5]} for row in rows}
    except Exception:
        pass
    return {}

def salvar_usuarios(usuarios_dict):
    if not usuarios_dict:
        return
    with engine.begin() as conn:
        for k, v in usuarios_dict.items():
            conn.execute(text("""
                INSERT INTO usuarios (id, senha, email, tipo, vencimento, status)
                VALUES (:id, :senha, :email, :tipo, :vencimento, :status)
                ON CONFLICT (id) DO UPDATE SET
                    senha = EXCLUDED.senha,
                    email = EXCLUDED.email,
                    tipo = EXCLUDED.tipo,
                    vencimento = EXCLUDED.vencimento,
                    status = EXCLUDED.status
            """), {
                "id": k,
                "senha": v["senha"],
                "email": v.get("email", ""),
                "tipo": v["tipo"],
                "vencimento": str(v["vencimento"]),
                "status": v["status"]
            })
    carregar_usuarios.clear()

@st.cache_data(ttl=300)
def carregar_servicos_por_salao(salao_id):
    salao_id_clean = urllib.parse.unquote(str(salao_id)).strip().lower() if salao_id else "padrao"
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT nome, preco FROM servicos WHERE usuario_id = :user"), {"user": salao_id_clean})
            rows = result.fetchall()
            if rows:
                return {row[0]: float(row[1]) for row in rows}
    except Exception:
        pass
    return {"Corte de Cabelo": 30.00, "Barba": 25.00, "Combo Cabelo e Barba": 50.00}

def carregar_servicos():
    usuario = st.session_state.usuario_logado if st.session_state.get("usuario_logado") else "padrao"
    return carregar_servicos_por_salao(usuario)

def salvar_ou_atualizar_servico(nome_antigo, nome_novo, preco):
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    with engine.begin() as conn:
        if nome_antigo and nome_antigo != "➕ Cadastrar Novo Serviço":
            conn.execute(text("""
                UPDATE servicos
                SET nome = :novo,
                    preco = :preco
                WHERE usuario_id = :user AND nome = :antigo
            """), {"novo": nome_novo, "preco": float(preco), "user": usuario, "antigo": nome_antigo})
        else:
            conn.execute(text("""
                INSERT INTO servicos (usuario_id, nome, preco)
                VALUES (:user, :nome, :preco)
            """), {"user": usuario, "nome": nome_novo, "preco": float(preco)})
    carregar_servicos_por_salao.clear()

def deletar_servico_banco(nome):
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    with engine.begin() as conn:
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
    except Exception:
        pass
    return pd.DataFrame(columns=["id", "Data", "Tipo", "Descrição", "Valor"])

def carregar_fluxo():
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    return carregar_fluxo_por_usuario(usuario)

def inserir_movimentacao_direta(tipo, descricao, valor, data_input):
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    data_str = data_input.strftime('%Y-%m-%d') if hasattr(data_input, 'strftime') else str(data_input)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO fluxo_caixa (usuario_id, data, tipo, descricao, valor)
            VALUES (:user, :data, :tipo, :descricao, :valor)
        """), {"user": usuario, "data": data_str, "tipo": tipo, "descricao": descricao, "valor": float(valor)})
    carregar_fluxo_por_usuario.clear()

def dar_baixa_fiado_direta(id_registro, nova_descricao):
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    data_hoje = datetime.now(TZ).strftime('%Y-%m-%d')
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE fluxo_caixa
            SET tipo = 'Entrada',
                data = :data,
                descricao = :desc
            WHERE id = :id AND usuario_id = :user
        """), {"data": data_hoje, "desc": nova_descricao, "id": int(id_registro), "user": usuario})
    carregar_fluxo_por_usuario.clear()

def deletar_movimentacao_fluxo(id_registro):
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM fluxo_caixa WHERE id = :id AND usuario_id = :user"), {"id": int(id_registro), "user": usuario})
    carregar_fluxo_por_usuario.clear()

@st.cache_data(ttl=60)
def carregar_agendamentos_por_usuario(usuario):
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT id, cliente_nome, cliente_contato, servico_nome, data, hora FROM agendamentos WHERE usuario_id = :user ORDER BY data ASC, hora ASC"),
                {"user": usuario}
            )
            rows = result.fetchall()
            if rows:
                return pd.DataFrame(rows, columns=["id", "Cliente", "Contato/WhatsApp", "Serviço", "Data", "Horário"])
    except Exception as e:
        st.error(f"Erro ao buscar agendamentos: {e}")
    return pd.DataFrame(columns=["id", "Cliente", "Contato/WhatsApp", "Serviço", "Data", "Horário"])

def carregar_agendamentos():
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    return carregar_agendamentos_por_usuario(usuario)

def deletar_agendamento(id_agendamento):
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM agendamentos WHERE id = :id AND usuario_id = :user"), {"id": int(id_agendamento), "user": usuario})
    carregar_agendamentos_por_usuario.clear()

def gerar_backup_json_completo():
    usuario = st.session_state.usuario_logado
    df_f = carregar_fluxo()

    if not df_f.empty:
        df_copy = df_f.copy()
        if 'Data' in df_copy.columns:
            df_copy['Data'] = df_copy['Data'].dt.strftime('%Y-%m-%d')
        fluxo_dict = df_copy.to_dict(orient="records")
    else:
        fluxo_dict = []

    def custom_serializer(obj):
        if isinstance(obj, (decimal.Decimal, float)):
            return float(obj)
        if isinstance(obj, (datetime, pd.Timestamp)):
            return obj.strftime('%Y-%m-%d')
        return str(obj)

    dados_backup = {
        "sistema": "Fio&Caixa",
        "usuario_dono": usuario,
        "data_geracao": datetime.now(TZ).strftime('%d/%m/%Y %H:%M:%S'),
        "catalogo_servicos": carregar_servicos(),
        "historico_financeiro": fluxo_dict
    }
    return json.dumps(dados_backup, indent=4, ensure_ascii=False, default=custom_serializer)

def gerar_pdf_contabilidade(df, mes_ref):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor("#00a8ff"), spaceAfter=15)
    story.append(Paragraph(f"Fio&Caixa - Relatório Contábil ({mes_ref})", title_style))

    table_data = [["Data", "Tipo", "Descrição", "Valor"]]
    for _, row in df.iterrows():
        dt_str = row['Data'].strftime('%d/%m/%Y') if hasattr(row['Data'], 'strftime') else str(row['Data'])
        table_data.append([dt_str, str(row['Tipo']), str(row['Descrição']), f"R$ {row['Valor']:.2f}"])
    t = Table(table_data, colWidths=[75, 60, 265, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#111823")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#00a8ff")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ESTADOS DE SESSÃO
if 'formulario_ativo' not in st.session_state: st.session_state.formulario_ativo = 'none'
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'usuario_logado' not in st.session_state: st.session_state.usuario_logado = None
if 'eh_admin' not in st.session_state: st.session_state.eh_admin = False
if 'recuperando_senha' not in st.session_state: st.session_state.recuperando_senha = False

# ==============================================================================
# ROTA PÚBLICA DE AGENDAMENTO CLIENTE (?salao=nome)
# ==============================================================================
query_params = st.query_params
salao_url = query_params.get("salao", None)

if salao_url:
    st.markdown("""
    <style>
        [data-testid="stSidebar"] {display: none !important;}
        [data-testid="collapsedControl"] {display: none !important;}
    </style>
    """, unsafe_allow_html=True)

    salao_id_clean = urllib.parse.unquote(str(salao_url)).strip().lower()
    nome_salao_formatado = salao_id_clean.replace('_', ' ').replace('-', ' ').title()

    HORARIOS_DISPONIVEIS = [
        "08:00", "08:30", "09:00", "09:30", "10:00", "10:30", 
        "11:00", "11:30", "13:00", "13:30", "14:00", "14:30", 
        "15:00", "15:30", "16:00", "16:30", "17:00", "17:30", "18:00"
    ]

    servicos_salao = carregar_servicos_por_salao(salao_id_clean)

    st.markdown(f"""
    <div class="ui-card-highlight" style="text-align: center; margin-bottom: 20px;">
        <h1 style="margin: 0; color: #ffffff;">✂️ {nome_salao_formatado}</h1>
        <p style="color: #00a8ff !important; font-weight: 600; margin-top: 5px;">Agendamento Online Rápido e Simples</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("form_agendamento_cliente", clear_on_submit=True):
        nome_cliente = st.text_input("Seu Nome Completo:")
        telefone_cliente = st.text_input("Seu WhatsApp (com DDD):")
        
        servico_escolhido = st.selectbox("Escolha o Serviço:", list(servicos_salao.keys())) if servicos_salao else None
        data_escolhida = st.date_input("Escolha a Data:", min_value=datetime.now(TZ).date())
        data_str = data_escolhida.strftime("%Y-%m-%d")

        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT hora FROM agendamentos WHERE usuario_id = :user AND data = :dt"), 
                    {"user": salao_id_clean, "dt": data_str}
                )
                ocupados = [r[0] for r in result.fetchall()]
        except Exception:
            ocupados = []

        horarios_livres = [h for h in HORARIOS_DISPONIVEIS if h not in ocupados]
        horario_escolhido = st.selectbox("Horário Disponível:", horarios_livres) if horarios_livres else None

        if not horarios_livres:
            st.warning("⚠️ Todos os horários estão preenchidos nesta data.")

        enviar_agendamento = st.form_submit_button("Confirmar Agendamento 🚀", type="primary", use_container_width=True)

    if enviar_agendamento:
        if not nome_cliente or not telefone_cliente:
            st.warning("⚠️ Por favor, informe seu nome e telefone.")
        elif not horario_escolhido or not servico_escolhido:
            st.error("⚠️ Selecione um horário válido.")
        else:
            try:
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO agendamentos (usuario_id, cliente_nome, cliente_contato, servico_nome, data, hora)
                        VALUES (:user, :nome, :contato, :servico, :data, :hora)
                    """), {
                        "user": salao_id_clean,
                        "nome": nome_cliente.strip(),
                        "contato": telefone_cliente.strip(),
                        "servico": servico_escolhido,
                        "data": data_str,
                        "hora": horario_escolhido
                    })
                carregar_agendamentos_por_usuario.clear()
                st.success(f"🎉 Agendado com sucesso para {nome_cliente} às {horario_escolhido}!")
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao registrar agendamento: {e}")
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
            url_padrao_app = st.text_input("URL Base do App (Ex: https://fioecaixa.streamlit.app):")
            if st.form_submit_button("Salvar Inicialização"):
                if nova_adm_pass1 and nova_adm_pass2:
                    salvar_admin_hashes(nova_adm_pass1, nova_adm_pass2, url_padrao_app.strip())
                    st.success("Administração inicializada!")
                    st.rerun()
        st.stop()

    if st.session_state.recuperando_senha:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.markdown('<span class="login-tag">RECUPERAÇÃO</span>', unsafe_allow_html=True)
        st.markdown('<h1 class="login-title">Redefinir Senha</h1>', unsafe_allow_html=True)
        st.markdown('<p class="login-subtitle">Confirme seus dados para cadastrar uma nova senha.</p>', unsafe_allow_html=True)
        
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

    # --- CARD DE LOGIN ---
    st.markdown("<br>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 2.2, 1])

    with col_l2:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.markdown('<span class="login-tag">ACESSO AO SISTEMA</span>', unsafe_allow_html=True)
        st.markdown('<h1 class="login-title">Entrar</h1>', unsafe_allow_html=True)
        st.markdown('<p class="login-subtitle">Informe seus dados para acessar o painel do seu salão.</p>', unsafe_allow_html=True)

        tipo_acesso = st.radio("Selecione o Perfil:", ["Usuário / Salão", "Administrador Mestre"], horizontal=True)

        with st.form("form_login_moderno"):
            usuario_input = st.text_input("Usuário / Login", placeholder="Digite seu usuário").strip().lower()
            senha_input = st.text_input("Senha", type="password", placeholder="Digite sua senha")
            senha2_input = st.text_input("Senha Secundária Admin", type="password", placeholder="Chave de segurança admin") if tipo_acesso == "Administrador Mestre" else ""
            
            st.markdown("<br>", unsafe_allow_html=True)
            submit_login = st.form_submit_button("Entrar", type="primary", use_container_width=True)

            if submit_login:
                if tipo_acesso == "Administrador Mestre":
                    if usuario_input == "admin" and hash_password(senha_input) == admin_hash1 and hash_password(senha2_input) == admin_hash2:
                        st.session_state.autenticado = True
                        st.session_state.usuario_logado = "Administrador"
                        st.session_state.eh_admin = True
                        st.rerun()
                    else:
                        st.error("Credenciais de administrador mestre inválidas.")
                else:
                    if usuario_input in usuarios_cadastrados and usuarios_cadastrados[usuario_input]["senha"] == hash_password(senha_input):
                        dados_user = usuarios_cadastrados[usuario_input]
                        data_venc = datetime.strptime(dados_user["vencimento"], "%Y-%m-%d").date()
                        if datetime.now(TZ).date() > data_venc or dados_user.get("status") == "Suspenso":
                            st.error("❌ Acesso bloqueado. Licença expirada ou suspensa.")
                            st.stop()
                        st.session_state.autenticado = True
                        st.session_state.usuario_logado = usuario_input
                        st.session_state.eh_admin = False
                        st.rerun()
                    else:
                        st.error("Usuário ou senha incorretos.")

        st.markdown("<hr style='border-color: #1f2937; margin: 20px 0;'>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748b !important; font-size: 0.88rem;'>Problemas para acessar?</p>", unsafe_allow_html=True)
        if st.button("Esqueci minha senha", use_container_width=True):
            st.session_state.recuperando_senha = True
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ==============================================================================
# MODO ADMINISTRADOR MESTRE
# ==============================================================================
if st.session_state.eh_admin:
    st.title("👑 Gestão Geral de Salões (Admin)")
    tab_cad, tab_ger, tab_config = st.tabs(["➕ Cadastrar / Renovar", "⚙️ Salões Cadastrados", "🔧 Configurações Mestre"])
    admin_hash1, admin_hash2, url_sistema_salva = carregar_admin_hashes()
    usuarios_cadastrados = carregar_usuarios()

    with tab_cad:
        with st.form("form_cadastro_cliente"):
            novo_usuario = st.text_input("Usuário do Salão (sem espaços):").strip().lower()
            novo_email = st.text_input("E-mail de Contato:").strip().lower()
            nova_senha = st.text_input("Senha de Acesso:", type="password").strip()
            tipo_conta = st.selectbox("Perfil:", ["Teste", "Cliente"])
            dias_validade = st.number_input("Dias de Acesso:", min_value=1, value=30)
            if st.form_submit_button("Cadastrar Salão", type="primary"):
                if novo_usuario and nova_senha and novo_email:
                    venc = (datetime.now(TZ) + timedelta(days=dias_validade)).strftime("%Y-%m-%d")
                    usuarios_cadastrados[novo_usuario] = {"senha": hash_password(nova_senha), "email": novo_email, "tipo": tipo_conta, "vencimento": venc, "status": "Ativo"}
                    salvar_usuarios(usuarios_cadastrados)
                    st.success("Salão cadastrado com sucesso!")
                    st.rerun()

    with tab_ger:
        if usuarios_cadastrados:
            salao_sel = st.selectbox("Selecione um Salão:", list(usuarios_cadastrados.keys()))
            dados = usuarios_cadastrados[salao_sel]
            with st.expander("📝 Editar Conta", expanded=True):
                e_email = st.text_input("E-mail:", value=dados.get("email", ""))
                e_senha_nova = st.text_input("Alterar Senha (opcional):", type="password")
                e_tipo = st.selectbox("Tipo:", ["Teste", "Cliente"], index=0 if dados['tipo'] == "Teste" else 1)
                e_venc = st.date_input("Vencimento:", datetime.strptime(dados['vencimento'], "%Y-%m-%d"))
                e_status = st.selectbox("Status:", ["Ativo", "Suspenso"], index=0 if dados['status'] == "Ativo" else 1)
                if st.button("Salvar Modificações"):
                    senha_f = hash_password(e_senha_nova) if e_senha_nova else dados['senha']
                    usuarios_cadastrados[salao_sel] = {"senha": senha_f, "email": e_email.strip().lower(), "tipo": e_tipo, "vencimento": e_venc.strftime("%Y-%m-%d"), "status": e_status}
                    salvar_usuarios(usuarios_cadastrados)
                    st.success("Conta atualizada!")
                    st.rerun()
            if st.checkbox(f"Confirmar exclusão de {salao_sel}"):
                if st.button("EXCLUIR PERMANENTEMENTE", type="primary"):
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": salao_sel})
                    carregar_usuarios.clear()
                    st.rerun()

    with tab_config:
        nova_url_input = st.text_input("URL Principal do Sistema:", value=url_sistema_salva if url_sistema_salva else "")
        if st.button("Salvar URL Global"):
            atualizar_url_sistema(nova_url_input.strip())
            st.success("URL Salva!")
            st.rerun()

    with st.sidebar:
        st.markdown("---")
        if st.button("🚪 Sair do Mestre", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    st.stop()

# ==============================================================================
# PAINEL PRINCIPAL DO SALÃO (USUÁRIO LOGADO)
# ==============================================================================
df_fluxo_caixa = carregar_fluxo()
servicos = carregar_servicos()
_, _, url_sistema_salva = carregar_admin_hashes()

if not df_fluxo_caixa.empty:
    hoje = pd.Timestamp(datetime.now(TZ).date())
    df_limpo = df_fluxo_caixa.dropna(subset=['Data'])
    df_diario = df_limpo[df_limpo['Data'].dt.date == hoje.date()]
    df_semanal = df_limpo[df_limpo['Data'] >= (hoje - timedelta(days=7))]
    df_mensal = df_limpo[df_limpo['Data'].dt.month == hoje.month]

    ent_dia, sai_dia = df_diario[df_diario['Tipo'] == 'Entrada']['Valor'].sum(), df_diario[df_diario['Tipo'] == 'Saída']['Valor'].sum()
    ent_sem, sai_sem = df_semanal[df_semanal['Tipo'] == 'Entrada']['Valor'].sum(), df_semanal[df_semanal['Tipo'] == 'Saída']['Valor'].sum()
    ent_mes, sai_mes = df_mensal[df_mensal['Tipo'] == 'Entrada']['Valor'].sum(), df_mensal[df_mensal['Tipo'] == 'Saída']['Valor'].sum()
    lucro_dia, lucro_sem, lucro_mes = ent_dia + sai_dia, ent_sem + sai_sem, ent_mes + sai_mes
else:
    ent_dia = sai_dia = lucro_dia = ent_sem = sai_sem = lucro_sem = ent_mes = sai_mes = lucro_mes = 0

base_url = (url_sistema_salva or "https://fioecaixa.streamlit.app").rstrip('/')
link_clientes = f"{base_url}/?salao={st.session_state.usuario_logado}"
nome_salao_titulo = st.session_state.usuario_logado.replace('_', ' ').replace('-', ' ').title()

mensagem_whatsapp = f"Olá! 👋 Agende seu horário no *{nome_salao_titulo}* de forma prática:\n👉 {link_clientes}"
wa_url_geral = f"https://api.whatsapp.com/send?text={urllib.parse.quote(mensagem_whatsapp)}"

# --- BOTÃO CONFI NO INÍCIO DO DASHBOARD (CANTO SUPERIOR ESQUERDO) ---
col_top_left, _ = st.columns([1, 4])
with col_top_left:
    with st.popover("⚙️ Confi", use_container_width=False):
        st.subheader("⚙️ Configurações do Salão")
        st.caption(f"Conectado como: **{nome_salao_titulo}**")

        st.markdown("---")
        st.markdown("#### 💈 Serviços & Atendimentos")
        st.write("Crie novos serviços, altere nomes, edite preços ou remova serviços antigos.")

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
                else:
                    st.error("Informe o nome do serviço.")

        with col_tp2:
            if servico_sel_pop != "➕ Cadastrar Novo Serviço":
                if st.button("🗑️ Excluir", use_container_width=True, key="top_del_btn"):
                    deletar_servico_banco(servico_sel_pop)
                    st.warning("Serviço excluído com sucesso!")
                    st.rerun()

        st.markdown("---")
        st.markdown("#### 📦 Backup e Dados")
        backup_dados_pop = gerar_backup_json_completo()
        st.download_button(
            label="📥 Baixar Backup JSON", 
            data=backup_dados_pop, 
            file_name=f"backup_{st.session_state.usuario_logado}_{datetime.now(TZ).strftime('%d_%m_%Y')}.json", 
            mime="application/json", 
            use_container_width=True,
            key="top_backup_btn"
        )

        st.markdown("---")
        if st.button("🚪 Sair do Sistema", use_container_width=True, type="secondary", key="top_logout_btn"):
            st.session_state.clear()
            st.rerun()

# --- CABEÇALHO DO PAINEL ---
st.markdown(f"""
<div class="ui-card-highlight" style="display: flex; justify-content: space-between; align-items: center; padding: 15px 25px; margin-bottom: 20px;">
    <div>
        <h2 style="margin: 0; color: #ffffff;">✂️ {nome_salao_titulo}</h2>
        <p style="margin: 0; color: #00a8ff !important; font-size: 0.9rem;">Painel de Controle Financeiro & Agendamentos</p>
    </div>
</div>
""", unsafe_allow_html=True)

# --- NAVEGAÇÃO POR TABS ---
tab1, tab0, tab_agend, tab2 = st.tabs(["📊 Dashboard Vivo", "🚀 Lançamentos Rápidos", "📅 Agendamentos", "📜 Histórico & Relatórios"])

# ==============================================================================
# TAB 1: DASHBOARD VIVO
# ==============================================================================
with tab1:
    st.markdown("### 📊 Visão Geral de Desempenho")
    
    c_kpi1, c_kpi2, c_kpi3, c_kpi4 = st.columns(4)
    
    with c_kpi1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Faturamento Hoje</div>
            <div class="kpi-value">R$ {ent_dia:.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    with c_kpi2:
        st.markdown(f"""
        <div class="kpi-card kpi-card-neutral">
            <div class="kpi-title">Líquido do Dia</div>
            <div class="kpi-value">R$ {lucro_dia:.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    with c_kpi3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Faturamento Semanal</div>
            <div class="kpi-value">R$ {ent_sem:.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    with c_kpi4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Faturamento Mensal</div>
            <div class="kpi-value">R$ {ent_mes:.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_chart1, col_chart2 = st.columns([1, 1])

    with col_chart1:
        st.markdown('<div class="ui-card">', unsafe_allow_html=True)
        st.markdown("#### 🎯 Distribuição Financeira (Mês Atual)")
        if ent_mes > 0 or abs(sai_mes) > 0:
            labels = ['Receitas (Entradas)', 'Despesas (Saídas)']
            valores = [ent_mes, abs(sai_mes)]
            
            fig_donut = go.Figure(data=[go.Pie(
                labels=labels, 
                values=valores, 
                hole=.6,
                marker=dict(colors=['#00E676', '#FF5252']),
                textinfo='percent+label',
                hoverinfo='value',
                textfont=dict(color='#ffffff', size=14)
            )])
            fig_donut.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#ffffff', size=13),
                showlegend=False,
                margin=dict(l=10, r=10, t=20, b=20),
                height=320
            )
            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("Sem movimentações suficientes neste mês.")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_chart2:
        st.markdown('<div class="ui-card">', unsafe_allow_html=True)
        st.markdown("#### 📈 Fluxo Diário de Caixas")
        if not df_fluxo_caixa.empty:
            df_chart = df_fluxo_caixa.copy()
            df_chart['DataStr'] = df_chart['Data'].dt.strftime('%d/%m')
            df_group = df_chart.groupby(['DataStr', 'Tipo'])['Valor'].sum().reset_index()
            
            fig_bar = px.bar(
                df_group, 
                x='DataStr', 
                y='Valor', 
                color='Tipo',
                color_discrete_map={'Entrada': '#00E676', 'Saída': '#FF5252', 'Pendência': '#FFD700'},
                barmode='group'
            )
            fig_bar.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#ffffff'),
                xaxis=dict(title='', showgrid=False, tickfont=dict(color='#ffffff')),
                yaxis=dict(title='Valor (R$)', showgrid=True, gridcolor='rgba(255,255,255,0.1)', tickfont=dict(color='#ffffff')),
                legend=dict(title='', orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color='#ffffff')),
                margin=dict(l=10, r=10, t=20, b=20),
                height=320
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Registre movimentações para ativar o histórico gráfico.")
        st.markdown('</div>', unsafe_allow_html=True)

# ==============================================================================
# TAB 0: LANÇAMENTOS RÁPIDOS
# ==============================================================================
with tab0:
    st.markdown('### 🚀 Ações Rápidas do Caixa')
    col_a, col_b, col_c, col_d = st.columns(4)

    with col_a:
        if st.button("✂️ Novo Atendimento", key="btn_atend", use_container_width=True, type="primary"):
            st.session_state.formulario_ativo = 'none' if st.session_state.formulario_ativo == 'new_atendimento' else 'new_atendimento'
            st.rerun()

    with col_b:
        if st.button("🛍️ Nova Despesa", key="btn_venda", use_container_width=True):
            st.session_state.formulario_ativo = 'none' if st.session_state.formulario_ativo == 'new_venda' else 'new_venda'
            st.rerun()

    with col_c:
        if st.button("💰 Anotar Fiado", key="btn_receber", use_container_width=True):
            st.session_state.formulario_ativo = 'none' if st.session_state.formulario_ativo == 'new_receber' else 'new_receber'
            st.rerun()

    with col_d:
        if st.button("💸 Baixar Fiado", key="btn_pagar", use_container_width=True):
            st.session_state.formulario_ativo = 'none' if st.session_state.formulario_ativo == 'new_pagar' else 'new_pagar'
            st.rerun()

    if st.session_state.formulario_ativo == 'new_atendimento':
        st.markdown('<div class="ui-card-highlight">', unsafe_allow_html=True)
        st.markdown("#### ✂️ Registrar Novo Atendimento")
        if list(servicos.keys()):
            servico_selecionado = st.selectbox("Serviço Realizado:", list(servicos.keys()), key="f_atend_serv")
            preco_final = st.number_input("Valor Recebido (R$):", value=float(servicos[servico_selecionado]), step=1.0, key=f"prc_atend_din_{servico_selecionado}")
            data_entrada = st.date_input("Data do Atendimento:", datetime.now(TZ).date(), key="f_atend_dt")
            if st.button("Confirmar Entrada 🟢", type="primary", key="f_atend_save", use_container_width=True):
                inserir_movimentacao_direta("Entrada", f"Atendimento: {servico_selecionado}", preco_final, data_entrada)
                st.session_state.formulario_ativo = 'none'
                st.success("Atendimento registrado no caixa!")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    elif st.session_state.formulario_ativo == 'new_venda':
        st.markdown('<div class="ui-card-highlight">', unsafe_allow_html=True)
        st.markdown("#### 🛍️ Registrar Nova Despesa")
        descricao_saida = st.text_input("Descrição da Despesa:", key="f_venda_desc", placeholder="Ex: Produto de limpeza, conta de luz...")
        valor_saida = st.number_input("Valor Pago (R$):", min_value=0.0, step=5.0, key="f_venda_val")
        data_saida = st.date_input("Data do Pagamento:", datetime.now(TZ).date(), key="f_venda_dt")
        if st.button("Lançar Saída 🔴", type="primary", key="f_venda_save", use_container_width=True):
            if descricao_saida and valor_saida > 0:
                inserir_movimentacao_direta("Saída", descricao_saida, -valor_saida, data_saida)
                st.session_state.formulario_ativo = 'none'
                st.success("Despesa lançada!")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    elif st.session_state.formulario_ativo == 'new_receber':
        st.markdown('<div class="ui-card-highlight">', unsafe_allow_html=True)
        st.markdown("#### 💰 Registrar Atendimento Fiado")
        if list(servicos.keys()):
            nome_devedor = st.text_input("Nome do Cliente Devedor:", key="f_fiado_nome")
            servico_pendente = st.selectbox("Serviço Realizado:", list(servicos.keys()), key="f_fiado_serv")
            preco_final_p = st.number_input("Valor a Pagar (R$):", value=float(servicos[servico_pendente]), key=f"prc_fiado_din_{servico_pendente}")
            data_pendencia = st.date_input("Data do Serviço:", datetime.now(TZ).date(), key="f_fiado_dt")
            if st.button("Anotar Pendência 🟡", type="primary", key="f_fiado_save", use_container_width=True):
                if nome_devedor:
                    inserir_movimentacao_direta("Pendência", f"Fiado de: {nome_devedor} ({servico_pendente})", preco_final_p, data_pendencia)
                    st.session_state.formulario_ativo = 'none'
                    st.success("Fiado registrado!")
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    elif st.session_state.formulario_ativo == 'new_pagar':
        st.markdown('<div class="ui-card-highlight">', unsafe_allow_html=True)
        st.markdown("#### 💸 Dar Baixa em Fiado")
        df_pendencias = df_fluxo_caixa[df_fluxo_caixa['Tipo'] == 'Pendência']
        if not df_pendencias.empty:
            opcoes_pendentes = {f"{row['Descrição']} - R$ {abs(row['Valor']):.2f}": row['id'] for _, row in df_pendencias.iterrows()}
            pendencia_selecionada = st.selectbox("Selecione o Fiado a Baixar:", list(opcoes_pendentes.keys()), key="f_pago_sel")
            if st.button("Confirmar Recebimento 💵", type="primary", key="f_pago_save", use_container_width=True):
                id_alterar = opcoes_pendentes[pendencia_selecionada]
                row_atual = df_pendencias[df_pendencias['id'] == id_alterar].iloc[0]
                nova_desc = row_atual['Descrição'].replace("Fiado de:", "Recebido Fiado:") + " [PAGO]"
                dar_baixa_fiado_direta(id_alterar, nova_desc)
                st.session_state.formulario_ativo = 'none'
                st.success("Pagamento registrado no caixa!")
                st.rerun()
        else:
            st.info("Nenhum fiado pendente no momento.")
        st.markdown('</div>', unsafe_allow_html=True)

# ==============================================================================
# TAB AGENDAMENTOS
# ==============================================================================
with tab_agend:
    st.subheader("📅 Agendamentos Confirmados")
    
    st.markdown('<div class="ui-card">', unsafe_allow_html=True)
    st.info(f"🔗 Link direto de agendamentos para clientes: **{link_clientes}**")
    st.markdown(f"""
    <a href="{wa_url_geral}" target="_blank" style="display:inline-block;width:100%;text-align:center;background-color:#00E676;color:#000;padding:0.75rem;border-radius:8px;text-decoration:none;font-weight:700;margin-bottom:10px;">
        📲 Enviar Link no WhatsApp dos Clientes
    </a>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    df_agendamentos = carregar_agendamentos()

    if not df_agendamentos.empty:
        df_display = df_agendamentos.copy()
        try:
            df_display['Data'] = pd.to_datetime(df_display['Data']).dt.strftime('%d/%m/%Y')
        except Exception:
            pass
            
        st.dataframe(df_display.drop(columns=['id'], errors='ignore'), use_container_width=True, hide_index=True)

        st.markdown('<div class="ui-card">', unsafe_allow_html=True)
        st.markdown("#### 🛠️ Gestão do Agendamento")
        opcoes_agend = {f"{row['Cliente']} - {row['Data']} às {row['Horário']} ({row['Serviço']})": row['id'] for _, row in df_agendamentos.iterrows()}
        agend_selecionado = st.selectbox("Selecione o Cliente:", list(opcoes_agend.keys()))

        id_sel = opcoes_agend[agend_selecionado]
        row_ag = df_agendamentos[df_agendamentos['id'] == id_sel].iloc[0]
        num_clean = re.sub(r'\D', '', str(row_ag['Contato/WhatsApp']))

        if num_clean:
            if not num_clean.startswith('55') and len(num_clean) <= 11:
                num_clean = '55' + num_clean
            msg_cli = urllib.parse.quote(f"Olá {row_ag['Cliente']}! Confirmando seu agendamento no {nome_salao_titulo} para {row_ag['Data']} às {row_ag['Horário']}.")
            wa_direct = f"https://api.whatsapp.com/send?phone={num_clean}&text={msg_cli}"
            
            st.markdown(f"""
            <a href="{wa_direct}" target="_blank" style="display:inline-block;width:100%;text-align:center;background-color:#00a8ff;color:white;padding:0.6rem;border-radius:8px;text-decoration:none;font-weight:700;margin-bottom:10px;">
                💬 Chamar Cliente no WhatsApp
            </a>
            """, unsafe_allow_html=True)

        if st.button("✅ Concluir / Excluir Agendamento", type="primary", use_container_width=True):
            deletar_agendamento(id_sel)
            st.success("Agendamento finalizado!")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Nenhum agendamento ativo na lista.")

# ==============================================================================
# TAB 2: HISTÓRICO & RELATÓRIOS
# ==============================================================================
with tab2:
    st.subheader("📜 Histórico Financeiro Completo")
    if not df_fluxo_caixa.empty:
        df_filtro = df_fluxo_caixa.dropna(subset=['Data']).copy()
        df_filtro['Mês/Ano'] = df_filtro['Data'].dt.strftime('%m/%Y')

        st.markdown('<div class="ui-card">', unsafe_allow_html=True)
        modo_filtro = st.radio("Filtro de Exibição:", ["Por Mês Fechado", "Por Período Customizado"], horizontal=True)
        
        if modo_filtro == "Por Mês Fechado":
            meses = sorted(df_filtro['Mês/Ano'].unique(), reverse=True)
            mes_escolhido = st.selectbox("📅 Selecione o Mês:", ["Ver Tudo"] + meses)
            df_exibicao = df_filtro[df_filtro['Mês/Ano'] == mes_escolhido] if mes_escolhido != "Ver Tudo" else df_filtro
            texto_pdf = mes_escolhido
            nome_arq = f"contabilidade_{mes_escolhido.replace('/', '_')}" if mes_escolhido != "Ver Tudo" else "contabilidade_geral"
        else:
            col_dt1, col_dt2 = st.columns(2)
            with col_dt1: dt_inicio = st.date_input("Data Inicial:", datetime.now(TZ).date() - timedelta(days=30))
            with col_dt2: dt_fim = st.date_input("Data Final:", datetime.now(TZ).date())
            df_exibicao = df_filtro[(df_filtro['Data'].dt.date >= dt_inicio) & (df_filtro['Data'].dt.date <= dt_fim)]
            texto_pdf = f"{dt_inicio.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}"
            nome_arq = f"contabilidade_{dt_inicio.strftime('%d_%m_%Y')}_a_{dt_fim.strftime('%d_%m_%Y')}"
        st.markdown('</div>', unsafe_allow_html=True)

        if not df_exibicao.empty:
            tot_ent = df_exibicao[df_exibicao['Tipo'] == 'Entrada']['Valor'].sum()
            tot_sai = abs(df_exibicao[df_exibicao['Tipo'] == 'Saída']['Valor'].sum())
            tot_liq = tot_ent - tot_sai

            st.markdown('<div class="ui-card-highlight">', unsafe_allow_html=True)
            st.markdown("#### 📊 Balanço do Período Selecionado")
            m_h1, m_h2, m_h3 = st.columns(3)
            with m_h1:
                st.markdown(f'<div class="kpi-card"><div class="kpi-title">Receita Total</div><div class="kpi-value">R$ {tot_ent:.2f}</div></div>', unsafe_allow_html=True)
            with m_h2:
                st.markdown(f'<div class="kpi-card kpi-card-expense"><div class="kpi-title">Despesas Totais</div><div class="kpi-value">R$ {tot_sai:.2f}</div></div>', unsafe_allow_html=True)
            with m_h3:
                st.markdown(f'<div class="kpi-card kpi-card-neutral"><div class="kpi-title">Resultado Líquido</div><div class="kpi-value">R$ {tot_liq:.2f}</div></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            
            col_down1, col_down2 = st.columns(2)
            with col_down1:
                st.download_button("📄 Baixar CSV Contábil", data=df_exibicao.drop(columns=['id', 'Mês/Ano'], errors='ignore').to_csv(index=False).encode('utf-8-sig'), file_name=f"{nome_arq}.csv", mime="text/csv", use_container_width=True)
            with col_down2:
                st.download_button("📕 Baixar Relatório PDF", data=gerar_pdf_contabilidade(df_exibicao.drop(columns=['id', 'Mês/Ano'], errors='ignore'), texto_pdf), file_name=f"{nome_arq}.pdf", mime="application/pdf", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

            df_vis = df_exibicao.sort_index(ascending=False).copy()
            df_vis['Data'] = df_vis['Data'].dt.strftime('%d/%m/%Y')
            df_vis = df_vis.drop(columns=['Mês/Ano', 'id'], errors='ignore')

            def colorir_linha(row):
                cols = len(row)
                if row['Tipo'] == 'Entrada':
                    return ['background-color: #0d3320; color: #00E676; font-weight: 700;'] * cols
                elif row['Tipo'] == 'Saída':
                    return ['background-color: #3d1418; color: #FF5252; font-weight: 700;'] * cols
                return ['background-color: #3d310d; color: #FFD700; font-weight: 700;'] * cols

            st.dataframe(df_vis.style.apply(colorir_linha, axis=1).format({"Valor": "R$ {:.2f}"}), use_container_width=True, hide_index=True)

            st.markdown('<div class="ui-card">', unsafe_allow_html=True)
            with st.expander("🗑️ Excluir Registro Incorreto do Caixa"):
                opcoes_del_fluxo = {
                    f"#{row['id']} - {row['Data'].strftime('%d/%m')} - {row['Tipo']}: {row['Descrição']} (R$ {row['Valor']:.2f})": row['id']
                    for _, row in df_exibicao.iterrows()
                }
                reg_selecionado = st.selectbox("Selecione o Lançamento para Excluir:", list(opcoes_del_fluxo.keys()))
                if st.button("❌ APAGAR REGISTRO", type="primary", use_container_width=True):
                    id_apagar = opcoes_del_fluxo[reg_selecionado]
                    deletar_movimentacao_fluxo(id_apagar)
                    st.warning("Registro excluído!")
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("Nenhum registro no período selecionado.")
    else:
        st.info("Histórico de caixa vazio.")

# ==============================================================================
# MENU LATERAL (CONFIGURAÇÕES DO SISTEMA & GERENCIAMENTO DE SERVIÇOS)
# ==============================================================================
with st.sidebar:
    st.title("⚙️ Configurações")
    nome_s = st.session_state.usuario_logado.title() if st.session_state.usuario_logado else "Salão"
    st.caption(f"Conectado como: **{nome_s}**")

    st.markdown("---")
    st.subheader("💈 Serviços & Atendimentos")
    st.write("Crie novos serviços, altere nomes, edite preços ou remova serviços antigos.")

    opcoes_gerenciamento = ["➕ Cadastrar Novo Serviço"] + list(servicos.keys())
    servico_sel = st.selectbox("Ação / Serviço:", opcoes_gerenciamento, key="sidebar_select_servico")
    
    nome_p = "" if servico_sel == "➕ Cadastrar Novo Serviço" else servico_sel
    preco_p = 0.0 if servico_sel == "➕ Cadastrar Novo Serviço" else float(servicos[servico_sel])
    
    novo_servico = st.text_input("Nome do Serviço:", value=nome_p, key=f"side_nome_{servico_sel}")
    novo_preco = st.number_input("Valor do Serviço (R$):", min_value=0.0, value=preco_p, step=5.0, key=f"side_prc_{servico_sel}")

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("💾 Salvar", type="primary", use_container_width=True, key="side_save_btn"):
            if novo_servico.strip():
                salvar_ou_atualizar_servico(servico_sel, novo_servico.strip(), novo_preco)
                st.success("Serviço atualizado com sucesso!")
                st.rerun()
            else:
                st.error("Informe o nome do serviço.")

    with col_s2:
        if servico_sel != "➕ Cadastrar Novo Serviço":
            if st.button("🗑️ Excluir", use_container_width=True, key="side_del_btn"):
                deletar_servico_banco(servico_sel)
                st.warning("Serviço excluído com sucesso!")
                st.rerun()

    st.markdown("---")
    st.subheader("📦 Backup e Dados")
    backup_dados = gerar_backup_json_completo()
    st.download_button(
        label="📥 Baixar Backup JSON", 
        data=backup_dados, 
        file_name=f"backup_{st.session_state.usuario_logado}_{datetime.now(TZ).strftime('%d_%m_%Y')}.json", 
        mime="application/json", 
        use_container_width=True
    )

    st.markdown("---")
    # BOTÃO DE SAIR ENCERRA A SESSÃO E RETORNA À TELA DE LOGIN
    if st.button("🚪 Sair do Sistema", use_container_width=True, type="secondary"):
        st.session_state.clear()
        st.rerun()

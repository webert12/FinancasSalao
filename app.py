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

# --- INICIALIZAÇÃO OBRIGATÓRIA DO SESSION STATE ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "eh_admin" not in st.session_state:
    st.session_state.eh_admin = False
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None
if "recuperando_senha" not in st.session_state:
    st.session_state.recuperando_senha = False
if "formulario_ativo" not in st.session_state:
    st.session_state.formulario_ativo = "none"

# --- OTIMIZAÇÃO DE VELOCIDADE: CACHE DA IMAGEM DE FUNDO ---
@st.cache_data
def get_image_base64(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    return ""

# --- DESIGN & CSS ULTRA PREMIUM (PRETO & DOURADO) ---
def set_background_com_logo(image_path):
    encoded_string = get_image_base64(image_path)
    if encoded_string:
        bg_style = f'background-image: linear-gradient(180deg, rgba(20, 18, 15, 0.90) 0%, rgba(10, 10, 10, 0.98) 100%), url("data:image/png;base64,{encoded_string}") !important;'
    else:
        bg_style = 'background: radial-gradient(circle at top, #1c1a17 0%, #0d0d0d 60%, #050505 100%) !important;'

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
            background-color: #0b0b0b !important;
            color: #ffffff !important;
            border: 1.5px solid #2b251a !important;
            border-radius: 12px !important;
            padding: 12px 14px !important;
            font-size: 1rem !important;
            transition: all 0.2s ease-in-out !important;
        }}
        
        input:focus, div[data-baseweb="input"] > div:focus-within {{
            border-color: #E5B80B !important;
            box-shadow: 0 0 10px rgba(229, 184, 11, 0.25) !important;
        }}

        div[data-testid="stPopover"] button,
        div[data-testid="stPopover"] button *,
        [data-testid="stPopoverButton"],
        [data-testid="stPopoverButton"] * {{
            color: #ffffff !important;
            font-weight: 800 !important;
            font-size: 0.95rem !important;
            opacity: 1 !important;
            visibility: visible !important;
        }}

        div[data-testid="stPopover"] button,
        [data-testid="stPopoverButton"] {{
            background-color: #1a1814 !important;
            border: 1.5px solid #E5B80B !important;
            border-radius: 12px !important;
            padding: 8px 18px !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
            transition: all 0.2s ease-in-out !important;
        }}

        div[data-testid="stPopover"] button:hover,
        [data-testid="stPopoverButton"]:hover {{
            background-color: #2b251a !important;
            border-color: #E5B80B !important;
            box-shadow: 0 0 15px rgba(229, 184, 11, 0.5) !important;
        }}

        div[data-testid="stPopover"] button:hover *,
        [data-testid="stPopoverButton"]:hover * {{
            color: #E5B80B !important;
        }}

        button[data-testid="stNumberInputStepDown"], button[data-testid="stNumberInputStepUp"] {{
            background-color: #1a1814 !important;
            color: #ffffff !important;
            border: 1px solid #2b251a !important;
        }}
        button[data-testid="stNumberInputStepDown"]:hover, button[data-testid="stNumberInputStepUp"]:hover {{
            background-color: #2b251a !important;
            color: #E5B80B !important;
        }}

        div[data-baseweb="popover"], div[data-baseweb="calendar"], div[role="dialog"] {{
            background-color: #0b0b0b !important;
            border: 1px solid #2b251a !important;
            border-radius: 12px !important;
            color: #ffffff !important;
            box-shadow: 0 10px 30px rgba(0,0,0,0.8) !important;
        }}

        div[data-baseweb="calendar"] * {{
            color: #ffffff !important;
            background-color: transparent !important;
        }}
        div[data-baseweb="calendar"] header {{
            background-color: #0b0b0b !important;
        }}
        div[data-baseweb="calendar"] button {{
            color: #ffffff !important;
            background-color: transparent !important;
            border-radius: 8px !important;
        }}
        div[data-baseweb="calendar"] button:hover {{
            background-color: #1a1814 !important;
            color: #E5B80B !important;
        }}
        div[data-baseweb="calendar"] [aria-selected="true"] {{
            background-color: #E5B80B !important;
            color: #000000 !important;
            font-weight: bold !important;
            border-radius: 50% !important;
        }}

        div[data-baseweb="menu"], ul[data-baseweb="menu"], [data-baseweb="popover"] ul {{
            background-color: #0b0b0b !important;
            border: 1px solid #2b251a !important;
            border-radius: 8px !important;
        }}
        li[data-baseweb="option"], [data-baseweb="menu"] li, [role="option"] {{
            background-color: #0b0b0b !important;
            color: #ffffff !important;
            padding: 10px 14px !important;
        }}
        li[data-baseweb="option"]:hover, [data-baseweb="menu"] li:hover, [role="option"]:hover {{
            background-color: #1a1814 !important;
            color: #E5B80B !important;
        }}

        [data-testid="stRadio"] label, [data-testid="stCheckbox"] label, [data-testid="stWidgetLabel"] p {{
            color: #cbd5e1 !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
            margin-bottom: 4px !important;
        }}

        .login-card {{
            background: #0d0d0d;
            border: 1px solid #221f1a;
            border-radius: 20px;
            padding: 40px 32px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.9);
            max-width: 460px;
            margin: 0 auto;
        }}

        .login-tag {{
            color: #E5B80B !important;
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
            background: #0d0d0d;
            border: 1px solid #221f1a;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        }}

        .ui-card-highlight {{
            background: linear-gradient(145deg, #0d0d0d 0%, #1a1814 100%);
            border: 1px solid #E5B80B;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 0 20px rgba(229, 184, 11, 0.15);
        }}

        .kpi-card {{
            background-color: #0d0d0d;
            border: 1px solid #221f1a;
            border-top: 4px solid #00E676;
            border-radius: 14px;
            padding: 18px;
            text-align: center;
            box-shadow: 0 6px 16px rgba(0,0,0,0.4);
        }}

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
            background-color: #1a1814 !important;
            color: #ffffff !important;
            border: 1px solid #2b251a !important;
            border-radius: 12px !important;
            font-weight: 700 !important;
            padding: 12px 20px !important;
            transition: all 0.2s ease !important;
            width: 100% !important;
        }}

        .stButton > button:hover, 
        .stDownloadButton > button:hover, 
        div[data-testid="stDownloadButton"] > button:hover {{
            background-color: #2b251a !important;
            border-color: #E5B80B !important;
            color: #E5B80B !important;
            box-shadow: 0 0 12px rgba(229, 184, 11, 0.3) !important;
        }}

        .stButton > button[kind="primary"], 
        .stDownloadButton > button[kind="primary"], 
        div[data-testid="stDownloadButton"] > button[kind="primary"] {{
            background: linear-gradient(135deg, #E5B80B 0%, #B8860B 100%) !important;
            color: #000000 !important;
            border: none !important;
            box-shadow: 0 6px 20px rgba(229, 184, 11, 0.35) !important;
        }}

        .stButton > button[kind="primary"]:hover, 
        .stDownloadButton > button[kind="primary"]:hover, 
        div[data-testid="stDownloadButton"] > button[kind="primary"]:hover {{
            background: linear-gradient(135deg, #FDD835 0%, #FBC02D 100%) !important;
            box-shadow: 0 8px 25px rgba(229, 184, 11, 0.5) !important;
            color: #000000 !important;
        }}

        [data-testid="stDataFrame"] {{
            background-color: #0d0d0d !important;
            border: 1px solid #221f1a !important;
            border-radius: 12px !important;
            padding: 8px !important;
        }}

        [data-testid="stSidebar"] {{
            background-color: #080808 !important;
            border-right: 1px solid #221f1a !important;
        }}
        
        .stTabs [data-baseweb="tab-list"] {{
            gap: 10px;
            background-color: transparent;
        }}
        .stTabs [data-baseweb="tab"] {{
            background-color: #0d0d0d;
            border-radius: 10px 10px 0 0;
            border: 1px solid #221f1a;
            border-bottom: none;
            padding: 12px 24px;
            color: #94a3b8 !important;
        }}
        .stTabs [aria-selected="true"] {{
            background-color: #1a1814 !important;
            color: #E5B80B !important;
            font-weight: bold;
            border-top: 3px solid #E5B80B !important;
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
            background-color: #0d0d0d !important;
            border: 1px solid #E5B80B !important;
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

# --- FUNÇÕES DE PERSISTÊNCIA E SUPORTE ---

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

def carregar_fluxo():
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, data, tipo, descricao, valor FROM fluxo_caixa WHERE usuario_id = :user ORDER BY id DESC"), {"user": usuario})
            rows = result.fetchall()
            if rows:
                df = pd.DataFrame(rows, columns=['id', 'Data', 'Tipo', 'Descrição', 'Valor'])
                df['Data'] = pd.to_datetime(df['Data'])
                df['Valor'] = df['Valor'].astype(float)
                return df
    except Exception:
        pass
    return pd.DataFrame(columns=['id', 'Data', 'Tipo', 'Descrição', 'Valor'])

def inserir_movimentacao_direta(tipo, descricao, valor, data_obj):
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    data_str = data_obj.strftime('%Y-%m-%d')
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO fluxo_caixa (usuario_id, data, tipo, descricao, valor)
            VALUES (:user, :data, :tipo, :desc, :val)
        """), {"user": usuario, "data": data_str, "tipo": tipo, "desc": descricao, "val": float(valor)})

def dar_baixa_fiado_direta(id_registro, nova_descricao):
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE fluxo_caixa
            SET tipo = 'Entrada',
                descricao = :desc
            WHERE id = :id
        """), {"desc": nova_descricao, "id": int(id_registro)})

def carregar_agendamentos_por_usuario(salao_id):
    salao_id_clean = urllib.parse.unquote(str(salao_id)).strip().lower() if salao_id else "padrao"
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, cliente_nome, cliente_contato, servico_nome, data, hora FROM agendamentos WHERE usuario_id = :user ORDER BY data, hora"), {"user": salao_id_clean})
            rows = result.fetchall()
            if rows:
                return pd.DataFrame(rows, columns=['id', 'Cliente', 'Contato', 'Serviço', 'Data', 'Horário'])
    except Exception:
        pass
    return pd.DataFrame(columns=['id', 'Cliente', 'Contato', 'Serviço', 'Data', 'Horário'])

def carregar_agendamentos():
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    return carregar_agendamentos_por_usuario(usuario)

def deletar_agendamento(id_ag):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM agendamentos WHERE id = :id"), {"id": int(id_ag)})

def gerar_backup_json_completo():
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    dados = {
        "usuario": usuario,
        "servicos": carregar_servicos_por_salao(usuario),
        "fluxo_caixa": carregar_fluxo().to_dict(orient="records"),
        "agendamentos": carregar_agendamentos_por_usuario(usuario).to_dict(orient="records"),
        "gerado_em": datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')
    }
    return json.dumps(dados, ensure_ascii=False, indent=4, default=str)

def gerar_pdf_contabilidade(df, titulo_relatorio):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elementos = []
    styles = getSampleStyleSheet()
    
    titulo_style = ParagraphStyle(
        'TituloPDF',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#1a1814'),
        spaceAfter=15
    )
    
    elementos.append(Paragraph(f"Relatório Financeiro - {titulo_relatorio}", titulo_style))
    elementos.append(Paragraph(f"Emitido em: {datetime.now(TZ).strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    elementos.append(Paragraph("<br/><br/>", styles['Normal']))
    
    if not df.empty:
        df_export = df.drop(columns=['id'], errors='ignore').copy()
        dados_tabela = [df_export.columns.tolist()] + df_export.values.tolist()
        tabela = Table(dados_tabela, colWidths=[100, 80, 180, 100])
        tabela.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E5B80B')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#000000')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        elementos.append(tabela)
        
    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()

def renderizar_whatsapp_flutuante():
    components.html("""
        <div style="position: fixed; bottom: 20px; right: 20px; z-index: 999999;">
            <a href="https://api.whatsapp.com/send?phone=5537991598179&text=Olá! Preciso de suporte com o sistema Fio&Caixa." target="_blank" 
               style="display: flex; align-items: center; justify-content: center; width: 55px; height: 55px; background-color: #25D366; border-radius: 50%; box-shadow: 0 4px 15px rgba(0,0,0,0.4); text-decoration: none; transition: transform 0.2s;">
                <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" fill="white" viewBox="0 0 16 16">
                  <path d="M13.601 2.326A7.85 7.85 0 0 0 7.994 0C3.627 0 .068 3.558.064 7.926c0 1.399.366 2.76 1.057 3.965L0 16l4.22-1.102a7.85 7.85 0 0 0 3.772.96h.004c4.368 0 7.926-3.558 7.93-7.93A7.89 7.89 0 0 0 13.601 2.326zM7.994 14.521a6.57 6.57 0 0 1-3.356-.92l-.24-.144-2.494.654.666-2.433-.156-.251a6.56 6.56 0 0 1-1.007-3.505c0-3.626 2.957-6.584 6.591-6.584a6.56 6.56 0 0 1 4.66 1.931 6.558 6.558 0 0 1 1.928 4.66c-.004 3.639-2.961 6.592-6.592 6.592zm3.615-4.934c-.197-.099-1.17-.578-1.353-.646-.182-.065-.315-.099-.445.099-.133.197-.513.646-.627.775-.114.133-.232.148-.43.05-.197-.1-.836-.308-1.592-.985-.59-.525-.985-1.175-1.103-1.372-.114-.198-.012-.305.087-.403.089-.088.196-.232.295-.348.1-.117.133-.198.198-.33.065-.134.034-.248-.015-.347-.05-.099-.445-1.076-.612-1.47-.16-.389-.323-.335-.445-.342l-.38-.003c-.133 0-.348.05-.53.247-.183.198-.7 宝.683-.7 1.664 0 .981.715 1.929 815 2.062.1.133 1.407 2.15 3.41 3.017.477.206.848.33 1.138.423.478.152.913.13 1.258.079.385-.057 1.17-.478 1.334-.94.164-.463.164-.86.114-.94-.05-.08-.182-.13-.381-.23z"/>
                </svg>
            </a>
        </div>
    """, height=90)

# ==============================================================================
# ROTA PÚBLICA DE AGENDAMENTO (SE HOUVER ?salao=XYZ NA URL)
# ==============================================================================
params = st.query_params
if "salao" in params:
    salao_id_raw = params["salao"]
    salao_id_clean = urllib.parse.unquote(str(salao_id_raw)).strip().lower()
    nome_salao_formatado = salao_id_clean.replace('_', ' ').replace('-', ' ').title()

    HORARIOS_DISPONIVEIS = [
        "08:00", "08:30", "09:00", "09:30", "10:00", "10:30", 
        "11:00", "11:30", "13:00", "13:30", "14:00", "14:30", 
        "15:00", "15:30", "16:00", "16:30", "17:00", "17:30", "18:00", "18:30"
    ]

    st.markdown(f"""
        <div class="login-card" style="max-width: 600px; margin-top: 2rem;">
            <span class="login-tag">AGENDAMENTO ONLINE</span>
            <h1 class="login-title">✂️ {nome_salao_formatado}</h1>
            <p class="login-subtitle">Escolha o serviço, a data e o horário desejado para agendar seu atendimento.</p>
        </div>
    """, unsafe_allow_html=True)

    servicos_salao = carregar_servicos_por_salao(salao_id_clean)

    with st.form("form_agendamento_cliente", clear_on_submit=False):
        st.markdown("### 📋 Preencha seus dados")
        nome_cliente = st.text_input("Seu Nome Completo:")
        telefone_cliente = st.text_input("Seu WhatsApp (com DDD):")
        
        if servicos_salao:
            servico_escolhido = st.selectbox("Selecione o Serviço:", list(servicos_salao.keys()))
            valor_servico = servicos_salao[servico_escolhido]
            st.info(f"💎 Valor estimado: **R$ {valor_servico:.2f}**")
        else:
            servico_escolhido = "Atendimento Padrão"
            st.warning("Nenhum serviço específico cadastrado. Será considerado atendimento padrão.")

        data_escolhida = st.date_input("Data do Atendimento:", min_value=datetime.now(TZ).date())
        data_str = data_escolhida.strftime('%Y-%m-%d')

        df_ag_existentes = carregar_agendamentos_por_usuario(salao_id_clean)
        ocupados = []
        if not df_ag_existentes.empty and 'Data' in df_ag_existentes.columns and 'Horário' in df_ag_existentes.columns:
            df_filtrado_data = df_ag_existentes[df_ag_existentes['Data'] == data_str]
            ocupados = df_filtrado_data['Horário'].tolist()

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
        
        with st.form("form_recuperar"):
            rec_user = st.text_input("ID do Salão / Usuário:")
            rec_email = st.text_input("E-mail Cadastrado:")
            rec_nova = st.text_input("Nova Senha:", type="password")
            
            if st.form_submit_button("Atualizar Senha", type="primary", use_container_width=True):
                rec_user_clean = rec_user.strip().lower()
                if rec_user_clean in usuarios_cadastrados:
                    if usuarios_cadastrados[rec_user_clean].get("email", "").strip().lower() == rec_email.strip().lower():
                        usuarios_cadastrados[rec_user_clean]["senha"] = hash_password(rec_nova)
                        salvar_usuarios(usuarios_cadastrados)
                        st.success("Senha alterada com sucesso! Faça login.")
                        st.session_state.recuperando_senha = False
                        st.rerun()
                    else:
                        st.error("E-mail não confere com o cadastro.")
                else:
                    st.error("Usuário não encontrado.")
            
            if st.button("Voltar ao Login", use_container_width=True):
                st.session_state.recuperando_senha = False
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        st.stop()

    # TELA DE LOGIN PRINCIPAL
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown('<span class="login-tag">FIO & CAIXA SYSTEM</span>', unsafe_allow_html=True)
    st.markdown('<h1 class="login-title">Bem-vindo(a)</h1>', unsafe_allow_html=True)
    st.markdown('<p class="login-subtitle">Acesse sua conta para gerenciar seu salão ou barbearia.</p>', unsafe_allow_html=True)

    with st.form("form_login"):
        tipo_acesso = st.radio("Tipo de Acesso:", ["Salão / Barbearia", "Administrador Mestre"], horizontal=True)
        usuario_input = st.text_input("Usuário ou ID do Salão:").strip().lower()
        senha_input = st.text_input("Senha:", type="password")
        senha2_input = st.text_input("Segunda Senha (Apenas Administrador Mestre):", type="password") if tipo_acesso == "Administrador Mestre" else ""
        
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

    st.markdown("<hr style='border-color: #221f1a; margin: 20px 0;'>", unsafe_allow_html=True)
    col_rec_1, col_rec_2 = st.columns(2)
    with col_rec_1:
        if st.button("Esqueci minha senha", use_container_width=True):
            st.session_state.recuperando_senha = True
            st.rerun()
    with col_rec_2:
        wa_login_msg = urllib.parse.quote("Olá! Gostaria de saber mais sobre a assinatura do Fio&Caixa.")
        st.markdown(f"""
            <a href="https://api.whatsapp.com/send?phone=5537991598179&text={wa_login_msg}" target="_blank" style="display: flex; align-items: center; justify-content: center; gap: 8px; background-color: #25D366; color: white; padding: 10px; border-radius: 12px; text-decoration: none; font-weight: 700; font-size: 0.9rem;">
                Adquirir Sistema
            </a>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    renderizar_whatsapp_flutuante()
    st.stop()


# ==============================================================================
# PAINEL DO ADMINISTRADOR MESTRE
# ==============================================================================
if st.session_state.eh_admin:
    st.title("👑 Painel do Administrador Mestre")
    usuarios_cadastrados = carregar_usuarios()
    tab_cad, tab_ger, tab_config = st.tabs(["➕ Cadastrar Salão", "👥 Gerenciar Salões", "⚙️ Configurações"])

    with tab_cad:
        st.subheader("Cadastrar Novo Salão ou Barbearia")
        with st.form("novo_salao"):
            novo_id = st.text_input("ID Único do Salão (ex: barbearia_central):").strip().lower()
            nova_senha = st.text_input("Senha de Acesso:", type="password")
            novo_email = st.text_input("E-mail de Contato:").strip().lower()
            tipo_conta = st.selectbox("Tipo de Conta:", ["Teste", "Cliente"])
            venc = st.date_input("Data de Vencimento da Licença:", datetime.now(TZ).date() + timedelta(days=30))
            
            if st.form_submit_button("Cadastrar Salão", type="primary"):
                if novo_id and nova_senha:
                    usuarios_cadastrados[novo_id] = {
                        "senha": hash_password(nova_senha),
                        "email": novo_email,
                        "tipo": tipo_conta,
                        "vencimento": venc.strftime("%Y-%m-%d"),
                        "status": "Ativo"
                    }
                    salvar_usuarios(usuarios_cadastrados)
                    st.success(f"Salão '{novo_id}' cadastrado com sucesso!")
                    st.rerun()

    with tab_ger:
        st.subheader("Gerenciar Contas Existentes")
        if usuarios_cadastrados:
            salao_sel = st.selectbox("Selecione um Salão:", list(usuarios_cadastrados.keys()))
            dados = usuarios_cadastrados[salao_sel]
            with st.form("form_edicao_salao"):
                e_email = st.text_input("E-mail:", value=dados.get("email", ""))
                e_senha_nova = st.text_input("Nova Senha (deixe em branco para manter):", type="password")
                e_tipo = st.selectbox("Tipo:", ["Teste", "Cliente"], index=0 if dados['tipo'] == "Teste" else 1)
                e_venc = st.date_input("Vencimento:", datetime.strptime(dados['vencimento'], "%Y-%m-%d"))
                e_status = st.selectbox("Status:", ["Ativo", "Suspenso"], index=0 if dados['status'] == "Ativo" else 1)
                
                if st.form_submit_button("Salvar Modificações"):
                    senha_f = hash_password(e_senha_nova) if e_senha_nova else dados['senha']
                    usuarios_cadastrados[salao_sel] = {
                        "senha": senha_f,
                        "email": e_email.strip().lower(),
                        "tipo": e_tipo,
                        "vencimento": e_venc.strftime("%Y-%m-%d"),
                        "status": e_status
                    }
                    salvar_usuarios(usuarios_cadastrados)
                    st.success("Conta atualizada com sucesso!")
                    st.rerun()

    with tab_config:
        nova_url_input = st.text_input("URL Principal do Sistema:", value=url_sistema_salva if url_sistema_salva else "")
        if st.button("Salvar URL Global"):
            atualizar_url_sistema(nova_url_input.strip())
            st.success("URL Salva!")
            st.rerun()

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

usuario_logado_limpo = urllib.parse.quote(str(st.session_state.usuario_logado).strip().lower())
url_base_ativa = url_sistema_salva if url_sistema_salva else "https://fioecaixa.onrender.com"
link_clientes = f"{url_base_ativa}/?salao={usuario_logado_limpo}"

wa_msg_geral = urllib.parse.quote(f"Olá! Agende seu horário conosco através do link: {link_clientes}")
wa_url_geral = f"https://api.whatsapp.com/send?text={wa_msg_geral}"

nome_salao_titulo = str(st.session_state.usuario_logado).replace('_', ' ').replace('-', ' ').title()

# BARRA LATERAL (SIDEBAR) COM OPÇÕES DO SALÃO
with st.sidebar:
    st.markdown(f"### ✂️ {nome_salao_titulo}")
    st.markdown("---")
    
    with st.popover("⚙️ Configurações & Serviços", use_container_width=True):
        st.markdown("#### 🛠️ Gerenciar Serviços")
        servico_sel_pop = st.selectbox("Selecione o Serviço:", ["➕ Cadastrar Novo Serviço"] + list(servicos.keys()), key="top_srv_sel")
        
        nome_p_pop = "" if servico_sel_pop == "➕ Cadastrar Novo Serviço" else servico_sel_pop
        preco_p_pop = 0.0 if servico_sel_pop == "➕ Cadastrar Novo Serviço" else float(servicos[servico_sel_pop])
        
        novo_servico_pop = st.text_input("Nome do Serviço:", value=nome_p_pop, key=f"top_nome_{servico_sel_pop}")
        novo_preco_pop = st.number_input("Valor do Serviço (R$):", min_value=0.0, value=preco_p_pop, step=5.0, key=f"top_prc_{servico_sel_pop}")
        
        col_tp1, col_tp2 = st.columns(2)
        with col_tp1:
            if st.button("💾 Salvar", type="primary", use_container_width=True, key="top_save_btn"):
                if novo_servico_pop.strip():
                    salvar_ou_atualizar_servico(servico_sel_pop, novo_servico_pop.strip(), novo_preco_pop)
                    st.success("Serviço atualizado!")
                    st.rerun()
                else:
                    st.error("Informe o nome.")
        with col_tp2:
            if servico_sel_pop != "➕ Cadastrar Novo Serviço":
                if st.button("🗑️ Excluir", use_container_width=True, key="top_del_btn"):
                    deletar_servico_banco(servico_sel_pop)
                    st.warning("Serviço excluído!")
                    st.rerun()
                    
        st.markdown("---")
        backup_dados_pop = gerar_backup_json_completo()
        st.download_button(
            label="📥 Baixar Backup JSON",
            data=backup_dados_pop,
            file_name=f"backup_{st.session_state.usuario_logado}.json",
            mime="application/json",
            use_container_width=True
        )

    if st.button("🚪 Sair do Sistema", use_container_width=True, type="secondary"):
        st.session_state.clear()
        st.rerun()

# --- CABEÇALHO DO PAINEL ---
st.markdown(f"""
    <div class="ui-card-highlight" style="display: flex; justify-content: space-between; align-items: center; padding: 15px 25px; margin-bottom: 20px;">
        <div>
            <h2 style="margin: 0; color: #ffffff;">✂️ {nome_salao_titulo}</h2>
            <p style="margin: 0; color: #E5B80B !important; font-size: 0.9rem;">Painel de Controle Financeiro & Agendamentos</p>
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
    if not df_fluxo_caixa.empty:
        hoje = pd.Timestamp(datetime.now(TZ).date())
        df_limpo = df_fluxo_caixa.dropna(subset=['Data'])
        
        val_dia = df_limpo[(df_limpo['Data'] == hoje) & (df_limpo['Tipo'] == 'Entrada')]['Valor'].sum()
        val_mes = df_limpo[(df_limpo['Data'].dt.month == hoje.month) & (df_limpo['Data'].dt.year == hoje.year) & (df_limpo['Tipo'] == 'Entrada')]['Valor'].sum()
        
        c_kpi1, c_kpi2 = st.columns(2)
        with c_kpi1:
            st.markdown(f'<div class="kpi-card"><div class="kpi-title">Faturamento Hoje</div><div class="kpi-value">R$ {val_dia:.2f}</div></div>', unsafe_allow_html=True)
        with c_kpi2:
            st.markdown(f'<div class="kpi-card"><div class="kpi-title">Faturamento Este Mês</div><div class="kpi-value">R$ {val_mes:.2f}</div></div>', unsafe_allow_html=True)
    else:
        st.info("Nenhum dado financeiro registrado ainda.")


# ==============================================================================
# TAB 0: LANÇAMENTOS RÁPIDOS
# ==============================================================================
with tab0:
    st.markdown("### 🚀 Ações Rápidas do Caixa")
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
        if servicos:
            servico_selecionado = st.selectbox("Serviço Realizado:", list(servicos.keys()), key="f_atend_serv")
            preco_final = st.number_input("Valor Recebido (R$):", value=float(servicos[servico_selecionado]), step=1.0, key="prc_atend_din")
            if st.button("Confirmar Entrada 🚀", type="primary", key="save_atend", use_container_width=True):
                inserir_movimentacao_direta("Entrada", f"Serviço: {servico_selecionado}", preco_final, datetime.now(TZ))
                st.session_state.formulario_ativo = 'none'
                st.success("Atendimento registrado com sucesso!")
                st.rerun()
        else:
            st.warning("Cadastre serviços primeiro no menu lateral.")
        st.markdown('</div>', unsafe_allow_html=True)

    elif st.session_state.formulario_ativo == 'new_venda':
        st.markdown('<div class="ui-card-highlight">', unsafe_allow_html=True)
        st.markdown("#### 🛍️ Registrar Nova Despesa")
        desc_desp = st.text_input("Descrição da Despesa:")
        val_desp = st.number_input("Valor da Despesa (R$):", min_value=0.0, step=5.0)
        if st.button("Salvar Despesa 💸", type="primary", key="save_desp", use_container_width=True):
            if desc_desp.strip() and val_desp > 0:
                inserir_movimentacao_direta("Saída", desc_desp.strip(), val_desp, datetime.now(TZ))
                st.session_state.formulario_ativo = 'none'
                st.success("Despesa registrada com sucesso!")
                st.rerun()
            else:
                st.error("Preencha todos os campos corretamente.")
        st.markdown('</div>', unsafe_allow_html=True)

    elif st.session_state.formulario_ativo == 'new_receber':
        st.markdown('<div class="ui-card-highlight">', unsafe_allow_html=True)
        st.markdown("#### 💰 Anotar Fiado / Venda Fiada")
        cliente_fiado = st.text_input("Nome do Cliente:")
        val_fiado = st.number_input("Valor Fiado (R$):", min_value=0.0, step=5.0, key="val_fiar")
        if st.button("Registrar Fiado 📌", type="primary", key="save_fiado", use_container_width=True):
            if cliente_fiado.strip() and val_fiado > 0:
                inserir_movimentacao_direta("Pendência", f"Fiado de: {cliente_fiado.strip()}", val_fiado, datetime.now(TZ))
                st.session_state.formulario_ativo = 'none'
                st.success("Fiado anotado com sucesso!")
                st.rerun()
            else:
                st.error("Preencha o nome e o valor.")
        st.markdown('</div>', unsafe_allow_html=True)

    elif st.session_state.formulario_ativo == 'new_pagar':
        st.markdown('<div class="ui-card-highlight">', unsafe_allow_html=True)
        st.markdown("#### 💸 Baixar Fiado / Receber Pendência")
        df_pend = df_fluxo_caixa[df_fluxo_caixa['Tipo'] == 'Pendência'] if not df_fluxo_caixa.empty else pd.DataFrame()
        if not df_pend.empty:
            opcoes_pend = {f"{row['Descrição']} - R$ {abs(row['Valor']):.2f}": row['id'] for _, row in df_pend.iterrows()}
            pendencia_selecionada = st.selectbox("Selecione o Fiado a Baixar:", list(opcoes_pend.keys()))
            if st.button("Confirmar Recebimento 💵", type="primary", key="save_baixa", use_container_width=True):
                id_alt = opcoes_pend[pendencia_selecionada]
                row_atual = df_pend[df_pend['id'] == id_alt].iloc[0]
                nova_desc = row_atual['Descrição'].replace("Fiado de:", "Recebido Fiado:") + " [PAGO]"
                dar_baixa_fiado_direta(id_alt, nova_desc)
                st.session_state.formulario_ativo = 'none'
                st.success("Baixa realizada com sucesso!")
                st.rerun()
        else:
            st.info("Nenhum fiado pendente registrado.")
        st.markdown('</div>', unsafe_allow_html=True)


# ==============================================================================
# TAB AGENDAMENTOS
# ==============================================================================
with tab_agend:
    st.subheader("📅 Agendamentos Confirmados")
    st.markdown('<div class="ui-card">', unsafe_allow_html=True)
    st.info(f"🔗 Link direto para clientes agendarem: **{link_clientes}**")
    st.markdown(f"""
        <a href="{wa_url_geral}" target="_blank" style="display:inline-block;width:100%;text-align:center;background-color:#00E676;color:#000;padding:0.75rem;border-radius:8px;text-decoration:none;font-weight:700;margin-bottom:10px;">
            📲 Enviar Link no WhatsApp dos Clientes
        </a>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    df_agendamentos = carregar_agendamentos()
    if not df_agendamentos.empty:
        df_disp_ag = df_agendamentos.copy()
        try:
            df_disp_ag['Data'] = pd.to_datetime(df_disp_ag['Data']).dt.strftime('%d/%m/%Y')
        except Exception:
            pass
        st.dataframe(df_disp_ag.drop(columns=['id'], errors='ignore'), use_container_width=True, hide_index=True)
        
        st.markdown('<div class="ui-card">', unsafe_allow_html=True)
        st.markdown("#### 🛠️ Gerenciar / Excluir Agendamento")
        opcoes_ag = {f"{row['Cliente']} - {row['Data']} às {row['Horário']} ({row['Serviço']})": row['id'] for _, row in df_agendamentos.iterrows()}
        ag_sel = st.selectbox("Selecionar Agendamento:", list(opcoes_ag.keys()))
        if st.button("Excluir Agendamento Selecionado", use_container_width=True):
            deletar_agendamento(opcoes_ag[ag_sel])
            st.warning("Agendamento removido!")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Nenhum agendamento registrado no momento.")


# ==============================================================================
# TAB 2: HISTÓRICO & RELATÓRIOS
# ==============================================================================
with tab2:
    st.subheader("📜 Histórico Completo & Relatórios")
    if not df_fluxo_caixa.empty:
        df_hist = df_fluxo_caixa.copy()
        st.dataframe(df_hist.drop(columns=['id'], errors='ignore'), use_container_width=True, hide_index=True)
        
        st.markdown("#### 📄 Exportar Relatórios")
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            pdf_bytes = gerar_pdf_contabilidade(df_hist, "Geral")
            st.download_button("📥 Baixar Relatório PDF", data=pdf_bytes, file_name="relatorio_financeiro.pdf", mime="application/pdf", use_container_width=True)
        with col_exp2:
            csv_bytes = df_hist.drop(columns=['id'], errors='ignore').to_csv(index=False).encode('utf-8')
            st.download_button("📥 Baixar Planilha CSV", data=csv_bytes, file_name="historico_caixa.csv", mime="text/csv", use_container_width=True)
    else:
        st.info("Nenhum registro no histórico contábil.")

# Renderiza botão flutuante de suporte via WhatsApp em todas as telas autenticadas
renderizar_whatsapp_flutuante()

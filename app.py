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

# ==========================================
# FIO&CAIXA PREMIUM UI
# Componentes reutilizáveis
# Versão 2.0
# ==========================================

from datetime import datetime
from textwrap import dedent

PRIMARY_COLOR = "#3B82F6"
SUCCESS_COLOR = "#22C55E"
WARNING_COLOR = "#F59E0B"
ERROR_COLOR = "#EF4444"

BACKGROUND = "#0F1117"
SURFACE = "#171B22"
SURFACE_LIGHT = "#202632"

TEXT = "#F7F8FA"
TEXT_SECONDARY = "#AAB3C5"

BORDER = "#2D3748"

BORDER_RADIUS = "18px"

CARD_SHADOW = "0 10px 25px rgba(0,0,0,.25)"

def load_theme():

    st.markdown(
        f"""
<style>

html,
body,
[data-testid="stAppViewContainer"]{{
    background:{BACKGROUND};
    color:{TEXT};
}}

section[data-testid="stSidebar"]{{
    background:#141922;
    border-right:1px solid {BORDER};
}}

.block-container{{
    padding-top:2rem;
    padding-bottom:2rem;
}}

h1,h2,h3,h4,h5{{
    color:{TEXT};
}}

p,
label,
span{{
    color:{TEXT_SECONDARY};
}}

.stButton>button{{
    background:{PRIMARY_COLOR};
    color:white;
    border:none;
    border-radius:12px;
    height:44px;
    font-weight:600;
}}

.stButton>button:hover{{
    transform:translateY(-2px);
    transition:.2s;
}}

.stTextInput input,
.stNumberInput input,
.stDateInput input,
.stSelectbox div{{
    border-radius:12px;
}}

[data-testid="stDataFrame"]{{
    border-radius:16px;
    overflow:hidden;
}}

.element-container{{
    animation:fade .35s ease;
}}

@keyframes fade{{

from{{
opacity:0;
transform:translateY(8px);
}}

to{{
opacity:1;
transform:translateY(0);
}}

}}

</style>

""",
        unsafe_allow_html=True,
    )
def card(
    titulo,
    conteudo,
    icone="",
):
    st.markdown(
        f"""
<div
style="
background:{SURFACE};
border:1px solid {BORDER};
border-radius:{BORDER_RADIUS};
padding:20px;
margin-bottom:15px;
box-shadow:{CARD_SHADOW};
">

<div
style="
font-size:15px;
color:{TEXT_SECONDARY};
margin-bottom:10px;
">

{icone} {titulo}

</div>

<div
style="
font-size:28px;
font-weight:700;
color:{TEXT};
">

{conteudo}

</div>

</div>

""",
unsafe_allow_html=True
)

def kpi(
    titulo,
    valor,
    cor=PRIMARY_COLOR,
):

    st.markdown(
        f"""
<div
style="
background:{SURFACE};
padding:18px;
border-radius:18px;
border-left:5px solid {cor};
box-shadow:{CARD_SHADOW};
margin-bottom:12px;
">

<div
style="
font-size:14px;
color:{TEXT_SECONDARY};
">

{titulo}

</div>

<div
style="
font-size:32px;
font-weight:700;
color:{TEXT};
">

{valor}

</div>

</div>

""",
unsafe_allow_html=True
)


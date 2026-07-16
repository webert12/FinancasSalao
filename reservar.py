import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import urllib.parse
from sqlalchemy import create_engine, text

# --- CONFIGURAÇÃO DE HORÁRIO ---
TZ = ZoneInfo("America/Sao_Paulo")

st.set_page_config(page_title="Agendamento Online", layout="centered", page_icon="✂️")

# --- INJEÇÃO DE CSS CUSTOMIZADO (Identidade Visual Dark & Gold) ---
st.markdown("""
<style>
    body, .stApp { background-color: #121212 !important; color: #ffffff !important; }
    .stApp p, .stApp span, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4 {
        color: #ffffff !important;
    }
    [data-testid="stHeader"], header { display: none !important; visibility: hidden !important; height: 0px !important; }
    .block-container { padding-top: 2rem !important; }
    
    /* Inputs */
    div[data-testid="stTextInput"] input, 
    div[data-testid="stDateInput"] input,
    div[data-baseweb="input"] input {
        background-color: #1e222b !important; 
        color: #ffffff !important; 
        border: 2px solid #4f5b66 !important; 
        border-radius: 6px !important; 
        padding: 10px !important;
    }
    
    /* Selectbox */
    div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
        background-color: #1e222b !important; 
        color: #ffffff !important; 
        border: 2px solid #4f5b66 !important; 
        border-radius: 6px !important;
    }
    
    /* Botões */
    div.stButton > button {
        background-color: #d4af37 !important; 
        color: #121212 !important; 
        border: 2px solid #d4af37 !important; 
        border-radius: 6px !important; 
        width: 100% !important; 
        font-weight: bold !important; 
        font-size: 1rem !important; 
        padding: 12px !important; 
        box-shadow: 0px 4px 10px rgba(212, 175, 55, 0.2) !important;
    }
    div.stButton > button:hover { 
        background-color: #ffffff !important; 
        color: #121212 !important; 
        border-color: #ffffff !important; 
    }
</style>
""", unsafe_allow_html=True)

# --- CONEXÃO COM O BANCO DE DADOS ---
if "DB_URL" in st.secrets:
    DB_URL = st.secrets["DB_URL"]
else:
    st.error("❌ ERRO CRÍTICO: Banco de dados não configurado nos Secrets deste aplicativo.")
    st.stop()

@st.cache_resource
def init_connection(url):
    return create_engine(url, pool_pre_ping=True)

try:
    engine = init_connection(DB_URL)
except Exception as e:
    st.error(f"Erro ao conectar ao banco: {e}")
    st.stop()

# --- FUNÇÕES DE BANCO ---
def carregar_usuarios():
    try:
        with engine.connect() as conn:
            df = pd.read_sql("SELECT id FROM usuarios", conn)
            return df['id'].tolist() if not df.empty else []
    except:
        return []

def carregar_servicos_custom(usuario):
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text("SELECT nome, preco FROM servicos WHERE usuario_id = :user"), conn, params={"user": usuario})
            if not df.empty:
                return {row['nome']: float(row['preco']) for _, row in df.iterrows()}
    except:
        pass
    return {"Corte de Cabelo": 25.00, "Barba": 25.00, "Combo Cabelo e Barba": 50.00}

def verificar_horario_disponivel(usuario_id, data_str, horario_str):
    with engine.connect() as conn:
        query = text("SELECT 1 FROM agendamentos WHERE usuario_id = :user AND data = :data AND horario = :horario")
        result = conn.execute(query, {"user": usuario_id, "data": data_str, "horario": horario_str}).fetchone()
        return result is None

def buscar_sugestoes_horarios(usuario_id, data_str):
    horarios_comerciais = [f"{h:02d}:{m:02d}" for h in range(8, 19) for m in (0, 30)]
    try:
        with engine.connect() as conn:
            query = text("SELECT horario FROM agendamentos WHERE usuario_id = :user AND data = :data")
            df_ocupados = pd.read_sql(query, conn, params={"user": usuario_id, "data": data_str})
        ocupados = df_ocupados['horario'].tolist() if not df_ocupados.empty else []
    except:
        ocupados = []
    disponiveis = [h for h in horarios_comerciais if h not in ocupados]
    return disponiveis[:5]

def registrar_agendamento(usuario_id, nome, telefone, servico, data_str, horario_str):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO agendamentos (usuario_id, cliente_nome, cliente_telefone, servico, data, horario)
            VALUES (:user, :nome, :tel, :serv, :data, :horario)
        """), {"user": usuario_id, "nome": nome, "tel": telefone, "serv": servico, "data": data_str, "horario": horario_str})


# --- FLUXO DE LEITURA DO PARÂMETRO DA URL ---
query_params = st.query_params

if "salao" not in query_params:
    st.error("❌ Link Inválido! Use o link de agendamento correto enviado pelo seu salão.")
    st.stop()

salao_id_raw = query_params["salao"]
salao_id = urllib.parse.unquote(salao_id_raw).strip().lower()

# Verifica se o salão existe no banco de dados
salões_cadastrados = carregar_usuarios()
if salao_id not in salões_cadastrados:
    st.error("❌ Desculpe, este estabelecimento não foi localizado em nossa base de dados.")
    st.stop()

nome_salao_bonito = salao_id.replace("_", " ").title()

# --- INTERFACE DE AGENDAMENTO ---
st.markdown(f'<div style="text-align: center; margin-top: 10px;"><h2 style="color: #d4af37;">✂️ {nome_salao_bonito}</h2><p>Agende seu horário online de forma rápida e simples</p></div>', unsafe_allow_html=True)
st.markdown("---")

servicos_disponiveis = carregar_servicos_custom(salao_id)

with st.form("form_agendamento"):
    c_nome = st.text_input("Seu Nome Completo:")
    c_tel = st.text_input("Seu Telefone / WhatsApp:")
    c_serv = st.selectbox("Selecione o Serviço desejado:", list(servicos_disponiveis.keys()))
    c_data = st.date_input("Escolha a Data do Atendimento:", min_value=datetime.now(TZ).date())
    
    # Gera a grade de horários de 8h às 18h30 (de 30 em 30 min)
    lista_horarios = [f"{h:02d}:{m:02d}" for h in range(8, 19) for m in (0, 30)]
    c_hora = st.selectbox("Selecione o Horário:", lista_horarios)
    
    st.write("")
    btn_enviar = st.form_submit_button("Confirmar Agendamento")

if btn_enviar:
    if not c_nome or not c_tel:
        st.error("⚠️ Por favor, informe seu nome e telefone para que possamos confirmar o horário!")
    else:
        data_str = c_data.strftime('%Y-%m-%d')
        
        # Faz a varredura para garantir que o horário está livre para aquele salão específico
        if verificar_horario_disponivel(salao_id, data_str, c_hora):
            registrar_agendamento(salao_id, c_nome, c_tel, c_serv, data_str, c_hora)
            st.success(f"🎉 Excelente, {c_nome}! Seu agendamento foi confirmado para o dia {c_data.strftime('%d/%m/%Y')} às {c_hora}!")
            st.balloons()
        else:
            st.error(f"⚠️ Sentimos muito, mas o horário das **{c_hora}** já foi reservado para essa data.")
            
            # Varre o banco e busca os horários alternativos para sugerir
            sugestoes = buscar_sugestoes_horarios(salao_id, data_str)
            if sugestoes:
                st.info("💡 **Veja outras opções de horários livres para este mesmo dia:**")
                for sug in sugestoes:
                    st.markdown(f"• ✨ Horário das **{sug}** está disponível")
                st.write("Por favor, selecione uma das opções acima no menu e tente reservar novamente.")
            else:
                st.warning("Todas as vagas para este dia foram preenchidas. Que tal escolher outra data?")

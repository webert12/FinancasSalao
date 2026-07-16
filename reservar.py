import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import create_engine, text

# --- CONFIGURAÇÕES BÁSICAS ---
TZ = ZoneInfo("America/Sao_Paulo")
st.set_page_config(page_title="Agendamento Online", layout="centered", page_icon="📅")

# --- ESTILO VISUAL LIMPO ---
st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    h1 { text-align: center; color: #d4af37; }
    p { text-align: center; }
</style>
""", unsafe_allow_html=True)

# --- CONEXÃO COM O BANCO DE DADOS ---
if "DB_URL" in st.secrets:
    DB_URL = st.secrets["DB_URL"]
else:
    st.error("Erro técnico: Banco de dados não configurado nos Secrets.")
    st.stop()

@st.cache_resource
def init_connection(url):
    return create_engine(url, pool_pre_ping=True)

engine = init_connection(DB_URL)

# --- FUNÇÕES DE BUSCA E SALVAMENTO ---
def carregar_servicos_por_salao(salao_id):
    try:
        with engine.connect() as conn:
            df = pd.read_sql(
                text("SELECT nome, preco FROM servicos WHERE usuario_id = :user"), 
                conn, 
                params={"user": salao_id}
            )
            if not df.empty:
                return {row['nome']: float(row['preco']) for _, row in df.iterrows()}
    except Exception as e:
        st.error(f"Erro ao carregar serviços: {e}")
    # Retorno padrão caso o salão não tenha serviços cadastrados ainda
    return {"Corte": 30.0, "Barba": 25.0}

def verificar_se_salao_existe(salao_id):
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT id FROM usuarios WHERE id = :user AND status = 'Ativo'"), 
                {"user": salao_id}
            ).fetchone()
            return result is not None
    except:
        return False

def salvar_agendamento(salao_id, cliente, contato, servico, data, hora):
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO agendamentos (usuario_id, cliente_nome, cliente_contato, servico_nome, data, hora)
                VALUES (:user, :cliente, :contato, :servico, :data, :hora)
            """), {
                "user": salao_id, 
                "cliente": cliente, 
                "contato": contato, 
                "servico": servico, 
                "data": str(data), 
                "hora": str(hora)
            })
            return True
    except Exception as e:
        st.error(f"Erro ao salvar agendamento: {e}")
        return False

# --- ROTEAMENTO E LEITURA DO SALÃO ---
query_params = st.query_params

if "salao" not in query_params:
    st.warning("⚠️ Link Inválido. Por favor, use o link correto enviado pelo seu salão de beleza.")
    st.stop()

salao_id = query_params["salao"].strip().lower()

# Verifica se o salão de fato existe no seu banco de dados
if not verificar_se_salao_existe(salao_id):
    st.error(f"❌ O salão '{salao_id}' não foi encontrado ou está com a licença inativa.")
    st.stop()

# --- TELA DE AGENDAMENTO PARA O CLIENTE ---
st.title(f"📅 Agendamento Online - {salao_id.title()}")
st.markdown("Reserve seu horário em poucos segundos. É rápido e prático!")
st.markdown("---")

servicos_disponiveis = carregar_servicos_por_salao(salao_id)

with st.form("form_agendamento_publico"):
    cliente_nome = st.text_input("Seu Nome completo (Obrigatório):")
    cliente_contato = st.text_input("Seu WhatsApp com DDD (Ex: 11999999999):")
    
    servico_selecionado = st.selectbox("Selecione o Serviço desejado:", list(servicos_disponiveis.keys()))
    
    preco_estimado = servicos_disponiveis[servico_selecionado]
    st.info(f"💵 Valor do serviço: R$ {preco_estimado:.2f}")
    
    data_agendada = st.date_input("Escolha o Dia:", datetime.now(TZ).date())
    
    # Criação de horários de 30 em 30 minutos
    slots_horario = [f"{h:02d}:00" for h in range(8, 20)] + [f"{h:02d}:30" for h in range(8, 20)]
    slots_horario.sort()
    
    horario_selecionado = st.selectbox("Escolha o Horário:", slots_horario)
    
    enviar_agendamento = st.form_submit_button("Confirmar Agendamento 🚀", use_container_width=True)
    
    if enviar_agendamento:
        if not cliente_nome.strip():
            st.error("Por favor, preencha o seu nome.")
        else:
            sucesso = salvar_agendamento(salao_id, cliente_nome, cliente_contato, servico_selecionado, data_agendada, horario_selecionado)
            if sucesso:
                st.success(f"🎉 Excelente, {cliente_nome}! Seu horário para o dia {data_agendada.strftime('%d/%m/%Y')} às {horario_selecionado} foi reservado com sucesso!")
                st.balloons()

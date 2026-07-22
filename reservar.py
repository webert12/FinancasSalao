import streamlit as st
import sqlite3
from datetime import datetime

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA E BANCO DE DADOS
# ==========================================
st.set_page_config(page_title="Sistema de Agendamento", page_icon="✂️", layout="centered")

def init_db():
    conn = sqlite3.connect('agendamentos_salao.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS agendamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            salao_id TEXT NOT NULL,
            cliente_nome TEXT NOT NULL,
            cliente_telefone TEXT NOT NULL,
            servico TEXT NOT NULL,
            data_agendamento TEXT NOT NULL,
            horario TEXT NOT NULL,
            status TEXT DEFAULT 'Confirmado'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Horários padrão de atendimento
HORARIOS_DISPONIVEIS = [
    "08:00", "08:30", "09:00", "09:30", "10:00", "10:30", 
    "11:00", "11:30", "13:00", "13:30", "14:00", "14:30", 
    "15:00", "15:30", "16:00", "16:30", "17:00", "17:30", 
    "18:00", "18:30", "19:00"
]

def buscar_agendamentos_ocupados(salao_id, data_str):
    conn = sqlite3.connect('agendamentos_salao.db')
    c = conn.cursor()
    c.execute(
        "SELECT horario FROM agendamentos WHERE salao_id = ? AND data_agendamento = ? AND status = 'Confirmado'", 
        (salao_id, data_str)
    )
    ocupados = [item[0] for item in c.fetchall()]
    conn.close()
    return ocupados

def salvar_agendamento(salao_id, nome, telefone, servico, data_str, horario):
    conn = sqlite3.connect('agendamentos_salao.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO agendamentos (salao_id, cliente_nome, cliente_telefone, servico, data_agendamento, horario)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (salao_id, nome, telefone, servico, data_str, horario))
    conn.commit()
    conn.close()

# ==========================================
# 2. CAPTURA DE PARÂMETROS DA URL
# ==========================================
query_params = st.query_params
salao_atual = query_params.get("salao", "salao_exemplo")
modo_painel = query_params.get("painel", "false")

# ==========================================
# 3. INTERFACE: PAINEL DO DONO DO SALÃO
# ==========================================
if modo_painel == "true":
    st.title("📊 Painel de Controle - Salão")
    st.info(falta_msg := f"Você está gerenciando o salão: **{salao_atual.upper()}**")

    # Exibe o link personalizado para enviar aos clientes
    url_base = "https://financassalao-blazvouwtjau5y667nrlrd.streamlit.app/"
    link_cliente = f"{url_base}?salao={salao_atual}"
    
    st.subheader("🔗 Link de Agendamento para seus Clientes")
    st.code(link_cliente, language="text")
    
    msg_wa = f"Olá! Agende seu horário no nosso salão direto pelo link: {link_cliente}"
    st.markdown(f"[📲 Enviar link no WhatsApp dos Clientes](https://api.whatsapp.com/send?text={msg_wa.replace(' ', '%20')})")

    st.divider()
    st.subheader("📅 Agendamentos do Dia")

    data_filtro = st.date_input("Filtrar por data:", datetime.now().date())
    data_filtro_str = data_filtro.strftime("%Y-%m-%d")

    conn = sqlite3.connect('agendamentos_salao.db')
    c = conn.cursor()
    c.execute('''
        SELECT id, horario, cliente_nome, cliente_telefone, servico, status 
        FROM agendamentos 
        WHERE salao_id = ? AND data_agendamento = ?
        ORDER BY horario ASC
    ''', (salao_atual, data_filtro_str))
    
    agendamentos = c.fetchall()
    conn.close()

    if agendamentos:
        for item in agendamentos:
            id_ag, hora, cliente, fone, serv, status = item
            with st.expander(f"⏰ {hora} - {cliente} ({serv})"):
                st.write(f"**Telefone/WhatsApp:** {fone}")
                st.write(f"**Serviço:** {serv}")
                st.write(f"**Status:** {status}")
                if st.button(f"Cancelar Agendamento #{id_ag}", key=f"btn_{id_ag}"):
                    conn = sqlite3.connect('agendamentos_salao.db')
                    c = conn.cursor()
                    c.execute("UPDATE agendamentos SET status = 'Cancelado' WHERE id = ?", (id_ag,))
                    conn.commit()
                    conn.close()
                    st.success("Agendamento cancelado com sucesso!")
                    st.rerun()
    else:
        st.info("Nenhum agendamento para esta data.")
        
    st.stop()  # Para a execução aqui para o cliente não ver o painel

# ==========================================
# 4. INTERFACE: TELA DE AGENDAMENTO DO CLIENTE
# ==========================================
st.title(f"✂️ Agendamento Online")
st.write(f"Seja bem-vindo ao sistema de agendamento do **{salao_atual.capitalize()}**.")

with st.form("form_cliente"):
    nome_cliente = st.text_input("Seu Nome Completo:")
    telefone_cliente = st.text_input("Seu WhatsApp (com DDD):")
    
    servico_escolhido = st.selectbox(
        "Escolha o Serviço Desejado:",
        ["Corte de Cabelo", "Barba", "Combo (Corte + Barba)"]
    )
    
    data_escolhida = st.date_input("Escolha o Dia:", min_value=datetime.now().date())
    data_str = data_escolhida.strftime("%Y-%m-%d")

    # Sistema de Conflito: Busca horários já reservados
    ocupados = buscar_agendamentos_ocupados(salao_atual, data_str)
    horarios_livres = [h for h in HORARIOS_DISPONIVEIS if h not in ocupados]

    if horarios_livres:
        horario_escolhido = st.selectbox("Horários Disponíveis:", horarios_livres)
    else:
        st.error("⚠️ Todos os horários para este dia já estão ocupados! Por favor, selecione outra data.")
        horario_escolhido = None

    enviar = st.form_submit_button("Confirmar Agendamento 🚀")

if enviar:
    if not nome_cliente or not telefone_cliente:
        st.warning("⚠️ Por favor, preencha seu nome e WhatsApp.")
    elif not horario_escolhido:
        st.error("⚠️ Escolha um horário válido antes de confirmar.")
    else:
        salvar_agendamento(salao_atual, nome_cliente, telefone_cliente, servico_escolhido, data_str, horario_escolhido)
        st.success(f"🎉 Agendamento confirmado com sucesso, {nome_cliente}!")
        st.balloons()
        st.info(f"📅 **Data:** {data_escolhida.strftime('%d/%m/%Y')} às **{horario_escolhido}**\n✂️ **Serviço:** {servico_escolhido}")

# Rodapé discreto para acesso do dono
st.divider()
st.caption("É dono do salão? [Acesse seu painel administrativo aqui](?painel=true&salao=" + salao_atual + ")")

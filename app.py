import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import json

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Financeira - Salão", layout="wide", page_icon="✂️")

USUARIOS_FILE = "usuarios.json"
ADMIN_MESTRE_USER = "admin"
ADMIN_MESTRE_PASS = "master2026"

# --- FUNÇÕES DE GERENCIAMENTO DE USUÁRIOS ---
def carregar_usuarios():
    vencimento_padrao = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    if os.path.exists(USUARIOS_FILE):
        with open(USUARIOS_FILE, "r") as f:
            dados = json.load(f)
        
        # Migração automática caso o arquivo esteja no formato antigo
        usuarios_atualizados = {}
        modificado = False
        for k, v in dados.items():
            if isinstance(v, str):
                usuarios_atualizados[k] = {
                    "senha": v, 
                    "tipo": "Cliente", 
                    "vencimento": vencimento_padrao, 
                    "status": "Ativo"
                }
                modificado = True
            else:
                usuarios_atualizados[k] = v
        if modificado:
            salvar_usuarios(usuarios_atualizados)
        return usuarios_atualizados
    
    # Dados iniciais
    usuarios_padrao = {
        "salao_central": {
            "senha": "admin123",
            "tipo": "Cliente",
            "vencimento": vencimento_padrao,
            "status": "Ativo"
        }
    }
    salvar_usuarios(usuarios_padrao)
    return usuarios_padrao

def salvar_usuarios(usuarios):
    with open(USUARIOS_FILE, "w") as f:
        json.dump(usuarios, f, indent=4)

# --- FUNÇÕES DE PERSISTÊNCIA ---
def obter_nomes_arquivos():
    usuario = st.session_state.usuario_logado
    return f"servicos_{usuario}.json", f"fluxo_caixa_{usuario}.csv"

def carregar_servicos():
    servicos_file, _ = obter_nomes_arquivos()
    if os.path.exists(servicos_file):
        with open(servicos_file, "r") as f:
            return json.load(f)
    return {"Corte de Cabelo": 25.00, "Barba": 25.00, "Combo Cabelo e Barba": 50.00}

def salvar_servicos(servicos):
    servicos_file, _ = obter_nomes_arquivos()
    with open(servicos_file, "w") as f:
        json.dump(servicos, f, indent=4)

def carregar_fluxo():
    _, fluxo_file = obter_nomes_arquivos()
    if os.path.exists(fluxo_file):
        try:
            df = pd.read_csv(fluxo_file)
            df['Data'] = pd.to_datetime(df['Data'])
            return df
        except:
            return pd.DataFrame(columns=["Data", "Tipo", "Descrição", "Valor"])
    return pd.DataFrame(columns=["Data", "Tipo", "Descrição", "Valor"])

def salvar_fluxo(df):
    _, fluxo_file = obter_nomes_arquivos()
    df.to_csv(fluxo_file, index=False)

# --- INICIALIZAÇÃO DE ESTADO ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'usuario_logado' not in st.session_state: st.session_state.usuario_logado = None
if 'eh_admin' not in st.session_state: st.session_state.eh_admin = False

usuarios_cadastrados = carregar_usuarios()

# --- LOGIN ---
if not st.session_state.autenticado:
    st.title("✂️ Sistema de Gestão - Login")
    st.markdown("---")
    with st.form("form_login"):
        st.subheader("Acesse seu Painel")
        usuario_input = st.text_input("Usuário do Salão ou ADM:").strip().lower()
        senha_input = st.text_input("Senha:", type="password")
        if st.form_submit_button("Entrar no Sistema"):
            if usuario_input == ADMIN_MESTRE_USER and senha_input == ADMIN_MESTRE_PASS:
                st.session_state.autenticado = True
                st.session_state.usuario_logado = "Administrador"
                st.session_state.eh_admin = True
                st.rerun()
            elif usuario_input in usuarios_cadastrados and usuarios_cadastrados[usuario_input]["senha"] == senha_input:
                dados_user = usuarios_cadastrados[usuario_input]
                data_vencimento = datetime.strptime(dados_user["vencimento"], "%Y-%m-%d").date()
                if datetime.now().date() > data_vencimento or dados_user.get("status") == "Suspenso":
                    st.error("❌ ACESSO BLOQUEADO! Licença vencida.")
                    st.stop()
                st.session_state.autenticado = True
                st.session_state.usuario_logado = usuario_input
                st.session_state.eh_admin = False
                st.session_state.servicos = carregar_servicos()
                st.session_state.fluxo_caixa = carregar_fluxo()
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
    st.stop()

# --- PAINEL ADMINISTRADOR ---
if st.session_state.eh_admin:
    st.title("👑 Central do Administrador")
    col_cad, col_lista = st.columns([1, 1.2])
    with col_cad:
        with st.form("form_cadastro_cliente"):
            novo_usuario = st.text_input("Usuário do Salão:").strip().lower()
            nova_senha = st.text_input("Senha:", type="password")
            tipo_conta = st.selectbox("Tipo:", ["Teste", "Cliente"])
            dias_validade = st.number_input("Dias de Acesso:", value=30)
            if st.form_submit_button("Salvar/Atualizar"):
                vencimento = (datetime.now() + timedelta(days=dias_validade)).strftime("%Y-%m-%d")
                usuarios_cadastrados[novo_usuario] = {"senha": nova_senha, "tipo": tipo_conta, "vencimento": vencimento, "status": "Ativo"}
                salvar_usuarios(usuarios_cadastrados); st.success("Salão salvo!"); st.rerun()
    with col_lista:
        df_users = pd.DataFrame([{"Salão": k, **v} for k, v in usuarios_cadastrados.items()])
        st.dataframe(df_users, use_container_width=True)
    if st.sidebar.button("🚪 Sair"):
        st.session_state.autenticado = False; st.rerun()
    st.stop()

# --- PAINEL DO CLIENTE ---
nome_salao = st.session_state.usuario_logado.replace("_", " ").title()
st.title(f"✂️ {nome_salao}")

# Sidebar: Serviços
with st.sidebar:
    st.header("⚙️ Configurações")
    servicos = st.session_state.servicos
    servico_sel = st.selectbox("Gerenciar serviços:", ["Novo"] + list(servicos.keys()))
    nome_serv = st.text_input("Nome:", value="" if servico_sel=="Novo" else servico_sel)
    preco_serv = st.number_input("Preço:", value=0.0 if servico_sel=="Novo" else float(servicos.get(servico_sel, 0)))
    if st.button("Salvar Serviço"):
        servicos[nome_serv] = preco_serv
        salvar_servicos(servicos); st.rerun()
    if st.button("🚪 Sair"):
        st.session_state.autenticado = False; st.rerun()

# Dashboard / Tabs
tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "💰 Lançar", "📜 Histórico"])

with tab2:
    with st.expander("📥 Registrar Entrada"):
        servico = st.selectbox("Serviço:", list(st.session_state.servicos.keys()))
        valor = st.number_input("Valor:", value=float(st.session_state.servicos[servico]))
        if st.button("Confirmar Entrada"):
            nova_linha = pd.DataFrame([{"Data": datetime.now(), "Tipo": "Entrada", "Descrição": f"Atendimento: {servico}", "Valor": valor}])
            st.session_state.fluxo_caixa = pd.concat([st.session_state.fluxo_caixa, nova_linha], ignore_index=True)
            salvar_fluxo(st.session_state.fluxo_caixa); st.rerun()

with tab1:
    df = st.session_state.fluxo_caixa
    if not df.empty:
        st.metric("Total Entradas", f"R$ {df[df['Tipo']=='Entrada']['Valor'].sum():.2f}")
    else:
        st.info("Nenhuma transação.")

with tab3:
    st.dataframe(st.session_state.fluxo_caixa, use_container_width=True)

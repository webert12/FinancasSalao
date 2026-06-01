import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import json
import hashlib
from cryptography.fernet import Fernet

# --- CONFIGURAÇÃO DE SEGURANÇA (NOVA) ---
if not os.path.exists("secret.key"):
    with open("secret.key", "wb") as f: f.write(Fernet.generate_key())
with open("secret.key", "rb") as f: cipher = Fernet(f.read())

USUARIOS_FILE = "usuarios.dat" # Arquivo criptografado

def hash_senha(senha): return hashlib.sha256(senha.encode()).hexdigest()

def salvar_usuarios(usuarios):
    dados_bytes = json.dumps(usuarios).encode()
    with open(USUARIOS_FILE, "wb") as f: f.write(cipher.encrypt(dados_bytes))

def carregar_usuarios():
    if not os.path.exists(USUARIOS_FILE): return {}
    with open(USUARIOS_FILE, "rb") as f:
        try: return json.loads(cipher.decrypt(f.read()).decode())
        except: return {}

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Financeira - Salão", layout="wide", page_icon="✂️")

ADMIN_MESTRE_USER = "admin"
ADMIN_MESTRE_PASS = "master2026"
SENHA_2FA = "123456" # Defina sua senha secundária aqui

# --- FUNÇÕES DE PERSISTÊNCIA ---
def obter_nomes_arquivos():
    usuario = st.session_state.usuario_logado
    return f"servicos_{usuario}.json", f"fluxo_caixa_{usuario}.csv"

def carregar_servicos():
    servicos_file, _ = obter_nomes_arquivos()
    if os.path.exists(servicos_file):
        with open(servicos_file, "r") as f: return json.load(f)
    return {"Corte de Cabelo": 25.00, "Barba": 25.00, "Combo Cabelo e Barba": 50.00}

def salvar_servicos(servicos):
    servicos_file, _ = obter_nomes_arquivos()
    with open(servicos_file, "w") as f: json.dump(servicos, f, indent=4)

def carregar_fluxo():
    _, fluxo_file = obter_nomes_arquivos()
    if os.path.exists(fluxo_file):
        try:
            df = pd.read_csv(fluxo_file)
            df['Data'] = pd.to_datetime(df['Data'])
            return df
        except: return pd.DataFrame(columns=["Data", "Tipo", "Descrição", "Valor"])
    return pd.DataFrame(columns=["Data", "Tipo", "Descrição", "Valor"])

def salvar_fluxo(df):
    _, fluxo_file = obter_nomes_arquivos()
    df.to_csv(fluxo_file, index=False)

# --- INICIALIZAÇÃO DE ESTADO ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'usuario_logado' not in st.session_state: st.session_state.usuario_logado = None
if 'eh_admin' not in st.session_state: st.session_state.eh_admin = False
if 'admin_2fa' not in st.session_state: st.session_state.admin_2fa = False

usuarios_cadastrados = carregar_usuarios()

# --- LOGIN ---
if not st.session_state.autenticado:
    st.title("✂️ Sistema de Gestão - Login")
    
    # Recuperação de Senha
    if st.checkbox("Esqueci minha senha"):
        user_rec = st.text_input("Usuário:").strip().lower()
        if user_rec in usuarios_cadastrados:
            resp_seg = st.text_input("Resposta da pergunta de segurança:")
            if st.button("Validar Resposta"):
                if hash_senha(resp_seg) == usuarios_cadastrados[user_rec].get("rec_resp"):
                    nova_s = st.text_input("Nova Senha:", type="password")
                    if st.button("Salvar Nova Senha"):
                        usuarios_cadastrados[user_rec]["senha"] = hash_senha(nova_s)
                        salvar_usuarios(usuarios_cadastrados)
                        st.success("Senha atualizada!")
                else: st.error("Resposta incorreta.")
    
    with st.form("form_login"):
        st.subheader("Acesse seu Painel")
        usuario_input = st.text_input("Usuário do Salão ou ADM:").strip().lower()
        senha_input = st.text_input("Senha:", type="password")
        if st.form_submit_button("Entrar no Sistema"):
            if usuario_input == ADMIN_MESTRE_USER and senha_input == ADMIN_MESTRE_PASS:
                st.session_state.admin_2fa = True
                st.rerun()
            elif usuario_input in usuarios_cadastrados and usuarios_cadastrados[usuario_input]["senha"] == hash_senha(senha_input):
                dados_user = usuarios_cadastrados[usuario_input]
                st.session_state.autenticado = True
                st.session_state.usuario_logado = usuario_input
                st.session_state.eh_admin = False
                st.session_state.servicos = carregar_servicos()
                st.session_state.fluxo_caixa = carregar_fluxo()
                st.rerun()
            else: st.error("Usuário ou senha incorretos.")
            
    # 2FA Admin
    if st.session_state.admin_2fa:
        st.warning("Confirme sua senha secundária (2FA):")
        if st.text_input("Senha 2FA:", type="password") == SENHA_2FA:
            st.session_state.autenticado = True
            st.session_state.usuario_logado = "Administrador"
            st.session_state.eh_admin = True
            st.session_state.admin_2fa = False
            st.rerun()
    st.stop()

# --- PAINEL ADMINISTRADOR ---
if st.session_state.eh_admin:
    st.title("👑 Central do Administrador")
    col_cad, col_lista = st.columns([1, 1.2])
    with col_cad:
        with st.form("form_cadastro_cliente"):
            novo_usuario = st.text_input("Usuário do Salão:").strip().lower()
            nova_senha = st.text_input("Senha:", type="password")
            pergunta = st.text_input("Pergunta Segurança (Ex: Cor Favorita)")
            resposta = st.text_input("Resposta")
            if st.form_submit_button("Salvar / Atualizar"):
                usuarios_cadastrados[novo_usuario] = {
                    "senha": hash_senha(nova_senha),
                    "rec_resp": hash_senha(resposta),
                    "tipo": "Cliente"
                }
                salvar_usuarios(usuarios_cadastrados)
                st.success("Salão salvo!"); st.rerun()
    with col_lista:
        for user in list(usuarios_cadastrados.keys()):
            col1, col2 = st.columns([3, 1])
            col1.write(f"Usuário: {user}")
            if col2.button("Excluir", key=f"del_{user}"):
                del usuarios_cadastrados[user]
                salvar_usuarios(usuarios_cadastrados); st.rerun()
    if st.sidebar.button("🚪 Sair"):
        st.session_state.autenticado = False; st.rerun()
    st.stop()

# --- PAINEL DO CLIENTE (MANTIDO 100% ORIGINAL) ---
nome_salao = st.session_state.usuario_logado.replace("_", " ").title()
st.title(f"✂️ {nome_salao} - Gestão Financeira")

with st.sidebar:
    st.header("⚙️ Configurações de Serviços")
    opcoes = ["➕ Cadastrar Novo Serviço"] + list(st.session_state.servicos.keys())
    servico_sel = st.selectbox("Escolha uma ação:", opcoes)
    nome_serv = st.text_input("Nome do Serviço:", value="" if servico_sel=="➕ Cadastrar Novo Serviço" else servico_sel)
    preco_serv = st.number_input("Preço (R$):", value=0.0 if servico_sel=="➕ Cadastrar Novo Serviço" else float(st.session_state.servicos[servico_sel]))
    if st.button("Salvar"):
        st.session_state.servicos[nome_serv] = preco_serv
        salvar_servicos(st.session_state.servicos); st.rerun()
    if st.button("🚪 Sair"): st.session_state.autenticado = False; st.rerun()

tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "💰 Lançar Movimentação", "📜 Histórico de Caixa"])

with tab2:
    with st.expander("📥 REGISTRAR ENTRADA"):
        servico = st.selectbox("Serviço:", list(st.session_state.servicos.keys()))
        valor = st.number_input("Valor (R$):", value=float(st.session_state.servicos[servico]))
        if st.button("Confirmar Entrada"):
            nova_linha = pd.DataFrame([{"Data": datetime.now(), "Tipo": "Entrada", "Descrição": f"Atendimento: {servico}", "Valor": valor}])
            st.session_state.fluxo_caixa = pd.concat([st.session_state.fluxo_caixa, nova_linha], ignore_index=True)
            salvar_fluxo(st.session_state.fluxo_caixa); st.rerun()

with tab1:
    df = st.session_state.fluxo_caixa
    if not df.empty: st.metric("Total Entradas", f"R$ {df[df['Tipo']=='Entrada']['Valor'].sum():.2f}")
    else: st.info("Sem transações.")

with tab3:
    st.dataframe(st.session_state.fluxo_caixa, use_container_width=True)

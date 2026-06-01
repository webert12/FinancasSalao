import streamlit as st
import pandas as pd
import json
import hashlib
import os
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

# --- SEGURANÇA: AUTO-CONFIGURAÇÃO ---
def obter_chave():
    if not os.path.exists("secret.key"):
        key = Fernet.generate_key()
        with open("secret.key", "wb") as key_file:
            key_file.write(key)
    with open("secret.key", "rb") as key_file:
        return key_file.read()

CHAVE = obter_chave()
cipher = Fernet(CHAVE)
USUARIOS_FILE = "usuarios.dat"

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def salvar_usuarios_seguro(usuarios):
    dados_bytes = json.dumps(usuarios).encode()
    dados_cripto = cipher.encrypt(dados_bytes)
    with open(USUARIOS_FILE, "wb") as f:
        f.write(dados_cripto)

def carregar_usuarios_seguro():
    if not os.path.exists(USUARIOS_FILE):
        return {}
    with open(USUARIOS_FILE, "rb") as f:
        try:
            dados_cripto = f.read()
            dados_bytes = cipher.decrypt(dados_cripto)
            return json.loads(dados_bytes.decode())
        except:
            return {}

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Salão Pro", layout="wide")

# --- ESTADOS DA SESSÃO ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'eh_admin' not in st.session_state: st.session_state.eh_admin = False
if 'usuario_logado' not in st.session_state: st.session_state.usuario_logado = None

usuarios = carregar_usuarios_seguro()

# --- LOGIN ---
if not st.session_state.autenticado:
    st.title("🔐 Login Seguro")
    
    # Recuperação
    if st.checkbox("Esqueci minha senha"):
        user_rec = st.text_input("Usuário:")
        if user_rec in usuarios:
            resp = st.text_input("Resposta da pergunta de segurança:")
            if st.button("Validar"):
                if hash_senha(resp) == usuarios[user_rec].get("rec_resposta"):
                    nova_s = st.text_input("Nova Senha:", type="password")
                    if st.button("Salvar Nova Senha"):
                        usuarios[user_rec]["senha"] = hash_senha(nova_s)
                        salvar_usuarios_seguro(usuarios)
                        st.success("Senha alterada!")
                else: st.error("Resposta incorreta.")
    
    with st.form("login"):
        u = st.text_input("Usuário").lower()
        p = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            # Lógica Admin
            if u == "admin" and p == "master2026":
                st.session_state.autenticado = True
                st.session_state.usuario_logado = "Administrador"
                st.session_state.eh_admin = True
                st.rerun()
            # Lógica Cliente
            elif u in usuarios and usuarios[u]["senha"] == hash_senha(p):
                st.session_state.autenticado = True
                st.session_state.usuario_logado = u
                st.rerun()
            else: st.error("Credenciais inválidas.")
    st.stop()

# --- PAINEL ADMINISTRADOR ---
if st.session_state.eh_admin:
    st.title("👑 Central do Admin")
    tab1, tab2 = st.tabs(["Novo Usuário", "Gerenciar"])
    with tab1:
        with st.form("cria_user"):
            n = st.text_input("Nome do Usuário").lower()
            s = st.text_input("Senha", type="password")
            p = st.text_input("Pergunta de segurança (Ex: Nome do pet)")
            r = st.text_input("Resposta da pergunta")
            if st.form_submit_button("Criar Usuário"):
                usuarios[n] = {"senha": hash_senha(s), "pergunta": p, "rec_resposta": hash_senha(r)}
                salvar_usuarios_seguro(usuarios)
                st.success("Usuário criado!")
    with tab2:
        for user in list(usuarios.keys()):
            col1, col2 = st.columns([3, 1])
            col1.write(f"Usuário: **{user}**")
            if col2.button("Excluir", key=f"del_{user}"):
                del usuarios[user]
                salvar_usuarios_seguro(usuarios)
                st.rerun()

    if st.button("Sair"):
        st.session_state.autenticado = False; st.session_state.eh_admin = False; st.rerun()
    st.stop()

# --- PAINEL CLIENTE ---
st.title(f"Bem-vindo, {st.session_state.usuario_logado}")
st.write("Sistema seguro. Criptografia ativa.")
if st.button("Sair"):
    st.session_state.autenticado = False; st.rerun()

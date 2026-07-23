import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import json
import time
import hashlib
from io import BytesIO
import urllib.parse
import re
import decimal
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
st.set_page_config(page_title="Sistema de Gestão", layout="wide", page_icon="✂️")

# --- CUSTOMIZAÇÃO CSS (Foco em legibilidade APK + Logo de Fundo) ---
st.markdown("""
    <style>
        /* Remove rodapés e marcas nativas */
        footer, [data-testid="stFooter"], .stFooter, 
        #MainMenu, [data-testid="stToolbar"], [data-testid="stDecoration"], .stDeployButton {
            display: none !important;
        }
        
        /* Botão de menu/configurações flutuante e discreto */
        [data-testid="collapsedControl"] {
            display: flex !important;
            visibility: visible !important;
            position: fixed !important;
            top: 10px !important;       
            right: 15px !important;     
            left: auto !important;      
            z-index: 9999999 !important; 
        }

        .main .block-container {
            padding-top: 2.5rem !important;
            padding-bottom: 2rem !important;
            max-width: 100% !important;
        }

        /* Logo de Fundo Discreta */
        [data-testid="stSidebar"]::before {
            content: "";
            display: block;
            height: 120px;
            background: url('https://raw.githubusercontent.com/seu-usuario/seu-repo/main/logo.png') no-repeat center center;
            background-size: contain;
            margin-bottom: 15px;
        }
    </style>
""", unsafe_allow_html=True)

# --- SCRIPT JAVASCRIPT DE PROTEÇÃO DE TELA ---
components.html("""
    <script>
        function removeUnwantedElements() {
            const selectors = [
                'div[class*="viewerBadge"]',
                'a[href*="streamlit.io"]',
                'a[href*="github"]',
                'footer',
                '#manage-app-button'
            ];
            selectors.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => { el.remove(); });
            });
        }
        setInterval(removeUnwantedElements, 1000);
    </script>
""", height=0, width=0)

# --- CAPTURA DA DATABASE DIRETAMENTE DOS SECRETS ---
if "DB_URL" in st.secrets:
    DB_URL = st.secrets["DB_URL"]
else:
    st.error("❌ ERRO CRÍTICO: A variável 'DB_URL' não foi configurada nos Secrets do Streamlit Cloud.")
    st.stop()

# --- Inicialização da Engine de Banco de Dados ---
@st.cache_resource
def init_connection(url):
    return create_engine(url, pool_pre_ping=True)

try:
    engine = init_connection(DB_URL)
except Exception as e:
    st.error(f"Erro crítico ao instanciar o motor do banco de dados: {e}")
    st.stop()

# --- FUNÇÃO DE CRIAÇÃO AUTOMÁTICA DE TABELAS ---
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
        except:
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

try:
    inicializar_banco()
except Exception as e:
    st.error(f"Erro ao estruturar tabelas automáticas: {e}")
    st.stop()

# --- FUNÇÕES DE PERSISTÊNCIA ---
def carregar_admin_hashes():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT hash1, hash2, url_sistema FROM admin_config WHERE id = 1")).fetchone()
            if result:
                return result[0], result[1], result[2]
    except:
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
    except Exception as e:
        st.error(f"Erro ao salvar configurações administrativas: {e}")

def atualizar_url_sistema(url):
    try:
        with engine.begin() as conn:
            conn.execute(text("UPDATE admin_config SET url_sistema = :url WHERE id = 1"), {"url": url})
    except Exception as e:
        st.error(f"Erro ao atualizar URL do sistema: {e}")

def carregar_usuarios():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, senha, email, tipo, vencimento, status FROM usuarios"))
            rows = result.fetchall()
            if rows:
                return {row[0]: {"id": row[0], "senha": row[1], "email": row[2], "tipo": row[3], "vencimento": row[4], "status": row[5]} for row in rows}
    except:
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

def carregar_servicos_por_salao(salao_id):
    salao_id_clean = urllib.parse.unquote(str(salao_id)).strip().lower() if salao_id else "padrao"
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT nome, preco FROM servicos WHERE usuario_id = :user"), {"user": salao_id_clean})
            rows = result.fetchall()
            if rows:
                return {row[0]: float(row[1]) for row in rows}
    except:
        pass
    return {"Corte de Cabelo": 25.00, "Barba": 25.00, "Combo Cabelo e Barba": 50.00}

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

def deletar_servico_banco(nome):
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM servicos WHERE usuario_id = :user AND nome = :nome"), {"user": usuario, "nome": nome})

def carregar_fluxo():
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, data, tipo, descricao, valor FROM fluxo_caixa WHERE usuario_id = :user ORDER BY id DESC"), {"user": usuario})
            rows = result.fetchall()
            if rows:
                df = pd.DataFrame(rows, columns=['id', 'Data', 'Tipo', 'Descrição', 'Valor'])
                df['Data'] = pd.to_datetime(df['Data'])
                return df
    except:
        pass
    return pd.DataFrame(columns=["id", "Data", "Tipo", "Descrição", "Valor"])

def inserir_movimentacao_direta(tipo, descricao, valor, data_input):
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    data_str = data_input.strftime('%Y-%m-%d') if hasattr(data_input, 'strftime') else str(data_input)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO fluxo_caixa (usuario_id, data, tipo, descricao, valor)
            VALUES (:user, :data, :tipo, :descricao, :valor)
        """), {"user": usuario, "data": data_str, "tipo": tipo, "descricao": descricao, "valor": float(valor)})

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

def deletar_movimentacao_fluxo(id_registro):
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM fluxo_caixa WHERE id = :id AND usuario_id = :user"), {"id": int(id_registro), "user": usuario})

def carregar_agendamentos():
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
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

def deletar_agendamento(id_agendamento):
    usuario = str(st.session_state.usuario_logado).strip().lower() if st.session_state.get("usuario_logado") else "padrao"
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM agendamentos WHERE id = :id AND usuario_id = :user"), {"id": int(id_agendamento), "user": usuario})

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

# --- INICIALIZAÇÃO DE ESTADOS ---
if 'formulario_ativo' not in st.session_state: st.session_state.formulario_ativo = 'none'
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'usuario_logado' not in st.session_state: st.session_state.usuario_logado = None
if 'eh_admin' not in st.session_state: st.session_state.eh_admin = False
if 'recuperando_senha' not in st.session_state: st.session_state.recuperando_senha = False

def gerar_pdf_contabilidade(df, mes_ref):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=16, spaceAfter=15)
    story.append(Paragraph(f"Relatório para Contabilidade ({mes_ref})", title_style))

    table_data = [["Data", "Tipo", "Descrição", "Valor"]]
    for _, row in df.iterrows():
        dt_str = row['Data'].strftime('%d/%m/%Y') if hasattr(row['Data'], 'strftime') else str(row['Data'])
        table_data.append([dt_str, str(row['Tipo']), str(row['Descrição']), f"R$ {row['Valor']:.2f}"])
    t = Table(table_data, colWidths=[75, 60, 265, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ==============================================================================
# --- ROTA PÚBLICA EXCLUSIVA PARA O CLIENTE (?salao=nome) ---
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
        "15:00", "15:30", "16:00", "16:30", "17:00", "17:30", 
        "18:00", "18:30", "19:00"
    ]

    servicos_salao = carregar_servicos_por_salao(salao_id_clean)

    st.header(f"Agendamento - {nome_salao_formatado}")

    with st.form("form_agendamento_cliente", clear_on_submit=True):
        nome_cliente = st.text_input("Seu Nome Completo:")
        telefone_cliente = st.text_input("Seu WhatsApp (com DDD):")
        
        if servicos_salao:
            servico_escolhido = st.selectbox("Escolha o Serviço Desejado:", list(servicos_salao.keys()))
        else:
            st.warning("Nenhum serviço disponível no momento.")
            servico_escolhido = None

        data_escolhida = st.date_input("Escolha o Dia:", min_value=datetime.now(TZ).date())
        data_str = data_escolhida.strftime("%Y-%m-%d")

        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT hora FROM agendamentos WHERE usuario_id = :user AND data = :dt"), 
                    {"user": salao_id_clean, "dt": data_str}
                )
                ocupados = [r[0] for r in result.fetchall()]
        except:
            ocupados = []

        horarios_livres = [h for h in HORARIOS_DISPONIVEIS if h not in ocupados]

        if horarios_livres:
            horario_escolhido = st.selectbox("Horários Disponíveis:", horarios_livres)
        else:
            st.error("Sem horários disponíveis nesta data. Escolha outro dia.")
            horario_escolhido = None

        enviar_agendamento = st.form_submit_button("Confirmar Agendamento", use_container_width=True)

    if enviar_agendamento:
        if not nome_cliente or not telefone_cliente:
            st.warning("Preencha seu nome e telefone para contato.")
        elif not horario_escolhido or not servico_escolhido:
            st.error("Escolha um serviço e horário válidos.")
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
                st.success(f"Agendamento confirmado para {nome_cliente}!")
                time.sleep(1.5)
                st.rerun()

            except Exception as e:
                st.error(f"Erro ao salvar agendamento: {e}")

    st.stop()

# ==============================================================================
# --- CONTROLE DE ACESSO INTERNO ---
# ==============================================================================
admin_hash1, admin_hash2, url_sistema_salva = carregar_admin_hashes()
usuarios_cadastrados = carregar_usuarios()

if not st.session_state.autenticado:
    if not admin_hash1 or not admin_hash2:
        st.title("Configuração Inicial de Segurança")
        st.warning("Defina as credenciais mestre de Administrador do sistema abaixo:")
        with st.form("primeiro_acesso"):
            nova_adm_pass1 = st.text_input("Senha PRINCIPAL de ADMIN:", type="password")
            nova_adm_pass2 = st.text_input("Senha SECUNDÁRIA de ADMIN:", type="password")
            url_padrao_app = st.text_input("URL do App de AGENDAMENTO (Ex: https://seuapp.streamlit.app):")
            if st.form_submit_button("Criar Acesso Seguro"):
                if nova_adm_pass1 and nova_adm_pass2:
                    salvar_admin_hashes(nova_adm_pass1, nova_adm_pass2, url_padrao_app.strip())
                    st.success("Configuração inicial salva! Recarregando...")
                    time.sleep(1.5)
                    st.rerun()
        st.stop()

    if st.session_state.recuperando_senha:
        st.title("Recuperação de Senha")
        with st.form("form_recuperacao"):
            user_recup = st.text_input("Seu Usuário:").strip().lower()
            email_recup = st.text_input("Seu E-mail Cadastrado:").strip().lower()
            nova_senha_recup = st.text_input("Nova Senha de Acesso:", type="password")
            conf_senha_recup = st.text_input("Confirme a Nova Senha:", type="password")
            c_rec1, c_rec2 = st.columns(2)
            with c_rec1:
                if st.form_submit_button("Atualizar Senha"):
                    if user_recup in usuarios_cadastrados and usuarios_cadastrados[user_recup].get("email") == email_recup:
                        if nova_senha_recup == conf_senha_recup and nova_senha_recup:
                            usuarios_cadastrados[user_recup]["senha"] = hash_password(nova_senha_recup)
                            salvar_usuarios(usuarios_cadastrados)
                            st.success("Senha redefinida com sucesso!")
                            st.session_state.recuperando_senha = False
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error("As senhas informadas não coincidem.")
                    else:
                        st.error("Usuário ou e-mail não encontrado.")
            with c_rec2:
                if st.form_submit_button("Cancelar"):
                    st.session_state.recuperando_senha = False
                    st.rerun()
        st.stop()

    st.title("Sistema de Gestão - Login")
    tipo_acesso = st.radio("Tipo de Acesso:", ["Usuário", "Administrador Mestre"], horizontal=True)
    with st.form("form_login"):
        usuario_input = st.text_input("Usuário:").strip().lower()
        senha_input = st.text_input("Senha:", type="password")
        senha2_input = st.text_input("Senha Secundária:", type="password") if tipo_acesso == "Administrador Mestre" else ""
        if st.form_submit_button("Entrar"):
            if tipo_acesso == "Administrador Mestre":
                if usuario_input == "admin" and hash_password(senha_input) == admin_hash1 and hash_password(senha2_input) == admin_hash2:
                    st.session_state.autenticado = True
                    st.session_state.usuario_logado = "Administrador"
                    st.session_state.eh_admin = True
                    st.rerun()
                else:
                    st.error("Credenciais de Administrador incorretas.")
            else:
                if usuario_input in usuarios_cadastrados and usuarios_cadastrados[usuario_input]["senha"] == hash_password(senha_input):
                    dados_user = usuarios_cadastrados[usuario_input]
                    data_vencimento = datetime.strptime(dados_user["vencimento"], "%Y-%m-%d").date()
                    if datetime.now(TZ).date() > data_vencimento or dados_user.get("status") == "Suspenso":
                        st.error("Acesso bloqueado: Licença vencida ou suspensa.")
                        st.stop()
                    st.session_state.autenticado = True
                    st.session_state.usuario_logado = usuario_input
                    st.session_state.eh_admin = False
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
    if st.button("Esqueci minha senha"):
        st.session_state.recuperando_senha = True
        st.rerun()
    st.stop()

# --- INTERFACE 1: ADMINISTRADOR MESTRE ---
if st.session_state.eh_admin:
    st.title("Central do Administrador")
    tab_cad, tab_ger, tab_config = st.tabs(["Cadastrar/Renovar", "Gerenciar Contas", "Configurações"])

    with tab_cad:
        with st.form("form_cadastro_cliente"):
            novo_usuario = st.text_input("Nome de Usuário:").strip().lower()
            novo_email = st.text_input("E-mail de Recuperação:").strip().lower()
            nova_senha = st.text_input("Senha de Acesso:", type="password").strip()
            tipo_conta = st.selectbox("Tipo de Conta:", ["Teste", "Cliente"])
            dias_validate = st.number_input("Dias de Validade:", min_value=1, value=30)
            if st.form_submit_button("Salvar Cadastro"):
                if novo_usuario and nova_senha and novo_email:
                    vencimento_calculado = (datetime.now(TZ) + timedelta(days=dias_validate)).strftime("%Y-%m-%d")
                    usuarios_cadastrados[novo_usuario] = { "senha": hash_password(nova_senha), "email": novo_email, "tipo": tipo_conta, "vencimento": vencimento_calculado, "status": "Ativo" }
                    salvar_usuarios(usuarios_cadastrados)
                    st.success("Cadastro efetuado com sucesso!")
                    st.rerun()

    with tab_ger:
        usuarios_cadastrados = carregar_usuarios()
        if not usuarios_cadastrados:
            st.info("Nenhuma conta cadastrada.")
        else:
            salao_sel = st.selectbox("Selecione a Conta:", list(usuarios_cadastrados.keys()))
            dados = usuarios_cadastrados[salao_sel]
            with st.form("form_edicao_conta"):
                e_email = st.text_input("E-mail:", value=dados.get("email", ""))
                e_senha_nova = st.text_input("Nova Senha (deixe em branco para manter):", type="password")
                e_tipo = st.selectbox("Tipo:", ["Teste", "Cliente"], index=0 if dados['tipo'] == "Teste" else 1)
                e_venc = st.date_input("Vencimento:", datetime.strptime(dados['vencimento'], "%Y-%m-%d"))
                e_status = st.selectbox("Status:", ["Ativo", "Suspenso"], index=0 if dados['status'] == "Ativo" else 1)
                
                if st.form_submit_button("Salvar Alterações"):
                    senha_final = hash_password(e_senha_nova) if e_senha_nova else dados['senha']
                    usuarios_cadastrados[salao_sel] = { "senha": senha_final, "email": e_email.strip().lower(), "tipo": e_tipo, "vencimento": e_venc.strftime("%Y-%m-%d"), "status": e_status }
                    salvar_usuarios(usuarios_cadastrados)
                    st.success("Conta atualizada!")
                    st.rerun()

            if st.checkbox(f"Confirmar exclusão definitiva de: {salao_sel}"):
                if st.button("EXCLUIR CONTA", type="primary"):
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": salao_sel})
                    st.warning("Conta removida com sucesso!")
                    st.rerun()

    with tab_config:
        nova_url_input = st.text_input("URL Padrão do Sistema de Agendamento:", value=url_sistema_salva if url_sistema_salva else "")
        if st.button("Salvar URL"):
            atualizar_url_sistema(nova_url_input.strip())
            st.success("URL salva com sucesso!")
            time.sleep(1)
            st.rerun()

    with st.sidebar:
        if st.button("Sair do Modo Admin", use_container_width=True):
            st.session_state.autenticado = False
            st.rerun()
    st.stop()

# --- INTERFACE 2: PAINEL INTERNO DO USUÁRIO ---
df_fluxo_caixa = carregar_fluxo()
servicos = carregar_servicos()

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

base_url = (url_sistema_salva or "https://fioecaixa-agendar.streamlit.app").rstrip('/')
link_clientes = f"{base_url}/?salao={st.session_state.usuario_logado}"
nome_sistema_titulo = st.session_state.usuario_logado.replace('_', ' ').replace('-', ' ').title()

mensagem_whatsapp = f"Olá! Agende seu horário: {link_clientes}"
wa_url_geral = f"https://api.whatsapp.com/send?text={urllib.parse.quote(mensagem_whatsapp)}"

tab1, tab0, tab_agend, tab2 = st.tabs(["Dashboard", "Ações Rápidas", "Agendamentos", "Histórico"])

with tab1:
    st.subheader("Resumo Financeiro")
    st.metric("Fechamento do Dia", f"R$ {lucro_dia:.2f}")
    st.metric("Acumulado 7 Dias", f"R$ {lucro_sem:.2f}")
    st.metric("Faturamento do Mês", f"R$ {lucro_mes:.2f}")

with tab0:
    st.subheader("Ações Rápidas")
    
    opcao_acao = st.selectbox("Selecione a Ação:", [
        "Selecionar Ação...",
        "Novo Atendimento / Entrada", 
        "Nova Despesa / Saída", 
        "Marcar Fiado (Pendente)", 
        "Receber Fiado (Baixa)"
    ])

    if opcao_acao == "Novo Atendimento / Entrada":
        with st.form("f_atend"):
            if list(servicos.keys()):
                servico_selecionado = st.selectbox("Serviço:", list(servicos.keys()))
                preco_final = st.number_input("Valor (R$):", value=float(servicos[servico_selecionado]), step=1.0)
                data_entrada = st.date_input("Data:", datetime.now(TZ).date())
                if st.form_submit_button("Lançar Entrada"):
                    inserir_movimentacao_direta("Entrada", f"Atendimento: {servico_selecionado}", preco_final, data_entrada)
                    st.success("Lançado com sucesso!")
                    time.sleep(0.5)
                    st.rerun()

    elif opcao_acao == "Nova Despesa / Saída":
        with st.form("f_saida"):
            descricao_saida = st.text_input("Descrição da Despesa:")
            valor_saida = st.number_input("Valor (R$):", min_value=0.0, step=5.0)
            data_saida = st.date_input("Data:", datetime.now(TZ).date())
            if st.form_submit_button("Lançar Despesa"):
                if descricao_saida and valor_saida > 0:
                    inserir_movimentacao_direta("Saída", descricao_saida, -valor_saida, data_saida)
                    st.success("Despesa lançada!")
                    time.sleep(0.5)
                    st.rerun()

    elif opcao_acao == "Marcar Fiado (Pendente)":
        with st.form("f_fiado"):
            if list(servicos.keys()):
                nome_devedor = st.text_input("Nome do Cliente:")
                servico_pendente = st.selectbox("Serviço:", list(servicos.keys()))
                preco_final_p = st.number_input("Valor:", value=float(servicos[servico_pendente]))
                data_pendencia = st.date_input("Data:", datetime.now(TZ).date())
                if st.form_submit_button("Salvar Fiado"):
                    if nome_devedor:
                        inserir_movimentacao_direta("Pendência", f"Fiado de: {nome_devedor} ({servico_pendente})", preco_final_p, data_pendencia)
                        st.success("Fiado registrado!")
                        time.sleep(0.5)
                        st.rerun()

    elif opcao_acao == "Receber Fiado (Baixa)":
        df_pendencias = df_fluxo_caixa[df_fluxo_caixa['Tipo'] == 'Pendência']
        if not df_pendencias.empty:
            with st.form("f_baixa"):
                opcoes_pendentes = {f"{row['Descrição']} - R$ {abs(row['Valor']):.2f}": row['id'] for _, row in df_pendencias.iterrows()}
                pendencia_selecionada = st.selectbox("Selecione o Fiado:", list(opcoes_pendentes.keys()))
                if st.form_submit_button("Dar Baixa (Recebido)"):
                    id_alterar = opcoes_pendentes[pendencia_selecionada]
                    row_atual = df_pendencias[df_pendencias['id'] == id_alterar].iloc[0]
                    nova_desc = row_atual['Descrição'].replace("Fiado de:", "Recebido Fiado:") + " [PAGO]"
                    dar_baixa_fiado_direta(id_alterar, nova_desc)
                    st.success("Baixa realizada!")
                    time.sleep(0.5)
                    st.rerun()
        else:
            st.info("Nenhum fiado pendente no momento.")

with tab_agend:
    st.subheader("Gerenciamento de Agendamentos")
    st.text("Link para clientes agendarem:")
    st.code(link_clientes, language="text")
    st.link_button("Compartilhar link no WhatsApp", wa_url_geral, use_container_width=True)

    df_agendamentos = carregar_agendamentos()

    if not df_agendamentos.empty:
        df_display = df_agendamentos.copy()
        try:
            df_display['Data'] = pd.to_datetime(df_display['Data']).dt.strftime('%d/%m/%Y')
        except:
            pass
            
        st.dataframe(df_display.drop(columns=['id'], errors='ignore'), use_container_width=True, hide_index=True)

        st.markdown("---")
        opcoes_agend = {f"{row['Cliente']} - {row['Data']} às {row['Horário']}": row['id'] for _, row in df_agendamentos.iterrows()}
        agend_selecionado = st.selectbox("Selecionar Agendamento para Ação:", list(opcoes_agend.keys()))
        id_sel = opcoes_agend[agend_selecionado]
        
        row_ag = df_agendamentos[df_agendamentos['id'] == id_sel].iloc[0]
        num_clean = re.sub(r'\D', '', str(row_ag['Contato/WhatsApp']))

        if num_clean:
            if not num_clean.startswith('55') and len(num_clean) <= 11:
                num_clean = '55' + num_clean
            msg_cli = urllib.parse.quote(f"Olá {row_ag['Cliente']}, confirmando seu horário para {row_ag['Data']} às {row_ag['Horário']}.")
            st.link_button("Chamar Cliente no WhatsApp", f"https://api.whatsapp.com/send?phone={num_clean}&text={msg_cli}", use_container_width=True)

        if st.button("Concluir / Remover Agendamento", use_container_width=True):
            deletar_agendamento(id_sel)
            st.success("Removido com sucesso!")
            time.sleep(0.5)
            st.rerun()
    else:
        st.info("Nenhum agendamento encontrado.")

with st.sidebar:
    st.title(f"Painel: {nome_sistema_titulo}")
    st.link_button("Compartilhar Link", wa_url_geral, use_container_width=True)
    st.markdown("---")

    opcoes_gerenciamento = ["➕ Cadastrar Novo Serviço"] + list(servicos.keys())
    servico_sel = st.selectbox("Gerenciar Serviços:", opcoes_gerenciamento)
    nome_padrao = "" if servico_sel == "➕ Cadastrar Novo Serviço" else servico_sel
    preco_padrao = 0.0 if servico_sel == "➕ Cadastrar Novo Serviço" else float(servicos[servico_sel])
    
    novo_servico = st.text_input("Nome:", value=nome_padrao)
    novo_preco = st.number_input("Preço (R$):", min_value=0.0, value=preco_padrao, step=5.0)

    if st.button("Salvar Serviço", use_container_width=True):
        if novo_servico:
            salvar_ou_atualizar_servico(servico_sel, novo_servico, novo_preco)
            st.success("Salvo com sucesso!")
            time.sleep(0.5)
            st.rerun()

    if servico_sel != "➕ Cadastrar Novo Serviço" and st.button("Remover Serviço", use_container_width=True):
        deletar_servico_banco(servico_sel)
        st.warning("Serviço removido.")
        time.sleep(0.5)
        st.rerun()

    st.markdown("---")
    backup_dados = gerar_backup_json_completo()
    st.download_button("Baixar Backup (.json)", data=backup_dados, file_name=f"backup_{st.session_state.usuario_logado}.json", mime="application/json", use_container_width=True)

    if st.button("Sair do Sistema", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()

with tab2:
    st.subheader("Histórico e Relatórios")
    if not df_fluxo_caixa.empty:
        df_filtro = df_fluxo_caixa.dropna(subset=['Data']).copy()
        df_filtro['Mês/Ano'] = df_filtro['Data'].dt.strftime('%m/%Y')

        meses = sorted(df_filtro['Mês/Ano'].unique(), reverse=True)
        mes_escolhido = st.selectbox("Filtrar por Mês:", ["Ver Tudo"] + meses)
        df_exibicao = df_filtro[df_filtro['Mês/Ano'] == mes_escolhido] if mes_escolhido != "Ver Tudo" else df_filtro

        if not df_exibicao.empty:
            c1, c2 = st.columns(2)
            with c1:
                st.download_button("Baixar CSV", data=df_exibicao.drop(columns=['id', 'Mês/Ano'], errors='ignore').to_csv(index=False).encode('utf-8-sig'), file_name="relatorio.csv", mime="text/csv", use_container_width=True)
            with c2:
                st.download_button("Baixar PDF", data=gerar_pdf_contabilidade(df_exibicao.drop(columns=['id', 'Mês/Ano'], errors='ignore'), mes_escolhido), file_name="relatorio.pdf", mime="application/pdf", use_container_width=True)
            
            df_vis = df_exibicao.sort_index(ascending=False).copy()
            df_vis['Data'] = df_vis['Data'].dt.strftime('%d/%m/%Y')
            st.dataframe(df_vis.drop(columns=['id', 'Mês/Ano'], errors='ignore'), use_container_width=True, hide_index=True)
            
            st.markdown("---")
            opcoes_del_fluxo = {f"#{row['id']} - {row['Data'].strftime('%d/%m')} - {row['Tipo']}: {row['Descrição']} (R$ {row['Valor']:.2f})": row['id'] for _, row in df_exibicao.iterrows()}
            reg_selecionado = st.selectbox("Excluir Lançamento:", list(opcoes_del_fluxo.keys()))
            if st.button("Apagar Lançamento Selecionado", use_container_width=True):
                deletar_movimentacao_fluxo(opcoes_del_fluxo[reg_selecionado])
                st.warning("Removido com sucesso.")
                time.sleep(1)
                st.rerun()
        else:
            st.info("Sem registros para este período.")
    else:
        st.info("Nenhuma movimentação registrada.")

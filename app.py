import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import json
import time
import hashlib
from io import BytesIO

# Bibliotecas de Conexão Direta SQL
from sqlalchemy import create_engine, text

# Relatórios e Segurança
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- CONFIGURAÇÃO DE SEGURANÇA E HORÁRIO ---
SALT = "salao_fio_caixa_2026_security"
TZ = ZoneInfo("America/Sao_Paulo")

def hash_password(password):
    return hashlib.sha256((password + SALT).encode()).hexdigest()

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Financeira - Salão", layout="wide", page_icon="✂️")

# --- INJEÇÃO DE CSS CUSTOMIZADO (OTIMIZADO PARA MOBILE) ---
st.markdown("""
<style>
    body, .stApp { background-color: #121212 !important; color: #ffffff !important; }
    .stApp p, .stApp span, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {
        color: #ffffff !important;
    }
    [data-testid="stHeader"], header { display: none !important; visibility: hidden !important; height: 0px !important; }
    .block-container { padding-top: 2rem !important; }
    button[data-testid="stSidebarCollapseButton"] { color: #d4af37 !important; background-color: #1e222b !important; border: 2px solid #d4af37 !important; border-radius: 6px !important; }
    
    div[data-testid="stTextInput"] input, div[data-testid="stSelectbox"] [data-baseweb="select"] > div, div[data-testid="stDateInput"] input {
        background-color: #1e222b !important; color: #ffffff !important; border: 2px solid #4f5b66 !important; border-radius: 6px !important; padding: 10px !important;
    }
    div[data-testid="stNumberInput"] div[data-baseweb="input"] { background-color: #1e222b !important; border: 2px solid #4f5b66 !important; }
    div[data-testid="stNumberInput"] input { color: #ffffff !important; }
    div[data-testid="stNumberInput"] button { background-color: #33363c !important; color: #d4af37 !important; border: 1px solid #4f5b66 !important; }
    
    div.stButton > button, div[data-testid="stFormSubmitButton"] button {
        background-color: #d4af37 !important; color: #121212 !important; border: 2px solid #d4af37 !important; border-radius: 6px !important; width: 100% !important; font-weight: bold !important; font-size: 1rem !important; padding: 10px !important; box-shadow: 0px 4px 10px rgba(212, 175, 55, 0.2) !important;
    }
    div.stButton > button:hover, div[data-testid="stFormSubmitButton"] button:hover { background-color: #ffffff !important; color: #121212 !important; border-color: #ffffff !important; }
    .sim-header { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #333; margin-bottom: 20px; }
    .sim-header-title { color: #d4af37; font-weight: bold; font-size: 1.2rem; }
    .fast-actions-header { display: flex; align-items: center; margin-bottom: 15px; }
    .fast-actions-title { color: white; font-weight: bold; font-size: 1rem; margin-right: 10px; }
    .fast-actions-line { flex-grow: 1; height: 2px; background-color: #d4af37; }
    .embedded-form-container { margin-top: 15px; background-color: #1a1d21; padding: 15px; border-radius: 8px; border: 1px solid #d4af37; }
</style>
""", unsafe_allow_html=True)

# --- CAPTURA DA DATABASE DIRETAMENTE DOS SECRETS ---
if "DB_URL" in st.secrets:
    DB_URL = st.secrets["DB_URL"]
else:
    st.error("❌ ERRO CRÍTICO: A variável 'DB_URL' não foi configurada nos Secrets do Streamlit Cloud.")
    st.info("Por favor, adicione a linha DB_URL = '...' nas configurações (Secrets) do painel do Streamlit.")
    st.stop()

# Inicialização da Engine de Banco de Dados
@st.cache_resource
def init_connection(url):
    return create_engine(url, pool_pre_ping=True)

try:
    engine = init_connection(DB_URL)
except Exception as e:
    st.error(f"Erro crítico ao instanciar o motor do banco de dados: {e}")
    st.stop()

# --- FUNÇÕES DE PERSISTÊNCIA (SQL DIRECT) ---

def carregar_admin_hashes():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT hash1, hash2 FROM admin_config WHERE id = 1")).fetchone()
            if result:
                return result[0], result[1]
    except Exception as e:
        # Se o erro for apenas que a tabela não existe (banco novo), permite criar.
        # Qualquer outro erro (como falha de conexão/senha) vai travar e exibir o motivo real.
        if "relation" in str(e) and "does not exist" in str(e):
            return None, None
        st.error(f"❌ Erro de Conexão com o Banco de Dados Supabase: {e}")
        st.stop()
    return None, None

def salvar_admin_hashes(password1, password2):
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO admin_config (id, hash1, hash2) VALUES (1, :h1, :h2)
                ON CONFLICT (id) DO UPDATE SET hash1 = EXCLUDED.hash1, hash2 = EXCLUDED.hash2
            """), {"h1": hash_password(password1), "h2": hash_password(password2)})
    except Exception as e:
        st.error(f"Erro ao salvar hashes administrativos: {e}")
        st.stop()

def carregar_usuarios():
    try:
        with engine.connect() as conn:
            df = pd.read_sql("SELECT * FROM usuarios", conn)
            if not df.empty:
                return {row['id']: dict(row) for _, row in df.iterrows()}
    except:
        pass
    return {}

def salvar_usuarios(usuarios_dict):
    if not usuarios_dict: return
    with engine.begin() as conn:
        for k, v in usuarios_dict.items():
            conn.execute(text("""
                INSERT INTO usuarios (id, senha, email, tipo, vencimento, status)
                VALUES (:id, :senha, :email, :tipo, :vencimento, :status)
                ON CONFLICT (id) DO UPDATE SET 
                    senha = EXCLUDED.senha, email = EXCLUDED.email, 
                    tipo = EXCLUDED.tipo, vencimento = EXCLUDED.vencimento, status = EXCLUDED.status
            """), {
                "id": k, "senha": v["senha"], "email": v.get("email", ""),
                "tipo": v["tipo"], "vencimento": str(v["vencimento"]), "status": v["status"]
            })

def carregar_servicos():
    usuario = st.session_state.usuario_logado if st.session_state.get("usuario_logado") else "padrao"
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text("SELECT nome, preco FROM servicos WHERE usuario_id = :user"), conn, params={"user": usuario})
            if not df.empty:
                return {row['nome']: float(row['preco']) for _, row in df.iterrows()}
    except:
        pass
    return {"Corte de Cabelo": 25.00, "Barba": 25.00, "Combo Cabelo e Barba": 50.00}

def salvar_servicos(servicos):
    usuario = st.session_state.usuario_logado if st.session_state.get("usuario_logado") else "padrao"
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM servicos WHERE usuario_id = :user"), {"user": usuario})
        for k, v in servicos.items():
            conn.execute(text("INSERT INTO servicos (usuario_id, nome, preco) VALUES (:user, :nome, :preco)"),
                         {"user": usuario, "nome": k, "preco": float(v)})

def carregar_fluxo():
    usuario = st.session_state.usuario_logado if st.session_state.get("usuario_logado") else "padrao"
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text("SELECT data, tipo, descricao, valor FROM fluxo_caixa WHERE usuario_id = :user"), conn, params={"user": usuario})
            if not df.empty:
                df = df.rename(columns={"data": "Data", "tipo": "Tipo", "descricao": "Descrição", "valor": "Valor"})
                df['Data'] = pd.to_datetime(df['Data'])
                return df[['Data', 'Tipo', 'Descrição', 'Valor']]
    except:
        pass
    return pd.DataFrame(columns=["Data", "Tipo", "Descrição", "Valor"])

def salvar_fluxo(df):
    usuario = st.session_state.usuario_logado if st.session_state.get("usuario_logado") else "padrao"
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM fluxo_caixa WHERE usuario_id = :user"), {"user": usuario})
        if not df.empty:
            for _, row in df.iterrows():
                conn.execute(text("INSERT INTO fluxo_caixa (usuario_id, data, tipo, descricao, valor) VALUES (:user, :data, :tipo, :descricao, :valor)"),
                             {
                                 "user": usuario,
                                 "data": row['Data'].strftime('%Y-%m-%d') if hasattr(row['Data'], 'strftime') else str(row['Data']),
                                 "tipo": row['Tipo'],
                                 "descricao": row['Descrição'],
                                 "valor": float(row['Valor'])
                             })

# --- INICIALIZAÇÃO DE ESTADOS ---
if 'formulario_ativo' not in st.session_state: st.session_state.formulario_ativo = 'none'
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'usuario_logado' not in st.session_state: st.session_state.usuario_logado = None
if 'eh_admin' not in st.session_state: st.session_state.eh_admin = False
if 'recuperando_senha' not in st.session_state: st.session_state.recuperando_senha = False

# --- GERAÇÃO DE PDF ---
def gerar_pdf_contabilidade(df, mes_ref):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor("#d4af37"), spaceAfter=15)
    story.append(Paragraph(f"Fio&Caixa - Relatório para Contabilidade ({mes_ref})", title_style))
    
    table_data = [["Data", "Tipo", "Descrição", "Valor"]]
    for _, row in df.iterrows():
        dt_str = row['Data'].strftime('%d/%m/%Y') if hasattr(row['Data'], 'strftime') else str(row['Data'])
        table_data.append([dt_str, str(row['Tipo']), str(row['Descrição']), f"R$ {row['Valor']:.2f}"])
        
    t = Table(table_data, colWidths=[75, 60, 265, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#22252a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#d4af37")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# --- CONTROLE DE ACESSO ---
admin_hash1, admin_hash2 = carregar_admin_hashes()
usuarios_cadastrados = carregar_usuarios()

if not st.session_state.autenticado:
    if not admin_hash1 or not admin_hash2:
        st.title("⚠️ Configuração Inicial de Segurança")
        st.warning("Nenhum Administrador Mestre encontrado no banco de dados. Configure suas senhas master abaixo:")
        with st.form("primeiro_acesso"):
            nova_adm_pass1 = st.text_input("Definir Senha PRINCIPAL de ADMIN:", type="password")
            nova_adm_pass2 = st.text_input("Definir Senha SECUNDÁRIA de ADMIN:", type="password")
            if st.form_submit_button("Criar Acesso Seguro"):
                if nova_adm_pass1 and nova_adm_pass2:
                    salvar_admin_hashes(nova_adm_pass1, nova_adm_pass2)
                    st.success("Administrador configurado! Reiniciando...")
                    time.sleep(1.5)
                    st.rerun()
        st.stop()

    if st.session_state.recuperando_senha:
        st.title("🔑 Recuperação de Senha Segura")
        with st.form("form_recuperacao"):
            user_recup = st.text_input("Seu Usuário do Salão:").strip().lower()
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
                            st.success("✅ Senha redefinida no Banco de Dados!")
                            st.session_state.recuperando_senha = False
                            time.sleep(1.5); st.rerun()
                    else: st.error("Usuário ou e-mail correspondente não encontrado.")
            with c_rec2:
                if st.form_submit_button("Cancelar"): st.session_state.recuperando_senha = False; st.rerun()
        st.stop()

    st.title("✂️ Sistema de Gestão - Login")
    tipo_acesso = st.radio("Selecione o Tipo de Acesso:", ["Usuário / Salão", "Administrador Mestre"], horizontal=True)
    
    with st.form("form_login"):
        usuario_input = st.text_input("Usuário do Salão:").strip().lower()
        senha_input = st.text_input("Senha:", type="password")
        senha2_input = st.text_input("Senha Secundária:", type="password") if tipo_acesso == "Administrador Mestre" else ""
            
        if st.form_submit_button("Entrar no Sistema"):
            if tipo_acesso == "Administrador Mestre":
                if usuario_input == "admin" and hash_password(senha_input) == admin_hash1 and hash_password(senha2_input) == admin_hash2:
                    st.session_state.autenticado = True
                    st.session_state.usuario_logado = "Administrador"
                    st.session_state.eh_admin = True
                    st.rerun()
                else: st.error("Credenciais de Administrador incorretas.")
            else:
                if usuario_input in usuarios_cadastrados and usuarios_cadastrados[usuario_input]["senha"] == hash_password(senha_input):
                    dados_user = usuarios_cadastrados[usuario_input]
                    data_vencimento = datetime.strptime(dados_user["vencimento"], "%Y-%m-%d").date()
                    if datetime.now(TZ).date() > data_vencimento or dados_user.get("status") == "Suspenso":
                        st.error("❌ ACESSO BLOQUEADO! Licença vencida ou suspensa.")
                        st.stop()
                    st.session_state.autenticado = True
                    st.session_state.usuario_logado = usuario_input
                    st.session_state.eh_admin = False
                    st.rerun()
                else: st.error("Usuário ou senha incorretos.")
            
    if st.button("Esqueci minha senha ❯"): st.session_state.recuperando_senha = True; st.rerun()
    st.stop()

# --- INTERFACE 1: ADMINISTRADOR MESTRE ---
if st.session_state.eh_admin:
    st.title("👑 Central do Administrador")
    tab_cad, tab_ger = st.tabs(["➕ Cadastrar/Renovar", "⚙️ Gerenciar Salões"])
    
    with tab_cad:
        with st.form("form_cadastro_cliente"):
            novo_usuario = st.text_input("Usuário do Salão (Minúsculo, sem espaços):").strip().lower()
            novo_email = st.text_input("E-mail de Recuperação:").strip().lower()
            nova_senha = st.text_input("Senha de Acesso:", type="password").strip()
            tipo_conta = st.selectbox("Tipo de Conta:", ["Teste", "Cliente"])
            dias_validade = st.number_input("Dias de Validade:", min_value=1, value=30)
            if st.form_submit_button("Salvar Salão"):
                if novo_usuario and nova_senha and novo_email:
                    vencimento_calculado = (datetime.now(TZ) + timedelta(days=dias_validade)).strftime("%Y-%m-%d")
                    usuarios_cadastrados[novo_usuario] = {
                        "senha": hash_password(nova_senha), "email": novo_email,
                        "tipo": tipo_conta, "vencimento": vencimento_calculado, "status": "Ativo"
                    }
                    salvar_usuarios(usuarios_cadastrados); st.success("Salão salvo com sucesso!"); st.rerun()

    with tab_ger:
        usuarios_cadastrados = carregar_usuarios()
        if not usuarios_cadastrados: st.info("Nenhum salão cadastrado.")
        else:
            salao_sel = st.selectbox("Selecione o Salão:", list(usuarios_cadastrados.keys()))
            dados = usuarios_cadastrados[salao_sel]
            
            with st.expander("📝 Editar Informações", expanded=True):
                e_email = st.text_input("E-mail:", value=dados.get("email", ""))
                e_senha_nova = st.text_input("Nova Senha (deixe em branco):", type="password")
                e_tipo = st.selectbox("Tipo:", ["Teste", "Cliente"], index=0 if dados['tipo'] == "Teste" else 1)
                e_venc = st.date_input("Vencimento:", datetime.strptime(dados['vencimento'], "%Y-%m-%d"))
                e_status = st.selectbox("Status:", ["Ativo", "Suspenso"], index=0 if dados['status'] == "Ativo" else 1)
                
                if st.button("Salvar Edição"):
                    senha_final = hash_password(e_senha_nova) if e_senha_nova else dados['senha']
                    usuarios_cadastrados[salao_sel] = {
                        "senha": senha_final, "email": e_email.strip().lower(),
                        "tipo": e_tipo, "vencimento": e_venc.strftime("%Y-%m-%d"), "status": e_status
                    }
                    salvar_usuarios(usuarios_cadastrados); st.success("Atualizado!"); st.rerun()

            if st.checkbox(f"Confirmar exclusão de: {salao_sel}"):
                if st.button("EXCLUIR DEFINITIVAMENTE", type="primary"):
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": salao_sel})
                    st.warning("Removido!"); st.rerun()

    with st.sidebar:
        if st.button("🚪 Sair do Modo ADM", use_container_width=True): st.session_state.autenticado = False; st.rerun()
    st.stop()

# --- INTERFACE 2: PAINEL DO CLIENTE ---
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

tab1, tab0, tab2 = st.tabs(["📊 Dashboard", "🚀 Início / Ações Rápidas", "📜 Histórico"])

with tab1:
    st.subheader("📊 Resumo Financeiro Estruturado")
    m1, m2, m3 = st.columns(3)
    m1.metric("Fechamento do Dia", f"R$ {lucro_dia:.2f}")
    m2.metric("Acumulado 7 Dias", f"R$ {lucro_sem:.2f}")
    m3.metric("Faturamento do Mês", f"R$ {lucro_mes:.2f}")
    st.markdown("---")
    st.bar_chart(pd.DataFrame({"Categoria": ["Entradas", "Saídas"], "Total (R$)": [ent_mes, abs(sai_mes)]}), x="Categoria", y="Total (R$)", color="#29b6f6")

with tab0:
    st.markdown('<div class="sim-header"><span class="sim-header-title">Fio&Caixa</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="fast-actions-header"><span class="fast-actions-title">Ações rápidas</span><div class="fast-actions-line"></div></div>', unsafe_allow_html=True)
    col_a, col_b, col_c, col_d, col_e = st.columns(5)
    
    with col_a:
        if st.button("✂️ Novo atendimento  ❯", key="btn_atend", use_container_width=True):
            st.session_state.formulario_ativo = 'none' if st.session_state.formulario_ativo == 'new_atendimento' else 'new_atendimento'
            st.rerun()
        if st.session_state.formulario_ativo == 'new_atendimento':
            st.markdown('<div class="embedded-form-container">', unsafe_allow_html=True)
            if list(servicos.keys()):
                servico_selecionado = st.selectbox("Serviço realizado:", list(servicos.keys()), key="f_atend_serv")
                preco_final = st.number_input("Valor Cobrado (R$):", value=float(servicos[servico_selecionado]), step=1.0, key=f"prc_atend_din_{servico_selecionado}")
                data_entrada = st.date_input("Data:", datetime.now(TZ).date(), key="f_atend_dt")
                if st.button("Lançar", type="primary", key="f_atend_save", use_container_width=True):
                    nova_linha = pd.DataFrame([{"Data": pd.to_datetime(data_entrada), "Tipo": "Entrada", "Descrição": f"Atendimento: {servico_selecionado}", "Valor": preco_final}])
                    salvar_fluxo(pd.concat([df_fluxo_caixa, nova_linha], ignore_index=True))
                    st.session_state.formulario_ativo = 'none'; time.sleep(0.5); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            
    with col_b:
        if st.button("🛍️ Nova despesa  ❯", key="btn_venda", use_container_width=True):
            st.session_state.formulario_ativo = 'none' if st.session_state.formulario_ativo == 'new_venda' else 'new_venda'
            st.rerun()
        if st.session_state.formulario_ativo == 'new_venda':
            st.markdown('<div class="embedded-form-container">', unsafe_allow_html=True)
            descricao_saida = st.text_input("Descrição:", key="f_venda_desc")
            valor_saida = st.number_input("Valor (R$):", min_value=0.0, step=5.0, key="f_venda_val")
            data_saida = st.date_input("Data:", datetime.now(TZ).date(), key="f_venda_dt")
            if st.button("Confirmar despesa", type="primary", key="f_venda_save", use_container_width=True):
                if descricao_saida and valor_saida > 0:
                    nova_linha = pd.DataFrame([{"Data": pd.to_datetime(data_saida), "Tipo": "Saída", "Descrição": descricao_saida, "Valor": -valor_saida}])
                    salvar_fluxo(pd.concat([df_fluxo_caixa, nova_linha], ignore_index=True))
                    st.session_state.formulario_ativo = 'none'; time.sleep(0.5); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            
    with col_c:
        if st.button("💰 Marcar fiado  ❯", key="btn_receber", use_container_width=True):
            st.session_state.formulario_ativo = 'none' if st.session_state.formulario_ativo == 'new_receber' else 'new_receber'
            st.rerun()
        if st.session_state.formulario_ativo == 'new_receber':
            st.markdown('<div class="embedded-form-container">', unsafe_allow_html=True)
            if list(servicos.keys()):
                nome_devedor = st.text_input("Cliente:", key="f_fiado_nome")
                servico_pendente = st.selectbox("Serviço:", list(servicos.keys()), key="f_fiado_serv")
                preco_final_p = st.number_input("Valor:", value=float(servicos[servico_pendente]), key=f"prc_fiado_din_{servico_pendente}")
                data_pendencia = st.date_input("Data:", datetime.now(TZ).date(), key="f_fiado_dt")
                if st.button("Salvar Fiado", type="primary", key="f_fiado_save", use_container_width=True):
                    if nome_devedor:
                        nova_linha = pd.DataFrame([{"Data": pd.to_datetime(data_pendencia), "Tipo": "Pendência", "Descrição": f"Fiado de: {nome_devedor} ({servico_pendente})", "Valor": preco_final_p}])
                        salvar_fluxo(pd.concat([df_fluxo_caixa, nova_linha], ignore_index=True))
                        st.session_state.formulario_ativo = 'none'; time.sleep(0.5); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            
    with col_d:
        if st.button("💸 Receber fiado  ❯", key="btn_pagar", use_container_width=True):
            st.session_state.formulario_ativo = 'none' if st.session_state.formulario_ativo == 'new_pagar' else 'new_pagar'
            st.rerun()
        if st.session_state.formulario_ativo == 'new_pagar':
            st.markdown('<div class="embedded-form-container">', unsafe_allow_html=True)
            df_pendencias = df_fluxo_caixa[df_fluxo_caixa['Tipo'] == 'Pendência']
            if not df_pendencias.empty:
                opcoes_pendentes = {f"{row['Descrição']} - R$ {abs(row['Valor']):.2f}": idx for idx, row in df_pendencias.iterrows()}
                pendencia_selecionada = st.selectbox("Selecione:", list(opcoes_pendentes.keys()), key="f_pago_sel")
                if st.button("Dar Baixa", type="primary", key="f_pago_save", use_container_width=True):
                    idx_alterar = opcoes_pendentes[pendencia_selecionada]
                    df_fluxo_caixa.at[idx_alterar, 'Tipo'] = 'Entrada'
                    df_fluxo_caixa.at[idx_alterar, 'Data'] = pd.to_datetime(datetime.now(TZ).date())
                    df_fluxo_caixa.at[idx_alterar, 'Descrição'] = df_fluxo_caixa.at[idx_alterar, 'Descrição'].replace("Fiado de:", "Recebido Fiado:") + " [PAGO]"
                    salvar_fluxo(df_fluxo_caixa)
                    st.session_state.formulario_ativo = 'none'; time.sleep(0.5); st.rerun()
            else: st.info("Sem fiados pendentes.")
            st.markdown('</div>', unsafe_allow_html=True)
            
    with col_e:
        if st.button("📊 Ver relatórios  ❯", key="btn_relatorios", use_container_width=True):
            st.session_state.formulario_ativo = 'none' if st.session_state.formulario_ativo == 'view_relatorios' else 'view_relatorios'
            st.rerun()
        if st.session_state.formulario_ativo == 'view_relatorios':
            st.markdown('<div class="embedded-form-container">', unsafe_allow_html=True)
            st.metric("Líquido Diário", f"R$ {lucro_dia:.2f}")
            st.metric("Líquido Mensal", f"R$ {lucro_mes:.2f}")
            st.markdown('</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Configurações")
    nome_salao = st.session_state.usuario_logado.replace("_", " ").title() if st.session_state.usuario_logado else "Salão"
    st.title(f"✂️ {nome_salao}")
    st.markdown("---")
    opcoes_gerenciamento = ["➕ Cadastrar Novo Serviço"] + list(servicos.keys())
    servico_sel = st.selectbox("Gerenciar serviços:", opcoes_gerenciamento)
    nome_padrao = "" if servico_sel == "➕ Cadastrar Novo Serviço" else servico_sel
    preco_padrao = 0.0 if servico_sel == "➕ Cadastrar Novo Serviço" else float(servicos[servico_sel])
    novo_servico = st.text_input("Nome do Serviço:", value=nome_padrao, key=f"side_nome_din_{servico_sel}")
    novo_preco = st.number_input("Preço Cobrado:", min_value=0.0, value=preco_padrao, step=5.0, key=f"side_prc_din_{servico_sel}")
    if st.button("Salvar Alteração", type="primary", use_container_width=True):
        if novo_servico:
            if servico_sel != "➕ Cadastrar Novo Serviço" and servico_sel != novo_servico: del servicos[servico_sel]
            servicos[novo_servico] = novo_preco; salvar_servicos(servicos); st.rerun()
    if servico_sel != "➕ Cadastrar Novo Serviço" and st.button("🗑️ Remover do Catálogo", use_container_width=True):
        del servicos[servico_sel]; salvar_servicos(servicos); st.rerun()
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("🚪 Sair do Sistema", use_container_width=True): st.session_state.autenticado = False; st.rerun()

with tab2:
    st.subheader("📜 Histórico de Transações Completas")
    if not df_fluxo_caixa.empty:
        df_filtro = df_fluxo_caixa.dropna(subset=['Data']).copy()
        df_filtro['Mês/Ano'] = df_filtro['Data'].dt.strftime('%m/%Y')
        meses = sorted(df_filtro['Mês/Ano'].unique(), reverse=True)
        mes_escolhido = st.selectbox("📅 Mês de referência:", ["Ver Tudo"] + meses)
        df_exibicao = df_filtro[df_filtro['Mês/Ano'] == mes_escolhido] if mes_escolhido != "Ver Tudo" else df_filtro
        
        if mes_escolhido != "Ver Tudo" and not df_exibicao.empty:
            col_down1, col_down2 = st.columns(2)
            with col_down1:
                st.download_button(label="📄 Baixar em CSV", data=df_exibicao.to_csv(index=False).encode('utf-8-sig'), file_name=f"contabilidade_{mes_escolhido.replace('/', '_')}.csv", mime="text/csv", use_container_width=True)
            with col_down2:
                st.download_button(label="📕 Baixar em PDF", data=gerar_pdf_contabilidade(df_exibicao, mes_escolhido), file_name=f"contabilidade_{mes_escolhido.replace('/', '_')}.pdf", mime="application/pdf", use_container_width=True)
            st.markdown("---")
            
        if not df_exibicao.empty:
            df_vis = df_exibicao.sort_index(ascending=False).copy()
            df_vis['Data'] = df_vis['Data'].dt.strftime('%d/%m/%Y')
            df_vis = df_vis.drop(columns=['Mês/Ano'])
            def colorir(row):
                if row['Tipo'] == 'Entrada': return ['background-color: #d4edda; color: #155724'] * 4
                elif row['Tipo'] == 'Saída': return ['background-color: #f8d7da; color: #721c24'] * 4
                return ['background-color: #fff3cd; color: #856404'] * 4
            st.dataframe(df_vis.style.apply(colorir, axis=1).format({"Valor": "R$ {:.2f}"}), use_container_width=True, hide_index=True)
    else: st.info("Nenhuma movimentação financeira registrada.")

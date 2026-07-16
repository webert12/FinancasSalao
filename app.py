import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import json
import time
import hashlib
from io import BytesIO

# --- Bibliotecas de Conexão Direta SQL ---
from sqlalchemy import create_engine, text

# --- Relatórios e Segurança ---
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

# --- INJEÇÃO DE CSS CUSTOMIZADO ---
st.markdown("""
<style>
/* CSS personalizado pode ser inserido aqui */
</style>
""", unsafe_allow_html=True)

# --- CAPTURA DA DATABASE DIRETAMENTE DOS SECRETS ---
if "DB_URL" in st.secrets:
    DB_URL = st.secrets["DB_URL"]
else:
    st.error("❌ ERRO CRÍTICO: A variável 'DB_URL' não foi configurada nos Secrets do Streamlit Cloud.")
    st.stop()

# --- Inicialização da Engine de Banco de Dados ---
@st.cache_resourced
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
        conn.execute(text("""CREATE TABLE IF NOT EXISTS admin_config (id INT PRIMARY KEY,hash1 TEXT NOT NULL,hash2 TEXT NOT NULL);"""))
        conn.execute(text("""CREATE TABLE IF NOT EXISTS usuarios (id TEXT PRIMARY KEY,senha TEXT NOT NULL,email TEXT,tipo TEXT,vencimento TEXT,status TEXT);"""))
        conn.execute(text("""CREATE TABLE IF NOT EXISTS servicos (id SERIAL PRIMARY KEY,usuario_id TEXT NOT NULL,nome TEXT NOT NULL,preco NUMERIC NOT NULL);"""))
        conn.execute(text("""CREATE TABLE IF NOT EXISTS fluxo_caixa (id SERIAL PRIMARY KEY,usuario_id TEXT NOT NULL,data TEXT NOT NULL,tipo TEXT NOT NULL,descricao TEXT NOT NULL,valor NUMERIC NOT NULL);"""))
        # NOVA TABELA PARA AGENDAMENTOS DOS CLIENTES
        conn.execute(text("""CREATE TABLE IF NOT EXISTS agendamentos (
            id SERIAL PRIMARY KEY,
            usuario_id TEXT NOT NULL,
            cliente_nome TEXT NOT NULL,
            cliente_contato TEXT,
            servico_nome TEXT NOT NULL,
            data TEXT NOT NULL,
            hora TEXT NOT NULL
        );"""))

try:
    inicializar_banco()
except Exception as e:
    st.error(f"Erro ao estruturar tabelas automáticas no Supabase: {e}")
    st.stop()

# --- FUNÇÕES DE PERSISTÊNCIA ---
def carregar_admin_hashes():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT hash1, hash2 FROM admin_config WHERE id = 1")).fetchone()
            if result:
                return result[0], result[1]
    except:
        pass
    return None, None

def salvar_admin_hashes(password1, password2):
    try:
        with engine.begin() as conn:
            conn.execute(text("""INSERT INTO admin_config (id, hash1, hash2) VALUES (1, :h1, :h2)ON CONFLICT (id) DO UPDATE SET hash1 = EXCLUDED.hash1, hash2 = EXCLUDED.hash2"""), {"h1": hash_password(password1), "h2": hash_password(password2)})
    except Exception as e:
        st.error(f"Erro ao salvar hashes administrativos: {e}")

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
            conn.execute(text("""INSERT INTO usuarios (id, senha, email, tipo, vencimento, status)VALUES (:id, :senha, :email, :tipo, :vencimento, :status)ON CONFLICT (id) DO UPDATE SETsenha = EXCLUDED.senha, email = EXCLUDED.email,tipo = EXCLUDED.tipo, vencimento = EXCLUDED.vencimento, status = EXCLUDED.status"""), {"id": k, "senha": v["senha"], "email": v.get("email", ""),"tipo": v["tipo"], "vencimento": str(v["vencimento"]), "status": v["status"]})

def carregar_servicos():
    usuario = st.session_state.usuario_logado if st.session_state.get("usuario_logado") else "padrao"
    return carregar_servicos_por_salao(usuario)

# Carrega serviços específicos de um salão (usado na tela pública do cliente)
def carregar_servicos_por_salao(salao_id):
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text("SELECT nome, preco FROM servicos WHERE usuario_id = :user"), conn, params={"user": salao_id})
            if not df.empty:
                return {row['nome']: float(row['preco']) for _, row in df.iterrows()}
    except:
        pass
    return {"Corte de Cabelo": 25.00, "Barba": 25.00, "Combo Cabelo e Barba": 50.00}

def salvar_ou_atualizar_servico(nome_antigo, nome_novo, preco):
    usuario = st.session_state.usuario_logado if st.session_state.get("usuario_logado") else "padrao"
    with engine.begin() as conn:
        if nome_antigo and nome_antigo != "➕ Cadastrar Novo Serviço":
            conn.execute(text("""UPDATE servicos SET nome = :novo, preco = :precoWHERE usuario_id = :user AND nome = :antigo"""), {"novo": nome_novo, "preco": float(preco), "user": usuario, "antigo": nome_antigo})
        else:
            conn.execute(text("""INSERT INTO servicos (usuario_id, nome, preco) VALUES (:user, :nome, :preco)"""), {"user": usuario, "nome": nome_novo, "preco": float(preco)})

def deletar_servico_banco(nome):
    usuario = st.session_state.usuario_logado if st.session_state.get("usuario_logado") else "padrao"
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM servicos WHERE usuario_id = :user AND nome = :nome"), {"user": usuario, "nome": nome})

def carregar_fluxo():
    usuario = st.session_state.usuario_logado if st.session_state.get("usuario_logado") else "padrao"
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text("SELECT id, data, tipo, descricao, valor FROM fluxo_caixa WHERE usuario_id = :user"), conn, params={"user": usuario})
            if not df.empty:
                df = df.rename(columns={"data": "Data", "tipo": "Tipo", "descricao": "Descrição", "valor": "Valor"})
                df['Data'] = pd.to_datetime(df['Data'])
                return df[['id', 'Data', 'Tipo', 'Descrição', 'Valor']]
    except:
        pass
    return pd.DataFrame(columns=["id", "Data", "Tipo", "Descrição", "Valor"])

def inserir_movimentacao_direta(tipo, descricao, valor, data_input):
    usuario = st.session_state.usuario_logado if st.session_state.get("usuario_logado") else "padrao"
    data_str = data_input.strftime('%Y-%m-%d') if hasattr(data_input, 'strftime') else str(data_input)
    with engine.begin() as conn:
        conn.execute(text("""INSERT INTO fluxo_caixa (usuario_id, data, tipo, descricao, valor)VALUES (:user, :data, :tipo, :descricao, :valor)"""), {"user": usuario, "data": data_str, "tipo": tipo, "descricao": descricao, "valor": float(valor)})

def dar_baixa_fiado_direta(id_registro, nova_descricao):
    usuario = st.session_state.usuario_logado if st.session_state.get("usuario_logado") else "padrao"
    data_hoje = datetime.now(TZ).strftime('%Y-%m-%d')
    with engine.begin() as conn:
        conn.execute(text("""UPDATE fluxo_caixaSET tipo = 'Entrada', data = :data, descricao = :descWHERE id = :id AND usuario_id = :user"""), {"data": data_hoje, "desc": nova_descricao, "id": int(id_registro), "user": usuario})

# --- FUNÇÕES DE AGENDAMENTO ---
def salvar_agendamento(salao_id, cliente, contato, servico, data, hora):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO agendamentos (usuario_id, cliente_nome, cliente_contato, servico_nome, data, hora)
            VALUES (:user, :cliente, :contato, :servico, :data, :hora)
        """), {"user": salao_id, "cliente": cliente, "contato": contato, "servico": servico, "data": str(data), "hora": str(hora)})

def carregar_agendamentos():
    usuario = st.session_state.usuario_logado if st.session_state.get("usuario_logado") else "padrao"
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text("SELECT id, cliente_nome, cliente_contato, servico_nome, data, hora FROM agendamentos WHERE usuario_id = :user ORDER BY data ASC, hora ASC"), conn, params={"user": usuario})
            if not df.empty:
                df = df.rename(columns={"cliente_nome": "Cliente", "cliente_contato": "Contato/WhatsApp", "servico_nome": "Serviço", "data": "Data", "hora": "Horário"})
                return df
    except:
        pass
    return pd.DataFrame(columns=["id", "Cliente", "Contato/WhatsApp", "Serviço", "Data", "Horário"])

def deletar_agendamento(id_agendamento):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM agendamentos WHERE id = :id"), {"id": int(id_agendamento)})

# --- FUNÇÃO DE EXPORTAÇÃO DE BACKUP SEGURO ---
def gerar_backup_json_completo():
    usuario = st.session_state.usuario_logado
    df_f = carregar_fluxo()
    if not df_f.empty:
        df_f['Data'] = df_f['Data'].dt.strftime('%Y-%m-%d')
        fluxo_dict = df_f.to_dict(orient="records")
    else:
        fluxo_dict = []
    
    dados_backup = { 
        "sistema": "Fio&Caixa", 
        "usuario_dono": usuario, 
        "data_geracao": datetime.now(TZ).strftime('%d/%m/%Y %H:%M:%S'), 
        "catalogo_servicos": carregar_servicos(), 
        "historico_financeiro": fluxo_dict
    }
    return json.dumps(dados_backup, indent=4, ensure_ascii=False)

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

# ==============================================================================
# 🎯 INTERCEPTADOR: ROTA DE AGENDAMENTO DO CLIENTE (SEM LOGIN)
# ==============================================================================
query_params = st.query_params
if "salao" in query_params:
    salao_id = query_params["salao"].strip().lower()
    
    # Renderiza a página limpa apenas para o agendamento do cliente
    st.title(f"📅 Agendamento Online - {salao_id.title()}")
    st.markdown("Reserve seu horário de forma rápida e simples, sem complicações!")
    st.markdown("---")
    
    # Carrega os serviços cadastrados especificamente por este salão
    servicos_disponiveis = carregar_servicos_por_salao(salao_id)
    
    with st.form("form_agendamento_cliente"):
        cliente_nome = st.text_input("Seu Nome (Obrigatório):")
        cliente_contato = st.text_input("Seu WhatsApp/Telefone (Opcional):")
        
        servico_selecionado = st.selectbox("Selecione o Serviço desejado:", list(servicos_disponiveis.keys()))
        
        # Mostra o valor do serviço selecionado
        preco_estimado = servicos_disponiveis[servico_selecionado]
        st.info(f"💵 Valor estimado do serviço: R$ {preco_estimado:.2f}")
        
        data_agendada = st.date_input("Escolha o Dia:", datetime.now(TZ).date())
        
        # Cria slots de horário dinâmicos das 08h00 às 19h30
        slots_horario = [f"{h:02d}:00" for h in range(8, 20)] + [f"{h:02d}:30" for h in range(8, 20)]
        slots_horario.sort()
        
        horario_selecionado = st.selectbox("Escolha o Horário:", slots_horario)
        
        enviar_agendamento = st.form_submit_button("Confirmar Agendamento 🚀", use_container_width=True)
        
        if enviar_agendamento:
            if cliente_nome.strip():
                salvar_agendamento(salao_id, cliente_nome, cliente_contato, servico_selecionado, data_agendada, horario_selecionado)
                st.success(f"🎉 Pronto, {cliente_nome}! Seu horário para {servico_selecionado} foi reservado com sucesso no dia {data_agendada.strftime('%d/%m/%Y')} às {horario_selecionado}!")
                st.balloons()
            else:
                st.error("Por favor, informe seu nome para confirmar a reserva.")
                
    st.stop() # Finaliza a execução aqui para o cliente, não mostrando a tela de login.

# ==============================================================================
# --- CONTROLE DE ACESSO (SALAO / ADMIN) ---
# ==============================================================================
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
                            time.sleep(1.5)
                            st.rerun() 
                        else: 
                            st.error("Usuário ou e-mail correspondente não encontrado.") 
            with c_rec2: 
                if st.form_submit_button("Cancelar"): 
                    st.session_state.recuperando_senha = False
                    st.rerun() 
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
                else: 
                    st.error("Credenciais de Administrador incorretas.") 
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
                else: 
                    st.error("Usuário ou senha incorretos.") 
    if st.button("Esqueci minha senha ❯"): 
        st.session_state.recuperando_senha = True
        st.rerun()
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
            dias_validate = st.number_input("Dias de Validade:", min_value=1, value=30) 
            if st.form_submit_button("Salvar Salão"): 
                if novo_usuario and nova_senha and novo_email: 
                    vencimento_calculado = (datetime.now(TZ) + timedelta(days=dias_validate)).strftime("%Y-%m-%d") 
                    usuarios_cadastrados[novo_usuario] = { "senha": hash_password(nova_senha), "email": novo_email, "tipo": tipo_conta, "vencimento": vencimento_calculado, "status": "Ativo" } 
                    salvar_usuarios(usuarios_cadastrados)
                    st.success("Salão salvo com sucesso!")
                    st.rerun()
    with tab_ger: 
        usuarios_cadastrados = carregar_usuarios() 
        if not usuarios_cadastrados: 
            st.info("Nenhum salão cadastrado.") 
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
                    usuarios_cadastrados[salao_sel] = { "senha": senha_final, "email": e_email.strip().lower(), "tipo": e_tipo, "vencimento": e_venc.strftime("%Y-%m-%d"), "status": e_status } 
                    salvar_usuarios(usuarios_cadastrados)
                    st.success("Atualizado!")
                    st.rerun() 
            if st.checkbox(f"Confirmar exclusão de: {salao_sel}"): 
                if st.button("EXCLUIR DEFINITIVAMENTE", type="primary"): 
                    with engine.begin() as conn: 
                        conn.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": salao_sel}) 
                    st.warning("Removido!")
                    st.rerun()
    with st.sidebar: 
        if st.button("🚪 Sair do Modo ADM", use_container_width=True): 
            st.session_state.autenticado = False
            st.rerun()
    st.stop()

# --- INTERFACE 2: PAINEL DO CLIENTE (SALAO LOGADO) ---
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

# ADICIONADA A ABA "📅 Agendamentos" NA VISUALIZAÇÃO DO DONO DO SALÃO
tab1, tab0, tab_agend, tab2 = st.tabs(["📊 Dashboard", "🚀 Início / Ações Rápidas", "📅 Agendamentos", "📜 Histórico"])

with tab1:
    st.subheader("📊 Resumo Financeiro Estruturado")
    m1, m2, m3 = st.columns(3)
    m1.metric("Fechamento do Dia", f"R$ {lucro_dia:.2f}")
    m2.metric("Acumulado 7 Dias", f"R$ {lucro_sem:.2f}")
    m3.metric("Faturamento do Mês", f"R$ {lucro_mes:.2f}")
    st.markdown("---")
    st.bar_chart(pd.DataFrame({"Categoria": ["Entradas", "Saídas"], "Total (R$)": [ent_mes, abs(sai_mes)]}), x="Categoria", y="Total (R$)", color="#29b6f6")

with tab0:
    st.markdown('<div>Fio&Caixa</div>', unsafe_allow_html=True)
    st.markdown('<div>Ações rápidas</div>', unsafe_allow_html=True)
    col_a, col_b, col_c, col_d, col_e = st.columns(5)
    
    with col_a: 
        if st.button("✂️ Novo atendimento ❯", key="btn_atend", use_container_width=True): 
            st.session_state.formulario_ativo = 'none' if st.session_state.formulario_ativo == 'new_atendimento' else 'new_atendimento' 
            st.rerun() 
        if st.session_state.formulario_ativo == 'new_atendimento': 
            st.markdown('<div class="embedded-form-container">', unsafe_allow_html=True) 
            if list(servicos.keys()): 
                servico_selecionado = st.selectbox("Serviço realizado:", list(servicos.keys()), key="f_atend_serv") 
                preco_final = st.number_input("Valor Cobrado (R$):", value=float(servicos[servico_selecionado]), step=1.0, key=f"prc_atend_din_{servico_selecionado}") 
                data_entrada = st.date_input("Data:", datetime.now(TZ).date(), key="f_atend_dt") 
                if st.button("Lançar", type="primary", key="f_atend_save", use_container_width=True): 
                    inserir_movimentacao_direta("Entrada", f"Atendimento: {servico_selecionado}", preco_final, data_entrada) 
                    st.session_state.formulario_ativo = 'none'
                    time.sleep(0.5)
                    st.rerun() 
            st.markdown('</div>', unsafe_allow_html=True) 
            
    with col_b: 
        if st.button("🛍️ Nova despesa ❯", key="btn_venda", use_container_width=True): 
            st.session_state.formulario_ativo = 'none' if st.session_state.formulario_ativo == 'new_venda' else 'new_venda' 
            st.rerun() 
        if st.session_state.formulario_ativo == 'new_venda': 
            st.markdown('<div class="embedded-form-container">', unsafe_allow_html=True) 
            descricao_saida = st.text_input("Descrição:", key="f_venda_desc") 
            valor_saida = st.number_input("Valor (R$):", min_value=0.0, step=5.0, key="f_venda_val") 
            data_saida = st.date_input("Data:", datetime.now(TZ).date(), key="f_venda_dt") 
            if st.button("Confirmar despesa", type="primary", key="f_venda_save", use_container_width=True): 
                if descricao_saida and valor_saida > 0: 
                    inserir_movimentacao_direta("Saída", descricao_saida, -valor_saida, data_saida) 
                    st.session_state.formulario_ativo = 'none'
                    time.sleep(0.5)
                    st.rerun() 
            st.markdown('</div>', unsafe_allow_html=True) 
            
    with col_c: 
        if st.button("💰 Marcar fiado ❯", key="btn_receber", use_container_width=True): 
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
                        inserir_movimentacao_direta("Pendência", f"Fiado de: {nome_devedor} ({servico_pendente})", preco_final_p, data_pendencia) 
                        st.session_state.formulario_ativo = 'none'
                        time.sleep(0.5)
                        st.rerun() 
            st.markdown('</div>', unsafe_allow_html=True) 
            
    with col_d: 
        if st.button("💸 Receber fiado ❯", key="btn_pagar", use_container_width=True): 
            st.session_state.formulario_ativo = 'none' if st.session_state.formulario_ativo == 'new_pagar' else 'new_pagar' 
            st.rerun() 
        if st.session_state.formulario_ativo == 'new_pagar': 
            st.markdown('<div class="embedded-form-container">', unsafe_allow_html=True) 
            df_pendencias = df_fluxo_caixa[df_fluxo_caixa['Tipo'] == 'Pendência'] 
            if not df_pendencias.empty: 
                opcoes_pendentes = {f"{row['Descrição']} - R$ {abs(row['Valor']):.2f}": row['id'] for _, row in df_pendencias.iterrows()} 
                pendencia_selecionada = st.selectbox("Selecione:", list(opcoes_pendentes.keys()), key="f_pago_sel") 
                if st.button("Dar Baixa", type="primary", key="f_pago_save", use_container_width=True): 
                    id_alterar = opcoes_pendentes[pendencia_selecionada] 
                    row_atual = df_pendencias[df_pendencias['id'] == id_alterar].iloc[0] 
                    nova_desc = row_atual['Descrição'].replace("Fiado de:", "Recebido Fiado:") + " [PAGO]" 
                    dar_baixa_fiado_direta(id_alterar, nova_desc) 
                    st.session_state.formulario_ativo = 'none'
                    time.sleep(0.5)
                    st.rerun() 
            else: 
                st.info("Sem fiados pendentes.") 
            st.markdown('</div>', unsafe_allow_html=True) 
            
    with col_e: 
        if st.button("📊 Ver relatórios ❯", key="btn_relatorios", use_container_width=True): 
            st.session_state.formulario_ativo = 'none' if st.session_state.formulario_ativo == 'view_relatorios' else 'view_relatorios' 
            st.rerun() 
        if st.session_state.formulario_ativo == 'view_relatorios': 
            st.markdown('<div class="embedded-form-container">', unsafe_allow_html=True) 
            st.metric("Líquido Diário", f"R$ {lucro_dia:.2f}") 
            st.metric("Líquido Mensal", f"R$ {lucro_mes:.2f}") 
            st.markdown('</div>', unsafe_allow_html=True)

# GESTÃO DOS AGENDAMENTOS RECEBIDOS DOS CLIENTES
with tab_agend:
    st.subheader("📅 Próximos Agendamentos Realizados por Clientes")
    df_agendamentos = carregar_agendamentos()
    
    if not df_agendamentos.empty:
        st.dataframe(df_agendamentos.drop(columns=['id'], errors='ignore'), use_container_width=True, hide_index=True)
        
        # Opção para o dono do salão gerenciar os agendamentos realizados
        st.markdown("---")
        st.write("🔧 **Gerenciar Agendamentos**")
        opcoes_agend = {f"{row['Cliente']} - {row['Data']} às {row['Horário']} ({row['Serviço']})": row['id'] for _, row in df_agendamentos.iterrows()}
        agend_selecionado = st.selectbox("Selecione um agendamento para concluir/remover:", list(opcoes_agend.keys()))
        
        if st.button("Remover / Concluir Agendamento Selecionado", type="primary"):
            deletar_agendamento(opcoes_agend[agend_selecionado])
            st.success("Agendamento atualizado com sucesso!")
            time.sleep(0.5)
            st.rerun()
    else:
        st.info("Nenhum agendamento pendente no momento. Divulgue seu link para receber reservas!")

with st.sidebar:
    st.header("⚙️ Configurações")
    nome_salao = st.session_state.usuario_logado.replace("", " ").title() if st.session_state.usuario_logado else "Salão"
    st.title(f"✂️ {nome_salao}")
    st.markdown("---")
    
    opcoes_gerenciamento = ["➕ Cadastrar Novo Serviço"] + list(servicos.keys())
    servico_sel = st.selectbox("Gerenciar serviços:", opcoes_gerenciamento)
    nome_padrao = "" if servico_sel == "➕ Cadastrar Novo Serviço" else servico_sel
    preco_padrao = 0.0 if servico_sel == "➕ Cadastrar Novo Serviço" else float(servicos[servico_sel])
    novo_servico = st.text_input("Nome do Serviço:", value=nome_padrao, key=f"side_nome_din{servico_sel}")
    novo_preco = st.number_input("Preço Cobrado:", min_value=0.0, value=preco_padrao, step=5.0, key=f"side_prc_din_{servico_sel}")
    
    if st.button("Salvar Alteração", type="primary", use_container_width=True):
        if novo_servico:
            salvar_ou_atualizar_servico(servico_sel, novo_servico, novo_preco)
            st.success("Serviço atualizado com sucesso!")
            time.sleep(0.5)
            st.rerun()
            
    if servico_sel != "➕ Cadastrar Novo Serviço" and st.button("🗑️ Remover do Catálogo", use_container_width=True):
        deletar_servico_banco(servico_sel)
        st.warning("Serviço removido!")
        time.sleep(0.5)
        st.rerun()
        
    st.markdown("---")
    
    # GERADOR DE LINK AUTOMÁTICO PARA O DONO DO SALÃO
    st.subheader("🔗 Link de Agendamento")
    # Nota: Caso use um subdomínio específico, o dono do salão pode atualizar este endereço.
    base_url = "https://seu-app.streamlit.app" 
    link_clientes = f"{base_url}/?salao={st.session_state.usuario_logado}"
    st.info("Envie o link abaixo para seus clientes. Ao acessá-lo, eles poderão reservar horários diretamente sem precisar de login!")
    st.code(link_clientes, language="text")
    
    st.markdown("---")
    with st.expander("📦 Central de Backups"): 
        st.write("Seus dados estão em segurança na nuvem do Supabase, mas você pode baixar uma cópia completa de salvaguarda quando desejar.") 
        backup_dados = gerar_backup_json_completo() 
        st.download_button( label="📥 Baixar Backup Geral (.json)", data=backup_dados, file_name=f"backup_{st.session_state.usuario_logado}_{datetime.now(TZ).strftime('%d_%m_%Y')}.json", mime="application/json", use_container_width=True ) 
        st.markdown("<br><br>", unsafe_allow_html=True)
        
    if st.button("🚪 Sair do Sistema", use_container_width=True): 
        st.session_state.autenticado = False
        st.rerun()

with tab2:
    st.subheader("📜 Histórico de Transações e Exportação para Contador")
    if not df_fluxo_caixa.empty:
        df_filtro = df_fluxo_caixa.dropna(subset=['Data']).copy()
        df_filtro['Mês/Ano'] = df_filtro['Data'].dt.strftime('%m/%Y')
        
        modo_filtro = st.radio("Escolha como deseja filtrar os dados para baixar:", ["Por Mês Fechado", "Por Período Customizado (Escolher Datas)"], horizontal=True) 
        if modo_filtro == "Por Mês Fechado": 
            meses = sorted(df_filtro['Mês/Ano'].unique(), reverse=True) 
            mes_escolhido = st.selectbox("📅 Selecione o Mês de referência:", ["Ver Tudo"] + meses) 
            df_exibicao = df_filtro[df_filtro['Mês/Ano'] == mes_escolhido] if mes_escolhido != "Ver Tudo" else df_filtro 
            texto_pdf = mes_escolhido 
            nome_arq = f"contabilidade_{mes_escolhido.replace('/', '_')}" if mes_escolhido != "Ver Tudo" else "contabilidade_geral" 
        else: 
            col_dt1, col_dt2 = st.columns(2) 
            with col_dt1: 
                dt_inicio = st.date_input("Data Inicial:", datetime.now(TZ).date() - timedelta(days=30)) 
            with col_dt2: 
                dt_fim = st.date_input("Data Final:", datetime.now(TZ).date()) 
            df_exibicao = df_filtro[(df_filtro['Data'].dt.date >= dt_inicio) & (df_filtro['Data'].dt.date <= dt_fim)] 
            texto_pdf = f"{dt_inicio.strftime('%d/%m/%Y')} ate {dt_fim.strftime('%d/%m/%Y')}" 
            nome_arq = f"contabilidade_{dt_inicio.strftime('%d_%m_%Y')}_a_{dt_fim.strftime('%d_%m_%Y')}" 
            
        if not df_exibicao.empty: 
            col_down1, col_down2 = st.columns(2) 
            with col_down1: 
                st.download_button(label="📄 Baixar Arquivo CSV para Contador", data=df_exibicao.drop(columns=['id', 'Mês/Ano'], errors='ignore').to_csv(index=False).encode('utf-8-sig'), file_name=f"{nome_arq}.csv", mime="text/csv", use_container_width=True) 
            with col_down2: 
                st.download_button(label="📕 Baixar Relatório PDF para Contador", data=gerar_pdf_contabilidade(df_exibicao.drop(columns=['id', 'Mês/Ano'], errors='ignore'), texto_pdf), file_name=f"{nome_arq}.pdf", mime="application/pdf", use_container_width=True) 
            st.markdown("---") 
            df_vis = df_exibicao.sort_index(ascending=False).copy() 
            df_vis['Data'] = df_vis['Data'].dt.strftime('%d/%m/%Y') 
            if 'Mês/Ano' in df_vis.columns: 
                df_vis = df_vis.drop(columns=['Mês/Ano']) 
            if 'id' in df_vis.columns: 
                df_vis = df_vis.drop(columns=['id']) 
                
            def colorir(row): 
                if row['Tipo'] == 'Entrada': 
                    return ['background-color: #d4edda; color: #155724'] * 4 
                elif row['Tipo'] == 'Saída': 
                    return ['background-color: #f8d7da; color: #721c24'] * 4 
                return ['background-color: #fff3cd; color: #856404'] * 4 
            st.dataframe(df_vis.style.apply(colorir, axis=1).format({"Valor": "R$ {:.2f}"}), use_container_width=True, hide_index=True) 
        else: 
            st.info("Nenhuma movimentação encontrada para o período selecionado.")
    else: 
        st.info("Nenhuma movimentação financeira registrada.")

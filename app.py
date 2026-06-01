import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import json
import time
import hashlib

# --- CONFIGURAÇÃO ---
SALT = "salao_fio_caixa_2026_security"
TZ = ZoneInfo("America/Sao_Paulo")
USUARIOS_FILE = "usuarios.json"
ADMIN_CONFIG_FILE = "admin_config.json"

def hash_password(password):
    return hashlib.sha256((password + SALT).encode()).hexdigest()

def carregar_admin_hash():
    if os.path.exists(ADMIN_CONFIG_FILE):
        try:
            with open(ADMIN_CONFIG_FILE, "r") as f:
                return json.load(f).get("hash")
        except: return None
    return None

def salvar_admin_hash(password):
    with open(ADMIN_CONFIG_FILE, "w") as f:
        json.dump({"hash": hash_password(password)}, f)

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Financeira - Salão", layout="wide", page_icon="✂️")

st.markdown("""
<style>
    body, .stApp { background-color: #121212; color: white; }
    .sim-header { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #333; margin-bottom: 20px; }
    .sim-header-title { color: #d4af37; font-weight: bold; font-size: 1.2rem; }
    .fast-actions-header { display: flex; align-items: center; margin-bottom: 15px; }
    .fast-actions-title { color: white; font-weight: bold; font-size: 1rem; margin-right: 10px; }
    .fast-actions-line { flex-grow: 1; height: 2px; background-color: #d4af37; }
    .is-action-card { display: none; }
    div[data-testid="stColumn"]:has(.is-action-card) button {
        background-color: #22252a !important; color: white !important; border: 1px solid #333 !important;
        border-radius: 8px !important; padding: 18px 15px !important; min-height: 75px !important;
        width: 100% !important; display: flex !important; align-items: center !important;
        justify-content: flex-start !important; gap: 10px !important; transition: all 0.2s ease-in-out !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.15) !important; cursor: pointer !important;
    }
    div[data-testid="stColumn"]:has(.is-action-card) button:hover { background-color: #2a2e35 !important; border-color: #d4af37 !important; transform: translateY(-2px) !important; box-shadow: 0 6px 12px rgba(212, 175, 55, 0.1) !important; }
    .embedded-form-container { margin-top: 15px; background-color: #1a1d21; padding: 15px; border-radius: 8px; border: 1px solid #d4af37; }
    .confirmacao-dourada { background-color: #1e1e1e; border: 2px solid #d4af37; padding: 12px 15px; border-radius: 6px; color: #fff; font-weight: 500; margin-bottom: 15px; display: flex; align-items: center; gap: 10px; }
</style>
""", unsafe_allow_html=True)

# --- INICIALIZAÇÃO DE ESTADOS ---
if 'formulario_ativo' not in st.session_state: st.session_state.formulario_ativo = 'none'
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'usuario_logado' not in st.session_state: st.session_state.usuario_logado = None
if 'eh_admin' not in st.session_state: st.session_state.eh_admin = False

# --- FUNÇÕES ---
def carregar_usuarios():
    if os.path.exists(USUARIOS_FILE):
        try:
            with open(USUARIOS_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def salvar_usuarios(usuarios):
    with open(USUARIOS_FILE, "w") as f: json.dump(usuarios, f, indent=4)

def obter_nomes_arquivos():
    usuario = st.session_state.usuario_logado if st.session_state.usuario_logado else "padrao"
    return f"servicos_{usuario}.json", f"fluxo_caixa_{usuario}.csv"

def carregar_servicos():
    servicos_file, _ = obter_nomes_arquivos()
    if os.path.exists(servicos_file):
        try:
            with open(servicos_file, "r") as f: return json.load(f)
        except: pass
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

# --- CONTROLE DE SESSÃO E LOGIN ---
admin_hash = carregar_admin_hash()
usuarios_cadastrados = carregar_usuarios()

if not st.session_state.autenticado:
    if not admin_hash:
        st.title("⚠️ Configuração Inicial")
        st.write("Defina a senha do Administrador:")
        with st.form("primeiro_acesso"):
            nova_adm_pass = st.text_input("Definir senha de ADMIN:", type="password")
            if st.form_submit_button("Criar Acesso"):
                salvar_admin_hash(nova_adm_pass)
                st.success("Administrador criado! Reiniciando...")
                st.rerun()
        st.stop()

    st.title("✂️ Sistema de Gestão - Login")
    st.markdown("---")
    with st.form("form_login"):
        usuario_input = st.text_input("Usuário do Salão ou ADM:").strip().lower()
        senha_input = st.text_input("Senha:", type="password")
        if st.form_submit_button("Entrar no Sistema"):
            if usuario_input == "admin" and hash_password(senha_input) == admin_hash:
                st.session_state.autenticado = True
                st.session_state.usuario_logado = "Administrador"
                st.session_state.eh_admin = True
                st.rerun()
            elif usuario_input in usuarios_cadastrados and usuarios_cadastrados[usuario_input]["senha"] == hash_password(senha_input):
                dados_user = usuarios_cadastrados[usuario_input]
                data_vencimento = datetime.strptime(dados_user["vencimento"], "%Y-%m-%d").date()
                if datetime.now(TZ).date() > data_vencimento or dados_user.get("status") == "Suspenso":
                    st.error("❌ ACESSO BLOQUEADO! Licença vencida.")
                    st.stop()
                st.session_state.autenticado = True
                st.session_state.usuario_logado = usuario_input
                st.session_state.eh_admin = False
                st.rerun()
            else: st.error("Usuário ou senha incorretos.")
    st.stop()

# --- INTERFACE 1: ADMINISTRADOR MESTRE ---
if st.session_state.eh_admin:
    st.title("👑 Central do Administrador")
    tab_cad, tab_ger = st.tabs(["➕ Cadastrar/Renovar", "⚙️ Gerenciar Salões"])
    
    with tab_cad:
        with st.form("form_cadastro_cliente"):
            novo_usuario = st.text_input("Usuário do Salão:").strip().lower()
            nova_senha = st.text_input("Senha de Acesso:", type="password").strip()
            tipo_conta = st.selectbox("Tipo de Conta:", ["Teste", "Cliente"])
            dias_validade = st.number_input("Dias de Validade:", min_value=1, value=30)
            if st.form_submit_button("Salvar Salão"):
                if novo_usuario and nova_senha:
                    vencimento_calculado = (datetime.now(TZ) + timedelta(days=dias_validade)).strftime("%Y-%m-%d")
                    usuarios_cadastrados[novo_usuario] = {"senha": hash_password(nova_senha), "tipo": tipo_conta, "vencimento": vencimento_calculado, "status": "Ativo"}
                    salvar_usuarios(usuarios_cadastrados); st.success("Salão configurado!"); st.rerun()

    with tab_ger:
        usuarios_cadastrados = carregar_usuarios()
        if not usuarios_cadastrados: st.info("Nenhum salão cadastrado.")
        else:
            salao_sel = st.selectbox("Selecione o Salão para editar ou excluir:", list(usuarios_cadastrados.keys()))
            dados = usuarios_cadastrados[salao_sel]
            
            with st.expander("📝 Editar Informações", expanded=True):
                e_senha_nova = st.text_input("Nova Senha (deixe em branco para manter a atual):", type="password")
                e_tipo = st.selectbox("Tipo:", ["Teste", "Cliente"], index=0 if dados['tipo'] == "Teste" else 1)
                e_venc = st.date_input("Data de Vencimento:", datetime.strptime(dados['vencimento'], "%Y-%m-%d"))
                e_status = st.selectbox("Status:", ["Ativo", "Suspenso"], index=0 if dados['status'] == "Ativo" else 1)
                
                if st.button("Salvar Edição"):
                    senha_final = hash_password(e_senha_nova) if e_senha_nova else dados['senha']
                    usuarios_cadastrados[salao_sel] = {"senha": senha_final, "tipo": e_tipo, "vencimento": e_venc.strftime("%Y-%m-%d"), "status": e_status}
                    salvar_usuarios(usuarios_cadastrados)
                    st.success("Dados updated!")
                    st.rerun()

            st.markdown("---")
            st.error("⚠️ Área de Perigo")
            if st.checkbox(f"Confirmar que deseja excluir permanentemente o salão: {salao_sel}"):
                if st.button("EXCLUIR SALÃO", type="primary"):
                    del usuarios_cadastrados[salao_sel]
                    salvar_usuarios(usuarios_cadastrados)
                    st.warning("Salão removido com sucesso!")
                    st.rerun()

    with st.sidebar:
        if st.button("🚪 Sair do Modo ADM", use_container_width=True):
            st.session_state.autenticado = False; st.rerun()
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
        st.markdown('<div class="is-action-card"></div>', unsafe_allow_html=True)
        if st.button("✂️ Novo atendimento  ❯", key="btn_atend", use_container_width=True):
            st.session_state.formulario_ativo = 'none' if st.session_state.formulario_ativo == 'new_atendimento' else 'new_atendimento'
            st.rerun()
        if st.session_state.formulario_ativo == 'new_atendimento':
            st.markdown('<div class="embedded-form-container">', unsafe_allow_html=True)
            st.write("**📥 Novo Atendimento**")
            servicos = carregar_servicos()
            if list(servicos.keys()):
                servico_selecionado = st.selectbox("Serviço realizado:", list(servicos.keys()), key="f_atend_serv")
                preco_final = st.number_input("Valor Cobrado (R$):", value=float(servicos[servico_selecionado]), step=1.0, key=f"prc_atend_din_{servico_selecionado}")
                data_entrada = st.date_input("Data:", datetime.now(TZ).date(), key="f_atend_dt")
                if st.button("Lançar", type="primary", key="f_atend_save", use_container_width=True):
                    nova_linha = pd.DataFrame([{"Data": pd.to_datetime(data_entrada), "Tipo": "Entrada", "Descrição": f"Atendimento: {servico_selecionado}", "Valor": preco_final}])
                    st.session_state.fluxo_caixa = pd.concat([df_fluxo_caixa, nova_linha], ignore_index=True); salvar_fluxo(st.session_state.fluxo_caixa)
                    st.markdown('<div class="confirmacao-dourada">✅ Atendimento registrado com sucesso!</div>', unsafe_allow_html=True)
                    st.session_state.formulario_ativo = 'none'; time.sleep(1.2); st.rerun()
            else: st.info("Cadastre serviços na barra lateral.")
            st.markdown('</div>', unsafe_allow_html=True)
            
    with col_b:
        st.markdown('<div class="is-action-card"></div>', unsafe_allow_html=True)
        if st.button("🛍️ Nova despesa  ❯", key="btn_venda", use_container_width=True):
            st.session_state.formulario_ativo = 'none' if st.session_state.formulario_ativo == 'new_venda' else 'new_venda'
            st.rerun()
        if st.session_state.formulario_ativo == 'new_venda':
            st.markdown('<div class="embedded-form-container">', unsafe_allow_html=True)
            st.write("**📤 Registrar Despesa**")
            descricao_saida = st.text_input("Descrição (Ex: Luz, Aluguel):", key="f_venda_desc")
            valor_saida = st.number_input("Valor pago (R$):", min_value=0.0, step=5.0, key="f_venda_val")
            data_saida = st.date_input("Data:", datetime.now(TZ).date(), key="f_venda_dt")
            if st.button("Confirmar", type="primary", key="f_venda_save", use_container_width=True):
                if descricao_saida and valor_saida > 0:
                    nova_linha = pd.DataFrame([{"Data": pd.to_datetime(data_saida), "Tipo": "Saída", "Descrição": descricao_saida, "Valor": -valor_saida}])
                    st.session_state.fluxo_caixa = pd.concat([df_fluxo_caixa, nova_linha], ignore_index=True); salvar_fluxo(st.session_state.fluxo_caixa)
                    st.markdown('<div class="confirmacao-dourada">✅ Despesa registrada com sucesso!</div>', unsafe_allow_html=True)
                    st.session_state.formulario_ativo = 'none'; time.sleep(1.2); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            
    with col_c:
        st.markdown('<div class="is-action-card"></div>', unsafe_allow_html=True)
        if st.button("💰 Marcar fiado  ❯", key="btn_receber", use_container_width=True):
            st.session_state.formulario_ativo = 'none' if st.session_state.formulario_ativo == 'new_receber' else 'new_receber'
            st.rerun()
        if st.session_state.formulario_ativo == 'new_receber':
            st.markdown('<div class="embedded-form-container">', unsafe_allow_html=True)
            st.write("**⏳ Registrar Fiado**")
            servicos = carregar_servicos()
            if list(servicos.keys()):
                nome_devedor = st.text_input("Nome do Cliente:", key="f_fiado_nome")
                servico_pendente = st.selectbox("Serviço:", list(servicos.keys()), key="f_fiado_serv")
                preco_final_p = st.number_input("Valor (R$):", value=float(servicos[servico_pendente]), key=f"prc_fiado_din_{servico_pendente}")
                data_pendencia = st.date_input("Data:", datetime.now(TZ).date(), key="f_fiado_dt")
                if st.button("Salvar", type="primary", key="f_fiado_save", use_container_width=True):
                    if nome_devedor:
                        nova_linha = pd.DataFrame([{"Data": pd.to_datetime(data_pendencia), "Tipo": "Pendência", "Descrição": f"Fiado de: {nome_devedor} ({servico_pendente})", "Valor": preco_final_p}])
                        st.session_state.fluxo_caixa = pd.concat([df_fluxo_caixa, nova_linha], ignore_index=True); salvar_fluxo(st.session_state.fluxo_caixa)
                        st.markdown('<div class="confirmacao-dourada">✅ Corte fiado pendente registrado!</div>', unsafe_allow_html=True)
                        st.session_state.formulario_ativo = 'none'; time.sleep(1.2); st.rerun()
            else: st.info("Cadastre serviços na barra lateral.")
            st.markdown('</div>', unsafe_allow_html=True)
            
    with col_d:
        st.markdown('<div class="is-action-card"></div>', unsafe_allow_html=True)
        if st.button("💸 Receber fiado  ❯", key="btn_pagar", use_container_width=True):
            st.session_state.formulario_ativo = 'none' if st.session_state.formulario_ativo == 'new_pagar' else 'new_pagar'
            st.rerun()
        if st.session_state.formulario_ativo == 'new_pagar':
            st.markdown('<div class="embedded-form-container">', unsafe_allow_html=True)
            st.write("**✅ Receber Fiado**")
            df_pendencias = df_fluxo_caixa[df_fluxo_caixa['Tipo'] == 'Pendência']
            if not df_pendencias.empty:
                opcoes_pendentes = {f"{row['Descrição']} - R$ {abs(row['Valor']):.2f}": idx for idx, row in df_pendencias.iterrows()}
                pendencia_selecionada = st.selectbox("Selecione o cliente:", list(opcoes_pendentes.keys()), key="f_pago_sel")
                if st.button("Dar Baixa", type="primary", key="f_pago_save", use_container_width=True):
                    idx_alterar = opcoes_pendentes[pendencia_selecionada]
                    df_fluxo_caixa.at[idx_alterar, 'Tipo'] = 'Entrada'
                    df_fluxo_caixa.at[idx_alterar, 'Data'] = pd.to_datetime(datetime.now(TZ).date())
                    df_fluxo_caixa.at[idx_alterar, 'Descrição'] = df_fluxo_caixa.at[idx_alterar, 'Descrição'].replace("Fiado de:", "Recebido Fiado:") + " [PAGO]"
                    salvar_fluxo(df_fluxo_caixa)
                    st.markdown('<div class="confirmacao-dourada">✅ Baixa de fiado registrada com sucesso!</div>', unsafe_allow_html=True)
                    st.session_state.formulario_ativo = 'none'; time.sleep(1.2); st.rerun()
            else: st.info("Nenhum fiado em aberto.")
            st.markdown('</div>', unsafe_allow_html=True)
            
    with col_e:
        st.markdown('<div class="is-action-card"></div>', unsafe_allow_html=True)
        if st.button("📊 Ver relatórios  ❯", key="btn_relatorios", use_container_width=True):
            st.session_state.formulario_ativo = 'none' if st.session_state.formulario_ativo == 'view_relatorios' else 'view_relatorios'
            st.rerun()
        if st.session_state.formulario_ativo == 'view_relatorios':
            st.markdown('<div class="embedded-form-container">', unsafe_allow_html=True)
            st.write("**📊 Resumo Rápido**")
            st.metric("Líquido Diário", f"R$ {lucro_dia:.2f}")
            st.metric("Líquido Mensal", f"R$ {lucro_mes:.2f}")
            st.markdown('</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Configurações")
    nome_salao = st.session_state.usuario_logado.replace("_", " ").title() if st.session_state.usuario_logado else "Salão"
    st.title(f"✂️ {nome_salao}")
    st.markdown("---")
    servicos = carregar_servicos()
    opcoes_gerenciamento = ["➕ Cadastrar Novo Serviço"] + list(servicos.keys())
    servico_sel = st.selectbox("Escolha um serviço para gerenciar:", opcoes_gerenciamento)
    nome_padrao = "" if servico_sel == "➕ Cadastrar Novo Serviço" else servico_sel
    preco_padrao = 0.0 if servico_sel == "➕ Cadastrar Novo Serviço" else float(servicos[servico_sel])
    novo_servico = st.text_input("Nome do Serviço:", value=nome_padrao, key=f"side_nome_din_{servico_sel}")
    novo_preco = st.number_input("Preço Cobrado (R$):", min_value=0.0, value=preco_padrao, step=5.0, key=f"side_prc_din_{servico_sel}")
    if st.button("Salvar Alteração", type="primary", use_container_width=True):
        if novo_servico:
            if servico_sel != "➕ Cadastrar Novo Serviço" and servico_sel != novo_servico: del servicos[servico_sel]
            servicos[novo_servico] = novo_preco; salvar_servicos(servicos); st.rerun()
    if servico_sel != "➕ Cadastrar Novo Serviço" and st.button("🗑️ Remover Serviço do Catálogo", use_container_width=True):
        del servicos[servico_sel]; salvar_servicos(servicos); st.rerun()
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("🚪 Sair do Sistema", use_container_width=True):
        st.session_state.autenticado = False; st.rerun()

with tab2:
    st.subheader("📜 Histórico de Transações Completas")
    if not df_fluxo_caixa.empty:
        df_filtro = df_fluxo_caixa.dropna(subset=['Data']).copy()
        df_filtro['Mês/Ano'] = df_filtro['Data'].dt.strftime('%m/%Y')
        meses = sorted(df_filtro['Mês/Ano'].unique(), reverse=True)
        mes_escolhido = st.selectbox("📅 Escolha o mês de referência:", ["Ver Tudo"] + meses)
        df_exibicao = df_filtro[df_filtro['Mês/Ano'] == mes_escolhido] if mes_escolhido != "Ver Tudo" else df_filtro
        if not df_exibicao.empty:
            df_vis = df_exibicao.sort_index(ascending=False).copy()
            df_vis['Data'] = df_vis['Data'].dt.strftime('%d/%m/%Y')
            df_vis = df_vis.drop(columns=['Mês/Ano'])
            def colorir(row):
                if row['Tipo'] == 'Entrada': return ['background-color: #d4edda; color: #155724'] * 4
                elif row['Tipo'] == 'Saída': return ['background-color: #f8d7da; color: #721c24'] * 4
                return ['background-color: #fff3cd; color: #856404'] * 4
            st.dataframe(df_vis.style.apply(colorir, axis=1).format({"Valor": "R$ {:.2f}"}), use_container_width=True, hide_index=True)
    else: st.info("Nenhuma movimentação financeira registrada até o momento.")

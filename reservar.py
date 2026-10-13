
import streamlit as st
import pandas as pd
import calendar
import urllib.parse
import re

from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

# ============================================================
# 1. CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Agendamento Online | Fio&Caixa",
    page_icon="✂️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

TZ_BR = ZoneInfo("America/Sao_Paulo")
AGORA = datetime.now(TZ_BR)
HOJE = AGORA.date()

HORARIO_INICIO = time(8, 0)
HORARIO_FIM = time(19, 0)
INTERVALO_MINUTOS = 30
DIAS_AGENDA = 60

# ============================================================
# 2. IDENTIDADE VISUAL
# ============================================================

st.markdown("""
<style>
    #MainMenu, footer, header {visibility: hidden;}

    .stApp {
        background:
            radial-gradient(circle at top right,
                rgba(37, 99, 235, 0.13), transparent 35%),
            #0b1120;
        color: #f1f5f9;
    }

    .block-container {
        max-width: 900px;
        padding-top: 1.5rem;
        padding-bottom: 3rem;
    }

    .hero {
        padding: 28px 22px;
        border: 1px solid #263449;
        border-radius: 22px;
        background: linear-gradient(135deg, #17243a, #101827);
        margin-bottom: 22px;
        text-align: center;
    }

    .hero-icon {font-size: 42px; margin-bottom: 5px;}

    .hero h1 {
        font-size: clamp(25px, 5vw, 36px);
        color: #ffffff;
        margin: 0;
        font-weight: 800;
    }

    .hero p {
        color: #a8b6cb;
        margin: 10px 0 0;
        font-size: 15px;
    }

    .section-title {
        font-size: 19px;
        font-weight: 750;
        margin: 25px 0 12px;
        color: #f8fafc;
    }

    .info-card {
        padding: 16px;
        background: #111c2d;
        border: 1px solid #29374d;
        border-radius: 15px;
        margin-bottom: 14px;
    }

    .price-card {
        background: #111c2d;
        border: 1px solid #29374d;
        padding: 17px;
        border-radius: 15px;
        margin: 12px 0;
    }

    .price-value {
        color: #60a5fa;
        font-size: 27px;
        font-weight: 800;
    }

    .muted {
        color: #9caec4;
        font-size: 13px;
    }

    .calendar-legend {
        display: flex;
        flex-wrap: wrap;
        gap: 14px;
        margin: 12px 0;
        color: #b9c6d8;
        font-size: 12px;
    }

    .stButton > button {
        width: 100%;
        min-height: 43px;
        border-radius: 10px;
        border: 1px solid #33445d;
        background: #152238;
        color: #f8fafc;
        font-weight: 650;
        transition: all 0.15s ease;
    }

    .stButton > button:hover {
        border-color: #60a5fa;
        color: #93c5fd;
        background: #1b2d48;
    }

    .stFormSubmitButton > button {
        min-height: 52px;
        border-radius: 12px;
        background: #2563eb;
        border: none;
        color: white;
        font-size: 16px;
        font-weight: 750;
    }

    div[data-testid="stForm"] {
        background: #111c2d;
        border: 1px solid #29374d;
        border-radius: 17px;
        padding: 20px;
    }

    div[data-testid="stTextInput"] input,
    div[data-testid="stSelectbox"] > div > div {
        border-radius: 10px;
    }

    .footer {
        color: #8293aa;
        text-align: center;
        font-size: 12px;
        padding-top: 25px;
    }

    @media (max-width: 600px) {
        .block-container {
            padding-left: 12px;
            padding-right: 12px;
        }
        .hero {padding: 22px 12px;}
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 3. BANCO DE DADOS
# ============================================================

try:
    DB_URL = st.secrets["DB_URL"]
except Exception:
    st.error(
        "Não foi encontrada a variável DB_URL nos Secrets "
        "do Streamlit Cloud."
    )
    st.stop()


@st.cache_resource
def init_connection(url):
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800
    )


try:
    engine = init_connection(DB_URL)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
except Exception:
    st.error(
        "Não foi possível conectar ao banco de dados. "
        "Confira a variável DB_URL e a disponibilidade do PostgreSQL."
    )
    st.stop()


def ajustar_estrutura_banco():
    """
    Mantém compatibilidade com instalações que possuem
    cliente_telefone como coluna obrigatória.
    """
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                ALTER TABLE agendamentos
                ALTER COLUMN cliente_telefone DROP NOT NULL
            """))
    except Exception:
        pass


ajustar_estrutura_banco()

# ============================================================
# 4. CATÁLOGO DE REFERÊNCIA
#
# Os preços são referências iniciais, não uma tabela oficial.
# Se o salão já tiver serviços cadastrados no banco,
# esses serviços e preços terão prioridade.
# ============================================================

CATALOGO_REFERENCIA = {
    "Corte masculino": (35.00, 30),
    "Corte degradê / fade": (40.00, 40),
    "Corte na tesoura": (45.00, 45),
    "Corte social": (35.00, 30),
    "Corte infantil": (30.00, 30),
    "Raspar cabeça": (25.00, 20),
    "Pezinho / acabamento": (15.00, 15),
    "Barba": (30.00, 30),
    "Barba na navalha": (35.00, 30),
    "Barboterapia": (50.00, 40),
    "Bigode": (10.00, 10),
    "Sobrancelha": (15.00, 15),
    "Sobrancelha na pinça": (20.00, 15),
    "Desenho / freestyle": (15.00, 15),
    "Depilação nariz e orelhas": (25.00, 20),
    "Pigmentação capilar": (30.00, 30),
    "Pigmentação de barba": (35.00, 30),
    "Camuflagem de fios brancos": (35.00, 30),
    "Hidratação capilar": (35.00, 30),
    "Escova masculina": (25.00, 20),
    "Relaxamento capilar": (45.00, 40),
    "Alisamento capilar": (60.00, 60),
    "Selagem capilar": (80.00, 60),
    "Luzes": (100.00, 90),
    "Platinado": (150.00, 150),
    "Corte + barba": (60.00, 60),
    "Corte + sobrancelha": (45.00, 45),
    "Corte + barba + sobrancelha": (70.00, 75),
    "Corte + pigmentação": (60.00, 60),
    "Corte + luzes": (120.00, 120),
    "Corte + platinado": (180.00, 180),
    "Corte + relaxamento": (75.00, 75),
    "Corte + hidratação": (60.00, 60),
    "Corte + selagem": (100.00, 90),
    "Corte + barba + pigmentação": (85.00, 90),
    "Corte + barba + hidratação": (90.00, 90),
    "Corte + depilação nariz e orelhas": (60.00, 50),
    "Manutenção de prótese capilar": (100.00, 60),
    "Aplicação de prótese capilar": (500.00, 120),
    "Lavagem capilar": (15.00, 15),
}


def carregar_servicos_salao(salao_id):
    """
    Usa os serviços do próprio estabelecimento quando existem.
    Caso contrário, apresenta o catálogo de referência.
    Não insere nem altera preços no banco automaticamente.
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT nome, preco
                    FROM servicos
                    WHERE LOWER(TRIM(usuario_id::text)) = :user
                    ORDER BY nome ASC
                """),
                {"user": salao_id}
            )
            rows = result.fetchall()

        servicos = {}
        for row in rows:
            if row[0] is not None and row[1] is not None:
                servicos[str(row[0])] = float(row[1])

        if servicos:
            return servicos, True

    except Exception:
        # Se a consulta falhar, tenta oferecer o catálogo de referência.
        pass

    return {
        nome: dados[0]
        for nome, dados in CATALOGO_REFERENCIA.items()
    }, False


def duracao_servico(nome):
    """
    A duração é uma estimativa do catálogo.
    Para serviços personalizados do salão, usa 30 minutos
    como referência, pois a tabela atual não armazena duração.
    """
    if nome in CATALOGO_REFERENCIA:
        return CATALOGO_REFERENCIA[nome][1]

    return 30


# ============================================================
# 5. IDENTIFICAÇÃO DO ESTABELECIMENTO
# ============================================================

query_params = st.query_params

salao_param = query_params.get("salao", "padrao")

salao_id = urllib.parse.unquote(
    str(salao_param)
).strip().lower()

nome_salao = (
    salao_id.replace("_", " ")
    .replace("-", " ")
    .title()
)

# ============================================================
# 6. HORÁRIOS E AGENDAMENTOS EXISTENTES
# ============================================================

def gerar_horarios():
    horarios = []
    atual = datetime.combine(date.today(), HORARIO_INICIO)
    fim = datetime.combine(date.today(), HORARIO_FIM)

    while atual <= fim:
        # Pausa de almoço: 12h às 13h.
        if not (time(12, 0) <= atual.time() < time(13, 0)):
            horarios.append(atual.strftime("%H:%M"))

        atual += timedelta(minutes=INTERVALO_MINUTOS)

    return horarios


HORARIOS_DISPONIVEIS = gerar_horarios()


def carregar_agendamentos_periodo(salao_id, inicio, fim):
    """
    Busca as reservas do salão em um período para desenhar
    o calendário e liberar os horários disponíveis.
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT data, hora
                    FROM agendamentos
                    WHERE LOWER(TRIM(usuario_id::text)) = :user
                      AND data >= :inicio
                      AND data <= :fim
                """),
                {
                    "user": salao_id,
                    "inicio": inicio.strftime("%Y-%m-%d"),
                    "fim": fim.strftime("%Y-%m-%d"),
                }
            )
            rows = result.fetchall()

        reservas = {}

        for row in rows:
            data_reserva = row[0]
            hora_reserva = row[1]

            if isinstance(data_reserva, datetime):
                data_reserva = data_reserva.date()
            elif isinstance(data_reserva, str):
                try:
                    data_reserva = date.fromisoformat(
                        data_reserva[:10]
                    )
                except ValueError:
                    continue

            if isinstance(hora_reserva, time):
                hora_reserva = hora_reserva.strftime("%H:%M")
            else:
                hora_reserva = str(hora_reserva).strip()[:5]

            if data_reserva not in reservas:
                reservas[data_reserva] = set()

            reservas[data_reserva].add(hora_reserva)

        return reservas

    except Exception as e:
        st.error(
            "Não foi possível consultar a agenda. "
            "Verifique se as colunas data e hora existem "
            "na tabela agendamentos."
        )
        st.stop()


def buscar_horarios_ocupados(salao_id, data_escolhida):
    """
    Consulta novamente o banco no momento da seleção
    e antes de gravar a reserva.
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT hora
                    FROM agendamentos
                    WHERE LOWER(TRIM(usuario_id::text)) = :user
                      AND data = :dt
                """),
                {
                    "user": salao_id,
                    "dt": data_escolhida.strftime("%Y-%m-%d"),
                }
            )
            rows = result.fetchall()

        ocupados = set()

        for row in rows:
            valor = row[0]

            if isinstance(valor, time):
                valor = valor.strftime("%H:%M")
            else:
                valor = str(valor).strip()[:5]

            ocupados.add(valor)

        return ocupados

    except Exception:
        st.error("Erro ao consultar os horários reservados.")
        st.stop()


def salvar_agendamento(
    salao_id,
    cliente_nome,
    cliente_contato,
    servico_nome,
    data_escolhida,
    hora
):
    """
    Mantém compatibilidade com os dois formatos de INSERT
    existentes no código original.
    """
    dados = {
        "user": salao_id,
        "nome": cliente_nome.strip(),
        "contato": cliente_contato.strip(),
        "servico": servico_nome,
        "data": data_escolhida.strftime("%Y-%m-%d"),
        "hora": hora,
    }

    with engine.begin() as conn:
        try:
            conn.execute(
                text("""
                    INSERT INTO agendamentos (
                        usuario_id,
                        cliente_nome,
                        cliente_contato,
                        cliente_telefone,
                        servico_nome,
                        data,
                        hora
                    )
                    VALUES (
                        :user, :nome, :contato, :contato,
                        :servico, :data, :hora
                    )
                """),
                dados
            )

        except Exception:
            # Compatibilidade com instalações sem cliente_telefone.
            conn.execute(
                text("""
                    INSERT INTO agendamentos (
                        usuario_id,
                        cliente_nome,
                        cliente_contato,
                        servico_nome,
                        data,
                        hora
                    )
                    VALUES (
                        :user, :nome, :contato,
                        :servico, :data, :hora
                    )
                """),
                dados
            )


# ============================================================
# 7. CABEÇALHO DA PÁGINA
# ============================================================

st.markdown(f"""
<div class="hero">
    <div class="hero-icon">✂️</div>
    <h1>Agendamento Online</h1>
    <p>{nome_salao}</p>
    <p>Escolha seu serviço, encontre o melhor horário
    e reserve em poucos passos.</p>
</div>
""", unsafe_allow_html=True)

servicos_disponiveis, servicos_personalizados = (
    carregar_servicos_salao(salao_id)
)

if servicos_personalizados:
    st.caption(
        "Os valores exibidos são os cadastrados por este estabelecimento."
    )
else:
    st.info(
        "Você está vendo preços de referência. "
        "O estabelecimento pode ter uma tabela própria."
    )

# ============================================================
# 8. CALENDÁRIO VISUAL EM BLOCOS
# ============================================================

st.markdown(
    '<div class="section-title">📅 1. Escolha o dia</div>',
    unsafe_allow_html=True
)

if "data_agendamento" not in st.session_state:
    st.session_state.data_agendamento = HOJE

if "mes_calendario" not in st.session_state:
    st.session_state.mes_calendario = date(HOJE.year, HOJE.month, 1)

if "confirmacao_agendamento" not in st.session_state:
    st.session_state.confirmacao_agendamento = None

data_escolhida = st.session_state.data_agendamento
mes_atual = st.session_state.mes_calendario

# Impede selecionar datas fora da janela da agenda.
data_maxima = HOJE + timedelta(days=DIAS_AGENDA)

# Corrige o mês selecionado para que a navegação não saia da agenda.
mes_minimo = date(HOJE.year, HOJE.month, 1)
mes_maximo = date(data_maxima.year, data_maxima.month, 1)

if mes_atual < mes_minimo:
    st.session_state.mes_calendario = mes_minimo
    mes_atual = mes_minimo

if mes_atual > mes_maximo:
    st.session_state.mes_calendario = mes_maximo
    mes_atual = mes_maximo

# Cabeçalho de navegação do calendário.
col_ant, col_mes, col_prox = st.columns([1, 4, 1])

meses_pt = [
    "Janeiro", "Fevereiro", "Março", "Abril",
    "Maio", "Junho", "Julho", "Agosto",
    "Setembro", "Outubro", "Novembro", "Dezembro"
]

nome_mes = f"{meses_pt[mes_atual.month - 1]} de {mes_atual.year}"

with col_ant:
    if st.button(
        "◀",
        key="mes_anterior",
        disabled=(mes_atual <= mes_minimo),
        use_container_width=True
    ):
        ano = mes_atual.year
        mes = mes_atual.month - 1

        if mes == 0:
            mes = 12
            ano -= 1

        st.session_state.mes_calendario = date(ano, mes, 1)
        st.rerun()

with col_mes:
    st.markdown(
        f"<div style='text-align:center;padding-top:10px;"
        f"font-weight:800;font-size:18px'>{nome_mes}</div>",
        unsafe_allow_html=True
    )

with col_prox:
    if st.button(
        "▶",
        key="mes_proximo",
        disabled=(mes_atual >= mes_maximo),
        use_container_width=True
    ):
        ano = mes_atual.year
        mes = mes_atual.month + 1

        if mes == 13:
            mes = 1
            ano += 1

        st.session_state.mes_calendario = date(ano, mes, 1)
        st.rerun()

st.markdown(
    '<div class="calendar-legend">'
    '<span>🟢 Dia disponível</span>'
    '<span>🔵 Dia selecionado</span>'
    '<span>⚪ Dia indisponível</span>'
    '</div>',
    unsafe_allow_html=True
)

# Consulta das reservas para exibir a disponibilidade por dia.
inicio_mes = date(mes_atual.year, mes_atual.month, 1)

if mes_atual.month == 12:
    inicio_proximo_mes = date(mes_atual.year + 1, 1, 1)
else:
    inicio_proximo_mes = date(mes_atual.year, mes_atual.month + 1, 1)

fim_mes = inicio_proximo_mes - timedelta(days=1)

reservas_mes = carregar_agendamentos_periodo(
    salao_id,
    max(inicio_mes, HOJE),
    min(fim_mes, data_maxima)
) if max(inicio_mes, HOJE) <= min(fim_mes, data_maxima) else {}

# Cabeçalho dos dias da semana.
dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

cols = st.columns(7)

for i, dia in enumerate(dias_semana):
    with cols[i]:
        st.markdown(
            f"<div style='text-align:center;color:#9caec4;"
            f"font-size:12px;font-weight:700;padding:5px 0'>"
            f"{dia}</div>",
            unsafe_allow_html=True
        )

# Montagem das semanas.
calendario = calendar.monthcalendar(
    mes_atual.year,
    mes_atual.month
)

for semana_idx, semana in enumerate(calendario):
    colunas = st.columns(7)

    for dia_idx, dia_num in enumerate(semana):
        with colunas[dia_idx]:
            if dia_num == 0:
                st.markdown(
                    "<div style='height:43px'></div>",
                    unsafe_allow_html=True
                )
                continue

            dia_data = date(
                mes_atual.year,
                mes_atual.month,
                dia_num
            )

            fora_do_periodo = (
                dia_data < HOJE or dia_data > data_maxima
            )

            ocupados = reservas_mes.get(dia_data, set())

            horarios_futuros = [
                h for h in HORARIOS_DISPONIVEIS
                if not (
                    dia_data == HOJE
                    and h <= AGORA.strftime("%H:%M")
                )
            ]

            livres = [
                h for h in horarios_futuros
                if h not in ocupados
            ]

            sem_vagas = len(livres) == 0

            selecionado = dia_data == data_escolhida

            if selecionado:
                icone = "🔵"
            elif fora_do_periodo or sem_vagas:
                icone = "⚪"
            else:
                icone = "🟢"

            texto_botao = f"{icone} {dia_num}"

            if st.button(
                texto_botao,
                key=f"dia_{dia_data.isoformat()}",
                disabled=fora_do_periodo or sem_vagas,
                use_container_width=True
            ):
                st.session_state.data_agendamento = dia_data
                st.session_state.confirmacao_agendamento = None
                st.rerun()

st.caption(
    f"Agenda disponível de {HOJE.strftime('%d/%m/%Y')} "
    f"até {data_maxima.strftime('%d/%m/%Y')}."
)

# ============================================================
# 9. HORÁRIOS DISPONÍVEIS PARA O DIA SELECIONADO
# ============================================================

data_escolhida = st.session_state.data_agendamento

st.markdown(
    '<div class="section-title">🕒 2. Escolha o horário</div>',
    unsafe_allow_html=True
)

st.markdown(
    f"<div class='info-card'>"
    f"<span class='muted'>DATA SELECIONADA</span><br>"
    f"<strong style='font-size:20px'>"
    f"{data_escolhida.strftime('%d/%m/%Y')}</strong><br>"
    f"<span class='muted'>"
    f"{dias_semana[data_escolhida.weekday()]}, "
    f"{data_escolhida.strftime('%d/%m/%Y')}</span>"
    f"</div>",
    unsafe_allow_html=True
)

ocupados_agora = buscar_horarios_ocupados(
    salao_id,
    data_escolhida
)

horarios_livres = [
    h for h in HORARIOS_DISPONIVEIS
    if h not in ocupados_agora
    and not (
        data_escolhida == HOJE
        and h <= AGORA.strftime("%H:%M")
    )
]

if not horarios_livres:
    st.warning(
        "Não há horários livres para esse dia. "
        "Escolha outro dia no calendário."
    )
    horario_selecionado = None
else:
    if (
        "horario_selecionado" not in st.session_state
        or st.session_state.horario_selecionado not in horarios_livres
    ):
        st.session_state.horario_selecionado = horarios_livres[0]

    # Blocos clicáveis de horário.
    st.caption(
        f"{len(horarios_livres)} horário(s) disponível(is). "
        "Selecione uma opção abaixo."
    )

    horario_selecionado = st.session_state.horario_selecionado

    for inicio in range(0, len(horarios_livres), 3):
        grupo = horarios_livres[inicio:inicio + 3]
        cols_horarios = st.columns(3)

        for i, horario in enumerate(grupo):
            with cols_horarios[i]:
                marcador = "✓ " if horario == horario_selecionado else ""

                if st.button(
                    f"{marcador}{horario}",
                    key=f"horario_{data_escolhida}_{horario}",
                    use_container_width=True
                ):
                    st.session_state.horario_selecionado = horario
                    st.session_state.confirmacao_agendamento = None
                    st.rerun()

    horario_selecionado = st.session_state.horario_selecionado

    st.success(f"Horário escolhido: **{horario_selecionado}**")

# ============================================================
# 10. SERVIÇOS E VALORES
# ============================================================

st.markdown(
    '<div class="section-title">✂️ 3. Escolha o serviço</div>',
    unsafe_allow_html=True
)

lista_servicos = list(servicos_disponiveis.keys())

if not lista_servicos:
    st.error("Nenhum serviço disponível para agendamento.")
    st.stop()

servico_escolhido = st.selectbox(
    "Serviço desejado",
    options=lista_servicos,
    format_func=lambda nome: (
        f"{nome} — R$ {servicos_disponiveis[nome]:.2f}"
        .replace(".", ",")
    ),
    key="servico_cliente"
)

preco_servico = float(servicos_disponiveis[servico_escolhido])
duracao = duracao_servico(servico_escolhido)

st.markdown(f"""
<div class="price-card">
    <div class="muted">SERVIÇO SELECIONADO</div>
    <div style="font-size:19px;font-weight:750;margin:5px 0">
        {servico_escolhido}
    </div>
    <div class="price-value">
        R$ {preco_servico:,.2f}
    </div>
    <div class="muted">
        Duração estimada: {duracao} minutos
    </div>
</div>
""".replace(",", "X").replace(".", ",").replace("X", "."),
unsafe_allow_html=True)

# ============================================================
# 11. DADOS DO CLIENTE E CONFIRMAÇÃO
# ============================================================

st.markdown(
    '<div class="section-title">👤 4. Seus dados</div>',
    unsafe_allow_html=True
)

with st.form("form_agendamento_cliente", clear_on_submit=False):

    nome_cliente = st.text_input(
        "Nome completo",
        placeholder="Digite seu nome"
    )

    telefone_cliente = st.text_input(
        "WhatsApp com DDD",
        placeholder="Ex.: (31) 99999-9999"
    )

    st.caption(
        "Confira os dados, o serviço, a data e o horário antes de confirmar."
    )

    enviar = st.form_submit_button(
        "Confirmar meu agendamento",
        use_container_width=True
    )

# ============================================================
# 12. VALIDAÇÃO E SALVAMENTO
# ============================================================

if enviar:
    nome_cliente = nome_cliente.strip()
    telefone_cliente = telefone_cliente.strip()

    telefone_digitos = re.sub(r"\D", "", telefone_cliente)

    if len(nome_cliente) < 3:
        st.warning("Informe seu nome completo.")

    elif len(telefone_digitos) < 10 or len(telefone_digitos) > 13:
        st.warning(
            "Informe um número de WhatsApp válido, incluindo o DDD."
        )

    elif not horario_selecionado:
        st.warning("Selecione um horário disponível.")

    elif data_escolhida < HOJE:
        st.error("Essa data já passou. Escolha outra data.")

    elif data_escolhida > data_maxima:
        st.error("Essa data está fora do período de agendamento.")

    elif (
        data_escolhida == HOJE
        and horario_selecionado <= datetime.now(TZ_BR).strftime("%H:%M")
    ):
        st.error("Esse horário já passou. Selecione outro.")

    else:
        # Consulta novamente para reduzir a possibilidade de
        # dois clientes selecionarem o mesmo horário.
        ocupados_final = buscar_horarios_ocupados(
            salao_id,
            data_escolhida
        )

        if horario_selecionado in ocupados_final:
            st.error(
                "Esse horário acabou de ser reservado. "
                "Escolha outro horário disponível."
            )
            st.rerun()

        else:
            try:
                salvar_agendamento(
                    salao_id=salao_id,
                    cliente_nome=nome_cliente,
                    cliente_contato=telefone_cliente,
                    servico_nome=servico_escolhido,
                    data_escolhida=data_escolhida,
                    hora=horario_selecionado
                )

                st.session_state.confirmacao_agendamento = {
                    "nome": nome_cliente,
                    "telefone": telefone_cliente,
                    "servico": servico_escolhido,
                    "preco": preco_servico,
                    "data": data_escolhida.strftime("%d/%m/%Y"),
                    "hora": horario_selecionado,
                    "duracao": duracao,
                }

                st.rerun()

            except IntegrityError:
                st.error(
                    "Esse horário não pôde ser reservado. "
                    "Confira a disponibilidade e tente novamente."
                )

            except Exception:
                st.error(
                    "Não foi possível salvar o agendamento. "
                    "Confira a estrutura da tabela agendamentos "
                    "e tente novamente."
                )

# ============================================================
# 13. COMPROVANTE VISUAL
# ============================================================

confirmacao = st.session_state.confirmacao_agendamento

if confirmacao:
    st.balloons()

    st.markdown("""
    <div class="hero">
        <div class="hero-icon">✅</div>
        <h1>Agendamento registrado!</h1>
        <p>Confira os dados da sua reserva abaixo.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="info-card">
        <div class="muted">CLIENTE</div>
        <div style="font-size:19px;font-weight:750">
            {confirmacao['nome']}
        </div>
        <hr style="border-color:#29374d">
        <div class="muted">SERVIÇO</div>
        <div style="font-size:17px;font-weight:700">
            {confirmacao['servico']}
        </div>
        <div style="color:#60a5fa;font-size:23px;font-weight:800">
            R$ {confirmacao['preco']:.2f}
        </div>
        <hr style="border-color:#29374d">
        <div class="muted">DATA E HORÁRIO</div>
        <div style="font-size:19px;font-weight:750">
            {confirmacao['data']} às {confirmacao['hora']}
        </div>
        <div class="muted">
            Duração estimada: {confirmacao['duracao']} minutos
        </div>
    </div>
    """.replace(".", ","),
    unsafe_allow_html=True)

    st.info(
        "Guarde os dados do agendamento. Se precisar alterar "
        "ou cancelar, entre em contato com o estabelecimento."
    )

st.markdown("""
<div class="footer">
    Agendamento Online · Fio&Caixa<br>
    Tecnologia para facilitar a rotina do seu salão.
</div>
""", unsafe_allow_html=True)

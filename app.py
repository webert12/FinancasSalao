import os
import re
import logging
import json
import hmac
import hashlib
import decimal
import secrets
import urllib.parse
import urllib.request
import urllib.error
from io import BytesIO
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from flask import Flask, render_template, render_template_string, request, redirect, url_for, session, jsonify, send_file, flash, abort
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

TZ = ZoneInfo("America/Sao_Paulo")
DB_URL = os.getenv("DB_URL", "")
SALT = os.getenv("SECURITY_SALT", "")
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "")
SUPPORT_PHONE = re.sub(r"\D", "", os.getenv("SUPPORT_PHONE", ""))
RENDER_BASE_URL = os.getenv("RENDER_BASE_URL", "").strip().rstrip("/")
# Endpoint público do servidor Baileys no Termux. Pode ser substituído no Render.
WHATSAPP_BOT_URL = os.getenv("WA_API_URL", "https://fioecaixa.serveusercontent.com/enviar").strip()
WHATSAPP_BOT_TOKEN = os.getenv("WA_API_TOKEN", "").strip()
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"

if not DB_URL:
    raise RuntimeError("DB_URL não configurada no ambiente do Render.")
if not SECRET_KEY:
    raise RuntimeError("FLASK_SECRET_KEY não configurada no ambiente do Render.")
if not SALT:
    raise RuntimeError("SECURITY_SALT não configurada no ambiente do Render.")

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=COOKIE_SECURE,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=10),
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)

# O PostgreSQL do Render pode estar atrás de um pooler em transaction mode.
# O psycopg 3 prepara statements automaticamente após algumas execuções; isso pode
# gerar DuplicatePreparedStatement (_pg3_*) no pooler. Desativamos esse recurso
# para manter as conexões compatíveis com o pooler, sem alterar os dados.
engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=1800,
    connect_args={"prepare_threshold": None},
)

# Preços iniciais sugeridos para uma barbearia de bairro no Brasil (referência 2026).
# Cada profissional pode editar os valores na aba Serviços; não são preços obrigatórios.
DEFAULT_SERVICES = {
    "Corte de Cabelo": 30.0,
    "Corte Social": 30.0,
    "Corte Degradê / Fade": 40.0,
    "Corte Taper Fade": 40.0,
    "Corte na Tesoura": 40.0,
    "Corte Navalhado": 40.0,
    "Corte Máquina": 25.0,
    "Corte Infantil": 25.0,
    "Raspar a Cabeça": 25.0,
    "Pezinho / Acabamento": 10.0,
    "Risco / Desenho no Cabelo": 15.0,
    "Penteado / Finalização": 20.0,
    "Barba": 30.0,
    "Barba na Máquina": 20.0,
    "Barba Completa na Navalha": 30.0,
    "Barba com Toalha Quente": 40.0,
    "Design de Barba": 35.0,
    "Cavanhaque": 15.0,
    "Pezinho da Barba": 10.0,
    "Sobrancelha": 15.0,
    "Sobrancelha na Navalha": 15.0,
    "Sobrancelha na Pinça": 20.0,
    "Depilação do Nariz": 15.0,
    "Depilação da Orelha": 15.0,
    "Limpeza de Pele": 50.0,
    "Esfoliação Facial": 30.0,
    "Hidratação Capilar": 40.0,
    "Pigmentação Capilar": 45.0,
    "Pigmentação de Barba": 35.0,
    "Matização": 45.0,
    "Luzes / Mechas": 120.0,
    "Platinado": 180.0,
    "Coloração / Tintura": 70.0,
    "Relaxamento Capilar": 70.0,
    "Alisamento Americano": 70.0,
    "Selagem Capilar": 90.0,
    "Progressiva": 100.0,
    "Combo Cabelo e Barba": 50.0,
    "Combo Corte + Sobrancelha": 40.0,
    "Combo Corte + Barba + Sobrancelha": 65.0,
    "Combo Corte + Barba + Toalha Quente": 75.0,
    "Combo Completo Premium": 90.0,
    "Pacote Noivo / Dia do Noivo": 180.0,
    "Mensalidade": 100.0,
}
ALLOWED_HOURS = [f"{h:02d}:{m:02d}" for h in range(8, 21) for m in (0, 30)]


def password_hash(password: str) -> str:
    return generate_password_hash(password, method="pbkdf2:sha256:600000")


def legacy_hash(password: str) -> str:
    return hmac.new(SALT.encode(), str(password).encode(), hashlib.sha256).hexdigest()


def verify_password(typed: str, stored: str) -> bool:
    if not typed or not stored:
        return False
    if stored.startswith(("pbkdf2:", "scrypt:", "argon2:")):
        try:
            return check_password_hash(stored, typed)
        except Exception:
            return False
    return hmac.compare_digest(str(stored), legacy_hash(typed)) or hmac.compare_digest(str(stored), str(typed))


def needs_password_upgrade(stored: str) -> bool:
    return not str(stored or "").startswith(("pbkdf2:", "scrypt:", "argon2:"))


def db_exec(sql, params=None, fetch=False):
    with engine.begin() as conn:
        result = conn.execute(text(sql), params or {})
        if fetch:
            return result.fetchall()
    return None


def init_db():
    statements = [
        "CREATE TABLE IF NOT EXISTS admin_config (id INT PRIMARY KEY, hash1 TEXT NOT NULL, hash2 TEXT NOT NULL, url_sistema TEXT);",
        "ALTER TABLE admin_config ADD COLUMN IF NOT EXISTS url_sistema TEXT;",
        # Older deployments may already have this table without a PRIMARY KEY/UNIQUE
        # constraint on id. Remove duplicate IDs before creating the unique index
        # required by ON CONFLICT(id). Keep one row per ID; this table is config-only.
        "DELETE FROM admin_config a USING admin_config b WHERE a.id=b.id AND a.ctid < b.ctid;",
        "CREATE UNIQUE INDEX IF NOT EXISTS admin_config_id_uidx ON admin_config(id);",
        "CREATE TABLE IF NOT EXISTS usuarios (id TEXT PRIMARY KEY, senha TEXT NOT NULL, email TEXT, tipo TEXT, vencimento TEXT, status TEXT, whatsapp TEXT);",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS whatsapp TEXT;",
        "CREATE TABLE IF NOT EXISTS servicos (id SERIAL PRIMARY KEY, usuario_id TEXT NOT NULL, nome TEXT NOT NULL, preco NUMERIC NOT NULL);",
        "ALTER TABLE servicos ADD COLUMN IF NOT EXISTS ativo BOOLEAN NOT NULL DEFAULT TRUE;",
        "CREATE TABLE IF NOT EXISTS fluxo_caixa (id SERIAL PRIMARY KEY, usuario_id TEXT NOT NULL, data TEXT NOT NULL, tipo TEXT NOT NULL, descricao TEXT NOT NULL, valor NUMERIC NOT NULL);",
        "CREATE TABLE IF NOT EXISTS agendamentos (id SERIAL PRIMARY KEY, usuario_id TEXT NOT NULL, cliente_nome TEXT NOT NULL, cliente_contato TEXT, servico_nome TEXT NOT NULL, data TEXT NOT NULL, hora TEXT NOT NULL, status TEXT DEFAULT 'Pendente', valor NUMERIC DEFAULT 0, confirmado_em TIMESTAMP, concluido_em TIMESTAMP, financeiro_id INT);",
        "ALTER TABLE agendamentos ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Pendente';",
        "ALTER TABLE agendamentos ADD COLUMN IF NOT EXISTS valor NUMERIC DEFAULT 0;",
        "ALTER TABLE agendamentos ADD COLUMN IF NOT EXISTS confirmado_em TIMESTAMP;",
        "ALTER TABLE agendamentos ADD COLUMN IF NOT EXISTS concluido_em TIMESTAMP;",
        "ALTER TABLE agendamentos ADD COLUMN IF NOT EXISTS financeiro_id INT;",
        "ALTER TABLE fluxo_caixa ADD COLUMN IF NOT EXISTS appointment_id INT;",
        "ALTER TABLE fluxo_caixa ADD COLUMN IF NOT EXISTS hora TEXT;",
        "UPDATE agendamentos SET status='Pendente' WHERE status IS NULL;",
        "UPDATE agendamentos SET valor=COALESCE((SELECT preco FROM servicos s WHERE s.usuario_id=agendamentos.usuario_id AND s.nome=agendamentos.servico_nome),0) WHERE valor IS NULL OR valor=0;",
        "CREATE TABLE IF NOT EXISTS clientes_mensais (id SERIAL PRIMARY KEY, usuario_id TEXT NOT NULL, nome_cliente TEXT NOT NULL, telefone TEXT, servicos_feitos INT DEFAULT 0, valor_devido NUMERIC DEFAULT 0.0, status_divida TEXT DEFAULT 'Pendente');",
        "CREATE TABLE IF NOT EXISTS usuario_config (usuario_id TEXT PRIMARY KEY, meta_mensal NUMERIC DEFAULT 5000);",
        "CREATE TABLE IF NOT EXISTS login_rate (chave TEXT PRIMARY KEY, tentativas INT NOT NULL DEFAULT 0, janela_inicio TIMESTAMP NOT NULL);",
        "CREATE INDEX IF NOT EXISTS idx_fluxo_usuario_data ON fluxo_caixa(usuario_id, data);",
        "CREATE INDEX IF NOT EXISTS idx_agend_usuario_data_hora ON agendamentos(usuario_id, data, hora);",
        "CREATE INDEX IF NOT EXISTS idx_servicos_usuario ON servicos(usuario_id);",
        "CREATE INDEX IF NOT EXISTS idx_mensais_usuario ON clientes_mensais(usuario_id);",
    ]
    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))


init_db()


def app_base_url():
    # A URL do próprio request é a fonte mais confiável quando o serviço está no Render.
    # RENDER_BASE_URL pode ser usada para forçar uma URL personalizada.
    return (RENDER_BASE_URL or request.url_root.rstrip("/")).rstrip("/")


def booking_url(user):
    return f"{app_base_url()}/agendar?salao={urllib.parse.quote(user)}"


def send_whatsapp_notification(phone, message):
    """Envia a notificação ao bot Baileys no Termux, sem bloquear o salvamento."""
    number = normalize_phone(phone)
    if not number:
        app.logger.warning("WhatsApp não enviado: salão sem número cadastrado")
        return False
    endpoint = WHATSAPP_BOT_URL.rstrip()
    if not endpoint:
        app.logger.error("WhatsApp não enviado: WA_API_URL não configurada")
        return False
    # Aceita tanto o domínio público do túnel quanto a URL completa da rota.
    # O server.js do Termux recebe POST apenas em /enviar; POST / retorna 404.
    parsed_endpoint = urllib.parse.urlsplit(endpoint)
    if parsed_endpoint.path in ("", "/"):
        endpoint = urllib.parse.urlunsplit((
            parsed_endpoint.scheme, parsed_endpoint.netloc, "/enviar",
            parsed_endpoint.query, parsed_endpoint.fragment
        ))
    elif not parsed_endpoint.path.rstrip("/").endswith("/enviar"):
        endpoint = endpoint.rstrip("/") + "/enviar"
    payload = json.dumps({"telefone": number, "mensagem": message}, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    # Token opcional; o server.js atual aceita JSON sem autenticação.
    if WHATSAPP_BOT_TOKEN:
        headers["Authorization"] = f"Bearer {WHATSAPP_BOT_TOKEN}"
    req = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            body = response.read(1000).decode("utf-8", errors="replace")
            if 200 <= response.status < 300:
                app.logger.info("Notificação WhatsApp enviada pelo bot: telefone final=%s", number[-4:])
                return True
            app.logger.error("Bot WhatsApp respondeu HTTP %s: %s", response.status, body)
    except urllib.error.HTTPError as exc:
        body = exc.read(1000).decode("utf-8", errors="replace")
        app.logger.error("Falha HTTP do bot WhatsApp (%s): %s", exc.code, body)
    except Exception:
        app.logger.exception("Não foi possível alcançar o bot WhatsApp em %s", endpoint)
    return False


def whatsapp_url(phone, message=None):
    number = re.sub(r"\D", "", str(phone or ""))
    if not number:
        return ""
    base = f"https://wa.me/{number}"
    return base + ("?text=" + urllib.parse.quote(message) if message else "")


def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


@app.context_processor
def inject_globals():
    return {
        "logged_user": current_user(),
        "is_admin": require_admin(),
        "now": datetime.now(TZ),
        "base_url": app_base_url(),
        "csrf_token": csrf_token(),
        "support_url": whatsapp_url(SUPPORT_PHONE, "Olá! Gostaria de falar sobre o sistema Fio & Caixa."),
    }


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def validate_csrf():
    expected = session.get("csrf_token")
    supplied = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
    if not expected or not supplied or not hmac.compare_digest(str(expected), str(supplied)):
        abort(400, description="Token de segurança inválido. Atualize a página e tente novamente.")


@app.before_request
def csrf_guard():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        # O cadastro público também recebe um token de sessão e, portanto, continua protegido.
        validate_csrf()
    if current_user() and not require_admin() and request.endpoint not in {"logout", "login", "setup", "booking", "booking_slots", "static"}:
        u = users().get(current_user())
        if not user_valid(u):
            session.clear()
            if request.path.startswith("/api/"):
                return jsonify({"error": "Sessão expirada ou licença vencida."}), 401
            return redirect(url_for("index"))


def admin_config():
    rows = db_exec("SELECT hash1, hash2, url_sistema FROM admin_config WHERE id=1", fetch=True)
    return tuple(rows[0]) if rows else (None, None, None)


def save_admin(h1, h2, url):
    db_exec("""INSERT INTO admin_config(id,hash1,hash2,url_sistema) VALUES(1,:h1,:h2,:url)
               ON CONFLICT(id) DO UPDATE SET hash1=EXCLUDED.hash1, hash2=EXCLUDED.hash2, url_sistema=EXCLUDED.url_sistema""",
            {"h1": h1, "h2": h2, "url": url})


def users():
    rows = db_exec("SELECT id, senha, email, tipo, vencimento, status, whatsapp FROM usuarios", fetch=True)
    return {str(r[0]).strip().lower(): {"id": str(r[0]).strip().lower(), "senha": r[1], "email": r[2] or "", "tipo": r[3] or "Cliente", "vencimento": r[4], "status": r[5] or "Ativo", "whatsapp": r[6] or ""} for r in rows}


def save_user(user_id, data):
    venc = data.get("vencimento")
    if hasattr(venc, "strftime"):
        venc = venc.strftime("%Y-%m-%d")
    db_exec("""INSERT INTO usuarios(id,senha,email,tipo,vencimento,status,whatsapp) VALUES(:id,:senha,:email,:tipo,:venc,:status,:wa)
               ON CONFLICT(id) DO UPDATE SET senha=EXCLUDED.senha,email=EXCLUDED.email,tipo=EXCLUDED.tipo,vencimento=EXCLUDED.vencimento,status=EXCLUDED.status,whatsapp=EXCLUDED.whatsapp""",
            {"id": user_id.strip().lower(), "senha": data["senha"], "email": data.get("email", ""), "tipo": data.get("tipo", "Cliente"), "venc": str(venc), "status": data.get("status", "Ativo"), "wa": data.get("whatsapp", "")})


def current_user():
    return session.get("usuario_logado")


def require_login():
    return current_user() is not None


def require_admin():
    return session.get("eh_admin") is True


def user_valid(user):
    if not user:
        return False
    try:
        venc = datetime.strptime(str(user.get("vencimento")), "%Y-%m-%d").date()
    except Exception:
        return False
    return user.get("status") == "Ativo" and datetime.now(TZ).date() <= venc


def get_services(user):
    # Insere os serviços sugeridos que ainda não existem para esse salão.
    # Valores que o usuário já cadastrou/editou são preservados; serviços inativados
    # pelo barbeiro não são recriados automaticamente.
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT nome FROM servicos WHERE usuario_id=:u"), {"u": user}
        ).fetchall()
        existing_names = {str(row[0]) for row in existing}
        for name, price in DEFAULT_SERVICES.items():
            if name not in existing_names:
                conn.execute(
                    text("INSERT INTO servicos(usuario_id,nome,preco,ativo) VALUES(:u,:n,:p,TRUE)"),
                    {"u": user, "n": name, "p": price},
                )
    rows = db_exec(
        "SELECT nome, preco FROM servicos WHERE usuario_id=:u AND ativo=TRUE ORDER BY nome",
        {"u": user}, True,
    )
    return {r[0]: float(r[1]) for r in rows}


def get_flow(user):
    rows = db_exec("SELECT id,data,tipo,descricao,valor,hora FROM fluxo_caixa WHERE usuario_id=:u ORDER BY data DESC,hora DESC NULLS LAST,id DESC", {"u": user}, True)
    df = pd.DataFrame(rows, columns=["id", "Data", "Tipo", "Descrição", "Valor", "Horário"])
    if df.empty:
        return df
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0).astype(float)
    return df


def get_appointments(user, only_upcoming=False):
    where = "WHERE usuario_id=:u"
    if only_upcoming:
        where += " AND (data > :today OR (data = :today AND hora >= :hora))"
    params = {"u": user}
    if only_upcoming:
        now = datetime.now(TZ)
        params.update({"today": now.strftime("%Y-%m-%d"), "hora": now.strftime("%H:%M")})
    rows = db_exec(f"SELECT id,cliente_nome,cliente_contato,servico_nome,data,hora,status,valor FROM agendamentos {where} ORDER BY data,hora", params, True)
    return pd.DataFrame(rows, columns=["id", "Cliente", "Contato", "Serviço", "Data", "Horário", "Status", "Valor"])


def get_monthly(user):
    rows = db_exec("SELECT id,nome_cliente,telefone,servicos_feitos,valor_devido,status_divida FROM clientes_mensais WHERE usuario_id=:u ORDER BY id DESC", {"u": user}, True)
    return pd.DataFrame(rows, columns=["id", "Cliente", "Telefone", "Serviços Feitos", "Valor Devido", "Status"])


def get_goal(user):
    row = db_exec("SELECT meta_mensal FROM usuario_config WHERE usuario_id=:u", {"u": user}, True)
    return float(row[0][0]) if row else 5000.0


def set_goal(user, goal):
    db_exec("""INSERT INTO usuario_config(usuario_id,meta_mensal) VALUES(:u,:g)
               ON CONFLICT(usuario_id) DO UPDATE SET meta_mensal=EXCLUDED.meta_mensal""", {"u": user, "g": float(goal)})


def insert_flow(user, tipo, descricao, valor, data=None):
    now = datetime.now(TZ)
    data = data or now.date()
    data_str = data.strftime("%Y-%m-%d") if hasattr(data, "strftime") else str(data)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data_str):
        data_str = now.date().isoformat()
    if tipo not in {"Entrada", "Saída", "Pendência"}:
        raise ValueError("Tipo de movimentação inválido")
    db_exec("INSERT INTO fluxo_caixa(usuario_id,data,hora,tipo,descricao,valor) VALUES(:u,:d,:h,:t,:desc,:v)",
            {"u": user, "d": data_str, "h": now.strftime("%H:%M:%S"), "t": tipo, "desc": str(descricao).strip()[:250], "v": float(valor)})


def percent_change(current, previous):
    if current == previous == 0:
        return 0.0
    if previous == 0:
        return 100.0
    return ((current - previous) / abs(previous)) * 100


def calc_dashboard(user):
    df = get_flow(user)
    today = datetime.now(TZ).date()
    if df.empty:
        df = pd.DataFrame(columns=["id", "Data", "Tipo", "Descrição", "Valor"])
    clean = df.dropna(subset=["Data"]).copy() if not df.empty else df
    m, y = today.month, today.year
    pm, py = (m - 1, y) if m > 1 else (12, y - 1)
    cur = clean[(clean.Data.dt.month == m) & (clean.Data.dt.year == y)] if not clean.empty else clean
    prev = clean[(clean.Data.dt.month == pm) & (clean.Data.dt.year == py)] if not clean.empty else clean
    year = clean[clean.Data.dt.year == y] if not clean.empty else clean
    receita_dia = float(clean[(clean.Data.dt.date == today) & clean.Tipo.isin(["Entrada", "Pendência"])].Valor.sum()) if not clean.empty else 0
    receita_mes = float(cur[cur.Tipo.isin(["Entrada", "Pendência"])].Valor.sum()) if not cur.empty else 0
    receita_ano = float(year[year.Tipo.isin(["Entrada", "Pendência"])].Valor.sum()) if not year.empty else 0
    entradas = float(cur[cur.Tipo == "Entrada"].Valor.sum()) if not cur.empty else 0
    saidas = abs(float(cur[cur.Tipo == "Saída"].Valor.sum())) if not cur.empty else 0
    lucro = entradas - saidas
    receita_prev = float(prev[prev.Tipo.isin(["Entrada", "Pendência"])].Valor.sum()) if not prev.empty else 0
    entradas_prev = float(prev[prev.Tipo == "Entrada"].Valor.sum()) if not prev.empty else 0
    saidas_prev = abs(float(prev[prev.Tipo == "Saída"].Valor.sum())) if not prev.empty else 0
    lucro_prev = entradas_prev - saidas_prev
    appts = get_appointments(user)
    appt_today = appts[appts.Data.astype(str) == today.strftime("%Y-%m-%d")] if not appts.empty else appts
    pending_appts = int((appts["Status"] == "Pendente").sum()) if not appts.empty else 0
    confirmed_appts = int((appts["Status"] == "Confirmado").sum()) if not appts.empty else 0
    monthly = get_monthly(user)
    clients = set(monthly.Cliente.dropna()) if not monthly.empty else set()
    clients.update(appts.Cliente.dropna() if not appts.empty else [])
    goal = get_goal(user)
    progress = min(100.0, (receita_mes / goal * 100) if goal > 0 else 0)
    return {
        "receita_dia": receita_dia, "receita_mes": receita_mes, "receita_ano": receita_ano, "lucro": lucro,
        "pct_receita": percent_change(receita_mes, receita_prev), "pct_lucro": percent_change(lucro, lucro_prev),
        "ticket": entradas / len(cur[cur.Tipo == "Entrada"]) if not cur.empty and len(cur[cur.Tipo == "Entrada"]) else 0,
        "clientes": len(clients), "agendamentos_hoje": len(appt_today), "today": today.strftime("%d/%m"),
        "mes_passado": receita_prev, "goal": goal, "goal_progress": progress,
        "agendamentos_pendentes": pending_appts, "agendamentos_confirmados": confirmed_appts,
    }


def daily_chart(user, days=7):
    today = datetime.now(TZ).date()
    start = today - timedelta(days=days - 1)
    rows = db_exec("""SELECT data, tipo, valor FROM fluxo_caixa
                      WHERE usuario_id=:u AND data>=:start AND data<=:end
                      ORDER BY data""", {"u": user, "start": start.isoformat(), "end": today.isoformat()}, True)
    by_day = { (start + timedelta(days=i)).isoformat(): {"entrada": 0.0, "saida": 0.0} for i in range(days) }
    for d, tipo, valor in rows:
        key = str(d)
        if key in by_day:
            if tipo == "Entrada": by_day[key]["entrada"] += float(valor)
            elif tipo == "Saída": by_day[key]["saida"] += abs(float(valor))
    return [{"date": k, "label": datetime.strptime(k, "%Y-%m-%d").strftime("%d/%m"), **v} for k, v in by_day.items()]


def backup_json(user):
    def rows(table, columns):
        return [dict(zip(columns, r)) for r in db_exec(f"SELECT {','.join(columns)} FROM {table} WHERE usuario_id=:u", {"u": user}, True)]
    payload = {
        "sistema": "Fio&Caixa",
        "versao": "2.0",
        "usuario_dono": user,
        "data_geracao": datetime.now(TZ).isoformat(),
        "meta_mensal": get_goal(user),
        "servicos": rows("servicos", ["id", "nome", "preco"]),
        "historico_financeiro": rows("fluxo_caixa", ["id", "data", "tipo", "descricao", "valor"]),
        "agendamentos": rows("agendamentos", ["id", "cliente_nome", "cliente_contato", "servico_nome", "data", "hora", "status", "valor"]),
        "clientes_mensais": rows("clientes_mensais", ["id", "nome_cliente", "telefone", "servicos_feitos", "valor_devido", "status_divida"]),
    }
    def ser(o):
        if isinstance(o, decimal.Decimal): return float(o)
        if isinstance(o, (datetime, pd.Timestamp)): return o.isoformat()
        return str(o)
    return json.dumps(payload, ensure_ascii=False, indent=2, default=ser)


def make_pdf(df, ref):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("DocTitle", parent=styles["Heading1"], fontSize=16, textColor=colors.HexColor("#38bdf8"), spaceAfter=15)
    story = [Paragraph(f"Fio&Caixa - Relatório Contábil ({ref})", title)]
    data = [["Data", "Tipo", "Descrição", "Valor"]]
    for _, r in df.iterrows():
        data.append([r["Data"].strftime("%d/%m/%Y"), str(r["Tipo"]), str(r["Descrição"]), f"R$ {float(r['Valor']):,.2f}"])
    t = Table(data, colWidths=[70, 70, 300, 90])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(t)
    doc.build(story)
    buf.seek(0)
    return buf


def rate_key(prefix="login"):
    # IP não é exibido ao usuário e serve apenas para limitar tentativas abusivas.
    return f"{prefix}:{request.remote_addr or 'unknown'}"


def login_allowed(key, limit=8, window_minutes=10):
    now = datetime.utcnow()
    row = db_exec("SELECT tentativas, janela_inicio FROM login_rate WHERE chave=:k", {"k": key}, True)
    if not row:
        return True
    attempts, started = row[0]
    if now - started > timedelta(minutes=window_minutes):
        db_exec("DELETE FROM login_rate WHERE chave=:k", {"k": key})
        return True
    return int(attempts) < limit


def register_failed_login(key):
    """Registra tentativa inválida sem depender de um SELECT FOR UPDATE em linha ausente."""
    now = datetime.utcnow()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT tentativas, janela_inicio FROM login_rate WHERE chave=:k"),
            {"k": key},
        ).fetchone()
        if row is None:
            conn.execute(
                text("INSERT INTO login_rate(chave,tentativas,janela_inicio) VALUES(:k,1,:now) ON CONFLICT(chave) DO UPDATE SET tentativas=login_rate.tentativas+1"),
                {"k": key, "now": now},
            )
        elif now - row[1] > timedelta(minutes=10):
            conn.execute(
                text("UPDATE login_rate SET tentativas=1, janela_inicio=:now WHERE chave=:k"),
                {"k": key, "now": now},
            )
        else:
            conn.execute(
                text("UPDATE login_rate SET tentativas=tentativas+1 WHERE chave=:k"),
                {"k": key},
            )


def clear_login_rate(key):
    db_exec("DELETE FROM login_rate WHERE chave=:k", {"k": key})


def normalize_phone(value):
    digits = re.sub(r"\D", "", str(value or ""))
    if digits.startswith("00"):
        digits = digits[2:]
    return digits


def valid_date_time(date, hour):
    if hour not in ALLOWED_HOURS:
        return None
    try:
        dt = datetime.strptime(f"{date} {hour}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    except ValueError:
        return None
    return dt


@app.route("/", methods=["GET"])
def index():
    salao = request.args.get("salao")
    if salao and not require_login():
        return redirect(url_for("booking", salao=salao))
    if not require_login():
        h1, h2, _ = admin_config()
        return render_template("login.html", initialized=bool(h1 and h2), support_phone=SUPPORT_PHONE)
    if require_admin():
        return redirect(url_for("admin"))
    return redirect(url_for("dashboard"))


@app.route("/setup", methods=["GET", "POST"])
def setup():
    if admin_config()[0]:
        return redirect(url_for("index"))
    if request.method == "POST":
        p1 = request.form.get("senha1", "")
        p2 = request.form.get("senha2", "")
        base = request.form.get("url", app_base_url()).strip().rstrip("/")
        if len(p1) < 8 or len(p2) < 8:
            flash("Use pelo menos 8 caracteres em cada senha.", "error")
        elif p1 == p2:
            flash("As duas senhas administrativas devem ser diferentes.", "error")
        else:
            save_admin(password_hash(p1), password_hash(p2), base)
            flash("Administração inicializada com segurança.", "success")
            return redirect(url_for("index"))
    return render_template("setup.html")


@app.route("/login", methods=["POST"])
def login():
    key = rate_key()
    if not login_allowed(key):
        flash("Muitas tentativas. Aguarde alguns minutos e tente novamente.", "error")
        return redirect(url_for("index"))
    mode = request.form.get("tipo", "salao")
    user = request.form.get("usuario", "").strip().lower()
    password = request.form.get("senha", "")
    h1, h2, _ = admin_config()
    ok = False
    if mode == "admin":
        second = request.form.get("senha2", "")
        ok = bool(h1 and h2 and user == "admin" and verify_password(password, h1) and verify_password(second, h2))
        if ok:
            # Migra senhas legadas automaticamente para hashes modernos.
            if needs_password_upgrade(h1) or needs_password_upgrade(h2):
                save_admin(password_hash(password), password_hash(second), admin_config()[2] or app_base_url())
            session.clear(); session.permanent = True; session.update(usuario_logado="Administrador", eh_admin=True, csrf_token=secrets.token_urlsafe(32)); clear_login_rate(key)
            return redirect(url_for("admin"))
    else:
        u = users().get(user)
        ok = bool(u and verify_password(password, u["senha"]) and user_valid(u))
        if ok:
            if needs_password_upgrade(u["senha"]):
                u["senha"] = password_hash(password); save_user(user, u)
            session.clear(); session.permanent = True; session.update(usuario_logado=user, eh_admin=False, csrf_token=secrets.token_urlsafe(32)); clear_login_rate(key)
            return redirect(url_for("dashboard"))
    register_failed_login(key)
    flash("Credenciais inválidas ou acesso expirado.", "error")
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    if not require_login() or require_admin():
        return redirect(url_for("index"))
    user = current_user()
    d = calc_dashboard(user)
    appts = get_appointments(user, only_upcoming=False)
    flow_records = get_flow(user).to_dict("records")
    pending_credits = [r for r in flow_records if r.get("Tipo") == "Pendência"]
    return render_template(
        "dashboard.html", user=user, name=user.replace("_", " ").replace("-", " ").title(),
        services=get_services(user), dash=d, appointments=appts.to_dict("records"),
        monthly=get_monthly(user).to_dict("records"), flow=flow_records, pending_credits=pending_credits,
        chart=daily_chart(user), booking_link=booking_url(user),
    )


@app.route("/api/dashboard")
def api_dashboard():
    if not require_login() or require_admin():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"dashboard": calc_dashboard(current_user()), "chart": daily_chart(current_user())})


@app.route("/api/goal", methods=["POST"])
def api_goal():
    if not require_login() or require_admin(): return jsonify({"error": "unauthorized"}), 401
    d = request.get_json() or {}
    try: goal = float(d.get("goal", 0))
    except (TypeError, ValueError): return jsonify({"error": "Meta inválida"}), 400
    if goal < 0 or goal > 100000000: return jsonify({"error": "Meta inválida"}), 400
    set_goal(current_user(), goal)
    return jsonify({"ok": True, "goal": goal})


@app.route("/api/services", methods=["POST", "DELETE"])
def api_services():
    if not require_login() or require_admin(): return jsonify({"error": "unauthorized"}), 401
    user = current_user()
    if request.method == "POST":
        data = request.get_json() or {}
        name = str(data.get("name", "")).strip()[:100]
        try: price = float(data.get("price", 0) or 0)
        except (TypeError, ValueError): return jsonify({"error": "Preço inválido"}), 400
        old = str(data.get("old", "")).strip()
        if not name or price < 0: return jsonify({"error": "Informe nome e preço válidos"}), 400
        if old and old != "__new__":
            db_exec("UPDATE servicos SET nome=:n,preco=:p,ativo=TRUE WHERE usuario_id=:u AND nome=:o", {"n": name, "p": price, "u": user, "o": old})
        else:
            existing = db_exec("SELECT id FROM servicos WHERE usuario_id=:u AND nome=:n ORDER BY id LIMIT 1", {"u": user, "n": name}, True)
            if existing:
                db_exec("UPDATE servicos SET preco=:p,ativo=TRUE WHERE usuario_id=:u AND nome=:n", {"p": price, "u": user, "n": name})
            else:
                db_exec("INSERT INTO servicos(usuario_id,nome,preco,ativo) VALUES(:u,:n,:p,TRUE)", {"u": user, "n": name, "p": price})
    else:
        name = request.args.get("name", "")
        # Inativação preserva o histórico e evita que um padrão removido reapareça.
        db_exec("UPDATE servicos SET ativo=FALSE WHERE usuario_id=:u AND nome=:n", {"u": user, "n": name})
    return jsonify({"ok": True, "services": get_services(user)})


@app.route("/api/flow", methods=["POST", "DELETE"])
def api_flow():
    if not require_login() or require_admin(): return jsonify({"error": "unauthorized"}), 401
    user = current_user()
    if request.method == "POST":
        d = request.get_json() or {}
        try: value = float(d.get("valor", 0))
        except (TypeError, ValueError): return jsonify({"error": "Valor inválido"}), 400
        if value == 0: return jsonify({"error": "Informe um valor diferente de zero"}), 400
        try: insert_flow(user, d.get("tipo"), d.get("descricao", ""), value, d.get("data") or datetime.now(TZ).date())
        except ValueError as exc: return jsonify({"error": str(exc)}), 400
    else:
        try: rid = int(request.args.get("id"))
        except (TypeError, ValueError): return jsonify({"error": "Movimentação inválida"}), 400
        db_exec("DELETE FROM fluxo_caixa WHERE id=:id AND usuario_id=:u", {"id": rid, "u": user})
    return jsonify({"ok": True})


@app.route("/api/flow/<int:rid>/pay", methods=["POST"])
def pay_credit(rid):
    if not require_login() or require_admin(): return jsonify({"error": "unauthorized"}), 401
    user = current_user()
    row = db_exec("SELECT descricao,valor FROM fluxo_caixa WHERE id=:id AND usuario_id=:u AND tipo='Pendência'", {"id": rid, "u": user}, True)
    if not row: return jsonify({"error": "Fiado não encontrado"}), 404
    now = datetime.now(TZ)
    db_exec("UPDATE fluxo_caixa SET tipo='Entrada',data=:d,hora=:h,descricao=:desc WHERE id=:id AND usuario_id=:u", {"d": now.strftime("%Y-%m-%d"), "h": now.strftime("%H:%M:%S"), "desc": str(row[0][0]).replace("Fiado de:", "Recebido Fiado:") + " [PAGO]", "id": rid, "u": user})
    return jsonify({"ok": True})


@app.route("/api/monthly", methods=["POST"])
def api_monthly():
    if not require_login() or require_admin(): return jsonify({"error": "unauthorized"}), 401
    user = current_user(); d = request.get_json() or {}; action = d.get("action")
    if action == "create":
        name = str(d.get("name", "")).strip()[:100]; phone = normalize_phone(d.get("phone", ""))[:20]
        if not name: return jsonify({"error": "Informe o nome"}), 400
        db_exec("INSERT INTO clientes_mensais(usuario_id,nome_cliente,telefone) VALUES(:u,:n,:t)", {"u": user, "n": name, "t": phone})
    elif action == "service":
        try: rid, qty, price = int(d["id"]), int(d.get("qty", 1)), float(d.get("price", 0))
        except (KeyError, TypeError, ValueError): return jsonify({"error": "Dados inválidos"}), 400
        if qty < 1 or price < 0: return jsonify({"error": "Quantidade/valor inválidos"}), 400
        db_exec("UPDATE clientes_mensais SET servicos_feitos=servicos_feitos+:q,valor_devido=valor_devido+:v,status_divida='Pendente' WHERE id=:id AND usuario_id=:u", {"q": qty, "v": qty * price, "id": rid, "u": user})
    elif action == "pay":
        try: rid, value = int(d["id"]), float(d["value"])
        except (KeyError, TypeError, ValueError): return jsonify({"error": "Dados inválidos"}), 400
        row = db_exec("SELECT valor_devido,nome_cliente FROM clientes_mensais WHERE id=:id AND usuario_id=:u", {"id": rid, "u": user}, True)
        if not row: return jsonify({"error": "Cliente não encontrado"}), 404
        debt = float(row[0][0]); value = min(max(value, 0), debt)
        new = max(0, debt - value); status = "Quitado" if new == 0 else "Pendente"
        db_exec("UPDATE clientes_mensais SET valor_devido=:v,status_divida=:s WHERE id=:id AND usuario_id=:u", {"v": new, "s": status, "id": rid, "u": user})
        if value > 0: insert_flow(user, "Entrada", f"Mensalidade recebida: {row[0][1]}", value, datetime.now(TZ).date())
    else:
        return jsonify({"error": "Ação inválida"}), 400
    return jsonify({"ok": True})


@app.route("/api/appointments", methods=["POST"])
def create_appointment():
    if not require_login() or require_admin(): return jsonify({"error": "unauthorized"}), 401
    user = current_user(); d = request.get_json() or {}
    name = str(d.get("nome", "")).strip()[:100]
    phone = normalize_phone(d.get("telefone", ""))[:20]
    service = str(d.get("servico", "")).strip()
    date = str(d.get("data", "")); hour = str(d.get("hora", ""))
    services = get_services(user)
    dt = valid_date_time(date, hour)
    if not name or service not in services or not dt or dt <= datetime.now(TZ):
        return jsonify({"error": "Dados do agendamento inválidos"}), 400
    try:
        with engine.begin() as conn:
            lock_key = int(hashlib.sha256(f"{user}|{date}|{hour}".encode()).hexdigest()[:15], 16) % (2**63 - 1)
            conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": lock_key})
            exists = conn.execute(text("SELECT 1 FROM agendamentos WHERE usuario_id=:u AND data=:d AND hora=:h AND COALESCE(status, 'Pendente') <> 'Cancelado'"), {"u": user, "d": date, "h": hour}).fetchone()
            if exists: return jsonify({"error": "Esse horário já está ocupado"}), 409
            conn.execute(text("INSERT INTO agendamentos(usuario_id,cliente_nome,cliente_contato,servico_nome,data,hora,status,valor) VALUES(:u,:n,:c,:s,:d,:h,'Pendente',:v)"), {"u": user, "n": name, "c": phone, "s": service, "d": date, "h": hour, "v": float(services[service])})
    except Exception:
        return jsonify({"error": "Não foi possível criar o agendamento"}), 500
    return jsonify({"ok": True})


@app.route("/api/appointments/<int:aid>", methods=["POST", "DELETE"])
def appointment_action(aid):
    if not require_login() or require_admin():
        return jsonify({"error": "unauthorized"}), 401
    user = current_user()
    row = db_exec("SELECT cliente_nome,servico_nome,cliente_contato,data,hora,status,valor FROM agendamentos WHERE id=:id AND usuario_id=:u", {"id": aid, "u": user}, True)
    if not row:
        return jsonify({"error": "Agendamento não encontrado"}), 404
    client, service, phone, date, hour, status, stored_value = row[0]
    status = status or "Pendente"
    price = float(stored_value or get_services(user).get(service, 0))
    if request.method == "DELETE":
        db_exec("UPDATE agendamentos SET status='Cancelado' WHERE id=:id AND usuario_id=:u", {"id": aid, "u": user})
        return jsonify({"ok": True, "status": "Cancelado"})

    data = request.get_json(silent=True) or request.form
    action = str(data.get("action", "confirm")).strip().lower()
    now = datetime.now(TZ)
    if action == "confirm":
        if status != "Pendente":
            return jsonify({"error": "Este agendamento já foi processado."}), 409
        db_exec("UPDATE agendamentos SET status='Confirmado',confirmado_em=:now,valor=:v WHERE id=:id AND usuario_id=:u", {"now": now, "v": price, "id": aid, "u": user})
        return jsonify({"ok": True, "status": "Confirmado"})
    if action in {"complete", "fiado"}:
        if status != "Confirmado":
            return jsonify({"error": "Confirme o agendamento antes de concluir o atendimento."}), 409
        tipo = "Entrada" if action == "complete" else "Pendência"
        prefix = "Atendimento agendado" if action == "complete" else "Fiado - atendimento agendado"
        desc = f"{prefix}: {client} ({service}) [Agendamento #{aid}]"
        with engine.begin() as conn:
            result = conn.execute(text("INSERT INTO fluxo_caixa(usuario_id,data,hora,tipo,descricao,valor,appointment_id) VALUES(:u,:d,:h,:t,:desc,:v,:aid) RETURNING id"), {"u": user, "d": now.date().isoformat(), "h": now.strftime("%H:%M:%S"), "t": tipo, "desc": desc, "v": price, "aid": aid})
            flow_id = result.scalar()
            conn.execute(text("UPDATE agendamentos SET status='Concluído',concluido_em=:now,valor=:v,financeiro_id=:fid WHERE id=:id AND usuario_id=:u"), {"now": now, "v": price, "fid": flow_id, "id": aid, "u": user})
        return jsonify({"ok": True, "status": "Concluído", "tipo": tipo, "financeiro_id": flow_id})
    if action == "cancel":
        db_exec("UPDATE agendamentos SET status='Cancelado' WHERE id=:id AND usuario_id=:u", {"id": aid, "u": user})
        return jsonify({"ok": True, "status": "Cancelado"})
    return jsonify({"error": "Ação inválida"}), 400


BOOKING_TEMPLATE = r"""
<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="theme-color" content="#0b1220">
<title>Agendar horário | Fio&Caixa</title>
<style>
:root{color-scheme:dark;--bg:#08111f;--panel:#101b2d;--panel2:#142238;--line:#263750;--text:#edf4ff;--muted:#9aacc5;--blue:#3b82f6;--blue2:#2563eb}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 10% 0%,#142a49 0,transparent 34%),var(--bg);color:var(--text);font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif;line-height:1.45}
.wrap{width:min(1040px,100%);margin:0 auto;padding:24px 16px 48px}.brand{display:flex;align-items:center;gap:12px;margin-bottom:22px}.logo{width:46px;height:46px;border-radius:14px;display:grid;place-items:center;background:linear-gradient(135deg,#60a5fa,#2563eb);font-size:23px;font-weight:900;color:white}.brand h1{font-size:20px;margin:0;font-weight:800}.brand p{margin:2px 0 0;color:var(--muted);font-size:12px}
.hero{margin-bottom:22px}.eyebrow{color:#93c5fd;text-transform:uppercase;letter-spacing:1.8px;font-size:11px;font-weight:800}.hero h2{font-size:clamp(26px,5vw,38px);line-height:1.12;margin:8px 0}.hero p{color:var(--muted);margin:0;max-width:650px}
.layout{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(280px,.9fr);gap:18px;align-items:start}.panel{background:linear-gradient(180deg,#111e31,#0d1727);border:1px solid var(--line);border-radius:20px;padding:20px;box-shadow:0 18px 45px #0002}.panel h3{font-size:16px;margin:0 0 4px}.sub{color:var(--muted);font-size:13px;margin:0 0 18px}
.monthbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:12px 0 14px}.monthbar strong{font-size:15px;text-transform:capitalize}.iconbtn{border:1px solid var(--line);background:var(--panel2);color:var(--text);width:38px;height:38px;border-radius:11px;font-size:20px;cursor:pointer}.iconbtn:disabled{opacity:.3;cursor:not-allowed}
.week,.days{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px}.week span{text-align:center;color:var(--muted);font-size:11px;padding:7px 0}.day{min-width:0;aspect-ratio:1;border:1px solid transparent;background:#15243a;color:var(--text);border-radius:11px;cursor:pointer;font-size:13px}.day:hover:not(:disabled){border-color:#60a5fa;background:#1b3454}.day:disabled{opacity:.25;cursor:not-allowed}.day.selected{background:var(--blue);border-color:#93c5fd;color:white;font-weight:800}.day.today{box-shadow:inset 0 0 0 1px #60a5fa}.day.empty{background:transparent;cursor:default}
.selected-date{display:flex;gap:10px;align-items:center;margin:16px 0 0;padding:12px;background:#15243a;border-radius:12px;color:#dbeafe;font-size:13px}.selected-date .calico{font-size:21px}.selected-date strong{display:block}.slots{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:12px}.slot{border:1px solid #31445f;border-radius:10px;background:#142238;color:#eaf2ff;padding:11px 4px;cursor:pointer;font-weight:700;font-size:13px}.slot:hover{border-color:#60a5fa}.slot.selected{background:var(--blue2);border-color:#93c5fd}.hint{font-size:12px;color:var(--muted);margin:12px 0 0}.empty-state{padding:18px 10px;text-align:center;color:var(--muted);font-size:13px;border:1px dashed #31445f;border-radius:12px}
.field{margin-bottom:15px}.field label{display:block;font-size:12px;font-weight:750;color:#d6e4f7;margin-bottom:7px}.field input{width:100%;min-height:45px;background:#091321;border:1px solid #30415a;border-radius:11px;color:var(--text);padding:11px 12px;font:inherit;font-size:14px;outline:none}.field input:focus{border-color:#60a5fa;box-shadow:0 0 0 3px #3b82f622}
.service-list{display:grid;gap:8px;margin:12px 0 17px}.service-option{display:flex;align-items:center;gap:10px;padding:11px;border:1px solid #2c3e57;border-radius:12px;background:#0d1829;cursor:pointer}.service-option:has(input:checked){border-color:#60a5fa;background:#142a46}.service-option input{accent-color:#3b82f6}.service-name{flex:1;font-size:13px;font-weight:700}.price{font-size:13px;font-weight:800;color:#86efac;white-space:nowrap}
.summary{border:1px solid #2b4260;background:#0a1728;border-radius:13px;padding:13px;margin:16px 0}.summaryline{display:flex;justify-content:space-between;gap:12px;color:var(--muted);font-size:12px;margin:5px 0}.summaryline strong{color:var(--text);text-align:right}.summaryline.total{border-top:1px solid #2b4260;padding-top:10px;margin-top:10px;font-size:14px}.summaryline.total strong{color:#86efac;font-size:17px}
.submit{display:block;width:100%;border:0;border-radius:12px;background:linear-gradient(135deg,#3b82f6,#2563eb);color:white;padding:14px 16px;font-weight:850;font-size:14px;cursor:pointer;text-align:center;box-shadow:0 8px 24px #2563eb33}.submit:hover{filter:brightness(1.08)}.submit:disabled{opacity:.5;cursor:not-allowed}
.flash{padding:12px 14px;border-radius:12px;margin:0 0 16px;font-size:13px}.flash.error{background:#451a24;border:1px solid #9f3346;color:#fecdd3}.flash.success{background:#123324;border:1px solid #26734b;color:#bbf7d0}.success-card,.unavailable{max-width:680px;margin:20px auto;background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:26px;text-align:center}.success-mark{margin:0 auto 14px;width:58px;height:58px;border-radius:50%;display:grid;place-items:center;background:#14532d;color:#bbf7d0;font-size:28px}.success-card h2,.unavailable h2{margin:8px 0}.success-card p,.unavailable p{color:var(--muted)}.success-detail{background:#0a1728;border-radius:12px;padding:14px;text-align:left;margin:18px 0}.success-detail div{display:flex;justify-content:space-between;gap:12px;padding:7px 0;font-size:13px}.success-detail span{color:var(--muted)}.footer{text-align:center;color:#6f829d;font-size:11px;margin-top:22px}
@media(max-width:760px){.wrap{padding:18px 12px 34px}.layout{grid-template-columns:1fr}.panel{padding:16px}.slots{grid-template-columns:repeat(3,minmax(0,1fr))}.hero h2{font-size:30px}}
</style></head><body><div class="wrap">
<header class="brand"><div class="logo">F</div><div><h1>Fio&Caixa</h1><p>Gestão & Agendamento</p></div></header>
{% if unavailable %}
<section class="unavailable"><div class="success-mark">!</div><h2>Agendamento indisponível</h2><p>Este salão não está disponível para agendamentos online no momento. Confira o link ou entre em contato diretamente com o estabelecimento.</p></section>
{% elif success %}
<section class="success-card"><div class="success-mark">✓</div><div class="eyebrow">Solicitação registrada</div><h2>Obrigado, {{ success.nome|e }}!</h2><p>Seu horário foi solicitado com sucesso. O salão recebeu o registro e poderá confirmar o atendimento.</p>
<div class="success-detail"><div><span>Estabelecimento</span><strong>{{ name|e }}</strong></div><div><span>Serviço</span><strong>{{ success.servico|e }}</strong></div><div><span>Data</span><strong>{{ success.data_display }}</strong></div><div><span>Horário</span><strong>{{ success.hora }}</strong></div><div><span>Valor</span><strong>{{ success.valor_display }}</strong></div><div><span>Status</span><strong style="color:#fcd34d">Pendente de confirmação</strong></div></div>
{% if success.owner_whatsapp %}<a class="submit" style="text-decoration:none" href="{{ ('https://wa.me/' ~ success.owner_whatsapp ~ '?text=' ~ success.owner_message|urlencode) }}" target="_blank" rel="noopener">Entrar em contato pelo WhatsApp</a>{% endif %}</section>
{% else %}
<section class="hero"><div class="eyebrow">Reserve seu horário</div><h2>Seu próximo cuidado começa aqui.</h2><p>Escolha o serviço, selecione o melhor dia e horário e envie sua solicitação ao salão.</p></section>
{% with messages = get_flashed_messages(with_categories=true) %}{% for category, message in messages %}<div class="flash {{ category }}">{{ message }}</div>{% endfor %}{% endwith %}
<form method="post" id="bookingForm"><input type="hidden" name="csrf_token" value="{{ csrf_token }}"><input type="hidden" name="salao" value="{{ salao }}"><input type="hidden" name="data" id="dateInput" value="{{ form_data.get('data', today) }}"><input type="hidden" name="hora" id="timeInput" value="{{ form_data.get('hora', '') }}">
<div class="layout"><section class="panel"><h3>1. Escolha o dia</h3><p class="sub">Selecione uma data disponível no calendário.</p>
<div class="monthbar"><button type="button" class="iconbtn" id="prevMonth" aria-label="Mês anterior">‹</button><strong id="monthLabel"></strong><button type="button" class="iconbtn" id="nextMonth" aria-label="Próximo mês">›</button></div>
<div class="week"><span>SEG</span><span>TER</span><span>QUA</span><span>QUI</span><span>SEX</span><span>SÁB</span><span>DOM</span></div><div class="days" id="calendarDays"></div>
<div class="selected-date"><span class="calico">📅</span><div><strong id="selectedDateLabel">Selecione uma data</strong><span>Horários no fuso de Brasília</span></div></div>
<h3 style="margin-top:22px">2. Escolha o horário</h3><p class="sub">Os horários ocupados não aparecem na lista.</p><div id="slots" class="slots"><div class="empty-state" style="grid-column:1/-1">Selecione um dia para consultar os horários.</div></div><p class="hint">Os horários são atualizados a partir dos agendamentos registrados pelo salão.</p></section>
<section class="panel"><h3>3. Serviço e seus dados</h3><p class="sub">Confira o preço e informe como podemos identificar você.</p>
<div class="service-list">{% for service, price in services.items() %}<label class="service-option"><input type="radio" name="servico" value="{{ service }}" data-price="{{ '%.2f'|format(price) }}" {% if form_data.get('servico') == service or (not form_data.get('servico') and loop.first) %}checked{% endif %} required><span class="service-name">{{ service }}</span><span class="price">{{ ('R$ %.2f'|format(price)).replace('.', ',') }}</span></label>{% endfor %}</div>
<div class="field"><label for="nome">Seu nome completo</label><input id="nome" name="nome" type="text" maxlength="100" autocomplete="name" placeholder="Ex.: Maria Oliveira" value="{{ form_data.get('nome','') }}" required></div>
<div class="field"><label for="telefone">WhatsApp com DDD</label><input id="telefone" name="telefone" type="tel" maxlength="20" autocomplete="tel" inputmode="tel" placeholder="Ex.: (31) 99999-9999" value="{{ form_data.get('telefone','') }}" required></div>
<div class="summary"><div class="summaryline"><span>Serviço</span><strong id="summaryService">—</strong></div><div class="summaryline"><span>Data</span><strong id="summaryDate">—</strong></div><div class="summaryline"><span>Horário</span><strong id="summaryTime">Selecione um horário</strong></div><div class="summaryline total"><span>Valor do serviço</span><strong id="summaryPrice">—</strong></div></div>
<button class="submit" id="submitBtn" type="submit">Solicitar agendamento</button><p class="hint">Seu agendamento será registrado como pendente até a confirmação do salão.</p></section></div></form>
{% endif %}<div class="footer">Fio&Caixa · Agendamento online</div></div>
{% if not unavailable and not success %}<script>
(() => {
 const salon={{ salao|tojson }}, todayText={{ today|tojson }}, initialDate={{ form_data.get('data', today)|tojson }}, initialTime={{ form_data.get('hora', '')|tojson }};
 const parseDate=s=>{const p=String(s||todayText).split('-').map(Number);return new Date(p[0],(p[1]||1)-1,p[2]||1)};
 const today=parseDate(todayText), maxDate=new Date(today.getFullYear(),today.getMonth(),today.getDate()+90);
 let selectedDate=parseDate(initialDate), selectedTime=initialTime, visibleMonth=new Date(selectedDate.getFullYear(),selectedDate.getMonth(),1);
 const daysBox=document.getElementById('calendarDays'), monthLabel=document.getElementById('monthLabel'), dateInput=document.getElementById('dateInput'), timeInput=document.getElementById('timeInput'), slotsBox=document.getElementById('slots'), submitBtn=document.getElementById('submitBtn');
 const ptDate=new Intl.DateTimeFormat('pt-BR',{weekday:'long',day:'2-digit',month:'long',year:'numeric'}), money=n=>Number(n||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
 const dateKey=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
 const sameDay=(a,b)=>a.getFullYear()===b.getFullYear()&&a.getMonth()===b.getMonth()&&a.getDate()===b.getDate();
 function renderCalendar(){
  daysBox.innerHTML='';monthLabel.textContent=new Intl.DateTimeFormat('pt-BR',{month:'long',year:'numeric'}).format(visibleMonth);
  document.getElementById('prevMonth').disabled=visibleMonth.getFullYear()===today.getFullYear()&&visibleMonth.getMonth()===today.getMonth();
  document.getElementById('nextMonth').disabled=visibleMonth.getFullYear()===maxDate.getFullYear()&&visibleMonth.getMonth()===maxDate.getMonth();
  const first=new Date(visibleMonth.getFullYear(),visibleMonth.getMonth(),1), offset=(first.getDay()+6)%7;
  for(let i=0;i<offset;i++){const blank=document.createElement('div');blank.className='day empty';daysBox.appendChild(blank)}
  const count=new Date(visibleMonth.getFullYear(),visibleMonth.getMonth()+1,0).getDate();
  for(let day=1;day<=count;day++){const date=new Date(visibleMonth.getFullYear(),visibleMonth.getMonth(),day),btn=document.createElement('button');btn.type='button';btn.className='day';btn.textContent=day;
   btn.disabled=date<new Date(today.getFullYear(),today.getMonth(),today.getDate())||date>maxDate;
   if(sameDay(date,today))btn.classList.add('today');if(sameDay(date,selectedDate))btn.classList.add('selected');
   btn.setAttribute('aria-label',ptDate.format(date));btn.addEventListener('click',()=>chooseDate(date));daysBox.appendChild(btn)}
 }
 function chooseDate(date){selectedDate=new Date(date.getFullYear(),date.getMonth(),date.getDate());visibleMonth=new Date(date.getFullYear(),date.getMonth(),1);selectedTime='';timeInput.value='';dateInput.value=dateKey(selectedDate);renderCalendar();updateSummary();loadSlots()}
 async function loadSlots(){
  slotsBox.innerHTML='<div class="empty-state" style="grid-column:1/-1">Consultando horários disponíveis…</div>';
  try{const response=await fetch(`/api/booking/slots?salao=${encodeURIComponent(salon)}&date=${encodeURIComponent(dateKey(selectedDate))}`,{headers:{'Accept':'application/json'}});if(!response.ok)throw new Error('Falha ao consultar');const slots=await response.json();slotsBox.innerHTML='';
   if(!slots.length){slotsBox.innerHTML='<div class="empty-state" style="grid-column:1/-1">Não há horários livres neste dia. Escolha outra data.</div>';selectedTime='';timeInput.value='';updateSummary();return}
   slots.forEach(time=>{const btn=document.createElement('button');btn.type='button';btn.className='slot';btn.textContent=time;if(time===selectedTime)btn.classList.add('selected');btn.addEventListener('click',()=>{selectedTime=time;timeInput.value=time;slotsBox.querySelectorAll('.slot').forEach(el=>el.classList.toggle('selected',el===btn));updateSummary()});slotsBox.appendChild(btn)});
   if(selectedTime&&!slots.includes(selectedTime)){selectedTime='';timeInput.value='';updateSummary()}
  }catch(e){slotsBox.innerHTML='<div class="empty-state" style="grid-column:1/-1">Não foi possível carregar os horários. Atualize a página e tente novamente.</div>'}
 }
 function updateSummary(){const service=document.querySelector('input[name="servico"]:checked');document.getElementById('selectedDateLabel').textContent=ptDate.format(selectedDate);document.getElementById('summaryService').textContent=service?service.value:'—';document.getElementById('summaryDate').textContent=selectedDate.toLocaleDateString('pt-BR');document.getElementById('summaryTime').textContent=selectedTime||'Selecione um horário';document.getElementById('summaryPrice').textContent=service?money(service.dataset.price):'—';submitBtn.disabled=!(service&&selectedTime&&dateInput.value)}
 document.getElementById('prevMonth').addEventListener('click',()=>{if(!document.getElementById('prevMonth').disabled){visibleMonth=new Date(visibleMonth.getFullYear(),visibleMonth.getMonth()-1,1);renderCalendar()}});
 document.getElementById('nextMonth').addEventListener('click',()=>{if(!document.getElementById('nextMonth').disabled){visibleMonth=new Date(visibleMonth.getFullYear(),visibleMonth.getMonth()+1,1);renderCalendar()}});
 document.querySelectorAll('input[name="servico"]').forEach(el=>el.addEventListener('change',updateSummary));
 document.getElementById('bookingForm').addEventListener('submit',e=>{if(!dateInput.value||!timeInput.value||!document.querySelector('input[name="servico"]:checked')){e.preventDefault();alert('Selecione uma data, um horário e um serviço antes de continuar')}else{submitBtn.disabled=true;submitBtn.textContent='Enviando solicitação…'}});
 if(selectedDate<new Date(today.getFullYear(),today.getMonth(),today.getDate())||selectedDate>maxDate)selectedDate=new Date(today);
 dateInput.value=dateKey(selectedDate);renderCalendar();updateSummary();loadSlots();
})();
</script>{% endif %}</body></html>
"""


@app.route("/api/booking/slots")
def booking_slots():
    salao = request.args.get("salao", "").strip().lower() or (current_user() if require_login() and not require_admin() else "")
    date = request.args.get("date", "")
    u = users().get(salao)
    if not u or not user_valid(u):
        return jsonify([])
    try:
        day = datetime.strptime(date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return jsonify([])
    today = datetime.now(TZ).date()
    if day < today or day > today + timedelta(days=90):
        return jsonify([])
    rows = db_exec(
        """SELECT hora FROM agendamentos
           WHERE usuario_id=:u AND data=:d
             AND COALESCE(status, 'Pendente') <> 'Cancelado'""",
        {"u": salao, "d": date}, True
    )
    booked = {str(row[0])[:5] for row in rows}
    slots = [hour for hour in ALLOWED_HOURS if hour not in booked]
    if day == today:
        now_hm = datetime.now(TZ).strftime("%H:%M")
        slots = [hour for hour in slots if hour > now_hm]
    return jsonify(slots)


@app.route("/agendar", methods=["GET", "POST"])
def booking():
    salao = urllib.parse.unquote(request.args.get("salao") or request.form.get("salao") or "").strip().lower()
    today = datetime.now(TZ).date().isoformat()
    form_data = {
        "nome": str(request.form.get("nome", "")),
        "telefone": str(request.form.get("telefone", "")),
        "servico": str(request.form.get("servico", "")),
        "data": str(request.form.get("data", today)),
        "hora": str(request.form.get("hora", "")),
    }
    u = users().get(salao)
    if not u or not user_valid(u):
        return render_template_string(BOOKING_TEMPLATE, unavailable=True, salao=salao, today=today, form_data=form_data)
    services = get_services(salao)
    success = None
    if request.method == "POST":
        name = str(request.form.get("nome", "")).strip()[:100]
        phone = normalize_phone(request.form.get("telefone", ""))[:20]
        service = str(request.form.get("servico", "")).strip()
        date = str(request.form.get("data", ""))
        hour = str(request.form.get("hora", ""))
        dt = valid_date_time(date, hour)
        if len(name) < 2 or len(phone) < 8 or service not in services or not dt:
            flash("Confira seu nome, WhatsApp, serviço, data e horário.", "error")
        elif dt <= datetime.now(TZ):
            flash("Escolha um horário futuro.", "error")
        elif dt.date() > datetime.now(TZ).date() + timedelta(days=90):
            flash("Escolha uma data dentro dos próximos 90 dias.", "error")
        else:
            try:
                with engine.begin() as conn:
                    lock_key = int(hashlib.sha256(f"{salao}|{date}|{hour}".encode()).hexdigest()[:15], 16) % (2**63 - 1)
                    conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": lock_key})
                    exists = conn.execute(
                        text("""SELECT 1 FROM agendamentos
                                WHERE usuario_id=:u AND data=:d AND hora=:h
                                  AND COALESCE(status, 'Pendente') <> 'Cancelado'"""),
                        {"u": salao, "d": date, "h": hour},
                    ).fetchone()
                    if exists:
                        flash("Esse horário acabou de ser ocupado. Escolha outro.", "error")
                    else:
                        price = float(services[service])
                        saved = conn.execute(
                            text("""INSERT INTO agendamentos
                                (usuario_id,cliente_nome,cliente_contato,servico_nome,data,hora,status,valor)
                                VALUES(:u,:n,:c,:s,:d,:h,'Pendente',:v) RETURNING id"""),
                            {"u": salao, "n": name, "c": phone, "s": service, "d": date, "h": hour, "v": price},
                        ).scalar_one_or_none()
                        if not saved:
                            raise RuntimeError("O banco não retornou o ID do agendamento salvo")
                        app.logger.info("Agendamento online salvo: id=%s salao=%s data=%s hora=%s", saved, salao, date, hour)
                        date_display = datetime.strptime(date, "%Y-%m-%d").strftime("%d/%m/%Y")
                        price_display = f"R$ {price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        owner_phone = normalize_phone(u.get("whatsapp", ""))
                        owner_message = (
                            "Olá! Acabei de realizar um agendamento pelo site.\n\n"
                            f"👤 *Cliente:* {name}\n"
                            f"📅 *Data:* {date_display}\n"
                            f"⏰ *Horário:* {hour}\n"
                            f"💈 *Serviço:* {service}\n"
                            f"💵 *Valor Total:* {price_display}"
                        )
                        success = {
                            "nome": name, "servico": service, "data": date,
                            "data_display": date_display, "hora": hour, "phone": phone,
                            "salao": salao, "valor": price, "valor_display": price_display,
                            "owner_whatsapp": owner_phone, "owner_message": owner_message,
                        }
                if success and owner_phone:
                    send_whatsapp_notification(owner_phone, owner_message)
                elif success:
                    app.logger.warning("Agendamento %s salvo, mas salão %s não tem WhatsApp cadastrado", saved, salao)
            except Exception:
                app.logger.exception("Falha ao gravar agendamento online (salao=%s, data=%s, hora=%s)", salao, date, hour)
                flash("Não foi possível salvar o agendamento no banco. Nenhuma confirmação foi registrada; tente novamente.", "error")
    services = get_services(salao)
    return render_template_string(
        BOOKING_TEMPLATE, unavailable=False, salao=salao,
        name=salao.replace("_", " ").replace("-", " ").title(),
        services=services, success=success, today=today, form_data=form_data,
    )


@app.route("/backup.json")
def backup():
    if not require_login() or require_admin(): return redirect(url_for("index"))
    data = backup_json(current_user())
    return app.response_class(data, mimetype="application/json", headers={"Content-Disposition": f"attachment; filename=backup_{current_user()}_{datetime.now(TZ):%d_%m_%Y}.json"})


@app.route("/relatorio.pdf")
def report():
    if not require_login() or require_admin(): return redirect(url_for("index"))
    df = get_flow(current_user())
    if df.empty:
        flash("Não há movimentações para gerar relatório.", "error")
        return redirect(url_for("dashboard"))
    ref = request.args.get("ref", "Geral")
    buf = make_pdf(df, ref)
    return send_file(buf, as_attachment=True, download_name=f"contabilidade_{datetime.now(TZ):%Y%m%d}.pdf", mimetype="application/pdf")


@app.route("/admin", methods=["GET"])
def admin():
    if not require_admin(): return redirect(url_for("index"))
    us = users(); today = datetime.now(TZ).date()
    for uid, u in list(us.items()):
        try: venc = datetime.strptime(str(u["vencimento"]), "%Y-%m-%d").date()
        except Exception: venc = today
        if venc < today and u.get("status") == "Ativo":
            u["status"] = "Suspenso"; save_user(uid, u)
    return render_template("admin.html", users=users(), config=admin_config(), today=today)


@app.route("/admin/user", methods=["POST"])
def admin_user():
    if not require_admin(): return redirect(url_for("index"))
    action = request.form.get("action"); uid = request.form.get("id", "").strip().lower()
    if not re.fullmatch(r"[a-z0-9_-]{3,50}", uid):
        flash("Usuário inválido. Use letras, números, _ ou -.", "error")
        return redirect(url_for("admin"))
    existing = users().get(uid)
    if action == "save":
        raw = request.form.get("senha", "")
        senha = password_hash(raw) if raw else (existing.get("senha") if existing else password_hash(secrets.token_urlsafe(12)))
        venc = request.form.get("vencimento")
        if not venc:
            flash("Informe o vencimento.", "error"); return redirect(url_for("admin"))
        save_user(uid, {"senha": senha, "email": request.form.get("email", "").strip().lower(), "whatsapp": normalize_phone(request.form.get("whatsapp", "")), "tipo": request.form.get("tipo", "Cliente"), "vencimento": venc, "status": request.form.get("status", "Ativo")})
        db_exec("INSERT INTO usuario_config(usuario_id,meta_mensal) VALUES(:u,5000) ON CONFLICT DO NOTHING", {"u": uid})
        flash("Salão salvo.", "success")
    elif action == "block" and existing:
        existing["status"] = "Suspenso"; save_user(uid, existing); flash("Salão bloqueado.", "success")
    elif action == "renew" and existing:
        existing["status"] = "Ativo"; existing["vencimento"] = (datetime.now(TZ).date() + timedelta(days=30)).strftime("%Y-%m-%d"); save_user(uid, existing); flash("Salão renovado por 30 dias.", "success")
    elif action == "delete" and existing:
        # Limpa os dados dependentes para evitar registros órfãos.
        for table in ("servicos", "fluxo_caixa", "agendamentos", "clientes_mensais", "usuario_config"):
            db_exec(f"DELETE FROM {table} WHERE usuario_id=:u", {"u": uid})
        db_exec("DELETE FROM usuarios WHERE id=:id", {"id": uid})
        flash("Salão e seus dados foram excluídos.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/config", methods=["POST"])
def admin_config_route():
    if not require_admin(): return redirect(url_for("index"))
    h1, h2, _ = admin_config()
    url = request.form.get("url", app_base_url()).strip().rstrip("/")
    if not re.match(r"^https://[a-zA-Z0-9.-]+(?:/.*)?$", url):
        flash("Use uma URL HTTPS válida.", "error")
    else:
        save_admin(h1, h2, url); flash("URL do sistema atualizada.", "success")
    return redirect(url_for("admin"))


@app.errorhandler(400)
def bad_request(err):
    if request.path.startswith("/api/"):
        return jsonify({"error": getattr(err, "description", "Requisição inválida")}), 400
    return "Requisição inválida. Atualize a página e tente novamente.", 400


@app.errorhandler(404)
def not_found(err):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Não encontrado"}), 404
    return "Página não encontrada.", 404


@app.errorhandler(500)
def server_error(err):
    # O detalhe técnico fica apenas nos logs privados do Render, nunca na tela pública.
    original = getattr(err, "original_exception", None)
    if original is not None:
        app.logger.error(
            "Erro interno na rota %s (%s %s)",
            request.endpoint, request.method, request.path,
            exc_info=(type(original), original, original.__traceback__),
        )
    else:
        app.logger.exception(
            "Erro interno na rota %s (%s %s)",
            request.endpoint, request.method, request.path,
        )
    if request.path.startswith("/api/"):
        return jsonify({"error": "Erro interno. Consulte os logs privados do servidor."}), 500
    flash("Não foi possível concluir a operação. Tente novamente. Se persistir, consulte os logs do servidor.", "error")
    if request.path in {"/login", "/admin", "/"}:
        return redirect(url_for("index")), 303
    return "Ocorreu um erro interno. Consulte os logs do servidor para identificar a causa.", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

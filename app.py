import os
import re
import json
import hmac
import hashlib
import decimal
import urllib.parse
from io import BytesIO
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file, flash
from sqlalchemy import create_engine, text
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

TZ = ZoneInfo("America/Sao_Paulo")
RENDER_BASE_URL = os.getenv("RENDER_BASE_URL", "https://agendamentos-doy4.onrender.com").rstrip("/")
DB_URL = os.getenv("DB_URL", "")
SALT = os.getenv("SECURITY_SALT", "salao_fio_caixa_secure_default_2026")
SUPPORT_PHONE = os.getenv("SUPPORT_PHONE", "5537991598179")
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", os.getenv("SECRET_KEY", "troque-esta-chave-no-render"))

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "true").lower() == "true")

if not DB_URL:
    raise RuntimeError("DB_URL não configurada no ambiente do Render.")

engine = create_engine(DB_URL, pool_pre_ping=True, pool_size=5, max_overflow=10, pool_recycle=1800)


def gerar_hash(password: str) -> str:
    if not password:
        return ""
    return hmac.new(str(SALT).encode(), str(password).encode(), hashlib.sha256).hexdigest()


def hash_password(password):
    return gerar_hash(password)


def verificar_senha(digitada, armazenada):
    if not digitada or not armazenada:
        return False
    return hmac.compare_digest(str(armazenada), gerar_hash(digitada)) or hmac.compare_digest(str(armazenada), str(digitada))


def db_exec(sql, params=None, fetch=False, many=False):
    with engine.begin() as conn:
        result = conn.execute(text(sql), params or {})
        if fetch:
            return result.fetchall()
    return None


def init_db():
    statements = [
        "CREATE TABLE IF NOT EXISTS admin_config (id INT PRIMARY KEY, hash1 TEXT NOT NULL, hash2 TEXT NOT NULL, url_sistema TEXT);",
        "ALTER TABLE admin_config ADD COLUMN IF NOT EXISTS url_sistema TEXT;",
        "CREATE TABLE IF NOT EXISTS usuarios (id TEXT PRIMARY KEY, senha TEXT NOT NULL, email TEXT, tipo TEXT, vencimento TEXT, status TEXT, whatsapp TEXT);",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS whatsapp TEXT;",
        "CREATE TABLE IF NOT EXISTS servicos (id SERIAL PRIMARY KEY, usuario_id TEXT NOT NULL, nome TEXT NOT NULL, preco NUMERIC NOT NULL);",
        "CREATE TABLE IF NOT EXISTS fluxo_caixa (id SERIAL PRIMARY KEY, usuario_id TEXT NOT NULL, data TEXT NOT NULL, tipo TEXT NOT NULL, descricao TEXT NOT NULL, valor NUMERIC NOT NULL);",
        "CREATE TABLE IF NOT EXISTS agendamentos (id SERIAL PRIMARY KEY, usuario_id TEXT NOT NULL, cliente_nome TEXT NOT NULL, cliente_contato TEXT, servico_nome TEXT NOT NULL, data TEXT NOT NULL, hora TEXT NOT NULL);",
        "CREATE TABLE IF NOT EXISTS clientes_mensais (id SERIAL PRIMARY KEY, usuario_id TEXT NOT NULL, nome_cliente TEXT NOT NULL, telefone TEXT, servicos_feitos INT DEFAULT 0, valor_devido NUMERIC DEFAULT 0.0, status_divida TEXT DEFAULT 'Pendente');",
        "CREATE INDEX IF NOT EXISTS idx_fluxo_usuario_data ON fluxo_caixa(usuario_id, data);",
        "CREATE INDEX IF NOT EXISTS idx_agend_usuario_data_hora ON agendamentos(usuario_id, data, hora);",
        "CREATE INDEX IF NOT EXISTS idx_servicos_usuario ON servicos(usuario_id);",
        "CREATE INDEX IF NOT EXISTS idx_mensais_usuario ON clientes_mensais(usuario_id);",
    ]
    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))


init_db()


def admin_config():
    rows = db_exec("SELECT hash1, hash2, url_sistema FROM admin_config WHERE id=1", fetch=True)
    return tuple(rows[0]) if rows else (None, None, None)


def save_admin(h1, h2, url):
    db_exec("""INSERT INTO admin_config(id,hash1,hash2,url_sistema) VALUES(1,:h1,:h2,:url)
               ON CONFLICT(id) DO UPDATE SET hash1=EXCLUDED.hash1, hash2=EXCLUDED.hash2, url_sistema=EXCLUDED.url_sistema""", {"h1": h1, "h2": h2, "url": url})


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
    rows = db_exec("SELECT nome, preco FROM servicos WHERE usuario_id=:u ORDER BY nome", {"u": user}, True)
    if rows:
        return {r[0]: float(r[1]) for r in rows}
    return {"Corte de Cabelo": 30.0, "Barba": 30.0, "Combo Cabelo e Barba": 50.0, "Mensalidade": 100.0}


def get_flow(user):
    rows = db_exec("SELECT id,data,tipo,descricao,valor FROM fluxo_caixa WHERE usuario_id=:u ORDER BY data DESC,id DESC", {"u": user}, True)
    df = pd.DataFrame(rows, columns=["id", "Data", "Tipo", "Descrição", "Valor"])
    if df.empty:
        return df
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0).astype(float)
    return df


def get_appointments(user):
    rows = db_exec("SELECT id,cliente_nome,cliente_contato,servico_nome,data,hora FROM agendamentos WHERE usuario_id=:u ORDER BY data,hora", {"u": user}, True)
    return pd.DataFrame(rows, columns=["id", "Cliente", "Contato", "Serviço", "Data", "Horário"])


def get_monthly(user):
    rows = db_exec("SELECT id,nome_cliente,telefone,servicos_feitos,valor_devido,status_divida FROM clientes_mensais WHERE usuario_id=:u ORDER BY id DESC", {"u": user}, True)
    return pd.DataFrame(rows, columns=["id", "Cliente", "Telefone", "Serviços Feitos", "Valor Devido", "Status"])


def insert_flow(user, tipo, descricao, valor, data):
    data_str = data.strftime("%Y-%m-%d") if hasattr(data, "strftime") else str(data)
    db_exec("INSERT INTO fluxo_caixa(usuario_id,data,tipo,descricao,valor) VALUES(:u,:d,:t,:desc,:v)", {"u": user, "d": data_str, "t": tipo, "desc": descricao, "v": float(valor)})


def calc_dashboard(user):
    df = get_flow(user)
    today = datetime.now(TZ).date()
    if df.empty:
        empty = {"id": [], "Data": [], "Tipo": [], "Descrição": [], "Valor": []}
        df = pd.DataFrame(empty)
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
    def pct(a,b): return 0 if a == b == 0 else (100 if b == 0 else ((a-b)/b)*100)
    appts = get_appointments(user)
    appt_today = appts[appts.Data.astype(str) == today.strftime("%Y-%m-%d")] if not appts.empty else appts
    monthly = get_monthly(user)
    clients = set(monthly.Cliente.dropna()) if not monthly.empty else set()
    clients.update(appts.Cliente.dropna() if not appts.empty else [])
    return {
        "receita_dia": receita_dia, "receita_mes": receita_mes, "receita_ano": receita_ano, "lucro": lucro,
        "pct_receita": pct(receita_mes, receita_prev), "pct_lucro": pct(lucro, lucro_prev),
        "ticket": entradas / len(cur[cur.Tipo == "Entrada"]) if not cur.empty and len(cur[cur.Tipo == "Entrada"]) else 0,
        "clientes": len(clients), "agendamentos_hoje": len(appt_today), "today": today.strftime("%d/%m"),
        "mes_passado": receita_prev,
    }


def backup_json(user):
    df = get_flow(user)
    fluxo = []
    if not df.empty:
        cp = df.copy(); cp["Data"] = cp["Data"].dt.strftime("%Y-%m-%d"); fluxo = cp.to_dict("records")
    def ser(o):
        if isinstance(o, (decimal.Decimal, float)): return float(o)
        if isinstance(o, (datetime, pd.Timestamp)): return o.strftime("%Y-%m-%d")
        return str(o)
    return json.dumps({"sistema":"Fio&Caixa","usuario_dono":user,"data_geracao":datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S"),"catalogo_servicos":get_services(user),"historico_financeiro":fluxo}, ensure_ascii=False, indent=2, default=ser)


def make_pdf(df, ref):
    buf = BytesIO(); doc = SimpleDocTemplate(buf, pagesize=letter, rightMargin=30,leftMargin=30,topMargin=30,bottomMargin=30)
    styles=getSampleStyleSheet(); title=ParagraphStyle("DocTitle",parent=styles["Heading1"],fontSize=16,textColor=colors.HexColor("#38bdf8"),spaceAfter=15)
    story=[Paragraph(f"Fio&Caixa - Relatório Contábil ({ref})", title)]
    data=[["Data","Tipo","Descrição","Valor"]]
    for _,r in df.iterrows():
        data.append([r["Data"].strftime("%d/%m/%Y"),str(r["Tipo"]),str(r["Descrição"]),f"R$ {float(r['Valor']):,.2f}"])
    t=Table(data,colWidths=[70,70,300,90]); t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#0f172a")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.25,colors.grey),("FONTSIZE",(0,0),(-1,-1),8),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.append(t); doc.build(story); buf.seek(0); return buf


@app.context_processor
def inject_globals():
    return {"logged_user": current_user(), "is_admin": require_admin(), "now": datetime.now(TZ), "base_url": RENDER_BASE_URL}


@app.route("/", methods=["GET"])
def index():
    salao = request.args.get("salao")
    if salao and not require_login():
        return redirect(url_for("booking", salao=salao))
    if not require_login():
        h1,h2,url=admin_config()
        return render_template("login.html", initialized=bool(h1 and h2), support_phone=SUPPORT_PHONE)
    if require_admin():
        return redirect(url_for("admin"))
    return redirect(url_for("dashboard"))


@app.route("/setup", methods=["GET","POST"])
def setup():
    if admin_config()[0]: return redirect(url_for("index"))
    if request.method == "POST":
        p1=request.form.get("senha1",""); p2=request.form.get("senha2",""); base=request.form.get("url",RENDER_BASE_URL).strip().rstrip("/")
        if p1 and p2:
            save_admin(hash_password(p1),hash_password(p2),base); flash("Administração inicializada.","success"); return redirect(url_for("index"))
        flash("Informe as duas senhas.","error")
    return render_template("setup.html")


@app.route("/login", methods=["POST"])
def login():
    mode=request.form.get("tipo","salao"); user=request.form.get("usuario","").strip().lower(); password=request.form.get("senha","")
    h1,h2,_=admin_config()
    if mode=="admin":
        if user=="admin" and verificar_senha(password,h1) and verificar_senha(request.form.get("senha2",""),h2):
            session.clear(); session.update(usuario_logado="Administrador",eh_admin=True); return redirect(url_for("admin"))
        flash("Credenciais de administrador inválidas.","error"); return redirect(url_for("index"))
    u=users().get(user)
    if not u or not verificar_senha(password,u["senha"]):
        flash("Usuário ou senha incorretos.","error"); return redirect(url_for("index"))
    if not user_valid(u):
        flash("Acesso bloqueado ou licença expirada.","error"); return redirect(url_for("index"))
    session.clear(); session.update(usuario_logado=user,eh_admin=False); return redirect(url_for("dashboard"))


@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    if not require_login() or require_admin(): return redirect(url_for("index"))
    user=current_user(); d=calc_dashboard(user); appts=get_appointments(user)
    return render_template("dashboard.html", user=user, name=user.replace("_"," ").replace("-"," ").title(), services=get_services(user), dash=d, appointments=appts.to_dict("records"), monthly=get_monthly(user).to_dict("records"), flow=get_flow(user).to_dict("records"))


@app.route("/api/dashboard")
def api_dashboard():
    if not require_login() or require_admin(): return jsonify({"error":"unauthorized"}),401
    return jsonify(calc_dashboard(current_user()))


@app.route("/api/services", methods=["POST","DELETE"])
def api_services():
    if not require_login() or require_admin(): return jsonify({"error":"unauthorized"}),401
    user=current_user()
    if request.method=="POST":
        data=request.get_json() or {}; name=str(data.get("name","")).strip(); price=float(data.get("price",0) or 0); old=str(data.get("old","")).strip()
        if not name: return jsonify({"error":"Nome obrigatório"}),400
        if old and old != "__new__": db_exec("UPDATE servicos SET nome=:n,preco=:p WHERE usuario_id=:u AND nome=:o",{"n":name,"p":price,"u":user,"o":old})
        else: db_exec("INSERT INTO servicos(usuario_id,nome,preco) VALUES(:u,:n,:p)",{"u":user,"n":name,"p":price})
    else:
        name=request.args.get("name",""); db_exec("DELETE FROM servicos WHERE usuario_id=:u AND nome=:n",{"u":user,"n":name})
    return jsonify({"ok":True,"services":get_services(user)})


@app.route("/api/flow", methods=["POST","DELETE"])
def api_flow():
    if not require_login() or require_admin(): return jsonify({"error":"unauthorized"}),401
    user=current_user()
    if request.method=="POST":
        d=request.get_json() or {}; insert_flow(user,d.get("tipo"),d.get("descricao"),float(d.get("valor",0)),d.get("data") or datetime.now(TZ).date())
    else:
        rid=request.args.get("id"); db_exec("DELETE FROM fluxo_caixa WHERE id=:id AND usuario_id=:u",{"id":int(rid),"u":user})
    return jsonify({"ok":True})


@app.route("/api/flow/<int:rid>/pay", methods=["POST"])
def pay_credit(rid):
    if not require_login() or require_admin(): return jsonify({"error":"unauthorized"}),401
    user=current_user(); row=db_exec("SELECT descricao FROM fluxo_caixa WHERE id=:id AND usuario_id=:u AND tipo='Pendência'",{"id":rid,"u":user},True)
    if not row: return jsonify({"error":"Fiado não encontrado"}),404
    db_exec("UPDATE fluxo_caixa SET tipo='Entrada',data=:d,descricao=:desc WHERE id=:id AND usuario_id=:u",{"d":datetime.now(TZ).strftime('%Y-%m-%d'),"desc":str(row[0][0]).replace('Fiado de:','Recebido Fiado:')+' [PAGO]',"id":rid,"u":user})
    return jsonify({"ok":True})


@app.route("/api/monthly", methods=["POST"])
def api_monthly():
    if not require_login() or require_admin(): return jsonify({"error":"unauthorized"}),401
    user=current_user(); d=request.get_json() or {}; action=d.get("action")
    if action=="create": db_exec("INSERT INTO clientes_mensais(usuario_id,nome_cliente,telefone) VALUES(:u,:n,:t)",{"u":user,"n":str(d.get('name','')).strip(),"t":str(d.get('phone','')).strip()})
    elif action=="service":
        rid=int(d["id"]); qty=int(d.get("qty",1)); price=float(d.get("price",0)); db_exec("UPDATE clientes_mensais SET servicos_feitos=servicos_feitos+:q,valor_devido=valor_devido+:v,status_divida='Pendente' WHERE id=:id AND usuario_id=:u",{"q":qty,"v":qty*price,"id":rid,"u":user})
    elif action=="pay":
        rid=int(d["id"]); value=float(d["value"]); row=db_exec("SELECT valor_devido,nome_cliente FROM clientes_mensais WHERE id=:id AND usuario_id=:u",{"id":rid,"u":user},True)
        if row:
            new=max(0,float(row[0][0])-value); status="Quitado" if new==0 else "Pendente"; db_exec("UPDATE clientes_mensais SET valor_devido=:v,status_divida=:s WHERE id=:id AND usuario_id=:u",{"v":new,"s":status,"id":rid,"u":user}); insert_flow(user,"Entrada",f"Mensalidade recebida: {row[0][1]}",value,datetime.now(TZ).date())
    return jsonify({"ok":True})


@app.route("/api/appointments/<int:aid>", methods=["DELETE","POST"])
def appointment_action(aid):
    if not require_login() or require_admin(): return jsonify({"error":"unauthorized"}),401
    user=current_user(); row=db_exec("SELECT cliente_nome,servico_nome FROM agendamentos WHERE id=:id AND usuario_id=:u",{"id":aid,"u":user},True)
    if not row: return jsonify({"error":"Agendamento não encontrado"}),404
    if request.method=="POST":
        service=row[0][1]; price=get_services(user).get(service,0); insert_flow(user,"Entrada",f"Agendamento: {row[0][0]} ({service})",price,datetime.now(TZ).date())
    db_exec("DELETE FROM agendamentos WHERE id=:id AND usuario_id=:u",{"id":aid,"u":user})
    return jsonify({"ok":True})


@app.route("/api/booking/slots")
def booking_slots():
    salao=request.args.get("salao","").strip().lower(); date=request.args.get("date","")
    booked={r[0] for r in db_exec("SELECT hora FROM agendamentos WHERE usuario_id=:u AND data=:d",{"u":salao,"d":date},True)}
    hours=[f"{h:02d}:{m:02d}" for h in range(8,21) for m in (0,30)]
    return jsonify([h for h in hours if h not in booked])


@app.route("/agendar", methods=["GET","POST"])
def booking():
    salao=request.args.get("salao") or request.form.get("salao") or ""
    salao=urllib.parse.unquote(salao).strip().lower(); u=users().get(salao)
    if not u or not user_valid(u): return render_template("booking.html", unavailable=True, salao=salao)
    services=get_services(salao); success=None
    if request.method=="POST":
        name=request.form.get("nome","").strip(); phone=request.form.get("telefone","").strip(); service=request.form.get("servico",""); date=request.form.get("data",""); hour=request.form.get("hora","")
        if not name or not phone or service not in services or not date or not hour: flash("Preencha todos os campos.","error")
        else:
            try:
                selected_dt=datetime.strptime(f"{date} {hour}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
                if selected_dt <= datetime.now(TZ):
                    flash("Escolha um horário futuro.","error")
                    return render_template("booking.html", unavailable=False, salao=salao, name=salao.replace("_"," ").title(), services=services, success=None, today=datetime.now(TZ).date().isoformat())
            except ValueError:
                flash("Data ou horário inválido.","error")
                return render_template("booking.html", unavailable=False, salao=salao, name=salao.replace("_"," ").title(), services=services, success=None, today=datetime.now(TZ).date().isoformat())
            exists=db_exec("SELECT 1 FROM agendamentos WHERE usuario_id=:u AND data=:d AND hora=:h",{"u":salao,"d":date,"h":hour},True)
            if exists: flash("Esse horário acabou de ser ocupado. Escolha outro.","error")
            else:
                try:
                    db_exec("INSERT INTO agendamentos(usuario_id,cliente_nome,cliente_contato,servico_nome,data,hora) VALUES(:u,:n,:c,:s,:d,:h)",{"u":salao,"n":name,"c":phone,"s":service,"d":date,"h":hour})
                    success={"nome":name,"servico":service,"data":date,"hora":hour}
                except Exception:
                    flash("Esse horário acabou de ser ocupado. Escolha outro.","error")
    return render_template("booking.html", unavailable=False, salao=salao, name=salao.replace("_"," ").title(), services=services, success=success, today=datetime.now(TZ).date().isoformat())


@app.route("/backup.json")
def backup():
    if not require_login() or require_admin(): return redirect(url_for("index"))
    data=backup_json(current_user()); return app.response_class(data,mimetype="application/json",headers={"Content-Disposition":f"attachment; filename=backup_{current_user()}_{datetime.now(TZ):%d_%m_%Y}.json"})


@app.route("/relatorio.pdf")
def report():
    if not require_login() or require_admin(): return redirect(url_for("index"))
    df=get_flow(current_user())
    if df.empty: flash("Não há movimentações para gerar relatório.","error"); return redirect(url_for("dashboard"))
    ref=request.args.get("ref","Geral"); buf=make_pdf(df,ref); return send_file(buf,as_attachment=True,download_name=f"contabilidade_{datetime.now(TZ):%Y%m%d}.pdf",mimetype="application/pdf")


@app.route("/admin", methods=["GET","POST"])
def admin():
    if not require_admin(): return redirect(url_for("index"))
    us=users(); today=datetime.now(TZ).date()
    # bloqueio automático de vencidos
    for uid,u in list(us.items()):
        try: venc=datetime.strptime(str(u["vencimento"]),"%Y-%m-%d").date()
        except Exception: venc=today
        if venc < today and u.get("status")=="Ativo":
            u["status"]="Suspenso"; save_user(uid,u)
    us=users()
    return render_template("admin.html", users=us, config=admin_config(), today=today)


@app.route("/admin/user", methods=["POST"])
def admin_user():
    if not require_admin(): return redirect(url_for("index"))
    action=request.form.get("action"); uid=request.form.get("id","").strip().lower()
    if action=="save":
        existing=users().get(uid,{}); senha=request.form.get("senha") or existing.get("senha") or hash_password("123456")
        if not str(senha).startswith("pbkdf2") and len(str(senha))<60: senha=hash_password(senha)
        save_user(uid,{"senha":senha,"email":request.form.get("email","").strip().lower(),"whatsapp":request.form.get("whatsapp",""),"tipo":request.form.get("tipo","Cliente"),"vencimento":request.form.get("vencimento"),"status":request.form.get("status","Ativo")})
    elif action=="block":
        u=users().get(uid); u["status"]="Suspenso"; save_user(uid,u)
    elif action=="renew":
        u=users().get(uid); u["status"]="Ativo"; u["vencimento"]=(today:=datetime.now(TZ).date()+timedelta(days=30)).strftime("%Y-%m-%d"); save_user(uid,u)
    elif action=="delete": db_exec("DELETE FROM usuarios WHERE id=:id",{"id":uid})
    return redirect(url_for("admin"))


@app.route("/admin/config", methods=["POST"])
def admin_config_route():
    if not require_admin(): return redirect(url_for("index"))
    h1,h2,_=admin_config(); save_admin(h1,h2,request.form.get("url",RENDER_BASE_URL).strip().rstrip("/")); return redirect(url_for("admin"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",5000)))

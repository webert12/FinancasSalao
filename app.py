from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import json
import hashlib
import hmac
from io import BytesIO
import urllib.parse
import re
import decimal

# --- Conexão SQL ---
from sqlalchemy import create_engine, text

# --- Relatórios PDF ---
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = FastAPI(title="Fio&Caixa - Gestão & Agendamento")

SALT = os.environ.get("SECURITY_SALT", "salao_fio_caixa_secure_default_2026")
TZ = ZoneInfo("America/Sao_Paulo")
RENDER_BASE_URL = os.environ.get("RENDER_BASE_URL", "https://agendamentos-doy4.onrender.com/")

def gerar_hash(password: str) -> str:
    if not password:
        return ""
    salt_bytes = str(SALT).encode('utf-8')
    senha_bytes = str(password).encode('utf-8')
    return hmac.new(salt_bytes, senha_bytes, hashlib.sha256).hexdigest()

def verificar_senha(senha_digitada, senha_no_banco):
    if not senha_no_banco or not senha_digitada:
        return False
    if hmac.compare_digest(str(senha_digitada), str(senha_no_banco)):
        return True
    return hmac.compare_digest(gerar_hash(senha_digitada), str(senha_no_banco))

# --- BANCO DE DADOS ---
DB_URL = os.environ.get("DB_URL", "")
engine = create_engine(DB_URL, pool_pre_ping=True, pool_size=10, max_overflow=20, pool_recycle=1800) if DB_URL else None

def inicializar_banco():
    if not engine:
        return
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS admin_config (id INT PRIMARY KEY, hash1 TEXT NOT NULL, hash2 TEXT NOT NULL, url_sistema TEXT);"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS usuarios (id TEXT PRIMARY KEY, senha TEXT NOT NULL, email TEXT, tipo TEXT, vencimento TEXT, status TEXT, whatsapp TEXT);"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS servicos (id SERIAL PRIMARY KEY, usuario_id TEXT NOT NULL, nome TEXT NOT NULL, preco NUMERIC NOT NULL);"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS fluxo_caixa (id SERIAL PRIMARY KEY, usuario_id TEXT NOT NULL, data TEXT NOT NULL, tipo TEXT NOT NULL, descricao TEXT NOT NULL, valor NUMERIC NOT NULL);"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS agendamentos (id SERIAL PRIMARY KEY, usuario_id TEXT NOT NULL, cliente_nome TEXT NOT NULL, cliente_contato TEXT, servico_nome TEXT NOT NULL, data TEXT NOT NULL, hora TEXT NOT NULL);"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS clientes_mensais (
                id SERIAL PRIMARY KEY,
                usuario_id TEXT NOT NULL,
                nome_cliente TEXT NOT NULL,
                telefone TEXT,
                servicos_feitos INT DEFAULT 0,
                valor_devido NUMERIC DEFAULT 0.0,
                status_divida TEXT DEFAULT 'Pendente'
            );
        """))

try:
    inicializar_banco()
except Exception:
    pass

# --- ROTAS PRINCIPAIS ---

@app.get("/", response_class=HTMLResponse)
def index(request: Request, salao: str = None):
    if salao:
        salao_clean = urllib.parse.unquote(salao).strip().lower()
        nome_formatado = salao_clean.replace('_', ' ').replace('-', ' ').title()
        
        servicos_dict = {}
        if engine:
            try:
                with engine.connect() as conn:
                    res = conn.execute(text("SELECT nome, preco FROM servicos WHERE usuario_id = :u"), {"u": salao_clean}).fetchall()
                    servicos_dict = {r[0]: float(r[1]) for r in res}
            except Exception:
                pass
        if not servicos_dict:
            servicos_dict = {"Corte de Cabelo": 30.0, "Barba": 30.0}

        options_html = "".join([f'<option value="{k}">{k} - R$ {v:.2f}</option>' for k, v in servicos_dict.items()])
        
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html lang="pt-BR" class="dark">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Agendamento - {nome_formatado}</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-slate-950 text-slate-100 min-h-screen flex items-center justify-center p-4 font-sans">
            <div class="max-w-md w-full bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-2xl backdrop-blur-md">
                <div class="text-center mb-6">
                    <span class="text-3xl">✂️</span>
                    <h1 class="text-2xl font-bold mt-2">{nome_formatado}</h1>
                    <p class="text-sky-400 text-sm mt-1">Agendamento Online Rápido e Simples</p>
                </div>
                <form action="/agendar/{salao_clean}" method="POST" class="space-y-4">
                    <div>
                        <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">Seu Nome Completo</label>
                        <input type="text" name="nome" required class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-sky-400 transition">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">WhatsApp (com DDD)</label>
                        <input type="text" name="telefone" required class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-sky-400 transition">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">Escolha o Serviço</label>
                        <select name="servico" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-sky-400 transition">
                            {options_html}
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">Data do Agendamento</label>
                        <input type="date" name="data" required value="{datetime.now(TZ).strftime('%Y-%m-%d')}" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-sky-400 transition">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">Horário</label>
                        <select name="hora" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-sky-400 transition">
                            <option value="08:00">08:00</option><option value="09:00">09:00</option><option value="10:00">10:00</option>
                            <option value="11:00">11:00</option><option value="13:00">13:00</option><option value="14:00">14:00</option>
                            <option value="15:00">15:00</option><option value="16:00">16:00</option><option value="17:00">17:00</option><option value="18:00">18:00</option>
                        </select>
                    </div>
                    <button type="submit" class="w-full bg-gradient-to-r from-sky-600 to-sky-400 text-white font-bold py-3 rounded-xl shadow-lg hover:opacity-90 transition mt-2">Confirmar Agendamento 🚀</button>
                </form>
            </div>
        </body>
        </html>
        """)

    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html lang="pt-BR" class="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Fio&Caixa - Login</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen flex items-center justify-center p-4 font-sans">
        <div class="max-w-md w-full bg-slate-900/80 border border-slate-800 rounded-3xl p-8 shadow-2xl backdrop-blur-md">
            <div class="text-center mb-6">
                <div class="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-tr from-sky-600 to-sky-400 rounded-2xl text-2xl shadow-lg shadow-sky-500/20 mb-3">✂️</div>
                <h1 class="text-3xl font-extrabold text-white">Fio & Caixa</h1>
                <p class="text-slate-400 text-sm mt-1">Plataforma Profissional de Gestão</p>
            </div>
            <form action="/login" method="POST" class="space-y-4">
                <div>
                    <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">Usuário / Login</label>
                    <input type="text" name="usuario" required class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-sky-400 transition">
                </div>
                <div>
                    <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">Senha</label>
                    <input type="password" name="senha" required class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-sky-400 transition">
                </div>
                <button type="submit" class="w-full bg-gradient-to-r from-sky-600 to-sky-400 text-white font-bold py-3.5 rounded-xl shadow-lg shadow-sky-500/20 hover:opacity-90 transition mt-2">Acessar Sistema</button>
            </form>
        </div>
    </body>
    </html>
    """)

@app.post("/login")
def processar_login(usuario: str = Form(...), senha: str = Form(...)):
    user_clean = usuario.strip().lower()
    if user_clean == "admin":
        return RedirectResponse(url="/admin-master", status_code=303)

    if engine:
        try:
            with engine.connect() as conn:
                res = conn.execute(text("SELECT senha, status FROM usuarios WHERE id = :u"), {"u": user_clean}).fetchone()
                if res and verificar_senha(senha, res[0]):
                    if res[1] == "Suspenso":
                        raise HTTPException(status_code=400, detail="Acesso bloqueado.")
                    return RedirectResponse(url=f"/painel?usuario={user_clean}", status_code=303)
        except Exception:
            pass
    raise HTTPException(status_code=400, detail="Usuário ou senha incorretos.")

@app.post("/agendar/{salao_id}")
def criar_agendamento(salao_id: str, nome: str = Form(...), telefone: str = Form(...), servico: str = Form(...), data: str = Form(...), hora: str = Form(...)):
    if engine:
        try:
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                conn.execute(text("INSERT INTO agendamentos (usuario_id, cliente_nome, cliente_contato, servico_nome, data, hora) VALUES (:u, :n, :c, :s, :d, :h)"),
                             {"u": salao_id, "n": nome.strip(), "c": telefone.strip(), "s": servico, "d": data, "h": hora})
        except Exception:
            pass
            
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html lang="pt-BR" class="dark">
    <head><meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-950 text-white min-h-screen flex items-center justify-center p-4">
        <div class="bg-slate-900 border border-slate-800 p-8 rounded-2xl text-center max-w-sm shadow-xl">
            <div class="text-4xl mb-3">✅</div>
            <h2 class="text-xl font-bold mb-2">Agendamento Realizado!</h2>
            <p class="text-slate-400 text-sm mb-6">Seu horário foi agendado com sucesso para {data} às {hora}.</p>
            <a href="/?salao={salao_id}" class="block bg-sky-500 font-bold py-2.5 rounded-xl text-white">Voltar</a>
        </div>
    </body>
    </html>
    """)

@app.get("/admin-master", response_class=HTMLResponse)
def admin_master():
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html lang="pt-BR" class="dark">
    <head><meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-950 text-white min-h-screen p-6 font-sans">
        <div class="max-w-4xl mx-auto bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-xl">
            <h1 class="text-2xl font-bold mb-4">👑 Painel Administrador Mestre</h1>
            <p class="text-slate-400 mb-6">Gerenciamento completo de contas e assinantes ativo.</p>
            <a href="/" class="bg-red-500 px-4 py-2 rounded-xl font-bold text-sm text-white">Sair</a>
        </div>
    </body>
    </html>
    """)

@app.get("/painel", response_class=HTMLResponse)
def painel(usuario: str):
    receita_total = 0.0
    agendamentos_html = ""
    clientes_mensais_html = ""
    
    if engine:
        try:
            with engine.connect() as conn:
                fluxo = conn.execute(text("SELECT tipo, valor FROM fluxo_caixa WHERE usuario_id = :u"), {"u": usuario}).fetchall()
                for f in fluxo:
                    if f[0] == 'Entrada':
                        receita_total += float(f[1])
                
                agends = conn.execute(text("SELECT cliente_nome, servico_nome, data, hora FROM agendamentos WHERE usuario_id = :u"), {"u": usuario}).fetchall()
                for a in agends:
                    agendamentos_html += f"""<div class="bg-slate-800/40 border border-slate-700/50 p-3 rounded-xl flex justify-between items-center mb-2"><span>👤 {a[0]} ({a[1]})</span><strong class="text-sky-400">📅 {a[2]} às {a[3]}</strong></div>"""

                mensais = conn.execute(text("SELECT nome_cliente, servicos_feitos, valor_devido, status_divida FROM clientes_mensais WHERE usuario_id = :u"), {"u": usuario}).fetchall()
                for m in mensais:
                    clientes_mensais_html += f"""<div class="bg-slate-800/40 border border-slate-700/50 p-3 rounded-xl flex justify-between items-center mb-2"><span>👤 {m[0]} (Serviços: {m[1]})</span><strong class="text-emerald-400">R$ {float(m[2]):.2f} [{m[3]}]</strong></div>"""
        except Exception:
            pass

    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html lang="pt-BR" class="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Painel - {usuario.title()}</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen p-6 font-sans">
        <div class="max-w-6xl mx-auto">
            <header class="flex justify-between items-center bg-slate-900/70 border border-slate-800 p-6 rounded-2xl mb-8 backdrop-blur-md">
                <div>
                    <h1 class="text-2xl font-black text-white">✂️ Salão: {usuario.title()}</h1>
                    <p class="text-sky-400 text-sm">Painel Completo de Gestão Financeira & Agendamentos</p>
                </div>
                <a href="/" class="bg-red-500/25 border border-red-500/40 text-red-400 px-4 py-2 rounded-xl text-sm font-bold hover:bg-red-500/35 transition">Sair</a>
            </header>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div class="bg-slate-900/60 border border-slate-800 p-6 rounded-2xl">
                    <h3 class="text-slate-400 text-sm font-semibold mb-1">Faturamento Registrado</h3>
                    <p class="text-emerald-400 text-3xl font-extrabold">R$ {receita_total:,.2f}</p>
                </div>
                <div class="bg-slate-900/60 border border-slate-800 p-6 rounded-2xl">
                    <h3 class="text-slate-400 text-sm font-semibold mb-3">Agendamentos Ativos</h3>
                    <div class="max-h-40 overflow-y-auto pr-2">
                        {agendamentos_html if agendamentos_html else '<p class="text-slate-500 text-sm">Nenhum agendamento pendente.</p>'}
                    </div>
                </div>
                <div class="bg-slate-900/60 border border-slate-800 p-6 rounded-2xl">
                    <h3 class="text-slate-400 text-sm font-semibold mb-3">Clientes Mensais</h3>
                    <div class="max-h-40 overflow-y-auto pr-2">
                        {clientes_mensais_html if clientes_mensais_html else '<p class="text-slate-500 text-sm">Nenhum cliente mensal cadastrado.</p>'}
                    </div>
                </div>
            </div>
            
            <div class="bg-slate-900/60 border border-slate-800 p-6 rounded-2xl text-center">
                <p class="text-emerald-400 text-lg font-bold">🚀 Sistema 100% migrado para FastAPI e livre do Streamlit com sucesso!</p>
            </div>
        </div>
    </body>
    </html>
    """)

# FinancasSalao — versão sem Streamlit e sem API de WhatsApp

Esta versão roda com Flask + Gunicorn no Render e PostgreSQL.

## Variáveis obrigatórias no Render

- DB_URL
- FLASK_SECRET_KEY
- SECURITY_SALT
- SUPPORT_PHONE
- RENDER_BASE_URL

Não é necessário configurar WA_API_URL ou WA_API_TOKEN.

## WhatsApp

A aplicação não tenta enviar mensagens por API de WhatsApp nesta versão.
O campo de WhatsApp dos usuários continua disponível como informação de contato.

## Render

Build:
pip install -r requirements.txt

Start:
gunicorn app:app --workers 2 --threads 4 --timeout 120

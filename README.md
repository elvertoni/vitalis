# Vitalis

Plataforma web de controle de vida pessoal: **Saúde**, **Treino** e **Nutrição** num só
lugar, com lembretes automáticos e isolamento total de dados por usuário.

Especificação completa em [`PRD-vitalis.md`](PRD-vitalis.md). Convenções de execução em
[`PROMPT-EXEC-vitalis.xml`](PROMPT-EXEC-vitalis.xml). Decisões técnicas tomadas ao longo do
desenvolvimento em [`DECISIONS.md`](DECISIONS.md). Guia de arquitetura para quem for mexer no
código: [`CLAUDE.md`](CLAUDE.md).

## Stack

Python 3.12+ · Django 6.0 · SQLite · Templates Django + Tailwind (design system Soluna) ·
autenticação nativa com login por e-mail.

## Rodar localmente

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py createsuperuser
.\.venv\Scripts\python manage.py runserver
```

`http://127.0.0.1:8000/`

Sem Docker, sem suíte de testes automatizados — decisão explícita do projeto (ver
`PROMPT-EXEC-vitalis.xml`, diretiva D10).

## Estado

| Sprint | Área | Status |
|---|---|---|
| S1 | Fundação (`config`, `accounts`, `core`) | ✅ |
| S2 | Saúde (`saude`) | ✅ |
| S3 | Treino (`treino`) | ✅ |
| S4 | Nutrição (`nutricao`) | ✅ |
| S5 | Lembretes (`lembretes`) + Dashboard consolidado | ✅ |
| S6 | SaaS (`billing`) | ✅ |

## Assinatura em desenvolvimento

Sem conta de vendedor Mercado Pago configurada, o checkout de verdade não roda. Pra testar o
fluxo de assinatura sem cobrança real, use o botão `[Teste]` que aparece em `/assinatura/`
quando `DJANGO_DEBUG=1` — nunca disponível com `DJANGO_DEBUG=0`. Pra ligar o gateway de
verdade, defina a variável de ambiente antes de rodar (não é lida de arquivo `.env` — este
projeto não tem loader de dotenv, `config/settings.py` só lê `os.environ` puro):

```powershell
$env:MERCADOPAGO_ACCESS_TOKEN = "seu-access-token"
```

## Lembretes em desenvolvimento

Sem cron rodando localmente, a central (`/lembretes/`) e o dashboard já resincronizam os
lembretes derivados a cada visita — não precisa do comando pra ver a lista atualizada. O
comando existe pra efetivamente **enviar** (e-mail, via `EMAIL_BACKEND` de console em dev):

```powershell
.\.venv\Scripts\python manage.py send_due_reminders
```

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Documentos que mandam neste repositório

| Arquivo | Papel |
|---|---|
| `PRD-vitalis.md` | **O QUE** construir. Fonte de verdade de escopo, models e telas. |
| `PROMPT-EXEC-vitalis.xml` | **COMO** executar. Diretivas absolutas, ordem das sprints, definition of done. |
| `design_system/design-system.html` | A referência visual. Nenhum estilo fora dela. |
| `DECISIONS.md` | Decisões tomadas sob o `ambiguity_protocol`. Toda decisão ambígua entra aqui. |
| `AGENTS.md` | Mesmas regras num resumo curto para outros agentes. Mantenha os dois em sincronia ao mudar convenção. |

Conflito de **escopo** → o PRD vence. Conflito de **convenção de código** → o XML vence.

## Comandos

```powershell
.\.venv\Scripts\python.exe manage.py runserver
.\.venv\Scripts\python.exe manage.py makemigrations
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py check          # validação de config — o mais perto de "lint" que existe
.\.venv\Scripts\python.exe manage.py send_due_reminders  # sincroniza e envia lembretes vencidos
.\.venv\Scripts\python.exe manage.py seed_medico --email <e-mail> --source <dossiê.json>  # importa um histórico de saúde (ver D-041)
```

Sem suíte de testes (diretiva D10). **Docker só existe para o deploy** (`Dockerfile`,
`entrypoint.sh`) — o desenvolvimento não usa: nada de Docker no fluxo local. Verificação de
mudança: `manage.py check`, inspecionar a migration gerada antes de aplicar, e smoke test no
navegador (criar/editar/apagar, erro de validação, acesso cruzado entre usuários devolvendo
404).

Banco em dev: SQLite em `db.sqlite3`. E-mail sai no console em desenvolvimento; o link de
recuperação de senha aparece no terminal do `runserver`.

### Stack e assets

Python 3.12+ · Django 6.0. Dependências extras (`gunicorn`, `psycopg`, `whitenoise`,
`dj-database-url`) são **só de produção** — o dev roda com Django + SQLite. **Tailwind vem
do CDN** (`cdn.tailwindcss.com` em `templates/base.html`), config inline no `<script>` daquele
head — **não há npm, nem build de CSS, nem `tailwind.config.js` em arquivo**. `static/` só tem
o favicon. Lucide também via CDN. Fonte Inter via Google Fonts.

### Produção (EasyPanel) — ver `DECISIONS.md` D-040

`Dockerfile` builda com `python:3.12-slim`, roda `collectstatic` no build, e o
`entrypoint.sh` aplica `migrate` e sobe `gunicorn config.wsgi`. WhiteNoise serve o estático
(sem nginx na frente). Postgres entra via `DATABASE_URL` — **é o único switch**: sem essa
env, `config/settings.py` cai no SQLite de sempre. Anexos de exame vivem num volume montado
em `/app/media` (dado sensível, LGPD — não pode sumir num redeploy). App publicado em
`work/vitalis` no EasyPanel; domínio `vitalis.tonicoimbra.com`.

### Configuração — só `os.environ`, sem loader de `.env`

O código lê variáveis de ambiente puras via `os.environ.get` (nenhum `python-dotenv`). Defina
no shell antes do `runserver`:

| Variável | Lida em | Default | Efeito |
|---|---|---|---|
| `DJANGO_DEBUG` | `config/settings.py` | `1` | `0` liga `SECURE_SSL_REDIRECT`, HSTS, cookies seguros, `SECURE_PROXY_SSL_HEADER`. Também esconde `/assinatura/ativar-teste/`. |
| `DJANGO_SECRET_KEY` | `config/settings.py` | chave insegura embutida | trocar em produção |
| `DJANGO_ALLOWED_HOSTS` | `config/settings.py` | `localhost,127.0.0.1` | lista separada por vírgula |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `config/settings.py` | vazio | csv de origens `https://…` — obrigatório pro POST de login/admin em produção |
| `DATABASE_URL` | `config/settings.py` | ausente (→ SQLite) | presente → Postgres via `dj-database-url`. É o único switch dev↔prod de banco. |
| `EMAIL_HOST` (+ `_USER`/`_PASSWORD`, `EMAIL_PORT`, `EMAIL_USE_TLS`) | `config/settings.py` | ausente (→ console) | presente → SMTP real; sem isso, e-mail de lembrete só loga |
| `MERCADOPAGO_ACCESS_TOKEN` | `billing/services.py` | ausente | ver seção Billing |

## Idioma — a regra que mais se erra

**Código em inglês, interface em português.** `Doctor`, `WorkoutSession`, `quantity_g` no
código; `verbose_name='médico'`, labels de `TextChoices` e todo texto de template em pt-BR.
Aspas simples. PEP8.

## Arquitetura

```
config/      settings, urls raiz, wsgi/asgi
core/        base models, mixins de isolamento, CBVs genéricas de dono, landing, dashboard
accounts/    User (login por e-mail), UserManager, Profile, signal, telas de auth
saude/       médicos, tratamentos, exames, consultas, medicamentos   (Sprint 2 — pronta)
treino/      grupos, exercícios, fichas, sessões                     (Sprint 3 — pronta)
nutricao/    alimentos, dietas, refeições, registro diário, peso     (Sprint 4 — pronta)
lembretes/   central de lembretes + command agendado                 (Sprint 5 — pronta)
billing/     planos, assinatura, gateway                             (Sprint 6 — pronta)
```

### Rotas

`config/urls.py` monta cada app num prefixo pt-BR (`conta/`, `saude/`, `treino/`, `nutricao/`,
`lembretes/`, `assinatura/`; `core` na raiz). Todo app tem `app_name` — refira URL sempre por
namespace (`accounts:login`, `core:dashboard`). `settings.LOGIN_URL` / `LOGIN_REDIRECT_URL` /
`LOGOUT_REDIRECT_URL` apontam pra esses nomes. `MEDIA_URL` só é servido pelo Django com `DEBUG`.

### Isolamento de dados — requisito de segurança nº 1

Multiusuário simples por dono. Não há organização acima do usuário; cada pessoa é dona
exclusiva dos próprios registros. A garantia mora em dois lugares, ambos em `core/mixins.py`:

- **`OwnerQuerySetMixin`** — filtra o queryset da view por `user=request.user`. Vale para
  list, detail, update e delete: uma detail view alcançada por PK devolve 404 para linha de
  outra pessoa, porque a linha não está no queryset.
- **`OwnerFormMixin`** — carimba o dono na criação **e** estreita o `queryset` de todo campo
  relacional do formulário. Sem essa segunda parte fica um buraco: num formulário de Exame,
  alguém poderia enviar por POST a chave do Médico de outro usuário e criar o vínculo.

Toda CBV de domínio usa o primeiro; toda CBV que escreve usa os dois. Não refaça o filtro na
mão dentro da view — herde das bases prontas em `core/views.py`:
`OwnerListView`/`OwnerDetailView`/`OwnerCreateView`/`OwnerUpdateView`/`OwnerDeleteView`. App
novo (`treino`, `nutricao`...) segue o padrão de `saude/views.py`: uma classe por operação,
`success_message` na de criar/editar, `extra_context` com `page_kicker`/`page_title` nas que
usam `templates/saude/object_form.html` (ou o equivalente do app).

### Recursos aninhados (item que só existe dentro de outro)

Padrão em `treino` — divisão dentro de ficha, série dentro de exercício de sessão — herde de
`ChildCreateView` (`core/views.py`) em vez de reimplementar "pegar o pai pela URL e conferir
dono". Define `parent_model`, `parent_field` (nome da FK no model filho) e, se a URL não usar
`parent_pk`, `parent_url_kwarg`. `nutricao` repete o padrão: item dentro de refeição, refeição
dentro de dieta.

**Nunca `on_delete=PROTECT` entre dois models do mesmo dono.** O `Collector` do Django avalia
`PROTECT` por FK isolada, sem saber que a linha "protegida" está sendo apagada na mesma
operação por outro caminho (`user` → `CASCADE`) — trava a exclusão em cascata do próprio
dono, inclusive a futura exclusão de conta (LGPD, Sprint 6), com um 500 cru. Caso real em
D-021 (`DECISIONS.md`). `PROTECT` só faz sentido para catálogo **compartilhado** entre
usuários, que esta base ainda não tem. `OwnerDeleteView` aceita `delete_warning` para avisar
na tela de confirmação quando a exclusão arrasta histórico junto (ex.: excluir exercício
apaga as séries registradas dele).

### Anexos (laudo, receita, foto de progresso...)

Nunca por `MEDIA_URL` direta. Padrão em `saude/models.py` (`Exam.attachment`) +
`core/validators.py`: `upload_to` grava em `<recurso>/<user_id>/<uuid4>.<ext>` — nome
original descartado, caminho não adivinhável — e uma view dedicada
(`ExamAttachmentView` é o exemplo) confere `user=request.user` antes de abrir o arquivo,
devolvendo **404**, nunca 403, para o que não é do dono ou não existe. `validate_attachment`
e `attachment_upload_path` são genéricos — reuse em qualquer FileField novo de dado sensível.

### Models base

Em `core/models.py`. `TimeStampedModel` dá `created_at`/`updated_at`; `OwnedModel` herda dele
e acrescenta a FK `user`. **Nenhum model de domínio foge dessas bases** — model com dados de
usuário sem `OwnedModel` escapa da camada de isolamento inteira.

O `related_name` é genérico (`'%(app_label)s_%(class)s_set'`) porque dezenas de models apontam
para `User` e nomes fixos colidiriam.

### Conta e perfil

`accounts.User` é `AbstractBaseUser` + `PermissionsMixin`: `USERNAME_FIELD = 'email'`, campo
único `full_name`, **sem `username`, `first_name` nem `last_name`**. `AUTH_USER_MODEL` está
fixado desde a primeira migration — trocar depois exige recriar o banco.

O `Profile` é criado por `post_save` em `accounts/signals.py`, registrado no `ready()` do
`AccountsConfig`. O resto do sistema pode assumir que `user.profile` existe; não escreva
`get_or_create` de perfil espalhado pelas views.

## Templates

`base.html` é a casca pública (nav, mensagens, rodapé, script do Lucide e do menu mobile).
`app_base.html` estende ela com a navegação autenticada — o logout é **POST**, num form.
`accounts/base_auth.html` é o layout split das telas de autenticação.

`partials/_field.html` renderiza um campo com o estilo Soluna. Formulário novo itera os campos
e inclui esse partial; não escreva markup de input à mão.

As classes de widget vivem em `accounts/forms.py` (`TEXT_INPUT_CLASS`, `SELECT_CLASS`) e são
aplicadas pelo `StyledFormMixin`. Formulário novo herda dele.

### Tokens do design system

| Papel | Cor |
|---|---|
| Página | `#f5f4f0` |
| Seção | `#ffffff` |
| Superfície | `#e8eae4` |
| Acento (hover) | `#5d674f` (`#4a523f`) |
| Ink | `#1a1a1a` |
| Warm | `#f2ece5` |
| Borda | `#dcdacd` |
| Texto secundário | `#5c5c5a` |
| Desabilitado | `#a0a09e` |

Botão primário: `rounded-full px-8 py-5`, ícone `arrow-right` que desliza no hover. Cartão:
`rounded-[2rem]`. Container: `max-w-screen-xl` ou `2xl` com `px-6 md:px-12`. Seção: `py-32`.
Tipografia Inter, peso máximo 600. Ícones Lucide com `stroke-[1.5]`.

### Macro calculado, não guardado

`nutricao.MealItem.macros` e `nutricao.DailyLog.macros` são `@property`, recalculadas de
`Food` + `quantity_g` a cada leitura — nunca gravadas na linha. `Food` é dado do próprio
usuário, editável a qualquer momento; congelar o macro deixaria totais antigos
dessincronizados sem aviso. Regra geral: **congele um valor histórico só quando a fonte é
externa e imutável por natureza** (laudo de exame, já em `saude`); calcule em runtime quando
a fonte é um cadastro que o próprio usuário edita.

## Lembretes: derivado × manual

`lembretes.Reminder` tem duas origens. **Derivado** — `content_type`/`object_id` preenchidos,
aponta pra `Medication`, `Exam`, `Appointment` ou `Meal` — é gerado por
`lembretes.services.sync_reminders(user)`, chamada tanto na visita à central
(`ReminderIndexView`) quanto no `dashboard` quanto no comando `send_due_reminders`. **Nunca
edite um `Reminder` derivado na mão nem tente fazer `get_or_create` incremental nele** — o
padrão é apaga-e-recria (D-029): toda chamada de `sync_reminders` apaga os pendentes
derivados da janela de 7 dias e recria do zero a partir do estado atual das apps de origem.
**Manual** — `content_type` nulo, criado pela pessoa em `/lembretes/novo/` — nunca é tocado
pelo sync.

Categoria nova de lembrete automático (ex.: um dia vier agendamento de treino) segue o padrão
de `lembretes/services.py`: uma função `_algo_reminders(user, today, horizon)` que devolve
uma lista de `Reminder(...)` não salvos, somada em `sync_reminders`, com `content_type` da
model de origem e `object_id` do registro. Rode `python manage.py send_due_reminders` pra
disparar manualmente em dev — ele sincroniza todo mundo e envia (console, `EMAIL_BACKEND`
atual) o que já venceu.

## Billing: `Plan` é catálogo, `Subscription` é do dono

`Plan` (Free/Premium, semeado por `billing/migrations/0002_seed_plans.py`) é o único model
sem `OwnedModel` de todo o domínio — é público, igual pra todo mundo, sem login inclusive
(aparece na landing). **Não** dê FK de dono a ele nem filtre por usuário pra lê-lo.
`Subscription` é `OwnedModel` normal, uma linha aberta por vez por pessoa
(`status in trial/active/past_due`), garantida por `UniqueConstraint` — **por usuário, não
por usuário+plano**: trocar de plano exige fechar (`status = cancelled`) a assinatura aberta
atual antes de abrir outra, sempre (D-035). Use `billing.models.current_subscription(user)` /
`current_plan(user)`, nunca consulte `Subscription` direto pra descobrir "o plano de alguém".

`Subscription.plan` é `on_delete=PROTECT` — e está certo assim. A regra de D-021 ("nunca
`PROTECT` entre models do mesmo dono") não se aplica aqui: `Plan` não é do dono de ninguém.
Antes de copiar `PROTECT` em qualquer FK nova, pergunte "os dois lados são do mesmo usuário?"
— se sim, `CASCADE`; se um lado é catálogo compartilhado (como `Plan`), `PROTECT` é o certo.

Gate de plano vive em `billing/gating.py` (`diet_limit_exceeded`, `auto_reminders_enabled`),
importado pelas apps de domínio — nunca o contrário, `billing/models.py` não importa
`nutricao`/`lembretes`. Nova regra de limite: adicione a chave em `Plan.limits` (JSON, editável
no admin sem migração) e uma função em `gating.py` que a lê via `limit_for(user, chave, default)`.

**`MERCADOPAGO_ACCESS_TOKEN` não está configurado neste ambiente** — não há conta de
vendedor real. O checkout (`billing/services.py`, `MercadoPagoGateway`) tem a forma correta
da API real (Checkout Pro, `urllib` puro, sem SDK nova) mas nunca rodou contra o Mercado Pago
de verdade. Em dev, `/assinatura/ativar-teste/` (só com `DEBUG=True`, rotulado `[Teste]` na
UI) ativa a assinatura sem cobrança — não confunda com pagamento real funcionando.

## LGPD

Anexo de exame é dado sensível. `MEDIA_URL` só é servido pelo Django com `DEBUG=True`; em
produção o laudo tem de sair por view autenticada que confere o dono, nunca por URL direta.
Exclusão e exportação completas da conta são entrega da Sprint 6.


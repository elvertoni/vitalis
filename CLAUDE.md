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
.\.venv\Scripts\python.exe manage.py seed_medico --email <e-mail> --source <dossiê.json> [--attachments-dir <pasta>]
```

`seed_medico` (em `core/management/commands/`) é **genérico e não contém dado nenhum**: tudo
vem do JSON de `--source`. É idempotente (`update_or_create` casando por campo natural), roda
numa transação e importa perfil, médicos, tratamentos, medicamentos, exames (com anexo, se
`--attachments-dir` apontar pros PDFs), consultas, alimentos, dietas e pesagens. A forma do
JSON está em `medico-seed.example.json` (versionado, sem dado). Dossiê real vive em
`medico-data/` e em `medico-seed.json` — **ambos no `.gitignore`** por serem dado sensível de
saúde (D-041). Nunca commite nem cole conteúdo desses arquivos.

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

`STORAGES['staticfiles']` é o `CompressedManifestStaticFilesStorage` do WhiteNoise: em
produção, `{% static %}` apontando pra arquivo que não existe em `staticfiles/` **quebra o
render**, não degrada em silêncio. Arquivo estático novo entra em `static/` e o `Dockerfile`
recolhe no build — não referencie caminho que só existe na sua máquina.

### Produção (EasyPanel) — ver `DECISIONS.md` D-040

`Dockerfile` builda com `python:3.12-slim`, roda `collectstatic` no build, e o
`entrypoint.sh` aplica `migrate` e sobe `gunicorn config.wsgi`. WhiteNoise serve o estático
(sem nginx na frente). Postgres entra via `DATABASE_URL` — **é o único switch**: sem essa
env, `config/settings.py` cai no SQLite de sempre. Anexos de exame vivem num volume montado
em `/app/media` (dado sensível, LGPD — não pode sumir num redeploy). App publicado em
`work/vitalis` no EasyPanel; domínio `vitalis.tonicoimbra.com`.

O serviço **`vitalis-backup`** no EasyPanel roda com `SERVICE_MODE=backup` a cada 24h via `scripts/backup.sh`:
- Gera dump do banco PostgreSQL (`vitalis-db-*.sql.gz`) e arquivo com os laudos de exame (`vitalis-media-*.tar.gz`).
- Testa integridade de cada arquivo com `gzip -t` antes de aceitar.
- Mantém retenção de 30 dias no volume `/backups`.
- Envia cópia externa para o Google Drive (`RCLONE_REMOTE=gdrive:`) na pasta `backup-vitalis` (`1iXaGZs_lHAbOC_lpxEe3hXLZYigatsPC`) autenticado via OAuth 2.0 com a conta pessoal do dono (D-055, D-056).

### Configuração — só `os.environ`, sem loader de `.env`

O código lê variáveis de ambiente puras via `os.environ.get` (nenhum `python-dotenv`). Defina
no shell antes do `runserver`:

| Variável | Lida em | Default | Efeito |
|---|---|---|---|
| `DJANGO_DEBUG` | `config/settings.py` | `0` | `1` ativa modo debug local. `0` (padrão) liga `SECURE_SSL_REDIRECT`, HSTS, cookies seguros e bloqueia inicialização sem `DJANGO_SECRET_KEY`. |
| `DJANGO_SECRET_KEY` | `config/settings.py` | obrigatória em prod | Chave criptográfica do Django. Obrigatória com `DEBUG=0` (levanta `RuntimeError` se omitida). |
| `DJANGO_ALLOWED_HOSTS` | `config/settings.py` | `localhost,127.0.0.1` | lista separada por vírgula |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `config/settings.py` | vazio | csv de origens `https://…` — obrigatório pro POST de login/admin em produção |
| `DATABASE_URL` | `config/settings.py` | ausente (→ SQLite) | presente → Postgres via `dj-database-url`. É o único switch dev↔prod de banco. |
| `EMAIL_HOST` (+ `_USER`/`_PASSWORD`, `EMAIL_PORT`, `EMAIL_USE_TLS`) | `config/settings.py` | ausente (→ console em dev, dummy em prod) | presente → SMTP real; em dev sem SMTP usa `console`; em prod sem SMTP usa `dummy` para não vazar tokens em logs |
| `DJANGO_SITE_URL` | `config/settings.py` | `http://127.0.0.1:8000` | base absoluta dos links dentro do lembrete enviado |
| `EVOLUTION_API_URL` / `_KEY` / `_INSTANCE` | `config/settings.py` | vazio (→ só e-mail) | as três juntas ligam o canal WhatsApp (D-045) |
| `DJANGO_DEFAULT_FROM_EMAIL` | `config/settings.py` | `Vitalis <nao-responda@vitalis.app>` | remetente dos lembretes e do reset de senha |
| `MERCADOPAGO_ACCESS_TOKEN` | `billing/services.py` | ausente | token de autenticação da API Mercado Pago |
| `MERCADOPAGO_WEBHOOK_SECRET` | `config/settings.py` | ausente | validação de assinatura HMAC (`x-signature`) no webhook |

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
treino/      grupos, exercícios, fichas, sessões, tela de registro   (Sprint 3 — pronta)
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
`OwnerListView`/`OwnerDetailView`/`OwnerCreateView`/`OwnerUpdateView`/`OwnerDeleteView`.
`OwnerListView` já vem com `paginate_by = 20` — a listagem nova inclui
`partials/_pagination.html` em vez de inventar navegação de páginas. App
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
apaga as séries registradas dele); quando um `PROTECT` legítimo barra a exclusão ela captura
`ProtectedError` e devolve `protected_message` como mensagem, nunca um 500.

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

Há um **segundo** `post_save` em `User`, este em `billing/signals.py` (`ready()` do
`BillingConfig`): toda conta nova abre uma `Subscription` no plano Free, `status=active`. Se
o plano `free` ainda não estiver semeado o signal sai calado — é o caso da própria migração
inicial rodando. Vale a mesma regra: não recrie assinatura na mão em view de cadastro.

## Templates

`base.html` é a casca pública (nav, mensagens, rodapé, script do Lucide e do menu mobile).
`app_base.html` estende ela com a navegação autenticada — o logout é **POST**, num form.
`accounts/base_auth.html` é o layout split das telas de autenticação.

`partials/_field.html` renderiza um campo com o estilo Soluna. Formulário novo itera os campos
e inclui esse partial; não escreva markup de input à mão. Os outros partials prontos são
`_empty_state.html` (lista vazia), `_pagination.html` (paginação das `OwnerListView`) e
`_logo.html` — inclua, não duplique.

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

### Navegação: o menu mobile é irmão do `<nav>`, nunca filho

`templates/base.html` tem `backdrop-blur-md` na barra, e `backdrop-filter` cria **bloco de
contenção para `position: fixed`**. Com o `#mobile-menu` dentro do `<nav>`, o `inset-0` media
a barra de 96px em vez da janela e metade dos itens nascia fora da tela, sem erro nenhum
(D-051). Se algum dia o menu for movido de volta para dentro da barra, o bug volta inteiro.
Os itens são **linhas de largura total de 56px**, não pílulas: pílula no design system
significa ação primária, e navegação não disputa com "Registrar treino". `h-[100dvh]`, não
`100vh` — a barra de URL do Safari iOS come a diferença.

### Treino: a tela de registro e o CRUD são caminhos diferentes

`/treino/registrar/` é o caminho semanal (D-048): escolhe a divisão e grava o treino inteiro
num POST — um par de campos por série, cronômetro que arma com o descanso prescrito, sugestão
de carga ao lado do campo. O CRUD de sessão continua existindo como "Sessão avulsa", para
corrigir e para treino que não segue ficha. **A tela nova não edita prescrição**: séries e
faixa de repetição mudam na ficha.

Três regras que valem ao mexer nela:

- **Visitar não é registrar** (D-049). O GET não escreve nada. Os campos são nomeados pelo
  alvo (`t<target_pk>s<n>reps`), não pela entrada, justamente porque a sessão ainda não
  existe. No POST, `read_submission` lê o formulário inteiro antes de tocar no banco; sessão e
  `SessionEntry` nascem só se veio número, e sessão que termina sem entrada é apagada. Não
  reintroduza `get_or_create` no GET: sessão vazia mente na frequência da semana.
- **Descanso prescrito ≠ descanso praticado** (D-050). `RoutineExerciseTarget.rest_seconds` é
  o plano (arma o cronômetro); `SessionEntry.rest_seconds` é o que aconteceu no dia. Campo
  novo de prescrição entra no alvo **e** em `RoutineExerciseTargetForm`, senão exercício
  criado pela interface nunca chega à tela.
- **`WorkoutSession.morning_after`** (`ok`/`worse`) é dado consultado, não anotação: numa
  tendinopatia a dor aparece no dia seguinte, e `progression.morning_streak` conta as semanas
  sem `worse`. Por isso é coluna, e não texto em `notes`.

`treino/progression.py` é puro cálculo, sem view: `top_of_range` lê a faixa (`'8-12'` → 12,
`'45s'` → `None`, porque prescrição em tempo não progride por repetição) e `suggestion_for` só
sugere subir carga quando **todas** as séries bateram o topo — +5 kg em perna, +2,5 kg no
resto. É sugestão exibida no campo, nunca escrita automática.

### Peso e macro: a fonte é o histórico, o formulário é só a porta

`ProfileForm.current_weight_kg` não é coluna de `Profile` — é campo de formulário que lê a
última pesagem e grava um `WeightLog` de hoje ao salvar (D-047). Se precisar do peso atual em
alguma tela nova, leia `WeightLog` (`.order_by('-date').first()`), nunca o perfil.

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
O wipe alcança só o que está **pendente**, então a recriação passa por `_drop_already_handled`
antes do `bulk_create`: derivado cuja chave `(content_type, object_id, remind_at)` já existe
na janela como enviado/concluído/cancelado não volta. Sem esse filtro, o lembrete da manhã
que já saiu por e-mail é recriado vencido e reenviado a cada rodada do agendador (D-043).
**Manual** — `content_type` nulo, criado pela pessoa em `/lembretes/novo/` — nunca é tocado
pelo sync.

Uma `Appointment` com `next_return_date` rende **dois** lembretes derivados (D-042): o do
retorno no dia (`_appointment_reminders`) e o de *marcar* a consulta 15 dias antes
(`_return_scheduling_reminders`, constante `RETURN_SCHEDULING_LEAD_DAYS` em `saude/models.py`
— fica lá porque `saude` não importa `lembretes`). O segundo só olha a última consulta de
cada médico: registrar uma consulta mais nova com o mesmo médico é o sinal de "já agendei" e
cala o aviso, sem campo de controle manual.

### Gerar é uma coisa, notificar é outra

`sync_reminders` gera tudo; **quem sai por mensagem é só a categoria `agendar`**
(`Reminder.Category.SCHEDULING`), listada em `lembretes/notifications.py`
(`NOTIFY_CATEGORIES`). Dose de remédio e refeição da dieta continuam na central e no painel e
nunca viram e-mail — onze avisos de rotina por dia afogam o único que exige ação, que é ligar
para marcar alguma coisa (D-044). Três geradores alimentam a categoria: retorno pedido pelo
médico, exame solicitado sem data marcada e tratamento aberto sem nada agendado.

`notifications.py` é também o **único lugar que conhece o canal**: `send_reminder` monta o
texto e entrega. O comando `send_due_reminders` decide *quando*, nunca *o quê* nem *como*.
Canais: e-mail sempre, e **WhatsApp** por `lembretes/whatsapp.py` (Evolution API, instância
própria `vitalis` — D-045) quando a pessoa escolheu esse canal no perfil, o gateway está
configurado e há telefone. Qualquer falha do gateway cai para e-mail com `logger.warning`:
lembrete que chega pelo canal errado vale mais que lembrete que não chega.

O pareamento da sessão fica em `/lembretes/whatsapp/`, **só para superusuários ou quem tem `lembretes.manage_whatsapp`** e devolvendo 404
para os demais (D-046): a instância é o remetente do sistema, não o WhatsApp de cada conta —
derrubar aquela sessão tira o canal de todo mundo. Em produção o `EVOLUTION_API_URL` aponta
para `http://work_evolution-api:8080` (rede interna do EasyPanel); pela URL pública o
Cloudflare barra o User-Agent do `urllib` com 403 `error code: 1010`, por isso o cliente se
identifica como `Vitalis/1.0`. Os links dentro da
mensagem usam `settings.SITE_URL` (env `DJANGO_SITE_URL`), porque quem envia está fora do
ciclo HTTP e não tem `request` para montar URL absoluta.

Categoria nova de lembrete automático (ex.: um dia vier agendamento de treino) segue o padrão
de `lembretes/services.py`: uma função `_algo_reminders(user, today, horizon)` que devolve
uma lista de `Reminder(...)` não salvos, somada em `sync_reminders`, com `content_type` da
model de origem e `object_id` do registro. Rode `python manage.py send_due_reminders` pra
disparar manualmente em dev — ele sincroniza todo mundo e envia (console, `EMAIL_BACKEND`
atual) o que já venceu.

Em produção quem chama esse comando é o serviço **`vitalis-cron`** do EasyPanel: mesma imagem
do app, `SERVICE_MODE=cron` no ambiente, e o `entrypoint.sh` entra num laço de
`send_due_reminders` a cada 15 minutos em vez de subir o gunicorn. Nesse modo ele **não** roda
`migrate` — quem aplica schema é o serviço web. Mexeu em `sync_reminders` ou no envio? Rode
o comando duas vezes seguidas e confira que a segunda envia zero: é o teste que pega
regressão de reenvio.

## Billing: `Plan` é catálogo, `Subscription` é do dono

`Plan` (Free/Premium, semeado por `billing/migrations/0002_seed_plans.py`) é o único model
sem `OwnedModel` de todo o domínio — é público, igual pra todo mundo, sem login inclusive
(aparece na landing). **Não** dê FK de dono a ele nem filtre por usuário pra lê-lo.
`Subscription` é `OwnedModel` normal, uma linha aberta por vez por pessoa
(`status in trial/active/past_due`), garantida por `UniqueConstraint` — **por usuário, não
por usuário+plano**: trocar de plano exige fechar (`status = cancelled`) a assinatura aberta
atual antes de abrir outra, sempre (D-035). Use `billing.models.current_subscription(user)` /
`current_plan(user)`, nunca consulte `Subscription` direto pra descobrir "o plano de alguém".

Ao ativar (`Subscription.activate()`), `expires_at` é calculado com base na periodicidade
(`monthly` = +30 dias, `yearly` = +365 dias). Se `expires_at` tiver passado, `current_subscription`
marca a linha como `past_due` e `current_plan` faz fallback seguro para o plano `Free`.

`Subscription.plan` é `on_delete=PROTECT` — e está certo assim. A regra de D-021 ("nunca
`PROTECT` entre models do mesmo dono") não se aplica aqui: `Plan` não é do dono de ninguém.
Antes de copiar `PROTECT` em qualquer FK nova, pergunte "os dois lados são do mesmo usuário?"
— se sim, `CASCADE`; se um lado é catálogo compartilhado (como `Plan`), `PROTECT` é o certo.

Gate de plano vive em `billing/gating.py` (`diet_limit_exceeded`, `auto_reminders_enabled`),
importado pelas apps de domínio — nunca o contrário, `billing/models.py` não importa
`nutricao`/`lembretes`. Nova regra de limite: adicione a chave em `Plan.limits` (JSON, editável
no admin sem migração) e uma função em `gating.py` que a lê via `limit_for(user, chave, default)`.

O webhook do Mercado Pago valida a assinatura HMAC (`x-signature`) via `MERCADOPAGO_WEBHOOK_SECRET`
e grava o histórico em `ProcessedWebhookEvent` para garantir idempotência contra replay.

**`MERCADOPAGO_ACCESS_TOKEN` não está configurado neste ambiente** — não há conta de
vendedor real. O checkout (`billing/services.py`, `MercadoPagoGateway`) tem a forma correta
da API real (Checkout Pro, `urllib` puro, sem SDK nova) mas nunca rodou contra o Mercado Pago
de verdade. Em dev, `/assinatura/ativar-teste/` (só com `DEBUG=True`, rotulado `[Teste]` na
UI) ativa a assinatura sem cobrança — não confunda com pagamento real funcionando.

## Segurança e Rate Limiting

- **Rate Limiting:** `core/ratelimit.py` protege `/contas/entrar/` (5 req/min) e `/contas/recuperar-senha/` (3 req/5min) contra ataques de força bruta.
- **Content-Security-Policy (CSP):** Injetado por `core.middleware.SecurityHeadersMiddleware` em todas as respostas HTTP.
- **Fail-Closed:** Em produção sem `DJANGO_SECRET_KEY`, o app recusa inicializar. Sem `EMAIL_HOST` em produção, e-mails usam `dummy.EmailBackend` para evitar vazamento de tokens em stdout/logs.

## LGPD e Portabilidade

- **Portabilidade de Dados (Art. 18):** Implementada a rota autenticada `/contas/exportar-dados/` (`ExportUserDataView`) que gera download direto em `.zip` contendo `prontuario_vitalis.json` com o histórico clínico/antropométrico completo e os laudos anexados em PDF na pasta `laudos/` (D-059).
- **Dados Sensíveis:** Anexos de exame são dados de saúde sensíveis. `MEDIA_URL` só é servido pelo Django com `DEBUG=True`; em produção o laudo tem de sair por view autenticada (`ExamAttachmentView`) que confere a titularidade do dono. Dossiês reais vivem fora do git (`medico-data/`, `medico-seed.json`, `/toni/` — D-041, D-058).

## Módulos Clínicos Recentes

- **Biomarcadores Laboratoriais (`/saude/biomarcadores/`):** Painel gráfico com réguas de referência proporcionais, rastro comparativo com exames anteriores e delta percentual, régua de IMC e alertas clínicos prioritários (D-058).
# [dado clinico removido do historico - D-061]
- **Acessibilidade Impeccable (D-060):** Regra global `@media (prefers-reduced-motion: reduce)` em `base.html`, injeção automática de `aria-required`, `aria-invalid` e `aria-describedby` em todos os formulários via `StyledFormMixin`, e touch targets mínimos de 44px em botões de ação e exclusão.

## O que ainda não existe

O roadmap S1–S6 do PRD e as extensões clínicas estão entregues. As lacunas conhecidas remanescentes são:

- **Exclusão completa da conta (LGPD).** A exportação está entregue (`/contas/exportar-dados/`), mas a exclusão irreversível da conta (`delete_account`) ainda não foi implementada. Ao construir: a exclusão cai em `user.delete()` com CASCADE por toda a base (D-021).
- **Pagamento real.** O `MercadoPagoGateway` nunca rodou contra o Mercado Pago de vendedor real; opera com checkout simulado.
- **Catálogo de alimentos de referência (TACO).** `Food` é cadastro do usuário (D-025).
- **Lembrete automático de treino.** Decisão explícita de não ter (D-027).
- **Instância WhatsApp conectada.** A integração Evolution API existe no código, mas o envio ativo em produção requer chip conectado (D-028).



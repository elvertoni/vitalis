# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Documentos que mandam neste repositório

| Arquivo | Papel |
|---|---|
| `PRD-vitalis.md` | **O QUE** construir. Fonte de verdade de escopo, models e telas. |
| `PROMPT-EXEC-vitalis.xml` | **COMO** executar. Diretivas absolutas, ordem das sprints, definition of done. |
| `design_system/design-system.html` | A referência visual. Nenhum estilo fora dela. |
| `DECISIONS.md` | Decisões tomadas sob o `ambiguity_protocol`. Toda decisão ambígua entra aqui. |

Conflito de **escopo** → o PRD vence. Conflito de **convenção de código** → o XML vence.

## Comandos

```powershell
.\.venv\Scripts\python.exe manage.py runserver
.\.venv\Scripts\python.exe manage.py makemigrations
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Sem Docker, sem suíte de testes — ambos proibidos pela diretiva D10. Banco: SQLite em
`db.sqlite3`. E-mail sai no console em desenvolvimento; o link de recuperação de senha aparece
no terminal do `runserver`.

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
nutricao/    alimentos, dietas, refeições, registro diário, peso     (Sprint 4)
lembretes/   central de lembretes + command agendado                 (Sprint 5)
billing/     planos, assinatura, gateway                             (Sprint 6)
```

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

## LGPD

Anexo de exame é dado sensível. `MEDIA_URL` só é servido pelo Django com `DEBUG=True`; em
produção o laudo tem de sair por view autenticada que confere o dono, nunca por URL direta.
Exclusão e exportação completas da conta são entrega da Sprint 6.

## `_legado_vida/`

Sistema anterior e incompatível: PostgreSQL com Row-Level Security, Docker, código em
português, apps `contas`/`exames`/`medicacao`. **Não é referência de arquitetura** — foi
substituído pelo Vitalis. Serve só como fonte de domínio para as sprints de saúde e nutrição
(modelagem de exame laboratorial, faixa de referência, posologia em fases). Nada dali deve ser
importado como está.

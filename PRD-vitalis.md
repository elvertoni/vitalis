# PRD — Vitalis

**Product Requirement Document**
**Versão:** 1.0
**Status:** Draft para desenvolvimento
**Stack principal:** Python 3.12+ · Django 6.0 · SQLite

> **Nome do projeto:** *Vitalis* (provisório — trocar aqui e no `settings` caso opte por outro).
> **Decisões pendentes marcadas com ⚠️ ao longo do documento** (canal de lembrete, gateway de pagamento e escopo da camada de IA na v1).

---

## 1. Visão Geral

O **Vitalis** é uma plataforma web de controle de vida pessoal centrada em três pilares: **Saúde**, **Treino** e **Nutrição**. Cada usuário mantém, em um único lugar, o histórico completo de médicos, tratamentos, exames, treinos, dieta e evolução física, recebendo lembretes automáticos de remédios, exames e retornos médicos.

O produto se comporta como um **assistente pessoal de saúde e bem-estar** e é construído desde a fundação para operar como **SaaS multiusuário**, onde cada usuário assina um plano e gerencia exclusivamente a própria vida na plataforma.

### 1.1 Problema

As informações de saúde, treino e alimentação de uma pessoa ficam espalhadas: exames em pastas físicas ou no e-mail, treino em planilha ou caderno, dieta no papel do nutricionista, lembretes de remédio na cabeça. Não há visão consolidada nem histórico evolutivo.

### 1.2 Solução

Um app único que centraliza essas três áreas, gera lembretes e mostra a evolução ao longo do tempo, com potencial futuro de uma camada de IA que analisa o histórico do usuário e devolve insights.

### 1.3 Objetivos do produto

1. Centralizar saúde, treino e nutrição de cada usuário em um só lugar.
2. Nunca deixar o usuário esquecer remédio, exame ou retorno médico.
3. Dar visão evolutiva (carga no treino, peso corporal, aderência à dieta).
4. Escalar como SaaS com planos pagos individuais.

### 1.4 Não-objetivos (v1)

- Não é prontuário médico oficial nem substitui acompanhamento profissional.
- Não faz prescrição médica, de treino ou de dieta automaticamente.
- Não integra com wearables na v1 (fase futura).
- Sem app mobile nativo na v1 (web responsivo apenas).

---

## 2. Público-alvo e Personas

| Persona | Descrição | Necessidade principal |
|---|---|---|
| **Autogerenciador** | Pessoa que treina, se cuida e quer organizar tudo | Ter tudo num lugar só, com lembretes |
| **Paciente em tratamento** | Faz tratamento contínuo, muitos exames e retornos | Não perder retornos e horários de remédio |
| **Praticante de treino/dieta** | Foco em performance física | Registrar carga, evolução e macros |

Público SaaS: **usuário final individual** que assina um plano. Não há hierarquia de organização acima do usuário (diferente do modelo escola→curso→aluno).

---

## 3. Arquitetura

### 3.1 Modelo de isolamento de dados

Arquitetura **multiusuário simples com isolamento por owner**:

- Todo model de domínio tem FK obrigatória para o usuário dono (`user` / `owner`).
- Todas as queries filtram pelo usuário logado. Nenhum dado é compartilhado entre usuários.
- Padrão de acesso: usar sempre `self.request.user` como filtro base nas CBVs (via `get_queryset()`), nunca expor PKs de outros usuários.
- Recomenda-se um `OwnerQuerySetMixin` central que aplica `filter(user=self.request.user)` automaticamente em todas as views de listagem/detalhe/edição/exclusão.

### 3.2 Stack técnica

| Camada | Tecnologia |
|---|---|
| Backend | Django 6.0 |
| Banco | SQLite (padrão Django) |
| Autenticação | Sistema nativo do Django, **login por e-mail** |
| Frontend | Templates Django + design system próprio (`@design_system/design-system.html`) |
| Gráficos | Chart.js (evolução de carga, peso, calorias) |
| Tarefas/lembretes | ⚠️ ver seção 8 (Celery+Redis ou `django-cron`/management command) |
| IA (fase futura) | LangChain / LangGraph + RAG sobre dados do próprio usuário |

### 3.3 Apps Django (separação por domínio)

```
config/                 # settings, urls raiz, wsgi/asgi
accounts/               # usuário customizado, auth por e-mail, perfil, planos
core/                   # dashboard, mixins, base models, utilitários compartilhados
saude/                  # médicos, tratamentos, exames, consultas, medicamentos
treino/                 # exercícios, grupos musculares, sessões, fichas, evolução
nutricao/               # alimentos, cardápios, registro diário, peso, macros
lembretes/              # central de lembretes e notificações
billing/                # planos, assinaturas, integração com gateway
```

### 3.4 Model base compartilhado

Todos os models herdam de um `TimeStampedModel` abstrato:

```python
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
```

Models de domínio herdam também de um `OwnedModel` (com FK `user`), quando aplicável.

---

## 4. App `accounts`

### 4.1 Responsabilidades

- Usuário customizado com login por **e-mail** (sem username).
- Cadastro, login, logout, recuperação de senha.
- Perfil do usuário (dados pessoais e biométricos base para cálculos).
- Vínculo com plano/assinatura.

### 4.2 Models

**`User`** (custom, `AbstractBaseUser` + `PermissionsMixin`):
- `email` (unique, USERNAME_FIELD)
- `full_name`
- `is_active`, `is_staff`
- `created_at`, `updated_at`

> Implementar `UserManager` customizado com `create_user`/`create_superuser` por e-mail. Definir `AUTH_USER_MODEL = 'accounts.User'` desde a primeira migration.

**`Profile`** (OneToOne com User):
- `birth_date`
- `sex` (choices: M/F/Outro)
- `height_cm`
- `phone` (para lembretes por WhatsApp/SMS, se aplicável)
- `notification_channel` (choices: e-mail / whatsapp / push) ⚠️
- `created_at`, `updated_at`

### 4.3 Regras

- Login sempre por e-mail.
- Ao criar `User`, criar `Profile` automaticamente via signal (`accounts/signals.py`).
- Após login → redirecionar para o **Dashboard** (`core`).

---

## 5. App `core` (Dashboard)

### 5.1 Responsabilidades

- Página inicial autenticada com visão consolidada das três áreas.
- Mixins compartilhados (`OwnerQuerySetMixin`, `TimeStampedModel`).
- Utilitários de data, cálculos comuns.

### 5.2 Conteúdo do Dashboard

Visão de um "raio-x do dia/semana":

- **Próximos compromissos de saúde:** próximos retornos, exames marcados, remédios de hoje.
- **Treino:** treino planejado para hoje/semana + status de aderência.
- **Nutrição:** dieta do dia, total de calorias/macros consumidos x meta, evolução de peso (mini gráfico).
- **Lembretes ativos:** lista dos lembretes das próximas 24–48h.
- **Atalhos rápidos:** registrar treino, registrar refeição, registrar peso, novo exame.

---

## 6. App `saude`

### 6.1 Models

**`Doctor`** (Médico):
- `user` (FK)
- `name`
- `specialty`
- `phone`, `email`
- `clinic_name`, `clinic_address`
- `notes`
- `created_at`, `updated_at`

**`Treatment`** (Tratamento):
- `user` (FK)
- `doctor` (FK, nullable)
- `name`
- `description`
- `start_date`, `end_date` (nullable)
- `status` (choices: em andamento / concluído / pausado / cancelado)
- `notes`
- `created_at`, `updated_at`

**`Exam`** (Exame):
- `user` (FK)
- `doctor` (FK solicitante, nullable)
- `treatment` (FK, nullable)
- `name`
- `requested_date`
- `done_date` (nullable)
- `result_summary`
- `attachment` (upload PDF/imagem — laudo)
- `status` (choices: solicitado / agendado / realizado)
- `created_at`, `updated_at`

**`Appointment`** (Consulta/Retorno):
- `user` (FK)
- `doctor` (FK)
- `treatment` (FK, nullable)
- `date`
- `reason`
- `notes`
- `next_return_date` (nullable → gera lembrete)
- `created_at`, `updated_at`

**`Medication`** (Medicamento):
- `user` (FK)
- `treatment` (FK, nullable)
- `name`
- `dosage`
- `frequency` (ex: 8/8h, 1x ao dia)
- `start_date`, `end_date` (nullable)
- `schedule_times` (horários do dia → geram lembretes)
- `is_active`
- `created_at`, `updated_at`

### 6.2 Regras

- Ao salvar `Appointment.next_return_date` → gerar lembrete de retorno.
- Ao salvar `Exam.done_date` com agendamento futuro → gerar lembrete de exame.
- `Medication` com `schedule_times` → gerar lembretes recorrentes de remédio.
- Upload de laudos: validar tipo (PDF/JPG/PNG) e tamanho.

---

## 7. App `treino`

### 7.1 Models

**`MuscleGroup`** (Grupo muscular):
- `user` (FK) — permite grupos padrão + customizados
- `name` (peito, costas, perna, ombro, bíceps, tríceps, core...)
- `created_at`, `updated_at`

**`Exercise`** (Exercício):
- `user` (FK)
- `muscle_group` (FK)
- `name`
- `type` (choices: força / cardio / mobilidade / funcional)
- `notes`
- `created_at`, `updated_at`

**`WorkoutRoutine`** (Ficha/Rotina):
- `user` (FK)
- `name` (ex: "Push Pull Legs")
- `description`
- `is_active`
- `created_at`, `updated_at`

**`RoutineDay`** (Divisão da ficha — treino A, B, C...):
- `routine` (FK)
- `label` (A, B, C / Push / Pull / Legs)
- `muscle_groups` (M2M com MuscleGroup)
- `exercises` (M2M com Exercise, ou via tabela intermediária com séries/reps alvo)
- `created_at`, `updated_at`

**`WorkoutSession`** (Sessão realizada):
- `user` (FK)
- `routine_day` (FK, nullable)
- `date`
- `duration_minutes` (nullable)
- `notes`
- `created_at`, `updated_at`

**`SessionEntry`** (Registro de exercício na sessão):
- `session` (FK)
- `exercise` (FK)
- `sets` (nº de séries)
- `reps` (repetições — pode ser por série via JSON, ver observação)
- `weight` (carga usada)
- `rest_seconds` (descanso)
- `created_at`, `updated_at`

> **Observação de modelagem:** para registrar séries com cargas/reps diferentes por série, considerar um model `SetLog` (série individual: `entry` FK, `set_number`, `reps`, `weight`). Isso viabiliza a evolução de carga fina. Decidir na Sprint de Treino.

### 7.2 Regras / Relatórios

- **Evolução de carga:** por exercício, gráfico de `weight` ao longo do tempo (linha temporal das sessões).
- **Volume por grupo muscular:** somatório de séries por `muscle_group` por semana.
- Frequência semanal de treino x meta.

---

## 8. App `nutricao`

### 8.1 Models

**`Food`** (Alimento):
- `user` (FK) — base própria; pré-carregar referência tipo tabela **TACO** como seed opcional
- `name`
- `portion_base_g` (porção base, ex: 100g)
- `calories`
- `protein_g`, `carbs_g`, `fat_g`
- `created_at`, `updated_at`

**`Diet`** (Dieta/Plano alimentar):
- `user` (FK)
- `name`
- `goal` (choices: emagrecimento / manutenção / ganho de massa)
- `daily_calorie_target`
- `protein_target_g`, `carbs_target_g`, `fat_target_g`
- `is_active`
- `created_at`, `updated_at`

**`Meal`** (Refeição do plano):
- `diet` (FK)
- `name` (café da manhã, almoço, jantar, lanche...)
- `time` (horário sugerido)
- `created_at`, `updated_at`

**`MealItem`** (Item da refeição):
- `meal` (FK)
- `food` (FK)
- `quantity_g` (quantidade)
- (macros calculados a partir de `food` × quantidade)
- `created_at`, `updated_at`

**`DailyLog`** (Registro diário do que foi consumido):
- `user` (FK)
- `date`
- `meal_name`
- `food` (FK)
- `quantity_g`
- `created_at`, `updated_at`

**`WeightLog`** (Controle de peso corporal):
- `user` (FK)
- `date`
- `weight_kg`
- `notes`
- `created_at`, `updated_at`

### 8.2 Regras / Cálculos

- **Cálculo nutricional:** calorias e macros por refeição = Σ (item.food.macros × quantity / portion_base). Total diário = Σ refeições.
- **Aderência:** comparar `DailyLog` do dia com o plano `Diet` ativo (consumido x planejado).
- **Evolução de peso:** gráfico temporal de `WeightLog` + linha de meta.
- (Opcional) cálculo de TMB/GET a partir de `Profile` (peso, altura, idade, sexo) para sugerir meta calórica.

---

## 9. App `lembretes`

### 9.1 Responsabilidades

Central unificada que consolida gatilhos das três áreas:
- Remédio (recorrente, por horário)
- Exame agendado
- Retorno médico
- Treino do dia
- Refeição/dieta do dia

### 9.2 Model

**`Reminder`**:
- `user` (FK)
- `category` (choices: remédio / exame / retorno / treino / nutrição)
- `title`
- `description`
- `remind_at` (datetime)
- `is_recurring`, `recurrence_rule` (para remédios)
- `status` (choices: pendente / enviado / concluído / cancelado)
- `source_content_type` + `source_object_id` (GenericFK opcional para o objeto de origem)
- `created_at`, `updated_at`

### 9.3 Envio de notificações ⚠️

**Decisão pendente — canal da v1:**

| Opção | Prós | Contras |
|---|---|---|
| **E-mail** | mais simples, sem custo de API | menor engajamento |
| **WhatsApp** (Evolution API) | alto engajamento, você já domina | mais infra |
| **Push web** | nativo, sem custo | usuário precisa permitir |

**Recomendação v1:** começar por **e-mail** (baixo atrito) e deixar WhatsApp como plugin da fase 2, já que você tem stack Evolution API pronta.

**Agendamento:** um **management command** (`send_due_reminders`) rodando via cron a cada X minutos para MVP, evoluindo para Celery + beat se o volume justificar. (Evita infra pesada no início, alinhado a "não implementar Docker".)

---

## 10. App `billing` (SaaS)

### 10.1 Models

**`Plan`**:
- `name` (Free / Premium)
- `price`
- `billing_period` (mensal / anual)
- `limits` (JSON: nº de exames, uso de IA, etc.)
- `created_at`, `updated_at`

**`Subscription`**:
- `user` (FK)
- `plan` (FK)
- `status` (choices: ativa / cancelada / inadimplente / trial)
- `started_at`, `expires_at`
- `gateway_customer_id`, `gateway_subscription_id`
- `created_at`, `updated_at`

### 10.2 Planos (sugestão inicial)

| Plano | Preço | Limites |
|---|---|---|
| **Free** | R$ 0 | 1 dieta ativa, treino ilimitado, sem lembretes automáticos, sem IA |
| **Premium** | ⚠️ definir | tudo ilimitado + lembretes + IA (fase futura) |

### 10.3 Gateway ⚠️

Decidir entre **Stripe** (internacional/robusto) e **Mercado Pago** (Brasil, Pix). Recomendação para público BR: **Mercado Pago** com Pix + cartão. Isolar a integração num serviço (`billing/services.py`) para trocar de gateway sem espalhar código.

---

## 11. Fluxos principais

### 11.1 Onboarding
1. Usuário acessa landing → clica em "Começar".
2. Cadastra e-mail + senha + nome.
3. Confirma e-mail (opcional na v1).
4. Preenche perfil base (altura, data de nascimento, sexo, canal de lembrete).
5. Escolhe plano (Free por padrão).
6. Cai no Dashboard.

### 11.2 Uso diário
- Vê Dashboard consolidado.
- Registra treino / refeição / peso.
- Recebe e conclui lembretes.

### 11.3 Fluxo de saúde
- Cadastra médico → cria tratamento → registra exames e consultas → agenda retorno → recebe lembrete.

---

## 12. Telas (mínimo v1)

**Públicas:**
- Landing page (copy de vendas + planos + CTA)
- Login / Cadastro / Recuperação de senha

**Autenticadas:**
- Dashboard consolidado
- **Saúde:** lista + CRUD de Médicos, Tratamentos, Exames, Consultas, Medicamentos
- **Treino:** Grupos musculares, Exercícios, Fichas/Rotinas, Registrar sessão, Evolução de carga (gráfico)
- **Nutrição:** Alimentos, Dietas/Cardápios, Registro diário, Controle de peso (gráfico), Resumo nutricional
- **Lembretes:** central + configuração
- **Perfil / Conta / Assinatura**

---

## 13. Convenções técnicas

- Python + Django 6.0, **SQLite** padrão.
- Autenticação nativa Django, **login por e-mail**.
- Código do projeto em **inglês**; toda a **interface em português brasileiro**.
- **Aspas simples** sempre que possível; PEP8.
- **Class-Based Views** e recursos nativos do Django preferencialmente.
- Todo model com `created_at` e `updated_at` (via `TimeStampedModel`).
- Signals em `signals.py` dentro da app correspondente (registrar em `apps.py > ready()`).
- Separação por apps de domínio (isolar responsabilidades).
- Design system rigorosamente seguido a partir de `@design_system/design-system.html`.
- **Não** implementar Docker.
- **Não** implementar testes automatizados.
- Isolamento de dados por `user` em todas as queries (`OwnerQuerySetMixin`).

---

## 14. Roadmap por Sprints

| Sprint | Entrega | Apps |
|---|---|---|
| **S1 — Fundação** | Projeto, settings, User custom (login por e-mail), Profile, base models, design system, landing, auth | `config`, `accounts`, `core` |
| **S2 — Saúde** | CRUD médicos, tratamentos, exames (upload), consultas, medicamentos | `saude` |
| **S3 — Treino** | Grupos musculares, exercícios, fichas, sessões, evolução de carga (gráfico) | `treino` |
| **S4 — Nutrição** | Alimentos (+seed TACO), dietas, refeições, registro diário, peso, cálculo de macros | `nutricao` |
| **S5 — Lembretes** | Central de lembretes + envio por e-mail + command agendado + Dashboard consolidado | `lembretes`, `core` |
| **S6 — SaaS** | Planos, assinatura, integração de gateway, gate de features por plano | `billing` |
| **S7 — Fase futura** | Camada de IA (RAG sobre dados do usuário), WhatsApp, wearables, exportações | — |

---

## 15. Riscos e pontos de atenção

- **Dado sensível de saúde:** exames e histórico médico exigem cuidado com LGPD (consentimento, criptografia de anexos, direito de exclusão/exportação de dados).
- **SQLite em SaaS:** ótimo para MVP/single-node; se o volume crescer, planejar migração para Postgres (manter models agnósticos).
- **Não é ferramenta clínica:** deixar claro na UI que não substitui profissional de saúde (disclaimer).
- **Cálculo nutricional:** precisa de base de alimentos confiável (TACO/IBGE) para os macros fazerem sentido.

---

## 16. Decisões pendentes (resolver antes/durante S1)

1. ⚠️ Nome definitivo do produto.
2. ⚠️ Canal de lembrete da v1 (recomendado: e-mail).
3. ⚠️ Gateway de pagamento (recomendado: Mercado Pago).
4. ⚠️ Escopo da IA: entra só na S7 (recomendado) ou já um MVP conversacional antes?
5. ⚠️ Registro de séries: `SessionEntry` simples ou `SetLog` por série.

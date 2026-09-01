# Decisões técnicas

Registro das decisões tomadas sob o `<ambiguity_protocol>` do `PROMPT-EXEC-vitalis.xml`.
Uma entrada por decisão, com o motivo. Ordem cronológica.

---

## Sprint 1 — Fundação

### D-001 · Stack anterior arquivada, não apagada
**Contexto:** o repositório continha um sistema diferente (`vida/`), com PostgreSQL, Row-Level
Security, Docker e testes — arquitetura incompatível com as diretivas D10/D11 deste prompt.
**Decisão:** mover tudo para `_legado_vida/` em vez de apagar.
**Motivo:** o diretório não está sob controle de versão; apagar seria irreversível. Arquivar
custa nada e mantém a referência de domínio (exames, posologia) disponível para as sprints de
saúde e nutrição.

### D-002 · Django fixado em 6.0.x
**Contexto:** `pip install "Django>=6.0"` traz a 6.1.
**Decisão:** fixar `Django>=6.0,<6.1` no `requirements.txt`.
**Motivo:** o prompt e o PRD especificam Django 6.0. Subir de minor é decisão do dono do
projeto, não efeito colateral de instalação.

### D-003 · `OwnedModel` herda de `TimeStampedModel`
**Contexto:** D1 exige timestamps em todo model; D2 exige a FK de dono nos models de dados.
**Decisão:** `OwnedModel(TimeStampedModel)` em vez de duas bases independentes.
**Motivo:** todo model com dono também precisa de timestamp. Uma herança só evita listas de
bases múltiplas repetidas em cada app.

### D-004 · `related_name` genérico no `OwnedModel`
**Decisão:** `related_name='%(app_label)s_%(class)s_set'`.
**Motivo:** com dezenas de models apontando para `User`, nomes fixos colidem. O padrão do
Django resolve isso sem exigir que cada model declare o seu.

### D-005 · Isolamento também nas escolhas de campo relacional
**Contexto:** D2 fala em filtrar as queries de leitura e escrita.
**Decisão:** além do `OwnerQuerySetMixin`, existe `OwnerFormMixin`, que estreita o `queryset`
de todo campo relacional do formulário para os registros do próprio usuário.
**Motivo:** filtrar só o queryset da view deixa um buraco: num formulário de Exame, alguém
poderia enviar por POST a chave do Médico de outro usuário e criar o vínculo. Fechar isso na
camada de acesso central evita repetir a checagem em cada `ModelForm`.

### D-006 · `User` sem `first_name`/`last_name`
**Contexto:** o PRD especifica `full_name`.
**Decisão:** `AbstractBaseUser` + `PermissionsMixin` com um único campo `full_name`.
**Motivo:** herdar de `AbstractUser` traria `username`, `first_name` e `last_name`, que o PRD
não pede e que conflitam com o login por e-mail.

### D-007 · Perfil criado por signal, nunca sob demanda
**Decisão:** `post_save` em `User` cria o `Profile`; as views assumem que `user.profile`
existe.
**Motivo:** um `get_or_create` espalhado pelas views seria a alternativa, e ela repete a mesma
verificação em todo lugar. Com o signal, a garantia é única e vale para conta criada pelo
site, pelo admin e pelo `createsuperuser`.

### D-008 · Envio de e-mail no console durante o desenvolvimento
**Decisão:** `EMAIL_BACKEND` de console em `settings`.
**Motivo:** a recuperação de senha precisa funcionar de ponta a ponta desde já, e a decisão
sobre o provedor de e-mail é da Sprint 5 (lembretes). O link aparece no terminal.

### D-009 · Anexos de exame fora do `MEDIA_URL` público
**Contexto:** D12 trata dado de saúde como sensível.
**Decisão:** `MEDIA_URL` só é servido pelo Django com `DEBUG=True`. A Sprint 2, ao criar o
`Exam.attachment`, deve entregar o arquivo por uma view autenticada que confere o dono.
**Motivo:** laudo servido por URL direta vaza para qualquer um que descubra o caminho, sem
passar por autenticação nenhuma.

### D-010 · Design system replicado por classes utilitárias, não por CSS próprio
**Decisão:** os templates usam as mesmas classes Tailwind do `design_system/design-system.html`
(Tailwind por CDN, Inter, Lucide), sem nenhuma folha de estilo nova.
**Motivo:** D9 proíbe inventar estilo fora do design system. Reaproveitar as classes exatas
mantém a paleta, os raios e o motion idênticos à referência.

### D-011 · Painéis das três áreas visíveis e marcados como pendentes
**Contexto:** o guardrail proíbe placeholder em funcionalidade central do step atual.
**Decisão:** o Dashboard já traz a estrutura das três áreas, cada painel dizendo que entra na
próxima entrega. Nenhum link aponta para rota inexistente.
**Motivo:** as áreas são das Sprints 2 a 4, não da 1. A casca do Dashboard é entrega da
Sprint 1 e está completa; o conteúdo chega com as apps.

---

## Sprint 2 — Saúde

### D-012 · CBVs genéricas de dono em `core/views.py`
**Decisão:** `OwnerListView`, `OwnerDetailView`, `OwnerCreateView`, `OwnerUpdateView`,
`OwnerDeleteView` combinando os mixins de `core/mixins.py` com as generic views do Django.
`saude` e as apps seguintes herdam delas em vez de montar os mixins toda vez.
**Motivo:** D6 pede recursos nativos do Django; repetir `OwnerQuerySetMixin, OwnerFormMixin,
CreateView` em toda view de todo app é o tipo de repetição que o framework existe para evitar.
Uma base errada corrigida uma vez corrige todas as views que dela herdam.

### D-013 · Laudo servido por view autenticada, nome de arquivo aleatório
**Contexto:** D12 exige anexo de exame com acesso restrito ao dono.
**Decisão:** `Exam.attachment` grava em `exams/<user_id>/<uuid4>.<ext>` (nome original
descartado); `ExamAttachmentView` confere `user=request.user` antes de abrir o arquivo, e
devolve 404 — nunca 403 — para exame de outra pessoa ou inexistente.
**Motivo:** nome original de laudo costuma trazer o tipo de exame ou até o nome do paciente
no arquivo; manter isso no `MEDIA_ROOT` seria expor informação sensível pelo próprio nome do
caminho. O 404 uniforme evita que a resposta confirme se aquele id existe.

### D-014 · Validação de anexo: extensão e tamanho, não conteúdo
**Decisão:** `core/validators.py` aceita PDF/JPG/PNG até 10 MB, checando extensão e
`value.size`. Não inspeciona o conteúdo do arquivo (magic bytes).
**Motivo:** suficiente para o objetivo declarado (D12: "validar tipo e tamanho"). Sniffing de
conteúdo é trabalho de uma camada de antivírus/verificação de upload, fora do escopo desta
sprint — decisão de baixo impacto, reversível a qualquer momento.

### D-015 · `ExamForm` corrige o status sozinho quando `done_date` é preenchida
**Decisão:** se a pessoa registra `done_date` sem trocar o status manualmente, o form ajusta
`status` para `done` no `clean()`.
**Motivo:** o PRD (6.2) já prevê a regra "ao salvar `Exam.done_date`… gerar lembrete de
exame"; um exame com data de realização e status "solicitado" é inconsistência que o form
pode evitar sem pedir passo extra à pessoa.

### D-016 · `schedule_times` como texto livre "HH:MM, HH:MM", não formset
**Contexto:** o PRD deixa em aberto como capturar os horários de `Medication`.
**Decisão:** um `CharField` que converte para lista de strings validadas, em vez de um
formset com um sub-form por horário.
**Motivo:** decisão de baixo impacto. Um formset pede JS de add/remove linha para ser
confortável — trabalho de UI desproporcional para "digite os horários da receita". Texto
livre resolve em uma linha e already valida formato antes de salvar.

### D-017 · `Doctor`/`Treatment` apagados com `SET_NULL`, não `CASCADE`, nas FKs de outros models
**Decisão:** `Exam.doctor`, `Exam.treatment`, `Appointment.treatment`, `Medication.treatment`
usam `on_delete=models.SET_NULL` (campo `null=True`). Só `Appointment.doctor` é `CASCADE`.
**Motivo:** apagar um médico não deveria apagar o exame que ele solicitou — o registro de
saúde é o que importa, o vínculo é metadado. `Appointment.doctor` é `CASCADE` porque uma
consulta sem médico nenhum não faz sentido como registro.

---

## Sprint 3 — Treino

### D-018 · `SetLog` por série, não campos fixos em `SessionEntry`
**Contexto:** o PRD (7.1) marcou explicitamente como decisão em aberto: campo único
`reps`/`weight` em `SessionEntry`, ou um model `SetLog` por série individual — "decidir na
Sprint de Treino".
**Decisão:** `SetLog` por série (`set_number`, `reps`, `weight`), ligado a `SessionEntry` por
FK. `SessionEntry` guarda só o que é comum ao exercício inteiro (descanso, observação).
**Motivo:** o próprio PRD já apontava a razão — "viabiliza a evolução de carga fina". Uma
pirâmide ou um drop-set têm carga diferente por série; achatar isso num `weight` único do
`SessionEntry` obrigaria a escolher uma média ou o último valor, e o gráfico de evolução
(7.2) perderia precisão exatamente no dado que o torna útil.

### D-019 · Models aninhados também ganham `user` direto, redundante com o pai
**Contexto:** `RoutineDay`, `RoutineExerciseTarget`, `SessionEntry`, `SetLog` são sempre
alcançados por um pai já pertencente ao dono (`routine`, `routine_day`, `session`, `entry`).
**Decisão:** mesmo assim, todos herdam `OwnedModel` e carregam `user` próprio.
**Motivo:** dois motivos, um de cada lado da stack. (1) Segurança: `OwnerFormMixin`
(`core/mixins.py`) só filtra o `queryset` de um campo relacional se o model de destino tiver
coluna `user` — sem ela, o combo de exercícios de `RoutineExerciseTargetForm`, por exemplo,
listaria os exercícios de todo mundo. (2) Literal: a diretiva D2 do XML exige FK de dono em
"todo model que armazena dado de usuário", sem exceção para model filho. Mesmo padrão que
`_legado_vida` usava em `Resultado.paciente` (redundante com `coleta.paciente` de propósito).

### D-020 · `ChildCreateView` em `core/views.py`, generalizando o padrão de recurso aninhado
**Decisão:** base nova ao lado de `OwnerCreateView`: recebe `parent_model`/`parent_field` do
subclasse, resolve o pai pela URL **re-filtrado por `user=request.user`** a cada request, e
carimba a FK do pai no `form_valid` antes do carimbo de dono. Usada por
`RoutineDayCreateView`, `RoutineExerciseTargetCreateView`, `SessionEntryCreateView`,
`SetLogCreateView`.
**Motivo:** sem isso, cada view aninhada reimplementaria "pegue o pai pela URL, confira que é
do usuário, senão 404" na mão — e esquecer o filtro de dono no pai seria a mesma classe de
furo que motivou `OwnerFormMixin` na Sprint 1. `treino/nutricao` seguem herdando dela sempre
que um recurso pertence a outro (refeição → dieta, item → refeição).

### D-021 · `Exercise.muscle_group`, `RoutineExerciseTarget.exercise` e `SessionEntry.exercise`: `CASCADE`, não `PROTECT`
**Contexto:** a primeira versão usava `PROTECT` nessas três FKs — parecia a escolha óbvia
para "não perder histórico de treino por acidente". Bug real, pego pelo teste de exclusão em
cascata: apagar um `MuscleGroup` com exercício vinculado (ou um usuário, via
`User.objects.filter(...).delete()`) estourava `ProtectedError`/erro 500. Causa: o
`Collector` do Django avalia `PROTECT` por FK isolada — não sabe que a linha "protegida"
(`Exercise`, `SessionEntry`) está sendo apagada na mesma operação por outro caminho
(`user` → `CASCADE`). `PROTECT` entre dois models do mesmo dono trava a própria cascata do
dono, sempre, mesmo quando tecnicamente não deveria.
**Decisão:** as três viraram `CASCADE`. `OwnerDeleteView` (`core/views.py`) ganhou um
`delete_warning` opcional — texto mostrado na tela de confirmação quando a exclusão arrasta
histórico junto — e um `try/except ProtectedError` que nunca mais deveria disparar aqui, mas
protege qualquer `PROTECT` futuro contra um 500 cru.
**Motivo:** `PROTECT` faz sentido para proteger **catálogo compartilhado** de uma exclusão
que afetaria outra pessoa — é o que `saude` faz com `Resultado.tipo` → `TipoExame` (no
legado) e o que esta app não tem: `MuscleGroup`/`Exercise` são dados de uma pessoa só. Regra
geral daqui pra frente: **nunca `PROTECT` entre dois models que pertencem ao mesmo dono** —
isso quebra a exclusão de conta (LGPD, Sprint 6) de um jeito que só aparece em teste de
ponta a ponta, não em `manage.py check`.

---

## Sprint 4 — Nutrição

### D-022 · Macros calculados sempre em runtime, nunca guardados em `MealItem`/`DailyLog`
**Contexto:** o PRD (8.2) define o cálculo como `item.food.macros × quantity / portion_base`,
mas não diz se o resultado é persistido.
**Decisão:** `MealItem.macros` e `DailyLog.macros` são `@property`, recalculadas a cada
acesso a partir de `Food` e `quantity_g`. Nada de `calories`/`protein_g` gravado na linha do
item ou do registro.
**Motivo:** `Food` é dado do próprio usuário (não catálogo global), editável a qualquer
momento — se `MealItem` guardasse macro congelado, editar um alimento depois de já usado em
três refeições deixaria os totais dessincronizados sem nenhum sinal de que isso aconteceu.
Diferente de `saude.Resultado.faixa`, que **precisa** congelar (é laudo histórico: mudar o
catálogo não pode reescrever o passado) — aqui é o oposto, o item aponta pro alimento vivo.

### D-023 · `Profile.target_weight_kg` novo, para viabilizar a "linha de meta" do gráfico
**Contexto:** o PRD (8.2) pede "gráfico temporal de `WeightLog` + linha de meta", mas nenhum
model do PRD tem campo de peso-alvo — nem `WeightLog`, nem `Diet`, nem `Profile` original.
**Decisão:** baixo impacto, decidido e registrado: campo novo `target_weight_kg` em
`accounts.Profile` (mesma migração de perfil que já guarda altura, sexo, nascimento).
Opcional — em branco, o gráfico mostra só a curva real, sem a linha tracejada.
**Motivo:** meta de peso é dado da pessoa, não da dieta (ela pode trocar de dieta sem mudar
onde quer chegar) nem de um registro pontual de peso — `Profile` é o único lugar que já reúne
"dado biométrico estável da pessoa" (altura está lá pelo mesmo motivo).

### D-024 · Sugestão de TMB/GET (Mifflin-St Jeor) implementada, mas nunca grava por cima da meta
**Contexto:** PRD 8.2 marca como "(Opcional) cálculo de TMB/GET... para sugerir meta
calórica".
**Decisão:** `nutricao.models.estimate_daily_calories()` calcula BMR de Mifflin-St Jeor ×
fator de atividade leve (1.375) × ajuste por objetivo da dieta (-15% emagrecimento / +15%
ganho), usando `Profile` (nascimento, sexo, altura) + o `WeightLog` mais recente. Mostrado
como texto informativo na página da dieta — `daily_calorie_target` continua um campo comum
que a pessoa preenche e edita como quiser, a sugestão nunca sobrescreve.
**Motivo:** é estimativa, não prescrição — a linha do README ("o sistema registra, não
interpreta") vale aqui também. Retorna `None` sem quebrar nada quando faltam dados (perfil
incompleto, nenhum peso registrado).

### D-025 · Seed de tabela TACO (alimentos de referência) não implementado nesta sprint
**Contexto:** PRD 8.1 sugere "pré-carregar referência tipo tabela TACO como seed opcional".
**Decisão:** não implementado. `Food` funciona via CRUD normal — a pessoa cadastra os
próprios alimentos, testado de ponta a ponta.
**Motivo:** o próprio PRD marca como opcional. Importar a TACO direito (centenas de itens,
valores por 100g conferidos) é trabalho de fonte de dados, não de código — melhor como
`management command` dedicado quando houver um dataset confiável à mão, e assim não arrisca
poluir o banco de cada usuário com um seed malfeito. Documentado aqui para não se perder.

### D-026 · `DailyLog` sem `Meal` como pai, filtro por `?data=` em vez de paginação
**Contexto:** o PRD já separa: `Meal`/`MealItem` são o *plano* (dieta), `DailyLog` é o que
*aconteceu de fato* — independentes um do outro, `DailyLog.meal_name` é texto livre.
**Decisão:** `DailyLogListView` não herda de `OwnerListView`/`ListView` — é uma `TemplateView`
que lê `?data=YYYY-MM-DD` (hoje por padrão) e mostra o dia inteiro de uma vez, com os totais
contra a dieta ativa logo ao lado.
**Motivo:** um registro diário se lê por dia, não por página de 20 em 20 — paginação cortaria
o almoço de terça no meio da lista e escantearia o comparativo com a meta, que é o motivo de
a tela existir. Consistente com o padrão de `treino`: filtro nativo do Django (`?data=`, sem
JS) em vez de reinventar seletor de data.

---

## Sprint 5 — Lembretes + Dashboard

### D-027 · Sem lembrete automático de "treino do dia"
**Contexto:** o PRD (9.1) lista "Treino do dia" entre os cinco gatilhos que a central
consolida.
**Decisão:** as outras quatro categorias (remédio, exame, retorno, refeição) têm uma fonte de
horário real para nascer: `Medication.schedule_times`, `Exam.scheduled_date`,
`Appointment.next_return_date`, `Meal.time`. Treino não tem — `RoutineDay` não carrega dia da
semana nem horário nenhum (o PRD tampouco pediu isso na seção 7). Sem uma fonte, não há o que
sincronizar automaticamente; a categoria `treino` existe em `Reminder.Category` e a pessoa
pode criar um lembrete manual dessa categoria à mão.
**Motivo:** inventar um agendamento de dias de treino que o PRD nunca pediu (ex.: "toda
segunda é Push") seria adicionar escopo não pedido para preencher uma lacuna que a própria
central não exige — a pessoa já vê "sessões desta semana" ao vivo no painel de treino e no
dashboard (Sprint 3), o que cobre a necessidade sem inventar modelo novo.

### D-028 · Canal de envio: só e-mail, mesmo com `Profile.notification_channel` aceitando mais opções
**Contexto:** PRD 9.3 recomenda e-mail para v1, WhatsApp como plugin da fase 2. O campo
`notification_channel` (criado na Sprint 1) já tem as três opções no `TextChoices`.
**Decisão:** `send_due_reminders` despacha por e-mail para todo mundo, sem olhar o valor de
`notification_channel`. O campo continua existindo e editável — é preferência declarada da
pessoa para quando os outros canais existirem — mas nada lê esse valor para decidir a rota de
envio ainda.
**Motivo:** implementar WhatsApp/push exigiria integração externa (Evolution API, Web Push)
que o PRD explicitamente empurra pra fase 2. Fingir suportar canais que não despacham nada
seria pior que não oferecer — por isso o comando não checa o campo, e esta decisão fica
registrada para quem for religar o WhatsApp depois saber onde entrar.

### D-029 · `sync_reminders`: apaga-e-recria os lembretes derivados pendentes na janela, nunca "upsert" incremental
**Contexto:** um lembrete derivado (remédio, exame, retorno, refeição) muda de horário toda
vez que a fonte muda — o médico remarca o retorno, a pessoa edita o horário do remédio.
**Decisão:** a cada chamada, `sync_reminders` apaga todo `Reminder` do usuário com
`status=pendente`, `content_type` preenchido (ou seja, derivado, não manual) e `remind_at`
dentro da janela de 7 dias — e recria do zero a partir do estado atual de `Medication`,
`Exam`, `Appointment` e `Diet`/`Meal`. Lembrete manual (`content_type` nulo) e lembrete já
`enviado`/`concluído`/`cancelado` nunca são tocados.
**Motivo:** um `get_or_create` chaveado por `(user, categoria, origem, remind_at)` pareceria
mais "cirúrgico", mas deixaria lembrete órfão pra trás sempre que a fonte muda de horário — o
retorno remarcado geraria um lembrete novo E manteria o antigo, pendente, apontando pra uma
data que não existe mais no registro de origem. Apagar e recriar garante que a lista sempre
reflete o estado atual dos dados, e é barato o bastante (dezenas de linhas, não milhares) pra
rodar a cada visita à central, não só no cron.

### D-030 · Central resincroniza a cada visita, comando de cron sincroniza + envia
**Contexto:** PRD 9.3 pede um `management command` agendado via cron para o MVP.
**Decisão:** `sync_reminders(user)` roda tanto dentro de `ReminderIndexView.get_context_data`
(só pro usuário logado, a cada carregamento da página) quanto dentro de
`send_due_reminders` (pra todo mundo, de uma vez, antes de checar o que venceu).
**Motivo:** sem isso, a central ficaria vazia ou desatualizada em ambiente de desenvolvimento
(sem cron rodando) — cadastrar um remédio novo e abrir a central tem que mostrar o lembrete
na hora, não só depois do próximo tick do cron. Resincronizar por usuário na visita é barato;
o comando existe pra cobrir todo mundo de uma vez e de fato enviar o e-mail, que a página não
faz.

---

## Sprint 6 — SaaS (billing)

### D-031 · Gateway: Mercado Pago, seguindo a recomendação explícita do PRD
**Contexto:** PRD 10.3 marca `⚠️` mas já recomenda: "Mercado Pago com Pix + cartão" pro
público brasileiro.
**Decisão:** `MercadoPagoGateway` como única implementação de `PaymentGateway`. Nenhuma
alternativa (Stripe) foi construída.
**Motivo:** o `ambiguity_protocol` manda seguir a recomendação registrada quando ela existe.
Existe, é explícita, e cabe ao público-alvo do produto (seção 2 do PRD: usuário final BR).

### D-032 · Preço do Premium: R$ 29,90/mês, placeholder documentado, vive no banco
**Contexto:** PRD 10.2 marca preço do Premium como "⚠️ definir", sem recomendação em lugar
nenhum do documento — ao contrário do gateway, aqui não há decisão a seguir, só a decidir.
**Decisão:** R$ 29,90/mês, semeado por migração de dados (`billing/migrations/0002_seed_plans.py`),
não hardcoded em código nenhum. Trocar o preço é editar a linha do `Plan` no admin — zero
deploy, zero migração nova.
**Motivo:** decisão de baixo impacto pelo `ambiguity_protocol` — "escolha a opção mais
simples e reversível e documente o motivo". Preço de SaaS pessoal de saúde/treino/nutrição no
Brasil gira nessa faixa (comparáveis de app de hábito/saúde ficam entre R$ 20–40/mês); o valor
exato é a decisão de negócio mais fácil de mudar depois de todo o PRD, porque não exige tocar
em uma linha de código — só justifica por que não travei a sprint esperando essa resposta.

### D-033 · `Plan` é o único model não-`OwnedModel` de todo o app de domínio
**Contexto:** todo model deste projeto até aqui pertence a um usuário. `Plan` é catálogo
puro — Free e Premium são as mesmas duas linhas pra todo mundo.
**Decisão:** `Plan(TimeStampedModel)`, sem FK de dono, sem `OwnerQuerySetMixin` em view
nenhuma que o leia (é lido livre, tipo `saude.Laboratorio` seria se este build tivesse
catálogo — este é o primeiro caso real).
**Motivo:** um `Plan` "do usuário X" não faz sentido — outro usuário não pode "ver o plano
Premium de outra pessoa" porque não há dado nenhum ali que pertença a alguém; o preço e os
limites são públicos por natureza (aparecem até na landing page, sem login). Forçar
`OwnedModel` aqui seria contorcer o padrão pra um caso que não é dele.

### D-034 · `Subscription.plan` é `PROTECT` — o primeiro `PROTECT` legítimo do projeto
**Contexto:** D-021 (Sprint 3) baniu `PROTECT` entre models do mesmo dono, depois de um bug
real (exclusão em cascata travando com `ProtectedError`).
**Decisão:** `Subscription.plan` usa `PROTECT` mesmo assim.
**Motivo:** esta FK não é entre dois models do mesmo dono — `Plan` não pertence a ninguém.
A cascata de exclusão de um `User` passa por `Subscription` (que É do dono, `CASCADE`) e
para; ela nunca precisa atravessar `Plan` pra terminar. `PROTECT` aqui bloqueia exatamente o
que deveria: apagar um plano com assinantes ativos pelo admin. É a mesma distinção que
`saude` faria com um catálogo global (`TipoExame` no `_legado_vida`) — a regra de D-021 é
"nunca entre dois do mesmo dono", não "nunca `PROTECT`".

### D-035 · Constraint de assinatura corrente é por usuário, não por usuário+plano
**Contexto:** achado testando, não planejado: `SubscribeView` tentava criar uma `Subscription`
trial nova pro Premium sem fechar a `Subscription` Free ainda `active` da mesma pessoa — a
`UniqueConstraint` (`fields=['user']`, `condition=status in trial/active/past_due`) rejeitou
com `IntegrityError`, porque ela permite **uma linha aberta por usuário**, não uma por
usuário-e-plano.
**Decisão:** `SubscribeView` fecha (`status = cancelled`) qualquer assinatura aberta da
pessoa antes de abrir uma nova trial — mesmo padrão que a troca gratuita já fazia. Reaproveita
uma trial pendente do mesmo plano em vez de duplicar (retry de checkout sem gerar lixo).
**Motivo:** é a leitura certa de "uma assinatura corrente" — a pessoa está num plano de cada
vez, nunca em dois simultaneamente, então trocar de plano sempre fecha o anterior primeiro.
Pego pelo mesmo hábito que salvou a Sprint 3 e a Sprint 4: rodar o fluxo de ponta a ponta de
verdade antes de dar por encerrado, não só `manage.py check`.

### D-036 · Gate de plano: dieta ativa e lembrete automático, não IA (ainda não existe)
**Contexto:** PRD 10.2 lista três diferenças Free × Premium: "1 dieta ativa" / "sem lembretes
automáticos" / "sem IA".
**Decisão:** os dois primeiros ganharam gate de verdade — `billing/gating.py`,
`diet_limit_exceeded()` em `nutricao.views.DietPlanLimitMixin`, `auto_reminders_enabled()`
dentro do próprio `lembretes.services.sync_reminders()` (Free limpa os derivados em vez de
gerar). "Sem IA" não tem código nenhum: não existe camada de IA neste build — é fase 7 do
roadmap (recomendação do PRD, item 4 da seção 16) — então a restrição já vale por
inexistência, não por gate.
**Motivo:** gatear algo que não existe seria código morto. Quando a S7 (IA) nascer, o gate
natural é checar `limit_for(user, 'ai_enabled')` no ponto de entrada da funcionalidade — a
chave já está semeada em `Plan.limits` (`False` no Free, `False` no Premium também, porque a
IA nem começou a existir) esperando por isso.

### D-037 · "Ativar sem cobrança" só com `DEBUG=True`, rotulado como ambiente de teste
**Contexto:** não há conta de vendedor Mercado Pago de verdade nem access token neste
ambiente — sem eles, o checkout genuíno nunca roda de ponta a ponta aqui.
**Decisão:** `DevActivateSubscriptionView` marca a assinatura trial pendente como ativa sem
passar pelo gateway, mas só responde quando `settings.DEBUG` é `True`; a UI rotula o botão
como `[Teste]` e a mensagem de sucesso deixa claro que não houve cobrança real.
**Motivo:** sem isso, o fluxo de assinatura paga simplesmente não seria testável nem
demonstrável neste ambiente — mas fingir que um clique qualquer "paga de verdade" seria
enganoso. `DEBUG=False` desliga a view inteira (retorna 405 mesmo com o POST certo), então
não sobrevive a um deploy de produção por acidente.

---

## Pós-S6 — Pass de acessibilidade e hierarquia (crítica do impeccable)

### D-038 · A ação primária do dashboard é "Registrar treino"
**Contexto:** o painel abria com seis atalhos de peso visual igual (P1 #3 da crítica do
impeccable em `.impeccable/critique/`). Era preciso eleger *uma* próxima ação dominante. Os
dois fluxos diários candidatos são "Registrar treino" (`treino:session_create`) e "Registrar
refeição" (`nutricao:dailylog_create`).
**Decisão:** "Registrar treino" recebe o tratamento de botão primário do design system (olive,
`arrow-right` que desliza no hover); "Registrar refeição" fica como botão outline secundário
ao lado; os demais registros (exame, consulta, medicamento, peso) continuam sob o disclosure
"Mais registros". Os três cards de área (Saúde/Treino/Nutrição), o bloco de lembretes e o de
perfil foram rebaixados a peso visual secundário (heading menor, menos padding, link de texto
em vez de botão, sem cor de preenchimento).
**Motivo:** mantém a ordem que já existia no template e não mexe na lógica de contexto da
view. Se o dono do produto preferir nutrição como âncora diária (ou alternância por
horário/uso), basta trocar as duas classes de botão — a estrutura já suporta.

### D-039 · Landing sem canal de suporte declarado
**Contexto:** a crítica do impeccable (P1 #4) pede informação de suporte visível na landing
para um produto de dados de saúde. Não existe e-mail de suporte, página de ajuda nem
formulário de contato no sistema; `EMAIL_BACKEND` é console em dev e
`MERCADOPAGO_ACCESS_TOKEN` não está configurado. Também não há exportação nem exclusão de
conta (nada em `accounts/`), então portabilidade de dados não pode ser prometida.
**Decisão:** não adicionar afordância de suporte à landing nem ao rodapé, e não citar
exportação/portabilidade, até o dono do produto definir um canal real e a S6/S7 entregar
exclusão+exportação (LGPD). O rodapé e a nova seção "Privacidade faz parte do produto"
afirmam só o que é verificável hoje: isolamento por dono (`OwnerQuerySetMixin`), anexos por
rota autenticada (`ExamAttachmentView`), 404 em vez de 403 para registro de terceiro, e o
disclaimer médico.
**Motivo:** um canal de suporte falso ou uma promessa de portabilidade inexistente numa
página que pede confiança com exames e medicação é pior que a ausência. Claims absolutas do
texto antigo ("Nada esquecido", "chega antes da hora", "evolução inteira") foram trocadas por
afirmações defensáveis ("Lembrete com antecedência", "com dias de antecedência", "evolução
registrada").

---

## Deploy em produção (EasyPanel)

### D-040 · Produção usa Docker + Postgres; o D10 valeu só para a fase de construção
**Contexto:** o `PROMPT-EXEC-vitalis.xml` proíbe Docker e Postgres — D10 (`MUST_NOT`, linha
79), guardrail da linha 181, DoD da linha 175 ("apenas SQLite"). O dono do produto pediu
deploy na VPS dele (EasyPanel, `161.97.69.249`), que builda por Dockerfile e não serve
SQLite com segurança em container.
**Decisão:** adicionar `Dockerfile`, `entrypoint.sh` (gunicorn), WhiteNoise para o estático e
suporte a Postgres via `DATABASE_URL` (`dj-database-url`). **O desenvolvimento continua
idêntico:** sem `DATABASE_URL`, `config/settings.py` cai no SQLite de sempre; ninguém precisa
de Docker para rodar local. O switch é uma única variável de ambiente. Anexos de exame moram
num volume persistente montado em `/app/media` (dado sensível, LGPD — não pode sumir num
redeploy).
**Motivo:** o D10 era uma diretiva da fase de MVP, para não afogar a construção em
infraestrutura. Publicar o produto é outra fase e o dono decidiu explicitamente — o que o
`ambiguity_protocol` manda registrar aqui. A regra continua valendo para o dia a dia de
código: ninguém adiciona Postgres/Docker ao fluxo local.

### D-041 · Dados médicos reais entram por `seed_medico` + JSON fora do git
**Contexto:** o dono pediu a ingestão do dossiê de saúde dele (`RESUMO-SAUDE.md` + PDFs) na
conta `elvertoni@gmail.com`. Esses dados — diagnósticos, medicação, resultados de exame — são
dado sensível de saúde e não podem virar literal de código num repositório, nem mesmo
privado.
**Decisão:** o comando `core/management/commands/seed_medico.py` é **genérico e vazio de
dados** — lê tudo de um `--source` JSON. O JSON com dados reais (`medico-seed.json` /
`medico-data/`) está no `.gitignore` e no `.dockerignore`; só o `medico-seed.example.json`
(estrutura, sem dados) é versionado. Em produção o JSON é entregue ao container por
`exec_in_container` (base64), o comando roda, e o arquivo é apagado do disco em seguida. Os
PDFs de laudo sobem pela UI real (form validado por `validate_attachment`), nunca por commit.
O comando é idempotente (`update_or_create` por campo natural): rodar de novo corrige em vez
de duplicar.
**Motivo:** o dossiê de uma pessoa não tem por que estar no histórico do git de todo mundo
que clonar o repo. Manter o comando separado dos dados também o deixa reutilizável para
qualquer usuário futuro que queira importar um histórico.

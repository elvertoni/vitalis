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

### D-042 · Retorno gera dois lembretes: um para **marcar** (D-15) e o do dia
**Contexto:** `Appointment.next_return_date` já virava lembrete, mas só na data do retorno.
No dia não adianta: consultório de especialista costuma estar com a agenda cheia semanas
antes, e o aviso chegava quando não havia mais o que fazer.
**Decisão:** a mesma data passa a gerar duas linhas em `lembretes`:
`_appointment_reminders` (o retorno em si, no dia, como já era) e o novo
`_return_scheduling_reminders`, `RETURN_SCHEDULING_LEAD_DAYS = 15` dias antes, com o título
"Agendar retorno · <médico>". Nenhum campo novo: a constante vive em `saude/models.py` — a
consulta precisa dela para mostrar a data na tela, e `saude` não pode importar `lembretes`
(a dependência corre no sentido contrário).
**Motivo secundário — como o sistema sabe que já agendou:** não sabe, e não vale um campo
"já marquei" que a pessoa teria de manter na mão. O sinal é o próprio uso: só a **última
consulta de cada médico** gera a cobrança de agendamento (`Appointment.return_is_booked`).
Registrou a consulta nova com aquele médico, o aviso da anterior some sozinho.
**Motivo da janela estrita:** o aviso só é criado quando o dia D-15 cai dentro da janela do
sync (`LOOKAHEAD_DAYS`), como todo lembrete derivado. Recriar avisos com data no passado
duplicaria linha a cada visita, porque o apaga-e-recria do D-029 só limpa a janela de hoje
para a frente. Com o `send_due_reminders` diário (D-030) nada se perde; sem nenhuma
sincronização por vários dias seguidos, um aviso pode passar batido — troca aceita em favor
de não encher a central de cobranças repetidas.
**Consequência de plano:** como todo lembrete derivado, este é bloqueado no Free pelo gate do
D-036 (`auto_reminders_enabled`). No Free a data do retorno continua registrada e visível na
consulta e no hub de saúde, mas nenhum dos dois lembretes é gerado.

### D-043 · O apaga-e-recria não pode ressuscitar lembrete já resolvido
**Contexto:** com o SMTP real ligado e o agendador (`SERVICE_MODE=cron`) rodando a cada 15
minutos, os mesmos quatro lembretes da manhã chegaram duas vezes por e-mail em produção, com
seis minutos de diferença. O defeito é do D-029, não do agendador: o wipe do `sync_reminders`
apaga só os derivados **pendentes** da janela, mas a linha que saiu desse estado (enviada,
concluída, cancelada) permanece na tabela — e o gerador, que é determinístico, recria a dose
das 07:00 de hoje do zero. A cópia nova nasce pendente e vencida, o `send_due_reminders`
manda de novo, e o ciclo se repete a cada execução até a meia-noite. O mesmo valia para um
lembrete que a pessoa concluísse na mão: voltava no sync seguinte.
**Decisão:** `_drop_already_handled` filtra o lote antes do `bulk_create`, descartando todo
derivado cuja chave já exista na janela em estado diferente de pendente. A chave é
`(content_type_id, object_id, remind_at)` — a origem mais o instante exato, que é o que os
geradores derivam de forma determinística dos dados de domínio.
**Motivo de não ter mudado o wipe:** apagar também as linhas enviadas resolveria a duplicação
e destruiria o histórico de envio junto — é o registro de que aquele aviso chegou. Manter o
wipe restrito ao pendente e filtrar na recriação preserva as duas coisas.
**Motivo de a chave incluir o horário:** o mesmo remédio gera uma linha por dose por dia.
Deduplicar só por origem calaria as doses seguintes.
**Nota de operação:** o `entrypoint.sh` deixou de rodar `migrate` no modo cron. Quem aplica
migration é o serviço web, sozinho; dois containers subindo o schema ao mesmo tempo num
deploy é corrida sem ganho nenhum.

### D-044 · Só o que ainda não tem data marcada vira e-mail
**Contexto:** com o envio real ligado, a caixa do dono recebia ~11 mensagens por dia — uma por
dose de remédio e uma por refeição da dieta ativa. Ele pediu que o e-mail passasse a ser
"não se esqueça de agendar sua próxima consulta / o exame de sangue / o retorno".
**Decisão:** nasce a categoria `Reminder.Category.SCHEDULING` ('agendar'), e
`lembretes.notifications.NOTIFY_CATEGORIES` — hoje só ela — define o que sai do sistema. Dose
de remédio e refeição continuam sendo geradas e continuam na central e no painel; apenas não
viram mensagem. Três geradores alimentam a categoria: retorno pedido pelo médico (D-042),
**exame solicitado que ninguém marcou** e **tratamento em andamento sem nada agendado**.
**Motivo:** remédio e refeição são rotina que a pessoa já vive; o valor do aviso é baixo e o
custo é alto — onze e-mails por dia treinam qualquer um a ignorar o remetente, e aí o aviso
que importa (algo sem data marcada, que exige ligar para um consultório) se perde no meio.
Notificação só se paga quando pede uma ação que não aconteceria sozinha.
**O buraco que isso fechou:** `_exam_reminders` só cobria exame **com** data marcada. O pedido
de exame que nunca foi agendado — o caso mais fácil de esquecer — não gerava nada. Agora
`_exam_scheduling_reminders` cobra 3 dias depois da solicitação e repete semanalmente por até
8 semanas enquanto o exame seguir sem data; depois disso a solicitação é velha, não urgente.
**Ritmo do "próxima consulta":** `_treatment_checkup_reminders` só dispara com o tratamento
aberto, sem consulta futura e sem retorno pendente — os dois já têm aviso próprio. A cadência
é ancorada na última consulta daquele tratamento (a cada 30 dias), não em "quando o sync
rodou", para o dia do aviso ser previsível.
**Canal:** `notifications.send_reminder` é o único ponto que conhece o meio de entrega. O
WhatsApp via Evolution API (que `Profile.notification_channel` promete desde a Sprint 5,
D-028) entra ali, sem o comando despachante saber da diferença.

### D-045 · WhatsApp pela Evolution API, em instância própria do Vitalis
**Contexto:** `Profile.notification_channel` oferece WhatsApp desde a Sprint 5, mas nada
despachava (D-028) — a central chegou a exibir "Lembretes por WhatsApp" para um perfil que só
recebia e-mail. O dono já opera uma Evolution API na mesma VPS (`evoapi.tonicoimbra.com`),
usada pelo agenda-med e por outros projetos.
**Decisão:** usar esse gateway, mas numa **instância separada chamada `vitalis`**, com a
apikey própria que a Evolution devolve na criação — não a chave global do painel, que abre
todas as instâncias. O cliente é `lembretes/whatsapp.py`: `urllib` puro, um endpoint
(`/message/sendText/{instance}`), sem SDK nova, no mesmo estilo de `billing/services.py`.
**Motivo da instância separada:** a instância `CLINICA` atende pacientes de um consultório.
Aviso pessoal de saúde saindo da mesma sessão de WhatsApp mistura dois contextos que não têm
nada a ver, e um número que cai leva o outro junto. Sessões separadas falham separadamente.
**Motivo do fallback:** `notifications.send_reminder` tenta o WhatsApp só quando a pessoa o
escolheu, o gateway está configurado e há telefone no perfil; qualquer falha de rede ou
recusa do gateway cai para e-mail, com `logger.warning`. Um aviso que chega pelo canal
errado vale muito mais que um aviso que não chega — e a instância do WhatsApp é a peça mais
frágil de toda a cadeia, porque depende de uma sessão que pode ser desconectada do celular.
**Telefone:** `whatsapp.normalize_phone` aceita o que a pessoa digitou (`(41) 99115-8701`) e
devolve `5541991158701`; número sem DDD é recusado, e o envio cai para e-mail em vez de
entregar no vazio.

### D-046 · O painel de pareamento do WhatsApp é de quem administra, não do usuário
**Contexto:** o dono pediu "um painel na própria área do usuário para conectar o WhatsApp".
Ao implementar, a base já tinha **duas** contas.
**Decisão:** o painel (`/lembretes/whatsapp/`) exige `is_staff` e responde **404** — não 403 —
para quem não é, seguindo a mesma escolha do isolamento por dono: rota que a pessoa não pode
usar não se anuncia. O usuário comum continua controlando o que é dele: o telefone e o canal,
no perfil. O link para o painel também só aparece na central para staff.
**Motivo:** a instância da Evolution é o **remetente do sistema**, uma só para todas as contas
— não o WhatsApp pessoal de cada pessoa. Desconectar aquela sessão tira o canal de todo mundo,
e um QR de pareamento na tela é, literalmente, acesso à sessão de WhatsApp: quem escaneia
passa a enviar como o Vitalis. Isso é operação de instalação, não preferência de conta.
**Sobre o QR:** é pedido ao gateway a cada carregamento em vez de guardado, porque cada
código vive menos de um minuto — QR velho é beco sem saída para quem está com o celular na
mão. Enquanto ele está exposto, a página consulta `/lembretes/whatsapp/estado/` a cada 5s e
se recarrega sozinha quando o pareamento conclui.
**Achado de infraestrutura:** o Cloudflare na frente de `evoapi.tonicoimbra.com` devolve
403 (`error code: 1010`) para o User-Agent padrão do `urllib` — o cliente agora se identifica
como `Vitalis/1.0`. Em produção a chamada nem sai para a internet: `EVOLUTION_API_URL` aponta
para `http://work_evolution-api:8080`, a rede interna do EasyPanel, o que também evita expor
conteúdo de lembrete de saúde ao CDN.

### D-047 · "Peso atual" é campo do formulário de perfil, não coluna do `Profile`
**Contexto:** duas pessoas — o dono e o segundo usuário da instalação — preencheram o perfil
inteiro (nascimento, sexo, altura, **peso alvo**, telefone) e ficaram com **zero pesagens**.
As duas procuraram o peso atual no perfil, acharam só a meta e pararem por aí. O caminho real
(Nutrição → Peso → novo) existia, mas nada levava até ele: o cadastro joga direto no painel e
o único acesso era um item no menu de ações rápidas.
**Decisão:** `ProfileForm` ganha `current_weight_kg`, um campo **do formulário**, posicionado
entre a altura e o peso alvo (`field_order`). Ele abre mostrando a última pesagem e, ao
salvar, faz `update_or_create` de um `WeightLog` com a data de hoje. Em branco não mexe em
nada; o mesmo valor de novo não cria linha; valor diferente no mesmo dia corrige a pesagem de
hoje, respeitando a constraint `um_peso_por_dia`.
**Motivo de não virar coluna:** peso é série histórica, e o gráfico de evolução, o IMC e a
meta calórica leem de `WeightLog`. Uma cópia em `Profile` seria a correção fácil e errada:
duas verdades sobre o mesmo número divergem em semanas — a mesma razão pela qual macro é
calculado e nunca congelado (D-022). O formulário é só uma porta melhor para o mesmo dado.
**Também:** a tela de perfil passa a mostrar "Peso atual" com a data da pesagem, ou um link
para registrar a primeira quando não existe nenhuma.

### D-048 · Uma tela para registrar o treino inteiro, ao lado do CRUD que já existia
**Contexto:** registrar uma sessão pelo CRUD de `treino` custa uma sessão, uma entrada por
exercício e uma série por linha — para o treino A da ficha full-body isso é **mais de trinta
formulários** com o celular na mão, entre um exercício e outro, com o intervalo correndo.
Ninguém faz isso duas vezes. O histórico de carga é a matéria-prima da progressão, então o
custo de registrar decide se o resto do app tem dado para trabalhar.
**Decisão:** `/treino/registrar/` — escolhe a divisão, e uma única tela lista os exercícios
prescritos com um par de campos (repetições, carga) por série. Um POST grava tudo.
**O CRUD continua** (`treino:session_create`, agora rotulado "Sessão avulsa"): é o caminho de
correção e o de treino que não segue ficha nenhuma. A tela nova cobre o caso semanal, não
substitui o geral.
**Fora do escopo:** editar a prescrição por ali. Mudar séries ou faixa de repetição continua
na ficha — a tela de registro escreve histórico, não altera o plano.

### D-049 · A sessão nasce na escrita, não na visita
**Contexto:** a primeira versão fazia `get_or_create` da sessão e das entradas no GET, para
ter uma `SessionEntry` estável em que pendurar as séries. Abrir a tela e desistir — conferir a
prescrição no vestiário, errar a divisão, fechar o navegador — deixava uma `WorkoutSession`
vazia que entrava em "sessões recentes" e contava na frequência da semana.
**Decisão:** o GET não escreve. Os campos do formulário são nomeados pelo **alvo**
(`t<target_pk>s<n>reps`), que existe desde a ficha, e não pela entrada. No POST o formulário
é lido inteiro antes de tocar no banco (`read_submission`); sessão e entradas nascem só se
veio número. No fim, entrada sem série é apagada, e sessão que ficou sem entrada nenhuma
também.
**Consequência:** "frequência da semana" volta a significar treino que aconteceu. Regra geral
para tela de registro: **visitar não é registrar**.

### D-050 · Descanso é prescrição (fica no alvo), manhã seguinte é coluna própria
**Descanso:** `SessionEntry.rest_seconds` já existia e guarda o descanso *praticado* naquele
dia. O cronômetro da tela precisa do descanso *prescrito*, que vale antes de a sessão
existir — por isso `RoutineExerciseTarget` ganhou seu próprio `rest_seconds`. Os dois campos
não são duplicata: um é plano, o outro é execução. O do alvo aparece no formulário da ficha,
senão exercício criado pela interface nunca arma o cronômetro.
**Manhã seguinte:** `WorkoutSession.morning_after` (`ok` / `worse`). Numa tendinopatia a dor
não aparece durante o treino, e sim no dia seguinte — a manhã seguinte é o que diz se a carga
estava certa. Vai em coluna, e não em `notes`, porque é **dado consultado**: `progression.
morning_streak` conta as semanas seguidas sem `worse`, que é o critério objetivo para
reintroduzir exercício suspenso. Texto livre não se conta.
**Progressão dupla** (`treino/progression.py`): sugere subir carga só quando **todas** as
séries prescritas bateram o topo da faixa de repetições — `top_of_range` lê `'8-12'` como 12 e
devolve `None` para prescrição em tempo (`'45s'`), que não progride por repetição. O passo é
+5 kg para grupo de perna e +2,5 kg para o resto. É sugestão no campo, nunca escrita
automática: quem decide a carga é quem levanta.

### D-051 · O menu mobile ficava dentro do `<nav>` — e por isso nunca funcionou
**Contexto:** `templates/base.html` trazia o `<nav>` do `design_system/design-system.html`
com `backdrop-blur-md`, e o `#mobile-menu` (`fixed inset-0`) **dentro** dele. `backdrop-filter`
estabelece bloco de contenção para descendentes `position: fixed`: o `inset-0` passava a medir
a barra de 96px em vez da janela. Medido com o menu aberto a 390px: Painel em y=−199, Saúde
em −102, Treino em −34 — os três acima do topo da tela — e Nutrição coberta pelo logotipo
(`z-50` contra o `z-40` do menu). **Quatro dos sete destinos não abriam ao toque**, em todo
dispositivo abaixo de 1024px, desde `f0fb235`, o commit fundador. O defeito não produz erro:
o dedo toca e nada acontece.
**Decisão:** o menu é **irmão** do `<nav>`, não filho — é a única correção que preserva o
efeito de vidro da barra, que é assinatura do Soluna. Junto: `inset-0` vira
`top-0 left-0 right-0 h-[100dvh]` (a barra de URL do Safari iOS come altura de `100vh`),
`z-40` vira `z-[60]` para passar na frente do logotipo, e o menu ganha botão de fechar
próprio em vez de trocar o ícone do hambúrguer por JS.
**Consequência de layout:** os itens deixam de ser texto centralizado de 40px de altura e
viram **linhas de largura total com 56px** (`w-full px-6 py-4 min-h-[3.5rem]`), com chevron à
direita e um ponto de acento no item de `aria-current`. Ocupar a largura inteira elimina a
mira horizontal, que é o custo real de operar com uma mão só; 56px passa os 44px do HIG e os
48px do Material. **Botão/pílula foi considerado e recusado**: no design system
`rounded-full px-8 py-5` significa *ação primária*, e transformar quatro destinos em pílula
faria a navegação competir com "Registrar treino" — além de aumentar a altura total do menu.
**Também:** `matchMedia('(min-width: 1024px)')` fecha o menu ao cruzar o breakpoint, senão
ele some por CSS mas deixa o `<body>` presa em `overflow-hidden`. E a mesma correção foi
aplicada em `design_system/design-system.html`, senão a referência seguiria ensinando o bug.

### D-052 · O hub de treino mostra a ficha ativa, não a contagem de tabelas
**Contexto:** `/treino/` abria com quatro cartões que eram, literalmente, as quatro tabelas do
app reduzidas a `.count()` — grupos, exercícios, fichas, sessões. 782px de inventário antes de
qualquer verbo, com "Registrar treino" em y=1114, além da primeira dobra. O caminho até a
ficha passava por um cartão escrito "1 Fichas ativas" — um número no lugar de um nome — sem
nenhuma afordância de clique (só `hover:shadow-xl`, que não existe em toque).
**Decisão:** o topo do hub é a **ficha ativa**: nome, divisões com a contagem de exercícios,
e o par "Registrar treino" (pílula primária) + "Ver ficha" (link). `TrainingIndexView` troca
`routine_count = ....count()` por `active_routines = list(...)`, sem migração. Os quatro
contadores viram uma linha de texto de 14px abaixo do bloco, com cada termo linkado — são
dados de manutenção de catálogo, consultados poucas vezes, não de uso semanal.
**Medido:** a ação primária sai de y=1114 para **y=458** num viewport de 844 — passa a caber
na primeira tela — e a página encolhe de 2323px para 1819px.
**Por que "Ver ficha" é link e não botão:** a hierarquia espelha a frequência real de uso —
registrar acontece 3x por semana, consultar a ficha talvez 1x por mês. Dar a ela um cartão de
178px repetiria o erro que a mudança veio corrigir.

### D-053 · Consulta marcada tem contagem regressiva própria
**Contexto:** o sistema cobria as duas pontas e deixava o meio vazio. Havia o aviso de
*marcar* o retorno (D-042, 15 dias antes) e o aviso no *dia* da consulta — mas nada entre
"já marquei" e "é hoje", que é justamente onde uma consulta é esquecida.
**Decisão:** `_appointment_countdown_reminders` gera avisos em
`APPOINTMENT_COUNTDOWN_DAYS = (6, 4, 2, 1)` antes da data da consulta. Consulta marcada é
simplesmente um `Appointment` cuja própria `date` ainda está no futuro — o registro existe
porque a pessoa marcou; não há campo de controle novo.
**Por que a véspera está fora da sequência de dois em dois:** é o aviso que faz separar
documento e sair de casa na hora, e não pode depender da paridade da contagem cair certo.
**O dia da consulta em si fica de fora** desta série: `_appointment_reminders` já fala nele,
e dois avisos para a mesma manhã é ruído.

### D-054 · O canal é escolhido por categoria, não por pessoa
**Contexto:** `Profile.notification_channel` era um valor único para tudo. Escolher WhatsApp
movia *todos* os avisos de uma vez, e por isso a resposta segura tinha sido não notificar
quase nada (D-044): o dono do produto não podia querer a dose de remédio no WhatsApp sem
querer também as onze refeições da dieta.
**Decisão:** `lembretes.ChannelPreference` — uma linha por `(user, category)` com `by_email`
e `by_whatsapp`. `notifications.channels_for(user, category)` resolve, e `should_notify` deixa
de consultar uma constante para consultar a pessoa. Tela em `/lembretes/preferencias/`.
**A ausência de linha não é "desligado"** — significa "nunca decidiu", e cai em
`DEFAULT_CHANNELS`. Isso é o que impede que salvar preferências hoje silencie para sempre uma
categoria que o produto criar amanhã.
**Padrão novo, decidido com o dono:** e-mail só para `agendar` e `retorno` — o que é data a
combinar com terceiro e exige uma ação (ligar, sair de casa). Remédio, refeição e treino não
saem por nada até a pessoa pedir. Substitui a regra fixa de D-044, mantendo o motivo dela.
**Falha de gateway não vaza para e-mail:** se o WhatsApp cair e a categoria não tiver e-mail
marcado, `send_reminder` devolve `None` e o comando **não** marca como enviado — o lembrete
segue pendente para a próxima rodada. Mandar por e-mail o que a pessoa tirou do e-mail
desfaria a escolha que a tela existe para fazer.

### D-055 · Backup é serviço próprio, com verificação e cópia externa
**Contexto:** a auditoria de 02/09/2026 encontrou o sistema **sem backup nenhum** — nem do
Postgres, nem do volume `/app/media` onde ficam os laudos de exame. Era o único achado cuja
falha é irreversível: histórico clínico e PDF de laudo não se reconstroem de lugar nenhum, e
o dossiê real está fora do git justamente por ser sensível (D-041).
**Decisão:** `scripts/backup.sh` roda no serviço `vitalis-backup` do EasyPanel, mesma imagem
do app com `SERVICE_MODE=backup` — o mesmo padrão já usado pelo `vitalis-cron` (D-040). Faz
`pg_dump` do banco e `tar` dos anexos, guarda em `/backups` (**tem de ser volume**: backup no
sistema de arquivos do contêiner morre junto com o contêiner que deveria proteger), e apaga o
que passa de `BACKUP_KEEP_DAYS`.
**Duas escolhas que separam backup de teatro de backup:**
- **Verificação imediata.** `gzip -t` em cada arquivo logo após gerar; se estiver corrompido,
  o arquivo é removido e o script sai com erro. Dump que não abre não é backup, e descobrir
  isso na hora da restauração é tarde.
- **Cópia externa opcional, mas anunciada.** Com `RCLONE_REMOTE` definida, o script sincroniza
  para fora. Sem ela, ele **avisa em toda execução** que a cópia existe só naquele servidor.
  Guardar ao lado do original protege contra engano humano e corrupção de tabela, nunca contra
  perder o host — e um aviso repetido é melhor que uma falsa sensação de segurança.
**A falta da credencial nunca bloqueia o backup local:** a ausência de `RCLONE_REMOTE` é aviso,
não erro. O pior resultado possível seria não ter cópia alguma porque o envio externo não
estava configurado.
**Ainda falta:** teste de restauração periódico. Backup nunca restaurado é hipótese, não
garantia.

### D-056 · Cópia externa no Google Drive via OAuth 2.0 em vez de Service Account
**Contexto:** ao configurar o envio externo para a pasta do Google Drive (`1iXaGZs_lHAbOC_lpxEe3hXLZYigatsPC`),
a primeira tentativa utilizou uma Conta de Serviço (*Service Account* do GCP). A execução do `rclone`
falhou com `Error 403: Service Accounts do not have storage quota. Leverage shared drives, or use OAuth delegation instead`.
Em contas pessoais do Google (`@gmail.com`), contas de serviço não têm cota própria de armazenamento e o Drive
rejeita a criação de arquivos mesmo em pastas compartilhadas com permissão de editor.
**Decisão:** autenticar o `rclone` via **OAuth 2.0 Desktop App** vinculado à conta pessoal do dono (`elvertoni@gmail.com`).
Criado o cliente OAuth `Vitalis Backup Novo` no projeto `coimbra-500602`, gerado o token de autorização
de longa duração (app em modo Produção) e injetadas as variáveis correspondentes no serviço `vitalis-backup`
do EasyPanel: `RCLONE_CONFIG_GDRIVE_CLIENT_ID`, `RCLONE_CONFIG_GDRIVE_CLIENT_SECRET`, `RCLONE_CONFIG_GDRIVE_TOKEN` e
`RCLONE_CONFIG_GDRIVE_ROOT_FOLDER_ID`.
**Resultado:** o upload agora grava com a cota pessoal legítima do dono. Testado em produção com sucesso:
dump do Postgres (`vitalis-db-*.sql.gz`) e tarball dos 8 laudos clínicos (`vitalis-media-*.tar.gz`)
armazenados e validados visualmente na pasta `backup-vitalis`.

### D-057 · Refinamento global: Acessibilidade WCAG, Performance ORM e Validações de Segurança
**Contexto:** auditoria técnica abrangente identificou oportunidades em três frentes:
1. Acessibilidade (menu oculto capturando foco via teclado, formulários com erros não anunciados e semiótica confusa de cor de erro);
2. Performance (N+1 no cálculo de cargas de treino, sobrecarga de sincronização de lembretes no dashboard e ausência de índices compostos);
3. Segurança (validação de anexos restrita a extensão nominal de arquivo e rota de signup vulnerável a cadastros em massa).
**Decisão:**
- **Acessibilidade:** inclusão de Skip Link para `#main-content`, atributo `inert` dinâmico no `#mobile-menu` quando fechado, IDs descritivos em `_field.html` (`_error` e `_help`), cores de erro corrigidas para semiótica evidente de alerta (`text-red-700`) e prevenção de múltiplos cliques (*double-submit*) em formulários.
- **Performance:** novos índices compostos `['user', 'next_return_date']` e `['user', 'scheduled_date']` no PostgreSQL (`saude`); debounce de 10 minutos via cache na chamada `sync_reminders` no `DashboardView`; e otimização das propriedades `top_weight` e `total_reps` em `SessionEntry` para consumir sets já pré-buscados em memória pelo Django sem disparar queries SQL repetidas.
- **Segurança:** inspeção binária de *magic bytes* em `validate_attachment` para PDF, JPG e PNG; preservação da extensão real do anexo na rota autenticada `ExamAttachmentView`; e rate limiting de 5 requisições/hora por IP no `SignupView`.

### D-058 · Painel Gráfico de Biomarcadores Laboratoriais integrado à Saúde
**Contexto:** o dossiê médico pessoal do paciente (`medico-seed.json` e pasta `toni/`) contém um painel completo
de análises clínicas (hemograma, glicemia, lipídios, função renal, hormônios e vitaminas).
A interface padrão de exames resumia o laudo em um bloco de texto puro, sem permitir ao paciente visualizar sua posição
frente às faixas de referência e à evolução histórica de forma intuitiva.
**Decisão:** criada a rota `/saude/biomarcadores/` (`saude:biomarkers`), a view `BiomarkersView` e o template `saude/biomarkers.html`.
A interface implementa réguas visuais de laboratório proporcionais, marcadores de status ("na meta", "atenção", "fora da meta"),
rastro de comparação com o exame anterior e delta percentual, régua de IMC com escalas de sobrepeso e obesidade,
alertas clínicos prioritários e pontos de alinhamento para a próxima consulta.
Acesso direto a partir do hub de saúde, da lista de exames e dos detalhes do laudo.

### D-059 · Orquestração: Comparador de Cardápios, Ciclo Posológico e Exportação de Prontuário LGPD
**Contexto:** para completar lacunas estruturais de usabilidade e governança identificadas no dossiê clínico:
1. Em Nutrição, o paciente necessitava de clareza visual entre a prescrição ajustada para perda de peso e a dieta anterior, mais pobre em proteína;
2. Em Saúde/Medicamentos, a posologia bifásica (uma fase diária seguida de dias alternados) exigia rastreamento dinâmico automático;
3. Em Contas, o direito à portabilidade de dados pessoais sensíveis (LGPD Art. 18) era uma lacuna deliberada pendente de entrega.
**Decisão:**
- **Nutrição:** incorporado em `nutricao/index.html` e `NutritionIndexView` o comparador interativo com alternância dinâmica via JS, placar de macronutrientes (calorias, déficit seguro vs agressivo, proteína/kg alvo) e linha do tempo das refeições com as substituições proteicas destacadas.
- **Medicação:** adicionada a propriedade `cycle_status` em `saude.Medication` e badge correspondente em `saude/medication_list.html`, calculando se a data de hoje pertence à fase diária ("dia X de N") ou à fase alternada ("hoje toma" vs "hoje pula").
- **LGPD:** criada a rota `/contas/exportar-dados/` (`accounts:export_data`) e a view `ExportUserDataView`, gerando sob demanda um arquivo `.zip` com `prontuario_vitalis.json` (perfil, médicos, tratamentos, exames, consultas, remédios, dietas, pesagens e treinos) e todos os PDFs de laudos originais anexados na pasta `laudos/`.

### D-060 · Acessibilidade Impeccable: Redução de Movimento, Formulários WCAG AA e Touch Targets
**Contexto:** auditoria técnica conduzida pelo plugin Impeccable (v4.1.1) diagnosticou oportunidades de elevação de nota para 19/20:
1. Ausência de `@media (prefers-reduced-motion)` forçava animações e rolagem suave em usuários com sensibilidade vestibular;
2. Formulários renderizavam mensagens de erro visuais, mas os widgets `<input>`/`<select>` não recebiam `aria-invalid="true"` nem `aria-describedby`, deixando leitores de tela sem anúncio automático da falha;
3. Links de ação secundária ("Excluir") em telas de detalhe mediam menos de 44px de altura, abaixo da recomendação WCAG 2.5.5.
**Decisão:**
- **Redução de Movimento:** injetada a regra `@media (prefers-reduced-motion: reduce)` em `templates/base.html` zerando durações de animação e desativando rolagem suave para usuários com a preferência ativada no sistema operacional.
- **Formulários Acessíveis:** `StyledFormMixin` em `accounts/forms.py` aprimorado para injetar programaticamente `aria-required="true"` em campos obrigatórios, `aria-describedby="id_{field}_help"` em campos com ajuda e `aria-invalid="true"` associado ao `id_{field}_error` no método `full_clean()`.
- **Touch Targets:** botões e links de ação nas telas de detalhe (`exam_detail`, `doctor_detail`, `appointment_detail`, `treatment_detail`, `medication_detail`, `diet_detail`, `routine_detail`) padronizados para altura mínima de 44px (`min-h-[44px]`), garantindo precisão e conforto ergonômico em dispositivos móveis.






### D-061 · Biomarcadores e comparador saem do código e viram dado do dono
**Contexto:** o painel de biomarcadores (D-058) e o comparador de cardápios (D-059) nasceram
# [dado clinico removido do historico - D-061]
`saude.views.BiomarkersView`, `planos_comparativo` em `nutricao.views.NutritionIndexView`, mais
peso, altura, nome do médico e alertas clínicos digitados direto no template. Três problemas,
em ordem de gravidade:
1. **Dado de saúde real versionado no git** — exatamente o que D-041 tirou do repositório ao
   mover o dossiê para `medico-data/` e `medico-seed.json`.
2. **A tela não era multiusuário.** Qualquer conta logada via o hemograma e o cardápio da mesma
   pessoa. O isolamento por dono, que é o requisito de segurança nº 1 do projeto, não tinha o
   que filtrar: não havia linha, havia literal.
3. **Nada era editável.** Chegando um exame novo, a única forma de atualizar era editar Python.

**Decisão:** os dois painéis passam a ler as linhas do próprio usuário.

- **`saude.LabPanel` / `saude.LabResult`** — o painel pendura no `Exam` de onde veio (que é
  quem carrega o PDF e o médico solicitante) e cada resultado guarda o que a régua precisa:
  `value`, `previous_value`, a faixa desenhada (`scale_min`/`scale_max`) e a faixa normal
  (`ref_low`/`ref_high`). A referência é **coluna, não constante**: ela pertence ao laboratório
  que emitiu o laudo, e o mesmo analito lê diferente entre laboratórios. As posições da régua
  são `@property` no model — qualquer tela desenha a mesma barra sem repetir a conta na view.
- **`saude.ClinicalNote`** — "pontos de atenção" e "o que alinhar com o médico" são texto que
  alguém escreveu depois de ler o laudo; não se deriva de `LabResult`, porque valor dentro da
  faixa também rende conversa. Um model, dois `kind`.
- **`nutricao/plans.py`** — cálculo puro, no molde de `treino/progression.py`: `bmi_snapshot`
  (IMC a partir da altura do perfil e da última pesagem, com faixa da OMS) e `plan_comparison`
  (a dieta ativa contra a anterior, somando as refeições reais). `Meal` ganhou `description` e
  `change_note` para carregar o "como é montada" e o "o que mudou" que o comparador mostra.
- **`seed_medico`** aprendeu `lab_panels` e `clinical_notes`, e o dossiê real recebeu os valores
  que estavam no código — **fora do git**, como todo o resto (D-041).

**Sem dado, sem tela:** conta nova cai no `_empty_state` do painel, e o comparador some com
menos de duas dietas. É a diferença entre um painel vazio e um painel que mente.

**Proteína por quilo se lê sobre o peso alvo** quando o perfil tem um: em quem está acima do
peso, dividir pela massa atual pede proteína para a gordura que a pessoa está perdendo. Sem
peso alvo, usa a última pesagem.

**Achado do caminho — vírgula decimal quebra CSS inline.** Com `{{ valor|floatformat }}` dentro
de `style="left: …%"`, o pt-BR renderiza `left: 75,7%`, que é **declaração inválida**: o
navegador descarta em silêncio e o ponto encosta na origem. Era o estado do painel desde
D-058, sem erro nenhum no servidor. Número que entra em CSS sai por `|stringformat:'.1f'`.
Vale para qualquer largura, posição ou porcentagem calculada em template.

**A mesma poda alcançou o ciclo de medicação.** `Medication.cycle_status` decidia a fase
comparando o **nome** do remédio com uma lista fixa no código e assumindo 30 dias: regra de uma
pessoa escrita no código, que nunca funcionaria para outra conta nem para o mesmo remédio em
outro protocolo. Virou dado: `cycle_daily_days` e `cycle_alternates_after`, ambos no
formulário e no `seed_medico`. Sem os campos preenchidos a propriedade devolve `None` e a
tela não mostra selo, que é o comportamento certo para uso contínuo.

**Continua pendente:** o histórico do git ainda contém os valores clínicos dos commits
anteriores. Limpar exige reescrever história (`filter-repo`) e forçar push, decisão do dono.

### D-062 · Vitalis AI: Copiloto Clínico, Multimodal e Esportivo com Gemini (Google AI Studio)
**Contexto:** necessidade de um assistente de inteligência artificial integrado diretamente ao sistema para:
1. Leitura e interpretação multimodal de receitas e exames médicos enviados em PDF e foto;
2. Sugestão e adaptação de receitas nutricionais, cálculo de macronutrientes e propostas de refeições;
3. Montagem e progressão de rotinas de musculação;
4. Orientações de suplementação e metas personalizadas de hidratação.
**Decisão:**
- **App Dedicado (`assistente`):** criado o app Django com os models `Conversation` e `Message` (ambos herdando de `OwnedModel` com `CASCADE` conforme D-021), armazenando histórico por usuário.
- **Cliente Gemini REST Nativo:** integração via `urllib.request` conectando-se ao endpoint `v1beta` do Google AI Studio com `gemini-2.5-flash` (fallback para `gemini-1.5-flash`), sem dependência de SDKs adicionais.
- **Visão Multimodal:** suporte a envio de laudos em PDF e fotos de exames/refeições encapsulados em Base64 (`inlineData`).
- **Prontuário Contextual Ativo (`build_clinical_context`):** o prompt de sistema é alimentado em tempo real com os dados do próprio usuário (perfil, altura, peso recente, IMC, 7 medicações ativas, dietas, biomarcadores e divisões de treino).
- **Interface e Navegação:** tela de chat interativa em `/assistente/` com suporte a sugestões rápidas de comandos, formatação Markdown e atalhos na barra de navegação desktop e mobile.
- **Segurança de Credenciais:** chave do Google AI Studio configurada estritamente via variável de ambiente (`GEMINI_API_KEY`) no local e na VPS EasyPanel, nunca versionada em código.


### D-063 · Remédio semanal, alimento contado e o Vitalis instalável no celular
**Contexto:** rodada de ajustes pedida pelo dono depois de usar o sistema no dia a dia.
Quatro coisas travavam o uso real: injetável de uma vez por semana gerava lembrete todo dia,
o alimento que se conta (ovo) aparecia sempre em grama, a receita preparada em casa não tinha
onde morar, e no celular o sistema abria como site, sem atalho de app.
**Decisão:**
- **Periodicidade semanal.** `Medication.weekdays` (lista de 0 a 6, segunda = 0) entra no
  `is_current_on`, que agora responde "tem dose nesse dia?" em vez de "o tratamento está
  aberto?" — junta início/fim, dia da semana e a fase do ciclo num lugar só. **Em branco
  significa todo dia**, não "nenhum dia": é o caso da maioria das receitas. Marcar o dia sem
  informar horário é erro de formulário, porque o gerador percorre os horários e o remédio
  ficaria em silêncio.
- **Alimento contado.** `Food.unit_weight_g` + `Food.unit_label` fazem `quantity_display`
  render "3 ovos (150 g)". Quem não preenche continua em grama. A conversão vive no `Food`
  porque `MealItem` e `DailyLog` mostram a mesma quantidade em telas diferentes.
- **Receita.** `Food.recipe` aparece na tela do alimento, e a refeição que usa um alimento com
  receita ganha o atalho "ver preparo". O preparo é do alimento, não da refeição: o mesmo
  sanduíche entra em duas refeições do dia.
- **Instalável (PWA).** `manifest.json` e `sw.js` são **rotas**, não arquivos estáticos: o
  escopo de um service worker é a pasta de onde ele foi baixado, e servido de `/static/` ele
  controlaria só o estático — o navegador nunca ofereceria instalar. O worker **não guarda
  página nenhuma em cache**, só ícone: resposta autenticada carrega laudo, peso e medicação, e
  deixar isso no disco do aparelho desfaz o cuidado de servir anexo por rota autenticada. Sem
  rede, aparece um aviso franco em vez de dado velho de saúde. No iPhone o navegador não
  dispara o convite de instalar, então o banner explica o caminho do Compartilhar.
**Furo corrigido de passagem:** `lembretes.manage_whatsapp` era verificada no código mas nunca
tinha sido **declarada** em `Meta.permissions` de model nenhum — ou seja, a permissão não
existia no banco e só superusuário passava, apesar de a documentação prometer o contrário.
Agora está declarada em `Reminder.Meta`.

### D-064 · Refinamento Impeccable (A11y, PWA Safe Area e Prontuário Dinâmico da IA)
**Contexto:** auditoria técnica e ergonômica sobre as novas funcionalidades.
**Decisão:**
- **Banner PWA com WCAG AA e Safe Area:** container com `role="dialog"`, `aria-labelledby`, anéis de foco explícitos (`focus-visible:ring-2`) e suporte a `env(safe-area-inset-bottom)` para evitar sobreposição à barra de gestos do iOS.
- **Chips de Dia da Semana (`weekday_chips.html`):** grupo semântico com `role="group" aria-label="Dias da semana"`, rótulos `aria-label` completos em cada checkbox para leitor de tela, e alvos táteis `min-h-[44px]`.
- **Hub e Lista de Alimentos:** afordância aprimorada nos cards de receitas caseiras, estados de hover com micro-animação de setas e focus rings padrão Soluna.
- **Prontuário Contextual do Vitalis AI:** enriquecimento de `build_clinical_context` com periodicidade semanal dos medicamentos e sinalizador de dose programada no dia (`is_current_on`), permitindo respostas precisas sobre a rotina diária e semanal do paciente.

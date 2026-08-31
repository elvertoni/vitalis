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

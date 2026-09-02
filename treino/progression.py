"""
Dupla progressão e leitura do histórico de carga.

A regra vem da ficha e não do código: bateu o topo da faixa de repetições em **todas** as
séries alvo, sobe carga no próximo treino. O passo é +2,5 kg em membro superior e +5 kg em
inferior, porque a perna tolera incremento maior que o ombro na mesma proporção de força.

O topo da faixa é lido de ``RoutineExerciseTarget.target_reps``, que é texto livre por
design ('10-12', '8-12', '10 por lado', '45s'). Prescrição medida em tempo não progride por
carga — ``top_of_range`` devolve ``None`` e a tela não sugere nada.

Nada aqui grava: são leituras puras usadas pela tela de registro. O único lugar que decide
carga é a pessoa.
"""

import re
from decimal import Decimal

from .models import SetLog, WorkoutSession

#: Grupos musculares tratados como membro inferior para efeito de passo de carga.
LOWER_BODY_GROUPS = {'pernas', 'perna', 'panturrilha', 'glúteos', 'gluteos'}

STEP_UPPER = 2.5
STEP_LOWER = 5.0

#: Semanas seguidas sem manhã ruim que liberam a reintrodução do leg press.
REINTRODUCTION_WEEKS = 4

_TIME_UNIT = re.compile(r'\d\s*(s|seg|segundos?|min|minutos?)\b', re.IGNORECASE)
_NUMBER = re.compile(r'\d+')


def top_of_range(target_reps):
    """
    Maior repetição da faixa prescrita, ou ``None`` quando a prescrição é em tempo.

    '10-12' → 12 · '8-12' → 12 · '10' → 10 · '10 por lado' → 10
    '45s' → None · '30-40s' → None · '10 min' → None
    """
    text = (target_reps or '').strip()
    if not text or _TIME_UNIT.search(text):
        return None
    numbers = [int(n) for n in _NUMBER.findall(text)]
    return max(numbers) if numbers else None


def step_for(exercise):
    """Incremento de carga do exercício, decidido pelo grupo muscular que ele treina."""
    group = (exercise.muscle_group.name or '').strip().lower()
    return STEP_LOWER if group in LOWER_BODY_GROUPS else STEP_UPPER


def last_sets(user, exercise, before_date):
    """
    Séries do exercício na sessão mais recente anterior a ``before_date``.

    Devolve ``(sessão, [SetLog, ...])`` ou ``(None, [])``. Ignora sessões em que o exercício
    aparece sem nenhuma série registrada — abrir a tela e não treinar não vira histórico.
    """
    entry = (
        SetLog.objects.filter(
            user=user, entry__exercise=exercise, entry__session__date__lt=before_date,
        )
        .select_related('entry__session')
        .order_by('-entry__session__date', '-entry__session__pk', 'set_number')
        .first()
    )
    if entry is None:
        return None, []
    session = entry.entry.session
    sets = list(
        SetLog.objects.filter(user=user, entry__exercise=exercise, entry__session=session)
        .order_by('set_number')
    )
    return session, sets


def suggestion_for(user, target, before_date):
    """
    O que sugerir para este alvo hoje, olhando a última vez que ele foi treinado.

    Devolve um dicionário com ``last_session``, ``last_sets``, ``last_weight`` e — só quando
    a dupla progressão fecha — ``suggested_weight`` e ``step``. Sem histórico, devolve os
    campos vazios: a tela mostra os campos em branco em vez de inventar um número.
    """
    session, sets = last_sets(user, target.exercise, before_date)
    data = {
        'last_session': session,
        'last_sets': sets,
        'last_weight': None,
        'suggested_weight': None,
        'step': None,
    }
    if not sets:
        return data

    weights = [s.weight for s in sets if s.weight is not None]
    data['last_weight'] = max(weights) if weights else None

    top = top_of_range(target.target_reps)
    if top is None or data['last_weight'] is None:
        return data
    # A progressão só vale se a pessoa cumpriu o número de séries prescrito: duas séries no
    # topo da faixa quando o alvo eram três não é sessão completa, é sessão interrompida.
    if len(sets) < target.target_sets:
        return data
    if not all(s.reps >= top for s in sets):
        return data

    step = step_for(target.exercise)
    data['step'] = step
    data['suggested_weight'] = data['last_weight'] + Decimal(str(step))
    return data


def morning_streak(user, today):
    """
    Semanas seguidas sem manhã ruim, contadas da última manhã ruim para cá.

    É o critério de reintrodução do leg press na ficha atual. Sessão ainda sem resposta não
    quebra a sequência nem conta a favor: só interrompe quem respondeu 'pior'.
    """
    answered = list(
        WorkoutSession.objects.filter(user=user, morning_after__in=[
            WorkoutSession.MorningAfter.OK, WorkoutSession.MorningAfter.WORSE,
        ]).order_by('date')
    )
    if not answered:
        return 0
    since = None
    for session in reversed(answered):
        if session.morning_after == WorkoutSession.MorningAfter.WORSE:
            break
        since = session.date
    if since is None:
        return 0
    return max((today - since).days // 7, 0)


def pending_morning_session(user, today):
    """
    Sessão anterior a hoje que já tem série registrada e ainda não teve a manhã respondida.

    A tela pergunta uma vez, sobre a mais recente. Sessões antigas sem resposta ficam como
    estão — perguntar sobre a manhã de três semanas atrás não produz resposta confiável.
    """
    return (
        WorkoutSession.objects.filter(user=user, date__lt=today, morning_after='')
        .filter(entries__sets__isnull=False)
        .distinct()
        .order_by('-date')
        .first()
    )


def next_day_after(user, days, today):
    """
    Qual divisão toca hoje, alternando a partir da última sessão registrada.

    Com A e B, treinar A ontem sugere B hoje. A sugestão é só sugestão: a tela deixa
    escolher qualquer divisão, porque a vida real desalinha a sequência.
    """
    days = list(days)
    if not days:
        return None
    last = (
        WorkoutSession.objects.filter(user=user, routine_day__in=days)
        .exclude(date=today)
        .order_by('-date')
        .first()
    )
    if last is None or last.routine_day is None:
        return days[0]
    try:
        index = [d.pk for d in days].index(last.routine_day.pk)
    except ValueError:
        return days[0]
    return days[(index + 1) % len(days)]

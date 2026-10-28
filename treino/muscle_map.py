"""
Estado de cada região do mapa muscular, calculado no servidor a partir do guia.

Puro cálculo, sem view, como ``progression.py``. O desenho é o SVG de
``templates/treino/partials/_muscle_map.html`` (react-native-body-highlighter, MIT — D-076);
aqui fica só a ponte entre as regiões desenhadas e a lista controlada ``Muscle``.

O desenho tem um deltoide por vista, então o deltoide lateral pinta as duas, o anterior só a
frente e o posterior só as costas. Região sem músculo da lista (mãos, joelhos, cabeça...) não
aparece aqui: o partial pinta essas com a cor de base, fixa.
"""

from .models import Muscle

REGION_MUSCLES = {
    'front': {
        'chest': [Muscle.CHEST],
        'deltoids': [Muscle.FRONT_DELT, Muscle.SIDE_DELT],
        'trapezius': [Muscle.TRAPS],
        'biceps': [Muscle.BICEPS],
        'triceps': [Muscle.TRICEPS],
        'forearm': [Muscle.FOREARM],
        'abs': [Muscle.ABS],
        'obliques': [Muscle.OBLIQUES],
        'quadriceps': [Muscle.QUADS],
        'adductors': [Muscle.ADDUCTORS],
        'calves': [Muscle.CALVES],
    },
    'back': {
        'trapezius': [Muscle.TRAPS],
        'deltoids': [Muscle.REAR_DELT, Muscle.SIDE_DELT],
        'upper_back': [Muscle.LATS],
        'lower_back': [Muscle.LOWER_BACK],
        'triceps': [Muscle.TRICEPS],
        'forearm': [Muscle.FOREARM],
        'gluteal': [Muscle.GLUTES],
        'adductors': [Muscle.ADDUCTORS],
        'hamstring': [Muscle.HAMSTRINGS],
        'calves': [Muscle.CALVES],
    },
}


def region_states(primary, secondary):
    """``{'front': {'chest': 'primary', ...}, 'back': {...}}`` — primário vence secundário."""
    primary, secondary = set(primary), set(secondary)
    states = {}
    for view, regions in REGION_MUSCLES.items():
        states[view] = {}
        for region, muscles in regions.items():
            if primary.intersection(muscles):
                states[view][region] = 'primary'
            elif secondary.intersection(muscles):
                states[view][region] = 'secondary'
            else:
                states[view][region] = 'idle'
    return states


def labels(keys):
    """Nomes em pt-BR, na ordem do guia; chave desconhecida é ignorada, não vira erro de tela."""
    names = dict(Muscle.choices)
    return [names[key] for key in keys if key in names]


def build(primary, secondary):
    """Tudo que o partial precisa: estado das regiões, legendas e o texto acessível."""
    primary_labels = labels(primary)
    secondary_labels = labels(secondary)
    aria = 'Mapa dos músculos trabalhados. Primários: ' + (', '.join(primary_labels) or 'nenhum') + '.'
    if secondary_labels:
        aria += ' Secundários: ' + ', '.join(secondary_labels) + '.'
    return {
        **region_states(primary, secondary),
        'primary_labels': primary_labels,
        'secondary_labels': secondary_labels,
        'aria_label': aria,
    }

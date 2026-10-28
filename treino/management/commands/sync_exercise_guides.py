"""
Carrega o catálogo global de guias de execução a partir de ``treino/catalog/exercises.json``.

O JSON versionado é a única fonte (D-075): catálogo e estado de cada ilustração moram nele,
e o banco é só o reflexo. Idempotente — casa pelo ``slug``; a segunda rodada seguida não
muda nada. Roda no boot do serviço web (``entrypoint.sh``, D-077), então todo deploy deixa
o catálogo igual ao arquivo.

    python manage.py sync_exercise_guides [--source caminho/do/catalogo.json]
"""

import json
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from treino.models import ExerciseGuide

DEFAULT_SOURCE = Path(settings.BASE_DIR) / 'treino' / 'catalog' / 'exercises.json'
STATUSES = {'pending', 'generated', 'approved', 'rejected'}
FIELDS = [
    'name', 'equipment', 'primary_muscles', 'secondary_muscles',
    'execution_steps', 'common_mistakes', 'illustration_alt', 'has_illustration',
]


class Command(BaseCommand):
    help = 'Sincroniza os guias de execução com treino/catalog/exercises.json.'

    def add_arguments(self, parser):
        parser.add_argument('--source', default=str(DEFAULT_SOURCE), help='Caminho do catálogo JSON.')

    def handle(self, *args, **options):
        path = Path(options['source'])
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f'Não foi possível ler o catálogo {path}: {exc}') from exc

        # Valida tudo antes de escrever qualquer linha: catálogo com erro não entra pela metade.
        guides = [self._build(entry) for entry in data.get('guides', [])]
        slugs = [guide.slug for guide in guides]
        repeated = sorted({slug for slug in slugs if slugs.count(slug) > 1})
        if repeated:
            raise CommandError(f'Slug repetido no catálogo: {", ".join(repeated)}')

        counts = {'criados': 0, 'atualizados': 0, 'sem mudança': 0, 'apagados': 0, 'órfãos mantidos': 0}
        with transaction.atomic():
            existing = {guide.slug: guide for guide in ExerciseGuide.objects.all()}
            for guide in guides:
                current = existing.get(guide.slug)
                if current is None:
                    guide.save()
                    counts['criados'] += 1
                    continue
                changed = [f for f in FIELDS if getattr(current, f) != getattr(guide, f)]
                if changed:
                    for field in changed:
                        setattr(current, field, getattr(guide, field))
                    current.save(update_fields=[*changed, 'updated_at'])
                    counts['atualizados'] += 1
                else:
                    counts['sem mudança'] += 1

            # Guia que saiu do catálogo só sai do banco se ninguém o usa. Vinculado, fica —
            # apagar levaria o vínculo de quem escolheu esse guia no próprio exercício.
            for slug, guide in existing.items():
                if slug in slugs:
                    continue
                if guide.exercises.exists():
                    counts['órfãos mantidos'] += 1
                    self.stderr.write(f'  aviso: {slug} saiu do catálogo, mas tem exercício vinculado — mantido')
                else:
                    guide.delete()
                    counts['apagados'] += 1

        illustrated = sum(1 for guide in guides if guide.has_illustration)
        self.stdout.write(
            ' · '.join(f'{label} {value}' for label, value in counts.items())
            + f' · com ilustração {illustrated}/{len(guides)}'
        )

    def _build(self, entry):
        slug = entry.get('slug', '')
        illustration = entry.get('illustration') or {}
        status = illustration.get('status', 'pending')
        if status not in STATUSES:
            raise CommandError(f'{slug}: status de ilustração inválido: {status!r}')

        guide = ExerciseGuide(
            slug=slug,
            name=entry.get('name', ''),
            equipment=entry.get('equipment', ''),
            primary_muscles=entry.get('primary_muscles', []),
            secondary_muscles=entry.get('secondary_muscles', []),
            execution_steps=entry.get('execution_steps', []),
            common_mistakes=entry.get('common_mistakes', []),
            illustration_alt=illustration.get('alt', ''),
        )
        # Aprovado no catálogo não basta: sem o PNG em static/, o {% static %} quebraria a tela.
        guide.has_illustration = status == 'approved' and finders.find(guide.illustration_path) is not None
        if status == 'approved' and not guide.has_illustration:
            self.stderr.write(f'  aviso: {slug} aprovado, mas sem {guide.illustration_path} — exibido sem imagem')

        if not guide.execution_steps:
            raise CommandError(f'{slug}: o guia precisa de ao menos um passo de execução.')
        try:
            guide.full_clean(exclude=['created_at', 'updated_at'], validate_unique=False)
        except ValidationError as exc:
            raise CommandError(f'{slug or "(sem slug)"}: {"; ".join(exc.messages)}') from exc
        return guide

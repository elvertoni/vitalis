// Gera templates/treino/partials/_muscle_map.html a partir do react-native-body-highlighter 3.2.0
// (MIT, D-076). Não roda no deploy: só quando o desenho ou as regiões mudarem.
// Uso: npm pack react-native-body-highlighter@3.2.0 && tar xzf react-native-body-highlighter-3.2.0.tgz
//      node scripts/build_muscle_map.js package templates/treino/partials/_muscle_map.html
const fs = require('fs');
const path = require('path');
const [pkg, out] = process.argv.slice(2);

const front = require(path.join(pkg, 'dist/assets/bodyFront.js')).bodyFront;
const back = require(path.join(pkg, 'dist/assets/bodyBack.js')).bodyBack;
const wrapper = fs.readFileSync(path.join(pkg, 'dist/components/SvgMaleWrapper.js'), 'utf8');
const outlines = [...wrapper.matchAll(/side === "(front|back)" && \(<react_native_svg_1\.Path [^>]*? d="([^"]+)"/g)]
  .reduce((acc, m) => ({ ...acc, [m[1]]: m[2] }), {});
const license = fs.readFileSync(path.join(pkg, 'LICENSE'), 'utf8').trim();

const MUSCLE_REGIONS = {
  front: ['chest', 'deltoids', 'trapezius', 'biceps', 'triceps', 'forearm', 'abs', 'obliques', 'quadriceps', 'adductors', 'calves'],
  back: ['trapezius', 'deltoids', 'upper_back', 'lower_back', 'triceps', 'forearm', 'gluteal', 'adductors', 'hamstring', 'calves'],
};

function paths(view, parts) {
  const lines = [];
  for (const part of parts) {
    const region = part.slug.replace(/-/g, '_');
    const cls = MUSCLE_REGIONS[view].includes(region) ? `mm-{{ map.${view}.${region} }}` : 'mm-base';
    const ds = [...(part.path.common || []), ...(part.path.left || []), ...(part.path.right || [])];
    lines.push(`        {# ${region} #}`);
    for (const d of ds) lines.push(`        <path class="${cls}" d="${d}"/>`);
  }
  return lines.join('\n');
}

function svg(view, viewBox, parts) {
  return `    <svg viewBox="${viewBox}" class="w-full h-auto" aria-hidden="true" focusable="false">
        <path class="mm-outline" d="${outlines[view]}"/>
${paths(view, parts)}
    </svg>`;
}

const html = `{% comment %}
Mapa muscular de um guia de execução (D-076). Uso:
    {% include 'treino/partials/_muscle_map.html' with map=guide.muscle_map %}
O estado de cada região (primary | secondary | idle) vem de treino/muscle_map.py; as cores
moram nas classes .mm-* de templates/base.html. Região sem músculo da lista controlada usa
mm-base, fixa. Gerado por scripts/build_muscle_map.js — os "d" vêm do pacote abaixo, não
foram desenhados aqui. Não edite à mão: regenere.

Desenho do corpo: react-native-body-highlighter 3.2.0
https://github.com/HichamELBSI/react-native-body-highlighter

${license}
{% endcomment %}
<!-- Desenho do corpo: react-native-body-highlighter, © 2022 ELABBASSI Hicham, licença MIT -->
<div class="flex flex-col gap-6">
    <div role="img" aria-label="{{ map.aria_label }}" class="grid grid-cols-2 gap-4 max-w-sm mx-auto w-full">
        <div class="flex flex-col items-center gap-2">
${svg('front', '0 0 724 1448', front)}
            <span class="text-xs font-medium tracking-widest uppercase text-[#5c5c5a]" aria-hidden="true">Frente</span>
        </div>
        <div class="flex flex-col items-center gap-2">
${svg('back', '724 0 724 1448', back)}
            <span class="text-xs font-medium tracking-widest uppercase text-[#5c5c5a]" aria-hidden="true">Costas</span>
        </div>
    </div>
    <dl class="flex flex-col gap-3 text-sm">
        <div class="flex items-start gap-3">
            <span class="mt-1 w-3 h-3 rounded-full bg-[#5d674f] shrink-0" aria-hidden="true"></span>
            <div><dt class="inline font-medium text-[#1a1a1a]">Primários:</dt> <dd class="inline text-[#5c5c5a]">{{ map.primary_labels|join:', ' }}</dd></div>
        </div>
        {% if map.secondary_labels %}
        <div class="flex items-start gap-3">
            <span class="mt-1 w-3 h-3 rounded-full bg-[#5d674f]/60 shrink-0" aria-hidden="true"></span>
            <div><dt class="inline font-medium text-[#1a1a1a]">Secundários:</dt> <dd class="inline text-[#5c5c5a]">{{ map.secondary_labels|join:', ' }}</dd></div>
        </div>
        {% endif %}
    </dl>
</div>
`;
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, html);
console.log('ok', Object.keys(outlines), html.length);

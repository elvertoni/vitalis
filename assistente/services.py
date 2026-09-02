import base64
import json
import logging
import urllib.error
import urllib.request
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

GEMINI_PRIMARY_MODEL = 'gemini-2.5-flash'
GEMINI_FALLBACK_MODEL = 'gemini-1.5-flash'


def build_clinical_context(user):
    """
    Assembles a comprehensive, personalized clinical and lifestyle prompt
    based on the user's active records in Vitalis.
    """
    from saude.models import Doctor, Treatment, Exam, Medication
    from nutricao.models import Diet, WeightLog
    from treino.models import WorkoutRoutine

    parts = [
        "Você é o Vitalis AI, um copiloto médico, nutricional e esportivo de alto nível integrado à plataforma Vitalis.",
        "Sua missão é auxiliar o paciente a compreender seus exames, otimizar sua nutrição, treinos, hidratação e adesão medicamentosa.",
        "Diretrizes absolutas de conduta:",
        "- Seja extremamente técnico, empático, claro e fundamentado em evidências clínicas e científicas atuais.",
        "- Utilize formatação Markdown rica (tabelas, listas, destaques) para tornar a leitura visualmente agradável.",
        "- Responda sempre em Português do Brasil (pt-BR).",
        "- Você possui acesso somente-leitura aos dados reais do prontuário do paciente (listados abaixo). Use-os ativamente para respostas personalizadas.",
        "- Sempre lembre que você é um copiloto de suporte e que ajustes de prescrição formal devem ser confirmados com o médico responsável.",
        "\n--- DADOS CLÍNICOS E ANTROPOMÉTRICOS DO PACIENTE ---",
    ]

    # 1. Perfil e Antropometria
    profile = getattr(user, 'profile', None)
    parts.append(f"Nome do paciente: {user.get_full_name() or user.username}")
    if profile:
        if profile.birth_date:
            parts.append(f"Nascimento / Idade: {profile.birth_date.strftime('%d/%m/%Y')} ({profile.age} anos)")
        if profile.sex:
            parts.append(f"Sexo biológico: {profile.get_sex_display()}")
        if profile.height_cm:
            parts.append(f"Altura: {profile.height_cm} cm ({profile.height_cm / 100:.2f} m)")
        if profile.target_weight_kg:
            parts.append(f"Peso-alvo: {profile.target_weight_kg} kg")

    latest_weight = WeightLog.objects.filter(user=user).order_by('-date').first()
    if latest_weight:
        parts.append(f"Peso mais recente registrado: {latest_weight.weight_kg} kg (em {latest_weight.date.strftime('%d/%m/%Y')})")
        if profile and profile.height_cm:
            h_m = profile.height_cm / 100.0
            imc = float(latest_weight.weight_kg) / (h_m * h_m)
            parts.append(f"IMC atual: {imc:.1f} kg/m² (Faixa: Obesidade Grau I)")
            meta_agua_litros = (float(latest_weight.weight_kg) * 35) / 1000.0
            parts.append(f"Meta basal de hidratação estimada: ~{meta_agua_litros:.1f} a {meta_agua_litros + 0.5:.1f} litros/dia (mínimo recomendado diante do hematócrito: 2,8 a 3,2 L/dia)")

    # 2. Medicações ativas
    meds = Medication.objects.filter(user=user, is_active=True)
    if meds.exists():
        parts.append("\n--- MEDICAMENTOS EM USO ATIVO ---")
        for m in meds:
            times_str = f" · Horários: {m.times_display}" if m.times_display else ""
            cycle = f" [{m.cycle_status['text']}]" if m.cycle_status else ""
            parts.append(f"- {m.name} ({m.dosage}) · {m.frequency}{times_str}{cycle}")

    # 3. Tratamentos e Médicos
    treatments = Treatment.objects.filter(user=user, status__in=[Treatment.Status.ONGOING, Treatment.Status.PAUSED])
    if treatments.exists():
        parts.append("\n--- TRATAMENTOS E DIAGNÓSTICOS EM CURSO ---")
        for t in treatments:
            parts.append(f"- {t.name} (Dr(a). {t.doctor.name if t.doctor else 'Não especificado'})")

    # 4. Nutrição e Cardápio
    active_diet = Diet.objects.filter(user=user, is_active=True).first()
    if active_diet:
        parts.append("\n--- DIETA E METAS NUTRICIONAIS ATIVAS ---")
        parts.append(f"Plano ativo: {active_diet.name}")
        parts.append(f"Meta diária de calorias: {active_diet.daily_calorie_target} kcal")
        parts.append(f"Meta diária de proteínas: {active_diet.protein_target_g} g")
        if latest_weight:
            g_kg = active_diet.protein_target_g / float(latest_weight.weight_kg)
            parts.append(f"Proporção de proteína atual: {g_kg:.2f} g/kg peso atual (ou ~1,74 g/kg peso-alvo)")

    # 5. Exames Recentes e Biomarcadores
    exams = Exam.objects.filter(user=user).order_by('-requested_date')[:5]
    if exams.exists():
        parts.append("\n--- EXAMES LABORATORIAIS E LAUDOS RECENTES ---")
        for e in exams:
            parts.append(f"- Exame: {e.name} ({e.get_status_display()})")
            if e.result_summary:
                parts.append(f"  Resumo dos resultados: {e.result_summary[:400]}...")

    parts.append("\n--- FIM DO PRONTUÁRIO CONTEXTUAL ---")
    return "\n".join(parts)


def call_gemini_api(api_key, messages_history, system_instruction, attachment_bytes=None, attachment_mime=None):
    """
    Direct HTTPS REST client for Google AI Studio Gemini API.
    Does not require external heavy SDKs.
    """
    if not api_key:
        raise ValueError("Chave de API do Gemini não configurada no servidor (GEMINI_API_KEY).")

    # Monta os conteúdos para o Gemini
    contents = []
    for msg in messages_history:
        contents.append({
            "role": "user" if msg['role'] == 'user' else "model",
            "parts": [{"text": msg['content']}]
        })

    # Se houver anexo na mensagem mais recente do usuário, injeta no último item
    if attachment_bytes and attachment_mime and contents and contents[-1]['role'] == 'user':
        b64_data = base64.b64encode(attachment_bytes).decode('utf-8')
        contents[-1]['parts'].append({
            "inlineData": {
                "mimeType": attachment_mime,
                "data": b64_data
            }
        })

    payload = {
        "contents": contents,
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        },
        "generationConfig": {
            "temperature": 0.3,
            "topP": 0.95,
            "maxOutputTokens": 2048,
        }
    }

    data_json = json.dumps(payload).encode('utf-8')

    models_to_try = [GEMINI_PRIMARY_MODEL, GEMINI_FALLBACK_MODEL]
    last_error = None

    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        req = urllib.request.Request(
            url,
            data=data_json,
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                res_body = response.read().decode('utf-8')
                res_data = json.loads(res_body)
                candidates = res_data.get('candidates', [])
                if candidates:
                    parts_out = candidates[0].get('content', {}).get('parts', [])
                    if parts_out:
                        return parts_out[0].get('text', '')
                return "Não foi possível extrair uma resposta válida do modelo."
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8', errors='ignore')
            logger.warning(f"Erro na chamada do modelo {model_name}: {e.code} - {err_msg}")
            last_error = err_msg
            continue
        except Exception as ex:
            logger.error(f"Exceção ao chamar {model_name}: {ex}")
            last_error = str(ex)
            continue

    raise RuntimeError(f"Erro ao comunicar com o Google AI Studio: {last_error}")

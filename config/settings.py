"""Django settings for the Vitalis project."""

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get('DJANGO_DEBUG', '0') == '1'

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-&g$)))b&z$mozun!m_v#ga$0ghymvzl$y38nw4s94x6i#q(c=f'
    else:
        raise RuntimeError('DJANGO_SECRET_KEY é obrigatória quando DEBUG=False.')

ALLOWED_HOSTS = [h for h in os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h]

# Necessário para o POST de login/admin sob HTTPS atrás do proxy do EasyPanel.
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if o]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
    'accounts',
    'saude',
    'treino',
    'nutricao',
    'lembretes',
    'billing',
    'assistente',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.SecurityHeadersMiddleware',
    # Serve o estático em produção sem nginx na frente (ver DECISIONS.md D-040).
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Desenvolvimento é SQLite (diretiva D10). Produção passa DATABASE_URL e cai no Postgres —
# o switch é só a variável de ambiente; nada no fluxo local muda. Ver DECISIONS.md D-040.
if os.environ.get('DATABASE_URL'):
    DATABASES = {
        'default': dj_database_url.parse(
            os.environ['DATABASE_URL'], conn_max_age=600, conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Definido antes da primeira migration: trocar AUTH_USER_MODEL depois exige recriar o banco.
AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'core:landing'

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# WhiteNoise comprime e versiona o estático (hash no nome) para servir em produção sem nginx.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

# Anexos de exame são dado sensível de saúde (LGPD): servidos apenas por view autenticada
# que confere a propriedade do registro, nunca por URL direta de MEDIA_URL.
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Base absoluta dos links dentro dos lembretes enviados. Sem request para montar a URL
# (quem envia é um comando de fora do ciclo HTTP), então vem do ambiente.
SITE_URL = os.environ.get('DJANGO_SITE_URL', 'http://127.0.0.1:8000').rstrip('/')

# WhatsApp pela Evolution API que já roda na mesma VPS (instância própria do Vitalis, D-045).
# Sem estas três, o canal se declara não configurado e o lembrete continua saindo por e-mail.
EVOLUTION_API_URL = os.environ.get('EVOLUTION_API_URL', '').rstrip('/')
EVOLUTION_API_KEY = os.environ.get('EVOLUTION_API_KEY', '')
EVOLUTION_INSTANCE = os.environ.get('EVOLUTION_INSTANCE', '')

# Chave secreta de assinatura HMAC do webhook do Mercado Pago (opcional em dev, recomendada em prod)
MERCADOPAGO_WEBHOOK_SECRET = os.environ.get('MERCADOPAGO_WEBHOOK_SECRET', '')

# Lembretes da v1 saem por e-mail. Em desenvolvimento vão para o console; em produção,
# defina EMAIL_HOST (+ EMAIL_HOST_USER/PASSWORD, EMAIL_PORT, EMAIL_USE_TLS) para enviar
# de verdade. Sem EMAIL_HOST em produção, usa DummyBackend para não vazar tokens nos logs.
DEFAULT_FROM_EMAIL = os.environ.get('DJANGO_DEFAULT_FROM_EMAIL', 'Vitalis <nao-responda@vitalis.app>')
if os.environ.get('EMAIL_HOST'):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ['EMAIL_HOST']
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
    EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', '1') == '1'
elif DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'

if not DEBUG:
    # O EasyPanel/Traefik termina o TLS e repassa via HTTP com X-Forwarded-Proto; sem isto
    # o SECURE_SSL_REDIRECT abaixo entra em loop infinito.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_X_FORWARDED_HOST = True
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

# Google AI Studio (Gemini) para o assistente clínico e esportivo
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')


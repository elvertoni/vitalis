from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('conta/', include('accounts.urls')),
    path('saude/', include('saude.urls')),
    path('treino/', include('treino.urls')),
    path('nutricao/', include('nutricao.urls')),
    path('lembretes/', include('lembretes.urls')),
    path('assinatura/', include('billing.urls')),
    path('', include('core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

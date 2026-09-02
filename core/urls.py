from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.LandingView.as_view(), name='landing'),
    path('painel/', views.DashboardView.as_view(), name='dashboard'),

    # Instalação como app. Ambos na raiz de propósito: o escopo do worker é a pasta dele.
    path('sw.js', views.ServiceWorkerView.as_view(), name='service_worker'),
    path('manifest.json', views.WebManifestView.as_view(), name='web_manifest'),
]

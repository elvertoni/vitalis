from django.urls import path

from . import views

app_name = 'billing'

urlpatterns = [
    path('', views.SubscriptionView.as_view(), name='subscription'),
    path('assinar/<slug:slug>/', views.SubscribeView.as_view(), name='subscribe'),
    path('cancelar/', views.CancelSubscriptionView.as_view(), name='cancel'),
    path('ativar-teste/', views.DevActivateSubscriptionView.as_view(), name='dev_activate'),
    path('webhook/mercadopago/', views.MercadoPagoWebhookView.as_view(), name='mercadopago_webhook'),
]

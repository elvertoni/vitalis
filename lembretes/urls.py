from django.urls import path

from . import views

app_name = 'lembretes'

urlpatterns = [
    path('', views.ReminderIndexView.as_view(), name='index'),
    path('novo/', views.ReminderCreateView.as_view(), name='create'),
    path('<int:pk>/concluir/', views.ReminderCompleteView.as_view(), name='complete'),
    path('<int:pk>/cancelar/', views.ReminderCancelView.as_view(), name='cancel'),
    path('preferencias/', views.NotificationPreferenceView.as_view(), name='preferences'),
    path('whatsapp/', views.WhatsAppPanelView.as_view(), name='whatsapp'),
    path('whatsapp/estado/', views.WhatsAppStatusView.as_view(), name='whatsapp_status'),
    path('whatsapp/desconectar/', views.WhatsAppLogoutView.as_view(), name='whatsapp_logout'),
    path('whatsapp/testar/', views.WhatsAppTestView.as_view(), name='whatsapp_test'),
]

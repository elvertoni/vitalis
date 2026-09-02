from django.urls import path
from . import views

app_name = 'assistente'

urlpatterns = [
    path('', views.ChatIndexView.as_view(), name='index'),
    path('<int:pk>/', views.ChatIndexView.as_view(), name='conversation_detail'),
    path('enviar/', views.SendMessageView.as_view(), name='send_message'),
    path('nova/', views.NewConversationView.as_view(), name='new_conversation'),
    path('<int:pk>/excluir/', views.DeleteConversationView.as_view(), name='delete_conversation'),
]

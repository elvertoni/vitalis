from django.urls import path

from . import views

app_name = 'lembretes'

urlpatterns = [
    path('', views.ReminderIndexView.as_view(), name='index'),
    path('novo/', views.ReminderCreateView.as_view(), name='create'),
    path('<int:pk>/concluir/', views.ReminderCompleteView.as_view(), name='complete'),
    path('<int:pk>/cancelar/', views.ReminderCancelView.as_view(), name='cancel'),
]

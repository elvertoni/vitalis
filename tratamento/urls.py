from django.urls import path

from . import views

app_name = 'tratamento'

urlpatterns = [
    path('', views.TreatmentIndexView.as_view(), name='index'),
    path('comecar/', views.OnboardingView.as_view(), name='onboarding'),

    path('aplicacoes/nova/', views.InjectionCreateView.as_view(), name='injection_create'),
    path('aplicacoes/<int:pk>/editar/', views.InjectionUpdateView.as_view(), name='injection_update'),
    path('aplicacoes/<int:pk>/excluir/', views.InjectionDeleteView.as_view(), name='injection_delete'),

    path('efeitos/', views.SideEffectListView.as_view(), name='sideeffect_list'),
    path('efeitos/novo/', views.SideEffectCreateView.as_view(), name='sideeffect_create'),
    path('efeitos/<int:pk>/editar/', views.SideEffectUpdateView.as_view(), name='sideeffect_update'),
    path('efeitos/<int:pk>/excluir/', views.SideEffectDeleteView.as_view(), name='sideeffect_delete'),
]

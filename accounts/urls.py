from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('entrar/', views.VitalisLoginView.as_view(), name='login'),
    path('sair/', views.VitalisLogoutView.as_view(), name='logout'),
    path('cadastro/', views.SignupView.as_view(), name='signup'),
    path('perfil/', views.ProfileView.as_view(), name='profile'),
    path('perfil/editar/', views.ProfileUpdateView.as_view(), name='profile_edit'),
    path('exportar-dados/', views.ExportUserDataView.as_view(), name='export_data'),
    path('acesso/editar/', views.AccountUpdateView.as_view(), name='account_edit'),
    path('senha/', views.VitalisPasswordResetView.as_view(), name='password_reset'),
    path('senha/enviada/', views.VitalisPasswordResetDoneView.as_view(), name='password_reset_done'),
    path(
        'senha/nova/<uidb64>/<token>/',
        views.VitalisPasswordResetConfirmView.as_view(),
        name='password_reset_confirm',
    ),
    path(
        'senha/concluida/',
        views.VitalisPasswordResetCompleteView.as_view(),
        name='password_reset_complete',
    ),
]

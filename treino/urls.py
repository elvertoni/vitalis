from django.urls import path

from . import views

app_name = 'treino'

urlpatterns = [
    path('', views.TrainingIndexView.as_view(), name='index'),

    path('grupos/', views.MuscleGroupListView.as_view(), name='muscle_group_list'),
    path('grupos/novo/', views.MuscleGroupCreateView.as_view(), name='muscle_group_create'),
    path('grupos/<int:pk>/', views.MuscleGroupDetailView.as_view(), name='muscle_group_detail'),
    path('grupos/<int:pk>/editar/', views.MuscleGroupUpdateView.as_view(), name='muscle_group_update'),
    path('grupos/<int:pk>/excluir/', views.MuscleGroupDeleteView.as_view(), name='muscle_group_delete'),

    path('exercicios/', views.ExerciseListView.as_view(), name='exercise_list'),
    path('exercicios/novo/', views.ExerciseCreateView.as_view(), name='exercise_create'),
    path('exercicios/<int:pk>/', views.ExerciseDetailView.as_view(), name='exercise_detail'),
    path('exercicios/<int:pk>/editar/', views.ExerciseUpdateView.as_view(), name='exercise_update'),
    path('exercicios/<int:pk>/excluir/', views.ExerciseDeleteView.as_view(), name='exercise_delete'),
    path('exercicios/<int:pk>/evolucao.json', views.ExerciseProgressDataView.as_view(), name='exercise_progress_data'),

    path('fichas/', views.WorkoutRoutineListView.as_view(), name='routine_list'),
    path('fichas/nova/', views.WorkoutRoutineCreateView.as_view(), name='routine_create'),
    path('fichas/<int:pk>/', views.WorkoutRoutineDetailView.as_view(), name='routine_detail'),
    path('fichas/<int:pk>/editar/', views.WorkoutRoutineUpdateView.as_view(), name='routine_update'),
    path('fichas/<int:pk>/excluir/', views.WorkoutRoutineDeleteView.as_view(), name='routine_delete'),
    path('fichas/<int:parent_pk>/divisoes/nova/', views.RoutineDayCreateView.as_view(), name='routine_day_create'),

    path('divisoes/<int:pk>/', views.RoutineDayDetailView.as_view(), name='routine_day_detail'),
    path('divisoes/<int:pk>/editar/', views.RoutineDayUpdateView.as_view(), name='routine_day_update'),
    path('divisoes/<int:pk>/excluir/', views.RoutineDayDeleteView.as_view(), name='routine_day_delete'),
    path(
        'divisoes/<int:parent_pk>/exercicios/novo/',
        views.RoutineExerciseTargetCreateView.as_view(),
        name='routine_exercise_create',
    ),
    path(
        'divisoes/exercicios/<int:pk>/excluir/',
        views.RoutineExerciseTargetDeleteView.as_view(),
        name='routine_exercise_delete',
    ),

    path('sessoes/', views.WorkoutSessionListView.as_view(), name='session_list'),
    path('sessoes/nova/', views.WorkoutSessionCreateView.as_view(), name='session_create'),
    path('sessoes/<int:pk>/', views.WorkoutSessionDetailView.as_view(), name='session_detail'),
    path('sessoes/<int:pk>/editar/', views.WorkoutSessionUpdateView.as_view(), name='session_update'),
    path('sessoes/<int:pk>/excluir/', views.WorkoutSessionDeleteView.as_view(), name='session_delete'),
    path(
        'sessoes/<int:parent_pk>/exercicios/novo/',
        views.SessionEntryCreateView.as_view(),
        name='session_entry_create',
    ),
    path(
        'sessoes/exercicios/<int:pk>/excluir/',
        views.SessionEntryDeleteView.as_view(),
        name='session_entry_delete',
    ),
    path(
        'sessoes/exercicios/<int:parent_pk>/series/nova/',
        views.SetLogCreateView.as_view(),
        name='set_log_create',
    ),
    path('sessoes/series/<int:pk>/excluir/', views.SetLogDeleteView.as_view(), name='set_log_delete'),
]

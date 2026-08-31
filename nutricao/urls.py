from django.urls import path

from . import views

app_name = 'nutricao'

urlpatterns = [
    path('', views.NutritionIndexView.as_view(), name='index'),

    path('alimentos/', views.FoodListView.as_view(), name='food_list'),
    path('alimentos/novo/', views.FoodCreateView.as_view(), name='food_create'),
    path('alimentos/<int:pk>/', views.FoodDetailView.as_view(), name='food_detail'),
    path('alimentos/<int:pk>/editar/', views.FoodUpdateView.as_view(), name='food_update'),
    path('alimentos/<int:pk>/excluir/', views.FoodDeleteView.as_view(), name='food_delete'),

    path('dietas/', views.DietListView.as_view(), name='diet_list'),
    path('dietas/nova/', views.DietCreateView.as_view(), name='diet_create'),
    path('dietas/<int:pk>/', views.DietDetailView.as_view(), name='diet_detail'),
    path('dietas/<int:pk>/editar/', views.DietUpdateView.as_view(), name='diet_update'),
    path('dietas/<int:pk>/excluir/', views.DietDeleteView.as_view(), name='diet_delete'),
    path('dietas/<int:parent_pk>/refeicoes/nova/', views.MealCreateView.as_view(), name='meal_create'),

    path('refeicoes/<int:pk>/', views.MealDetailView.as_view(), name='meal_detail'),
    path('refeicoes/<int:pk>/editar/', views.MealUpdateView.as_view(), name='meal_update'),
    path('refeicoes/<int:pk>/excluir/', views.MealDeleteView.as_view(), name='meal_delete'),
    path('refeicoes/<int:parent_pk>/itens/novo/', views.MealItemCreateView.as_view(), name='meal_item_create'),
    path('refeicoes/itens/<int:pk>/excluir/', views.MealItemDeleteView.as_view(), name='meal_item_delete'),

    path('registro/', views.DailyLogListView.as_view(), name='dailylog_list'),
    path('registro/novo/', views.DailyLogCreateView.as_view(), name='dailylog_create'),
    path('registro/<int:pk>/excluir/', views.DailyLogDeleteView.as_view(), name='dailylog_delete'),

    path('peso/', views.WeightLogListView.as_view(), name='weightlog_list'),
    path('peso/novo/', views.WeightLogCreateView.as_view(), name='weightlog_create'),
    path('peso/<int:pk>/editar/', views.WeightLogUpdateView.as_view(), name='weightlog_update'),
    path('peso/<int:pk>/excluir/', views.WeightLogDeleteView.as_view(), name='weightlog_delete'),
    path('peso/evolucao.json', views.WeightProgressDataView.as_view(), name='weight_progress_data'),
]

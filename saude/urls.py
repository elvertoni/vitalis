from django.urls import path

from . import views

app_name = 'saude'

urlpatterns = [
    path('', views.HealthIndexView.as_view(), name='index'),

    path('medicos/', views.DoctorListView.as_view(), name='doctor_list'),
    path('medicos/novo/', views.DoctorCreateView.as_view(), name='doctor_create'),
    path('medicos/<int:pk>/', views.DoctorDetailView.as_view(), name='doctor_detail'),
    path('medicos/<int:pk>/editar/', views.DoctorUpdateView.as_view(), name='doctor_update'),
    path('medicos/<int:pk>/excluir/', views.DoctorDeleteView.as_view(), name='doctor_delete'),

    path('tratamentos/', views.TreatmentListView.as_view(), name='treatment_list'),
    path('tratamentos/novo/', views.TreatmentCreateView.as_view(), name='treatment_create'),
    path('tratamentos/<int:pk>/', views.TreatmentDetailView.as_view(), name='treatment_detail'),
    path('tratamentos/<int:pk>/editar/', views.TreatmentUpdateView.as_view(), name='treatment_update'),
    path('tratamentos/<int:pk>/excluir/', views.TreatmentDeleteView.as_view(), name='treatment_delete'),

    path('biomarcadores/', views.BiomarkersView.as_view(), name='biomarkers'),
    path('exames/', views.ExamListView.as_view(), name='exam_list'),
    path('exames/novo/', views.ExamCreateView.as_view(), name='exam_create'),
    path('exames/<int:pk>/', views.ExamDetailView.as_view(), name='exam_detail'),
    path('exames/<int:pk>/editar/', views.ExamUpdateView.as_view(), name='exam_update'),
    path('exames/<int:pk>/excluir/', views.ExamDeleteView.as_view(), name='exam_delete'),
    path('exames/<int:pk>/laudo/', views.ExamAttachmentView.as_view(), name='exam_attachment'),

    path('consultas/', views.AppointmentListView.as_view(), name='appointment_list'),
    path('consultas/nova/', views.AppointmentCreateView.as_view(), name='appointment_create'),
    path('consultas/<int:pk>/', views.AppointmentDetailView.as_view(), name='appointment_detail'),
    path('consultas/<int:pk>/editar/', views.AppointmentUpdateView.as_view(), name='appointment_update'),
    path('consultas/<int:pk>/excluir/', views.AppointmentDeleteView.as_view(), name='appointment_delete'),

    path('medicamentos/', views.MedicationListView.as_view(), name='medication_list'),
    path('medicamentos/novo/', views.MedicationCreateView.as_view(), name='medication_create'),
    path('medicamentos/<int:pk>/', views.MedicationDetailView.as_view(), name='medication_detail'),
    path('medicamentos/<int:pk>/editar/', views.MedicationUpdateView.as_view(), name='medication_update'),
    path('medicamentos/<int:pk>/excluir/', views.MedicationDeleteView.as_view(), name='medication_delete'),
]

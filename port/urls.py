from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('scan/', views.scan_view, name='scan'),
    path('export/json/<int:scan_id>/', views.export_json, name='export_json'),
    path('export/csv/<int:scan_id>/', views.export_csv, name='export_csv'),
]
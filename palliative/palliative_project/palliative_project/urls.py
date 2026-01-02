from django.contrib import admin
from django.urls import path
from api.views import patient_list, patient_detail, visit_list, allocation_list, visit_detail, translate_text, get_analytics, inventory_list, inventory_detail, allocation_detail, inventory_history

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/patients', patient_list),
    path('api/patients/<int:pk>', patient_detail),
    path('api/patients/<int:patient_id>/visits', visit_list),
    path('api/patients/<int:patient_id>/allocations', allocation_list),
    
    # New Endpoints
    path('api/visits', visit_list), # For listing all / creating generally
    path('api/visits/<int:pk>', visit_detail), # For updating a specific visit
    path('api/translate', translate_text),
    path('api/analytics', get_analytics),
    path('api/inventory', inventory_list),
    path('api/inventory/<int:pk>', inventory_detail),
    path('api/allocations/<int:pk>', allocation_detail),
    path('api/inventory/<int:pk>/history', inventory_history),
]

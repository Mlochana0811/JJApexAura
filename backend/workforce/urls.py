from django.urls import path
from . import api, salary_sheets, template_payroll
urlpatterns=[
 path('salary-sheets/',salary_sheets.sheets),
 path('salary-sheets/upload/',template_payroll.upload),
 path('salary-sheets/<int:pk>/apply/',template_payroll.apply_to_payroll),
 path('salary-sheets/options/',salary_sheets.options),
 path('salary-sheets/<int:pk>/',salary_sheets.sheets),
 path('salary-sheets/<int:pk>/export/',salary_sheets.export),
 path('auth/<str:action>/',api.auth),
 path('dashboard/',api.dashboard),
 path('clock/<str:verb>/',api.attendance_clock),
 path('schema/<str:name>/',api.schema),
 path('schema/<str:name>/<int:pk>/',api.schema),
 path('files/<int:pk>/',api.file_download),
 path('reports/<str:kind>/<int:pk>/',api.report),
 path('<str:name>/',api.resource),
 path('<str:name>/<int:pk>/',api.resource),
 path('<str:name>/<int:pk>/<str:verb>/',api.action),
]

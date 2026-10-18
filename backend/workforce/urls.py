from django.urls import path
from . import api
urlpatterns=[
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

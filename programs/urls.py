from django.urls import path
from . import views


urlpatterns = [
    path('', views.program_view, name='programs'),
    path('new-program/', views.create_program, name='create_program'),
    path('program-exist/', views.check_exist, name='check_program'),
]
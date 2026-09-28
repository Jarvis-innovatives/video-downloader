from django.urls import path
from . import views

app_name = 'downloader'

urlpatterns = [
    path('', views.index, name='index'),
    path('movies/', views.movies, name='movies'),
    path('enhance-image/', views.enhance_image, name='enhance_image'),
    path('api/enhance_image/', views.api_enhance_image, name='api_enhance_image'),
    path('api/fetch/', views.api_fetch, name='api_fetch'),
    path('api/search_movies/', views.api_search_movies, name='api_search_movies'),
    path('api/download/', views.api_download, name='api_download'),
    path('api/start_download/', views.api_start_download, name='api_start_download'),
    path('api/progress/<str:task_id>/', views.api_progress, name='api_progress'),
    path('api/get_file/<str:task_id>/', views.api_get_file, name='api_get_file'),
]



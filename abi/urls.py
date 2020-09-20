from django.urls import path

from . import views


urlpatterns = [
    path('stats/api/', views.stats_api),
    path('pool3/apy/', views.pool3_apy),
]
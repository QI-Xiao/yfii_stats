from django.urls import path

from . import views


urlpatterns = [
    path('roi_week', views.roi_week),
]
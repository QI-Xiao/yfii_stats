from django.urls import path

from . import views


urlpatterns = [
    path('stats/api/', views.stats_api),
    path('farm/pools/', views.farm_pools),
    path('stake/pools/', views.stake_pools),
    path('liquidity/pools/', views.lp_pools),
]
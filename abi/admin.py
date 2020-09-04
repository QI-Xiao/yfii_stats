from django.contrib import admin
from .models import TokenPrice


@admin.register(TokenPrice)
class TokenPriceAdmin(admin.ModelAdmin):

    list_display = ('id', 'name', 'signal', 'origin_price', 'roi_week', 'created_time')
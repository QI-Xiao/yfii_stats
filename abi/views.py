from django.shortcuts import render
from django.http import HttpResponse, JsonResponse, Http404

from .models import TokenPrice


def roi_week(request):
    last_one = TokenPrice.objects.all().last()
    roi_week = last_one.roi_week

    return JsonResponse({
        'roi_week': last_one.roi_week,
        'name': last_one.name,
        'update_time': last_one.created_time
    })

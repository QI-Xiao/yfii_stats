from django.shortcuts import render
from django.http import HttpResponse, JsonResponse, Http404

from .models import TokenJson  # TokenPrice

import json


def stats_api(request):
    last_one = TokenJson.objects.all().last()

    return HttpResponse(last_one.text)

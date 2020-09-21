from django.shortcuts import render
from django.http import HttpResponse, JsonResponse, Http404

from .models import TokenJson  # TokenPrice

import json


def stats_api(request):
    last_one = TokenJson.objects.all().last()

    response = HttpResponse(last_one.text)
    response["Access-Control-Allow-Origin"] = "*"
    # response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    # response["Access-Control-Max-Age"] = "1000"
    # response["Access-Control-Allow-Headers"] = "X-Requested-With, Content-Type"

    return response
    # return HttpResponse(last_one.text)


def pool3_apy(request):
    response = JsonResponse({'apy': 0})
    response["Access-Control-Allow-Origin"] = "*"
    return response


def stake_pools(request):
    last_one = TokenJson.objects.all().last()

    response = HttpResponse(last_one.text_3pool)
    response["Access-Control-Allow-Origin"] = "*"
    return response

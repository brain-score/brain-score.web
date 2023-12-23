from django.shortcuts import render
from django.views.decorators.cache import cache_page
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views import View
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import requests


SLACK_WEBHOOK_URL = 'https://hooks.slack.com/triggers/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'


def view(request):
    return render(request, 'benchmarks/community.html')


class JoinSlack(View):
    def post(self, request):
        email = request.POST['email']

        try:
            validate_email(email)
        except ValidationError as e:
            return HttpResponse('Please enter a valid email')

        res = requests.post(SLACK_WEBHOOK_URL, json={
            'user_email': email
        }, headers={
            'Content-Type': 'application/json'
        })

        if res.status_code < 400:
            return HttpResponseRedirect('../community?join_slack=true')
        else:
            return HttpResponse('Something went wrong')

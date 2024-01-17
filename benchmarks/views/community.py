import requests

from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views import View
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from benchmarks.models import MailingList

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
            return HttpResponseRedirect('../../../community?join_slack=true')
        else:
            return HttpResponse('Something went wrong')


class JoinMailingList(View):
    def post(self, request):
        email = request.POST['email']

        try:
            validate_email(email)
        except ValidationError as e:
            return HttpResponse('Please enter a valid email')

        MailingList.objects.update_or_create(email=email.lower())

        return HttpResponseRedirect('../../../community?join_mailing_list=true')

class Unsubscribe(View):
    def get(self, request):
        return render(request, 'benchmarks/unsubscribe.html')

    def post(self, request):
        email = request.POST['email']

        try:
            validate_email(email)
        except ValidationError as e:
            return HttpResponse('Please enter a valid email')

        MailingList.objects.get(email=email.lower()).delete()

        return HttpResponseRedirect('../../../unsubscribe?success=true')

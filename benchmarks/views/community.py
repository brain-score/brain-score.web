from django.views.decorators.csrf import csrf_exempt
import requests

from django.shortcuts import render
from django.views.decorators.cache import cache_page
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views import View
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from benchmarks.tokens import get_google_default_credentials


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

        try:
            service = build("people", "v1", credentials=get_google_default_credentials())

            contact_groups = service.contactGroups().list().execute()['contactGroups']
            brainscore_mailing_list = next((group for group in contact_groups if 'name' in group and group['name'] == 'Brainscore mailing list'), None)

            contact_payload = {
                'emailAddresses': [{ 'value': email }],
                'memberships': [
                    {
                        "contactGroupMembership": {
                            "contactGroupResourceName": brainscore_mailing_list['resourceName']
                        }
                    }
                ]
            }

            service.people().createContact(body=contact_payload).execute()
        except HttpError as e:
            return HttpResponse('Something went wrong')

        return HttpResponseRedirect('../../../community?join_mailing_list=true')

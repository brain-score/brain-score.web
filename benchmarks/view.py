import datetime
import json
import logging
import requests
from django.contrib.auth import get_user_model, login, authenticate, update_session_auth_hash, logout
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMessage
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.views import View

from .forms import SignupForm, LoginForm, UploadFileForm
from .models import Submission
from .tokens import account_activation_token

_logger = logging.getLogger(__name__)

User = get_user_model()


class Activate(View):
    def get(self, request, uidb64, token):
        try:
            uid = force_text(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except(TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and account_activation_token.check_token(user, token):
            # activate user and login:
            user.is_active = True
            user.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return HttpResponseRedirect('../../profile/')

        else:
            return HttpResponse('Activation link is invalid!')

    def post(self, request):
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important, to update the session with the new password
            return HttpResponse('Password changed successfully')


class Signup(View):
    def get(self, request):
        form = SignupForm()
        return render(request, 'benchmarks/signup.html', {'form': form})

    def post(self, request):
        form = SignupForm(request.POST)
        if form.is_valid():
            # Create an inactive user with no password:
            user = form.save()
            user.is_active = False
            to_email = form.cleaned_data.get('email')
            user.save()
            # Send an email to the user with the token:
            mail_subject = 'Activate your account.'
            current_site = get_current_site(request)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = account_activation_token.make_token(user)
            activation_link = f"{current_site}/activate/{uid}/{token}"
            message = (f"Hello {user.get_full_name()}!\n\n"
                       f"Please click or paste the following link to activate your account:\n{activation_link}")
            email = EmailMessage(mail_subject, message, to=[to_email])
            sent_messages = email.send()
            assert sent_messages == 1
            context = {"email": True, 'form': LoginForm}
            return render(request, 'benchmarks/login.html', context)
        else:
            context = {"email": True, 'form': LoginForm}
            return render(request, 'benchmarks/login.html', context)


class Login(View):
    def get(self, request):
        return render(request, 'benchmarks/login.html', {'form': LoginForm})

    def post(self, request):
        user = authenticate(request, username=request.POST['username'], password=request.POST['password'])
        if user is not None:
            login(request, user)
            return render(request, 'benchmarks/profile.html')
        else:
            context = {"Incorrect": True}
            return render(request, 'benchmarks/login.html', context)


class Logout(View):
    def get(self, request):
        logout(request)
        return HttpResponseRedirect('../../')


class Upload(View):
    def get(self, request):
        if str(request.user) == "AnonymousUser":
            return HttpResponseRedirect('../profile/')
        form = UploadFileForm()
        return render(request, 'benchmarks/upload.html', {'form': form})

    def post(self, request):
        form = UploadFileForm(request.POST, request.FILES)
        if not form.is_valid():
            return HttpResponse("Form is invalid", status=400)

        if not may_submit(request.user, delay=datetime.timedelta(days=7)):  # user has already submitted recently
            return HttpResponse("Too many submission attempts -- only one submission every 7 days is allowed",
                                status=403)

        # setup jenkins submission
        submission = Submission.objects.create(submitter=request.user, status=Submission.Status.PENDING)

        json_info = {
            "name": request.POST['name'],
            "model_type": request.POST['model_type'],
            "email": request.user.get_full_name(),
            "type": "zip",
            "zip_filename": request.FILES['zip_file'].name,
        }

        with open('result.json', 'w') as fp:
            json.dump(json_info, fp)

        _logger.debug(f"request user: {request.user.get_full_name()}")

        jenkins_url = "http://braintree.mit.edu:8080"
        auth = get_secret("brainscore-website_jenkins_access")
        auth = (auth['user'], auth['password'])
        job_name = "run_benchmarks"
        request_url = f"{jenkins_url}/job/{job_name}/buildWithParameters" \
                      f"?TOKEN=trigger2scoreAmodel" \
                      f"&email={request.user.get_full_name()}" \
                      f"&submission={submission.id}"
        _logger.debug(f"request_url: {request_url}")

        # submit to jenkins
        params = {"submission.zip": request.FILES['zip_file'], 'submission.config': open('result.json', 'rb')}
        _logger.debug(f"Triggering build: {job_name}")
        response = requests.post(request_url, files=params, auth=auth)
        _logger.debug(f"response: {response}")

        # update database
        submission.status = Submission.Status.SUBMITTED if response.status_code == 200 \
            else Submission.Status.SUBMISSION_FAILED
        submission.save()

        # update frontend
        response.raise_for_status()
        _logger.debug("Job triggered successfully")
        return render(request, 'benchmarks/success.html')


def may_submit(user, delay):
    submissions = Submission.objects.filter(submitter=user)  # get all submissions of this user
    submissions = submissions.exclude(status=Submission.Status.PENDING)  # exclude pendings which haven't gone through
    if not submissions:  # no submissions so far
        return True
    latest_submission = submissions.latest('timestamp')
    latest_timestamp = latest_submission.timestamp
    if latest_timestamp < datetime.datetime.now(tz=latest_timestamp.tzinfo) - delay:
        return True  # last submission >1 week ago
    return False


class Profile(View):
    def get(self, request):
        if str(request.user) == "AnonymousUser":
            return render(request, 'benchmarks/login.html', {'form': LoginForm})
        else:
            return render(request, 'benchmarks/profile.html')

    def post(self, request):
        user = authenticate(request, username=request.POST['username'], password=request.POST['password'])
        if user is not None:
            login(request, user)
            return render(request, 'benchmarks/profile.html')
        else:
            context = {"Incorrect": True, 'form': LoginForm}
            return render(request, 'benchmarks/login.html', context)

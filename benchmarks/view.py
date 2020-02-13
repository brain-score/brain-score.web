from django.views import View
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from .forms import SignupForm, LoginForm, UploadFileForm
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth import get_user_model, login, authenticate, update_session_auth_hash, logout
from django.contrib.auth.forms import PasswordChangeForm
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from .tokens import account_activation_token
from django.core.mail import EmailMessage
import requests
import json
import datetime
import logging

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
        if request.user.get_lowest_datefield() < datetime.date.today() - datetime.timedelta(7):
            form = UploadFileForm(request.POST, request.FILES)
            if form.is_valid():
                json_info = {
                    "model_type": request.POST['model_type'],
                    "name": request.POST['name'],
                    "email": request.user.get_full_name(),
                    "gpu_size": "8000",
                    "type": "zip",
                    "zip_filename": request.FILES['zip_file'].name,
                }

                with open('result.json', 'w') as fp:
                    json.dump(json_info, fp)

                _logger.debug(f"request user: {request.user.get_full_name()}")

                jenkins_url = "http://braintree.mit.edu:8080"
                auth = ("caleb", "BrownFoxTree")
                job_name = "run_benchmarks"
                request_url = f"{jenkins_url}/job/{job_name}/buildWithParameters?TOKEN=trigger2scoreAmodel" \
                              f"&email={request.user.get_full_name()}"

                _logger.debug(f"request_url: {request_url}")

                _logger.debug("Determining next build number")
                current_url = f"{jenkins_url:s}/job/{job_name:s}/api/json"

                job = requests.get(
                    current_url,
                    auth=auth,
                ).json()

                next_build_number = job['nextBuildNumber']

                params = {"submission.zip": request.FILES['zip_file'], 'submission.config': open('result.json', 'rb')}
                _logger.debug(f"Triggering build: {job_name:s} #{next_build_number:d}")
                response = requests.post(request_url, files=params, auth=auth)
                _logger.debug(f"response: {response}")

                response.raise_for_status()
                _logger.debug("Job triggered successfully")

                request.user.set_lowest_datefield(datetime.date.today())

                return render(request, 'benchmarks/success.html')
            else:
                return HttpResponse("Form is invalid")
        else:  # user has already submitted in the past x days
            return HttpResponse("Too many submission attempts -- only one submission every 7 days is allowed")


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

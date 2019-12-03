from django.views import View
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from .forms import SignupForm, LoginForm, UploadFileForm
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth import get_user_model, login, authenticate, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from .tokens import account_activation_token
from django.core.mail import EmailMessage
from django.urls import reverse
from urllib.request import Request, urlopen
import requests
import json
import time

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

            form = PasswordChangeForm(request.user)

            return render(request, 'benchmarks/activation.html', {'form': form})

        else:
            return HttpResponse('Activation link is invalid!')

    def post(self, request):
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user) # Important, to update the session with the new password
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
            activation_link = "{0}/activate/{1}/{2}".format(current_site, uid, token)
            message = "Hello {0}".format(activation_link)
            email = EmailMessage(mail_subject, message, to=[to_email])
            email.send()
            return HttpResponse('Please confirm your email address to complete the registration')
        else:
            return HttpResponse('Please confirm your email address to complete the registration')

class Login(View):
    def get(self, request):
        form = LoginForm()
        return render(request, 'benchmarks/login.html', {'form': LoginForm})

    def post(self, request):
        form = LoginForm(data=request.POST)
        user = authenticate(request, username=request.POST['username'], password=request.POST['password'])
        if user is not None:
            login(request, user)
            return render(request, 'benchmarks/profile.html')
        else:
            return HttpResponse("Something went Wrong!")

class Upload(View):
    def get(self, request):
        form = UploadFileForm()
        return render(request, 'benchmarks/upload.html', {'form': form})

    def post(self, request):
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            
            json_info = {
                "model_type": "BaseModel",
                "name": "DiCarloLab",
                "email": "calebl@mit.edu",
                "gpu_size": "8000",
                "type": "zip"
            }

            with open('result.json', 'w') as fp:
                json.dump(json_info, fp)

            print(request.user.get_full_name())

            jenkins_url = "http://braintree.mit.edu:8080"
            auth = ("caleb", "BrownFoxTree")
            job_name = "endpoint_copy"
            request_url = "{0:s}/job/{1:s}/buildWithParameters?TOKEN=trigger2scoreAmodel".format(
                jenkins_url,
                job_name
            )

            print(request_url)

            print("Determining next build number")
            current_url = "{0:s}/job/{1:s}/api/json".format(
                    jenkins_url,
                    job_name,
                )

            job = requests.get(
                current_url,
                auth=auth,
            ).json()

            next_build_number = job['nextBuildNumber']
            next_build_url = "{0:s}/job/{1:s}/{2:d}/api/json".format(
                jenkins_url,
                job_name,
                next_build_number,
            )
            print(request.FILES)
            params = {"submission.zip": request.FILES['zip_file'], 'submission.config': open('result.json', 'rb')}
            print(params)
            print("Triggering build: {0:s} #{1:d}".format(job_name, next_build_number))
            response = requests.post(request_url, files=params, auth=auth)

            print(response)

            response.raise_for_status()
            print("Job triggered successfully")

            while True:
                print("Querying Job current status...")
                try:
                    build_data = requests.get(next_build_url, auth=auth).json()
                except ValueError:
                    print("No data, build still in queue")
                    print("Sleep for 20 sec")
                    time.sleep(20)
                    continue

                print("Building: {0}".format(build_data['building']))
                building = build_data['building']
                if building is False:
                    break
                else:
                    print("Sleep for 60 sec")
                    time.sleep(60)

            print("Job finished with status: {0:s}".format(build_data['result']))


            return render(request, 'benchmarks/upload.html')
        else:
            return HttpResponse("Form is invalid")


import boto3
import json
import logging
import requests
from botocore.exceptions import ClientError
from django.contrib.auth import get_user_model, login, authenticate, update_session_auth_hash, logout
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm, SetPasswordForm
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMessage
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.views import View

from benchmarks.forms import SignupForm, LoginForm, UploadFileForm
from benchmarks.models import Model
from benchmarks.tokens import account_activation_token
from benchmarks.views.index import get_context

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
            email.send()
            context = {"activation_email": True, "password_email": False, 'form': LoginForm}
            return render(request, 'benchmarks/login.html', context)
        elif form.errors:
            context = {'form': form}
            return render(request, 'benchmarks/signup.html', context)
        else:
            context = {'form': LoginForm}
            return render(request, 'benchmarks/profile.html', context)


class Login(View):
    def get(self, request):
        return render(request, 'benchmarks/login.html', {'form': LoginForm})

    def post(self, request):
        user = authenticate(request, username=request.POST['username'], password=request.POST['password'])
        if user is not None:
            login(request, user)
            return render(request, 'benchmarks/profile.html')
        else:
            context = {"Incorrect": True, 'form': LoginForm}
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

        user_inst = User.objects.get_by_natural_key(request.user.get_full_name())
        json_info = {
            "model_type": request.POST['model_type'],
            "user_id": user_inst.id,
            "public": str('public' in request.POST)
        }

        with open('result.json', 'w') as fp:
            json.dump(json_info, fp)

        _logger.debug(request.user.get_full_name())
        _logger.debug(f"request user: {request.user.get_full_name()}")

        # submit to jenkins
        jenkins_url = "http://braintree.mit.edu:8080"
        auth = get_secret("brainscore-website_jenkins_access")
        auth = (auth['user'], auth['password'])
        job_name = "run_benchmarks"
        request_url = f"{jenkins_url}/job/{job_name}/buildWithParameters" \
                      f"?TOKEN=trigger2scoreAmodel" \
                      f"&email={request.user.get_full_name()}"
        _logger.debug(f"request_url: {request_url}")
        params = {"submission.zip": request.FILES['zip_file'], 'submission.config': open('result.json', 'rb')}
        response = requests.post(request_url, files=params, auth=auth)
        _logger.debug(f"response: {response}")

        # update frontend
        response.raise_for_status()
        _logger.debug("Job triggered successfully")
        return render(request, 'benchmarks/success.html')


def resubmit(request):
    if request.method == 'POST':
        _logger.debug(f"request user: {request.user.get_full_name()}")
        model_ids = []
        benchmarks = []
        for key, value in request.POST.items():
            if 'models_' in key:
                model = Model.objects.get(id=value)  # get model instance uniquely referenced with the id
                verify_user_model_access(user=request.user, model=model)
                model_ids.append(model.id)
            if 'benchmarks_' in key:
                # benchmark identifiers are versioned, which we have to remove for submitting to jenkins
                benchmarks.append(value.split('_v')[0])
        if len(model_ids) > 0 and len(benchmarks) > 0:
            json_info = {
                "user_id": request.user.id,
                "model_ids": model_ids,
            }
            with open('result.json', 'w') as fp:
                json.dump(json_info, fp)

            # submit to jenkins
            jenkins_url = "http://braintree.mit.edu:8080"
            auth = get_secret("brainscore-website_jenkins_access")
            auth = (auth['user'], auth['password'])
            job_name = "run_benchmarks"
            s = ' '
            benchmark_string = s.join(benchmarks)
            request_url = f"{jenkins_url}/job/{job_name}/buildWithParameters" \
                          f"?TOKEN=trigger2scoreAmodel" \
                          f"&email={request.user.get_full_name()}" \
                          f"&benchmarks={benchmark_string}"
            _logger.debug(f"request_url: {request_url}")
            params = {'submission.config': open('result.json', 'rb')}
            response = requests.post(request_url, files=params, auth=auth)
            _logger.debug(f"response: {response}")

            # update frontend
            response.raise_for_status()
            _logger.debug("Job triggered successfully")
            return render(request, 'benchmarks/success.html')
        else:
            return render(request, 'benchmark/')


class Profile(View):
    def get(self, request):
        if str(request.user) == "AnonymousUser":
            return render(request, 'benchmarks/login.html', {'form': LoginForm})
        else:
            context = get_context(request.user)
            context["has_user"] = True
            return render(request, 'benchmarks/profile.html', context)

    def post(self, request):
        user = authenticate(request, username=request.POST['username'], password=request.POST['password'])
        if user is not None:
            login(request, user)
            context = get_context(user)
            context["has_user"] = True
            return render(request, 'benchmarks/profile.html', context)
        else:
            context = {"Incorrect": True, 'form': LoginForm}
            return render(request, 'benchmarks/login.html', context)


class Password(View):
    def get(self, request):
        form = PasswordResetForm()
        return render(request, 'benchmarks/password.html', {'form': form})

    def post(self, request):
        form = PasswordResetForm(request.POST)
        username = request.POST["email"]
        user = None
        try:
            user = User.objects.get_by_natural_key(username)
        except User.DoesNotExist:
            pass
        if form.is_valid() and user is not None:
            # Retrieve requested user:
            username = request.POST["email"]
            user = User.objects.get_by_natural_key(username)
            to_email = username

            # Send an email to the user with the token:
            mail_subject = 'Change Password Request'
            current_site = get_current_site(request)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = account_activation_token.make_token(user)
            activation_link = f"{current_site}/password-change/{uid}/{token}"
            message = f"Hello {user.get_full_name()}!\n\n" \
                      f"Please click or paste the following link to change your password:\n{activation_link}"
            email = EmailMessage(mail_subject, message, to=[to_email])
            email.send()
            return render(request, 'benchmarks/password-confirm.html')
        elif form.errors:
            context = {'form': form}
            return render(request, 'benchmarks/password.html', context)
        else:
            context = {"activation_email": False, 'password_email': False, 'form': LoginForm}
            return render(request, 'benchmarks/login.html', context)


class ChangePassword(View):
    def get(self, request, uidb64, token):
        try:
            uid = force_text(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except(TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and account_activation_token.check_token(user, token):
            # reset password:
            form = SetPasswordForm(user=user)

            return render(request, 'benchmarks/password.html', {'form': form})

        else:
            return HttpResponse('Password change link is invalid!')

    def post(self, request, uidb64, token):
        try:
            uid = force_text(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except(TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
        form = SetPasswordForm(user=user, data=request.POST)
        if form.is_valid():
            user.set_password(request.POST["new_password1"])
            user.save()
            user.is_active = True
            return HttpResponseRedirect('../../profile/')
        elif form.errors:
            context = {'form': form}
            return render(request, 'benchmarks/password.html', context)
        else:
            return render(request, 'benchmarks/password.html', {'form': form})


class PublicAjax(View):
    """
    deals with asynchronous user requests to change model public visibility
    """

    def post(self, request):
        # data contains a dictionary of model identifiers to a boolean setting of public
        data = json.loads(request.body)
        model_id, public = data['id'], data['public']
        model = Model.objects.get(id=model_id)
        verify_user_model_access(user=request.user, model=model)
        model.public = public
        model.save(update_fields=['public'])
        return JsonResponse("success", safe=False)


def verify_user_model_access(user, model):
    # make sure user is allowed to perform this operation: either model owner or superuser
    if not (user.is_superuser or model.owner == user.id):
        raise PermissionDenied(f"User {user} is not allowed access to model {model}")


def get_secret(secret_name, region_name='us-east-2'):
    session = boto3.session.Session()
    _logger.info("Fetch secret from secret manager")
    try:
        client = session.client(
            service_name='secretsmanager',
            region_name=region_name,
        )
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            _logger.error("The requested secret " + secret_name + " was not found")
        elif e.response['Error']['Code'] == 'InvalidRequestException':
            _logger.error("The request was invalid due to:", e)
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            _logger.error("The request had invalid params:", e)
        raise e
    except Exception as e:
        _logger.error("The request failed with:", e)
        raise e
    else:
        # Secrets Manager decrypts the secret value using the associated KMS CMK
        # Depending on whether the secret was a string or binary, only one of these fields will be populated
        _logger.info(f'Secret {secret_name}successfully fetched')
        if 'SecretString' in get_secret_value_response:
            _logger.info("Inside string response...")
            return json.loads(get_secret_value_response['SecretString'])
        else:
            _logger.info("Inside binary response...")
            return get_secret_value_response['SecretBinary']

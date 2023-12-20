import json
import logging

import boto3
import requests
from botocore.exceptions import ClientError
from django.contrib.auth import get_user_model, login, authenticate, update_session_auth_hash, logout
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm, SetPasswordForm
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMessage
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.views import View

from benchmarks.forms import SignupForm, LoginForm, UploadFileForm, UploadFileFormLanguage
from benchmarks.models import Model
from benchmarks.tokens import account_activation_token
from benchmarks.views.index import get_context
import zipfile
import os

_logger = logging.getLogger(__name__)

User = get_user_model()


class Activate(View):

    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except(TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and account_activation_token.check_token(user, token):
            # activate user and login:
            user.is_active = True
            user.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return HttpResponseRedirect(f'../../../profile/')

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
            current_site = get_current_site(request)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = account_activation_token.make_token(user)

            activation_link = f"https://{current_site}/activate/{uid}/{token}"
            message_suffix = (f"Please click or paste the following link to activate your account:\n"
                              f"{activation_link}\n\n"
                              f"If you encounter any trouble, please reach out to Mike (mferg@mit.edu)."
                              f"Thanks,\n"
                              f"The Brain-Score Team")
            # if indirect signup via PR, provide additional context:
            if "is_from_pr" in request.POST:
                message = (f"Hello!\n"
                           f"We have received your pull request via GitHub for a Brain-Score plugin.\n\n"
                           f"We did not find a Brain-Score account associated with your GitHub email {to_email}, "
                           f"so we created one for you. "
                           f"Your temporary password is {form.cleaned_data.get('password1')}, "
                           f"please reset it after activating you account."
                           f"\n\n{message_suffix}")
            # regular signup via website form
            else:
                message = (f"Hello!\n"
                           f"Thanks for signing up with Brain-Score."
                           f"\n\n{message_suffix}")
            mail_subject = 'Activate your Brain-Score Account'
            email = EmailMessage(mail_subject, message, to=[to_email])
            email.send()
            context = {"activation_email": True, "password_email": False, 'form': LoginForm}
            return render(request, 'benchmarks/login.html', context)
        elif form.errors:
            context = {'form': form}
            return render(request, 'benchmarks/signup.html', context)
        else:
            context = {'form': LoginForm, "domains": ["vision", "language"]}
            return render(request, 'benchmarks/central_profile.html', context)


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


class LandingPage(View):
    def get(self, request):
        return render(request, 'benchmarks/landing_page.html')

class Logout(View):
    domain = None

    def get(self, request):
        logout(request)
        return HttpResponseRedirect('../')


class Landing(View):

    def get(self, request):
        return render(request, 'benchmarks/landing_page.html')


class Tutorial(View):
    tutorial_type = None

    def get(self, request):
        return render(request, f'benchmarks/tutorial{self.tutorial_type}.html')


class Upload(View):
    domain = None

    def get(self, request):
        assert self.domain is not None
        if request.user.is_anonymous:
            return HttpResponseRedirect(f'../profile/{self.domain}')
        if self.domain == "language":
            form = UploadFileFormLanguage()
        else:
            form = UploadFileForm()
        return render(request, 'benchmarks/upload.html', {'form': form, 'domain': self.domain})

    def post(self, request):
        assert self.domain is not None
        if self.domain == "language":
            form = UploadFileFormLanguage(request.POST, request.FILES)
        else:
            form = UploadFileForm(request.POST, request.FILES)
        if not form.is_valid():
            return HttpResponse("Form is invalid", status=400)

        # parse directory tree, return new html page if not valid:
        if self.domain == "language":
            is_zip_valid, error = validate_zip(form.files.get('zip_file'))
            request.FILES['zip_file'].seek(0)  # reset file pointer
            if not is_zip_valid:
                return render(request, 'benchmarks/invalid_zip.html', {'error': error, "domain": self.domain})

        user_inst = User.objects.get_by_natural_key(request.user.email)
        json_info = {
            "model_type": request.POST['model_type'] if "model_type" in form.base_fields else "BrainModel",
            "user_id": user_inst.id,
            "public": str('public' in request.POST),
            "competition": 'cosyne2022' if 'competition' in request.POST and request.POST['competition'] else None,
            "domain": self.domain
        }

        with open('result.json', 'w') as fp:
            json.dump(json_info, fp)

        _logger.debug(request.user.get_full_name())
        _logger.debug(f"request user: {request.user.get_full_name()}")

        # submit to jenkins
        jenkins_url = "http://braintree.mit.edu:8080"
        auth = get_secret("brainscore-website_jenkins_access")
        auth = (auth['user'], auth['password'])

        if self.domain == "language":
            job_name = "create_github_pr"
        else:
            job_name = "run_benchmarks"

        request_url = f"{jenkins_url}/job/{job_name}/buildWithParameters" \
                      f"?TOKEN=trigger2scoreAmodel" \
                      f"&email={request.user.email}"
        _logger.debug(f"request_url: {request_url}")
        params = {"submission.zip": request.FILES['zip_file'], 'submission.config': open('result.json', 'rb')}
        response = requests.post(request_url, files=params, auth=auth)
        _logger.debug(f"response: {response}")

        # update frontend
        response.raise_for_status()
        _logger.debug("Job triggered successfully")
        return render(request, 'benchmarks/success.html', {"domain": self.domain})


def validate_zip(file):
    with zipfile.ZipFile(file, mode="r") as archive:
        namelist = archive.infolist()
        root = namelist[0]
        has_plugin, submitted_plugins = plugins_exist(namelist)
        if not has_plugin:
            return False, f"\nPlease make sure your {root.filename} folder contains at least one of the " \
                          f"following folders:" \
                          "[metrics, data, benchmarks, models]"
        instances = []
        files = []
        for plugin in submitted_plugins:
            has_instance, submitted_instances = plugin_has_instances(namelist, plugin)
            instances.append(submitted_instances)
        plugin_instance_dict = dict(zip(submitted_plugins, instances))

        # make sure there is at least one plugin that is not empty:
        if all(x == [] for x in plugin_instance_dict.values()):

            if len(list(plugin_instance_dict.keys())) == 1:
                return False, f"\nYour {list(plugin_instance_dict.keys())} folder is empty."
            else:
                return False, f"\nYour {list(plugin_instance_dict.keys())} folders are empty."

        for instance in plugin_instance_dict.values():
            if len(instance) < 1:
                pass
            else:
                has_files, submitted_files, broken_instance = instance_has_files(namelist, instance)
                if not has_files:
                    return False, f"\nYour {broken_instance} folder must contain an __init__.py and a test.py folder."
                files.append(submitted_files)
        return True, ""


# checks that there is >= 1 plugin
def plugins_exist(namelist):
    acceptable_plugins = ["models", "benchmarks", "data", "metrics"]
    plugins = [file.filename for file in namelist if file.filename.endswith("/") and file.filename.count("/") == 2]
    plugins_list = [plugin.split("/")[1].lower() for plugin in plugins]
    if len(list(set(plugins_list) & set(acceptable_plugins))) >= 1:
        return True, list(set(plugins_list) & set(acceptable_plugins))
    else:
        return False, []


# makes sure every plugin has an associated instance
def plugin_has_instances(namelist, plugin):
    instances = [file.filename for file in namelist if file.filename.endswith("/") and file.filename.count("/") == 3]
    instances_list = [file_path.split("/")[2] for file_path in instances if file_path.split("/")[1] == plugin]

    # make sure there is >= 1 instance submitted:
    if len(instances_list) < 1:
        return False, []
    else:
        return True, instances_list


# makes sure each instance has a __init__.py and setup.py
def instance_has_files(namelist, instances):
    files_list = []
    for instance in instances:
        files = [file.filename.split("/")[-1] for file in namelist if file.filename.split("/")[-2] == instance]
        if len(set(files) & {"__init__.py", "test.py"}) < 2:
            return False, [], instance
        files_list.append(files)

    return True, files_list, None


def collect_models_benchmarks(request):
    assert request.method == 'POST'

    _logger.debug(f"request user: {request.user.get_full_name()}")
    model_ids = []
    model_names = []
    benchmarks = []
    for key, value in request.POST.items():
        if key.startswith('model_selection_'):
            # value in this case is the model id
            model = Model.objects.get(id=value)  # get model instance uniquely referenced with the id
            verify_user_model_access(user=request.user, model=model)
            model_names.append(model.name)
            model_ids.append(model.id)
        elif key.startswith('benchmark_selection_'):
            # value is benchmark_type_id (un-versioned)
            benchmarks.append(value)
    return model_ids, model_names, benchmarks


def submit_to_jenkins(request, domain, model_name, benchmarks=None):
    # submit to jenkins
    jenkins_url = "http://braintree.mit.edu:8080"
    auth = get_secret("brainscore-website_jenkins_access")
    auth = (auth['user'], auth['password'])

    # language has a different URL building system than vision
    if domain == "vision":
        job_name = "run_benchmarks"
        benchmark_string = ' '.join(benchmarks)
        request_url = f"{jenkins_url}/job/{job_name}/buildWithParameters" \
                      f"?TOKEN=trigger2scoreAmodel" \
                      f"&email={request.user.email}" \
                      f"&benchmarks={benchmark_string}"
        _logger.debug(f"request_url: {request_url}")
    else:
        job_name = "score_plugins"
        benchmark_string = '%20'.join(benchmarks)
        request_url = f"{jenkins_url}/job/{job_name}/buildWithParameters" \
                      f"?token=trigger2scoreAmodel" \
                      f"&user_id={request.user.id}" \
                      f"&new_benchmarks={benchmark_string}" \
                      f"&new_models={model_name}" \
                      f"&specified_only=True"
        _logger.debug(f"request_url: {request_url}")

    params = {'submission.config': open('result.json', 'rb')}
    response = requests.post(request_url, files=params, auth=auth)
    response = requests.post(request_url, files=params, auth=auth)
    _logger.debug(f"response: {response}")

    # update frontend
    response.raise_for_status()
    _logger.debug("Job triggered successfully")


def resubmit(request, domain: str):

    model_ids, model_names, benchmarks = collect_models_benchmarks(request)
    model_id_name_dict = dict(zip(model_ids, model_names))

    if len(model_ids) == 0 or len(benchmarks) == 0:
        return render(request, 'benchmarks/submission_error.html', {'error': "No model ids and benchmarks found"})

    for model_id, model_name in model_id_name_dict.items():
        json_info = {
            "domain": domain,
            "user_id": request.user.id,
            "model_ids": [model_id],
        }
        with open('result.json', 'w') as fp:
            json.dump(json_info, fp)
        submit_to_jenkins(request, domain, model_name, benchmarks)
    return render(request, 'benchmarks/success.html', {"domain": domain})


class DisplayName(View):

    def post(self, request):
        user_instance = User.objects.get_by_natural_key(request.user.email)
        user_instance.display_name = request.POST['display_name']
        user_instance.save()
        return HttpResponseRedirect(f'../../profile/')


# intermediary account page: uniform across all Brain-Score domains.
class ProfileAccount(View):

    def get(self, request):
        if request.user.is_anonymous:
            return render(request, 'benchmarks/login.html', {'form': LoginForm})
        else:
            context = {"domains": ["vision", "language"]}
            return render(request, 'benchmarks/central_profile.html', context)

    def post(self, request):
        user = authenticate(request, username=request.POST['username'], password=request.POST['password'])
        if user is not None:
            login(request, user)
            context = {"domains": ["vision", "language"]}
            return render(request, 'benchmarks/central_profile.html', context)
        else:
            context = {"Incorrect": True, 'form': LoginForm, "domains": ["vision", "language"]}
            return render(request, 'benchmarks/login.html', context)


class Profile(View):
    domain = None

    def get(self, request):
        if request.user.is_anonymous:
            return render(request, 'benchmarks/login.html', {'form': LoginForm, "domain": self.domain})
        else:
            context = get_context(request.user, domain=self.domain)
            context["has_user"] = True
            return render(request, 'benchmarks/profile.html', context)

    def post(self, request):
        user = authenticate(request, username=request.POST['username'], password=request.POST['password'])
        if user is not None:
            login(request, user)
            context = get_context(user, domain=self.domain)
            context["has_user"] = True
            return render(request, 'benchmarks/profile.html', context)
        else:
            context = {"Incorrect": True, 'form': LoginForm, "domain": self.domain}
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
            activation_link = f"https://{current_site}/password-change/{uid}/{token}"
            message = (f"Hello!\n\n"
                       f"Please click or paste the following link to change your password:\n{activation_link}\n\n"
                       f"If you encounter any trouble, reach out to Martin (msch@mit.edu) or Mike (mferg@mit.edu)."
                       f"Thanks,\n"
                       f"The Brain-Score Team")
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
            uid = force_str(urlsafe_base64_decode(uidb64))
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
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except(TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
        form = SetPasswordForm(user=user, data=request.POST)
        if form.is_valid():
            user.set_password(request.POST["new_password1"])
            user.save()
            user.is_active = True
            return HttpResponseRedirect(f'../../../profile/')
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
    if not (user.is_superuser or model.owner == user):
        raise PermissionDenied(f"User {user} is not allowed access to model {model}")


def split_identifier_version(versioned_benchmark_identifier):
    """
    Separates a versioned benchmark identifier into identifier and version.
    :param versioned_benchmark_identifier: the combined specifier of identifier and version,
        e.g. `dicarlo.MajajHong2015.V4-pls_v3`
    :return: the benchmark identifier and version separate, e.g. `dicarlo.MajajHong2015.V4-pls` and `3`
    """
    identifier_version_split = versioned_benchmark_identifier.split('_v')
    # re-combine all components but the last (aka the version). This avoids identifiers being split at `_v`,
    # e.g. Marques2020_Ringach2002-circular_variance
    identifier = '_v'.join(identifier_version_split[:-1])
    version = identifier_version_split[-1]
    return identifier, version


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

import json
import logging
import os
import zipfile
import re
from typing import Tuple, Union, List
from io import TextIOWrapper

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

from benchmarks.forms import SignupForm, LoginForm, UploadFileForm
from benchmarks.models import Model, BenchmarkInstance, BenchmarkType
from benchmarks.tokens import account_activation_token
from benchmarks.views.index import get_context
from django.core.files.uploadedfile import InMemoryUploadedFile

_logger = logging.getLogger(__name__)

User = get_user_model()

PLUGIN_LIMIT = 5  # used to limit the amount of plugins that can be submitted at once by a user


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


class Sponsors(View):

    def get(self, request):
        return render(request, 'benchmarks/sponsors.html')


class Faq(View):

    def get(self, request):
        return render(request, 'benchmarks/faq.html')


class Tutorial(View):
    tutorial_type = None

    def get(self, request):
        return render(request, f'benchmarks/tutorials/tutorial{self.tutorial_type}.html')


class Upload(View):
    domain = None

    def get(self, request):
        assert self.domain is not None
        if request.user.is_anonymous:
            return HttpResponseRedirect(f'../profile/{self.domain}')
        form = UploadFileForm()
        return render(request, 'benchmarks/upload.html', {'form': form, 'domain': self.domain, 'formatted': self.domain.capitalize()})

    def post(self, request):
        assert self.domain is not None
        form = UploadFileForm(request.POST, request.FILES)
        if not form.is_valid():
            return HttpResponse("Form is invalid", status=400)

        user_instance = User.objects.get_by_natural_key(request.user.email)

        # parse directory tree, return new html page if not valid:
        is_zip_valid, error = validate_zip(form.files.get('zip_file'))
        submission_is_original, submission_data = is_submission_original_and_under_plugin_limit(file=form.files.get('zip_file'), submitter=user_instance)
        request.FILES['zip_file'].seek(0)  # reset file pointer
        if not is_zip_valid:
            return render(request, 'benchmarks/invalid_zip.html', {'error': error, "domain": self.domain})
        if not submission_is_original:  # also checks for amount of unique identifiers
            plugin, identifier = submission_data

            if plugin == 'too_many_identifiers':
                return render(request, 'benchmarks/invalid_zip.html', {'error': identifier, "domain": self.domain})

            # ensure the user is not accidentally submitting the tutorial model
            page = "tutorial" if identifier == "resnet50_tutorial" else "already"

            return render(request, f'benchmarks/{page}_submitted.html',
                          {'plugin': plugin, 'identifier': identifier, "domain": self.domain})

        json_info = {
            "model_type": request.POST['model_type'] if "model_type" in form.base_fields else "BrainModel",
            "user_id": user_instance.id,
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
        request_url = f"{jenkins_url}/job/create_github_pr/buildWithParameters" \
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


def is_submission_original_and_under_plugin_limit(file, submitter: User) -> Tuple[bool, Union[None, List[str]]]:
    """
    First, checks if the submission is below the max allowed plugin submission limit.
    If so, checks that the identifiers present within the submission are original.
    """
    # add metrics and data eventually
    plugin_db_mapping = {"models": Model, "benchmarks": BenchmarkType}

    with zipfile.ZipFile(file, mode="r") as archive:
        namelist = archive.infolist()
        plugins = plugins_exist(namelist)[1]

        # grab identifiers from inits of all plugins
        plugin_identifiers = extract_identifiers(archive)
        under_plugin_limit = under_identifier_limit(plugin_identifiers)
        if not under_plugin_limit:
            return False, ["too_many_identifiers", f"Exceeded the maximum limit of {PLUGIN_LIMIT} unique identifiers across all plugins."]

        # for each plugin submitted, make sure that the identifier does not exist already:
        for plugin in plugins:
            plugin_directory_names = plugin_has_instances(namelist, plugin)[1]
            db_table = plugin_db_mapping[plugin]

            # Determine the lookup field name based on the plugin type
            field_name = 'name' if plugin == "models" else 'identifier'

            # plugin_name corresponds to the directory name, plugin_identifier corresponds to actual identifiers from inits
            all_plugin_ids = plugin_directory_names + list(plugin_identifiers[plugin])
            for plugin_name_or_identifier in all_plugin_ids:
                query_filter = {field_name: plugin_name_or_identifier}
                
                # check for tutorial
                if "resnet50_tutorial" in plugin_name_or_identifier:
                    return False, [plugin, plugin_name_or_identifier]

                # check if an entry with the given identifier exists
                if db_table.objects.filter(**query_filter).exists():
                    owner_obj = db_table.objects.filter(**query_filter).first()
                    owner_id = getattr(owner_obj, 'owner_id', None) or getattr(owner_obj, 'owner').id

                    # check to see if the submitter is the owner (or superuser)
                    if owner_id != submitter.id and not submitter.is_superuser:
                        return False, [plugin, plugin_name_or_identifier]
                    # else, versioning will occur here
                        
    return True, []  # Passes all checks, then the submission is original -> good to go


def validate_zip(file: InMemoryUploadedFile) -> Tuple[bool, str]:
    """
    Validates the structure of a zip file. Checks for the existence of required plugins
    and their instances, and verifies that each instance contains specific files.

    :param file: Path to the zip file.
    :return: Tuple containing a boolean for success and an error message if any.
    """

    # check if file is above 50MB. If so reject and ask users to contact Brain-Score team
    file_size_mb = file.size / (1024 * 1024)  # Convert bytes to megabytes
    if file_size_mb > 50:
        return False, "Your zip file size cannot be greater than 50MB. Are you trying to submit weights with your model? " \
                      "If so, please contact the Brain-Score team and we can assist you in hosting your model " \
                      "weights elsewhere."

    with zipfile.ZipFile(file, mode="r") as archive:
        namelist = archive.infolist()

        # Check for spaces in file names
        for item in namelist:
            if ' ' in item.filename:
                return False, f"File '{item.filename}' contains spaces. Please remove spaces from all file names."
                
        root = namelist[0]
        has_plugin, submitted_plugins = plugins_exist(namelist)
        if not has_plugin:  # checks for at least one plugin
            return False, (f"\nPlease make sure your {root.filename} folder contains at least one of the "
                           "following valid plugin folders: [models, benchmarks, data, metrics].")

        plugin_instance_dict = {plugin: plugin_has_instances(namelist, plugin)[1] for plugin in submitted_plugins}
        if all(not instances for instances in plugin_instance_dict.values()):
            folder_names = list(plugin_instance_dict.keys())
            if len(folder_names) == 1:
                return False, f"\nYour {folder_names[0]} folder is empty."
            else:
                return False, f"\nYour {', '.join(folder_names)} folders are empty."

        for instances in plugin_instance_dict.values():
            for instance in instances:
                has_files, _, broken_instance = instance_has_files(namelist, [instance])
                if not has_files:
                    return False, f"\nYour {broken_instance} folder must contain both required Python files:" \
                                  f" __init__.py and test.py."

        return True, ""


def plugins_exist(namelist: List[zipfile.ZipInfo]) -> Tuple[bool, List[str]]:
    """
    Checks if at least one acceptable plugin exists in the zip file.

    :param namelist: List of ZipInfo objects from the zip file.
    :return: Tuple of boolean indicating existence and list of found plugins.
    """
    acceptable_plugins = {"models", "benchmarks", "data", "metrics"}
    plugins = {file.filename.split("/")[1].lower() for file in namelist if _is_plugin_path(file.filename)}
    valid_plugins = list(plugins & acceptable_plugins)
    return bool(valid_plugins), valid_plugins


def plugin_has_instances(namelist: List[zipfile.ZipInfo], plugin: str) -> Tuple[bool, List[str]]:
    """
    Determines if a plugin has associated instances.

    :param namelist: List of ZipInfo objects from the zip file.
    :param plugin: The plugin name to check.
    :return: Tuple of boolean indicating existence and list of instances.
    """
    # Filter filenames that represent plugin instances
    instances = [file.filename for file in namelist if file.filename.endswith("/")
                 and file.filename.count("/") == 3
                 and file.filename.split("/")[1] == plugin]

    # Extract instance names
    instances_list = [instance.split("/")[2] for instance in instances]
    return bool(instances_list), instances_list


def instance_has_files(namelist: List[zipfile.ZipInfo], instances: List[str]) -> Tuple[bool, List[List[str]], str]:
    """
    Checks if each instance has required files (__init__.py and test.py).

    :param namelist: List of ZipInfo objects from the zip file.
    :param instances: List of instance names to check.
    :return: Tuple of boolean indicating success, list of files, and the name of a broken instance if any.
    """
    required_files = {"__init__.py", "test.py"}
    all_files = []

    for instance in instances:
        files = {file.filename.split("/")[-1] for file in namelist if file.filename.split("/")[-2] == instance}
        all_files.append(list(files))
        if not required_files.issubset(files):
            return False, [], instance

    return True, all_files, ''


def _is_plugin_path(path: str) -> bool:
    """
    Helper function to check if a path corresponds to a plugin.
    """
    return path.endswith("/") and path.count("/") == 2


def _is_instance_path(path: str, plugin: str) -> bool:
    """
    Helper function to check if a path corresponds to an instance of a plugin.
    """
    parts = path.split("/")
    return len(parts) > 2 and parts[1] == plugin and path.endswith("/")


def extract_identifiers(zip_ref):
    # define patterns for each plugin type (data and metrics to be added later)
    possible_plugins = ["models", "benchmarks"]
    registry_patterns = {
        "models": re.compile(r"model_registry\['(.+?)'\]"),
        "benchmarks": re.compile(r"benchmark_registry\['(.+?)'\]"),
    }

    # dictionary to hold identifiers for each plugin type found
    identifiers = {plugin: set() for plugin in possible_plugins}

    for file_info in zip_ref.infolist():
        path_segments = file_info.filename.split('/')
        # ensure the path has 4 segments [zip root, plugin, plugin_name, __init__.py]
        if len(path_segments) == 4 and path_segments[1] in possible_plugins and path_segments[-1] == '__init__.py':
            plugin = path_segments[1]
            with zip_ref.open(file_info) as file:
                # extract identifier pattern matches
                for line in TextIOWrapper(file, encoding='utf-8'):
                    line_code = line.split('#', 1)[0].strip()  # ignore both inline and own line comments
                    pattern = registry_patterns.get(plugin)
                    if pattern:
                        matches = pattern.findall(line_code)
                        identifiers[plugin].update(matches)

    return identifiers


def under_identifier_limit(identifier_dict):
    """
    Ensures that the amount of plugins in the provided dictionary remains under the max plugin submission limit.
    """
    total_identifiers = sum(len(identifiers) for identifiers in identifier_dict.values())
    return total_identifiers <= PLUGIN_LIMIT


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
    job_name = "score_plugins"
    benchmark_string = '%20'.join(benchmarks)
    request_url = f"{jenkins_url}/job/{job_name}/buildWithParameters" \
                  f"?token=trigger2scoreAmodel" \
                  f"&user_id={request.user.id}" \
                  f"&email={request.user.email}" \
                  f"&new_benchmarks={benchmark_string}" \
                  f"&new_models={model_name}" \
                  f"&domain={domain}" \
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
            return render(request, 'benchmarks/login.html', {'form': LoginForm, "domain": self.domain, 'formatted': self.domain.capitalize()})
        else:
            context = get_context(request.user, domain=self.domain)
            context["has_user"] = True
            context["formatted"] = self.domain.capitalize()
            return render(request, 'benchmarks/profile.html', context)

    def post(self, request):
        user = authenticate(request, username=request.POST['username'], password=request.POST['password'])
        if user is not None:
            login(request, user)
            context = get_context(user, domain=self.domain)
            context["has_user"] = True
            context["formatted"] = self.domain.capitalize()
            return render(request, 'benchmarks/profile.html', context)
        else:
            context = {"Incorrect": True, 'form': LoginForm, "domain": self.domain, 'formatted': self.domain.capitalize()}
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

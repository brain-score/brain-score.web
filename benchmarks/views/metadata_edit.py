"""Propose repository changes with GitHub; never save edited metadata directly."""

import difflib
import secrets
import re
import hashlib
import base64
from copy import deepcopy
from functools import wraps
from urllib.parse import urlencode
import requests
from django.conf import settings
from django import forms
from django.core.cache import cache
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from benchmarks.models import FinalModelContext, ModelMetadataPublication
from benchmarks.model_metadata.github import GitHub, ProposalError, target, configured, allowed_path

DRAFT_TTL = 1800


def no_referrer(view):
    @wraps(view)
    def guarded(*args, **kwargs):
        response = view(*args, **kwargs)
        response["Referrer-Policy"] = "no-referrer"
        return response

    return guarded


def claim_submission_attempt(user_id):
    """Limit App write attempts across sessions and fail closed on cache errors."""
    try:
        for key, limit in [
            (f"metadata-submit:user:{user_id}", 10),
            ("metadata-submit:global", 100),
        ]:
            if cache.add(key, 1, 3600):
                continue
            if cache.incr(key) > limit:
                raise ProposalError(
                    "The metadata submission limit was reached. Please try again in an hour."
                )
    except ProposalError:
        raise
    except Exception:
        raise ProposalError(
            "Metadata submission is temporarily unavailable. Please retry later."
        ) from None


def contributor_required(view):
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_active:
            if request.headers.get("X-Metadata-Modal") == "1":
                return render(request, "benchmarks/metadata_login.html", status=401)
            return HttpResponseRedirect("/profile/")
        return view(request, *args, **kwargs)

    return guarded


def lookup(domain, id):
    if not configured():
        raise Http404("Metadata editing is not available yet.")
    try:
        config = target(domain)
    except ProposalError:
        raise Http404("Metadata editing is not available for this domain.") from None
    model = FinalModelContext.objects.filter(
        model_id=id, domain=domain, public=True
    ).first()
    if model is None:
        raise Http404
    publication = ModelMetadataPublication.objects.filter(
        domain__iexact=domain, identifier__iexact=model.name
    ).first()
    return model, publication, config


class ModelFolderForm(forms.Form):
    model_folder = forms.RegexField(
        regex=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,199}$",
        label="Model folder",
        help_text="The folder containing this model's registration in the repository models directory.",
    )


def unpublished_source(github, config, domain, folder, identifier):
    from benchmarks.model_metadata.proposal_source import optional_file, proposal_document
    from benchmarks.model_metadata.bootstrap import proposal_baseline

    form = ModelFolderForm({"model_folder": folder})
    if not form.is_valid():
        raise ProposalError("Choose a valid model folder.")
    path = config["model_root"].strip("/") + "/" + form.cleaned_data["model_folder"] + "/metadata.yaml"
    _, blob = optional_file(github, config["repository"], path, config["branch"])
    if blob is None:
        alternate = path[:-4] + "yml"
        _, alternate_blob = optional_file(github, config["repository"], alternate, config["branch"])
        if alternate_blob is not None:
            path = alternate
    document, content, blob = proposal_document(github, config, domain, path, identifier)
    document = proposal_baseline(document, content)
    return path, document, content, blob


def draft_for(request, key):
    draft = cache.get("metadata-draft:" + key)
    if (
        not draft
        or draft["owner"] != request.session.get("metadata_owner")
        or draft.get("user_id") != request.user.pk
    ):
        raise Http404("This proposal expired. Please start again.")
    return draft


@never_cache
@require_http_methods(["GET", "POST"])
@contributor_required
def edit(request, domain, id):
    model, publication, config = lookup(domain, id)
    from brainscore_core.metadata import (
        load,
        dump,
        validate,
        MetadataError,
    )
    from benchmarks.model_metadata.policy import protected_changes
    from benchmarks.model_metadata.bootstrap import document_revision
    from brainscore_core.metadata.contract import read_yaml
    from benchmarks.model_metadata.editor import (
        make_editor,
        editor_sections,
        describe_changes,
    )

    if publication is not None and publication.repository != config["repository"]:
        raise Http404
    if request.method == "GET" and request.headers.get("X-Metadata-Modal") != "1":
        return HttpResponseRedirect(f"/model/{domain}/{id}?metadata_edit=1")
    try:
        folder = request.GET.get("folder", "")
        discovery_message = ""
        if publication is None and not folder and request.method == "GET":
            from benchmarks.model_metadata.proposal_source import discover_model_folder

            try:
                with GitHub.reader(config) as github:
                    folder, discovery_message = discover_model_folder(github, config, model.name)
            except ProposalError:
                discovery_message = "Automatic folder lookup is temporarily unavailable. Choose the model folder below."
        choosing = publication is None and not folder
        if choosing:
            location_form = ModelFolderForm(request.POST if request.method == "POST" else None)
            if request.method != "POST" or not location_form.is_valid():
                return render(request, "benchmarks/metadata_destination.html", {
                    "form": location_form, "edit_url": request.path, "model": model,
                    "repository": config["repository"], "model_root": config["model_root"],
                    "discovery_message": discovery_message,
                })
            folder = location_form.cleaned_data["model_folder"]
        with GitHub.reader(config) as github:
            if publication is None:
                path, document, content, blob = unpublished_source(github, config, domain, folder, model.name)
                identifier = model.name
            else:
                path, identifier = publication.path, publication.identifier
                content, blob = github.file(publication.repository, path, config["branch"])
                document = load(content, domain)
        if identifier not in document["models"]:
            raise ProposalError(
                "The model moved in its repository. Its metadata mapping must be updated first."
            )
        entry = document["models"][identifier]
        conversion_models = (len(document["models"]) if publication is None and content
                             and read_yaml(content).get("schema_version") != "2.0" else 0)
        # Bind the submitted form to its starting revision without trusting a
        # client-supplied snapshot of field protections.
        submitting = request.method == "POST" and not choosing
        if submitting and request.POST.get("base_blob") != (blob or ""):
            raise ProposalError(
                "Metadata changed while you were editing. Reload before submitting."
            )
        if submitting and publication is None and request.POST.get("base_document_hash") != document_revision(document):
            raise ProposalError(
                "Metadata changed while you were editing. Reload before submitting."
            )
        form, groups, changes = make_editor(
            entry, request.POST if submitting else None
        )
        if submitting:
            changed = changes()
            if changed:
                updated, paths = changed
                candidate = deepcopy(document)
                candidate["models"][identifier] = updated
                try:
                    validate(candidate, domain)
                    if protected_changes(entry, updated):
                        raise MetadataError(
                            "This proposal changes protected metadata or its source classification."
                        )
                except MetadataError as exc:
                    form.add_error(None, str(exc))
                else:
                    owner = request.session.setdefault(
                        "metadata_owner", secrets.token_urlsafe(32)
                    )
                    request.session.modified = True
                    key = secrets.token_urlsafe(32)
                    cache.set(
                        "metadata-draft:" + key,
                        {
                            "owner": owner,
                            "user_id": request.user.pk,
                            "domain": domain,
                            "model_id": id,
                            "identifier": identifier,
                            "path": path,
                            "initial": publication is None,
                            "base_blob": blob,
                            "base_document_hash": document_revision(document) if publication is None else None,
                            "legacy_conversion_models": conversion_models,
                            "before": content,
                            "after": dump(candidate),
                            "reason": form.cleaned_data["reason"],
                            "paths": paths,
                            "changes": describe_changes(entry, updated, paths),
                        },
                        DRAFT_TTL,
                    )
                    return HttpResponseRedirect(
                        reverse("metadata-review", kwargs={"key": key})
                    )
        return render(
            request,
            "benchmarks/metadata_editor.html",
            {
                "model": model,
                "form": form,
                "groups": groups,
                "base_blob": blob or "",
                "base_document_hash": document_revision(document) if publication is None else "",
                "adding": blob is None,
                "edit_url": request.path + ("?" + urlencode({"folder": folder}) if publication is None else ""),
                **editor_sections(form, groups),
            },
        )
    except (ProposalError, MetadataError) as exc:
        if choosing:
            location_form.add_error(None, str(exc))
            return render(request, "benchmarks/metadata_destination.html", {
                "form": location_form, "edit_url": request.path, "model": model,
                "repository": config["repository"], "model_root": config["model_root"],
            }, status=409)
        return render(
            request,
            "benchmarks/metadata_editor.html",
            {"model": model, "error": str(exc)},
            status=409,
        )


@never_cache
@require_http_methods(["GET", "POST"])
@contributor_required
def review(request, key):
    if not configured():
        raise Http404
    draft = draft_for(request, key)
    if request.method == "GET" and request.headers.get("X-Metadata-Modal") != "1":
        return HttpResponseRedirect(
            f"/model/{draft['domain']}/{draft['model_id']}?"
            + urlencode({"metadata_proposal": key})
        )
    if request.method == "POST":
        # Bound nonce plus server-side storage protects both the account flow and
        # the exact proposal the user reviewed. No token is stored in cookies.
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(32)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        cache.set(
            "metadata-oauth:" + state,
            {
                "key": key,
                "owner": draft["owner"],
                "user_id": request.user.pk,
                "code_verifier": verifier,
            },
            600,
        )
        params = {
            "client_id": settings.METADATA_GITHUB_CLIENT_ID,
            "redirect_uri": settings.METADATA_GITHUB_CALLBACK_URL,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        url = "https://github.com/login/oauth/authorize?" + urlencode(params)
        if request.headers.get("X-Metadata-Modal") == "1":
            return JsonResponse({"redirect": url})
        return HttpResponseRedirect(url)
    diff = "\n".join(
        difflib.unified_diff(
            draft["before"].splitlines(),
            draft["after"].splitlines(),
            fromfile="Current metadata",
            tofile="Proposed metadata",
            lineterm="",
        )
    )
    return render(
        request,
        "benchmarks/metadata_review.html",
        {
            "draft": draft,
            "diff": diff,
            "review_url": request.path,
            "error": request.session.pop("metadata_error", ""),
        },
    )


@never_cache
@no_referrer
@require_GET
@contributor_required
@sensitive_variables()
def callback(request):
    if not configured():
        raise Http404
    state = request.GET.get("state", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", state):
        return HttpResponseBadRequest("Invalid or expired GitHub sign-in request.")
    flow = cache.get("metadata-oauth:" + state)
    if (
        not flow
        or not secrets.compare_digest(
            flow["owner"], request.session.get("metadata_owner", "")
        )
        or flow.get("user_id") != request.user.pk
        or not flow.get("code_verifier")
    ):
        return HttpResponseBadRequest("Invalid or expired GitHub sign-in request.")
    key = flow["key"]
    draft = draft_for(request, key)
    if not cache.add("metadata-oauth-used:" + state, True, 600):
        return HttpResponseBadRequest("Invalid or expired GitHub sign-in request.")
    cache.delete("metadata-oauth:" + state)
    try:
        if request.GET.get("error") or not request.GET.get("code"):
            raise ProposalError(
                "GitHub authorization was not completed. Your proposal is still available."
            )
        claim_submission_attempt(request.user.pk)
        response = requests.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": settings.METADATA_GITHUB_CLIENT_ID,
                "client_secret": settings.METADATA_GITHUB_CLIENT_SECRET,
                "code": request.GET["code"],
                "redirect_uri": settings.METADATA_GITHUB_CALLBACK_URL,
                "code_verifier": flow["code_verifier"],
            },
            headers={"Accept": "application/json"},
            timeout=(5, 20),
        )
        if response.status_code != 200:
            raise ProposalError("GitHub sign-in could not be completed. Please retry.")
        token = response.json().get("access_token")
        if not isinstance(token, str) or not token:
            raise ProposalError("GitHub did not authorize the request. Please retry.")
        identity = GitHub(token)
        try:
            github_login = identity.request("GET", "/user").get("login", "")
        finally:
            identity.session.close()
        if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", github_login):
            raise ProposalError("GitHub did not return a valid contributor account.")
        preview_url = None
        if draft.get("model_id"):
            preview_path = reverse(
                "metadata-preview",
                kwargs={
                    "domain": draft["domain"],
                    "id": draft["model_id"],
                    "number": 0,
                },
            )
            preview_url = (
                request.build_absolute_uri(preview_path).rsplit("/", 2)[0]
                + "/{number}/"
            )
        app = GitHub.installation(target(draft["domain"]))
        try:
            url = app.create_proposal(
                target(draft["domain"]),
                draft["path"],
                draft["base_blob"],
                draft["after"],
                draft["identifier"],
                draft["reason"],
                key,
                user_id=draft["user_id"],
                base_document_hash=draft.get("base_document_hash"),
                github_login=github_login,
                preview_url=preview_url,
                initial=draft.get("initial", False),
            )
        finally:
            app.session.close()
        expected_prefix = (
            "https://github.com/" + target(draft["domain"])["repository"] + "/pull/"
        )
        if (
            not url.startswith(expected_prefix)
            or not url[len(expected_prefix) :].isdigit()
        ):
            raise ProposalError("GitHub returned an unexpected pull request URL.")
        cache.delete("metadata-draft:" + key)
        return HttpResponseRedirect(url)
    except (ProposalError, requests.RequestException, ValueError) as exc:
        request.session["metadata_error"] = (
            str(exc)
            if isinstance(exc, ProposalError)
            else "GitHub is unavailable. Please retry; your proposal has been retained."
        )
        return HttpResponseRedirect(reverse("metadata-review", kwargs={"key": key}))


@never_cache
@require_GET
def preview(request, domain, id, number):
    model, publication, config = lookup(domain, id)
    from brainscore_core.metadata import load, MetadataError
    from benchmarks.model_metadata.policy import protected_changes
    from brainscore_core.metadata.storage import to_tables
    from benchmarks.model_metadata import repository

    visitor = (
        str(request.user.pk)
        if request.user.is_authenticated
        else request.META.get("REMOTE_ADDR", "unknown")
    )
    try:
        for label, limit in [
            ("global", 120),
            ("visitor:" + hashlib.sha256(visitor.encode()).hexdigest(), 30),
        ]:
            key = "metadata-preview-limit:" + label
            if cache.add(key, 1, 60):
                continue
            if cache.incr(key) > limit:
                response = HttpResponse(
                    "Too many previews. Please retry in a minute.", status=429
                )
                response["Retry-After"] = "60"
                return response
    except Exception:
        return HttpResponse(
            "Metadata previews are temporarily unavailable.", status=503
        )
    github = None
    try:
        github = GitHub.reader(config)
        pr = github.cached_request(f"/repos/{config['repository']}/pulls/{number}")
        if (
            pr["base"]["repo"]["full_name"] != config["repository"]
            or pr["base"]["ref"] != config["branch"]
        ):
            raise ProposalError("This PR does not target the model repository.")
        identifier = publication.identifier if publication is not None else model.name
        if publication is None:
            candidates = []
            for item in github.pages(f"/repos/{config['repository']}/pulls/{number}/files"):
                if not allowed_path(config, item["filename"]) or item["status"] in {"removed", "renamed"}:
                    continue
                candidate_content, _ = github.file(config["repository"], item["filename"], pr["head"]["sha"])
                if identifier in load(candidate_content, domain)["models"]:
                    candidates.append((item["filename"], candidate_content))
            if len(candidates) != 1:
                raise ProposalError("This PR must contain one metadata file for the selected model.")
            path, content = candidates[0]
            from benchmarks.model_metadata.proposal_source import proposal_document
            from benchmarks.model_metadata.bootstrap import proposal_baseline
            baseline, baseline_content, _ = proposal_document(github, config, domain, path, identifier)
            baseline = proposal_baseline(baseline, baseline_content)
            previous_entry = baseline["models"][identifier]
        else:
            content, _ = github.file(config["repository"], publication.path, pr["head"]["sha"])
            previous_entry = publication.document
        document = load(content, domain)
        entry = document["models"].get(identifier)
        if entry is None:
            raise ProposalError("This PR removes the selected model.")

        def scalar(value):
            if value is None:
                return ""
            if isinstance(value, bool):
                return "true" if value else "false"
            return str(value)

        tables = {
            name: [{key: scalar(value) for key, value in row.items()} for row in rows]
            for name, rows in to_tables(document).items()
        }
        card = repository._build_catalog(tables)[
            (domain.lower(), identifier.lower())
        ]
        card = repository.finalize_card_context(card, "proposal")
        card["source_label"] = "Unpublished proposal"
        return render(
            request,
            "benchmarks/metadata_preview.html",
            {
                "model": model,
                "model_metadata": card,
                "number": number,
                "revision": pr["head"]["sha"],
                "pr_url": f"https://github.com/{config['repository']}/pull/{number}",
                "protected": protected_changes(previous_entry, entry),
            },
        )
    except (ProposalError, MetadataError) as exc:
        return render(
            request,
            "benchmarks/metadata_preview.html",
            {"model": model, "error": str(exc)},
            status=409,
        )
    finally:
        if github is not None:
            github.session.close()

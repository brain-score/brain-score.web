"""The editing boundary must never publish an unmerged or unreviewed change."""

import importlib.util
from copy import deepcopy
from unittest import skipUnless
from unittest.mock import patch, Mock
from django.test import TestCase, SimpleTestCase, override_settings
from django.core.cache import cache
from benchmarks.models import (
    ModelMetadataRecord,
    ModelMetadataPublication,
    ModelMetadataRevision,
    User,
)
from benchmarks.model_metadata.github import ProposalError, GitHub
from benchmarks.model_metadata.publishing import publish_pull_request

REGISTRY = {
    "vision": {
        "repository": "brain-score/vision",
        "branch": "master",
        "model_root": "brainscore_vision/models",
    }
}
PATH = "brainscore_vision/models/example/metadata.yaml"


def document(value=100, kind="other"):
    return {
        "schema_version": "2.0",
        "domain": "vision",
        "models": {
            "example": {
                "model": {"parameter_count": value},
                "sources": {
                    "source": {"kind": kind, "url": "https://example.org/paper"}
                },
                "assertions": [
                    {
                        "path": "/model/parameter_count",
                        "status": "probable",
                        "sources": ["source"],
                    }
                ],
            }
        },
    }


class FakeGitHub:
    def __init__(self, doc=None, merged=True, blob="new"):
        from brainscore_metadata import dump

        self.content = dump(doc or document())
        self.blob = blob
        self.current = blob
        self.reviewer = ""
        self.pr = {
            "number": 10,
            "merged": merged,
            "base": {"ref": "master", "repo": {"full_name": "brain-score/vision"}},
            "merge_commit_sha": "a" * 40,
        }

    def request(self, *args, **kwargs):
        return self.pr

    def pages(self, *args, **kwargs):
        return [{"filename": PATH, "status": "modified"}]

    def file(self, repository, path, ref):
        return self.content, self.current if ref == "master" else self.blob

    def approved_reviewer(self, *args):
        return "maintainer"

    def override_reviewer(self, *args):
        return self.reviewer


@skipUnless(
    importlib.util.find_spec("brainscore_metadata"),
    "Install the shared metadata package to run editing integration tests",
)
@override_settings(MODEL_METADATA_REPOSITORIES=REGISTRY)
class PublicationTests(TestCase):
    def test_open_pr_cannot_write(self):
        with self.assertRaises(ProposalError):
            publish_pull_request("vision", 10, FakeGitHub(merged=False))
        self.assertFalse(ModelMetadataRecord.objects.exists())

    def test_merged_pr_without_current_maintainer_approval_cannot_write(self):
        api = FakeGitHub()
        api.approved_reviewer = lambda *args: ""
        with self.assertRaises(ProposalError):
            publish_pull_request("vision", 10, api)
        self.assertFalse(ModelMetadataRecord.objects.exists())

    def test_schema_downgrade_and_move_outside_model_directory_rejected(self):
        publish_pull_request("vision", 10, FakeGitHub())
        api = FakeGitHub()
        api.content = "example: {}"
        with self.assertRaises(ProposalError):
            publish_pull_request("vision", 10, api)
        api.pages = lambda *args: [
            {
                "filename": "elsewhere/metadata.yaml",
                "previous_filename": PATH,
                "status": "renamed",
            }
        ]
        with self.assertRaises(ProposalError):
            publish_pull_request("vision", 10, api)
        self.assertEqual(ModelMetadataRecord.objects.get().parameter_count, 100)

    def test_failure_in_second_file_rolls_back_entire_pr(self):
        api = FakeGitHub()
        second = PATH.replace("/example/", "/second/")
        api.pages = lambda *args: [
            {"filename": path, "status": "modified"} for path in [PATH, second]
        ]
        original = api.file

        def read(repo, path, ref):
            if path == second:
                raise ProposalError("Second file failed validation")
            return original(repo, path, ref)

        api.file = read
        with self.assertRaises(ProposalError):
            publish_pull_request("vision", 10, api)
        self.assertFalse(ModelMetadataRecord.objects.exists())
        self.assertFalse(ModelMetadataRevision.objects.exists())

    def test_large_counts_update_only_the_matching_domain(self):
        from benchmarks.models import User, Model, ModelMeta

        owner = User.objects.create(email="metadata-editor@example.invalid")
        vision = Model.objects.create(name="example", domain="vision", owner=owner)
        language = Model.objects.create(name="example", domain="language", owner=owner)
        ModelMeta.objects.create(model=language, total_parameter_count=7)
        publish_pull_request("vision", 10, FakeGitHub(document(70000000000)))
        self.assertEqual(
            ModelMeta.objects.get(model=vision).total_parameter_count, 70000000000
        )
        self.assertEqual(ModelMeta.objects.get(model=language).total_parameter_count, 7)

    def test_csv_cannot_overwrite_published_data(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from pathlib import Path
        from io import StringIO

        fixture = document()
        fixture["models"]["AdvProp_efficientnet-b2"] = fixture["models"].pop("example")
        publish_pull_request("vision", 10, FakeGitHub(fixture))
        with self.assertRaises(CommandError):
            call_command(
                "import_model_metadata",
                Path(__file__).resolve().parents[1] / "model_metadata" / "data",
                stdout=StringIO(),
            )
        self.assertEqual(ModelMetadataRecord.objects.get().parameter_count, 100)

    def test_success_retries_and_superseded_events(self):
        api = FakeGitHub()
        self.assertEqual(
            publish_pull_request("vision", 10, api)[0]["status"], "published"
        )
        self.assertEqual(ModelMetadataRecord.objects.get().parameter_count, 100)
        self.assertEqual(
            publish_pull_request("vision", 10, api)[0]["status"], "unchanged"
        )
        self.assertEqual(ModelMetadataRevision.objects.count(), 1)
        api.current = "newer"
        self.assertEqual(
            publish_pull_request("vision", 10, api)[0]["status"], "superseded"
        )
        self.assertEqual(ModelMetadataRevision.objects.count(), 1)

    def test_protected_sources_require_override_and_are_audited(self):
        publish_pull_request("vision", 10, FakeGitHub(document(kind="paper")))
        api = FakeGitHub(document(200))
        api.blob = api.current = "changed"
        api.pr["merge_commit_sha"] = "b" * 40
        with self.assertRaises(ProposalError):
            publish_pull_request("vision", 10, api)
        self.assertEqual(ModelMetadataRecord.objects.get().parameter_count, 100)
        api.reviewer = "maintainer"
        publish_pull_request("vision", 10, api)
        self.assertEqual(ModelMetadataRecord.objects.get().parameter_count, 200)
        self.assertEqual(
            ModelMetadataRevision.objects.order_by("-pk").first().override_reviewer,
            "maintainer",
        )

    def test_bootstrap_existing_data_requires_review(self):
        ModelMetadataRecord.objects.create(
            domain="vision", identifier="example", parameter_count=9
        )
        with self.assertRaises(ProposalError):
            publish_pull_request("vision", 10, FakeGitHub())
        self.assertEqual(ModelMetadataRecord.objects.get().parameter_count, 9)

    def test_failure_rolls_back_metadata_and_history(self):
        with patch(
            "benchmarks.model_metadata.publishing.ModelMetadataRevision.objects.get_or_create",
            side_effect=RuntimeError("failure"),
        ):
            with self.assertRaises(RuntimeError):
                publish_pull_request("vision", 10, FakeGitHub())
        self.assertFalse(ModelMetadataRecord.objects.exists())
        self.assertFalse(ModelMetadataPublication.objects.exists())

    def test_wrong_repository_domain_or_branch_rejected(self):
        for key, value in [
            ("ref", "unreviewed"),
            ("repo", {"full_name": "other/repository"}),
        ]:
            api = FakeGitHub()
            api.pr["base"][key] = value
            with self.assertRaises(ProposalError):
                publish_pull_request("vision", 10, api)
        api = FakeGitHub()
        api.content = api.content.replace("domain: vision", "domain: language")
        from brainscore_metadata import MetadataError

        with self.assertRaises(MetadataError):
            publish_pull_request("vision", 10, api)
        self.assertFalse(ModelMetadataRecord.objects.exists())


@skipUnless(
    importlib.util.find_spec("brainscore_metadata"),
    "Install the shared metadata package",
)
@override_settings(
    MODEL_METADATA_REPOSITORIES=REGISTRY,
    MODEL_METADATA_EDIT_ENABLED=True,
    METADATA_GITHUB_CLIENT_ID="client",
    METADATA_GITHUB_CLIENT_SECRET="secret",
    METADATA_GITHUB_APP_ID="1",
    METADATA_GITHUB_APP_PRIVATE_KEY="test-key",
    METADATA_GITHUB_CALLBACK_URL="http://testserver/metadata/github/callback/",
)
class EditorTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects._create_user(
            "metadata@example.org", "test-password", is_active=True
        )
        self.client.force_login(self.user)

    def test_anonymous_contributions_require_brainscore_login(self):
        self.client.logout()
        with patch("benchmarks.views.metadata_edit.GitHub.request") as github:
            for url in ["/model/vision/1/metadata/edit/", "/metadata/proposals/one/"]:
                self.assertEqual(self.client.get(url).url, "/profile/")
                response = self.client.post(url, HTTP_X_METADATA_MODAL="1")
                self.assertEqual(response.status_code, 401)
                self.assertContains(response, "Sign in to Brain-Score", status_code=401)
            self.assertEqual(
                self.client.get("/metadata/github/callback/?state=state&code=code").url,
                "/profile/",
            )
            github.assert_not_called()

    def test_draft_and_oauth_are_bound_to_brainscore_account(self):
        session = self.client.session
        session["metadata_owner"] = "owner"
        session.save()
        cache.set(
            "metadata-draft:one", {"owner": "owner", "user_id": self.user.pk + 1}, 300
        )
        cache.set(
            "metadata-oauth:state",
            {"key": "one", "owner": "owner", "user_id": self.user.pk + 1},
            300,
        )
        with patch("benchmarks.views.metadata_edit.GitHub.installation") as install:
            self.assertEqual(
                self.client.get("/metadata/proposals/one/").status_code, 404
            )
            self.assertEqual(
                self.client.get(
                    "/metadata/github/callback/?state=state&code=code"
                ).status_code,
                400,
            )
            install.assert_not_called()

    def test_disabled_feature_and_invalid_oauth_state(self):
        with override_settings(MODEL_METADATA_EDIT_ENABLED=False):
            self.assertEqual(
                self.client.get(
                    "/model/vision/1/metadata/edit/", HTTP_X_METADATA_MODAL="1"
                ).status_code,
                404,
            )
        with patch("benchmarks.views.metadata_edit.requests.post") as post:
            self.assertEqual(
                self.client.get(
                    "/metadata/github/callback/?state=bad&code=bad"
                ).status_code,
                400,
            )
            post.assert_not_called()

    def test_draft_is_bound_to_browser_session(self):
        cache.set("metadata-draft:one", {"owner": "other"}, 300)
        self.assertEqual(self.client.get("/metadata/proposals/one/").status_code, 404)

    def test_oauth_callback_creates_pr_without_metadata_writes(self):
        from brainscore_metadata import dump

        session = self.client.session
        session["metadata_owner"] = "owner"
        session["metadata_oauth_state"] = "state"
        session.save()
        cache.set(
            "metadata-draft:one",
            {
                "owner": "owner",
                "user_id": self.user.pk,
                "domain": "vision",
                "path": PATH,
                "base_blob": "blob",
                "after": dump(document()),
                "identifier": "example",
                "reason": "Correct the documented count.",
            },
            300,
        )
        cache.set(
            "metadata-oauth:state",
            {"key": "one", "owner": "owner", "user_id": self.user.pk},
            300,
        )
        response = Mock(status_code=200)
        response.json.return_value = {"access_token": "token"}
        with (
            patch(
                "benchmarks.views.metadata_edit.requests.post", return_value=response
            ),
            patch(
                "benchmarks.views.metadata_edit.GitHub.request",
                return_value={"login": "contributor"},
            ),
            patch("benchmarks.views.metadata_edit.GitHub.installation") as installation,
        ):
            installation.return_value.create_proposal.return_value = (
                "https://github.com/brain-score/vision/pull/10"
            )
            create = installation.return_value.create_proposal
            result = self.client.get("/metadata/github/callback/?state=state&code=code")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "https://github.com/brain-score/vision/pull/10")
        self.assertEqual(create.call_count, 1)
        self.assertEqual(create.call_args.kwargs["user_id"], self.user.pk)
        self.assertEqual(create.call_args.kwargs["github_login"], "contributor")
        self.assertFalse(ModelMetadataRecord.objects.exists())
        self.assertEqual(
            self.client.get(
                "/metadata/github/callback/?state=state&code=code"
            ).status_code,
            400,
        )

    def test_review_returns_to_model_and_modal_authorization_is_json(self):
        session = self.client.session
        session["metadata_owner"] = "owner"
        session.save()
        cache.set(
            "metadata-draft:one",
            {
                "owner": "owner",
                "user_id": self.user.pk,
                "domain": "vision",
                "model_id": 1,
                "identifier": "example",
                "before": "old",
                "after": "new",
                "reason": "Correction",
            },
            300,
        )
        direct = self.client.get("/metadata/proposals/one/")
        self.assertEqual(direct.url, "/model/vision/1?metadata_proposal=one")
        response = self.client.post(
            "/metadata/proposals/one/", HTTP_X_METADATA_MODAL="1"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.json()["redirect"].startswith(
                "https://github.com/login/oauth/authorize?"
            )
        )
        self.assertIn("state=", response.json()["redirect"])
        self.assertFalse(ModelMetadataRecord.objects.exists())

    def test_form_does_not_accept_protected_posted_value(self):
        from benchmarks.model_metadata.editor import make_editor

        entry = document(kind="paper")["models"]["example"]
        form, groups, changes = make_editor(entry)
        values = {
            name: field.initial
            for name, field in form.fields.items()
            if field.initial is not None
        }
        count = next(
            name
            for name, field in form.fields.items()
            if "parameter count" in field.label.lower()
            and "exact" not in field.label.lower()
        )
        values[count] = "999"
        values.update(
            reason="A correction",
            source_url="https://example.org/source",
            source_kind="other",
        )
        for group in groups:
            prefix = group["formset"].prefix
            values.update(
                {
                    prefix + "-TOTAL_FORMS": "0",
                    prefix + "-INITIAL_FORMS": "0",
                    prefix + "-MIN_NUM_FORMS": "0",
                    prefix + "-MAX_NUM_FORMS": "500",
                }
            )
        bound, _, _ = make_editor(entry, values)
        bound.is_valid()
        self.assertEqual(bound.cleaned_data[count], 100)

    def test_browser_form_roundtrip_and_preview_render_without_writes(self):
        from types import SimpleNamespace
        from brainscore_metadata import dump
        from bs4 import BeautifulSoup

        model = SimpleNamespace(
            name="example", model_id=1, domain="vision", public=True
        )
        publication = SimpleNamespace(
            repository="brain-score/vision",
            path=PATH,
            identifier="example",
            document=document()["models"]["example"],
        )
        with (
            patch(
                "benchmarks.views.metadata_edit.lookup",
                return_value=(model, publication, REGISTRY["vision"]),
            ),
            patch(
                "benchmarks.views.metadata_edit.GitHub.file",
                return_value=(dump(document()), "blob"),
            ),
        ):
            direct = self.client.get("/model/vision/1/metadata/edit/")
            self.assertEqual(direct.url, "/model/vision/1?metadata_edit=1")
            response = self.client.get(
                "/model/vision/1/metadata/edit/", HTTP_X_METADATA_MODAL="1"
            )
            self.assertContains(response, "Review changes")
            soup = BeautifulSoup(response.content, "html.parser")
            values = {}
            for field in soup.select("form input, form textarea, form select"):
                name = field.get("name")
                if not name or field.has_attr("disabled"):
                    continue
                if field.get("type") == "checkbox":
                    if field.has_attr("checked"):
                        values[name] = field.get("value", "on")
                elif field.name == "select":
                    choice = field.select_one("option[selected]") or field.select_one(
                        "option"
                    )
                    values[name] = choice.get("value", "")
                else:
                    values[name] = field.get("value", field.get_text())
            values.update(
                field_4="200",
                reason="Update documented count",
                source_url="https://example.org/new",
                source_kind="other",
                user_id="999999",
            )
            response = self.client.post(
                "/model/vision/1/metadata/edit/", values, HTTP_X_METADATA_MODAL="1"
            )
            self.assertEqual(response.status_code, 302)
            key = response.url.rstrip("/").rsplit("/", 1)[-1]
            self.assertEqual(
                cache.get("metadata-draft:" + key)["user_id"], self.user.pk
            )
            review = self.client.get(response.url, HTTP_X_METADATA_MODAL="1")
            self.assertContains(review, "parameter_count: 200")
            pr = {
                "base": {"repo": {"full_name": "brain-score/vision"}, "ref": "master"},
                "head": {"repo": {"full_name": "contributor/vision"}, "sha": "a" * 40},
            }
            with patch(
                "benchmarks.views.metadata_edit.GitHub.request", return_value=pr
            ):
                preview = self.client.get("/model/vision/1/metadata/preview/10/")
                self.assertContains(preview, "Unpublished proposal.")
                self.assertContains(preview, "a" * 40)
        self.assertFalse(ModelMetadataRecord.objects.exists())
        self.assertFalse(ModelMetadataPublication.objects.exists())

    def test_stale_file_rejected_before_branch_creation(self):
        from brainscore_metadata import dump

        api = GitHub("token")
        with (
            patch.object(api, "file", return_value=(dump(document()), "new-blob")),
            patch.object(api, "request") as request,
        ):
            with self.assertRaises(ProposalError):
                api.create_proposal(
                    REGISTRY["vision"],
                    PATH,
                    "old-blob",
                    dump(document(200)),
                    "example",
                    "reason",
                    "nonce",
                    user_id=12,
                    github_login="contributor",
                )
            request.assert_not_called()


@skipUnless(
    importlib.util.find_spec("brainscore_metadata"),
    "Install the shared metadata package",
)
class ConversionTests(SimpleTestCase):
    def test_all_catalog_values_survive_yaml_roundtrip(self):
        from pathlib import Path
        from benchmarks.model_metadata.catalog import read_catalog
        from brainscore_metadata import dump, load
        from brainscore_metadata.storage import from_tables, to_tables

        tables = read_catalog(
            Path(__file__).resolve().parents[1] / "model_metadata" / "data"
        )
        restored = to_tables(load(dump(from_tables(tables, "vision"))))
        for name, rows in tables.items():
            expected = deepcopy([row for row in rows if row["domain"] == "vision"])
            if name == "assertions":
                for row in expected:
                    if row["path"] == "/data/dataset_size":
                        row["path"] = "/data/summary"
            if name == "model_datasets":
                # YAML groups dataset roles; preserve ordering within each role.
                for items in (expected, restored[name]):
                    for row in items:
                        row.pop("ordinal")
            self.assertCountEqual(expected, restored[name], name)


@skipUnless(
    importlib.util.find_spec("brainscore_metadata"),
    "Install the shared metadata package",
)
class GitHubProposalTests(SimpleTestCase):
    def test_app_branch_commit_and_pr_payload_and_retry(self):
        from brainscore_metadata import dump
        import base64

        before, after = dump(document()), dump(document(200))
        api = GitHub("token")
        calls = []
        already_created = []

        def request(method, path, **kwargs):
            calls.append((method, path, kwargs))
            if path.endswith("/pulls") and method == "GET":
                return already_created
            if "/git/ref/heads/" in path:
                return {"object": {"sha": "head"}}
            if "/git/matching-refs/" in path:
                return []
            if path.endswith("/pulls") and method == "POST":
                already_created.append(
                    {
                        "html_url": "https://github.com/brain-score/vision/pull/10",
                        "number": 10,
                        "body": "Original reason",
                    }
                )
                return already_created[0]
            if method == "PATCH":
                already_created[0]["body"] = kwargs["json"]["body"]
            return {}

        with (
            patch.object(api, "request", side_effect=request),
            patch.object(api, "file", return_value=(before, "blob")),
        ):
            result = api.create_proposal(
                REGISTRY["vision"],
                PATH,
                "blob",
                after,
                "example",
                "Explain the count",
                "nonce",
                user_id=12,
                github_login="contributor",
                preview_url="https://example.org/model/vision/1/metadata/preview/{number}/",
            )
            again = api.create_proposal(
                REGISTRY["vision"],
                PATH,
                "blob",
                after,
                "example",
                "Explain the count",
                "nonce",
                user_id=12,
                github_login="contributor",
                preview_url="https://example.org/model/vision/1/metadata/preview/{number}/",
            )
        self.assertEqual(result, again)
        self.assertIn(
            "https://example.org/model/vision/1/metadata/preview/10/",
            already_created[0]["body"],
        )
        self.assertEqual(len([1 for method, path, kw in calls if method == "PATCH"]), 1)
        writes = [kw["json"] for method, path, kw in calls if method == "PUT"]
        self.assertEqual(len(writes), 1)
        self.assertEqual(base64.b64decode(writes[0]["content"]).decode(), after)
        self.assertEqual(writes[0]["message"], "docs(metadata): update model metadata")
        self.assertEqual(
            len(
                [
                    1
                    for method, path, kw in calls
                    if method == "POST" and path.endswith("/pulls")
                ]
            ),
            1,
        )
        self.assertFalse(
            any(
                path.endswith("/forks")
                or "/repos/contributor/" in path
                or path == "/user"
                for method, path, kw in calls
            )
        )
        pr_payload = next(
            kw["json"]
            for method, path, kw in calls
            if method == "POST" and path.endswith("/pulls")
        )
        self.assertEqual(pr_payload["base"], "master")
        self.assertTrue(pr_payload["head"].startswith("web_metadata_12_contributor_"))
        self.assertTrue(pr_payload["title"].endswith("(user:12)"))
        self.assertIn("Brain-Score user_id: 12", pr_payload["body"])
        self.assertIn("GitHub contributor: @contributor", pr_payload["body"])
        self.assertTrue(
            all(
                path.startswith("/repos/brain-score/vision/")
                for method, path, kw in calls
            )
        )

    def test_approval_must_be_current_human_non_author_and_not_revoked(self):
        api = GitHub()
        pr = {"number": 10, "user": {"login": "author"}, "head": {"sha": "current"}}
        approval = {
            "user": {"login": "reviewer", "type": "User"},
            "state": "APPROVED",
            "commit_id": "current",
        }
        with patch.object(api, "request", return_value={"permission": "write"}):
            for changed in (
                {"commit_id": "old"},
                {"user": {"login": "author", "type": "User"}},
                {"user": {"login": "bot", "type": "Bot"}},
            ):
                with patch.object(
                    api, "pages", return_value=[dict(approval, **changed)]
                ):
                    self.assertEqual(
                        api.approved_reviewer("brain-score/vision", pr), ""
                    )
            with patch.object(
                api,
                "pages",
                return_value=[approval, dict(approval, state="CHANGES_REQUESTED")],
            ):
                self.assertEqual(api.approved_reviewer("brain-score/vision", pr), "")
            with patch.object(api, "pages", return_value=[approval]):
                self.assertEqual(
                    api.approved_reviewer("brain-score/vision", pr), "reviewer"
                )

    def test_app_pr_submitter_cannot_approve_own_change(self):
        from brainscore_metadata.review import override

        api = GitHub()
        pr = {
            "number": 10,
            "user": {"login": "contributions[bot]", "type": "Bot"},
            "base": {"repo": {"full_name": "brain-score/vision"}},
            "head": {
                "sha": "current",
                "repo": {"full_name": "brain-score/vision"},
                "ref": api.proposal_branch("nonce", 12, "contributor"),
            },
            "labels": [{"name": "metadata-source-override"}],
        }
        review = {
            "user": {"login": "contributor", "type": "User"},
            "state": "APPROVED",
            "commit_id": "current",
        }
        with (
            patch.object(api, "pages", return_value=[review]),
            patch.object(api, "request", return_value={"permission": "admin"}),
        ):
            self.assertEqual(api.approved_reviewer("brain-score/vision", pr), "")
        with (
            patch("brainscore_metadata.review.pages", return_value=[review]),
            patch(
                "brainscore_metadata.review.api", return_value={"permission": "admin"}
            ),
        ):
            self.assertFalse(override(pr, "brain-score/vision"))

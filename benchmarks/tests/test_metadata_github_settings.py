from unittest.mock import Mock, patch
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from web.metadata_github_settings import load_metadata_github_settings
from benchmarks.model_metadata.github import GitHub, ProposalError, metadata_available


class MetadataGitHubSettingsTests(SimpleTestCase):
    def test_metadata_probe_handles_core_not_installed(self):
        with patch(
            "importlib.util.find_spec",
            side_effect=ModuleNotFoundError(name="brainscore_core"),
        ):
            self.assertFalse(metadata_available())

    def test_metadata_probe_handles_core_before_metadata_was_added(self):
        with patch("importlib.util.find_spec", return_value=None):
            self.assertFalse(metadata_available())

    def test_metadata_probe_does_not_hide_broken_installations(self):
        with patch(
            "importlib.util.find_spec", side_effect=ModuleNotFoundError(name="yaml")
        ):
            with self.assertRaises(ModuleNotFoundError):
                metadata_available()

    def fixture(self):
        return {
            "GITHUB_CLIENT_ID": "client",
            "GITHUB_CLIENT_SECRET": "credential",
            "GITHUB_APP_SLUG": "Brain-Score Contributions",
            "GITHUB_PUBLIC_LINK": "https://github.com/apps/brain-score-contributions",
            "GITHUB_CALLBACK_URL": "http://127.0.0.1:8767/metadata/github/callback/",
        }

    def test_disabled_unconfigured_site_does_not_read_aws(self):
        reader = Mock()
        config = load_metadata_github_settings({}, reader)
        reader.assert_not_called()
        self.assertEqual(config["METADATA_GITHUB_CLIENT_SECRET"], "")

    def test_secret_mapping_derives_slug_without_enabling_submission(self):
        reader = Mock(return_value=self.fixture())
        config = load_metadata_github_settings(
            {"METADATA_GITHUB_SECRET_NAME": "app-secret"}, reader
        )
        reader.assert_called_once_with("app-secret", "us-east-2")
        self.assertEqual(
            config["METADATA_GITHUB_APP_SLUG"], "brain-score-contributions"
        )
        self.assertEqual(config["METADATA_GITHUB_CLIENT_SECRET"], "credential")
        self.assertNotIn("MODEL_METADATA_EDIT_ENABLED", config)

    def test_environment_can_override_callback_for_deployment(self):
        callback = "https://dev.example.org/metadata/github/callback/"
        config = load_metadata_github_settings(
            {
                "METADATA_GITHUB_SECRET_NAME": "app-secret",
                "METADATA_GITHUB_CALLBACK_URL": callback,
            },
            lambda *args: self.fixture(),
        )
        self.assertEqual(config["METADATA_GITHUB_CALLBACK_URL"], callback)

    def test_installation_credentials_required_when_enabling_editing(self):
        values = dict(
            self.fixture(), GITHUB_APP_ID="123", GITHUB_APP_PRIVATE_KEY="private-key"
        )
        environ = {
            "METADATA_GITHUB_SECRET_NAME": "app-secret",
            "MODEL_METADATA_EDIT_ENABLED": "1",
        }
        config = load_metadata_github_settings(environ, lambda *args: values)
        self.assertEqual(config["METADATA_GITHUB_APP_ID"], "123")
        self.assertEqual(config["METADATA_GITHUB_APP_PRIVATE_KEY"], "private-key")
        with self.assertRaises(ImproperlyConfigured):
            load_metadata_github_settings(environ, lambda *args: self.fixture())

    def test_invalid_or_missing_configuration_fails_without_disclosing_values(self):
        for callback in [
            "http://example.org/metadata/github/callback/",
            "https://example.org/wrong/",
            "https://user:credential@example.org/metadata/github/callback/",
            "https://[",
        ]:
            with (
                self.subTest(callback=callback),
                self.assertRaises(ImproperlyConfigured) as error,
            ):
                load_metadata_github_settings(
                    {"METADATA_GITHUB_SECRET_NAME": "app-secret"},
                    lambda *args: dict(self.fixture(), GITHUB_CALLBACK_URL=callback),
                )
            self.assertNotIn("credential", str(error.exception))
        with self.assertRaises(ImproperlyConfigured):
            load_metadata_github_settings(
                {"METADATA_GITHUB_SECRET_NAME": "app-secret"},
                lambda *args: dict(self.fixture(), GITHUB_CLIENT_SECRET=""),
            )

    def test_secret_reader_error_is_sanitized(self):
        with self.assertRaises(ImproperlyConfigured) as error:
            load_metadata_github_settings(
                {"METADATA_GITHUB_SECRET_NAME": "app-secret"},
                Mock(side_effect=RuntimeError("credential")),
            )
        self.assertNotIn("credential", str(error.exception))


class InstallationTokenTests(SimpleTestCase):
    def test_signed_jwt_and_repository_scoped_installation_token(self):
        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PrivateFormat,
            NoEncryption,
        )

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
        ).decode()
        calls = []

        def request(client, method, path, **kwargs):
            claims = jwt.decode(
                client.session.headers["Authorization"].split(" ", 1)[1],
                key.public_key(),
                algorithms=["RS256"],
            )
            self.assertEqual(claims["iss"], "123")
            self.assertLessEqual(claims["exp"] - claims["iat"], 600)
            calls.append((method, path, kwargs))
            return {"id": 456} if method == "GET" else {"token": "installation-token"}

        with (
            override_settings(
                METADATA_GITHUB_APP_ID="123", METADATA_GITHUB_APP_PRIVATE_KEY=pem
            ),
            patch.object(GitHub, "request", request),
        ):
            api = GitHub.installation({"repository": "brain-score/vision"})
            reader = GitHub.installation(
                {"repository": "brain-score/vision"}, read_only=True
            )
        self.assertTrue(reader.read_only)
        self.assertEqual(
            calls[3][2]["json"]["permissions"],
            {"contents": "read", "pull_requests": "read"},
        )
        self.assertEqual(
            api.session.headers["Authorization"], "Bearer installation-token"
        )
        self.assertEqual(
            calls[0][:2], ("GET", "/repos/brain-score/vision/installation")
        )
        self.assertEqual(
            calls[1],
            (
                "POST",
                "/app/installations/456/access_tokens",
                {
                    "json": {
                        "repositories": ["vision"],
                        "permissions": {"contents": "write", "pull_requests": "write"},
                    }
                },
            ),
        )

    @override_settings(METADATA_GITHUB_APP_ID="123", METADATA_GITHUB_APP_PRIVATE_KEY="")
    def test_missing_key_never_calls_github(self):
        with (
            patch.object(GitHub, "request") as request,
            self.assertRaises(ProposalError),
        ):
            GitHub.installation({"repository": "brain-score/vision"})
        request.assert_not_called()

    def test_branch_only_uses_master_and_reuses_exact_ref(self):
        api = GitHub("installation-token")
        config = {"repository": "brain-score/vision", "branch": "master"}
        branch = api.proposal_branch("nonce", 12, "contributor")
        with patch.object(
            api,
            "request",
            side_effect=[
                [{"ref": "refs/heads/" + branch + "-other"}],
                {"object": {"sha": "master-head"}},
                {},
                [{"ref": "refs/heads/" + branch}],
            ],
        ) as request:
            self.assertEqual(
                api.create_branch(config, "nonce", 12, "contributor"), branch
            )
            self.assertEqual(
                api.create_branch(config, "nonce", 12, "contributor"), branch
            )
        writes = [call for call in request.call_args_list if call.args[0] != "GET"]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0].args, ("POST", "/repos/brain-score/vision/git/refs"))
        self.assertEqual(
            writes[0].kwargs["json"],
            {"ref": "refs/heads/" + branch, "sha": "master-head"},
        )

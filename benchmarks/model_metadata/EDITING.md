# Repository-backed metadata editing

Status: implemented behind disabled flags. The brain-score-contributions App
exists, and its credentials are stored in AWS Secrets Manager under
Brain-Score_Contributions_GitHub_App in us-east-2. Installation authentication,
repository access, and branch creation from master have been verified with a
signed-in Brain-Score contributor. The contributor has tested local PR submission;
merged-PR database publication still needs a dev rehearsal. The shared contract
lives in `brainscore_core.metadata`. Core #172 is merged, and repository-level
consumer pins are configured; website build configuration and converted plugin
files remain pending. Keep deployed PR submission and publication
workflows disabled until the rollout prerequisites are met.

## Behavior

The website edits schema 2.0 YAML in the model's registered repository. The form
and diff review open in a modal on the model card; Back preserves entered values,
and Close or Escape returns to the card. Contributions require an active,
signed-in Brain-Score account. A visitor reviews a diff and authorizes GitHub to
verify their GitHub username. The Contributions App then creates a branch and PR
directly in the domain repository using a repository-scoped installation token.
No personal fork or personal App installation is required.

The PR title uses `(user:123)`, matching model/plugin submissions. Its description
records `Brain-Score user_id: 123` and the verified GitHub username. The ID comes
from `request.user.pk`, never from submitted form data. Drafts and OAuth requests
are bound to both the browser session and that account; switching accounts or
logging out blocks submission. Branch names use
`web_metadata_<user-id>_<github-login>_<nonce-hash>/update_metadata`.
A proposal expires after 30 minutes. OAuth states are single-use and independently
bound so concurrent sign-ins cannot replace one another. User and installation
tokens are used in memory; they are not saved in cookies, the database, or cache.
Authorization uses S256 PKCE, and callback responses prohibit referrer leakage.
Submission attempts are limited to 10 per account and 100 overall per hour
through the shared cache; cache failures block submission.
The website never publishes the proposed metadata.

Paper and Hugging Face sources protect their fields, including mixed sources and
section-level assertions. Populated fields without classified evidence remain
locked. Empty undocumented fields can be filled with a supporting source.
The form cannot edit model identity, scoring configuration, or legacy adapters.
Protections are computed from approved evidence, not user-supplied source labels.

All publication requires a merged PR and a human maintainer's approval on its
current head revision. Changing protected values or evidence, or converting an
entry for the first time (including one without CSV data), additionally requires
the `metadata-source-override` label. The reviewer must differ from the PR author,
GitHub-linked commit authors/committers, and, for App-created metadata branches,
the contributor identified in the branch name. Changed values cannot keep or
claim verified status without an override. The editor marks changed fields
probable using field-specific assertions, preserving sibling evidence and
section assertions. Paper/Hugging Face protections still include section sources.
Publication is transactional across all affected files. Retries are idempotent;
an event whose file has since changed on the default branch is skipped.
Removing/moving a published file or downgrading its schema requires a separate
migration. The CSV importer refuses to overwrite repository-published records.
The publisher requires registered models in the matching domain and rejects
model additions/removals in existing v2 files. Initial publication preserves
existing legacy model metadata exactly; later edits project only changed,
representable facts. Unrelated edits cannot reset previously projected values.
The revision journal records the approving reviewer for ordinary and override
publications.
The merged metadata blob must match the approved PR head. A merge that combines
different metadata requires a fresh reviewed PR. Review independence fails closed
for incomplete commit lists and PRs with 250 or more commits, because GitHub caps
the commits API at 250 entries.

Generated PRs include a link to their preview. Previews are read-only at
`/model/<domain>/<model_id>/metadata/preview/<pr_number>/`, with the PR head SHA
displayed. Preview data is never stored in canonical metadata tables.
Editor and preview reads use repository-scoped App tokens with read permissions.
Tokens are reused in process memory, PR reads are cached for 30 seconds, and
immutable commit files for one hour. Mutable branch reads remain uncached for
stale-edit detection. Previews allow 30 requests per visitor and 120 overall per
minute through the shared cache and fail closed if that cache is unavailable.
Repository mappings must be published before a model's Edit link appears.

## Components

- Core: `brainscore_core.metadata` owns YAML validation, source policy, table
  conversion, and PR checks. It ships in the normal core distribution; there is
  no separate metadata package or PyPI release. Core loads its public scoring
  interfaces on demand, so metadata imports do not load scoring modules.
- Website: form, OAuth callback, previews, publication journal and worker.
- Vision and language: trusted `model-metadata-v2.yml` workflows validate PR
  data without checking out PR code and dispatch publication after merge.
- The existing core metadata endpoint rejects v2 writes; its adapter validates
  v2 files without publishing them. The legacy writer also refuses identifiers
  already owned by the publication journal, using the publisher's transaction
  lock. All metadata-file changes, including deletions and downgrades, are
  excluded from plugin auto-merge.

Schema 2.0 uses a document with `schema_version: "2.0"`, `domain`, and a
`models` mapping. Each model has grouped facts, structured `sources`, and
`assertions` referencing source IDs. Optional `legacy` values preserve existing
plugin metadata during conversion. The website's schema dialog uses the same
contract. The YAML download button remains disabled.

## Rollout order

Before production, upgrade and regression-test the website on a supported Django
release. Its current Django 4.1 dependency is unsupported; security support ended
December 1, 2023. See the [Django support table](https://www.djangoproject.com/download/#supported-versions).
Keep this framework upgrade separate from enabling metadata contributions.

1. Review and merge core's metadata module, v2 adapter, and auto-merge guards.
   Set `METADATA_CORE_REF` to the full approved 40-character core commit SHA in
   the website build environment, web CI/publishing environments, and domain
   repositories. Install core with `requirements-metadata.txt` on the website
   and publisher; domain validation workflows install the same pinned revision.
   Confirm scoring/submission workers have the core guards before converting
   plugin files. No separate metadata release is required.
2. Update `web_tests` before running the existing website unit-test suite. With
   `DJANGO_ENV=test`, `web.settings` explicitly selects `web_tests`, and
   `ExistingDatabaseTestRunner` skips database setup and migration entirely.
   Snapshot its fixtures, confirm the target database, inspect `showmigrations`
   and `migrate --plan`, and apply every pending migration through 0032. Do not
   assume it already has the metadata tables from 0027 through 0029. Run the
   website suite against that migrated database. Keep the separate disposable
   metadata CI tests and migration-history rehearsals as well; they do not update
   the shared `web_tests` database.

   Back up dev and rehearse migrations 0030 through 0032 with a
   production-shaped copy before applying them to dev. Repeat this process for
   each subsequent deployment database. 0030 adds publication/revision history; 0031 widens
   legacy parameter counts for language models. 0031 transactionally rebuilds
   the dependent final model context, preserving its definition, indexes,
   owner, explicit grants and comment. It takes table/view locks, so schedule
   the migration. It does not rewrite score rows. Rollback rejects counts
   that no longer fit a 32-bit integer. 0032 records the approving reviewer on
   every new publication revision; historical rows keep an empty reviewer.
3. Create/configure the GitHub App and worker environments described below.
   Deploy trusted workflows from the default branches. Keep all flags off.
4. Export the curated CSVs to a separate review directory:

   ```sh
   python scripts/export_model_metadata_yaml.py --domain vision \
     --checkout /path/to/vision --output /path/to/conversion-review
   ```

   This reads local files, preserves sibling model entries, and writes no
   repository or database changes. Review the report and classifications.
   The current rehearsal maps 61 of 78 curated models into 41 plugin files;
   17 identifiers have no exact metadata-file match. Resolve those mappings
   explicitly. Existing workbook evidence is marked unreviewed, never guessed
   to be a paper, Hugging Face, or another source.
5. Submit converted YAML through domain-repository PRs. Require the source
   override label and current-head maintainer approval for initial publication.
   Enable validation and the dev publisher, merge reviewed conversion PRs, then
   verify all metadata fields/child records against the CSV and the live cards.
6. Exercise one real contributor OAuth/App-branch/PR flow in dev, including a
   contributor outside the organization, source protection, stale edits,
   current-head approval, retries, and an open-PR preview. Confirm the website
   and worker use the same cache prefix and that leaderboard scores/ranks are
   unchanged. Only then set `MODEL_METADATA_EDIT_ENABLED=1`.
7. Repeat the reviewed deployment in staging/production. Retain the CSV catalog
   until complete YAML parity is verified. The plans folder is removed; this
   file is the operational documentation.

Migrations 0028 and 0029 and the CSV import were previously applied to shared dev.
Dev was backed up and migrated through 0032 on October 1, 2026 after a full local
restore rehearsal. All existing table rows, leaderboard scores and displayed
ranks, and the rebuilt view's definition/indexes/owner/grants/comment were
preserved. Publication workflow configuration and its end-to-end dev rehearsal
remain pending. Shared `web_tests` was backed up, rehearsed and migrated
through 0032 on October 1, 2026. Stored models/scores and displayed leaderboard
ranks were preserved. Its historical trend migration names were reconciled only
after checking the existing schema. See the infrastructure metadata rollout
record for the operation details and ordinary Jenkins test commands. Keep the
disposable PostgreSQL metadata suite for catalog tests that assume empty tables.

## Updating the core dependency intentionally

The initial approved core revision is
`30318623bae9846ca9d2dd7ae4573ad8d99ded9f` (core #172). This is configured as
repository variable `METADATA_CORE_REF` in web, vision, and language. It does not
automatically configure a deployed website build or create publisher environments.

Keep deployed consumers pinned rather than following core's `main` branch.
When intentionally adopting a metadata contract, policy, dependency, or other
needed core change, include a pin update in that change's rollout checklist:

1. Review/merge the core change and test its full SHA in a clean installation.
2. Rehearse compatible schema/database changes, metadata tests, and publication
   in dev before changing any defaults shared with production.
3. Update `METADATA_CORE_REF` in all three repositories and any web publishing
   environment overrides. Update and merge infrastructure's
   `ci/web/metadata-core-ref.txt` for the Jenkins PR and daily web runners.
   Revalidate affected open metadata PRs; GitHub variables do not automatically
   configure Jenkins workers.
4. Pass that same SHA to the website build, rebuild/redeploy, and verify the
   website, publisher, and validators agree. Updating a GitHub variable alone
   does not upgrade the running website.
5. Record the old/new SHAs and results. A rollback must also account for any
   database or YAML changes; reverting the pin alone does not undo those changes.

Unrelated core merges do not require advancing the metadata pin. The detailed
procedure is maintained in infrastructure's `web/metadata/rollout.md`.

The web metadata CI job always installs the approved core revision and fails if
the pin or import is invalid. It does not use the publication enable flag.
Jenkins runners install the same contract for checkouts containing
`requirements-metadata.txt`; older checkouts retain their existing test setup.
Installing core for tests does not enable editing or database publication.

## GitHub App

Use a public GitHub App so external contributors can authorize it. Configure an
exact HTTPS callback URL ending in `/metadata/github/callback/`. Enable the
user authorization flow, with expiring user tokens. Store the client secret
through the deployment secret mechanism, never in repository files.

The contributor App needs Contents read/write and Pull requests read/write,
installed on the registered domain repositories. Store its App ID and private
key in AWS Secrets Manager as `GITHUB_APP_ID` and `GITHUB_APP_PRIVATE_KEY` (full
PEM text). The server discovers the installation ID for the selected repository,
signs an RS256 JWT, and requests a token limited to that repository and these
permissions. The OAuth client secret identifies the user; it cannot replace the
App private key for installation authentication. Private keys and tokens must
never appear in logs or error messages.

References:
- [App installation authentication](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation)
- [User access token permissions](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app)

The workflow app needs Actions write on the web repository for dispatch and
Contents/Pull requests read on domain repositories for publication. Prefer a
separate automation app to avoid giving the contributor app Actions write.
Each workflow's `METADATA_APP_ID` and private key can refer to that automation app.
The source-policy check uses the workflow token with Checks write; it executes
only the pinned core validator, not plugin or PR code.

Website environment:

Use Python 3.11 and install the normal core distribution. For a pip deployment:

```sh
# METADATA_CORE_REF must be the full approved core commit SHA.
python -m pip install -r requirements.txt -r requirements-metadata.txt
python -c 'import brainscore_core.metadata'
python -m pip check
```

For the Docker image, pass `--build-arg METADATA_CORE_REF="$METADATA_CORE_REF"`.
Omitting the argument retains a website image without the optional editor
dependency. Invalid nonempty refs fail the build. Core's dependencies are installed,
but its scoring modules are not imported by metadata. The website and core use
the same `psycopg2-binary` distribution; avoid installing `psycopg2` alongside it
in new pip environments. Before the core changes are committed, local integration
can install a wheel built from the reviewed core working tree instead.

Set `METADATA_GITHUB_SECRET_NAME=Brain-Score_Contributions_GitHub_App` and
`METADATA_GITHUB_SECRET_REGION=us-east-2` to retrieve credentials at startup.
The loader maps `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`,
`GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`,
`GITHUB_APP_SLUG`, and `GITHUB_CALLBACK_URL` to the website variables below.
If the stored slug is a display name, it derives the slug from
`GITHUB_PUBLIC_LINK`. Individual environment variables override secret values.
Credential retrieval does not enable submission. Without a secret name, the
website continues to support environment-only configuration and makes no new
AWS request.

The current secret contains a local callback on port 8767. Override it with the
exact registered HTTPS callback when deploying to dev or production.
The website's IAM role needs GetSecretValue access to this secret; credentials
are kept in process memory and must not be printed.

- `MODEL_METADATA_EDIT_ENABLED`: default off; set `1` only after rehearsal.
- `METADATA_GITHUB_APP_SLUG`: public app slug for installation links.
- `METADATA_GITHUB_APP_ID`, `METADATA_GITHUB_APP_PRIVATE_KEY`: installation authentication.
- `METADATA_GITHUB_CLIENT_ID`, `METADATA_GITHUB_CLIENT_SECRET`: contributor identity.
- `METADATA_GITHUB_CALLBACK_URL`: exact registered URL.
- `MODEL_METADATA_REPOSITORIES`: JSON registry of domain to repository, branch,
  and model_root. Defaults are vision/master/brainscore_vision/models and
  language/main/brainscore_language/models.

Use shared Redis for the website's draft/OAuth cache across workers, secure
session/CSRF cookies, HTTPS, and normal edge request limits. Do not use a
per-process memory cache in deployment. Logs must not record callback query
strings or authorization headers.

## Publication environments

Create protected GitHub environments `metadata-dev`, `metadata-staging`, and
`metadata-production` in the web repository. Restrict deployment refs to reviewed
trusted code; require environment approval for production. Set the repository
variable `METADATA_V2_ENABLED=true` only after the approved core revision is
available and `METADATA_CORE_REF` is configured. The workflows reject missing,
branch-name, or abbreviated refs before installing dependencies.
The October 1, 2026 configuration review found no deployment environments in the
web repository. It also found that vision/master did not require the metadata
policy check, dismiss stale approvals, or require approval of the latest push.
Configure these protections and verify equivalent language settings before
enabling publication; application checks do not replace deployment protections.

Environment variables/secrets:

- `METADATA_CORE_REF`: full approved core commit SHA; use the same revision for
  website, publisher, and domain validators. This is configuration, not a secret.
- `METADATA_PUBLISH_ROLE_ARN`: AWS role assumed through GitHub OIDC, restricted
  to this repository/environment and the required secrets/network.
- `METADATA_APP_ID`, secret `METADATA_APP_PRIVATE_KEY`.
- `METADATA_DOMAIN_REPOSITORIES`: newline-separated repository names accessible
  to the automation app, initially `vision` and `language`.
- `MODEL_METADATA_REPOSITORIES`: explicit JSON registry.
- `METADATA_DATABASE_SECRET`: AWS secret name. For dev,
  `brainscore-1-ohio-cred-migrated`; set `METADATA_DATABASE_NAME=dev` separately.
  The instance identifier is never used as the database name.
- `METADATA_CACHE_SECRET`: the existing cache endpoint secret with host/port;
  `METADATA_CACHE_PREFIX`: exactly the website deployment's prefix.

The supplied worker cache adapter expects the existing TLS Redis endpoint
without password authentication. If the deployment requires an auth token,
configure the worker cache identically to the website before rollout.
The runner must reach PostgreSQL and Redis; use a trusted runner in the required
network if GitHub-hosted runners cannot. Do not expose the database to the public
internet just for this workflow.

Each domain repository also needs `METADATA_CORE_REF`, `METADATA_V2_ENABLED`, `METADATA_APP_ID`,
`METADATA_APP_PRIVATE_KEY`, `METADATA_WEB_PUBLISH_REF` (trusted web branch),
and `METADATA_PUBLISH_ENVIRONMENT`. Require the
`Metadata v2 source policy` check and a maintainer review in branch protection.
Reviews submitted or dismissed on same-repository PRs rerun validation.
For fork PRs, rerun with workflow_dispatch and the PR number, or reapply the
label; fork review-event tokens cannot write checks. A new head commit
invalidates the prior approval. Require approval of the most recent reviewable
push in branch protection as well: commit attribution alone cannot identify
every person who pushed a change. Do not grant the contribution App a bypass.
Dismiss stale approvals when new commits are pushed.
Restrict the publication environments and AWS trust policy to reviewed workflow
refs. The publisher requests only Contents/Pull requests read permissions.

To retry publication, dispatch `publish-model-metadata.yml` with domain, merged
PR number, and environment. Publication journal rows make retries safe. If
context refresh fails after publication, rerunning also refreshes the context
and invalidates caches. Inspect failures; disabling the editor alone does not
disable publication. Disable the repository workflow flag to stop publication.
Measure materialized-view refresh duration with production-shaped data before
rollout; the current refresh can block readers. Verify deployment and documentation
builds against the approved core revision before enabling contributions.

## Verification

With core's metadata module installed and isolated PostgreSQL settings:

```sh
python manage.py makemigrations --check --dry-run --settings=web.metadata_test_settings
python manage.py test benchmarks.tests.test_metadata_edit benchmarks.tests.test_model_metadata benchmarks.tests.test_compare_dashboard benchmarks.tests.test_migrations benchmarks.tests.test_models benchmarks.tests.test_ratelimit benchmarks.tests.test_score_trends --settings=web.metadata_test_settings --noinput
```

Core contract tests: `python -m unittest discover -s tests/test_metadata` from the
core checkout. Build core's wheel and test from outside that checkout as well, to
verify the installed distribution includes metadata without a separate dependency.
Web JavaScript tests: `npm run test:compare-dashboard`.
The unrelated full website suite requires its own populated benchmark fixtures
and full URL settings; the isolated metadata settings intentionally omit them.

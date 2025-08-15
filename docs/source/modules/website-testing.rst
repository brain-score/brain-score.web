.. _test-suite-overview:

Testing Suite Overview
######################

Brain-Score's web repository includes two complementary test suites:

* **UI/Integration tests** with ``pytest`` + ``Playwright`` that exercise the interactive **AG-Grid leaderboard** in a real browser.
* **Server/Template tests** with **Django’s** test client that validate core pages, endpoints, and a materialized-view query.

The goal here is to provide a quick overview—enough to run the tests locally/CI, understand what they cover, and know how to debug common issues.

Files and Scope
***************

``tests/test_ag_grid.py``
=========================
**Scope:** End-to-end UI tests for the Vision leaderboard (AG-Grid) via Playwright/Chromium.

Covers:

* Page load, default state assertions (e.g., rank/average sorting).
* Column sorting behavior (rank/model/average/neural/behavior/engineering).
* Filters and controls:

  - Expandable headers presence.
  - Benchmark include/exclude (single and multiple).
  - Architecture and Model Family dropdowns.
  - Numeric filters (parameter count, model size).
  - Region/species/task filters.
  - Public-data-only toggle.

* Utility features:

  - **Copy BibTeX** (all/subset).
  - **CSV export** (ZIP contains both leaderboard + plugin metadata).
  - **Search bar** filters models by substring.

``tests/test_views.py``
=======================
**Scope:** Fast server-side checks using Django’s test client (no migrations, no test DB cloning).

Covers:

* Basic page availability (home, vision, language, profile, explore, compare, tutorials).
* Language/vision model detail pages (status and key content blocks).
* Materialized view smoke test (``mv_final_model_context``) with a direct DB cursor.
* Vision leaderboard template sanity checks (buttons, search input).

Prerequisites & Installation
****************************

* Python environment with ``pytest``, ``Django``, ``playwright``, ``beautifulsoup4``.
* Playwright browsers installed (Chromium).

Example installation::

    pip install -r requirements.txt
    pip install pytest-playwright
    python -m playwright install --with-deps
    playwright install
    pip install bs4

Runtime services:

* A Django server must be reachable at ``http://127.0.0.1:8000`` for Playwright tests.

How to Run
**********

* Make sure you are in the ``brain-score.web`` root folder!
* Both tests are configured to use the ``web-tests`` DB. This is a separate copy of the production DB.


Run only Playwright UI tests::

    DJANGO_ENV=test python -m pytest benchmarks/tests/test_ag_grid.py -vv

Run only Django server tests::

    DJANGO_ENV=test DEBUG=True python manage.py runserver
    DJANGO_ENV=test python manage.py test benchmarks --keepdb -v 2

Playwright Tests
****************

**Representative checks**

* Sorting – default and click-to-sort columns.
* Filtering – benchmarks, architecture, model family, numeric sliders, region/species/task filters.
* Utilities – Copy BibTeX, CSV export, search filtering.

Django Tests
************

**Design**

* ``BaseTestCase`` disables Django’s test DB creation/teardown. This is used to force Django to use the ``web-tests``, and
  not create a separate testing DB by default.
* Uses Django’s test client for fast HTTP checks.

**Representative checks**

* Routing/status for all main pages.
* Content assertions via BeautifulSoup.
* Materialized view smoke test.
* Vision leaderboard template buttons and search input.

Markers and Flakiness
*********************

Some tests are marked ``@pytest.mark.skip`` with reasons like *"flaky on CI/EC2"*.
This was discovered after running on EC2 instances. Only seen on Playwright tests, and will be addressed in the
future.

Troubleshooting
***************

Playwright page never ready
===========================

* Ensure the Django server is running before tests.
* Increase waits if necessary.
* Confirm static assets/JS build is current.

Sorting tests flaky
===================

* Keep them skipped on CI or add more targeted waits locally.

CSV export test fails
=====================

* Ensure CI allows downloads and has a writable temp path.

Clipboard / Copy BibTeX
=======================

* May be restricted on CI—fallback reads from page JS.

Database / Materialized view
============================

* ``BaseTestCase`` expects the web_test DB and materialized view to exist.

Headed debugging
================

Run Playwright in headed mode with slow motion if you want to see the tests in action::

    p.chromium.launch(headless=False, slow_mo=300)


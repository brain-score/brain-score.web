.. _interface:

Brain-Score Website Developer Documentation
###########################################

.. image:: https://travis-ci.com/brain-score/brain-score.web.svg?branch=master
    :target: https://travis-ci.com/brain-score/brain-score.web

LocalHost Setup
***************

NOTE: Before beginning this process, contact one of the Brain-Score Administrators listed below and request an
``AWS_ACCESS_KEY_ID``, and an ``AWS_SECRET_ACCESS_KEY``.  You will need these to complete this process.

Brain Score Administrators:

1. Kartik Pradeepan: kpradeep@mit.edu
2. Mike Ferguson: mferg@mit.edu

Once you have these values, continue by ensuring you are using ``<= python@3.8``. You can do this by first checking if you have 3.8 installed::

    python3.8 --version

And if not, install it::

    sudo apt-get update
    sudo apt-get install python3.8

Next, create and activate a virtual environment::

    python3.8 -m venv <env_name>
    source <env_name>/bin/activate

Then, clone the repository and change to the ``brain-score.web`` directory::

    git clone https://github.com/brain-score/brain-score.web.git
    cd brain-score.web

Install dependencies (including node dependencies)::

    python3 -m pip install --upgrade pip
    pip3 install -r requirements.txt
    npm install --no-optional

Set up Database credentials (host and password) by first going to your home directory::

    cd ~

Then make a directory called ``.aws`` and ``cd`` into that directory ::

    mkdir .aws
    cd .aws

Then make a file called ``config``::

    touch config

Edit that file with ``nano config``, paste in the following, save, and exit (REMEMBER to replace ``AWS_ACCESS_KEY_ID``,
and ``AWS_SECRET_ACCESS_KEY`` with the values you received from a Brain Score admin (see note at top of page))::

    [default]
    region = us-east-1
    output = json
    aws_access_key_id = AWS_ACCESS_KEY_ID
    aws_secret_access_key = AWS_SECRET_ACCESS_KEY

Return to the ``brain-score.web`` directory and run the website in dev::

    DEBUG=True python manage.py runserver

View the website running locally by opening a browser to the following URL::

    http://localhost:8000


LocalHost tips and common errors:
=================================

1. Make sure to add ``127.0.0.1`` to hosts_list (``hosts_list.append("127.0.0.1")``) in ``settings.py`` line 53 when running locally.
2. Disable ``settings.py`` lines 181-193 that deal with SSL and cookies, as this causes some weird errors with login and profiles on the localhost site.
3. If you get an error about ``cannot connect to server`` when visiting your profile, you are probably on an ``https`` URL, which the localhost (and dev) sites do not support. To fix this, just use ``http``.
4. To change what database is used for the localhost, you can pass the string values ``prod``, ``dev``, ``dev_18072024`` and ``test`` in ``settings.py`` lines 150 and 138.
   Make sure you talk to another Brain-Score team member when using ``prod`` to make sure nothing major will happen!
5. **DO NOT** ever run migrations on dev or prod without talking to another Brain-Score team member as a check.
6. **DO NOT** ever run a ``flush`` command on ``prod`` or ``dev``!

LocalHost Setup Errors - Troubleshooting
========================================

Error installing sass with pip: ``ERROR: Failed building wheel for sass``

Fix: install ``cython`` and try again::

    pip3 install cython
    pip3 install -r requirements.txt

Error installing ``psycopg2``: ``Error: pg_config executable not found.``

Fix: install postgresql::

    brew install postgresql

Error running the server: ``/bin/sh: command not found: sass``

Fix: Make sure sass is installed correctly::

    npm install -g sass


Migrations
**********

If you need to apply migrations to the database (relevant after changing ``models.py``):

1. Check with a Brain-Score team member to double check what you are doing is needed/makes sense.
2. Run the following commands::

    python manage.py makemigrations  # creates the migration file
    python manage.py migrate         # applies the migration

If you run the ``migrate`` command (even on localhost) with your database set to ``dev`` or ``prod`` (as outlined in step 4 in the previous section), this WILL change the corresponding database with the migration you have. ``makemigrations`` itself will not alter the database but is just needed to create the actual migration file to be applied via ``migrate``.


Django Overview
***************

`Django <https://www.djangoproject.com>`_ follows the Model-View-Template (MVT) architecture:

MVT separates Brain-Score by dividing our application into three components: Models, Views, and Templates.

1. **Models**:
   Models in Django represent the structure of our database—this is separate from a Brain-Score concept of a model!
   Each model corresponds to a single database table and defines the fields and behaviors of the data we store.
   For example, we have a model ``User`` which contains fields such as ``email``, ``display_name``, ``is_staff``, etc. You can
   see a complete set of our models in the ``models.py`` file. Models in Django are Python classes that inherit from
   ``django.db.models.Model``, and each attribute of the model represents a database field. Django provides many field types
   and methods to interact with the database— for the most part, no Brain-Score dev should have to interact directly with
   the database, as Django handles all requests.

2. **Views**:
   Views in Django handle the logic behind the web pages:
   they process user requests, interact with models (Django models, not Brain-Score models!), and return responses. Our views
   are in the ``views`` folder, and many are located in the ``user.py`` file itself.
   There are two main types of views, and we use both in Brain-Score:

   * Function-Based Views (FBVs): Defined as Python functions.
   * Class-Based Views (CBVs): Defined as Python classes, providing more structure and reusability.

   Our ``views.py`` use CBVs extensively, including:

   * ``Activate`` View: Handles user activation via GET and POST requests.
   * ``Signup`` View: Manages user signup, rendering the signup form, and processing form submissions.
   * ``Login`` View: Handles user authentication, rendering the login form, and logging in users.
   * ``Upload`` View: Manages file uploads, ensuring proper validation and processing.

3. **Templates**:
   In Django, these are HTML files with placeholders for dynamic content. The placeholders are filled using
   the context data (see below). Django templates are a simple way to render dynamic content, looping, and conditional
   logic. Some examples in Brain-Score include:

   * ``Signup`` View renders ``signup.html`` with a context containing the signup form.
   * ``Login`` View renders ``login.html`` with a context containing the login form and error messages if authentication fails.
   * ``Upload`` View renders ``upload.html`` with a context containing the upload form and domain information.

   Our templates are contained in the folder ``benchmarks/templates``.

4. **Context**:
   Django uses ``contexts``. These are dictionaries containing data passed to a template; they allow dynamic
   rendering of HTML pages based on this data. For instance in Brain-Score:

   * In ``Signup`` View's ``post`` method, if the signup form is valid, it passes a context containing ``activation_email``,
     ``password_email``, and form to the ``login.html`` template.
   * In ``Profile`` View's ``get`` method, context is populated with user-specific data and passed to the ``profile.html`` template.

5. **GET vs POST request**:
   In Django, GET and POST requests serve different purposes. GET requests are used to retrieve data
   from the server without causing any changes, commonly used for fetching and displaying information. For example, a
   GET request to a view might render a form or display a list of items. POST requests, on the other hand, are used to
   submit data to the server, typically resulting in changes like creating or updating records. For example, a
   POST request to a view might handle form submissions, such as user registration or file uploads. Django provides
   built-in handling for these requests through its views, allowing us to define separate methods for GET and POST
   requests to manage different behaviors and responses efficiently.


Deployment
**********

See :ref:`website-deployment`

Jenkins and the Submission Process
**********************************

Jenkins Integration
===================

1. Jobs are triggered via calls to ``user.py``'s ``Upload`` Class for normal submissions, and ``resubmit`` for resubmissions.
2. For an overall GitHub workflow, visit the diagram `here <https://github.com/brain-score/vision/blob/master/docs/source/modules/brainscore_submission.png>`_.

Submission/Upload Process
=========================

1. Zip file is first checked for validity (``is_zip_valid``), then
2. Zip file is checked for originality and ownership (``submission_is_original``):

   * If a zip file is both valid and original, then the submission goes through.
   * If a zip file is not valid, a user will be redirected upon upload via the website to an error page.
3. If a zip is not original AND a user is not the owner, then the user will be redirected via website to an error page.
4. Zip files have the following constraints that provide a check (both ``Upload()`` and ``validate_zip()``):

   * They must be <50MB.
   * There must only be 1 plugin overall submitted (i.e., one model submitted at a time). The code itself can handle multiple plugins, but we artificially cap submissions at 1 plugin for Jenkins' sake.
   * They must not be the tutorial model (sanity check to make sure users do not submit the tutorial model).

Extraneous Website Information
******************************

1. Domain Name: Brain-Score's domain is managed via `United Domains <https://www.uniteddomains.com>`_. Contact a Team Member for the login information.
2. Brain-Score sends emails out from ``info.brainscore@gmail.com``. This email is its own separate Gmail account, and a Team Member can give the credentials out.
3. Brain-Score uses AWS Secrets Manager for sensitive login information and various credentials.
4. In order to be able to send emails out via Django, the website has its own specific login information for the email address mentioned in #2 above. See lines 57-59 of ``settings.py`` for more information.







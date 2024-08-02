[![Build Status](https://travis-ci.com/brain-score/brain-score.web.svg?branch=master)](https://travis-ci.com/brain-score/brain-score.web)

# Setup

Ensure you are using `<= python@3.8`

Create and activate a virtual environment

```
python3 -m venv <env_name>
source <env_name>/bin/activate
```

Install dependencies:

```
python3 -m pip install --upgrade pip
pip3 install -r requirements.txt
```

Install node dependencies: `npm install --no-optional`

Create a `.env` file and add `DB_HOST` and `DB_PASSWORD` vars for the development database.

Run server in dev: `DEBUG=True python manage.py runserver`


# LocalHost tips and common errors:
1. Make sure to add `127.0.0.1` to hosts_list (`hosts_list.append("127.0.0.1)`) in `settings.py` line 53 when running locally.
2. Disable `settings.py` lines 181-193 that deal with SSL and cookies, as this causes some weird errors with login and 
   and profiles on the localhost site. 
3. If you get an error about `cannot connect to server` when visiting your profile, you are probably on an `https` URL, 
   which the localhost (and dev) sites do not support. To fix this, just use `http`.
4. To change what database is used for the localhost, you can pass the string values `prod`, `dev`, `dev_18072024` and `test` in `settings.py`
   lines 150 and 138. 
   * Make sure you talk to another Brain-Score team member when using `prod` to make sure nothing major will happen!
5. IF you do not have credentials set up, the localhost will default to a (blank) `db.sqlite3` file. 
   * To set up database access, contact a Brain-Score team member. 
6. *DO NOT* ever run migrations on dev or prod without talking to another Brain-Score team member as a check. 
7. *DO NOT* ever run a `flush` command on `prod` or `dev`!

### LocalHost Setup Errors - Troubleshooting

Error installing sass with pip: `ERROR: Failed building wheel for sass`

Fix: install `cython` and try again: 
1. `pip3 install cython`
2. `pip3 install -r requirements.txt`


Error installing `psycopg2` Error: `pg_config executable not found.` --> Fix: install postgresql `brew install postgresql`

Error running the server: `/bin/sh: command not found: sass` --> Fix: `npm install -g sass`


## Migrations
If you need to apply migrations the database (relevant after changing `models.py`):
1. Check with a Brain-Score team member to double check what you are doing is needed/makes sense. 
2. `python manage.py makemigrations` -> creates the migration file
3. `python manage.py migrate` -> applies the migration

If you run the `migrate` command (even on localhost) with your database set to `dev` or `prod` (as outlined in step 4 in previous
section), then this WILL change the corresponding database with the migration you have. `makemigrations` itself will not alter the 
database, but is just needed to create the actual migration file to be applied via `migrate`. 


# Django Overview

[Django](https://www.djangoproject.com) follows the Model-View-Template (MVT) architecture: 
MVT separates Brain-Score by dividing our application into three components: 
Models handle the data and core logic, Views manage request processing and interaction with models, and Templates handle 
the front end.

1. Models in Django represent the structure of our database - this is separate from a Brain-Score concept of a model! 
   Each model corresponds to a single database table and defines the fields and behaviors of the data we store. 
   For example, we have a model `User` which contains fields such as `email`,  `display_name`, `is_staff`, etc. You can 
   see a complete set of our models in the `models.py` file. Models in Django are Python classes that inherit from 
   `django.db.models.Model`, and each attribute of the model represents a database field. Django provides many field types 
   and methods to interact with the database - for the most part, no Brain-Score dev should have to interact directly with 
   the database, as Django handles all requests. 

2. Views: Views in Django handle the logic behind the web pages:
   they process user requests, interact with models (Django models, not Brain-Score models!), and return responses. Our views
   are in the `views` folder, and many are located in the `user.py` file itself.
   There are two main types of views, and we use both in Brain-Score:

   * Function-Based Views (FBVs): Defined as Python functions.
   * Class-Based Views (CBVs): Defined as Python classes, providing more structure and reusability. 
   
   Our `views.py` use CBVs extensively, including: 

    * `Activate` View: Handles user activation via GET and POST requests.
    * `Signup` View: Manages user signup, rendering the signup form, and processing form submissions.
    * `Login` View: Handles user authentication, rendering the login form, and logging in users.
    * `Upload` View: Manages file uploads, ensuring proper validation and processing.
3. Templates: In Django, these are HTML files with placeholders for dynamic content. The placeholders are filled using 
   the context data (see below). Django templates are a simple way to render dynamic content, looping, and conditional 
   logic. Some examples in Brain-Score include:
   * `Signup` View renders `signup.html` with a context containing the signup form.
   * `Login` View renders `login.html` with a context containing the login form and error messages if authentication fails.
   * `Upload` View renders `upload.html` with a context containing the upload form and domain information.
   
    Our templates are contained in the folder `benchmarks/templates`.
4. Context: Django uses `contexts`. These are dictionaries containing data passed to a template; they allow dynamic 
   rendering of HTML pages based on this data. For instance in Brain-Score:
   * In `Signup` View's `post` method, if the signup form is valid, it passes a context containing `activation_email`, 
     `password_email`, and form to the `login.html` template.
   * In `Profile` View's `get` method, context is populated with user-specific data and passed to the `profile.html` template.

5. GET vs POST request: In Django, GET and POST requests serve different purposes. GET requests are used to retrieve data 
   from the server without causing any changes, commonly used for fetching and displaying information. For example, a 
   GET request to a view might render a form or display a list of items. POST requests, on the other hand, are used to 
   submit data to the server, typically resulting in changes like creating or updating records. For example, a 
   POST request to a view might handle form submissions, such as user registration or file uploads. Django provides 
   built-in handling for these requests through its views, allowing us to define separate methods for GET and POST 
   requests to manage different behaviors and responses efficiently.



## Export as static html

1. save website locally (Ctrl+S `http://localhost:8000`)
2. replace `http://localhost:8000/#*` with `#` (when saved with Chrome)
3. replace `http://localhost:8000/benchmarks/fixtures/img/icon.png` with `https://s3.amazonaws.com/www.brain-score.org/icon.png`
4. delete the svg from `<div id="brain-score">`[]
5. In `compare.js`, replace the static json link `/benchmarks/fixtures/fixture-scores-javascript.json`
    with `https://s3.us-east-2.amazonaws.com/brain-score.web-mock/fixture-scores-javascript.json`
    or `fixture-scores-javascript.json`
6. upload `Brain-Score.html`, `Brain-Score_files` and `fixture-scores-javascript.json` to S3
    (account id ****75, bucket www.brain-score.org)

# Deployment

See [deployment.md](deployment.md)


# Jenkins and the Submission Process

## Jenkins Integration
1. Jobs are triggered via calls to `user.py`'s `Upload` Class for normal submissions, and `resubmit` for resubmissions.
2. For an overall Github workflow, visit the diagram [here](https://github.com/brain-score/vision/blob/master/docs/source/modules/brainscore_submission.png).

## Submisison/Upload Process
1. Zip file is first checked for validity (`is_zip_valid`), then
2. Zip file is checked for originality and ownership (`submission_is_original`):
   * If a zip file is both valid and original, then the submission goes through. 
   * If a zip file is not valid, a user will be redirected upon upload via the website to an error page.
3. If a zip is not original AND a user is not the owner, then user will be redirected via website to an error page. 
4. Zip files have the following constraints that provide a check (both `Upload()` and `validate_zip()`):
   * They must be <50MB
   * There must only be 1 plugin overall submitted (i.e. one model submitted at a time). The code itself can handle 
     multiple plugins, but we artificially cap submissions at 1 plugin for Jenkins' sake.
   * They must not be the tutorial model (sanity check to make sure users do not submit tutorial model)
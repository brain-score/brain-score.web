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

# Extraneous Website Information
1. Domain Name: Brain-Score's domain is managed via [United Domains](https://www.uniteddomains.com). Contact a Team Member 
   for the login information.
2. Brain-Score sends emails out from `info.brainscore@gmail.com`. This email is it's own separate gmail account, and a 
   Team Member can give the credentials out. 
3. Brain-Score uses AWS Secrets Manager for sensitive login information and various credentials.
4. In Order to be able to send emails out via Django, the website has its own specific login information for the email a
   address mentioned in #2 above. See lines 57-59 of `settings.py` for more information.
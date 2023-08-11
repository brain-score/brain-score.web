[![Build Status](https://travis-ci.com/brain-score/brain-score.web.svg?branch=master)](https://travis-ci.com/brain-score/brain-score.web)

## Setup

Create and activate a virtual environment

Install dependencies: `pip install -r dev-requirements.txt`

Install node dependencies: `npm install --no-optional`

Run server in dev: `DEBUG=True python manage.py runserver &`


### Setup Errors - troubleshooting

Error installing sass with pip - `pip3 install cython` and try again

Error installing `psycopg2` Error: pg_config executable not found. - Install postgresql `brew install postgresql`

Error running the server  - `/bin/sh: command not found: sass` - `npm install -g sass`


## Update data
```
python manage.py flush

python manage.py loaddata benchmarks/fixtures/fixture-benchmarkreferences.json
python manage.py loaddata benchmarks/fixtures/fixture-benchmarktypes.json
python manage.py loaddata benchmarks/fixtures/fixture-benchmarkinstances.json
python manage.py loaddata benchmarks/fixtures/fixture-users.json
python manage.py loaddata benchmarks/fixtures/fixture-submissions.json
python manage.py loaddata benchmarks/fixtures/fixture-modelreferences.json
python manage.py loaddata benchmarks/fixtures/fixture-models.json
python manage.py loaddata benchmarks/fixtures/fixture-scores.json
```

If you need to reset the database and all migrations (relevant after changing `models.py`):
1. delete `db.sqlite3`
2. `python manage.py makemigrations`
3. `python manage.py migrate`


## Export as static html

1. save website locally (Ctrl+S `http://localhost:8000`)
2. replace `http://localhost:8000/#*` with `#` (when saved with Chrome)
3. replace `http://localhost:8000/benchmarks/fixtures/img/icon.png` with `https://s3.amazonaws.com/www.brain-score.org/icon.png`
4. delete the svg from `<div id="brain-score">`
5. In `compare.js`, replace the static json link `/benchmarks/fixtures/fixture-scores-javascript.json`
    with `https://s3.us-east-2.amazonaws.com/brain-score.web-mock/fixture-scores-javascript.json`
    or `fixture-scores-javascript.json`
6. upload `Brain-Score.html`, `Brain-Score_files` and `fixture-scores-javascript.json` to S3
    (account id ****75, bucket www.brain-score.org)

## Deployment

See [deployment.md](deployment.md)

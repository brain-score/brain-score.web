## Setup
Create environment: `conda env create -f environment.yml && conda activate brain-score.web`

Install node dependencies: `npm install`

Run server: `python manage.py runserver &`


## Update data
```
echo "from benchmarks.models import CandidateModel; CandidateModel.objects.all().delete()" | python manage.py shell
python manage.py loaddata static/benchmarks/fixture.json
```


## Export

1. save website locally (Ctrl+S `http://localhost:8000`)
2. replace `http://localhost:8000/#*` with `#` (when saved with Chrome)
3. replace `http://localhost:8000/static/benchmarks/img/icon.png` with `https://s3.amazonaws.com/www.brain-score.org/icon.png`
4. delete the svg from `<div id="brain-score">`
5. In `analysis.js`, replace the static json link `/static/benchmarks/fixture.json`
    with `https://s3.us-east-2.amazonaws.com/brain-score.web-mock/fixture.json`
    or `fixture.json`
6. upload `Brain-Score.html`, `Brain-Score_files` and `fixture.json` to S3

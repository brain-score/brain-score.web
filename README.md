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

1. replace `http://localhost:8000/#*` with `#`
2. replace `http://localhost:8000/static/benchmarks/img/icon.png` with `https://s3.amazonaws.com/www.brain-score.org/icon.png`
3. delete the svg from `<div id="brain-score">`
4. In `analysis.js`, replace the json static link 
    with `https://s3.us-east-2.amazonaws.com/brain-score.web-mock/fixture.json`
    or `fixture.json`
5. upload `Brain-Score.html`, `Brain-Score_files` and `fixture.json` to S3

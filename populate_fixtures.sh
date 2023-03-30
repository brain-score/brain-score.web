echo "Migrating new db changes..."
python manage.py makemigrations
python manage.py migrate
echo "Populating Fixtures now..."
python manage.py loaddata benchmarks/fixtures/fixture-benchmarkreferences.json
python manage.py loaddata benchmarks/fixtures/fixture-benchmarktypes.json
python manage.py loaddata benchmarks/fixtures/fixture-benchmarkmeta.json
python manage.py loaddata benchmarks/fixtures/fixture-benchmarkinstances.json
python manage.py loaddata benchmarks/fixtures/fixture-users.json
python manage.py loaddata benchmarks/fixtures/fixture-submissions.json
python manage.py loaddata benchmarks/fixtures/fixture-modelreferences.json
python manage.py loaddata benchmarks/fixtures/fixture-models.json
python manage.py loaddata benchmarks/fixtures/fixture-scores.json
echo "Installing language fixtures..."
python manage.py loaddata benchmarks/fixtures/fixture-benchmarktypes-language.json
python manage.py loaddata benchmarks/fixtures/fixture-benchmarkmeta-language.json
python manage.py loaddata benchmarks/fixtures/fixture-benchmarkinstances-language.json
python manage.py loaddata benchmarks/fixtures/fixture-users-language.json
python manage.py loaddata benchmarks/fixtures/fixture-models-language.json
python manage.py loaddata benchmarks/fixtures/fixture-scores-language.json
echo "Done. Check db.sqlite file."
"""Representative YAML inputs; recovery CSVs exist only in temporary test folders."""
import csv
from pathlib import Path


def fixture_document():
    from brainscore_core.metadata import load
    path = Path(__file__).parent / 'fixtures' / 'model_metadata.yaml'
    return load(path.read_text(), 'vision')


def fixture_tables():
    from brainscore_core.metadata.storage import to_tables
    return to_tables(fixture_document())


def write_catalog_fixture(directory):
    from benchmarks.model_metadata.catalog import TABLES, scalar_fields
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, rows in fixture_tables().items():
        fields = [field.name for field in scalar_fields(TABLES[name][0])]
        if name != 'models':
            fields = ['domain', 'identifier'] + fields
        with (directory / (name + '.csv')).open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: str(value).lower() if isinstance(value, bool)
                                 else '' if value is None else value
                                 for key, value in row.items()})
    return directory

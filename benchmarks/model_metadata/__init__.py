"""CSV-backed model-metadata catalog (six-table schema, see data/README.md).

The card reads from these CSVs directly; migration 0027 + the
``import_model_metadata`` management command move the same tables into the
database later without changing this package's public interface.
"""
from .repository import get_model_metadata, with_model_card_ids  # noqa: F401

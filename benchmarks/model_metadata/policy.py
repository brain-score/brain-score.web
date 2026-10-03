"""Website editing protects verified metadata values and their evidence."""


def editability(entry, path):
    from brainscore_core.metadata.policy import is_verified

    if is_verified(entry, path):
        return False, "Verified metadata is protected."
    return True, "Editable with a supporting source."


def protected_changes(before, after):
    from brainscore_core.metadata.policy import evidence, is_verified
    from brainscore_core.metadata.contract import FIELD_SPECS, LIST_PATHS, get_path

    changed = set()
    for path in (*FIELD_SPECS, *LIST_PATHS):
        if is_verified(before, path) and (
            get_path(before, path) != get_path(after, path)
            or evidence(before, path) != evidence(after, path)
        ):
            changed.add(path)
    return sorted(changed)

def get_different_items(d1, d2):
    """Return the set of keys and values that differ between two dicts."""
    keys1 = set(d1.keys())
    keys2 = set(d2.keys())
    diff_keys = keys1.symmetric_difference(keys2)

    diff_values = {k: (d1[k], d2[k]) for k in keys1.intersection(keys2) if d1[k] != d2[k]}

    return diff_keys, diff_values
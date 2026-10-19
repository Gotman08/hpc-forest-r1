import importlib.util
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples/marathon22"
sys.path.insert(0, str(EXAMPLES))
spec = importlib.util.spec_from_file_location("archive_preparation_for_test", EXAMPLES / "archive_preparation.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize("key", [k for k in module.SIZES if k != "2021-johnson"])
def test_prepared_cases_are_independent_and_bounded(key):
    sizes = module.SIZES[key][1]
    search = [module.text_input(key, n, 1000 + i) for i, n in enumerate(sizes)]
    confirmation = [module.text_input(key, n + (0 if key == "2021-sokoban" else 1), 2000 + i)
                    for i, n in enumerate(sizes)]
    assert not set(search) & set(confirmation)
    assert all(0 < len(x.encode()) < 128 * 1024 * 1024 for x in search + confirmation)


def test_no_false_2024_subjects_or_solutions():
    assert len(module.SUBJECTS) == 19
    assert not any(key.startswith("2024-") for key in module.SUBJECTS)
    assert module.text_input("2023-count", 17, 7).splitlines()[0].startswith("17 ")


def test_matrix_subject_filter_preserves_preparation_failures():
    from archive_matrix import select_subjects
    records = {"2023-count": {"status": "ready"}, "2020-jacobi": {"status": "preparation_failed"}}
    assert select_subjects(records) == ["2023-count"]
    assert select_subjects(records, ["2020-jacobi"]) == []
    with pytest.raises(ValueError):
        select_subjects(records, ["2024-count"])

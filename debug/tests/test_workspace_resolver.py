import os
import tempfile
from pathlib import Path

import pytest

from tarno.core.workspace import (
    get_workspace_roots,
    is_allowed,
    resolve_for_read,
    resolve_for_write,
    search_all_roots,
)


@pytest.fixture
def sample_workspace():
    with tempfile.TemporaryDirectory() as tmp:
        root_a = Path(tmp) / "a"
        root_b = Path(tmp) / "b"
        root_a.mkdir()
        root_b.mkdir()
        (root_a / "shared.txt").write_text("a")
        (root_b / "shared.txt").write_text("b")
        (root_b / "nested").mkdir()
        (root_b / "nested" / "file.txt").write_text("nested")
        workspace = {
            "id": "ws",
            "name": "test",
            "folders": [
                {"id": "1", "name": "A", "path": str(root_a)},
                {"id": "2", "name": "B", "path": str(root_b)},
            ],
            "root_paths": [str(root_a), str(root_b)],
            "include_patterns": ["**/*"],
            "exclude_patterns": [],
        }
        yield workspace


def test_get_workspace_roots(sample_workspace):
    roots = get_workspace_roots(sample_workspace)
    assert len(roots) == 2
    assert all(r.is_absolute() for r in roots)


def test_resolve_for_read_finds_file_in_any_root(sample_workspace):
    path = resolve_for_read("shared.txt", sample_workspace)
    assert path is not None
    assert path.name == "shared.txt"


def test_resolve_for_read_prefers_longest_root(sample_workspace):
    # root_b has a 'nested' directory that also exists under a hypothetical longer path?
    # Here we verify it can locate the nested file.
    path = resolve_for_read("nested/file.txt", sample_workspace)
    assert path is not None
    assert path.name == "file.txt"


def test_resolve_for_write_uses_longest_prefix(sample_workspace):
    # Writing nested/file.txt should land in root_b because 'nested' exists there.
    path = resolve_for_write("nested/new_file.txt", sample_workspace)
    assert path is not None
    assert "b" in Path(path).parts
    assert path.name == "new_file.txt"


def test_resolve_for_write_defaults_to_primary_root(sample_workspace):
    # A brand new top-level file goes to the first root.
    path = resolve_for_write("brand_new.txt", sample_workspace)
    assert path is not None
    assert path.name == "brand_new.txt"
    assert sample_workspace["root_paths"][1] not in str(path)


def test_is_allowed_blocks_outside_roots_and_home():
    workspace = {"id": "ws", "name": "test", "folders": [], "root_paths": [], "include_patterns": [], "exclude_patterns": []}
    assert is_allowed(Path("C:/Windows/system32"), workspace) is False


def test_is_allowed_allows_workspace_root_outside_home(sample_workspace):
    root = get_workspace_roots(sample_workspace)[0]
    assert is_allowed(root / "shared.txt", sample_workspace) is True


def test_search_all_roots_finds_matches(sample_workspace):
    matches = search_all_roots("", "*.txt", sample_workspace)
    assert len(matches) >= 3


def test_search_all_roots_respects_directory(sample_workspace):
    matches = search_all_roots("nested", "*.txt", sample_workspace)
    assert len(matches) == 1

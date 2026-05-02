from contextmesh.indexer.repo_indexer import find_symbol, list_files, list_symbols, reindex


def test_reindex_persists_files_and_symbols(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.py").write_text("def foo(x):\n    return x + 1\n")
    (tmp_path / "b.py").write_text("class Bar:\n    def hi(self):\n        return 1\n")

    stats = reindex(tmp_path)
    assert stats.scanned >= 2
    assert stats.new >= 2
    assert stats.symbols >= 3

    files = list_files()
    assert any(f.path.endswith("a.py") for f in files)
    assert all(f.language == "python" for f in files if f.path.endswith(".py"))


def test_reindex_is_delta_aware(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.py").write_text("def foo(): pass\n")

    reindex(tmp_path)
    stats2 = reindex(tmp_path)
    assert stats2.unchanged >= 1
    assert stats2.changed == 0
    assert stats2.new == 0


def test_reindex_drops_deleted_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    f = tmp_path / "a.py"
    f.write_text("def foo(): pass\n")
    reindex(tmp_path)
    f.unlink()
    stats = reindex(tmp_path)
    assert stats.removed == 1
    assert list_symbols("a.py") == []


def test_find_symbol(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.py").write_text("def needle(): pass\n")
    reindex(tmp_path)
    matches = find_symbol("needle")
    assert len(matches) == 1
    assert matches[0].name == "needle"

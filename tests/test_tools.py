import pytest

from contextmesh.agent.tools import expand_symbol


def test_expand_symbol(tmp_path):
    f = tmp_path / "dummy.py"
    f.write_text(
        "import os\n"
        "\n"
        "def target_function(x):\n"
        "    y = x + 1\n"
        "    return y\n"
        "\n"
        "def other_function():\n"
        "    pass\n"
    )

    body = expand_symbol(str(f), "target_function")
    assert body is not None
    assert "def target_function(x):" in body
    assert "    y = x + 1" in body
    assert "    return y" in body
    assert "def other_function" not in body


def test_expand_symbol_disambiguates_by_parent(tmp_path):
    f = tmp_path / "dup.py"
    f.write_text(
        "class A:\n"
        "    def method(self):\n"
        "        return 'A'\n"
        "\n"
        "class B:\n"
        "    def method(self):\n"
        "        return 'B'\n"
    )

    a_body = expand_symbol(str(f), "method", parent="A")
    b_body = expand_symbol(str(f), "method", parent="B")
    assert "return 'A'" in a_body
    assert "return 'B'" in b_body


def test_expand_symbol_not_found(tmp_path):
    f = tmp_path / "dummy.py"
    f.write_text("def foo(): pass\n")
    assert expand_symbol(str(f), "bar") is None


def test_expand_symbol_resolves_project_relative_from_subdir(tmp_path, monkeypatch):
    """Regression: a project-relative path (the form stored in SymbolPackets)
    must resolve when the caller's cwd is a subdirectory of the project.

    This was silently broken for the focus mechanism — see Test 4 in the
    real-world results: ``expand_symbol`` returned ``None`` when the
    consumer ran from a different cwd than the indexer, so the body never
    got inlined.
    """
    project = tmp_path / "myproj"
    project.mkdir()
    (project / ".contextmesh").mkdir()
    (project / "src").mkdir()
    src = project / "src" / "auth.py"
    src.write_text("def verify(token):\n    return token == 'ok'\n")

    deep = project / "src" / "nested" / "subdir"
    deep.mkdir(parents=True)
    monkeypatch.chdir(deep)

    body = expand_symbol("src/auth.py", "verify")
    assert body is not None
    assert "return token == 'ok'" in body


def test_expand_symbol_returns_none_for_truly_missing_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert expand_symbol("does/not/exist.py", "foo") is None

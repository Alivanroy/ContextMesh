from contextmesh.indexer.fingerprint import detect_language, get_file_hash, index_file
from contextmesh.indexer.tree_sitter_parser import parse_python_source


def test_get_file_hash(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello world")
    assert get_file_hash(str(f)) == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


def test_index_file(tmp_path):
    content = "print('hello')\nprint('world')"
    f = tmp_path / "script.py"
    f.write_text(content)

    result = index_file(str(f))
    assert result["path"] == str(f)
    assert result["language"] == "python"
    assert result["size"] == len(content.encode("utf-8"))
    assert result["line_count"] == 2
    assert "sha256" in result


def test_detect_language():
    assert detect_language("foo.py") == "python"
    assert detect_language("foo.tsx") == "typescript"
    assert detect_language("foo.go") == "go"
    assert detect_language("foo.unknown") == "unknown"


def test_tree_sitter_parser():
    source = b"""import os
from typing import List

class Parser:
    \"\"\"A simple parser\"\"\"
    def parse(self, text: str) -> None:
        \"\"\"Parses the text\"\"\"
        pass

def main():
    pass
"""
    result = parse_python_source(source)
    imports = result["imports"]
    symbols = result["symbols"]

    assert len(imports) == 2
    assert imports[0].module == "os"
    assert imports[1].module == "typing"

    assert len(symbols) == 3
    assert symbols[0].symbol_type == "class"
    assert symbols[0].name == "Parser"
    assert symbols[1].symbol_type == "method"
    assert symbols[1].name == "parse"
    assert symbols[1].parent == "Parser"
    assert symbols[1].signature == "def parse(self, text: str) -> None"
    assert symbols[2].symbol_type == "function"
    assert symbols[2].name == "main"
    assert symbols[2].parent is None

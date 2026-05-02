"""Tree-sitter Python parser. Extracts symbols and imports.

Other languages are stubbed: hooking up tree-sitter-typescript, tree-sitter-go,
etc. is a matter of adding their grammars and a small ``walk`` per language.
"""
from __future__ import annotations

from typing import Optional

import tree_sitter
import tree_sitter_python

from contextmesh.packets.schema import ExtractedImport, ExtractedSymbol

PY_LANGUAGE = tree_sitter.Language(tree_sitter_python.language())


def get_parser() -> tree_sitter.Parser:
    return tree_sitter.Parser(PY_LANGUAGE)


def _end_line(node: tree_sitter.Node) -> int:
    """Convert tree-sitter's end_point (position right after last byte) to a
    1-indexed inclusive line number."""
    end = node.end_point
    line = end.row + 1 if end.column > 0 else end.row
    return max(node.start_point.row + 1, line)


def _docstring(node: tree_sitter.Node) -> Optional[str]:
    for child in node.children:
        if child.type != "block":
            continue
        if not child.children:
            return None
        first = child.children[0]
        if first.type == "expression_statement" and first.children:
            inner = first.children[0]
            if inner.type == "string":
                return inner.text.decode("utf-8", errors="replace")
    return None


def _import_module(node: tree_sitter.Node) -> Optional[str]:
    """Best-effort module-name extraction for import statements."""
    if node.type == "import_from_statement":
        mod = node.child_by_field_name("module_name")
        if mod is not None:
            return mod.text.decode("utf-8", errors="replace")
    elif node.type == "import_statement":
        for child in node.children:
            if child.type in {"dotted_name", "aliased_import"}:
                if child.type == "aliased_import":
                    name = child.child_by_field_name("name")
                    if name is not None:
                        return name.text.decode("utf-8", errors="replace")
                return child.text.decode("utf-8", errors="replace")
    return None


def parse_python_source(source_code: bytes) -> dict:
    parser = get_parser()
    tree = parser.parse(source_code)

    symbols: list[ExtractedSymbol] = []
    imports: list[ExtractedImport] = []

    def walk(node: tree_sitter.Node, parent_name: Optional[str] = None) -> None:
        if node.type in ("import_statement", "import_from_statement"):
            imports.append(ExtractedImport(
                statement=node.text.decode("utf-8", errors="replace"),
                module=_import_module(node),
                line=node.start_point.row + 1,
            ))
            return

        if node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = name_node.text.decode("utf-8")
                superclasses = node.child_by_field_name("superclasses")
                signature = f"class {name}{superclasses.text.decode('utf-8') if superclasses else ''}:"
                symbols.append(ExtractedSymbol(
                    symbol_type="class",
                    name=name,
                    signature=signature,
                    start_line=node.start_point.row + 1,
                    end_line=_end_line(node),
                    docstring=_docstring(node),
                    parent=parent_name,
                ))
                for child in node.children:
                    if child.type == "block":
                        walk(child, parent_name=name)
            return

        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = name_node.text.decode("utf-8")
                params = node.child_by_field_name("parameters")
                ret = node.child_by_field_name("return_type")
                params_str = params.text.decode("utf-8") if params else "()"
                ret_str = f" -> {ret.text.decode('utf-8')}" if ret else ""
                sym_type = "method" if parent_name else "function"
                symbols.append(ExtractedSymbol(
                    symbol_type=sym_type,
                    name=name,
                    signature=f"def {name}{params_str}{ret_str}",
                    start_line=node.start_point.row + 1,
                    end_line=_end_line(node),
                    docstring=_docstring(node),
                    parent=parent_name,
                ))
                for child in node.children:
                    if child.type == "block":
                        walk(child, parent_name=f"{parent_name}.{name}" if parent_name else name)
            return

        for child in node.children:
            walk(child, parent_name)

    walk(tree.root_node)
    return {"symbols": symbols, "imports": imports}

#!/usr/bin/env python3
"""Scan a repository and emit a deterministic, self-contained HTML code map.

Python files are parsed with `ast` (classes/functions, imports, relative-import
resolution); JS/ESM files with regexes (imports, exports). The output is
byte-identical for identical inputs: no timestamps, no absolute paths, every
list sorted. Stdlib only; portable to any project (packages are auto-discovered
from --root, nothing repo-specific is hardcoded).

Usage:
    python3 build_code_map.py --root . --out docs/code-map.html [--check]
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import posixpath
import re
import sys

DEFAULT_EXCLUDES = {
    "node_modules", "third_party", "vendor", "outputs", "dist", "build",
    "venv", "env", "__pycache__",
}

# ---------------------------------------------------------------- discovery


def discover(root: str, includes: list[str], excludes: set[str]) -> tuple[list[str], list[str]]:
    """Return sorted repo-relative posix paths of (.py files, .js/.mjs files)."""
    py: list[str] = []
    js: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = sorted(
            d for d in dirnames if d not in excludes and not d.startswith(".")
        )
        for name in sorted(filenames):
            rel = os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, "/")
            if includes and not any(
                rel == p or rel.startswith(p.rstrip("/") + "/") for p in includes
            ):
                continue
            if name.endswith(".py"):
                py.append(rel)
            elif name.endswith((".js", ".mjs")):
                js.append(rel)
    return sorted(py), sorted(js)


def build_module_map(py_files: list[str]) -> dict[str, str]:
    """Map dotted module names to file paths for every importable .py file.

    A file is importable when every ancestor directory up to the root has an
    __init__.py (namespace packages are out of scope). Root-level modules map
    as bare names; a package maps to its __init__.py.
    """
    file_set = set(py_files)
    mmap: dict[str, str] = {}
    for p in py_files:
        dir_parts = p.split("/")[:-1]
        if not all(
            "/".join(dir_parts[: i + 1]) + "/__init__.py" in file_set
            for i in range(len(dir_parts))
        ):
            continue
        parts = p[: -len(".py")].split("/")
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if parts:
            mmap[".".join(parts)] = p
    return mmap


# ---------------------------------------------------------------- edge store


class EdgeStore:
    """Accumulates and merges import edges for one source file."""

    def __init__(self) -> None:
        self.internal: dict[str, dict] = {}   # target path -> edge
        self.external: dict[str, dict] = {}   # module name -> entry

    def add_internal(self, target: str, symbols: list[str], lineno: int,
                     flags: list[str], alias: str | None = None) -> None:
        e = self.internal.setdefault(
            target, {"t": target, "s": set(), "ln": lineno, "f": set(), "a": None}
        )
        e["s"].update(symbols)
        e["f"].update(flags)
        if lineno < e["ln"]:
            e["ln"] = lineno
        if alias and not e["a"]:
            e["a"] = alias

    def add_external(self, module: str, symbols: list[str], lineno: int, group: str) -> None:
        e = self.external.setdefault(
            module, {"m": module, "s": set(), "ln": lineno, "g": group}
        )
        e["s"].update(symbols)
        if lineno < e["ln"]:
            e["ln"] = lineno

    def dump(self) -> tuple[list[dict], list[dict]]:
        internal = []
        for e in sorted(self.internal.values(), key=lambda e: (e["t"], e["ln"])):
            out = {"t": e["t"], "s": sorted(e["s"]), "ln": e["ln"]}
            if e["f"]:
                out["f"] = sorted(e["f"])
            if e["a"]:
                out["a"] = e["a"]
            internal.append(out)
        external = [
            {"m": e["m"], "s": sorted(e["s"]), "g": e["g"], "ln": e["ln"]}
            for e in sorted(self.external.values(), key=lambda e: (e["g"], e["m"]))
        ]
        return internal, external


# ---------------------------------------------------------------- python


def _is_type_checking_test(test: ast.expr) -> bool:
    return any(
        (isinstance(n, ast.Name) and n.id == "TYPE_CHECKING")
        or (isinstance(n, ast.Attribute) and n.attr == "TYPE_CHECKING")
        for n in ast.walk(test)
    )


def _classify(dotted: str, top_names: set[str]) -> str:
    first = dotted.split(".")[0]
    if first in sys.stdlib_module_names:
        return "std"
    if first in top_names:
        return "unres"
    return "ext"


def parse_python(text: str, rel: str, mmap: dict[str, str], path_to_module: dict[str, str],
                 top_names: set[str]) -> tuple[list[dict], list[dict], list[dict], str | None]:
    """Return (defs, internal_edges, external_entries, err) for one .py file."""
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [], [], [], f"SyntaxError: {exc.msg} (line {exc.lineno})"

    defs: list[dict] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = [
                [m.name, m.lineno]
                for m in node.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            d = {"k": "c", "n": node.name, "ln": node.lineno}
            if methods:
                d["m"] = methods
            defs.append(d)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs.append({"k": "f", "n": node.name, "ln": node.lineno})
    defs.sort(key=lambda d: d["ln"])

    tc_nodes: set[int] = set()
    for node in tree.body:
        if isinstance(node, ast.If) and _is_type_checking_test(node.test):
            for sub in ast.walk(node):
                if isinstance(sub, (ast.Import, ast.ImportFrom)):
                    tc_nodes.add(id(sub))

    own_module = path_to_module.get(rel)
    is_pkg = rel.endswith("/__init__.py")
    store = EdgeStore()

    for node in ast.walk(tree):
        flags = ["tc"] if id(node) in tc_nodes else []
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in mmap:
                    store.add_internal(mmap[alias.name], [], node.lineno,
                                       flags + ["mod"], alias.asname)
                else:
                    store.add_external(alias.name, [], node.lineno,
                                       _classify(alias.name, top_names))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if own_module is None:
                    store.add_external("." * node.level + (node.module or ""),
                                       [a.name for a in node.names], node.lineno, "unres")
                    continue
                pkg = own_module.split(".")
                if not is_pkg:
                    pkg = pkg[:-1]
                drop = node.level - 1
                if drop > len(pkg):
                    store.add_external("." * node.level + (node.module or ""),
                                       [a.name for a in node.names], node.lineno, "unres")
                    continue
                pkg = pkg[: len(pkg) - drop] if drop else pkg
                base = ".".join(pkg + (node.module.split(".") if node.module else []))
            else:
                base = node.module or ""
            if base in mmap:
                for alias in node.names:
                    if alias.name == "*":
                        store.add_internal(mmap[base], ["*"], node.lineno, flags + ["st"])
                    elif f"{base}.{alias.name}" in mmap:
                        store.add_internal(mmap[f"{base}.{alias.name}"], [], node.lineno,
                                           flags + ["mod"], alias.asname)
                    else:
                        store.add_internal(mmap[base], [alias.name], node.lineno, flags)
            else:
                store.add_external(base, [a.name for a in node.names], node.lineno,
                                   _classify(base, top_names) if base else "unres")

    internal, external = store.dump()
    return defs, internal, external, None


# ---------------------------------------------------------------- javascript

_JS_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_JS_LINE_COMMENT = re.compile(r"(^|[^:\\\"'])//[^\n]*", re.M)
_JS_STATIC_IMPORT = re.compile(
    r"\bimport\s+(?:([\w$]+)\s*,\s*)?(\{[^}]*\}|\*\s*as\s+[\w$]+|[\w$]+)\s+from\s*[\"']([^\"']+)[\"']"
)
_JS_SIDE_EFFECT = re.compile(r"\bimport\s*[\"']([^\"']+)[\"']")
_JS_DYNAMIC = re.compile(r"\bimport\s*\(\s*[\"']([^\"']+)[\"']\s*\)")
_JS_REEXPORT = re.compile(
    r"\bexport\s+(\{[^}]*\}|\*(?:\s*as\s+[\w$]+)?)\s+from\s*[\"']([^\"']+)[\"']"
)
_JS_DEF_FN = re.compile(r"\bexport\s+(?:default\s+)?(?:async\s+)?(function|class)\s+([\w$]+)")
_JS_DEF_VAR = re.compile(r"\bexport\s+(?:const|let|var)\s+([\w$]+)")


def _strip_js_comments(text: str) -> str:
    text = _JS_BLOCK_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    return _JS_LINE_COMMENT.sub(lambda m: m.group(1), text)


def _js_named_symbols(clause: str) -> tuple[list[str], str | None]:
    """Parse an import binding clause; return (source symbol names, alias)."""
    clause = clause.strip()
    if clause.startswith("{"):
        names = []
        for part in clause.strip("{}").split(","):
            part = part.strip()
            if part:
                names.append(part.split()[0])
        return names, None
    if clause.startswith("*"):
        return ["*"], clause.split()[-1]
    return ["default"], clause


def _resolve_js(spec: str, from_file: str, js_set: set[str]) -> str | None:
    if not spec.startswith("."):
        return None
    base = posixpath.normpath(posixpath.join(posixpath.dirname(from_file), spec))
    for cand in (base, base + ".js", base + "/index.js"):
        if cand in js_set:
            return cand
    return None


def parse_js(text: str, rel: str, js_set: set[str]) -> tuple[list[dict], list[dict], list[dict], str | None]:
    """Return (defs, internal_edges, external_entries, err) for one .js file."""
    text = _strip_js_comments(text)

    def lineno(pos: int) -> int:
        return text.count("\n", 0, pos) + 1

    defs: list[dict] = []
    for m in _JS_DEF_FN.finditer(text):
        defs.append({"k": "c" if m.group(1) == "class" else "f",
                     "n": m.group(2), "ln": lineno(m.start())})
    for m in _JS_DEF_VAR.finditer(text):
        defs.append({"k": "v", "n": m.group(1), "ln": lineno(m.start())})
    defs.sort(key=lambda d: (d["ln"], d["n"]))

    store = EdgeStore()

    def add(spec: str, symbols: list[str], ln: int, flags: list[str], alias: str | None = None) -> None:
        target = _resolve_js(spec, rel, js_set)
        if target:
            store.add_internal(target, symbols, ln, flags, alias)
        else:
            store.add_external(spec, symbols, ln,
                               "unres" if spec.startswith(".") else "ext")

    for m in _JS_STATIC_IMPORT.finditer(text):
        default_name, clause, spec = m.groups()
        symbols, alias = _js_named_symbols(clause)
        if default_name:
            symbols = ["default"] + symbols
        add(spec, symbols, lineno(m.start()), ["st"] if symbols == ["*"] else [], alias)
    for m in _JS_SIDE_EFFECT.finditer(text):
        add(m.group(1), [], lineno(m.start()), ["mod"])
    for m in _JS_DYNAMIC.finditer(text):
        add(m.group(1), [], lineno(m.start()), ["dy"])
    for m in _JS_REEXPORT.finditer(text):
        clause, spec = m.groups()
        symbols, alias = _js_named_symbols(clause)
        add(spec, symbols, lineno(m.start()), ["re"], alias)

    internal, external = store.dump()
    return defs, internal, external, None


# ---------------------------------------------------------------- model


def build_model(root: str, py_files: list[str], js_files: list[str]) -> dict:
    mmap = build_module_map(py_files)
    path_to_module = {p: m for m, p in mmap.items()}
    top_names = {m.split(".")[0] for m in mmap}
    js_set = set(js_files)

    files = []
    for rel, lang in [(p, "py") for p in py_files] + [(p, "js") for p in js_files]:
        try:
            with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            files.append({"p": rel, "l": lang, "n": 0, "err": f"unreadable: {exc}"})
            continue
        if lang == "py":
            defs, internal, external, err = parse_python(
                text, rel, mmap, path_to_module, top_names)
        else:
            defs, internal, external, err = parse_js(text, rel, js_set)
        entry: dict = {"p": rel, "l": lang, "n": len(text.splitlines())}
        if defs:
            entry["d"] = defs
        if internal:
            entry["i"] = internal
        if external:
            entry["e"] = external
        if err:
            entry["err"] = err
        files.append(entry)

    files.sort(key=lambda f: f["p"])
    return {"root": os.path.basename(os.path.abspath(root)), "files": files}


# ---------------------------------------------------------------- check


def check_report(model: dict) -> int:
    """Print a resolution report; return the number of problems found."""
    files = model["files"]
    py = sum(1 for f in files if f["l"] == "py")
    js = len(files) - py
    edges = sum(len(f.get("i", [])) for f in files)
    problems = []
    externals: dict[str, set[str]] = {"std": set(), "ext": set()}
    for f in files:
        if f.get("err"):
            problems.append(f"  {f['p']}: {f['err']}")
        for e in f.get("e", []):
            if e["g"] == "unres":
                problems.append(f"  {f['p']}:{e['ln']}  {e['m']}  ({', '.join(e['s']) or 'module'})")
            else:
                externals[e["g"]].add(e["m"].split(".")[0])
    unres = sum(1 for f in files for e in f.get("e", []) if e["g"] == "unres")
    rate = 100.0 * edges / (edges + unres) if (edges + unres) else 100.0
    print(f"files: {len(files)} (py {py}, js {js})")
    print(f"internal edges: {edges}   resolution rate: {rate:.1f}%")
    print(f"external: stdlib {len(externals['std'])} modules, "
          f"third-party {len(externals['ext'])} modules")
    if problems:
        print(f"problems ({len(problems)}):")
        print("\n".join(problems))
    else:
        print("problems: none")
    return len(problems)


# ---------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".", help="repository root to scan")
    parser.add_argument("--out", default=None,
                        help="output HTML path (default <root>/docs/code-map.html)")
    parser.add_argument("--include", action="append", default=[],
                        help="repo-relative prefix to scan (repeatable; default: everything)")
    parser.add_argument("--exclude", action="append", default=[],
                        help="directory name to skip at any depth (repeatable)")
    parser.add_argument("--check", action="store_true",
                        help="print a resolution report; exit 1 on unresolved imports or parse errors")
    parser.add_argument("--json", action="store_true",
                        help="print the JSON model to stdout instead of writing HTML")
    args = parser.parse_args(argv)

    excludes = DEFAULT_EXCLUDES | set(args.exclude)
    py_files, js_files = discover(args.root, args.include, excludes)
    model = build_model(args.root, py_files, js_files)

    if args.json:
        print(json.dumps(model, sort_keys=True, indent=1))
    else:
        from render_html import render
        out = args.out or os.path.join(args.root, "docs", "code-map.html")
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render(model))
        print(f"wrote {out}", file=sys.stderr)

    if args.check:
        return 1 if check_report(model) else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())

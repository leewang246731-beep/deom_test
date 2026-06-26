# -*- coding: utf-8 -*-
"""
AST hard-check: scan @router.post/put endpoints, forbid body: dict.

Usage:
  python backend/scripts/check_body_dict.py [--fix]

pre-commit hook (.git/hooks/pre-commit):
  python backend/scripts/check_body_dict.py || exit 1
"""
import ast
import sys
import io
from pathlib import Path

# Force UTF-8 on Windows
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

API_DIR = Path(__file__).resolve().parent.parent / "app" / "api"


def check_file(filepath: Path) -> list:
    violations = []
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except SyntaxError as e:
        return [f"{filepath.name}: syntax error - {e}"]

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        is_write = False
        for d in node.decorator_list:
            ds = ast.unparse(d) if hasattr(ast, 'unparse') else ast.dump(d)
            if any(p in ds for p in ['@router.post', '@router.put', '.post(', '.put(']):
                is_write = True
                break
        if not is_write or node.name.startswith('_'):
            continue

        for arg in node.args.args:
            if arg.arg == 'body':
                if arg.annotation:
                    ann = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else ast.dump(arg.annotation)
                    if ann == 'dict':
                        violations.append(
                            f"{filepath.name}:{node.lineno} - "
                            f"'{node.name}' has body: dict, replace with Pydantic Schema"
                        )
                else:
                    violations.append(
                        f"{filepath.name}:{node.lineno} - "
                        f"'{node.name}' body missing type annotation"
                    )
                break

    return violations


def main():
    if not API_DIR.exists():
        print(f"ERROR: API dir not found: {API_DIR}")
        return 1

    all_v = []
    for f in sorted(API_DIR.rglob("*.py")):
        if f.name == "__init__.py":
            continue
        all_v.extend(check_file(f))

    if all_v:
        print(f"FAIL: {len(all_v)} body:dict violation(s) found:")
        for v in all_v:
            print(f"  {v}")
        return 1

    py_count = len([f for f in API_DIR.rglob("*.py") if f.name != "__init__.py"])
    print(f"PASS: scanned {py_count} API files, no body:dict found")
    return 0


if __name__ == "__main__":
    sys.exit(main())

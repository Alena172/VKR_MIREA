from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path


MODULES_ROOT = Path(__file__).resolve().parents[1] / "app" / "modules"
FORBIDDEN_CROSS_MODULE_LAYERS = {"repository", "application_service", "models"}


@dataclass(frozen=True)
class BoundaryViolation:
    file_path: Path
    line: int
    current_module: str
    imported_module: str
    imported_layer: str
    imported_path: str

    def render(self, repo_root: Path) -> str:
        relative_file = self.file_path.relative_to(repo_root)
        return (
            f"{relative_file}:{self.line} "
            f"[{self.current_module} -> {self.imported_module}] "
            f"forbidden import `{self.imported_path}` "
            f"(use `{self.imported_module}.public_api` instead)"
        )


@dataclass(frozen=True)
class ApplicationSchemaViolation:
    file_path: Path
    line: int
    current_module: str
    schema_name: str
    reason: str

    def render(self, repo_root: Path) -> str:
        relative_file = self.file_path.relative_to(repo_root)
        return (
            f"{relative_file}:{self.line} "
            f"[{self.current_module}] forbidden web-schema usage `{self.schema_name}` "
            f"({self.reason})"
        )


def _iter_python_files() -> list[Path]:
    return sorted(
        path
        for path in MODULES_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _module_name_for_file(file_path: Path) -> str | None:
    try:
        relative = file_path.relative_to(MODULES_ROOT)
    except ValueError:
        return None
    parts = relative.parts
    if len(parts) < 2:
        return None
    return parts[0]


def _extract_app_module_imports(node: ast.AST) -> list[tuple[int, str]]:
    imports: list[tuple[int, str]] = []
    if isinstance(node, ast.ImportFrom) and node.module:
        imports.append((node.lineno, node.module))
    elif isinstance(node, ast.Import):
        for alias in node.names:
            imports.append((node.lineno, alias.name))
    return imports


def _find_violations(file_path: Path) -> list[BoundaryViolation]:
    current_module = _module_name_for_file(file_path)
    if current_module is None:
        return []

    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    violations: list[BoundaryViolation] = []

    for node in ast.walk(tree):
        for lineno, imported_path in _extract_app_module_imports(node):
            parts = imported_path.split(".")
            if len(parts) < 4:
                continue
            if parts[0] != "app" or parts[1] != "modules":
                continue

            imported_module = parts[2]
            imported_layer = parts[3]

            if imported_module == current_module:
                continue
            if imported_layer not in FORBIDDEN_CROSS_MODULE_LAYERS:
                continue

            violations.append(
                BoundaryViolation(
                    file_path=file_path,
                    line=lineno,
                    current_module=current_module,
                    imported_module=imported_module,
                    imported_layer=imported_layer,
                    imported_path=imported_path,
                )
            )

    return violations


def _is_application_service(file_path: Path) -> bool:
    return file_path.name == "application_service.py"


def _extract_same_module_schema_imports(file_path: Path, tree: ast.AST) -> dict[str, int]:
    current_module = _module_name_for_file(file_path)
    if current_module is None:
        return {}

    schema_module = f"app.modules.{current_module}.schemas"
    imported_names: dict[str, int] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module != schema_module:
            continue
        for alias in node.names:
            imported_names[alias.asname or alias.name] = node.lineno

    return imported_names


def _is_request_like_schema(name: str) -> bool:
    request_suffixes = ("Request", "Create", "Update", "Upsert")
    return name.endswith(request_suffixes) or name.endswith("Me")


def _annotation_uses_name(annotation: ast.AST | None, name: str) -> bool:
    if annotation is None:
        return False
    return any(isinstance(node, ast.Name) and node.id == name for node in ast.walk(annotation))


def _return_uses_name(node: ast.Return, name: str) -> bool:
    if node.value is None:
        return False
    return any(isinstance(child, ast.Name) and child.id == name for child in ast.walk(node.value))


def _find_application_schema_violations(file_path: Path) -> list[ApplicationSchemaViolation]:
    if not _is_application_service(file_path):
        return []

    current_module = _module_name_for_file(file_path)
    if current_module is None:
        return []

    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    imported_schema_names = _extract_same_module_schema_imports(file_path, tree)
    disallowed_schema_names = {
        name
        for name in imported_schema_names
        if not _is_request_like_schema(name)
    }
    if not disallowed_schema_names:
        return []

    violations: list[ApplicationSchemaViolation] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue

        for schema_name in sorted(disallowed_schema_names):
            if _annotation_uses_name(node.returns, schema_name):
                violations.append(
                    ApplicationSchemaViolation(
                        file_path=file_path,
                        line=node.lineno,
                        current_module=current_module,
                        schema_name=schema_name,
                        reason="public application service must return DTO/contracts, not web response schema",
                    )
                )

            for child in ast.walk(node):
                if isinstance(child, ast.Return) and _return_uses_name(child, schema_name):
                    violations.append(
                        ApplicationSchemaViolation(
                            file_path=file_path,
                            line=child.lineno,
                            current_module=current_module,
                            schema_name=schema_name,
                            reason="public application service must not construct or return web schema objects",
                        )
                    )
    return violations


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    violations: list[BoundaryViolation] = []
    application_schema_violations: list[ApplicationSchemaViolation] = []

    for file_path in _iter_python_files():
        violations.extend(_find_violations(file_path))
        application_schema_violations.extend(_find_application_schema_violations(file_path))

    if not violations and not application_schema_violations:
        print("Module boundary check passed.")
        return 0

    print("Module boundary violations found:")
    for violation in violations:
        print(f"- {violation.render(repo_root)}")
    for violation in application_schema_violations:
        print(f"- {violation.render(repo_root)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

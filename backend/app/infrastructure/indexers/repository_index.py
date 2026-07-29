"""TestGen AI v2.3 — RepositoryContextIndex Implementation

Static AST-based project indexer for Python repositories.
Performs deterministic scanning, symbol extraction, test discovery, dependency parsing,
and framework detection without external LLMs, RAG, embeddings, or vector databases.
"""

import ast
import os
import time
from typing import Any, Dict, List, Optional, Set
import structlog

from app.domain.v23_models import RepositoryContext
from app.infrastructure.indexers.base import BaseContextIndexer

logger = structlog.get_logger()

# Ignored directories during recursive repository scanning
IGNORED_DIRS: Set[str] = {
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".git",
    ".idea",
    ".vscode",
    "node_modules",
    "dist",
    "build",
    "htmlcov",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage",
    "site-packages",
}


class RepositoryContextIndex(BaseContextIndexer):
    """Deterministic AST repository context indexer."""

    def __init__(self) -> None:
        super().__init__(indexer_name="RepositoryContextIndex")

    def build_context(self, source_code: str, file_path: Optional[str] = None) -> RepositoryContext:
        """Parse source code AST or index a full project repository.

        Args:
            source_code: Source code string OR absolute/relative directory path.
            file_path: Optional specific file path context.

        Returns:
            Populated RepositoryContext domain object.
        """
        start_time = time.perf_counter()

        # If source_code points to an existing directory, run repository directory scan
        if os.path.exists(source_code) and os.path.isdir(source_code):
            return self.index_directory(root_path=source_code)

        # Otherwise, parse the provided single source code string
        return self._index_single_source(source_code=source_code, file_path=file_path, start_time=start_time)

    def index_directory(self, root_path: str) -> RepositoryContext:
        """Recursively inspect and index a project directory.

        Args:
            root_path: Directory path to scan.

        Returns:
            Populated RepositoryContext object.
        """
        start_time = time.perf_counter()
        abs_root = os.path.abspath(root_path)

        all_files: List[str] = []
        py_files: List[str] = []
        ignored_count = 0
        failed_files: List[str] = []

        # 1. Directory Tree Walk
        for dirpath, dirnames, filenames in os.walk(abs_root):
            # Prune ignored directories
            dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".")]

            for fn in filenames:
                rel_file = os.path.relpath(os.path.join(dirpath, fn), abs_root)
                all_files.append(rel_file)
                if fn.endswith(".py"):
                    py_files.append(os.path.join(dirpath, fn))

        # 2. Extract AST Symbols & Tests
        all_classes: List[Dict[str, Any]] = []
        all_functions: List[Dict[str, Any]] = []
        all_imports: List[str] = []
        all_fixtures: List[str] = []
        existing_tests: List[Dict[str, Any]] = []
        modules: List[Dict[str, Any]] = []
        frameworks: Dict[str, float] = {}

        for full_py_path in py_files:
            rel_py_path = os.path.relpath(full_py_path, abs_root)
            try:
                with open(full_py_path, "r", encoding="utf-8", errors="replace") as f:
                    code_content = f.read()

                mod_info = self._parse_ast_symbols(code_content, rel_py_path)
                modules.append(mod_info)

                all_classes.extend(mod_info["classes"])
                all_functions.extend(mod_info["functions"])
                all_imports.extend(mod_info["imports"])
                all_fixtures.extend(mod_info["fixtures"])

                # Existing Test Detection
                if self._is_test_file(rel_py_path):
                    existing_tests.append({
                        "file_path": rel_py_path,
                        "classes": [c["name"] for c in mod_info["classes"]],
                        "functions": [f["name"] for f in mod_info["functions"]],
                    })

                # Detect Frameworks from Source File AST
                self._detect_frameworks_from_imports(mod_info["imports"], code_content, frameworks)

            except Exception as exc:
                self.logger.warning("file_parsing_failed", file_path=rel_py_path, error=str(exc))
                failed_files.append(rel_py_path)

        # 3. Detect Dependencies
        dependencies = self._detect_dependencies(abs_root)

        # 4. Framework Detection via Config Files
        self._detect_frameworks_from_config(abs_root, all_files, frameworks)

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        metadata = {
            "root_path": abs_root,
            "total_files": len(all_files),
            "source_files_count": len(py_files),
            "test_files_count": len(existing_tests),
        }

        statistics = {
            "total_modules": len(modules),
            "total_classes": len(all_classes),
            "total_functions": len(all_functions),
            "total_imports": len(set(all_imports)),
            "total_fixtures": len(all_fixtures),
            "total_existing_tests": len(existing_tests),
        }

        indexing_summary = {
            "duration_ms": elapsed_ms,
            "indexed_files": len(py_files),
            "ignored_files": ignored_count,
            "failed_files": len(failed_files),
        }

        self.logger.info(
            "directory_indexing_completed",
            root_path=abs_root,
            indexed_py_files=len(py_files),
            duration_ms=elapsed_ms,
            frameworks=list(frameworks.keys()),
        )

        return RepositoryContext(
            file_path=abs_root,
            imports=sorted(list(set(all_imports))),
            custom_types=[c["name"] for c in all_classes],
            pytest_fixtures=sorted(list(set(all_fixtures))),
            call_graph={},
            metadata=metadata,
            languages=["python"],
            packages=self._extract_packages(abs_root),
            modules=modules,
            files=all_files,
            classes=all_classes,
            functions=all_functions,
            dependencies=dependencies,
            frameworks=frameworks,
            existing_tests=existing_tests,
            statistics=statistics,
            indexing_summary=indexing_summary,
        )

    def _index_single_source(
        self, source_code: str, file_path: Optional[str], start_time: float
    ) -> RepositoryContext:
        """Parse AST of a single source code string."""
        imports: List[str] = []
        classes: List[Dict[str, Any]] = []
        functions: List[Dict[str, Any]] = []
        fixtures: List[str] = []
        frameworks: Dict[str, float] = {}

        try:
            mod_info = self._parse_ast_symbols(source_code, file_path or "source_code.py")
            imports = mod_info["imports"]
            classes = mod_info["classes"]
            functions = mod_info["functions"]
            fixtures = mod_info["fixtures"]
            self._detect_frameworks_from_imports(imports, source_code, frameworks)
        except Exception as exc:
            self.logger.warning("single_source_parsing_failed", error=str(exc))

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return RepositoryContext(
            file_path=file_path,
            imports=imports,
            custom_types=[c["name"] for c in classes],
            pytest_fixtures=fixtures,
            call_graph={},
            metadata={"root_path": file_path or "inline", "total_files": 1, "source_files_count": 1, "test_files_count": 0},
            languages=["python"],
            packages=[],
            modules=[{"file_path": file_path or "inline", "classes": classes, "functions": functions}],
            files=[file_path] if file_path else [],
            classes=classes,
            functions=functions,
            dependencies=[],
            frameworks=frameworks,
            existing_tests=[],
            statistics={"total_modules": 1, "total_classes": len(classes), "total_functions": len(functions)},
            indexing_summary={"duration_ms": elapsed_ms, "indexed_files": 1, "failed_files": 0},
        )

    def _parse_ast_symbols(self, code_content: str, rel_path: str) -> Dict[str, Any]:
        """Parse source code string into classes, functions, imports, and fixtures via ast.NodeVisitor."""
        classes: List[Dict[str, Any]] = []
        functions: List[Dict[str, Any]] = []
        imports: List[str] = []
        fixtures: List[str] = []

        tree = ast.parse(code_content)

        for node in ast.walk(tree):
            # Imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)

            # Classes
            elif isinstance(node, ast.ClassDef):
                bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
                docstring = ast.get_docstring(node)
                classes.append({
                    "name": node.name,
                    "bases": bases,
                    "docstring": docstring,
                    "file_path": rel_path,
                    "line_number": node.lineno,
                })

            # Functions & Async Functions
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decorators = [self._decorator_name(d) for d in node.decorator_list]
                docstring = ast.get_docstring(node)
                arg_names = [a.arg for a in node.args.args]
                is_async = isinstance(node, ast.AsyncFunctionDef)

                functions.append({
                    "name": node.name,
                    "args": arg_names,
                    "is_async": is_async,
                    "decorators": decorators,
                    "docstring": docstring,
                    "file_path": rel_path,
                    "line_number": node.lineno,
                })

                # Check if decorated as pytest fixture
                if any("fixture" in d for d in decorators):
                    fixtures.append(node.name)

        return {
            "file_path": rel_path,
            "classes": classes,
            "functions": functions,
            "imports": imports,
            "fixtures": fixtures,
        }

    def _decorator_name(self, node: ast.AST) -> str:
        """Extract decorator string representation."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._decorator_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Call):
            return self._decorator_name(node.func)
        return "decorator"

    def _is_test_file(self, rel_path: str) -> bool:
        """Check if file path follows test conventions."""
        filename = os.path.basename(rel_path)
        norm_path = rel_path.replace("\\", "/").lower()
        return (
            filename.startswith("test_")
            or filename.endswith("_test.py")
            or "/tests/" in norm_path
            or "/test/" in norm_path
        )

    def _detect_dependencies(self, abs_root: str) -> List[str]:
        """Detect project dependencies from requirements.txt, pyproject.toml, or poetry.lock."""
        deps: Set[str] = set()

        # 1. requirements.txt
        req_path = os.path.join(abs_root, "requirements.txt")
        if os.path.exists(req_path):
            try:
                with open(req_path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            pkg = line.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].strip()
                            if pkg:
                                deps.add(pkg)
            except Exception as exc:
                self.logger.warning("requirements_parsing_failed", error=str(exc))

        # 2. pyproject.toml
        pyproject_path = os.path.join(abs_root, "pyproject.toml")
        if os.path.exists(pyproject_path):
            try:
                with open(pyproject_path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        if "=" in line and not line.strip().startswith("#"):
                            pkg = line.split("=")[0].strip()
                            if pkg and pkg not in ("name", "version", "description", "authors"):
                                deps.add(pkg)
            except Exception as exc:
                self.logger.warning("pyproject_parsing_failed", error=str(exc))

        return sorted(list(deps))

    def _detect_frameworks_from_imports(
        self, imports: List[str], code_content: str, frameworks: Dict[str, float]
    ) -> None:
        """Detect web & test frameworks from imports and source code symbols."""
        imp_set = set(imports)

        if "fastapi" in imp_set or "FastAPI" in code_content or "APIRouter" in code_content:
            frameworks["FastAPI"] = 1.0
        if "django" in imp_set or "DJANGO_SETTINGS_MODULE" in code_content:
            frameworks["Django"] = 1.0
        if "flask" in imp_set or "Flask(" in code_content:
            frameworks["Flask"] = 1.0
        if "pytest" in imp_set or "pytest" in code_content:
            frameworks["Pytest"] = 1.0
        if "unittest" in imp_set:
            frameworks["Unittest"] = 1.0

    def _detect_frameworks_from_config(
        self, abs_root: str, all_files: List[str], frameworks: Dict[str, float]
    ) -> None:
        """Detect frameworks from repository config files."""
        if any("manage.py" in f for f in all_files):
            frameworks["Django"] = 1.0
        if any("pytest.ini" in f or "conftest.py" in f for f in all_files):
            frameworks["Pytest"] = 1.0
        if os.path.exists(os.path.join(abs_root, "requirements.txt")):
            try:
                with open(os.path.join(abs_root, "requirements.txt"), "r", encoding="utf-8", errors="replace") as f:
                    req_text = f.read().lower()
                    if "fastapi" in req_text:
                        frameworks["FastAPI"] = 1.0
                    if "flask" in req_text:
                        frameworks["Flask"] = 1.0
                    if "pytest" in req_text:
                        frameworks["Pytest"] = 1.0
            except Exception:
                pass

    def _extract_packages(self, abs_root: str) -> List[str]:
        """Discover Python packages containing __init__.py files."""
        packages: List[str] = []
        for dirpath, dirnames, filenames in os.walk(abs_root):
            dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".")]
            if "__init__.py" in filenames:
                rel_pkg = os.path.relpath(dirpath, abs_root).replace(os.sep, ".")
                if rel_pkg != ".":
                    packages.append(rel_pkg)
        return sorted(packages)

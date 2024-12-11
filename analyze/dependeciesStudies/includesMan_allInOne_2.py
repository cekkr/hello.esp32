#!/usr/bin/env python3

from dataclasses import dataclass, field
from typing import Dict, List, Set, NamedTuple, Optional
from pathlib import Path
import logging
import os
import sys
from clang.cindex import Index, CursorKind, Config
import clang.cindex

from checkCircularDeps import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Symbol(NamedTuple):
    """Represents a source code symbol."""
    name: str
    symbol_type: str
    line: int
    context: str
    cursor_kind: CursorKind
    metadata: Dict[str, any] = {}


@dataclass
class SourceFile:
    """Represents a source file with its symbols and dependencies."""
    path: Path
    includes: List[Path]
    included_by: Set[Path]
    definitions: List[Symbol]
    usages: List[Symbol]
    raw_content: Optional[str] = None
    is_header: bool = False

    def add_definition(self, name: str, kind: str, line: int, context: str,
                       cursor_kind: Optional[CursorKind] = None, metadata: dict = None):
        self.definitions.append(Symbol(name, kind, line, context, cursor_kind, metadata or {}))

    def add_usage(self, name: str, kind: str, line: int, context: str,
                  cursor_kind: Optional[CursorKind] = None, metadata: dict = None):
        self.usages.append(Symbol(name, kind, line, context, cursor_kind, metadata or {}))


def setup_libclang() -> bool:
    """Configure libclang path."""
    possible_paths = [
        '/usr/lib/llvm-14/lib/libclang.so.1',
        '/usr/lib/llvm-14/lib/libclang.so',
        '/usr/lib/x86_64-linux-gnu/libclang-14.so.1',
        '/Library/Developer/CommandLineTools/usr/lib/libclang.dylib',
        '/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib/libclang.dylib'
    ]

    for path in possible_paths:
        if os.path.exists(path):
            Config.set_library_file(path)
            return True

    logger.error("libclang not found. Please install LLVM/Clang.")
    return False


class SourceAnalyzer:
    SOURCE_EXTENSIONS = {'.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx'}

    def __init__(self, project_paths: List[str]):
        if not setup_libclang():
            raise RuntimeError("Failed to initialize libclang")

        self.project_paths = [Path(p) for p in project_paths]
        self.files: Dict[Path, SourceFile] = {}
        self.include_graph = {}
        self.symbol_definitions = {}
        self.symbol_usages = {}
        self.index = Index.create()

        # Add compilation flags for better parsing
        self.compilation_flags = [
            '-x', 'c++',
            '-std=c++14',
            '-I/usr/include',
            '-I/usr/local/include'
        ]

        # Add project paths to include paths
        for path in self.project_paths:
            self.compilation_flags.extend(['-I', str(path)])

    def analyze(self):
        """Analyze all source files in the project."""
        self._find_source_files()

        for file_path in self.files:
            self._analyze_file(file_path)

    def _find_source_files(self):
        """Find all source files in project directories."""
        for path in self.project_paths:
            if not path.exists():
                logger.warning(f"Path {path} does not exist")
                continue

            for file_path in path.rglob('*'):
                if self._is_source_file(file_path):
                    is_header = file_path.suffix.lower() in {'.h', '.hpp', '.hxx'}
                    self.files[file_path] = SourceFile(
                        path=file_path,
                        includes=[],
                        included_by=set(),
                        definitions=[],
                        usages=[],
                        is_header=is_header
                    )

        logger.info(f"Found {len(self.files)} source files")

    def _analyze_file(self, file_path: Path):
        """Analyze a single file using libclang."""
        try:
            source_file = self.files[file_path]

            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                source_file.raw_content = f.read()

            # Parse with libclang
            translation_unit = self.index.parse(
                str(file_path),
                args=self.compilation_flags,
                options=clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
            )

            if not translation_unit:
                logger.error(f"Failed to parse {file_path}")
                return

            # Process includes
            for include in translation_unit.get_includes():
                included_path = Path(include.include.name)
                if included_path in self.files:
                    source_file.includes.append(included_path)
                    self.files[included_path].included_by.add(file_path)

            # Process symbols
            self._process_cursor(translation_unit.cursor, source_file)

        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")

    def _process_cursor(self, cursor, source_file: SourceFile):
        """Process a cursor and its children recursively."""
        if not cursor.location.file:
            return

        if Path(cursor.location.file.name) != source_file.path:
            return

        # Get symbol information
        symbol_type = self._get_symbol_type(cursor.kind)
        if symbol_type:
            line = cursor.location.line
            context = self._get_context(source_file.raw_content, line)

            # Create metadata
            metadata = {
                'is_definition': cursor.is_definition(),
                'is_declaration': cursor.is_declaration(),
                'access': str(cursor.access_specifier).lower() if hasattr(cursor, 'access_specifier') else None,
                'storage_class': str(cursor.storage_class).lower() if hasattr(cursor, 'storage_class') else None
            }

            # Add symbol
            if cursor.is_definition():
                source_file.add_definition(
                    cursor.spelling,
                    symbol_type,
                    line,
                    context,
                    cursor.kind,
                    metadata
                )
            else:
                source_file.add_usage(
                    cursor.spelling,
                    symbol_type,
                    line,
                    context,
                    cursor.kind,
                    metadata
                )

        # Process children
        for child in cursor.get_children():
            self._process_cursor(child, source_file)

    def _get_symbol_type(self, cursor_kind: CursorKind) -> Optional[str]:
        """Map cursor kinds to symbol types."""
        symbol_types = {
            CursorKind.FUNCTION_DECL: 'function',
            CursorKind.METHOD_DECL: 'method',
            CursorKind.CONSTRUCTOR: 'constructor',
            CursorKind.DESTRUCTOR: 'destructor',
            CursorKind.CLASS_DECL: 'class',
            CursorKind.STRUCT_DECL: 'struct',
            CursorKind.ENUM_DECL: 'enum',
            CursorKind.FIELD_DECL: 'field',
            CursorKind.VAR_DECL: 'variable',
            CursorKind.TYPEDEF_DECL: 'typedef',
            CursorKind.NAMESPACE: 'namespace',
            CursorKind.CLASS_TEMPLATE: 'class_template',
            CursorKind.FUNCTION_TEMPLATE: 'function_template'
        }
        return symbol_types.get(cursor_kind)

    def _get_context(self, content: str, line: int, context_lines: int = 1) -> str:
        """Get context around a specific line."""
        if not content:
            return ""

        lines = content.splitlines()
        if not (0 < line <= len(lines)):
            return ""

        start = max(0, line - context_lines - 1)
        end = min(len(lines), line + context_lines)
        return '\n'.join(lines[start:end]).strip()

    def _is_source_file(self, file_path: Path) -> bool:
        """Check if a file is a valid source file."""
        return (
                file_path.is_file() and
                file_path.suffix.lower() in self.SOURCE_EXTENSIONS and
                not any(p.lower() in {'build', 'cmake-build', 'dist'} for p in file_path.parts)
        )

    def output(self) -> dict:
        """Return analysis results."""
        return {
            "files": self.files,
            "include_graph": self.include_graph,
            "symbol_definitions": self.symbol_definitions,
            "symbol_usages": self.symbol_usages
        }

    def calculateCircularDeps(self):

        files = convert_paths_to_strings(self.files)
        optimizer = HeaderDependencyOptimizer(files)

        optimized = {}
        try:
            optimized = optimizer.generate_include_statements(break_cycles=True)
        except CircularDependencyError as e:
            raise e
            print(f"Errore: {e}")

        # Stampa i risultati
        for file_name, includes in optimized.items():
            print(f"\n{file_name}:")
            print(includes)

        return optimized
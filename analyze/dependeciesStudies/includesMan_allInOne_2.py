#!/usr/bin/env python3

from dataclasses import dataclass, field
from typing import Dict, List, Set, NamedTuple, Optional, Callable
from pathlib import Path
from collections import defaultdict
import contextlib
import re
import sys
import os
import subprocess
import clang.cindex
from clang.cindex import Index, CursorKind, TypeKind, Config
from typing import Dict, Set, List, Optional, DefaultDict, NamedTuple, Tuple, Any
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SymbolLocation:
    """Rappresenta la locazione di un simbolo."""
    is_internal: bool  # Dichiarato in questo file
    is_project_local: bool  # Dichiarato in un altro file del progetto
    is_external: bool  # Dichiarato in un header di sistema/esterno
    declaration_file: Optional[Path]  # File di dichiarazione
    definition_file: Optional[Path]  # File di definizione
    is_forward_declared: bool  # Se è una forward declaration


@dataclass
class SymbolMetadata:
    """Metadati di un simbolo."""
    location: SymbolLocation
    template_params: str = ""
    access: Optional[str] = None
    storage_class: Optional[str] = None
    is_virtual: bool = False
    is_pure_virtual: bool = False
    return_type: Optional[str] = None


class Symbol(NamedTuple):
    """Rappresenta un simbolo definito nel codice sorgente."""
    name: str
    symbol_type: str
    line: int
    context: str
    cursor_kind: CursorKind
    metadata: Dict[str, Any] = {}

    def __str__(self) -> str:
        base = f"{self.symbol_type} {self.name} at line {self.line}"
        if self.metadata.get('template_params'):
            base = f"template{self.metadata['template_params']} " + base
        if self.metadata.get('return_type'):
            base = f"{self.metadata['return_type']} {base}"
        if self.metadata.get('access'):
            base = f"{self.metadata['access']} {base}"
        if self.metadata.get('is_pure_virtual'):
            base += " = 0"
        elif self.metadata.get('is_virtual'):
            base = f"virtual {base}"
        if self.metadata.get('storage_class'):
            base = f"{self.metadata['storage_class'].lower()} {base}"
        return base

    def get_qualified_name(self) -> str:
        return self.name

    def is_member(self) -> bool:
        return self.metadata.get('access') is not None

    def is_template(self) -> bool:
        return bool(self.metadata.get('template_params'))

    def get_declaration(self) -> str:
        decl = str(self)
        if self.symbol_type in {'function', 'method'}:
            decl += ';'
        return decl


@dataclass
class SourceFile:
    path: Path
    includes: List[Path]
    included_by: Set[Path]
    definitions: List[Symbol]
    usages: List[Symbol]
    raw_content: Optional[str] = None
    is_header: bool = False
    available_types: Set[str] = field(default_factory=set)

    def __hash__(self):
        return hash(self.path)

    def add_definition(self, name: str, kind: str, line: int, context: str,
                       cursor_kind: Optional[CursorKind] = None, metadata: dict = None):
        symbol = Symbol(name, kind, line, context, cursor_kind, metadata or {})
        self.definitions.append(symbol)
        if kind == 'type':
            self.available_types.add(name)

    def add_usage(self, name: str, kind: str, line: int, context: str,
                  cursor_kind: Optional[CursorKind] = None, metadata: dict = None):
        self.usages.append(Symbol(name, kind, line, context, cursor_kind, metadata or {}))


@dataclass
class SymbolDefinition:
    """Enhanced symbol definition with scope and dependency information"""
    name: str
    kind: str
    file: Path
    line: int
    scope: str
    dependencies: Set[str] = field(default_factory=set)
    is_exported: bool = True


@dataclass
class SymbolUsage:
    """Track where and how symbols are used"""
    name: str
    file: Path
    line: int
    context: str
    required_symbols: Set[str] = field(default_factory=set)


@dataclass
class HeaderDependencies:
    """Track header file dependencies and symbols"""
    path: Path
    provided_symbols: Set[str] = field(default_factory=set)
    required_symbols: Set[str] = field(default_factory=set)
    direct_includes: Set[Path] = field(default_factory=set)
    transitive_includes: Set[Path] = field(default_factory=set)
    dependents: Set[Path] = field(default_factory=set)

    def add_provided_symbol(self, symbol: str):
        self.provided_symbols.add(symbol)

    def add_required_symbol(self, symbol: str):
        self.required_symbols.add(symbol)

    def add_include(self, header: Path):
        self.direct_includes.add(header)


@dataclass
class SymbolTable:
    """Global symbol management"""
    definitions: Dict[str, List[SymbolDefinition]] = field(default_factory=lambda: defaultdict(list))
    usages: Dict[str, List[SymbolUsage]] = field(default_factory=lambda: defaultdict(list))
    dependencies: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))

    def add_definition(self, symbol: SymbolDefinition):
        if symbol.name not in self.definitions:
            self.definitions[symbol.name] = []
        self.definitions[symbol.name].append(symbol)

    def add_usage(self, usage: SymbolUsage):
        if usage.name not in self.usages:
            self.usages[usage.name] = []
        self.usages[usage.name].append(usage)
        for req in usage.required_symbols:
            if usage.name not in self.dependencies:
                self.dependencies[usage.name] = set()
            self.dependencies[usage.name].add(req)

    def get_symbol_dependencies(self, symbol_name: str, visited: Optional[Set[str]] = None) -> Set[str]:
        if visited is None:
            visited = set()
        if symbol_name in visited:
            return set()
        visited.add(symbol_name)
        deps = self.dependencies.get(symbol_name, set())
        all_deps = deps.copy()
        for dep in deps:
            if dep not in visited:
                all_deps.update(self.get_symbol_dependencies(dep, visited))
        visited.remove(symbol_name)
        return all_deps


def setup_libclang() -> bool:
    """Configura il percorso di libclang."""
    try:
        # Prova prima con brew su macOS
        try:
            brew_prefix = subprocess.check_output(['brew', '--prefix']).decode().strip()
            possible_paths = [
                os.path.join(brew_prefix, 'opt/llvm/lib/libclang.dylib'),
                '/Library/Developer/CommandLineTools/usr/lib/libclang.dylib',
                '/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib/libclang.dylib',
                '/usr/lib/llvm-14/lib/libclang.so.1',
                '/usr/lib/llvm-14/lib/libclang.so'
            ]
        except subprocess.CalledProcessError:
            possible_paths = [
                '/usr/lib/llvm-14/lib/libclang.so.1',
                '/usr/lib/llvm-14/lib/libclang.so'
            ]

        for path in possible_paths:
            if os.path.exists(path):
                Config.set_library_file(path)
                return True

        logger.error("libclang non trovato. Installa LLVM:")
        logger.error("  macOS: brew install llvm")
        logger.error("  Linux: sudo apt install libclang1")
        return False
    except Exception as e:
        logger.error(f"Errore: {e}")
        return False


def get_full_name(cursor) -> str:
    """Ottiene il nome completo del simbolo includendo namespace, classe e template."""

    def _get_parent_context(cursor):
        if cursor is None or cursor.kind == CursorKind.TRANSLATION_UNIT:
            return []
        if not cursor.spelling and cursor.kind in {
            CursorKind.NAMESPACE,
            CursorKind.STRUCT_DECL,
            CursorKind.CLASS_DECL,
            CursorKind.CLASS_TEMPLATE
        }:
            return _get_parent_context(cursor.semantic_parent)
        return _get_parent_context(cursor.semantic_parent) + ([cursor.spelling] if cursor.spelling else [])

    parent_parts = _get_parent_context(cursor.semantic_parent)
    current_name = cursor.spelling if cursor.spelling else ""

    if cursor.kind in {
        CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION,
        CursorKind.FUNCTION_TEMPLATE,
        CursorKind.CLASS_TEMPLATE
    }:
        template_params = get_template_params(cursor)
        if template_params:
            current_name = f"{current_name}{template_params}"

    return "::".join(parent_parts + [current_name]) if parent_parts else current_name


def get_template_params(cursor) -> str:
    """Estrae e formatta i parametri template di un simbolo."""
    if cursor.kind not in {
        CursorKind.CLASS_TEMPLATE,
        CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION,
        CursorKind.FUNCTION_TEMPLATE
    }:
        return ""

    template_params = []

    def format_template_arg(arg):
        if arg.kind == CursorKind.TEMPLATE_TYPE_PARAMETER:
            name = arg.spelling or "typename"
            if arg.default_type:
                return f"{name} = {arg.default_type.spelling}"
            return name
        elif arg.kind == CursorKind.TEMPLATE_NON_TYPE_PARAMETER:
            param_type = arg.type.spelling
            param_name = arg.spelling
            if arg.default_value:
                return f"{param_type} {param_name} = {arg.default_value}"
            return f"{param_type} {param_name}"
        elif arg.kind == CursorKind.TEMPLATE_TEMPLATE_PARAMETER:
            name = arg.spelling or "template"
            inner_params = get_template_params(arg)
            if arg.default_type:
                return f"template {name}{inner_params} = {arg.default_type.spelling}"
            return f"template {name}{inner_params}"
        return str(arg.spelling)

    def get_specialization_args(cursor):
        if cursor.kind == CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION:
            spec_args = []
            for arg in cursor.get_specialization_args():
                if arg.kind == CursorKind.TYPE:
                    spec_args.append(arg.spelling)
                elif arg.kind == CursorKind.LITERAL:
                    spec_args.append(str(arg.literal))
            return spec_args
        return []

    for child in cursor.get_children():
        if child.kind in {
            CursorKind.TEMPLATE_TYPE_PARAMETER,
            CursorKind.TEMPLATE_NON_TYPE_PARAMETER,
            CursorKind.TEMPLATE_TEMPLATE_PARAMETER
        }:
            template_params.append(format_template_arg(child))

    spec_args = get_specialization_args(cursor)
    if spec_args:
        return f"<{', '.join(spec_args)}>"

    return f"<{', '.join(template_params)}>" if template_params else ""


class SourceAnalyzer:
    SOURCE_EXTENSIONS = {'.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx', '.h++'}

    def __init__(self, project_paths: List[str]):
        if isinstance(project_paths, str):
            project_paths = [project_paths]

        self.project_paths = [Path(p) for p in project_paths]
        self.files: Dict[Path, SourceFile] = {}
        self.include_graph = defaultdict(set)
        self.reverse_graph = defaultdict(set)
        self.symbol_definitions: DefaultDict[str, List[Symbol]] = defaultdict(list)
        self.symbol_usages: DefaultDict[str, List[tuple[Path, Symbol]]] = defaultdict(list)

        if not setup_libclang():
            raise RuntimeError("Impossibile inizializzare libclang")
        self.index = Index.create()

    def output(self):
        return {
            "files": self.files,
            "include_graph": self.include_graph,
            "reverse_graph": self.reverse_graph,
            "symbol_definitions": self.symbol_definitions,
            "symbol_usages": self.symbol_usages
        }

    def analyze(self):
        """Analizza tutti i file sorgente nel progetto."""
        self._find_source_files()

        # Prima passa: analizza le definizioni
        for file_path in self.files:
            self._analyze_file(file_path, first_pass=True)

        # Seconda passa: analizza gli usi
        for file_path in self.files:
            self._analyze_file(file_path, first_pass=False)

    def _find_source_files(self):
        """Trova tutti i file sorgente nelle directory del progetto."""
        found_files = set()

        for path in self.project_paths:
            if not path.is_dir():
                logger.warning(f"{path} non è una directory valida")
                continue

            try:
                for file_path in path.rglob('*'):
                    if self._is_source_file(file_path):
                        found_files.add(file_path)
                        is_header = file_path.suffix.lower() in {'.h', '.hpp', '.hxx', '.h++'}
                        self.files[file_path] = SourceFile(
                            path=file_path,
                            includes=[],
                            included_by=set(),
                            definitions=[],
                            usages=[],
                            raw_content=None,
                            is_header=is_header
                        )
            except Exception as e:
                logger.error(f"Errore durante la scansione di {path}: {e}")

            logger.info(f"\nTrovati {len(found_files)} file sorgente nel progetto:")
            for file_path in sorted(found_files):
                rel_path = self._get_relative_path(file_path)
                logger.info(f"  - {rel_path}")

    def _analyze_file(self, file_path: Path, first_pass: bool):
        """Analizza un singolo file usando libclang."""
        try:
            source_file = self.files[file_path]

            if source_file.raw_content is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_file.raw_content = f.read()

            # Usa libclang per il parsing
            translation_unit = self.index.parse(
                str(file_path),
                args=['-x', 'c++'] if file_path.suffix in {'.cpp', '.hpp'} else ['-x', 'c']
            )

            if first_pass:
                self._analyze_includes(translation_unit, source_file)
                self._analyze_definitions(translation_unit.cursor, source_file)
            else:
                self._analyze_usages(translation_unit.cursor, source_file)

        except Exception as e:
            logger.error(f"Errore analizzando {file_path}: {e}")

    def _analyze_includes(self, translation_unit, source_file: SourceFile):
        """Analizza le direttive #include usando libclang."""
        for include in translation_unit.get_includes():
            included_path = Path(include.include.name)
            resolved_path = self._resolve_include_path(included_path, source_file.path)

            if resolved_path and resolved_path in self.files:
                source_file.includes.append(resolved_path)
                self.files[resolved_path].included_by.add(source_file.path)
                self.include_graph[source_file.path].add(resolved_path)
                self.reverse_graph[resolved_path].add(source_file.path)

    def _analyze_definitions(self, cursor, source_file: SourceFile):
        if not (cursor.location.file and Path(cursor.location.file.name) == source_file.path):
            return

        line = cursor.location.line
        context = self._get_context(source_file.raw_content, line)

        cursor_type_map = {
            CursorKind.TYPEDEF_DECL: 'typedef',
            CursorKind.STRUCT_DECL: 'struct',
            CursorKind.UNION_DECL: 'union',
            CursorKind.CLASS_DECL: 'class',
            CursorKind.CLASS_TEMPLATE: 'class_template',
            CursorKind.ENUM_DECL: 'enum',
            CursorKind.FUNCTION_DECL: 'function',
            CursorKind.FUNCTION_TEMPLATE: 'function_template',
            CursorKind.VAR_DECL: 'variable',
            CursorKind.FIELD_DECL: 'field',
            CursorKind.MACRO_DEFINITION: 'macro',
            CursorKind.NAMESPACE: 'namespace',
            CursorKind.CONSTRUCTOR: 'constructor',
            CursorKind.DESTRUCTOR: 'destructor',
            CursorKind.METHOD_DECL: 'method',
            CursorKind.CONVERSION_FUNCTION: 'conversion',
            CursorKind.ENUM_CONSTANT_DECL: 'enum_constant'
        }

        def process_symbol(cursor, symbol_type):
            full_name = get_full_name(cursor)
            template_params = get_template_params(cursor)

            access_specifier = None
            if cursor.kind in {CursorKind.FIELD_DECL, CursorKind.METHOD_DECL}:
                access_specifier = cursor.access_specifier.name.lower()

            metadata = {
                'template_params': template_params,
                'access': access_specifier,
                'storage_class': cursor.storage_class.name if hasattr(cursor, 'storage_class') else None,
                'is_virtual': cursor.is_virtual_method() if hasattr(cursor, 'is_virtual_method') else False,
                'is_pure_virtual': cursor.is_pure_virtual_method() if hasattr(cursor,
                                                                              'is_pure_virtual_method') else False,
                'return_type': cursor.result_type.spelling if hasattr(cursor, 'result_type') else None
            }

            symbol = Symbol(
                name=full_name,
                symbol_type=symbol_type,
                line=line,
                context=context,
                cursor_kind=cursor.kind,
                metadata=metadata
            )

            source_file.add_definition(full_name, symbol_type, line, context, cursor.kind, metadata)
            self.symbol_definitions[full_name].append(symbol)

        # Processa il cursore corrente
        if cursor.kind in cursor_type_map:
            symbol_type = cursor_type_map[cursor.kind]

            if cursor.kind == CursorKind.VAR_DECL:
                if cursor.storage_class in {
                    clang.cindex.StorageClass.EXTERN,
                    clang.cindex.StorageClass.STATIC,
                    clang.cindex.StorageClass.NONE
                }:
                    process_symbol(cursor, symbol_type)
            else:
                process_symbol(cursor, symbol_type)

        # Analisi ricorsiva dei figli
        for child in cursor.get_children():
            self._analyze_definitions(child, source_file)

    def _analyze_usages(self, cursor, source_file: SourceFile):
        if not (cursor.location.file and Path(cursor.location.file.name) == source_file.path):
            return

        line = cursor.location.line
        context = self._get_context(source_file.raw_content, line)

        def get_template_specialization(cursor):
            if cursor.kind == CursorKind.TEMPLATE_REF:
                spec_args = []
                for arg in cursor.get_specialization_args():
                    if arg.kind == CursorKind.TYPE:
                        spec_args.append(arg.spelling)
                    elif arg.kind == CursorKind.LITERAL:
                        spec_args.append(str(arg.literal))
                return '<' + ', '.join(spec_args) + '>' if spec_args else ''
            return ''

        def get_full_symbol_name(cursor):
            if not cursor:
                return None

            name_parts = []
            current = cursor

            while current and current.kind != CursorKind.TRANSLATION_UNIT:
                if current.spelling:
                    if current.kind == CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION:
                        spec = get_template_specialization(current)
                        name_parts.append(current.spelling + spec)
                    else:
                        name_parts.append(current.spelling)
                current = current.semantic_parent

            return '::'.join(reversed(name_parts)) if name_parts else None

        def create_usage_metadata(cursor, referenced):
            metadata = {
                'is_declaration': cursor.is_declaration(),
                'is_definition': cursor.is_definition(),
                'is_reference': cursor.is_reference(),
                'is_expression': cursor.is_expression(),
                'is_statement': cursor.is_statement(),
                'access_specifier': cursor.access_specifier.name.lower() if hasattr(cursor,
                                                                                    'access_specifier') else None,
                'storage_class': referenced.storage_class.name if hasattr(referenced,
                                                                          'storage_class') else None,
                'is_virtual_method': referenced.is_virtual_method() if hasattr(referenced,
                                                                               'is_virtual_method') else False,
                'containing_function': None,
                'template_args': get_template_specialization(cursor),
                'type_info': cursor.type.spelling if hasattr(cursor, 'type') else None
            }

            current = cursor
            while current and current.kind != CursorKind.TRANSLATION_UNIT:
                if current.kind in {CursorKind.FUNCTION_DECL, CursorKind.METHOD_DECL,
                                    CursorKind.CONSTRUCTOR, CursorKind.DESTRUCTOR}:
                    metadata['containing_function'] = current.spelling
                    break
                current = current.semantic_parent

            return metadata

        if cursor.referenced and cursor.referenced.spelling:
            referenced = cursor.referenced
            symbol_name = get_full_symbol_name(referenced)

            if symbol_name:
                is_tracked_definition = any(
                    d.line == line and d.name == symbol_name
                    for d in source_file.definitions
                )

                if not is_tracked_definition:
                    kind = self._get_symbol_kind(referenced.kind)
                    if kind:
                        metadata = create_usage_metadata(cursor, referenced)
                        usage_symbol = Symbol(
                            name=symbol_name,
                            symbol_type=kind,
                            line=line,
                            context=context,
                            cursor_kind=referenced.kind,
                            metadata=metadata
                        )

                        source_file.add_usage(symbol_name, kind, line, context, referenced.kind, metadata)
                        self.symbol_usages[symbol_name].append((source_file.path, usage_symbol))

        for child in cursor.get_children():
            self._analyze_usages(child, source_file)

    def _get_symbol_kind(self, cursor_kind: CursorKind) -> Optional[str]:
        symbol_kind_map = {
            CursorKind.TYPEDEF_DECL: 'typedef',
            CursorKind.TYPE_REF: 'type',
            CursorKind.STRUCT_DECL: 'struct',
            CursorKind.UNION_DECL: 'union',
            CursorKind.CLASS_DECL: 'class',
            CursorKind.ENUM_DECL: 'enum',
            CursorKind.CLASS_TEMPLATE: 'class_template',
            CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION: 'class_template_spec',
            CursorKind.FUNCTION_TEMPLATE: 'function_template',
            CursorKind.TEMPLATE_REF: 'template',
            CursorKind.FUNCTION_DECL: 'function',
            CursorKind.METHOD_DECL: 'method',
            CursorKind.CONSTRUCTOR: 'constructor',
            CursorKind.DESTRUCTOR: 'destructor',
            CursorKind.CONVERSION_FUNCTION: 'conversion',
            CursorKind.VAR_DECL: 'variable',
            CursorKind.FIELD_DECL: 'field',
            CursorKind.ENUM_CONSTANT_DECL: 'enum_constant',
            CursorKind.MACRO_DEFINITION: 'macro',
            CursorKind.NAMESPACE: 'namespace',
            CursorKind.NAMESPACE_REF: 'namespace',
            CursorKind.MEMBER_REF: 'member',
            CursorKind.MEMBER_REF_EXPR: 'member',
            CursorKind.DECL_REF_EXPR: 'reference',
        }
        return symbol_kind_map.get(cursor_kind)

    def _get_context(self, content: str, line: int, context_size: int = 50) -> str:
        lines = content.splitlines()
        if 1 <= line <= len(lines):
            target_line = lines[line - 1]
            return target_line.strip()
        return ""

    def _resolve_include_path(self, included_path: str, current_file: Path) -> Optional[Path]:
        try:
            relative_path = (current_file.parent / included_path).resolve()
            if relative_path in self.files:
                return relative_path

            for project_path in self.project_paths:
                potential_path = (project_path / included_path).resolve()
                if potential_path in self.files:
                    return potential_path

            return None

        except Exception:
            return None

    def _is_source_file(self, file_path: Path) -> bool:
        return (
                file_path.is_file() and
                file_path.suffix.lower() in self.SOURCE_EXTENSIONS and
                not self._is_system_file(file_path)
        )

    def _is_system_file(self, file_path: Path) -> bool:
        system_dirs = {'System', 'Library', 'usr', 'include', 'frameworks'}
        return any(part.lower() in system_dirs for part in file_path.parts)

    def _get_relative_path(self, file_path: Path) -> Path:
        try:
            return file_path.relative_to(file_path.parent.parent)
        except ValueError:
            return file_path


from dataclasses import dataclass, field
from typing import Dict, List, Set, NamedTuple, Optional, Callable
from pathlib import Path
from collections import defaultdict
import contextlib
from readCLib import *
from typing import Dict, Set, List, Optional, DefaultDict, NamedTuple, Tuple
from collections import defaultdict
import re
import sys
import os
import subprocess
import clang.cindex
from clang.cindex import Index, CursorKind, TypeKind, Config

from typing import NamedTuple, Optional, Dict, Any
from clang.cindex import CursorKind


def get_full_name(cursor) -> str:
    """Ottiene il nome completo del simbolo includendo namespace, classe e template.

    Args:
        cursor: Cursore libclang che punta al simbolo

    Returns:
        str: Nome completo qualificato del simbolo
    """

    def _get_parent_context(cursor):
        """Costruisce il contesto del genitore ricorsivamente."""
        if cursor is None or cursor.kind == CursorKind.TRANSLATION_UNIT:
            return []

        # Ignora i contesti anonimi
        if not cursor.spelling and cursor.kind in {
            CursorKind.NAMESPACE,
            CursorKind.STRUCT_DECL,
            CursorKind.CLASS_DECL,
            CursorKind.CLASS_TEMPLATE
        }:
            return _get_parent_context(cursor.semantic_parent)

        return _get_parent_context(cursor.semantic_parent) + ([cursor.spelling] if cursor.spelling else [])

    # Ottieni il contesto del genitore
    parent_parts = _get_parent_context(cursor.semantic_parent)

    # Gestisci il nome del simbolo corrente
    current_name = cursor.spelling if cursor.spelling else ""

    # Aggiungi specializzazione template se presente
    if cursor.kind in {
        CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION,
        CursorKind.FUNCTION_TEMPLATE,
        CursorKind.CLASS_TEMPLATE
    }:
        template_params = get_template_params(cursor)
        if template_params:
            current_name = f"{current_name}{template_params}"

    # Combina il tutto
    if parent_parts:
        return "::".join(parent_parts + [current_name])
    return current_name


def get_template_params(cursor) -> str:
    """Estrae e formatta i parametri template di un simbolo.

    Args:
        cursor: Cursore libclang che punta al simbolo

    Returns:
        str: Stringa formattata dei parametri template o stringa vuota se non presenti
    """
    if cursor.kind not in {
        CursorKind.CLASS_TEMPLATE,
        CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION,
        CursorKind.FUNCTION_TEMPLATE
    }:
        return ""

    template_params = []

    def format_template_arg(arg):
        """Formatta un singolo argomento template."""
        if arg.kind == CursorKind.TEMPLATE_TYPE_PARAMETER:
            # Gestisce parametri di tipo (typename/class)
            name = arg.spelling or "typename"
            if arg.default_type:
                return f"{name} = {arg.default_type.spelling}"
            return name

        elif arg.kind == CursorKind.TEMPLATE_NON_TYPE_PARAMETER:
            # Gestisce parametri non-tipo (e.g., int N)
            param_type = arg.type.spelling
            param_name = arg.spelling
            if arg.default_value:
                return f"{param_type} {param_name} = {arg.default_value}"
            return f"{param_type} {param_name}"

        elif arg.kind == CursorKind.TEMPLATE_TEMPLATE_PARAMETER:
            # Gestisce parametri template-template
            name = arg.spelling or "template"
            inner_params = get_template_params(arg)
            if arg.default_type:
                return f"template {name}{inner_params} = {arg.default_type.spelling}"
            return f"template {name}{inner_params}"

        return str(arg.spelling)

    def get_specialization_args(cursor):
        """Ottiene gli argomenti di specializzazione per template parzialmente specializzati."""
        if cursor.kind == CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION:
            spec_args = []
            for arg in cursor.get_specialization_args():
                if arg.kind == CursorKind.TYPE:
                    spec_args.append(arg.spelling)
                elif arg.kind == CursorKind.LITERAL:
                    spec_args.append(str(arg.literal))
            return spec_args
        return []

    # Raccogli parametri template standard
    for child in cursor.get_children():
        if child.kind in {
            CursorKind.TEMPLATE_TYPE_PARAMETER,
            CursorKind.TEMPLATE_NON_TYPE_PARAMETER,
            CursorKind.TEMPLATE_TEMPLATE_PARAMETER
        }:
            template_params.append(format_template_arg(child))

    # Aggiungi argomenti di specializzazione se presenti
    spec_args = get_specialization_args(cursor)
    if spec_args:
        return f"<{', '.join(spec_args)}>"

    # Restituisci i parametri template standard
    return f"<{', '.join(template_params)}>" if template_params else ""

class Symbol(NamedTuple):
    """Rappresenta un simbolo definito nel codice sorgente.

    Attributes:
        name (str): Nome completo del simbolo (incluso namespace/classe padre)
        symbol_type (str): Tipo del simbolo (typedef, struct, function, etc.)
        line (int): Numero di riga dove appare il simbolo
        context (str): Contesto del codice intorno al simbolo
        cursor_kind (CursorKind): Tipo di cursore libclang
        metadata (Dict[str, Any]): Metadati aggiuntivi del simbolo che includono:
            - template_params (str): Parametri template se presenti
            - access (Optional[str]): Specificatore di accesso (public/private/protected)
            - storage_class (Optional[str]): Classe di storage (static/extern)
            - is_virtual (bool): Se il metodo è virtuale
            - is_pure_virtual (bool): Se il metodo è pure virtual
            - return_type (Optional[str]): Tipo di ritorno per funzioni/metodi
    """
    name: str
    symbol_type: str
    line: int
    context: str
    cursor_kind: CursorKind
    metadata: Dict[str, Any] = {}

    def __str__(self) -> str:
        """Rappresentazione leggibile del simbolo."""
        base = f"{self.symbol_type} {self.name} at line {self.line}"

        # Aggiungi informazioni template se presenti
        if self.metadata.get('template_params'):
            base = f"template{self.metadata['template_params']} " + base

        # Aggiungi tipo di ritorno per funzioni/metodi
        if self.metadata.get('return_type'):
            base = f"{self.metadata['return_type']} {base}"

        # Aggiungi specificatore di accesso per membri
        if self.metadata.get('access'):
            base = f"{self.metadata['access']} {base}"

        # Aggiungi informazioni sulla virtualità
        if self.metadata.get('is_pure_virtual'):
            base += " = 0"
        elif self.metadata.get('is_virtual'):
            base = f"virtual {base}"

        # Aggiungi storage class
        if self.metadata.get('storage_class'):
            base = f"{self.metadata['storage_class'].lower()} {base}"

        return base

    def get_qualified_name(self) -> str:
        """Restituisce il nome completamente qualificato del simbolo."""
        return self.name

    def is_member(self) -> bool:
        """Verifica se il simbolo è un membro di una classe/struct."""
        return self.metadata.get('access') is not None

    def is_template(self) -> bool:
        """Verifica se il simbolo è un template."""
        return bool(self.metadata.get('template_params'))

    def get_declaration(self) -> str:
        """Genera una rappresentazione della dichiarazione del simbolo."""
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
    available_types: Set[str] = field(default_factory=set)  # Tipi disponibili nel contesto
    
    def __hash__(self):
        return hash(self.path)
    
    def add_definition(self, name: str, kind: str, line: int, context: str, cursor_kind: Optional[CursorKind] = None):
        symbol = Symbol(name, kind, line, context, cursor_kind)
        self.definitions.append(symbol)
        if kind == 'type':
            self.available_types.add(name)
    
    def add_usage(self, name: str, kind: str, line: int, context: str, cursor_kind: Optional[CursorKind] = None):
        self.usages.append(Symbol(name, kind, line, context, cursor_kind))


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
                '/usr/lib/llvm-14/lib/libclang.so.1',  # Linux
                '/usr/lib/llvm-14/lib/libclang.so'
            ]
        except subprocess.CalledProcessError:
            possible_paths = [
                '/usr/lib/llvm-14/lib/libclang.so.1',  # Linux
                '/usr/lib/llvm-14/lib/libclang.so'
            ]
        
        for path in possible_paths:
            if os.path.exists(path):
                Config.set_library_file(path)
                return True
        
        print("ERRORE: libclang non trovato. Installa LLVM:")
        print("  macOS: brew install llvm")
        print("  Linux: sudo apt install libclang1")
        return False
    except Exception as e:
        print(f"ERRORE: {e}")
        return False

class SourceAnalyzer:
    SOURCE_EXTENSIONS = {'.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx', '.h++'}
    
    def __init__(self, project_paths: List[str]):
        if isinstance(project_paths, str):
            project_paths = [project_paths]
            
        self.project_paths = [Path(p) for p in project_paths] # Path(p).resolve()
        self.files: Dict[Path, SourceFile] = {}
        self.include_graph = defaultdict(set)
        self.reverse_graph = defaultdict(set)
        self.symbol_definitions: DefaultDict[str, List[Symbol]] = defaultdict(list)
        self.symbol_usages: DefaultDict[str, List[tuple[Path, Symbol]]] = defaultdict(list)
        
        if not setup_libclang():
            raise RuntimeError("Impossibile inizializzare libclang")
        self.index = Index.create()
    
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
                print(f"ATTENZIONE: {path} non è una directory valida")
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
                print(f"Errore durante la scansione di {path}: {e}")
        
        print(f"\nTrovati {len(found_files)} file sorgente nel progetto:")
        for file_path in sorted(found_files):
            rel_path = self._get_relative_path(file_path)
            print(f"  - {rel_path}")
    
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
            print(f"Errore analizzando {file_path}: {e}")
    
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
        """Analizza le definizioni usando il cursore di libclang.

        Supporta:
        - Typedef e tipi base
        - Struct/Union/Class
        - Enum e costanti enum
        - Funzioni e prototipi
        - Variabili globali/static
        - Macro
        - Template
        - Namespace
        """
        if not (cursor.location.file and Path(cursor.location.file.name) == source_file.path):
            return

        line = cursor.location.line
        context = self._get_context(source_file.raw_content, line)

        # Dizionario per mappare i tipi di cursore al tipo di simbolo
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

        def get_full_name(cursor):
            """Ottiene il nome completo includendo il namespace/classe padre."""
            parts = []
            current = cursor
            while current and current.kind != CursorKind.TRANSLATION_UNIT:
                if current.spelling:
                    parts.append(current.spelling)
                current = current.semantic_parent
            return '::'.join(reversed(parts))

        def get_template_params(cursor):
            """Estrae i parametri template se presenti."""
            template_params = []
            if cursor.kind in {CursorKind.CLASS_TEMPLATE, CursorKind.FUNCTION_TEMPLATE}:
                for child in cursor.get_children():
                    if child.kind == CursorKind.TEMPLATE_TYPE_PARAMETER:
                        template_params.append(child.spelling or 'typename')
                    elif child.kind == CursorKind.TEMPLATE_NON_TYPE_PARAMETER:
                        template_params.append(f"{child.type.spelling} {child.spelling}")
            return '<' + ', '.join(template_params) + '>' if template_params else ''

        def process_symbol(cursor, symbol_type):
            """Processa un simbolo e lo aggiunge alle definizioni."""
            full_name = get_full_name(cursor)
            template_params = get_template_params(cursor)

            # Gestione speciale per i membri di struct/class
            access_specifier = None
            if cursor.kind in {CursorKind.FIELD_DECL, CursorKind.METHOD_DECL}:
                access_specifier = cursor.access_specifier.name.lower()

            # Aggiunta metadati extra
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

            # Gestione speciale per le variabili
            if cursor.kind == CursorKind.VAR_DECL:
                if cursor.storage_class in {
                    clang.StorageClass.EXTERN,
                    clang.StorageClass.STATIC,
                    clang.StorageClass.NONE  # Per variabili globali
                }:
                    process_symbol(cursor, symbol_type)
            else:
                process_symbol(cursor, symbol_type)

        # Analisi ricorsiva dei figli
        for child in cursor.get_children():
            self._analyze_definitions(child, source_file)

    ####

    def _analyze_usages(self, cursor, source_file: SourceFile):
        """Analizza gli usi dei simboli usando il cursore di libclang.

        Traccia:
        - Utilizzo di tipi (inclusi template)
        - Chiamate a funzioni/metodi
        - Accesso a variabili/membri
        - Utilizzo di macro
        - Riferimenti a namespace
        - Specializzazioni template
        """
        if not (cursor.location.file and Path(cursor.location.file.name) == source_file.path):
            return

        line = cursor.location.line
        context = self._get_context(source_file.raw_content, line)

        def get_template_specialization(cursor):
            """Estrae informazioni sulla specializzazione template."""
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
            """Ottiene il nome completo del simbolo inclusi namespace e template."""
            if not cursor:
                return None

            name_parts = []
            current = cursor

            # Risali la catena dei genitori per costruire il nome completo
            while current and current.kind != CursorKind.TRANSLATION_UNIT:
                if current.spelling:
                    # Gestisci specializzazioni template
                    if current.kind == CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION:
                        spec = get_template_specialization(current)
                        name_parts.append(current.spelling + spec)
                    else:
                        name_parts.append(current.spelling)
                current = current.semantic_parent

            return '::'.join(reversed(name_parts)) if name_parts else None

        def create_usage_metadata(cursor, referenced):
            """Crea metadati dettagliati per l'utilizzo."""
            metadata = {
                'is_declaration': cursor.is_declaration(),
                'is_definition': cursor.is_definition(),
                'is_reference': cursor.is_reference(),
                'is_expression': cursor.is_expression(),
                'is_statement': cursor.is_statement(),
                'access_specifier': cursor.access_specifier.name.lower() if hasattr(cursor,
                                                                                    'access_specifier') else None,
                'storage_class': referenced.storage_class.name if hasattr(referenced, 'storage_class') else None,
                'is_virtual_method': referenced.is_virtual_method() if hasattr(referenced,
                                                                               'is_virtual_method') else False,
                'containing_function': None,
                'template_args': get_template_specialization(cursor),
                'type_info': cursor.type.spelling if hasattr(cursor, 'type') else None
            }

            # Trova la funzione contenitore
            current = cursor
            while current and current.kind != CursorKind.TRANSLATION_UNIT:
                if current.kind in {CursorKind.FUNCTION_DECL, CursorKind.METHOD_DECL,
                                    CursorKind.CONSTRUCTOR, CursorKind.DESTRUCTOR}:
                    metadata['containing_function'] = current.spelling
                    break
                current = current.semantic_parent

            return metadata

        # Analizza il cursore corrente
        if cursor.referenced and cursor.referenced.spelling:
            referenced = cursor.referenced
            symbol_name = get_full_symbol_name(referenced)

            if symbol_name:
                # Verifica che non sia una definizione già tracciata
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

        # Analisi ricorsiva
        for child in cursor.get_children():
            self._analyze_usages(child, source_file)

    def _get_symbol_kind(self, cursor_kind: CursorKind) -> Optional[str]:
        """Converte il tipo di cursore in un tipo di simbolo."""
        symbol_kind_map = {
            # Tipi base
            CursorKind.TYPEDEF_DECL: 'typedef',
            CursorKind.TYPE_REF: 'type',
            CursorKind.STRUCT_DECL: 'struct',
            CursorKind.UNION_DECL: 'union',
            CursorKind.CLASS_DECL: 'class',
            CursorKind.ENUM_DECL: 'enum',

            # Template
            CursorKind.CLASS_TEMPLATE: 'class_template',
            CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION: 'class_template_spec',
            CursorKind.FUNCTION_TEMPLATE: 'function_template',
            CursorKind.TEMPLATE_REF: 'template',

            # Funzioni e metodi
            CursorKind.FUNCTION_DECL: 'function',
            CursorKind.METHOD_DECL: 'method',
            CursorKind.CONSTRUCTOR: 'constructor',
            CursorKind.DESTRUCTOR: 'destructor',
            CursorKind.CONVERSION_FUNCTION: 'conversion',

            # Variabili e membri
            CursorKind.VAR_DECL: 'variable',
            CursorKind.FIELD_DECL: 'field',
            CursorKind.ENUM_CONSTANT_DECL: 'enum_constant',

            # Altri
            CursorKind.MACRO_DEFINITION: 'macro',
            CursorKind.NAMESPACE: 'namespace',
            CursorKind.NAMESPACE_REF: 'namespace',
            CursorKind.MEMBER_REF: 'member',
            CursorKind.MEMBER_REF_EXPR: 'member',
            CursorKind.DECL_REF_EXPR: 'reference',
        }

        return symbol_kind_map.get(cursor_kind)

    def _get_context(self, content: str, line: int, context_size: int = 50) -> str:
        """Estrae il contesto attorno a una linea specifica."""
        lines = content.splitlines()
        if 1 <= line <= len(lines):
            target_line = lines[line - 1]
            return target_line.strip()
        return ""
    
    def _resolve_include_path(self, included_path: str, current_file: Path) -> Optional[Path]:
        """Risolve il path completo di un file incluso."""
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
    
    def print_dependencies(self):
        """Stampa le dipendenze di tutti i file."""
        print("\nDipendenze dei file:")
        for file_path, source_file in sorted(self.files.items()):
            rel_path = self._get_relative_path(file_path)
            print(f"\n{rel_path}:")
            
            if source_file.includes:
                print("  Include:")
                for included in sorted(source_file.includes):
                    print(f"    - {self._get_relative_path(included)}")
            
            if source_file.included_by:
                print("  Incluso da:")
                for including in sorted(source_file.included_by):
                    print(f"    - {self._get_relative_path(including)}")
    
    def print_symbols(self):
        """Stampa i simboli definiti e usati in ogni file."""
        print("\nAnalisi dei simboli:")
        for file_path, source_file in sorted(self.files.items()):
            rel_path = self._get_relative_path(file_path)
            print(f"\n{rel_path}:")
            
            if source_file.definitions:
                print("  Definizioni:")
                for symbol in sorted(source_file.definitions):
                    print(f"    - {symbol.kind} '{symbol.name}' "
                          f"(linea {symbol.line})")
                    if symbol.context:
                        print(f"      {symbol.context}")
            
            if source_file.usages:
                print("  Usi:")
                for symbol in sorted(source_file.usages):
                    definitions = [
                        (path, sym) 
                        for name, syms in self.symbol_definitions.items() 
                        if name == symbol.name
                        for sym in syms
                        for path in self.files
                        if sym in self.files[path].definitions
                    ]
                    
                    if definitions:
                        def_file, def_sym = definitions[0]
                        print(f"    - {symbol.kind} '{symbol.name}' "
                              f"(linea {symbol.line}) -> "
                              f"definito in {self._get_relative_path(def_file)}:{def_sym.line}")
                        if symbol.context:
                            print(f"      Uso: {symbol.context}")
                            print(f"      Definizione: {def_sym.context}")
                    else:
                        print(f"    - {symbol.kind} '{symbol.name}' "
                              f"(linea {symbol.line}) -> definizione non trovata")
                        if symbol.context:
                            print(f"      Uso: {symbol.context}")
    
    def analyze_symbol(self, symbol_name: str):
        """Analizza in dettaglio un simbolo specifico."""
        print(f"\n=== Analisi dettagliata del simbolo '{symbol_name}' ===\n")
        
        # Trova le definizioni
        definitions = self.symbol_definitions.get(symbol_name, [])
        if definitions:
            print("Definizioni trovate:")
            for def_sym in definitions:
                # Trova il file che contiene questa definizione
                def_file = next(
                    path for path in self.files
                    if def_sym in self.files[path].definitions
                )
                print(f"\n  In {self._get_relative_path(def_file)}:{def_sym.line}")
                print(f"  Tipo: {def_sym.kind}")
                if def_sym.cursor_kind:
                    print(f"  Tipo Clang: {def_sym.cursor_kind}")
                print(f"  Contesto: {def_sym.context}")
                
                # Mostra i file che includono questa definizione
                if def_file in self.reverse_graph:
                    including_files = self.reverse_graph[def_file]
                    if including_files:
                        print("\n  Accessibile attraverso:")
                        for inc_file in sorted(including_files):
                            print(f"    - {self._get_relative_path(inc_file)}")
        
        # Trova gli usi
        usages = self.symbol_usages.get(symbol_name, [])
        if usages:
            print("\nUtilizzi trovati:")
            for use_file, use_sym in sorted(usages):
                print(f"\n  In {self._get_relative_path(use_file)}:{use_sym.line}")
                print(f"  Contesto: {use_sym.context}")
                
                # Verifica il percorso di inclusione verso la definizione
                if definitions:
                    def_file = next(
                        path for path in self.files
                        if definitions[0] in self.files[path].definitions
                    )
                    paths = self.find_include_paths(use_file, def_file)
                    if paths:
                        print("\n  Percorso di inclusione:")
                        for path in paths[0]:  # Mostra solo il primo percorso trovato
                            print(f"    - {self._get_relative_path(path)}")
                    else:
                        print("\n  ATTENZIONE: Nessun percorso di inclusione trovato!")
        
        if not definitions and not usages:
            print(f"Nessuna informazione trovata per il simbolo '{symbol_name}'")
    
    def find_include_paths(self, from_file: Path, to_file: Path, 
                          max_depth: int = 10) -> List[List[Path]]:
        """Trova tutti i percorsi di inclusione tra due file."""
        def dfs(current: Path, target: Path, visited: Set[Path], 
                path: List[Path], depth: int) -> List[List[Path]]:
            if depth > max_depth:
                return []
            
            if current == target:
                return [path + [current]]
            
            if current in visited:
                return []
            
            paths = []
            visited.add(current)
            
            for next_file in self.include_graph[current]:
                for new_path in dfs(next_file, target, visited.copy(), 
                                  path + [current], depth + 1):
                    paths.append(new_path)
            
            return paths
        
        return dfs(from_file, to_file, set(), [], 0)
    
    def find_cycles(self):
        """Trova e stampa eventuali cicli di inclusione."""
        def dfs(current: Path, visited: Set[Path], path: List[Path]) -> List[List[Path]]:
            if current in path:
                cycle_start = path.index(current)
                return [path[cycle_start:] + [current]]
            
            cycles = []
            for next_file in self.include_graph[current]:
                if next_file not in visited:
                    visited.add(next_file)
                    for cycle in dfs(next_file, visited, path + [current]):
                        cycles.append(cycle)
                    visited.remove(next_file)
            
            return cycles
        
        print("\nRicerca cicli di inclusione:")
        cycles_found = False
        
        for file_path in self.files:
            cycles = dfs(file_path, set(), [])
            for cycle in cycles:
                cycles_found = True
                print("\nCiclo trovato:")
                print("  " + " -> ".join(str(self._get_relative_path(p)) for p in cycle))
        
        if not cycles_found:
            print("Nessun ciclo di inclusione trovato.")
    
    def suggest_missing_includes(self):
        """Suggerisce include mancanti basandosi sull'analisi dei simboli."""
        print("\nAnalisi degli #include mancanti:")
        
        for file_path, source_file in sorted(self.files.items()):
            missing_includes = set()
            
            # Per ogni simbolo usato
            for usage in source_file.usages:
                # Trova dove è definito il simbolo
                definitions = [
                    (path, sym) 
                    for name, syms in self.symbol_definitions.items() 
                    if name == usage.name
                    for sym in syms
                    for path in self.files
                    if sym in self.files[path].definitions
                ]
                
                if definitions:
                    def_file, _ = definitions[0]
                    # Se il file di definizione non è incluso direttamente o indirettamente
                    if not self._is_symbol_accessible(usage.name, file_path):
                        missing_includes.add(def_file)
            
            if missing_includes:
                rel_path = self._get_relative_path(file_path)
                print(f"\n{rel_path} potrebbe necessitare di:")
                for inc in sorted(missing_includes):
                    print(f"  #include \"{self._get_relative_path(inc)}\"")
    
    def _is_symbol_accessible(self, symbol_name: str, from_file: Path, 
                            visited: Optional[Set[Path]] = None) -> bool:
        """Verifica se un simbolo è accessibile da un file attraverso gli include."""
        if visited is None:
            visited = set()
        
        if from_file in visited:
            return False
        
        visited.add(from_file)
        
        # Verifica se il simbolo è definito nel file corrente
        current_file = self.files[from_file]
        if any(d.name == symbol_name for d in current_file.definitions):
            return True
        
        # Verifica ricorsivamente nei file inclusi
        for included in current_file.includes:
            if self._is_symbol_accessible(symbol_name, included, visited):
                return True
        
        return False

    def analyze_symbol_locations(self):
        """Analizza e stampa un report sulla locazione dei simboli."""
        print("\nAnalisi della locazione dei simboli:")

        for file_path, source_file in sorted(self.files.items()):
            internal_symbols = []
            project_symbols = []
            external_symbols = []

            for symbol in source_file.definitions:
                location = symbol.metadata.get('symbol_location', {})
                if location.get('is_internal'):
                    internal_symbols.append(symbol)
                elif location.get('is_project_local'):
                    project_symbols.append(symbol)
                elif location.get('is_external'):
                    external_symbols.append(symbol)

            if any([internal_symbols, project_symbols, external_symbols]):
                rel_path = self._get_relative_path(file_path)
                print(f"\n{rel_path}:")

                if internal_symbols:
                    print("  Simboli dichiarati internamente:")
                    for sym in internal_symbols:
                        print(f"    - {sym.kind} '{sym.name}' (linea {sym.line})")

                if project_symbols:
                    print("  Simboli del progetto:")
                    for sym in project_symbols:
                        location = sym.metadata['symbol_location']
                        decl_file = location['declaration_file']
                        print(f"    - {sym.kind} '{sym.name}' dichiarato in {decl_file}")

                if external_symbols:
                    print("  Simboli esterni:")
                    for sym in external_symbols:
                        location = sym.metadata['symbol_location']
                        decl_file = location['declaration_file']
                        print(f"    - {sym.kind} '{sym.name}' da {decl_file}")

    def _analyze_symbol_location(self, cursor, source_file: SourceFile):
        """Analizza se un simbolo è dichiarato internamente o esternamente."""
        if not (cursor.location.file and Path(cursor.location.file.name) == source_file.path):
            return

        def determine_symbol_location(cursor) -> dict:
            """Determina la locazione di un simbolo e raccoglie metadati sulla sua origine."""
            location_info = {
                'is_internal': False,  # Dichiarato in questo file
                'is_project_local': False,  # Dichiarato in un altro file del progetto
                'is_external': False,  # Dichiarato in un header di sistema/esterno
                'declaration_file': None,  # Path del file di dichiarazione
                'definition_file': None,  # Path del file di definizione
                'is_forward_declared': False,  # Se è una forward declaration
            }

            # Ottieni la dichiarazione e definizione
            declaration = cursor.get_definition() or cursor
            definition = cursor.get_definition()

            if declaration.location.file:
                decl_path = Path(declaration.location.file.name)
                location_info['declaration_file'] = decl_path

                # Controlla se è una dichiarazione interna
                if decl_path == source_file.path:
                    location_info['is_internal'] = True
                # Controlla se è nel progetto
                elif any(decl_path.is_relative_to(p) for p in self.project_paths):
                    location_info['is_project_local'] = True
                else:
                    location_info['is_external'] = True

            # Controlla se è una forward declaration
            if declaration != definition and definition:
                location_info['is_forward_declared'] = True
                if definition.location.file:
                    location_info['definition_file'] = Path(definition.location.file.name)

            return location_info

        def update_symbol_metadata(symbol: Symbol, location_info: dict):
            """Aggiorna i metadati del simbolo con le informazioni sulla locazione."""
            metadata = symbol.metadata or {}
            metadata.update({
                'symbol_location': {
                    'is_internal': location_info['is_internal'],
                    'is_project_local': location_info['is_project_local'],
                    'is_external': location_info['is_external'],
                    'declaration_file': str(location_info['declaration_file']) if location_info[
                        'declaration_file'] else None,
                    'definition_file': str(location_info['definition_file']) if location_info[
                        'definition_file'] else None,
                    'is_forward_declared': location_info['is_forward_declared']
                }
            })
            return metadata

        # Aggiorna _analyze_definitions per includere le informazioni sulla locazione
        def enhanced_process_symbol(cursor, symbol_type):
            """Versione estesa di process_symbol che include informazioni sulla locazione."""
            location_info = determine_symbol_location(cursor)
            full_name = get_full_name(cursor)
            template_params = get_template_params(cursor)

            # Ottieni i metadati esistenti e aggiungi le informazioni sulla locazione
            metadata = {
                'template_params': template_params,
                'access': cursor.access_specifier.name.lower() if hasattr(cursor, 'access_specifier') else None,
                'storage_class': cursor.storage_class.name if hasattr(cursor, 'storage_class') else None,
                'is_virtual': cursor.is_virtual_method() if hasattr(cursor, 'is_virtual_method') else False,
                'is_pure_virtual': cursor.is_pure_virtual_method() if hasattr(cursor,
                                                                              'is_pure_virtual_method') else False,
                'return_type': cursor.result_type.spelling if hasattr(cursor, 'result_type') else None,
            }

            # Aggiorna con le informazioni sulla locazione
            metadata = update_symbol_metadata(
                Symbol(name=full_name, symbol_type=symbol_type, line=cursor.location.line,
                       context="", cursor_kind=cursor.kind, metadata=metadata),
                location_info
            )

            symbol = Symbol(
                name=full_name,
                symbol_type=symbol_type,
                line=cursor.location.line,
                context=self._get_context(source_file.raw_content, cursor.location.line),
                cursor_kind=cursor.kind,
                metadata=metadata
            )

            source_file.add_definition(full_name, symbol_type, cursor.location.line,
                                       self._get_context(source_file.raw_content, cursor.location.line),
                                       cursor.kind, metadata)
            self.symbol_definitions[full_name].append(symbol)

        return enhanced_process_symbol


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
class SymbolTable:
    """Global symbol management"""
    definitions: Dict[str, List[SymbolDefinition]] = field(default_factory=lambda: defaultdict(list))
    usages: Dict[str, List[SymbolUsage]] = field(default_factory=lambda: defaultdict(list))
    dependencies: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))

    def __init__(self):
        self.dependencies = {}
        self.usages = {}
        self.definitions = {}
        self.dependenciesCache: Dict[str, object] = {}

    def add_definition(self, symbol: SymbolDefinition):
        if symbol.name not in self.definitions:
            self.definitions[symbol.name] = []

        self.definitions[symbol.name].append(symbol)

    def check_dependency(self, dep: str):
        if dep not in self.dependencies:
            self.dependencies[dep] = set()

    def add_usage(self, usage: SymbolUsage):
        if usage.name not in self.usages:
            self.usages[usage.name] = []

        self.usages[usage.name].append(usage)
        # Update symbol dependencies
        for req in usage.required_symbols:
            self.check_dependency(usage.name)
            self.dependencies[usage.name].add(req)
    
    def get_symbol_providers(self, symbol_name: str) -> List[Path]:
        """Get all files that provide a given symbol"""
        return [def_.file for def_ in self.definitions.get(symbol_name, [])]

    def get_symbol_dependencies(self, symbol_name: str, visited: Optional[Set[str]] = None) -> Set[str]:
        """
        Get all symbols that a given symbol depends on, avoiding circular dependencies.

        Args:
            symbol_name: Name of the symbol to analyze
            visited: Set of already visited symbols in the current recursion path

        Returns:
            Set of all dependent symbols
        """

        if symbol_name in self.dependenciesCache:
            return self.dependenciesCache[symbol_name]

        print("get_symbol_dependencies: ", symbol_name, visited)

        # Initialize visited set on first call
        if visited is None:
            visited = set()

        # Check for circular dependency
        if symbol_name in visited:
            return set()  # Break the cycle

        # Mark current symbol as visited
        visited.add(symbol_name)

        # Get direct dependencies
        direct_deps = self.dependencies.get(symbol_name, set())
        all_deps = set(direct_deps)

        # Recursively get transitive dependencies
        for dep in direct_deps:
            # Only recurse if we haven't seen this dependency yet
            if dep not in visited:
                # Pass the visited set to track the full recursion path
                all_deps.update(self.get_symbol_dependencies(dep, visited))

        # Remove current symbol from visited when backtracking
        visited.remove(symbol_name)

        self.dependenciesCache[symbol_name] = all_deps

        return all_deps

    # Alternative implementation using a context manager for better readability
    @contextlib.contextmanager
    def _track_dependency_path(self, symbol: str, path: Set[str]):
        """Context manager to track dependency path and handle cleanup"""
        path.add(symbol)
        try:
            yield
        finally:
            path.remove(symbol)

    def get_symbol_dependencies_alt(self, symbol_name: str, _path: Optional[Set[str]] = None) -> Set[str]:
        """
        Alternative implementation using a context manager for cleaner recursion tracking.

        Args:
            symbol_name: Name of the symbol to analyze
            _path: Internal parameter to track recursion path

        Returns:
            Set of all dependent symbols
        """
        # Initialize tracking set on first call
        if _path is None:
            _path = set()

        # Check for circular dependency
        if symbol_name in _path:
            return set()  # Break the cycle

        all_deps = set()

        # Use context manager to track current symbol in path
        with self._track_dependency_path(symbol_name, _path):
            # Get direct dependencies
            direct_deps = self.dependencies.get(symbol_name, set())
            all_deps.update(direct_deps)

            # Recursively get transitive dependencies
            for dep in direct_deps:
                if dep not in _path:  # Only recurse if not creating a cycle
                    all_deps.update(self.get_symbol_dependencies_alt(dep, _path))

        return all_deps

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


class ImprovedIncludeResolver:
    def __init__(self, source_files: Dict[Path, SourceFile]):
        self.source_files = source_files
        self.symbol_table = SymbolTable()
        self.header_deps: Dict[Path, HeaderDependencies] = {}
        self.include_order: Dict[Path, List[Path]] = {}
        self.available_types: Dict[Path, Set[str]] = {}  # Cache dei tipi disponibili per file
        self.type_declarations: Dict[str, Set[Path]] = defaultdict(set)  # Dove ogni tipo è dichiarato
        self.type_dependencies: Dict[Path, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))  # Dipendenze tra tipi per file
        
    def _analyze_type_declarations(self):
        """Analizza dove ogni tipo è dichiarato"""
        self.type_declarations.clear()
        for path, source in self.source_files.items():
            for def_ in source.definitions:
                if def_.kind == 'type':
                    self.type_declarations[def_.name].add(path)
    
    def _analyze_type_dependencies_in_file(self, file_path: Path):
        """Analizza le dipendenze tra tipi in un file"""
        source = self.source_files[file_path]
        file_deps = self.type_dependencies[file_path]
        
        # Analizza le definizioni per trovare dipendenze nei tipi composti
        for def_ in source.definitions:
            if def_.kind == 'type':
                deps = self._extract_type_refs_from_context(def_.context)
                if deps:
                    file_deps[def_.name].update(deps)
        
        # Analizza gli usi per trovare dipendenze nelle dichiarazioni di variabili e funzioni
        for usage in source.usages:
            context_types = self._extract_type_refs_from_context(usage.context)
            if context_types:
                # Se l'uso è parte di una definizione di tipo, aggiungi la dipendenza
                defining_type = self._find_defining_type(usage.line, source.definitions)
                if defining_type:
                    file_deps[defining_type].update(context_types)
    
    def _extract_type_refs_from_context(self, context: str) -> Set[str]:
        """Estrae riferimenti a tipi dal contesto, considerando pattern comuni in C/C++"""
        type_refs = set()
        
        # Pattern comuni per riferimenti a tipi in C/C++
        patterns = [
            r'\bstruct\s+(\w+)',  # struct declarations
            r'\bunion\s+(\w+)',   # union declarations
            r'\benum\s+(\w+)',    # enum declarations
            r'\bclass\s+(\w+)',   # class declarations
            r'(\w+)\s*[*&]',      # pointer/reference types
            r'(\w+)\s*\w+\s*[;,)]',  # variable/parameter declarations
            r'(\w+)\s*<',         # template usage
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, context)
            for match in matches:
                type_name = match.group(1)
                if type_name in self.type_declarations:
                    type_refs.add(type_name)
        
        return type_refs
    
    def _find_defining_type(self, line: int, definitions: List[Symbol]) -> Optional[str]:
        """Trova il tipo che sta venendo definito a una determinata linea"""
        for def_ in definitions:
            if def_.kind == 'type' and def_.line == line:
                return def_.name
        return None
    
    def _calculate_available_types(self, file_path: Path, visited: Optional[Set[Path]] = None) -> Set[str]:
        """Calcola ricorsivamente i tipi disponibili per un file, considerando l'ordine di inclusione"""
        if visited is None:
            visited = set()
            
        if file_path in visited:
            return set()  # Evita cicli infiniti
            
        visited.add(file_path)
        source = self.source_files[file_path]
        
        # Parti con i tipi definiti direttamente nel file
        available = set(source.available_types)
        
        # Aggiungi i tipi dagli include nell'ordine corretto
        include_order = self.get_include_order(file_path)
        if not include_order:  # Se non abbiamo ancora calcolato l'ordine, usa l'ordine attuale
            include_order = source.includes
            
        for include in include_order:
            if include in self.source_files and include not in visited:
                # Aggiungi i tipi disponibili dall'include
                include_types = self._calculate_available_types(include, visited)
                available.update(include_types)
                
                # Verifica se questo include fornisce tipi necessari per le definizioni locali
                local_deps = self.type_dependencies[file_path]
                for local_type, deps in local_deps.items():
                    if not (deps - available):  # Se tutte le dipendenze sono disponibili
                        available.add(local_type)
        
        visited.remove(file_path)
        return available
    
    def _resolve_include_order(self):
        """Determina l'ordine ottimale di inclusione basato sulle dipendenze dei tipi"""
        def calculate_score(include: Path, required: Set[str], available: Set[str]) -> int:
            """Calcola un punteggio per un include basato su quanti tipi richiesti fornisce"""
            include_types = self._calculate_available_types(include, set())
            needed_types = required & include_types
            blocking_types = set()
            
            # Controlla se questo include fornisce tipi necessari per altri tipi
            for type_name, deps in self.type_dependencies[include].items():
                if deps - available:  # Se ci sono dipendenze non ancora disponibili
                    blocking_types.add(type_name)
            
            return len(needed_types) - len(blocking_types)
        
        def process_header(path: Path, visited: Set[Path]) -> List[Path]:
            if path in visited:
                return []
                
            if path in self.include_order:
                return self.include_order[path]
                
            visited.add(path)
            source = self.source_files[path]
            order = []
            available_types = set(source.available_types)
            remaining_includes = set(source.includes)
            
            while remaining_includes:
                best_score = float('-inf')
                best_include = None
                
                for inc in remaining_includes:
                    if inc in self.source_files:
                        score = calculate_score(inc, self._get_required_types(path), available_types)
                        if score > best_score:
                            best_score = score
                            best_include = inc
                
                if best_include:
                    # Aggiungi gli include necessari per questo include
                    order.extend(process_header(best_include, visited.copy()))
                    order.append(best_include)
                    remaining_includes.remove(best_include)
                    available_types.update(self._calculate_available_types(best_include, set()))
                else:
                    # Aggiungi i rimanenti in ordine arbitrario
                    for inc in sorted(remaining_includes):
                        if inc in self.source_files:
                            order.extend(process_header(inc, visited.copy()))
                            order.append(inc)
                    break
            
            visited.remove(path)
            self.include_order[path] = order
            return order
        
        # Processa tutti gli header
        self.include_order.clear()
        for path in self.source_files:
            if path not in self.include_order and self.source_files[path].is_header:
                process_header(path, set())
    
    def _get_required_types(self, file_path: Path) -> Set[str]:
        """Ottiene tutti i tipi richiesti da un file, incluse le dipendenze indirette"""
        required = set()
        source = self.source_files[file_path]
        
        # Aggiungi dipendenze dirette dai tipi definiti
        for type_name, deps in self.type_dependencies[file_path].items():
            required.update(deps)
        
        # Aggiungi tipi usati nel file
        for usage in source.usages:
            context_types = self._extract_type_refs_from_context(usage.context)
            required.update(context_types)
        
        return required
    
    def analyze(self):
        """Main analysis workflow con analisi migliorata dei tipi"""
        self._analyze_type_declarations()
        
        # Analizza le dipendenze dei tipi per ogni file
        for path in self.source_files:
            self._analyze_type_dependencies_in_file(path)
        
        self._build_symbol_table()
        self._analyze_dependencies()
        self._resolve_include_order()
        
        # Calcola i tipi disponibili per tutti i file
        for path in self.source_files:
            self._calculate_available_types(path)

    def _check_type_dependencies(self, source: SourceFile) -> Set[str]:
        """Verifica le dipendenze dei tipi per un file"""
        required_types = set()
        
        # Estrai i tipi richiesti dalle definizioni
        for def_ in source.definitions:
            if def_.kind == 'type':
                context_types = self._extract_type_dependencies(def_.context)
                required_types.update(context_types)
                
        # Estrai i tipi richiesti dagli usi
        for usage in source.usages:
            context_types = self._extract_type_dependencies(usage.context)
            required_types.update(context_types)
            
        return required_types
    
    def _extract_type_dependencies(self, context: str) -> Set[str]:
        """Estrae le dipendenze di tipo dal contesto"""
        type_deps = set()
        words = re.findall(r'\b\w+\b', context)
        
        for word in words:
            # Verifica se il word è un tipo conosciuto
            if any(word in self.source_files[file].available_types 
                  for file in self.source_files):
                type_deps.add(word)
                
        return type_deps

    def verify_includes(self) -> dict:
        """Verifica le relazioni di inclusione e identifica i problemi"""
        issues = {
            'missing_types': defaultdict(set),
            'circular_deps': [],
            'unnecessary_includes': defaultdict(set)
        }
        
        # Verifica i tipi mancanti
        for path, source in self.source_files.items():
            required_types = self._check_type_dependencies(source)
            available_types = self._calculate_available_types(path)
            
            missing = required_types - available_types
            if missing:
                issues['missing_types'][str(path)] = missing
        
        # Trova le dipendenze circolari
        issues['circular_deps'] = self._find_circular_deps()
        
        # Trova gli include non necessari
        for path, source in self.source_files.items():
            required_types = self._check_type_dependencies(source)
            
            for inc in source.includes:
                if inc not in self.source_files:
                    continue
                    
                inc_types = self._calculate_available_types(inc)
                if not (required_types & inc_types):
                    issues['unnecessary_includes'][str(path)].add(str(inc))
        
        return issues

    def _build_symbol_table(self):
        """Build global symbol table from source files"""
        for path, source in self.source_files.items():
            # Process definitions
            for def_ in source.definitions:
                symbol_def = SymbolDefinition(
                    name=def_.name,
                    kind=def_.kind,
                    file=path,
                    line=def_.line,
                    scope=def_.context,
                    dependencies=self._extract_dependencies(def_.context)
                )
                self.symbol_table.add_definition(symbol_def)

            # Process usages
            for usage in source.usages:
                symbol_usage = SymbolUsage(
                    name=usage.name,
                    file=path,
                    line=usage.line,
                    context=usage.context,
                    required_symbols=self._extract_dependencies(usage.context)
                )
                self.symbol_table.add_usage(symbol_usage)

    def _find_circular_deps(self) -> List[List[str]]:
        """Find circular dependencies in the include graph"""
        cycles = []
        visited = set()
        path_stack = []

        def dfs(current: Path):
            if current in path_stack:
                start = path_stack.index(current)
                cycle = [str(p) for p in path_stack[start:]]
                cycles.append(cycle)
                return

            if current in visited:
                return

            visited.add(current)
            path_stack.append(current)

            if current in self.header_deps:
                for inc in self.header_deps[current].direct_includes:
                    dfs(inc)

            path_stack.pop()

        # Start DFS from each header
        for header in self.header_deps:
            if header not in visited:
                dfs(header)

        return cycles

    def _extract_dependencies(self, context: str) -> Set[str]:
        """Extract symbol dependencies from context"""
        deps = set()
        words = re.findall(r'\b\w+\b', context)
        for word in words:
            if word in self.symbol_table.definitions:
                deps.add(word)
        return deps

    def _analyze_dependencies(self):
        """Analyze header dependencies and build dependency graph"""
        for path, source in self.source_files.items():
            if not source.is_header:
                continue

            deps = HeaderDependencies(path)

            # Add symbols provided by this header
            for def_ in source.definitions:
                deps.add_provided_symbol(def_.name)

            # Add symbols required by this header
            for usage in source.usages:
                deps.add_required_symbol(usage.name)

            # Add direct includes
            for include in source.includes:
                deps.add_include(include)

            self.header_deps[path] = deps

        # Build transitive includes and dependents
        self._build_transitive_relations()

    def _build_transitive_relations(self):
        """Build transitive include relationships"""
        changed = True
        while changed:
            changed = False
            for deps in self.header_deps.values():
                old_size = len(deps.transitive_includes)

                # Add includes from direct includes
                for direct in deps.direct_includes:
                    if direct in self.header_deps:
                        deps.transitive_includes.update(
                            self.header_deps[direct].transitive_includes
                        )

                if len(deps.transitive_includes) > old_size:
                    changed = True

        # Build dependent relationships
        for path, deps in self.header_deps.items():
            for inc in deps.direct_includes:
                if inc in self.header_deps:
                    self.header_deps[inc].dependents.add(path)

    def get_source_analysis(self) -> Dict[str, dict]:
        """
        Get comprehensive analysis for all source files including type information.
        """
        sources = {}
        
        for path, source in self.source_files.items():
            str_path = str(path)
            header_deps = self.header_deps.get(path)
            
            # Base source info
            source_info = {
                'path': str_path,
                'is_header': source.is_header,
                'symbols': {
                    'provided': [],
                    'required': [],
                    'types': {
                        'available': list(source.available_types),
                        'required': list(self._check_type_dependencies(source))
                    }
                },
                'includes': {
                    'optimal_order': [str(p) for p in self.get_include_order(path)],
                    'current': [str(p) for p in source.includes],
                    'direct': [],
                    'transitive': [],
                    'unnecessary': []
                },
                'dependencies': {
                    'dependent_files': [],
                    'dependency_chain': self._get_dependency_chain(path),
                    'type_dependencies': self._get_type_dependency_chain(path)
                },
                'analysis': {
                    'has_circular_deps': False,
                    'missing_symbols': [],
                    'missing_types': [],
                    'symbol_overlap': [],
                    'include_suggestions': []
                }
            }
            
            # Add symbol information
            if header_deps:
                # Provided symbols with details
                for symbol in header_deps.provided_symbols:
                    symbol_info = self._get_symbol_info(symbol, path)
                    source_info['symbols']['provided'].append(symbol_info)
                
                # Required symbols with details
                for symbol in header_deps.required_symbols:
                    symbol_info = self._get_symbol_info(symbol, path)
                    source_info['symbols']['required'].append(symbol_info)
                
                # Include relationships
                source_info['includes']['direct'] = [
                    str(p) for p in header_deps.direct_includes
                ]
                source_info['includes']['transitive'] = [
                    str(p) for p in header_deps.transitive_includes
                ]
                source_info['dependencies']['dependent_files'] = [
                    str(p) for p in header_deps.dependents
                ]
            
            # Add analysis information with type checks
            self._add_analysis_info(source_info, path)
            
            sources[str_path] = source_info
            
        return sources

    def _get_symbol_info(self, symbol_name: str, file_path: Path) -> dict:
        """Get detailed information about a symbol"""
        symbol_info = {
            'name': symbol_name,
            'type': 'unknown',
            'definitions': [],
            'usages': [],
            'dependencies': list(self.symbol_table.get_symbol_dependencies(symbol_name))
        }

        # Add definition information
        for def_ in self.symbol_table.definitions.get(symbol_name, []):
            symbol_info['type'] = def_.kind
            def_info = {
                'file': str(def_.file),
                'line': def_.line,
                'scope': def_.scope,
                'is_exported': def_.is_exported
            }
            symbol_info['definitions'].append(def_info)

        # Add usage information
        for usage in self.symbol_table.usages.get(symbol_name, []):
            if usage.file == file_path:
                usage_info = {
                    'line': usage.line,
                    'context': usage.context,
                    'required_symbols': list(usage.required_symbols)
                }
                symbol_info['usages'].append(usage_info)

        return symbol_info

    def get_include_order(self, file_path: Path) -> List[Path]:
        """Get the optimal include order for a file"""
        return self.include_order.get(file_path, [])

    def _get_dependency_chain(self, path: Path) -> List[List[str]]:
        """Get all possible dependency chains for a file"""
        chains = []
        visited = set()

        def build_chain(current: Path, current_chain: List[Path]):
            if current in visited:
                return

            visited.add(current)
            current_chain.append(current)

            if current in self.header_deps:
                deps = self.header_deps[current]
                if not deps.direct_includes:
                    chains.append([str(p) for p in current_chain])
                else:
                    for inc in deps.direct_includes:
                        build_chain(inc, current_chain[:])

            visited.remove(current)

        build_chain(path, [])
        return chains

    def _get_type_dependency_chain(self, path: Path) -> List[dict]:
        """Get dependency chain based on type requirements"""
        chain = []
        source = self.source_files[path]
        required_types = self._check_type_dependencies(source)
        
        for type_name in required_types:
            providers = []
            for inc_path in source.includes:
                if inc_path in self.source_files:
                    inc_types = self._calculate_available_types(inc_path)
                    if type_name in inc_types:
                        providers.append({
                            'file': str(inc_path),
                            'direct_provider': type_name in self.source_files[inc_path].available_types
                        })
            
            if providers:
                chain.append({
                    'type': type_name,
                    'providers': providers
                })
        
        return chain

    def _add_analysis_info(self, source_info: dict, path: Path):
        """Add analysis information including type analysis to source info"""
        # Existing checks (circular deps, etc.)
        #super()._add_analysis_info(source_info, path)
        
        # Add type-specific analysis
        source = self.source_files[path]
        required_types = self._check_type_dependencies(source)
        available_types = self._calculate_available_types(path)
        
        # Find missing types
        missing_types = required_types - available_types
        if missing_types:
            source_info['analysis']['missing_types'] = list(missing_types)
        
        # Update include suggestions based on type dependencies
        suggestions = source_info['analysis']['include_suggestions']
        
        # Check for better include ordering based on types
        current_order = [str(p) for p in source.includes]
        optimal_order = [str(p) for p in self.get_include_order(path)]
        
        if current_order != optimal_order:
            suggestions.append({
                'type': 'reorder',
                'message': 'Consider reordering includes to resolve type dependencies properly',
                'current_order': current_order,
                'suggested_order': optimal_order,
                'affected_types': list(required_types)
            })
    
def usage():
    project_paths = "c-project/"

    analyzer = SourceAnalyzer([project_paths])
    analyzer.analyze()

    #result = optimize_includes(analyzer.files)
    # Create resolver
    resolver = ImprovedIncludeResolver(analyzer.files)

    # Run analysis
    resolver.analyze()

    # Get comprehensive source analysis
    sources = resolver.get_source_analysis()

    # Verify includes
    issues = resolver.verify_includes()

    result = {}
    result['sources'] = sources
    result['issues'] = issues
    return result
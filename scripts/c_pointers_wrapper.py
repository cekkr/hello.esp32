import subprocess
from clang.cindex import Index, CursorKind, TokenKind, Config
import sys
import os
from dataclasses import dataclass
from typing import List, Dict, Set, Tuple

def setup_libclang() -> bool:
    """Configura il percorso di libclang per macOS"""
    try:
        brew_prefix = subprocess.check_output(['brew', '--prefix']).decode().strip()
        possible_paths = [
            os.path.join(brew_prefix, 'opt/llvm/lib/libclang.dylib'),
            '/Library/Developer/CommandLineTools/usr/lib/libclang.dylib',
            '/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib/libclang.dylib'
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                Config.set_library_file(path)
                return True
        
        print("ERRORE: libclang non trovato. Installa LLVM:")
        print("brew install llvm")
        return False
    except subprocess.CalledProcessError:
        print("ERRORE: Homebrew non trovato. Installa Homebrew da https://brew.sh")
        return False


@dataclass
class PointerOperation:
    line: int
    column: int
    name: str
    is_assignment: bool
    source_file: str


class SourceFile:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.pointer_ops: List[PointerOperation] = []
        self.includes: Set[str] = set()

    def add_operation(self, op: PointerOperation):
        self.pointer_ops.append(op)

    def add_include(self, include_path: str):
        self.includes.add(include_path)


class PointerAnalyzer:
    def __init__(self, print_debug: bool = False):
        self.print_debug = print_debug
        self.files: Dict[str, SourceFile] = {}
        self.index = Index.create()

    def debug_print(self, message: str):
        if self.print_debug:
            print(f"[DEBUG] {message}")

    def is_pointer_assignment(self, node) -> bool:
        try:
            # Check for pointer declaration with assignment
            if node.kind == CursorKind.VAR_DECL:
                type_str = node.type.spelling
                return '*' in type_str and any(c.kind == CursorKind.INIT_LIST_EXPR for c in node.get_children())

            # Check for direct pointer assignment
            if node.kind == CursorKind.BINARY_OPERATOR:
                tokens = list(node.get_tokens())
                return (len(tokens) >= 3 and
                        tokens[1].spelling == '=' and
                        any('*' in t.spelling for t in tokens))

            return False
        except Exception as e:
            self.debug_print(f"Pointer assignment check error: {str(e)}")
            return False

    def is_pointer_dereference(self, node) -> bool:
        try:
            if node.kind == CursorKind.UNARY_OPERATOR:
                tokens = list(node.get_tokens())
                return (len(tokens) > 0 and
                        tokens[0].spelling == '*' and
                        not any(p.kind == CursorKind.DECLARATION for p in node.get_children()))

            # Check for arrow operator
            if node.kind == CursorKind.MEMBER_REF_EXPR:
                tokens = list(node.get_tokens())
                return len(tokens) >= 2 and '->' in [t.spelling for t in tokens]

            return False
        except Exception as e:
            self.debug_print(f"Pointer dereference check error: {str(e)}")
            return False

    def process_node(self, node, source_file: SourceFile):
        try:
            if node.location.file and node.location.file.name == source_file.filepath:
                if self.is_pointer_assignment(node):
                    op = PointerOperation(
                        line=node.location.line,
                        column=node.location.column,
                        name=node.spelling or "anonymous",
                        is_assignment=True,
                        source_file=source_file.filepath
                    )
                    source_file.add_operation(op)
                    self.debug_print(f"Found pointer assignment: {op}")

                elif self.is_pointer_dereference(node):
                    op = PointerOperation(
                        line=node.location.line,
                        column=node.location.column,
                        name=node.spelling or "anonymous",
                        is_assignment=False,
                        source_file=source_file.filepath
                    )
                    source_file.add_operation(op)
                    self.debug_print(f"Found pointer dereference: {op}")

                # Check for includes
                if node.kind == CursorKind.INCLUSION_DIRECTIVE:
                    included_file = node.get_included_file()
                    if included_file:
                        source_file.add_include(included_file.name)
                        self.debug_print(f"Found include: {included_file.name}")

            # Recurse through children
            for child in node.get_children():
                self.process_node(child, source_file)

        except Exception as e:
            self.debug_print(f"Error processing node: {str(e)}")

    def analyze_file(self, filepath: str) -> SourceFile:
        if filepath in self.files:
            return self.files[filepath]

        source_file = SourceFile(filepath)
        self.files[filepath] = source_file

        try:
            translation_unit = self.index.parse(
                filepath,
                args=['-x', 'c'],
                options=(1 << 2)  # DetailedPreprocessingRecord
            )

            if not translation_unit:
                raise RuntimeError(f"Failed to parse {filepath}")

            self.process_node(translation_unit.cursor, source_file)

            # Analyze included files
            for include_path in source_file.includes:
                if os.path.exists(include_path) and include_path not in self.files:
                    self.analyze_file(include_path)

        except Exception as e:
            self.debug_print(f"Error analyzing file {filepath}: {str(e)}")

        return source_file

    def get_statistics(self) -> dict:
        total_assignments = 0
        total_dereferences = 0
        file_stats = {}

        for filepath, source_file in self.files.items():
            assignments = len([op for op in source_file.pointer_ops if op.is_assignment])
            dereferences = len([op for op in source_file.pointer_ops if not op.is_assignment])

            file_stats[filepath] = {
                'assignments': assignments,
                'dereferences': dereferences,
                'total': assignments + dereferences
            }

            total_assignments += assignments
            total_dereferences += dereferences

        return {
            'per_file': file_stats,
            'total_assignments': total_assignments,
            'total_dereferences': total_dereferences,
            'total_operations': total_assignments + total_dereferences
        }


# Example usage:
def analyze_pointers(input_file: str, print_debug: bool = False):
    if not setup_libclang():
        raise RuntimeError("Impossibile inizializzare libclang")

    analyzer = PointerAnalyzer(print_debug=print_debug)
    source_file = analyzer.analyze_file(input_file)
    stats = analyzer.get_statistics()

    if print_debug:
        print("\nAnalysis Results:")
        print(f"Total files analyzed: {len(analyzer.files)}")
        print(f"Total pointer operations: {stats['total_operations']}")
        print(f"- Assignments: {stats['total_assignments']}")
        print(f"- Dereferences: {stats['total_dereferences']}")

    return analyzer

if __name__ == '__main__':
    analyze = "../hello-idf/main/wasm.h"
    if len(sys.argv) > 1:
        analyze = sys.argv[1]

    res = analyze_pointers(analyze, True)
    print(res)
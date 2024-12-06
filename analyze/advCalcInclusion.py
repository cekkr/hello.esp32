import os
from typing import Dict, Set, List, Generator, Tuple
import clang.cindex
from dataclasses import dataclass
from pathlib import Path
import networkx as nx
import platform
import subprocess

from calculateInclusions import *

@dataclass
class TypeInfo:
    name: str
    file_path: str
    line_number: int
    used_in: str
    dependencies: Set[str] = None  # Tipi da cui questo tipo dipende
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = set()

@dataclass
class HeaderContent:
    types: Set[str]
    includes: Set[str]
    forward_declarations: Set[str]
    content: str

def sanitize_filename(name: str) -> str:
    """Converte un nome di tipo in un nome di file sicuro."""
    # Rimuovi i caratteri non sicuri e le parole chiave problematiche
    unsafe_chars = '<>:"/\\|?* '
    name = ''.join(c for c in name if c not in unsafe_chars)
    
    # Gestisci i tipi anonimi
    if 'unnamed' in name.lower():
        # Estrai il percorso del file e la linea se presenti
        parts = name.split('at')
        if len(parts) > 1:
            location = parts[1].strip()
            # Crea un nome basato sulla posizione
            base_name = Path(location).stem
            return f"anonymous_type_{base_name}"
        return "anonymous_type"
    
    # Limita la lunghezza del nome
    if len(name) > 50:
        name = name[:47] + "..."
        
    return name

class EnhancedHeaderDependencyAnalyzer(HeaderDependencyAnalyzer):
    def update_source_files(self) -> List[str]:
        """Aggiorna i file sorgente per utilizzare i nuovi header."""
        modified_files = []
        
        # Crea una directory di backup
        backup_dir = self.project_path / 'source_backups'
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Per ogni file generato, trova le dichiarazioni da rimuovere
        for header_path in self.generated_headers:
            header_content = self._load_header_content(header_path)
            if not header_content:
                continue
                
            # Trova i tipi definiti in questo header
            types_in_header = set()
            for type_name, type_info in self.type_declarations.items():
                if any(self._is_type_in_content(type_name, header_content)):
                    types_in_header.add(type_name)
            
            # Aggiorna i file originali
            for type_name in types_in_header:
                type_info = self.type_declarations[type_name]
                source_file = type_info.file_path
                
                if self._update_source_file(source_file, type_info, Path(header_path)):
                    if source_file not in modified_files:
                        modified_files.append(source_file)
        
        return modified_files

    def _load_header_content(self, header_path: str) -> str:
        """Carica il contenuto di un header file."""
        try:
            with open(header_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Errore nel caricamento del header {header_path}: {e}")
            return ""

    def _is_type_in_content(self, type_name: str, content: str) -> bool:
        """Verifica se un tipo è definito nel contenuto."""
        patterns = [
            f"struct\\s+{type_name}\\s*{{",
            f"class\\s+{type_name}\\s*{{",
            f"enum\\s+{type_name}\\s*{{",
            f"typedef\\s+.*\\s+{type_name}\\s*;"
        ]
        return any(re.search(pattern, content, re.MULTILINE) for pattern in patterns)

    def _create_backup(self, file_path: str) -> bool:
        """Crea un backup del file prima di modificarlo."""
        try:
            backup_path = self.project_path / 'source_backups' / Path(file_path).name
            import shutil
            shutil.copy2(file_path, backup_path)
            return True
        except Exception as e:
            print(f"Errore nella creazione del backup per {file_path}: {e}")
            return False

    def _update_source_file(self, source_file: str, type_info: TypeInfo, new_header_path: Path) -> bool:
        """Aggiorna un file sorgente sostituendo le dichiarazioni con include."""
        try:
            # Crea backup
            if not self._create_backup(source_file):
                return False

            with open(source_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Trova l'inizio e la fine della dichiarazione
            start_line, end_line = self._find_declaration_bounds(lines, type_info)
            if start_line is None or end_line is None:
                return False

            # Genera il percorso relativo per l'include
            relative_header = self._get_relative_include_path(source_file, new_header_path)
            
            # Prepara le nuove linee
            new_lines = (
                lines[:start_line] +
                [f'#include "{relative_header}"  // Generated header\n'] +
                lines[end_line + 1:]
            )

            # Scrivi il file aggiornato
            with open(source_file, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

            return True

        except Exception as e:
            print(f"Errore nell'aggiornamento del file {source_file}: {e}")
            return False

    def _find_declaration_bounds(self, lines: List[str], type_info: TypeInfo) -> Tuple[int, int]:
        """Trova l'inizio e la fine di una dichiarazione di tipo."""
        start_line = type_info.line_number - 1
        
        # Trova l'inizio effettivo della dichiarazione
        while start_line > 0:
            if any(keyword in lines[start_line].strip() 
                  for keyword in ['struct', 'class', 'typedef', 'enum']):
                break
            start_line -= 1

        # Trova la fine della dichiarazione
        end_line = start_line
        brace_count = 0
        in_declaration = False

        while end_line < len(lines):
            line = lines[end_line]
            
            if '{' in line:
                in_declaration = True
                brace_count += line.count('{')
            if '}' in line:
                brace_count -= line.count('}')
            
            if in_declaration and brace_count == 0 and ';' in line:
                break
                
            end_line += 1

        return start_line, end_line

    def _get_relative_include_path(self, source_file: str, header_file: Path) -> str:
        """Genera un percorso relativo per l'include."""
        source_path = Path(source_file)
        try:
            relative_path = os.path.relpath(header_file, source_path.parent)
            return str(Path(relative_path)).replace('\\', '/')
        except ValueError:
            # Se non è possibile creare un percorso relativo, usa il percorso assoluto
            return str(header_file).replace('\\', '/')

    def run_full_update(self) -> str:
        """Esegue l'analisi completa e aggiorna i file."""
        report = []
        
        # Prima analizza il progetto
        analysis_report = self.analyze_project()
        report.append(analysis_report)
        
        # Poi aggiorna i file sorgente
        modified_files = self.update_source_files()
        
        if modified_files:
            report.append("\nFile sorgente modificati:")
            for file in modified_files:
                report.append(f"- {file}")
            report.append("\nBackup dei file originali salvati in: source_backups/")
        else:
            report.append("\nNessun file sorgente è stato modificato.")
            
        return "\n".join(report)
    
    def __init__(self, project_path: str):
        super().__init__(project_path)
        self.type_dependencies: Dict[str, Set[str]] = {}
        self.generated_headers: Set[str] = set()
        
    def analyze_type_dependencies(self, cursor: clang.cindex.Cursor, current_type: str = None):
        """Analizza le dipendenze tra i tipi definiti."""
        for node in cursor.walk_preorder():
            if node.location.file:
                if node.kind in [
                    clang.cindex.CursorKind.STRUCT_DECL,
                    clang.cindex.CursorKind.CLASS_DECL,
                    clang.cindex.CursorKind.TYPEDEF_DECL,
                    clang.cindex.CursorKind.ENUM_DECL
                ]:
                    if current_type and node.spelling in self.type_declarations:
                        if current_type not in self.type_dependencies:
                            self.type_dependencies[current_type] = set()
                        self.type_dependencies[current_type].add(node.spelling)
                        
                        # Aggiorna anche TypeInfo
                        if current_type in self.type_declarations:
                            self.type_declarations[current_type].dependencies.add(node.spelling)

    def analyze_declarations(self, cursor: clang.cindex.Cursor, file_path: str):
        super().analyze_declarations(cursor, file_path)
        for node in cursor.walk_preorder():
            if node.location.file and str(node.location.file) == file_path:
                if node.kind in [
                    clang.cindex.CursorKind.STRUCT_DECL,
                    clang.cindex.CursorKind.CLASS_DECL
                ]:
                    self.analyze_type_dependencies(node, node.spelling)

    def create_optimized_headers(self) -> Dict[str, HeaderContent]:
        """Crea nuovi file header ottimizzati per risolvere le dipendenze cicliche."""
        cycles = self.detect_circular_dependencies()
        new_headers: Dict[str, HeaderContent] = {}
        
        for cycle in cycles:
            # Trova i tipi coinvolti nel ciclo
            cycle_types = set()
            for file in cycle:
                for type_name, type_info in self.type_declarations.items():
                    if type_info.file_path == file:
                        cycle_types.add(type_name)
            
            if not cycle_types:
                continue
            
            # Genera un nome sicuro per il file header
            safe_types = [sanitize_filename(t) for t in sorted(cycle_types)]
            header_name = f"types_{'_'.join(safe_types[:3])}.h"  # Usa solo i primi 3 tipi nel nome
            
            # Analizza le dipendenze per determinare l'ordine corretto
            ordered_types = self._order_types_by_dependencies(cycle_types)
            
            # Genera il contenuto del nuovo header
            try:
                header_content = self._generate_header_content(ordered_types, cycle)
                new_headers[header_name] = header_content
            except Exception as e:
                print(f"Errore nella generazione del contenuto per {header_name}: {e}")
                continue
                
        return new_headers

    def write_optimized_headers(self, output_dir: str = None) -> List[str]:
        """Scrive i nuovi header file ottimizzati."""
        if output_dir is None:
            output_dir = self.project_path / 'generated_headers'
        
        output_path = Path(output_dir)
        
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Errore nella creazione della directory {output_path}: {e}")
            # Prova a usare una directory alternativa
            output_path = self.project_path / 'include' / 'generated'
            output_path.mkdir(parents=True, exist_ok=True)
        
        written_files = []
        new_headers = self.create_optimized_headers()
        
        for header_name, content in new_headers.items():
            try:
                file_path = output_path / header_name
                print(f"Scrittura del file: {file_path}")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content.content)
                written_files.append(str(file_path))
                self.generated_headers.add(str(file_path))
            except Exception as e:
                print(f"Errore nella scrittura del file {header_name}: {e}")
                continue
            
        return written_files

    def _extract_type_definition(self, type_info: TypeInfo) -> List[str]:
        """Estrae la definizione di un tipo dal file originale con gestione migliorata degli errori."""
        try:
            with open(type_info.file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            # Gestisci i tipi anonimi
            if 'unnamed' in type_info.name.lower():
                # Per i tipi anonimi, estrai il contesto circostante
                start_line = max(0, type_info.line_number - 5)
                end_line = min(len(lines), type_info.line_number + 5)
                return [
                    "// Anonymous type definition",
                    "// Original location: " + type_info.file_path + ":" + str(type_info.line_number),
                    *[line.rstrip() for line in lines[start_line:end_line]]
                ]
            
            # Per i tipi nominati, usa la logica esistente
            start_line = type_info.line_number - 1
            while start_line > 0 and not any(lines[start_line].strip().startswith(keyword) 
                for keyword in ['struct', 'class', 'typedef', 'enum']):
                start_line -= 1
            
            end_line = start_line
            brace_count = 0
            started = False
            
            while end_line < len(lines):
                line = lines[end_line]
                if '{' in line:
                    started = True
                    brace_count += line.count('{')
                if '}' in line:
                    brace_count -= line.count('}')
                if started and brace_count == 0 and ';' in line:
                    end_line += 1
                    break
                end_line += 1
            
            return [line.rstrip() for line in lines[start_line:end_line]]
            
        except Exception as e:
            print(f"Errore nell'estrazione della definizione per {type_info.name}: {e}")
            return [
                f"// Error: Could not extract definition for {type_info.name}",
                f"// From file: {type_info.file_path}",
                f"// At line: {type_info.line_number}"
            ]
        
    def _order_types_by_dependencies(self, types: Set[str]) -> List[str]:
        """Ordina i tipi in base alle loro dipendenze."""
        dep_graph = nx.DiGraph()
        
        for t in types:
            dep_graph.add_node(t)
            if t in self.type_dependencies:
                for dep in self.type_dependencies[t]:
                    if dep in types:  # Solo dipendenze interne al ciclo
                        dep_graph.add_edge(t, dep)
        
        try:
            # Prova a ordinare topologicamente
            return list(nx.topological_sort(dep_graph))
        except nx.NetworkXUnfeasible:
            # Se c'è un ciclo, usa un ordine basato sul nome
            return sorted(types)

    def _generate_header_content(self, ordered_types: List[str], cycle: List[str]) -> HeaderContent:
        """Genera il contenuto del nuovo header file."""
        includes = set()
        forward_declarations = set()
        content_lines = [
            "#pragma once",
            "",
            "// Auto-generated header to resolve circular dependencies",
            ""
        ]
        
        # Raccogli le dipendenze esterne necessarie
        for type_name in ordered_types:
            if type_name in self.type_declarations:
                type_info = self.type_declarations[type_name]
                if type_info.dependencies:
                    for dep in type_info.dependencies:
                        if dep not in ordered_types:
                            dep_info = self.type_declarations.get(dep)
                            if dep_info:
                                includes.add(self._get_relative_include_path(dep_info.file_path))
                            else:
                                forward_declarations.add(f"class {dep};")
        
        # Aggiungi include guards e includes
        for inc in sorted(includes):
            content_lines.append(f"#include {inc}")
        
        if includes:
            content_lines.append("")
        
        # Aggiungi forward declarations
        for decl in sorted(forward_declarations):
            content_lines.append(decl)
        
        if forward_declarations:
            content_lines.append("")
        
        # Aggiungi le definizioni dei tipi
        for type_name in ordered_types:
            if type_name in self.type_declarations:
                type_info = self.type_declarations[type_name]
                content_lines.extend(self._extract_type_definition(type_info))
                content_lines.append("")
        
        return HeaderContent(
            types=set(ordered_types),
            includes=includes,
            forward_declarations=forward_declarations,
            content="\n".join(content_lines)
        )

    def _extract_type_definition(self, type_info: TypeInfo) -> List[str]:
        """Estrae la definizione di un tipo dal file originale."""
        try:
            with open(type_info.file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            # Trova l'inizio della definizione
            start_line = type_info.line_number - 1
            while start_line > 0 and not any(lines[start_line].strip().startswith(keyword) 
                for keyword in ['struct', 'class', 'typedef', 'enum']):
                start_line -= 1
            
            # Trova la fine della definizione
            end_line = start_line
            brace_count = 0
            started = False
            
            while end_line < len(lines):
                line = lines[end_line]
                if '{' in line:
                    started = True
                    brace_count += line.count('{')
                if '}' in line:
                    brace_count -= line.count('}')
                if started and brace_count == 0 and ';' in line:
                    end_line += 1
                    break
                end_line += 1
            
            return [line.rstrip() for line in lines[start_line:end_line]]
        except Exception as e:
            print(f"Errore nell'estrazione della definizione per {type_info.name}: {e}")
            return [f"// Error: Could not extract definition for {type_info.name}"]

    def _get_relative_include_path(self, file_path: str) -> str:
        """Converte un percorso file in un'istruzione #include."""
        try:
            path = Path(file_path)
            rel_path = path.relative_to(self.project_path)
            return f'"{rel_path}"'
        except ValueError:
            return f'<{Path(file_path).name}>'
    
    def analyze_project(self) -> str:
        """Analizza il progetto e genera header ottimizzati."""
        report = super().analyze_project()
        
        try:
            written_files = self.write_optimized_headers()
            
            if written_files:
                report += "\n\nHeader files generati:"
                for file in written_files:
                    report += f"\n- {file}"
                
                report += "\n\nPer utilizzare i nuovi header:"
                report += "\n1. Includi i nuovi header nei file appropriati"
                report += "\n2. Rimuovi le inclusioni cicliche originali"
                report += "\n3. Aggiorna i percorsi di inclusione nel tuo build system"
            else:
                report += "\n\nNessun nuovo header file necessario."
                
        except Exception as e:
            report += f"\n\nErrore nella generazione degli header: {e}"
            
        return report

def main():
    import sys
    if len(sys.argv) != 2:
        print("Uso: python script.py <percorso_progetto>")
        sys.exit(1)
        
    try:
        analyzer = EnhancedHeaderDependencyAnalyzer(sys.argv[1])
        #report = analyzer.analyze_project()
        report = analyzer.run_full_update()
        print("\nRisultati dell'analisi:")
        print(report)
    except Exception as e:
        print(f"Errore durante l'analisi: {e}")
        raise

if __name__ == "__main__":
    main()
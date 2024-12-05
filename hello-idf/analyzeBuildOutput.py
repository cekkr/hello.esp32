import os
import re
from pathlib import Path
from typing import Dict, Set, List, Tuple

class IncludeAnalyzer:
    def __init__(self):
        self.include_tree: Dict[str, Set[str]] = {}
        self.forward_declarations: Dict[str, List[str]] = {}
        self.struct_definitions: Dict[str, List[str]] = {}
        self.errors: List[Tuple[str, str, int]] = []

    def parse_build_output(self, output_text: str):
        """Parse the build output to extract include hierarchy and errors"""
        current_file = None
        for line in output_text.splitlines():
            # Track include hierarchy
            if line.startswith('.'):
                depth = line.count('.')
                filepath = line.strip('. ')
                if depth == 0:
                    current_file = filepath
                if current_file:
                    if current_file not in self.include_tree:
                        self.include_tree[current_file] = set()
                    self.include_tree[current_file].add(filepath)
            
            # Track errors
            if 'error: invalid use of undefined type' in line:
                match = re.search(r'([^:]+):(\d+):\d+: error: invalid use of undefined type.*struct (\w+)', line)
                if match:
                    file, line_num, struct_name = match.groups()
                    self.errors.append((file, struct_name, int(line_num)))

    def analyze_source_file(self, filepath: str):
        """Analyze a source file for includes, forward declarations, and struct definitions"""
        if not os.path.exists(filepath):
            return

        with open(filepath, 'r') as f:
            content = f.read()

        # Find includes
        includes = re.findall(r'#include [<"]([^>"]+)[>"]', content)
        if filepath not in self.include_tree:
            self.include_tree[filepath] = set()
        self.include_tree[filepath].update(includes)

        # Find forward declarations
        forwards = re.findall(r'struct\s+(\w+);', content)
        self.forward_declarations[filepath] = forwards

        # Find struct definitions
        structs = re.findall(r'struct\s+(\w+)\s*{[^}]+}', content)
        self.struct_definitions[filepath] = structs

    def find_cycle(self) -> List[str]:
        """Find a cycle in the include dependencies if one exists"""
        def dfs(node: str, visited: Set[str], path: List[str]) -> List[str]:
            if node in path:
                idx = path.index(node)
                return path[idx:]
            
            path.append(node)
            visited.add(node)
            
            for neighbor in self.include_tree.get(node, set()):
                if neighbor not in visited:
                    cycle = dfs(neighbor, visited, path)
                    if cycle:
                        return cycle
            
            path.pop()
            return []

        visited = set()
        for node in self.include_tree:
            if node not in visited:
                cycle = dfs(node, visited, [])
                if cycle:
                    return cycle
        return []

    def print_analysis(self):
        """Print the analysis results"""
        print("=== Include Hierarchy ===")
        for file, includes in self.include_tree.items():
            print(f"\n{file}:")
            for inc in includes:
                print(f"  includes {inc}")

        print("\n=== Forward Declarations ===")
        for file, declarations in self.forward_declarations.items():
            if declarations:
                print(f"\n{file}:")
                for decl in declarations:
                    print(f"  forward declares struct {decl}")

        print("\n=== Struct Definitions ===")
        for file, definitions in self.struct_definitions.items():
            if definitions:
                print(f"\n{file}:")
                for defn in definitions:
                    print(f"  defines struct {defn}")

        print("\n=== Errors ===")
        for file, struct_name, line in self.errors:
            print(f"Error in {file} line {line}: undefined struct {struct_name}")

        cycle = self.find_cycle()
        if cycle:
            print("\n=== Circular Dependency Detected ===")
            print(" -> ".join(cycle))

def main():
    analyzer = IncludeAnalyzer()
    
    # Parse build output
    with open('build_output.txt', 'r') as f:
        analyzer.parse_build_output(f.read())
    
    # Analyze source files mentioned in the build output
    for filepath in analyzer.include_tree.keys():
        analyzer.analyze_source_file(filepath)
    
    # Print results
    analyzer.print_analysis()

if __name__ == "__main__":
    main()
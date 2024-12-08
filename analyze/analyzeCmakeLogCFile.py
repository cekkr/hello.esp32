import sys
import re
from pathlib import Path

def analyze_includes(cmake_log_path, target_file):
    # Read the CMake log file
    with open(cmake_log_path, 'r') as f:
        log_content = f.read()

    # Pattern to match compiler commands for our target file
    # This handles both gcc and clang style compiler outputs
    target_compile_pattern = rf'[gc]\+\+|\w+cc.*\s{re.escape(target_file)}(?:\s|$)'
    
    # Find all compiler commands for our target file
    compile_commands = []
    for line in log_content.split('\n'):
        if re.search(target_compile_pattern, line, re.IGNORECASE):
            compile_commands.append(line)

    if not compile_commands:
        print(f"No compilation commands found for {target_file}")
        return

    # Pattern to match include paths (-I flags)
    include_pattern = r'-I\s*(\S+)'
    
    # Pattern to match included files
    included_files_pattern = r'(?:\.\.\.)\s*(.*?\.h)'

    print(f"\nAnalysis for {target_file}:")
    print("\nCompiler commands found:")
    for cmd in compile_commands:
        print(f"\nCommand: {cmd[:200]}...")  # Truncate long commands
        
        # Extract include paths
        include_paths = re.findall(include_pattern, cmd)
        print("\nInclude paths (-I):")
        for path in include_paths:
            print(f"  {path}")

    # Find all included files mentioned in the log
    included_files = re.findall(included_files_pattern, log_content)
    
    if included_files:
        print("\nInclude order (from log):")
        seen_files = set()
        for file in included_files:
            if file not in seen_files:
                print(f"  {file}")
                seen_files.add(file)

def main():
    cmake_log_path = "../hello-idf/build_output.txt"
    target_file = "m3_exec.c"

    if len(sys.argv) < 3:
        #print("Usage: python script.py <cmake_log_path> <target_file>")
        #sys.exit(1)
        pass
    else:
        cmake_log_path = sys.argv[1]
        target_file = sys.argv[2]

    if not Path(cmake_log_path).exists():
        print(f"Error: CMake log file '{cmake_log_path}' not found")
        sys.exit(1)

    analyze_includes(cmake_log_path, target_file)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3

import re
import os
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class FunctionParam:
    name: str
    type: str
    is_vararg: bool = False
    is_pointer: bool = False


@dataclass
class WasmFunction:
    name: str
    params: List[FunctionParam]
    return_type: str
    description: str
    has_varargs: bool = False
    is_pointer_return: bool = False


class BindingGenerator:

    wasm_pointer_as = 64 # 32 or 64 (bits)

    TYPE_MAPPINGS = {
        'c': {
            'int': 'int32_t',
            'unsigned int': 'uint32_t',
            'long': 'int64_t',
            'unsigned long': 'uint64_t',
            'short': 'int16_t',
            'unsigned short': 'uint16_t',
            'char': 'int8_t',
            'unsigned char': 'uint8_t',
            'int32_t': 'int32_t',
            'uint32_t': 'uint32_t',
            'int64_t': 'int64_t',
            'uint64_t': 'uint64_t',
            'int16_t': 'int16_t',
            'uint16_t': 'uint16_t',
            'int8_t': 'int8_t',
            'uint8_t': 'uint8_t',
            'float': 'float',
            'double': 'double',
            'bool': 'bool',
            'const char*': 'const char*',
            'char*': 'char*',
            'void': 'void',
            'varargs': '...',
            'size_t': 'uint32_t' if wasm_pointer_as == 32 else 'uint64_t'
        },
        'rust': {
            'int': 'i32',
            'unsigned int': 'u32',
            'long': 'i64',
            'unsigned long': 'u64',
            'short': 'i16',
            'unsigned short': 'u16',
            'char': 'i8',
            'unsigned char': 'u8',
            'int32_t': 'i32',
            'uint32_t': 'u32',
            'int64_t': 'i64',
            'uint64_t': 'u64',
            'int16_t': 'i16',
            'uint16_t': 'u16',
            'int8_t': 'i8',
            'uint8_t': 'u8',
            'float': 'f32',
            'double': 'f64',
            'bool': 'bool',
            'const char*': '*const i8',
            'char*': '*mut i8',
            'void': '()',
            'varargs': '*const i32',
            'size_t': 'i32' if wasm_pointer_as == 32 else 'i64'
        },
        'typescript': {
            'int': 'number',
            'unsigned int': 'number',
            'long': 'number',
            'unsigned long': 'number',
            'short': 'number',
            'unsigned short': 'number',
            'char': 'number',
            'unsigned char': 'number',
            'int32_t': 'number',
            'uint32_t': 'number',
            'int64_t': 'number',
            'uint64_t': 'number',
            'int16_t': 'number',
            'uint16_t': 'number',
            'int8_t': 'number',
            'uint8_t': 'number',
            'float': 'number',
            'double': 'number',
            'bool': 'boolean',
            'const char*': 'number',
            'char*': 'number',
            'void': 'void',
            'varargs': '...number[]',
            'size_t': 'number'
        },
        'wasm3': {
            'int': 'i',
            'unsigned int': 'i',
            'long': 'I',
            'unsigned long': 'I',
            'short': 'i',
            'unsigned short': 'i',
            'char': 'i',
            'unsigned char': 'i',
            'int32_t': 'i',
            'uint32_t': 'i',
            'int64_t': 'I',
            'uint64_t': 'I',
            'int16_t': 'i',
            'uint16_t': 'i',
            'int8_t': 'i',
            'uint8_t': 'i',
            'float': 'f',
            'double': 'F',
            'bool': 'i',
            'const char*': 'i',
            'char*': 'i',
            'void': 'v',
            'varargs': 'i',
            'size_t': 'i' if wasm_pointer_as == 32 else 'I'
        }
    }

    def __init__(self, header_file: str):
        with open(header_file, 'r') as f:
            self.header_content = f.read()
        self.header_content = self._clean_comments(self.header_content)
        self.functions = self._parse_header()

    def _clean_comments(self, content: str) -> str:
        """Clean C-style comments from the content."""
        # First remove multi-line comments
        content = re.sub(r'/\*[\s\S]*?\*/', '', content)

        # Then remove single-line comments, but preserve the newline
        content = re.sub(r'//[^\n]*', '', content)

        # Remove empty lines and normalize whitespace
        lines = [line.strip() for line in content.splitlines()]
        return '\n'.join(line for line in lines if line)

    def _extract_comment(self, lines: List[str], idx: int) -> Tuple[str, int]:
        """Extract comment block before function declaration."""
        comment = []
        while idx >= 0 and (lines[idx].strip().startswith('//') or not lines[idx].strip()):
            if lines[idx].strip().startswith('//'):
                comment.insert(0, lines[idx].strip()[2:].strip())
            idx -= 1
        return '\n'.join(comment), idx

    def _parse_c_function(self, line: str) -> Tuple[str, str, List[Tuple[str, str]], bool]:
        """Parse C function declaration."""

        if line.startswith('typedef'):
            return None, None, None, False

        # Remove extern keyword and attributes if present
        line = re.sub(r'extern|__attribute__\s*\(\([^)]+\)\)', '', line).strip()
        line = re.sub(r'\s+', ' ', line)  # Normalize whitespace

        # Updated pattern to handle pointers in return type and parameters
        pattern = r'^([\w\s*]+?\*?)\s+(\w+)\s*\((.*?)\)\s*;?'

        # Remove extern keyword if present
        line = line.replace('extern', '').strip()

        # Basic pattern to extract the main function declaration before any attributes
        main_pattern = r'(.*?)(?:\s+__attribute__|\s*;)'
        main_match = re.match(main_pattern, line)
        if main_match:
            line = main_match.group(1).strip() + ';'

        # Basic pattern for C function declaration
        match = re.match(pattern, line)

        if not match:
            raise ValueError(f"Invalid C function declaration: {line}")

        return_type = match.group(1).strip()
        func_name = match.group(2).strip()
        params_str = match.group(3).strip()
        is_ptr_ret = '*' in return_type

        # Parse parameters
        params = []
        if params_str and params_str != 'void':
            # Handle varargs
            if params_str.endswith('...'):
                params_str = params_str[:-3].strip()
                if params_str:  # If there are other parameters before varargs
                    params.extend(self._parse_params(params_str))
                params.append(('varargs', 'args'))
            else:
                params.extend(self._parse_params(params_str))

        return return_type, func_name, params, is_ptr_ret

    def _parse_params(self, params_str: str) -> List[Tuple[str, str, bool]]:
        """Parse parameter list string into list of (type, name, is_pointer) tuples."""
        params = []

        # Check for varargs at the end
        has_varargs = params_str.strip().endswith('...')
        if has_varargs:
            params_str = params_str.strip()[:-3].strip().rstrip(',')

        if params_str.strip():
            for p in params_str.split(','):
                p = p.strip()
                if not p:
                    continue

                # Handle pointer types
                is_pointer = '*' in p
                if is_pointer:
                    parts = p.split('*')
                    type_part = ('*'.join(parts[:-1]) + '*').strip()
                    name_part = parts[-1].strip()
                else:
                    parts = p.split()
                    type_part = ' '.join(parts[:-1])
                    name_part = parts[-1]

                params.append((type_part, name_part, is_pointer))

        if has_varargs:
            params.append(('varargs', 'args', False))

        return params

    def _parse_header(self) -> List[WasmFunction]:
        """Parse C header file to extract function definitions."""
        functions = []
        lines = self.header_content.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if not line or line.startswith('#'):
                i += 1
                continue

            if any(key in line for key in ['void', 'int', 'float', 'double', 'bool', 'char']):
                description, _ = self._extract_comment(lines, i - 1)

                try:
                    return_type, name, params, is_pointer_return = self._parse_c_function(line)

                    if(return_type is None):
                        i += 1
                        continue  # Skip non-function declarations

                    func_params = []
                    has_varargs = False
                    for param_info in params:
                        param_type, param_name = param_info[:2]
                        is_pointer = len(param_info) > 2 and param_info[2]
                        is_vararg = param_type == 'varargs'
                        if is_vararg:
                            has_varargs = True
                        func_params.append(FunctionParam(
                            name=param_name,
                            type=param_type,
                            is_vararg=is_vararg,
                            is_pointer=is_pointer
                        ))

                    functions.append(WasmFunction(
                        name=name,
                        params=func_params,
                        return_type=return_type,
                        description=description,
                        has_varargs=has_varargs,
                        is_pointer_return=is_pointer_return
                    ))
                except ValueError as e:
                    print(f"Warning: Skipping line due to parsing error: {e}")
                    raise e

            i += 1

        return functions

    def generate_wasm3_signatures(self) -> Dict[str, str]:
        """Generate WASM3 signatures for each function."""
        signatures = {}
        for func in self.functions:
            params_sig = ''
            for param in func.params:
                if param.is_vararg or param.is_pointer:
                    params_sig += 'i'  # Pointers and varargs are passed as integers
                else:
                    param_type = self.TYPE_MAPPINGS['wasm3'][param.type]
                    params_sig += param_type

            # For pointer returns, use 'i' as the return signature
            return_sig = 'i' if func.is_pointer_return else self.TYPE_MAPPINGS['wasm3'][func.return_type]

            signatures[func.name] = f"{return_sig}({params_sig})"

        return signatures

    def generate_rust_bindings(self) -> str:
        """Generate Rust bindings."""
        output = [
            "// Auto-generated Rust bindings for ESP32 WASM",
            "",
            "#[link(wasm_import_module = \"env\")]",
            "extern \"C\" {"
        ]

        for func in self.functions:
            if func.description:
                output.append(f"    // {func.description}")

            params = []
            for p in func.params:
                if p.is_vararg:
                    params.append(f"{p.name}: {self.TYPE_MAPPINGS['rust']['varargs']}")
                elif p.is_pointer:
                    # Handle pointer types specifically for Rust
                    base_type = p.type.replace('*', '').strip()
                    if 'const' in base_type:
                        params.append(f"{p.name}: *const i8")
                    else:
                        params.append(f"{p.name}: *mut i8")
                else:
                    params.append(f"{p.name}: {self.TYPE_MAPPINGS['rust'][p.type]}")

            params_str = ', '.join(params)
            if func.has_varargs:
                params_str += ", vararg_count: i32"

            # Handle pointer return types
            if func.is_pointer_return:
                return_type = "*mut i8" if "char*" in func.return_type else "*mut i32"
            else:
                return_type = self.TYPE_MAPPINGS['rust'][func.return_type]

            output.append(
                f"    pub fn {func.name}({params_str}) -> {return_type};"
            )
            output.append("")

        output.append("}")
        return '\n'.join(output)

    def generate_typescript_bindings(self) -> str:
        """Generate TypeScript bindings."""
        output = [
            "// Auto-generated TypeScript bindings for ESP32 WASM",
            ""
        ]

        for func in self.functions:
            if func.description:
                output.append(f"// {func.description}")

            params = []
            for p in func.params:
                if p.is_vararg:
                    params.append(f"...{p.name}: {self.TYPE_MAPPINGS['typescript']['varargs']}")
                elif p.is_pointer:
                    params.append(f"{p.name}: number")  # Pointers are numbers in JS
                else:
                    params.append(f"{p.name}: {self.TYPE_MAPPINGS['typescript'][p.type]}")

            params_str = ', '.join(params)
            # In TypeScript, pointer returns are also just numbers
            return_type = 'number' if func.is_pointer_return else self.TYPE_MAPPINGS['typescript'][func.return_type]

            output.append(
                f"declare function {func.name}({params_str}): {return_type};"
            )
            output.append("")

        return '\n'.join(output)


def main():
    import argparse
    
    default_args = {
        "header_file": "bindings/esp_wasm.h",
        "output_dir": "bindings/"
    }

    parser = argparse.ArgumentParser(description='Generate ESP32 WASM bindings from C header')
    parser.add_argument('header_file', nargs='?', default=default_args["header_file"],
                    help='C header file with function declarations')
    parser.add_argument('output_dir', nargs='?', default=default_args["output_dir"],
                    help='Output directory for generated files')

    args = parser.parse_args()

    try:
        generator = BindingGenerator(args.header_file)
        
        # Create output directory if it doesn't exist
        os.makedirs(args.output_dir, exist_ok=True)
        
        # Generate WASM3 signatures
        signatures = generator.generate_wasm3_signatures()
        with open(os.path.join(args.output_dir, 'signatures.txt'), 'w') as f:
            for func_name, signature in signatures.items():
                f.write(f"{func_name}: {signature}\n")
        
        # Generate language bindings
        with open(os.path.join(args.output_dir, 'bindings.rs'), 'w') as f:
            f.write(generator.generate_rust_bindings())
            
        with open(os.path.join(args.output_dir, 'bindings.ts'), 'w') as f:
            f.write(generator.generate_typescript_bindings())
            
        print(f"Generated bindings in {args.output_dir}")
        
    except Exception as e:
        print(f"Error: {e}")
        raise e
        return 1
        
    return 0

if __name__ == "__main__":
    exit(main())

    # python binding_generator.py bindings/esp_wasm.h bindings/
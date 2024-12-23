#!/usr/bin/env python3

import yaml
import os
import argparse
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class FunctionParam:
    name: str
    type: str
    is_vararg: bool = False

@dataclass
class WasmFunction:
    name: str
    params: List[FunctionParam]
    return_type: str
    description: str
    has_varargs: bool = False

class BindingGenerator:
    TYPE_MAPPINGS = {
        'c': {
            'i32': 'int32_t',
            'i64': 'int64_t',
            'f32': 'float',
            'f64': 'double',
            'bool': 'bool',
            'string': 'const char*',
            'void': 'void',
            'varargs': '...'  # New type for variable arguments
        },
        'rust': {
            'i32': 'i32',
            'i64': 'i64',
            'f32': 'f32',
            'f64': 'f64',
            'bool': 'bool',
            'string': '&str',
            'void': '()',
            'varargs': '*const i32'  # Treated as pointer to array in Rust
        },
        'typescript': {
            'i32': 'number',
            'i64': 'number',
            'f32': 'number',
            'f64': 'number',
            'bool': 'boolean',
            'string': 'string',
            'void': 'void',
            'varargs': '...number[]'  # Spread operator in TypeScript
        }
    }

    def __init__(self, config_file: str):
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)
        self.functions = self._parse_functions()

    def _parse_functions(self) -> List[WasmFunction]:
        functions = []
        for func in self.config['functions']:
            params = []
            has_varargs = False
            
            for p in func.get('parameters', []):
                is_vararg = p.get('type') == 'varargs'
                if is_vararg:
                    has_varargs = True
                    # Varargs deve essere l'ultimo parametro
                    if len(params) < len(func.get('parameters', [])) - 1:
                        raise ValueError(f"Varargs must be the last parameter in function {func['name']}")
                
                params.append(FunctionParam(
                    name=p['name'],
                    type=p['type'],
                    is_vararg=is_vararg
                ))
            
            functions.append(WasmFunction(
                name=func['name'],
                params=params,
                return_type=func.get('return_type', 'void'),
                description=func.get('description', ''),
                has_varargs=has_varargs
            ))
        return functions

    def generate_c_header(self) -> str:
        output = [
            "#ifndef ESP32_WASM_BINDINGS_H",
            "#define ESP32_WASM_BINDINGS_H",
            "",
            "#include <stdint.h>",
            "#include <stdbool.h>",
            "#include <stdarg.h>",  # Added for varargs support
            "",
            "// Auto-generated ESP32 WASM bindings",
            ""
        ]

        for func in self.functions:
            if func.description:
                output.append(f"// {func.description}")
            
            params = []
            for p in func.params:
                if p.is_vararg:
                    params.append(self.TYPE_MAPPINGS['c']['varargs'])
                else:
                    params.append(f"{self.TYPE_MAPPINGS['c'][p.type]} {p.name}")
            
            params_str = ', '.join(params)
            output.append(
                f"{self.TYPE_MAPPINGS['c'][func.return_type]} {func.name}({params_str});"
            )
            output.append("")

        output.extend([
            "#endif // ESP32_WASM_BINDINGS_H",
            ""
        ])
        return '\n'.join(output)

    def generate_c_implementation(self) -> str:
        output = [
            "#include \"esp_wasm_bindings.h\"",
            "#include \"wasm3.h\"",
            "#include \"m3_env.h\"",
            "",
            "// Auto-generated WASM binding implementations",
            ""
        ]

        for func in self.functions:
            if func.has_varargs:
                # Per funzioni con varargs, generiamo un wrapper speciale
                output.extend([
                    f"m3ApiRawFunction({func.name}_wasm) {{",
                    "    m3ApiReturnType(" + self.TYPE_MAPPINGS['c'][func.return_type] + ")",
                    "    m3ApiGetArgCount(argCount)",  # Get number of arguments
                    ""
                ])

                # Gestione parametri fissi
                fixed_params = [p for p in func.params if not p.is_vararg]
                for param in fixed_params:
                    output.append(
                        f"    m3ApiGetArg({self.TYPE_MAPPINGS['c'][param.type]}, {param.name})"
                    )

                # Gestione varargs
                output.extend([
                    "    // Handle varargs",
                    "    int vararg_count = argCount - " + str(len(fixed_params)) + ";",
                    "    int32_t* varargs = m3ApiAlloc(vararg_count * sizeof(int32_t));",
                    "    for (int i = 0; i < vararg_count; i++) {",
                    "        m3ApiGetArg(int32_t, varargs[i])",
                    "    }",
                    ""
                ])

                # Chiamata alla funzione reale
                fixed_params_str = ', '.join(p.name for p in fixed_params)
                if fixed_params_str:
                    fixed_params_str += ", "
                
                if func.return_type != 'void':
                    output.append(f"    m3ApiReturn({func.name}_impl({fixed_params_str}varargs, vararg_count));")
                else:
                    output.append(f"    {func.name}_impl({fixed_params_str}varargs, vararg_count);")
                    output.append("    m3ApiSuccess();")

                output.extend([
                    "}",
                    ""
                ])
            else:
                # Implementazione standard per funzioni senza varargs
                output.extend([
                    f"m3ApiRawFunction({func.name}) {{",
                    "    m3ApiReturnType(" + self.TYPE_MAPPINGS['c'][func.return_type] + ")"
                ])

                # Genera il codice per ottenere i parametri
                for param in func.params:
                    output.append(
                        f"    m3ApiGetArg({self.TYPE_MAPPINGS['c'][param.type]}, {param.name})"
                    )

                # Chiamata alla funzione reale
                params_str = ', '.join(p.name for p in func.params)
                if func.return_type != 'void':
                    output.append(f"    m3ApiReturn({func.name}_impl({params_str}));")
                else:
                    output.append(f"    {func.name}_impl({params_str});")
                    output.append("    m3ApiSuccess();")

                output.extend([
                    "}",
                    ""
                ])

        # Genera l'array dei binding
        output.extend([
            "// Array of bindings",
            "WasmBinding esp_bindings[] = {"
        ])

        for func in self.functions:
            # Genera la signature WASM
            params_sig = ''
            for p in func.params:
                if not p.is_vararg:
                    params_sig += 'i'  # Per semplicità, trattiamo tutti i parametri come i32
            return_sig = 'v' if func.return_type == 'void' else 'i'
            signature = f"{return_sig}({params_sig})"
            
            func_name = f"{func.name}_wasm" if func.has_varargs else func.name
            output.append(f'    {{"{func.name}", {func_name}, "{signature}"}},')

        output.extend([
            "};",
            "",
            "size_t esp_bindings_count = sizeof(esp_bindings) / sizeof(WasmBinding);",
            ""
        ])

        return '\n'.join(output)

    def generate_rust_bindings(self) -> str:
        output = [
            "// Auto-generated Rust bindings for ESP32 WASM",
            ""
        ]

        output.append("#[link(wasm_import_module = \"env\")]")
        output.append("extern \"C\" {")
        
        for func in self.functions:
            if func.description:
                output.append(f"    // {func.description}")
            
            params = []
            for p in func.params:
                if p.is_vararg:
                    params.append(f"{p.name}: {self.TYPE_MAPPINGS['rust']['varargs']}")
                else:
                    params.append(f"{p.name}: {self.TYPE_MAPPINGS['rust'][p.type]}")
            
            params_str = ', '.join(params)
            if func.has_varargs:
                params_str += ", vararg_count: i32"
            
            return_type = self.TYPE_MAPPINGS['rust'][func.return_type]
            output.append(
                f"    pub fn {func.name}({params_str}) -> {return_type};"
            )
            output.append("")

        output.append("}")
        return '\n'.join(output)

    def generate_typescript_bindings(self) -> str:
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
                else:
                    params.append(f"{p.name}: {self.TYPE_MAPPINGS['typescript'][p.type]}")
            
            params_str = ', '.join(params)
            return_type = self.TYPE_MAPPINGS['typescript'][func.return_type]
            output.append(
                f"declare function {func.name}({params_str}): {return_type};"
            )
            output.append("")

        return '\n'.join(output)
    

def main():
    parser = argparse.ArgumentParser(description='Generate ESP32 WASM bindings')
    parser.add_argument('config', 
                        nargs='?',
                        default="bindings.yaml", 
                        type=str, 
                        help='YAML config file with function definitions')
    parser.add_argument('output_dir', 
                        nargs='?',
                        default="bindings",
                        type=str, 
                        help='Output directory for generated files')
    args = parser.parse_args()

    try:
        generator = BindingGenerator(args.config)

        # Crea la directory di output se non esiste
        os.makedirs(args.output_dir, exist_ok=True)

        # Genera i file
        with open(os.path.join(args.output_dir, 'esp_wasm_bindings.h'), 'w') as f:
            f.write(generator.generate_c_header())

        with open(os.path.join(args.output_dir, 'esp_wasm_bindings.c'), 'w') as f:
            f.write(generator.generate_c_implementation())

        with open(os.path.join(args.output_dir, 'bindings.rs'), 'w') as f:
            f.write(generator.generate_rust_bindings())

        with open(os.path.join(args.output_dir, 'bindings.ts'), 'w') as f:
            f.write(generator.generate_typescript_bindings())

    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
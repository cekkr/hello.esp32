import re
from typing import Tuple

def parse_c_function(c_function: str) -> Tuple[str, str, list]:
    """
    Parse a C function definition into return type, name, and parameters.
    """
    c_function = ' '.join(c_function.split())
    pattern = r'([\w\s*]+?)\s+(\w+)\s*\((.*?)\)'
    match = re.match(pattern, c_function)
    
    if not match:
        raise ValueError("Invalid C function definition")
        
    return_type = match.group(1).strip()
    func_name = match.group(2).strip()
    params_str = match.group(3).strip()
    
    if params_str == "void" or not params_str:
        params = []
    else:
        params = [p.strip() for p in params_str.split(',')]
        params = [re.match(r'([\w\s*]+)(?:\s+\w+)?', p).group(1).strip() for p in params]
    
    return return_type, func_name, params

def c_type_to_wasm3_type(c_type: str) -> str:
    """
    Convert C type to Wasm3 signature type.
    """
    # Rimuovi const e altri qualificatori
    c_type = c_type.replace('const', '').strip()
    
    # Se è un puntatore, ritorna 'i' indipendentemente dal tipo puntato
    if '*' in c_type:
        return 'i'
        
    # Normalizza il tipo rimuovendo spazi extra
    c_type = ' '.join(c_type.split())
    
    type_map = {
        'void': 'v',
        'int': 'i',
        'int32_t': 'i',
        'uint32_t': 'i',
        'long': 'I',
        'int64_t': 'I',
        'uint64_t': 'I',
        'float': 'f',
        'double': 'F',
        'short': 'i',
        'char': 'i',
        'bool': 'i',
        '_Bool': 'i',
        'unsigned int': 'i',
        'unsigned char': 'i',
        'unsigned short': 'i',
        'unsigned long': 'I',
        'size_t': 'I',
        'void*': 'i',
    }
    
    # Gestisci i tipi composti come "unsigned int"
    for known_type, wasm_type in type_map.items():
        if c_type.startswith(known_type):
            return wasm_type
            
    return type_map.get(c_type, 'i')

def generate_wasm3_signature(c_function: str) -> str:
    """
    Generate Wasm3 signature from C function definition.
    """
    return_type, _, params = parse_c_function(c_function)
    
    wasm_return = c_type_to_wasm3_type(return_type)
    wasm_params = ''.join(c_type_to_wasm3_type(p) for p in params)
    
    return f"{wasm_return}({wasm_params})"

def test_signatures():
    test_cases = [
        ("void print_number(int value)", "v(i)"),
        ("int add(int a, int b)", "i(ii)"),
        ("float calculate_average(int count, float sum)", "f(if)"),
        ("void init(void)", "v()"),
        ("double process_data(int32_t id, float value, double factor)", "F(ifF)"),
        ("int64_t get_timestamp(void)", "I()"),
        ("void write_buffer(const uint32_t* buffer, int size)", "v(ii)"),
        ("float complex_calc(unsigned int count, double value)", "f(iF)"),
        ("void process_chars(const char* str, unsigned char flags)", "v(ii)"),
        ("size_t get_buffer_size(const void* ptr)", "I(i)"),
    ]
    
    for test_input, expected in test_cases:
        result = generate_wasm3_signature(test_input)
        print(f"Input:    {test_input}")
        print(f"Expected: {expected}")
        print(f"Got:      {result}")
        print(f"{'✓' if result == expected else '✗'}\n")

if __name__ == "__main__":
    while True:
        try:
            print("\nEnter C function definition (or 'q' to quit, 't' to run tests):")
            user_input = input().strip()
            
            if user_input.lower() == 'q':
                break
            elif user_input.lower() == 't':
                test_signatures()
                continue
                
            signature = generate_wasm3_signature(user_input)
            print(f"Wasm3 signature: {signature}")
            
        except ValueError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
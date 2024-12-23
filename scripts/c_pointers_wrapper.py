from clang.cindex import Index, CursorKind, TokenKind
import sys

def find_pointer_accesses(node, source, replacements):
    if node.kind == CursorKind.BINARY_OPERATOR:
        tokens = list(node.get_tokens())
        for i, token in enumerate(tokens):
            if token.kind == TokenKind.PUNCTUATION and token.spelling == '*':
                if i + 1 < len(tokens):
                    ptr_name = tokens[i+1].spelling
                    start = token.extent.start.offset
                    end = tokens[i+1].extent.end.offset
                    replacements.append((start, end, f'PTR_ACCESS({ptr_name})'))
    
    for child in node.get_children():
        find_pointer_accesses(child, source, replacements)

def transform_file(filename):
    index = Index.create()
    tu = index.parse(filename)
    
    with open(filename, 'r') as f:
        source = f.read()
    
    replacements = []
    find_pointer_accesses(tu.cursor, source, replacements)
    
    # Applica le sostituzioni dall'ultima alla prima per mantenere gli offset validi
    for start, end, replacement in sorted(replacements, reverse=True):
        source = source[:start] + replacement + source[end:]
    
    print(source)
    return

    output_file = filename + '.transformed'
    with open(output_file, 'w') as f:
        f.write(source)

if __name__ == '__main__':
    analyze = "hello-idf/main/wasm.h"
    if len(sys.argv) > 1:
        analyze = sys.argv[1]

    transform_file(analyze)
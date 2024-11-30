import fs from 'fs';
import path from 'path';

// Definizioni dei tipi per WebAssembly
declare global {
  interface WebAssemblyExports {
    [key: string]: Function;
  }

  interface WebAssemblyImports {
    [key: string]: any;
  }

  interface ModuleImportDescriptor {
    module: string;
    name: string;
    kind: string;
  }

  interface ModuleExportDescriptor {
    name: string;
    kind: string;
  }
}

interface WasmValidationResult {
  isValid: boolean;
  error?: string;
  memorySize?: number;
  exports?: string[];
  imports?: {
    module: string;
    name: string;
    kind: string;
  }[];
}

function formatString(format: string, args: number[]): string {
  let result = '';
  let argIndex = 0;
  let i = 0;
  
  while (i < format.length) {
    if (format[i] === '%') {
      i++;
      let padding = '';
      let precision = '';
      
      // Gestione del padding
      while (format[i] >= '0' && format[i] <= '9') {
        padding += format[i];
        i++;
      }
      
      // Gestione della precisione
      if (format[i] === '.') {
        i++;
        while (format[i] >= '0' && format[i] <= '9') {
          precision += format[i];
          i++;
        }
      }
      
      switch (format[i]) {
        case 'd':
        case 'i':
          result += Math.floor(args[argIndex++]).toString();
          break;
        case 'f':
          const num = args[argIndex++];
          const precisionNum = precision ? parseInt(precision) : 6;
          result += num.toFixed(precisionNum);
          break;
        case 's':
          result += args[argIndex++].toString();
          break;
        case '%':
          result += '%';
          break;
        default:
          result += '%' + format[i];
      }
    } else {
      result += format[i];
    }
    i++;
  }
  
  return result;
}

async function validateAndTestWasm(filePath: string): Promise<WasmValidationResult> {
  try {
    const wasmBuffer = fs.readFileSync(filePath);
    
    if (wasmBuffer.length < 8) {
      return {
        isValid: false,
        error: 'File troppo piccolo per essere un modulo WASM valido'
      };
    }

    const magicNumber = wasmBuffer.slice(0, 4);
    if (magicNumber.toString('hex') !== '0061736d') {
      return {
        isValid: false,
        error: 'Magic number WASM non valido'
      };
    }

    const module = await WebAssembly.compile(wasmBuffer);
    
    const imports = (WebAssembly.Module.imports(module) as ModuleImportDescriptor[]).map(imp => ({
      module: imp.module,
      name: imp.name,
      kind: imp.kind
    }));

    const exports = (WebAssembly.Module.exports(module) as ModuleExportDescriptor[]).map(exp => exp.name);

    const memory = new WebAssembly.Memory({ initial: 1 });

    const defaultImports = {
      env: {
        memory,
        esp_printf: function(fmt: string, ...args: number[]): void {
          console.log(formatString(fmt, args));
        },
        abort: () => console.log('Abort called')
      },
      wasi_snapshot_preview1: {
        proc_exit: (code: number) => console.log(`Exit with code: ${code}`),
        fd_write: () => { return 0; },
        fd_close: () => { return 0; },
        fd_seek: () => { return 0; }
      }
    };

    const instance = await WebAssembly.instantiate(module, defaultImports);

    return {
      isValid: true,
      memorySize: defaultImports.env.memory.buffer.byteLength,
      exports,
      imports
    };

  } catch (error) {
    return {
      isValid: false,
      error: error instanceof Error ? error.message : 'Errore sconosciuto'
    };
  }
}

async function testWasmFunction(
  filePath: string, 
  functionName: string, 
  args: any[] = []
): Promise<any> {
  try {
    const wasmBuffer = fs.readFileSync(filePath);
    const module = await WebAssembly.compile(wasmBuffer);
    const memory = new WebAssembly.Memory({ initial: 1 });
    
    const instance = await WebAssembly.instantiate(module, {
      env: {
        memory,
        esp_printf: function(fmt: string, ...args: number[]): void {
          console.log(formatString(fmt, args));
        },
        abort: () => console.log('Abort called')
      }
    });

    const exports = instance.exports as WebAssemblyExports;
    
    if (typeof exports[functionName] !== 'function') {
      throw new Error(`Funzione '${functionName}' non trovata nelle esportazioni`);
    }

    return exports[functionName](...args);
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Errore sconosciuto';
    throw new Error(`Errore nel test della funzione: ${errorMessage}`);
  }
}

async function main() {
  const wasmPath = process.argv[2];
  if (!wasmPath) {
    console.error('Specificare il percorso del file WASM');
    process.exit(1);
  }

  console.log(`\nValidazione del file WASM: ${wasmPath}\n`);
  
  const result = await validateAndTestWasm(wasmPath);
  
  if (result.isValid) {
    console.log('✅ File WASM valido!');
    console.log(`\nInformazioni:\n`);
    console.log(`Memoria iniziale: ${result.memorySize! / 1024}KB`);
    console.log('\nFunzioni esportate:');
    result.exports?.forEach(exp => console.log(`- ${exp}`));
    console.log('\nImportazioni richieste:');
    result.imports?.forEach(imp => {
      console.log(`- ${imp.module}.${imp.name} (${imp.kind})`);
    });
  } else {
    console.error('❌ File WASM non valido!');
    console.error(`Errore: ${result.error}`);
  }

  if (result.isValid && result.exports && result.exports.length > 0) {
    console.log('\nTest delle funzioni esportate:');
    for (const functionName of result.exports) {
      try {
        const result = await testWasmFunction(wasmPath, functionName);
        console.log(`- ${functionName}: OK (risultato: ${result})`);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Errore sconosciuto';
        console.log(`- ${functionName}: ERRORE (${errorMessage})`);
      }
    }
  }
}

main().catch(console.error);

// ts-node validate.ts ../output/fibonacciPrint.wasm
// Targeted references/decompile around defect-related executable strings.
// @category Mewgenics

import java.util.HashSet;
import java.util.Set;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class GhidraDefectRefs extends GhidraScript {

    private static final long[] TARGETS = new long[] {
        0x140ecc0b0L, // birth_defect
        0x140ecc0c0L, // birth_defects
        0x14110d068L  // blind_spot executable string hit
    };

    private static final long[] RANGES = new long[] {
        0x140ecc060L, 0x140ecc100L,
        0x14110d020L, 0x14110d0a0L
    };

    private static final int DECOMPILE_TIMEOUT = 90;
    private static final int MAX_DECOMPILES = 80;

    private Address addr(long offset) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(offset);
    }

    private String safeName(Function function) {
        if (function == null) {
            return "<no function>";
        }
        return function.getName() + " @ " + function.getEntryPoint();
    }

    private void header(String title) {
        println("");
        println("================================================================================");
        println(title);
        println("================================================================================");
    }

    private DecompInterface openDecompiler() {
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        return decompiler;
    }

    private String decompile(Function function, DecompInterface decompiler) throws Exception {
        DecompileResults results = decompiler.decompileFunction(function, DECOMPILE_TIMEOUT, monitor);
        if (!results.decompileCompleted()) {
            return null;
        }
        return results.getDecompiledFunction().getC();
    }

    private void printRefsTo(Address target, Set<Function> functions) {
        Reference[] references = getReferencesTo(target);
        if (references.length == 0) {
            return;
        }
        println("target " + target + " refs=" + references.length);
        int shown = 0;
        for (Reference reference : references) {
            if (shown >= 40) {
                println("  ...");
                break;
            }
            Function function = getFunctionContaining(reference.getFromAddress());
            println("  from " + reference.getFromAddress() + " in " + safeName(function)
                + " type=" + reference.getReferenceType());
            if (function != null) {
                functions.add(function);
            }
            shown++;
        }
    }

    private void collectTargetRefs(Set<Function> functions) {
        header("DIRECT TARGET REFERENCES");
        for (long target : TARGETS) {
            printRefsTo(addr(target), functions);
        }
    }

    private void collectRangeRefs(Set<Function> functions) {
        header("RANGE REFERENCES");
        for (int rangeIndex = 0; rangeIndex < RANGES.length; rangeIndex += 2) {
            long start = RANGES[rangeIndex];
            long end = RANGES[rangeIndex + 1];
            println("range 0x" + Long.toHexString(start) + "..0x" + Long.toHexString(end));
            for (long current = start; current <= end; current++) {
                printRefsTo(addr(current), functions);
            }
        }
    }

    private void decompileReferencingFunctions(Set<Function> functions) throws Exception {
        header("DECOMPILE REFERENCING FUNCTIONS");
        DecompInterface decompiler = openDecompiler();
        int count = 0;
        for (Function function : functions) {
            if (count >= MAX_DECOMPILES) {
                println("Skipping remaining functions after max " + MAX_DECOMPILES);
                break;
            }
            println("");
            println("----- " + safeName(function) + " -----");
            String text = decompile(function, decompiler);
            if (text == null) {
                println("<decompile failed>");
            } else {
                println(text);
            }
            count++;
        }
    }

    @Override
    public void run() throws Exception {
        Set<Function> functions = new HashSet<Function>();
        collectTargetRefs(functions);
        collectRangeRefs(functions);
        decompileReferencingFunctions(functions);
    }
}

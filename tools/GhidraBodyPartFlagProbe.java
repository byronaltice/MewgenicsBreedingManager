// Probe body-part missing flag serialization/deserialization candidates.
// @category Mewgenics

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class GhidraBodyPartFlagProbe extends GhidraScript {

    private static final long[] FUNCTIONS = new long[] {
        0x14022ce10L, // known body-part serializer
        0x14022d360L, // known cat serializer
        0x1400b5260L, // called at start of CatData::breed
        0x1400a5390L, // uses CatPart+0x18 missing flag and 0xfffffffe lookup
        0x1400a5600L  // paired body-part post-process helper
    };

    private static final String[] PATTERNS = new String[] {
        "0xfffffffe",
        "+ 0x18",
        "+ 0x60",
        "+ 0x8c",
        "+ 0xe0",
        "+ 0x134",
        "+ 0x188",
        "+ 0x1dc",
        "+ 0x230",
        "+ 0x284",
        "+ 0x2d8",
        "+ 0x32c",
        "+ 0x380",
        "+ 0x3d4",
        "+ 0x428",
        "+ 0x47c",
        "+ 0x4d0",
        "FUN_14022ce10",
        "FUN_14022d360",
        "FUN_1400a5390"
    };

    private static final int DECOMPILE_TIMEOUT = 120;
    private static final int CONTEXT_LINES = 12;

    private Address addr(long offset) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(offset);
    }

    private String safeName(Function function) {
        if (function == null) {
            return "<no function>";
        }
        return function.getName() + " @ " + function.getEntryPoint();
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

    private void header(String title) {
        println("");
        println("================================================================================");
        println(title);
        println("================================================================================");
    }

    private void printCallers(Function function) {
        println("CALLERS:");
        if (function == null) {
            return;
        }
        for (Reference reference : getReferencesTo(function.getEntryPoint())) {
            if (!reference.getReferenceType().isCall()) {
                continue;
            }
            Function caller = getFunctionContaining(reference.getFromAddress());
            println("  " + reference.getFromAddress() + " from " + safeName(caller));
        }
    }

    private void printMatchingContexts(String text, String pattern) {
        String[] lines = text.split("\n");
        for (int lineIndex = 0; lineIndex < lines.length; lineIndex++) {
            if (!lines[lineIndex].contains(pattern)) {
                continue;
            }
            int start = Math.max(0, lineIndex - CONTEXT_LINES);
            int end = Math.min(lines.length, lineIndex + CONTEXT_LINES + 1);
            println("");
            println("--- context for pattern: " + pattern + " at line " + (lineIndex + 1) + " ---");
            for (int contextIndex = start; contextIndex < end; contextIndex++) {
                println(String.format("%04d: %s", contextIndex + 1, lines[contextIndex]));
            }
        }
    }

    private void dumpFunction(long offset, DecompInterface decompiler) throws Exception {
        Function function = getFunctionAt(addr(offset));
        header(safeName(function));
        printCallers(function);
        if (function == null) {
            return;
        }
        String text = decompile(function, decompiler);
        if (text == null) {
            println("<decompile failed>");
            return;
        }
        for (String pattern : PATTERNS) {
            if (text.contains(pattern)) {
                printMatchingContexts(text, pattern);
            }
        }
    }

    @Override
    public void run() throws Exception {
        DecompInterface decompiler = openDecompiler();
        for (long offset : FUNCTIONS) {
            dumpFunction(offset, decompiler);
        }
    }
}

// Focused decompile for birth-defect application/display helpers.
// @category Mewgenics

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class GhidraDefectDisplayProbe extends GhidraScript {

    private static final long[] FUNCTIONS = new long[] {
        0x1400caa20L, // called by FUN_1400ca4a0 to test/apply tagged CatPartID
        0x1400ba2e0L, // caller of ca4a0/c17f0 near mutation/passive application
        0x1401e64a0L, // caller of ca4a0
        0x1408c3f70L  // caller of ca4a0/c17f0 and birth_defects string
    };

    private static final long[] TARGET_ADDRESSES = new long[] {
        0x1400caa20L,
        0x1400ca4a0L,
        0x1400c17f0L,
        0x140ece4dcL // nearby string/constant used after BirthDefectTooltip
    };

    private static final int DECOMPILE_TIMEOUT = 120;

    private Address addr(long offset) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(offset);
    }

    private String safeName(Function function) {
        if (function == null) {
            return "<no function>";
        }
        return function.getName() + " @ " + function.getEntryPoint();
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

    private void printRefsToTargets() {
        header("REFERENCES TO TARGET ADDRESSES");
        for (long target : TARGET_ADDRESSES) {
            Address address = addr(target);
            println("target " + address);
            for (Reference reference : getReferencesTo(address)) {
                Function function = getFunctionContaining(reference.getFromAddress());
                println("  " + reference.getFromAddress() + " in " + safeName(function)
                    + " type=" + reference.getReferenceType());
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
        println(text);
    }

    @Override
    public void run() throws Exception {
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        printRefsToTargets();
        for (long offset : FUNCTIONS) {
            dumpFunction(offset, decompiler);
        }
    }
}

// Direction 38: Full decompile dump of FUN_1402345e0.
// Goal: Identify what FUN_1402345e0 serializes from CatData+0x8.
// @category Mewgenics

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

public class GhidraFun1402345e0Dump extends GhidraScript {

    private static final long FUN_TARGET = 0x1402345e0L;
    private static final int DECOMPILE_TIMEOUT = 240;

    private Address addr(long offset) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(offset);
    }

    private void dumpFunction(DecompInterface decompiler, long target) throws Exception {
        Function function = getFunctionAt(addr(target));
        if (function == null) {
            println(String.format("Function @ 0x%x not found", target));
            return;
        }
        println("================================================================================");
        println("FULL DECOMPILE: " + function.getName() + " @ " + function.getEntryPoint());
        println("================================================================================");

        DecompileResults results = decompiler.decompileFunction(function, DECOMPILE_TIMEOUT, monitor);
        if (!results.decompileCompleted()) {
            println("Decompile failed: " + results.getErrorMessage());
            return;
        }
        String text = results.getDecompiledFunction().getC();
        String[] lines = text.split("\n");
        for (int i = 0; i < lines.length; i++) {
            println(String.format("%04d: %s", i + 1, lines[i]));
        }
        println("================================================================================");
        println("END OF DECOMPILE -- total lines: " + lines.length);
        println("================================================================================");
    }

    @Override
    public void run() throws Exception {
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);

        dumpFunction(decompiler, FUN_TARGET);
    }
}

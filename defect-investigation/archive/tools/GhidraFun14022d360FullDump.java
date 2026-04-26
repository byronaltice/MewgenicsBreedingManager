// Direction 37: Full decompile dump of FUN_14022d360 (glaiel::SerializeCatData).
// Goal: map post-equipment writes (lines 0379+ after the 5th FUN_14022b1f0 call).
// @category Mewgenics

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

public class GhidraFun14022d360FullDump extends GhidraScript {

    private static final long FUN_CAT_SERIALIZER = 0x14022d360L;
    private static final int DECOMPILE_TIMEOUT = 240;

    private Address addr(long offset) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(offset);
    }

    @Override
    public void run() throws Exception {
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);

        Function function = getFunctionAt(addr(FUN_CAT_SERIALIZER));
        if (function == null) {
            println("FUN_14022d360 not found");
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
}

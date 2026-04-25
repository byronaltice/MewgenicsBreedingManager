// Direction 43c: Decompile the other callers of FUN_1400ca4a0 to find the real
// load-time birth defect applier (not the GlobalProgressionData one at 1401d3c8b).
// Callers to investigate: FUN_1400ba2e0, FUN_1400701a0, FUN_1401e64a0, FUN_1403cce80
// Also decompile FUN_14022d360 callers that do NOT call ca4a0, to map the real save-load path.
// @category Mewgenics

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class GhidraDirection43cProbe extends GhidraScript {

    // The known callers of FUN_1400ca4a0 (birth_defect applier)
    private static final long FUN_MUTATION_APPLY_HELPER = 0x1400ba2e0L;  // non-breed mutation helper
    private static final long FUN_UNKNOWN_701a0         = 0x1400701a0L;  // unknown
    private static final long FUN_UNKNOWN_1e64a0        = 0x1401e64a0L;  // unknown
    private static final long FUN_MULTI_CALLER_cce80    = 0x1403cce80L;  // 4 callsites

    // FUN_14022d360 callers (cat deserializer)
    private static final long FUN_SINGLE_CAT_LOAD       = 0x14022dfb0L; // single cat load
    private static final long FUN_BATCH_CAT_LOAD        = 0x14022fb40L; // batch cat load
    private static final long FUN_UNKNOWN_D6A70         = 0x1400d6a70L; // unknown context
    private static final long FUN_SAVE_CONTEXT_230750   = 0x140230750L; // save context with s_save_file_cat

    // Target: find who calls FUN_1400ca4a0 in a load-time context
    private static final long FUN_BIRTH_DEFECT_APPLIER  = 0x1400ca4a0L;

    private static final int DECOMPILE_TIMEOUT = 180;

    private Address addr(long offset) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(offset);
    }

    private void header(String title) {
        println("");
        println("================================================================================");
        println(title);
        println("================================================================================");
    }

    private String decompileToString(long offset, DecompInterface decompiler) throws Exception {
        Function function = getFunctionAt(addr(offset));
        if (function == null) {
            println("NOT FOUND @ " + Long.toHexString(offset));
            return null;
        }
        println("Function: " + function.getName() + " @ " + function.getEntryPoint());
        DecompileResults results = decompiler.decompileFunction(function, DECOMPILE_TIMEOUT, monitor);
        if (!results.decompileCompleted()) {
            println("<decompile failed: " + results.getErrorMessage() + ">");
            return null;
        }
        return results.getDecompiledFunction().getC();
    }

    private void dumpContextAroundTarget(String[] lines, long targetOffset, int contextBefore, int contextAfter) {
        String targetHex = Long.toHexString(targetOffset);
        // Try matching by hex address or by extracted function name fragment
        for (int i = 0; i < lines.length; i++) {
            if (lines[i].contains(targetHex) || lines[i].contains("FUN_" + targetHex)) {
                int start = Math.max(0, i - contextBefore);
                int end   = Math.min(lines.length, i + contextAfter);
                println("=== Match at line " + (i+1) + " ===");
                for (int j = start; j < end; j++) {
                    println(String.format("  %04d: %s", j+1, lines[j]));
                }
                println("=== End ===");
            }
        }
    }

    private void analyzeCallerForBirthDefect(long callerOffset, DecompInterface decompiler) throws Exception {
        header("CALLER @ " + Long.toHexString(callerOffset));
        String text = decompileToString(callerOffset, decompiler);
        if (text == null) return;
        String[] lines = text.split("\n");
        println("Total lines: " + lines.length);

        // Dump first 30 lines for signature/structure overview
        println("--- First 30 lines ---");
        int cap = Math.min(30, lines.length);
        for (int i = 0; i < cap; i++) {
            println(String.format("  %04d: %s", i+1, lines[i]));
        }

        // Context around FUN_1400ca4a0 calls
        println("");
        println("--- Context around FUN_1400ca4a0 (birth_defect applier) calls ---");
        dumpContextAroundTarget(lines, FUN_BIRTH_DEFECT_APPLIER, 30, 20);

        // Context around FUN_14022d360 (deserializer) calls
        println("");
        println("--- Context around FUN_14022d360 (deserializer) calls ---");
        dumpContextAroundTarget(lines, 0x14022d360L, 20, 20);

        // Check for save-related strings
        println("");
        println("--- Lines with save/load/cat strings ---");
        for (int i = 0; i < lines.length; i++) {
            String l = lines[i].toLowerCase();
            if (l.contains("save") || l.contains("load") || l.contains("cat") || l.contains("inbred") ||
                l.contains("birth") || l.contains("defect") || l.contains("0x178")) {
                println(String.format("  %04d: %s", i+1, lines[i]));
            }
        }
    }

    @Override
    public void run() throws Exception {
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);

        // Analyze each unknown caller of FUN_1400ca4a0
        analyzeCallerForBirthDefect(FUN_MUTATION_APPLY_HELPER, decompiler);
        analyzeCallerForBirthDefect(FUN_UNKNOWN_701a0, decompiler);
        analyzeCallerForBirthDefect(FUN_UNKNOWN_1e64a0, decompiler);
        analyzeCallerForBirthDefect(FUN_MULTI_CALLER_cce80, decompiler);

        // Also look at the real save-load context: FUN_140230750
        header("SAVE CONTEXT: FUN_140230750 — full context dump");
        String text230750 = decompileToString(FUN_SAVE_CONTEXT_230750, decompiler);
        if (text230750 != null) {
            String[] lines = text230750.split("\n");
            println("Total lines: " + lines.length);
            // First 60 lines for structure
            int cap = Math.min(60, lines.length);
            println("--- First 60 lines ---");
            for (int i = 0; i < cap; i++) {
                println(String.format("  %04d: %s", i+1, lines[i]));
            }
            // Context around FUN_1400ca4a0
            println("--- Context around FUN_1400ca4a0 ---");
            dumpContextAroundTarget(lines, FUN_BIRTH_DEFECT_APPLIER, 30, 20);
            // Context around FUN_14022d360
            println("--- Context around FUN_14022d360 ---");
            dumpContextAroundTarget(lines, 0x14022d360L, 20, 20);
        }

        // Also: FUN_1400d6a70
        header("UNKNOWN DESERIALIZER CONTEXT: FUN_1400d6a70");
        String textD6A70 = decompileToString(FUN_UNKNOWN_D6A70, decompiler);
        if (textD6A70 != null) {
            String[] lines = textD6A70.split("\n");
            println("Total lines: " + lines.length);
            int cap = Math.min(50, lines.length);
            println("--- First 50 lines ---");
            for (int i = 0; i < cap; i++) {
                println(String.format("  %04d: %s", i+1, lines[i]));
            }
            dumpContextAroundTarget(lines, FUN_BIRTH_DEFECT_APPLIER, 20, 15);
            dumpContextAroundTarget(lines, 0x14022d360L, 15, 15);
        }

        // Finally: who calls FUN_14022dfb0 (single-cat load) and FUN_14022fb40 (batch)?
        header("CALLERS of FUN_14022dfb0 (single-cat load wrapper)");
        Function funSingle = getFunctionAt(addr(FUN_SINGLE_CAT_LOAD));
        if (funSingle != null) {
            for (Reference ref : getReferencesTo(funSingle.getEntryPoint())) {
                if (!ref.getReferenceType().isCall()) continue;
                Function caller = getFunctionContaining(ref.getFromAddress());
                String callerName = (caller != null) ? caller.getName() + " @ " + caller.getEntryPoint() : "<unknown>";
                println("  callsite=" + ref.getFromAddress() + "  in  " + callerName);
            }
        } else {
            println("NOT FOUND");
        }

        header("CALLERS of FUN_14022fb40 (batch-cat load wrapper)");
        Function funBatch = getFunctionAt(addr(FUN_BATCH_CAT_LOAD));
        if (funBatch != null) {
            for (Reference ref : getReferencesTo(funBatch.getEntryPoint())) {
                if (!ref.getReferenceType().isCall()) continue;
                Function caller = getFunctionContaining(ref.getFromAddress());
                String callerName = (caller != null) ? caller.getName() + " @ " + caller.getEntryPoint() : "<unknown>";
                println("  callsite=" + ref.getFromAddress() + "  in  " + callerName);
            }
        } else {
            println("NOT FOUND");
        }

        header("DIRECTION 43c PROBE COMPLETE");
    }
}

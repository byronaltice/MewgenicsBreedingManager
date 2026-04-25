// Direction 43: Decompile FUN_1401d2ff0 around callsite 1401d3c8b and full FUN_1400ca4a0.
// Goal: identify what saved signal drives load-time birth-defect application.
// @category Mewgenics

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class GhidraDirection43Probe extends GhidraScript {

    // Save loader — contains callsite 1401d3c8b (FUN_1400ca4a0 call after deserialization)
    private static final long FUN_SAVE_LOADER       = 0x1401d2ff0L;
    // Birth_defect tagged partID applier — called at load-time to set CatPart+0x18
    private static final long FUN_BIRTH_DEFECT_PART = 0x1400ca4a0L;
    // Cat deserializer (for context: called before birth_defect applier)
    private static final long FUN_CAT_DESERIALIZER  = 0x14022d360L;

    // The exact callsite address inside FUN_1401d2ff0 that calls FUN_1400ca4a0
    private static final long CALLSITE_1401d3c8b    = 0x1401d3c8bL;

    private static final int DECOMPILE_TIMEOUT = 180;

    private Address addr(long offset) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(offset);
    }

    private String safeName(Function function) {
        if (function == null) return "<no function>";
        return function.getName() + " @ " + function.getEntryPoint();
    }

    private void header(String title) {
        println("");
        println("================================================================================");
        println(title);
        println("================================================================================");
    }

    private String decompileToString(Function function, DecompInterface decompiler) throws Exception {
        if (function == null) return null;
        DecompileResults results = decompiler.decompileFunction(function, DECOMPILE_TIMEOUT, monitor);
        if (!results.decompileCompleted()) return null;
        return results.getDecompiledFunction().getC();
    }

    @Override
    public void run() throws Exception {
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);

        // ----------------------------------------------------------------
        // TASK 1: FUN_1401d2ff0 — focused window around callsite 1401d3c8b
        // Print all lines around every call to FUN_1400ca4a0 (±40 lines each)
        // Also print all calls to FUN_14022d360 in context (±25 lines each)
        // ----------------------------------------------------------------
        header("TASK1: FUN_1401d2ff0 (save loader) — context around callsite 1401d3c8b");

        Function saveLoader = getFunctionAt(addr(FUN_SAVE_LOADER));
        if (saveLoader == null) {
            println("FUN_1401d2ff0 NOT FOUND");
        } else {
            println("Function: " + safeName(saveLoader));
            String text = decompileToString(saveLoader, decompiler);
            if (text == null) {
                println("<decompile failed>");
            } else {
                String[] lines = text.split("\n");
                println("Total lines in FUN_1401d2ff0: " + lines.length);

                // Pass 1: Print context around every mention of FUN_1400ca4a0
                println("");
                println("--- PASS 1: Lines mentioning FUN_1400ca4a0 (birth_defect applier) ---");
                String targetName = "FUN_1400ca4a0";
                String targetHex  = "1400ca4a0";
                boolean found = false;
                for (int i = 0; i < lines.length; i++) {
                    if (lines[i].contains(targetName) || lines[i].contains(targetHex)) {
                        found = true;
                        int start = Math.max(0, i - 40);
                        int end   = Math.min(lines.length, i + 40);
                        println("=== CONTEXT WINDOW: line " + (i+1) + " mentions FUN_1400ca4a0 ===");
                        for (int j = start; j < end; j++) {
                            println(String.format("  %04d: %s", j+1, lines[j]));
                        }
                        println("=== END WINDOW ===");
                    }
                }
                if (!found) {
                    println("(no direct mention by name; trying hex address 0x1400ca4a0)");
                }

                // Pass 2: Print context around every mention of FUN_14022d360 (deserializer)
                println("");
                println("--- PASS 2: Lines mentioning FUN_14022d360 (cat deserializer) ---");
                String deserName = "FUN_14022d360";
                String deserHex  = "14022d360";
                found = false;
                for (int i = 0; i < lines.length; i++) {
                    if (lines[i].contains(deserName) || lines[i].contains(deserHex)) {
                        found = true;
                        int start = Math.max(0, i - 20);
                        int end   = Math.min(lines.length, i + 30);
                        println("=== CONTEXT WINDOW: line " + (i+1) + " mentions FUN_14022d360 ===");
                        for (int j = start; j < end; j++) {
                            println(String.format("  %04d: %s", j+1, lines[j]));
                        }
                        println("=== END WINDOW ===");
                    }
                }
                if (!found) {
                    println("(no direct mention of deserializer by name)");
                }

                // Pass 3: Print a broad function signature + first 80 lines to show overall shape
                println("");
                println("--- PASS 3: First 80 lines of FUN_1401d2ff0 (shape/param overview) ---");
                int cap = Math.min(80, lines.length);
                for (int i = 0; i < cap; i++) {
                    println(String.format("  %04d: %s", i+1, lines[i]));
                }
            }
        }

        // ----------------------------------------------------------------
        // TASK 2: FUN_1400ca4a0 — full decompile
        // ----------------------------------------------------------------
        header("TASK2: FUN_1400ca4a0 (birth_defect partID applier) — FULL DECOMPILE");

        Function birthDefectFun = getFunctionAt(addr(FUN_BIRTH_DEFECT_PART));
        if (birthDefectFun == null) {
            println("FUN_1400ca4a0 NOT FOUND");
        } else {
            println("Function: " + safeName(birthDefectFun));
            String text = decompileToString(birthDefectFun, decompiler);
            if (text == null) {
                println("<decompile failed>");
            } else {
                String[] lines = text.split("\n");
                println("Total lines: " + lines.length);
                for (int i = 0; i < lines.length; i++) {
                    println(String.format("  %04d: %s", i+1, lines[i]));
                }
            }
        }

        // ----------------------------------------------------------------
        // TASK 3: List all callers of FUN_1400ca4a0 with addresses
        //         (to confirm which callsites are in FUN_1401d2ff0)
        // ----------------------------------------------------------------
        header("TASK3: All callers of FUN_1400ca4a0 with callsite addresses");

        if (birthDefectFun != null) {
            for (Reference ref : getReferencesTo(birthDefectFun.getEntryPoint())) {
                if (!ref.getReferenceType().isCall()) continue;
                Function caller = getFunctionContaining(ref.getFromAddress());
                String callerName = (caller != null) ? safeName(caller) : "<unknown>";
                println("  callsite=" + ref.getFromAddress() + "  in  " + callerName);
            }
        }

        // ----------------------------------------------------------------
        // TASK 4: Decompile any immediate helper called by FUN_1400ca4a0
        //         that looks like it reads a saved offset (CatData+0xXXX)
        //         We'll find these from the full decompile text above.
        //         Also decompile FUN_1400ca4a0's direct parent in context
        //         (FUN_1400caa20 from Direction 34, which calls it in breed path).
        // ----------------------------------------------------------------
        header("TASK4: Callers of FUN_1401d2ff0 (save loader) with counts");

        if (saveLoader != null) {
            int count = 0;
            for (Reference ref : getReferencesTo(saveLoader.getEntryPoint())) {
                if (!ref.getReferenceType().isCall()) continue;
                Function caller = getFunctionContaining(ref.getFromAddress());
                String callerName = (caller != null) ? safeName(caller) : "<unknown>";
                println("  callsite=" + ref.getFromAddress() + "  in  " + callerName);
                count++;
            }
            println("Total callers: " + count);
        }

        header("DIRECTION 43 PROBE COMPLETE");
    }
}

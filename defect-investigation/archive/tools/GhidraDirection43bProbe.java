// Direction 43b: Dump FUN_1401d2ff0 lines 80-540 (to find iVar4/iVar5 assignment and loop context)
// Also decompile FUN_1400d2450 (the RNG/random function called from FUN_1400ca4a0)
// Also decompile FUN_1400caa20 (the mutation applier called inside the loop in FUN_1400ca4a0)
// @category Mewgenics

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

public class GhidraDirection43bProbe extends GhidraScript {

    private static final long FUN_SAVE_LOADER       = 0x1401d2ff0L;
    private static final long FUN_RNG_PICK          = 0x1400d2450L;  // called with TLS+0x178 (RNG state?)
    private static final long FUN_MUTATE_APPLY      = 0x1400caa20L;  // applies the mutation to cat

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
        // TASK 1: FUN_1401d2ff0 lines 80-540 -- searching for iVar4/iVar5
        // Also search for any RNG-seed-like reads
        // ----------------------------------------------------------------
        header("TASK1: FUN_1401d2ff0 lines 80-540 — iVar4/iVar5 assignment hunt");

        Function saveLoader = getFunctionAt(addr(FUN_SAVE_LOADER));
        if (saveLoader == null) {
            println("FUN_1401d2ff0 NOT FOUND");
        } else {
            String text = decompileToString(saveLoader, decompiler);
            if (text == null) {
                println("<decompile failed>");
            } else {
                String[] lines = text.split("\n");
                println("Total lines: " + lines.length);

                // Lines 81-540 (0-indexed: 80 to 539)
                println("--- Lines 81-540 ---");
                int startLine = 80;
                int endLine = Math.min(540, lines.length);
                for (int i = startLine; i < endLine; i++) {
                    println(String.format("%04d: %s", i+1, lines[i]));
                }

                // Also: search for any line containing "iVar4" or "iVar5" (assignment)
                println("");
                println("--- ALL lines mentioning iVar4 = or iVar5 = (assignments) ---");
                for (int i = 0; i < lines.length; i++) {
                    String l = lines[i];
                    // show assignments (lines with = and iVar4/iVar5 on left side)
                    if ((l.contains("iVar4") || l.contains("iVar5")) && l.contains("=")) {
                        println(String.format("  %04d: %s", i+1, l));
                    }
                }

                // Also: search for "ThreadLocalStorage" or "0x178" — RNG seed reads
                println("");
                println("--- Lines mentioning ThreadLocalStorage or 0x178 ---");
                for (int i = 0; i < lines.length; i++) {
                    String l = lines[i];
                    if (l.contains("ThreadLocal") || l.contains("0x178")) {
                        int start = Math.max(0, i - 3);
                        int end   = Math.min(lines.length, i + 5);
                        println("  ==> Line " + (i+1) + ":");
                        for (int j = start; j < end; j++) {
                            println(String.format("    %04d: %s", j+1, lines[j]));
                        }
                    }
                }

                // Also: lines mentioning "inbred" or "inbredness" or "breed_chance" or "chance"
                println("");
                println("--- Lines mentioning inbred/chance/seed ---");
                for (int i = 0; i < lines.length; i++) {
                    String l = lines[i].toLowerCase();
                    if (l.contains("inbred") || l.contains("chance") || l.contains("seed")) {
                        println(String.format("  %04d: %s", i+1, lines[i]));
                    }
                }
            }
        }

        // ----------------------------------------------------------------
        // TASK 2: FUN_1400d2450 — full decompile (the RNG helper)
        // ----------------------------------------------------------------
        header("TASK2: FUN_1400d2450 (RNG helper called in FUN_1400ca4a0) — FULL DECOMPILE");

        Function rngFun = getFunctionAt(addr(FUN_RNG_PICK));
        if (rngFun == null) {
            println("FUN_1400d2450 NOT FOUND");
        } else {
            println("Function: " + rngFun.getName() + " @ " + rngFun.getEntryPoint());
            String text = decompileToString(rngFun, decompiler);
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
        // TASK 3: FUN_1400caa20 — full decompile (the mutation applier)
        // ----------------------------------------------------------------
        header("TASK3: FUN_1400caa20 (mutation applier called in FUN_1400ca4a0) — FULL DECOMPILE");

        Function mutApply = getFunctionAt(addr(FUN_MUTATE_APPLY));
        if (mutApply == null) {
            println("FUN_1400caa20 NOT FOUND");
        } else {
            println("Function: " + mutApply.getName() + " @ " + mutApply.getEntryPoint());
            String text = decompileToString(mutApply, decompiler);
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

        header("DIRECTION 43b PROBE COMPLETE");
    }
}

// Direction 42: Runtime/display code path investigation for birth defects with no GON entry.
// Goals:
//   1. Understand FUN_1400e38c0 "no GON entry" branch (what happens when FUN_1407b1190 returns null/empty)
//   2. List all callers of FUN_1400a5390 (body-part inheritance helper)
//   3. List all callers of FUN_1400ca4a0 (birth_defect tagged partID helper)
//   4. List all callers of FUN_1400c17f0 (birth_defects list helper)
//   5. List all callers of FUN_14022d360 (cat deserializer) and decompile their post-deserialize code
//   6. Decompile FUN_14073ab50 (called right after CatData+0x8a8 is set)
//   7. Decompile FUN_1400d1470 (builds something from mutation list; result stored at CatData+0x78)
//   8. Decompile FUN_1400c9810 (iterates the mutation container at CatData+0x8a8)
//   9. Decompile FUN_1407b1190 (GON entry lookup - find null/empty handling)
//  10. Search for display strings: "BirthDefect", "Birth Defect", "Blind", "BIRTH_DEFECT"
// @category Mewgenics

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.mem.MemoryAccessException;

public class GhidraDirection42Probe extends GhidraScript {

    private static final long FUN_DISPLAY_MUTATION     = 0x1400e38c0L; // mutation tooltip builder
    private static final long FUN_BODY_PART_INHERIT    = 0x1400a5390L; // uses CatPart+0x18 / 0xFFFFFFFE
    private static final long FUN_BIRTH_DEFECT_PART    = 0x1400ca4a0L; // called with "birth_defect"
    private static final long FUN_BIRTH_DEFECTS_LIST   = 0x1400c17f0L; // called with "birth_defects"
    private static final long FUN_CAT_DESERIALIZER     = 0x14022d360L; // save deserializer
    private static final long FUN_POST_ASSIGN_0x8a8    = 0x140073ab50L; // called after CatData+0x8a8 set
    private static final long FUN_MUTATION_LIST_BUILD  = 0x1400d1470L;  // builds something from mut list
    private static final long FUN_MUTATION_ITER        = 0x1400c9810L;  // iterates CatData+0x8a8 container
    private static final long FUN_GON_LOOKUP           = 0x1407b1190L;  // GON entry lookup by partID

    private static final int DECOMPILE_TIMEOUT = 120;

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

    private String decompile(Function function, DecompInterface decompiler) throws Exception {
        if (function == null) return null;
        DecompileResults results = decompiler.decompileFunction(function, DECOMPILE_TIMEOUT, monitor);
        if (!results.decompileCompleted()) return null;
        return results.getDecompiledFunction().getC();
    }

    private void printCallers(Function function) {
        if (function == null) {
            println("CALLERS: <function not found>");
            return;
        }
        println("CALLERS of " + safeName(function) + ":");
        for (Reference ref : getReferencesTo(function.getEntryPoint())) {
            if (!ref.getReferenceType().isCall()) continue;
            Function caller = getFunctionContaining(ref.getFromAddress());
            println("  " + ref.getFromAddress() + " from " + safeName(caller));
        }
    }

    private void dumpFunction(long offset, String label, DecompInterface decompiler) throws Exception {
        Function function = getFunctionAt(addr(offset));
        header(label + ": " + safeName(function));
        printCallers(function);
        if (function == null) {
            println("<function not found at " + Long.toHexString(offset) + ">");
            return;
        }
        String text = decompile(function, decompiler);
        if (text == null) {
            println("<decompile failed>");
            return;
        }
        println("DECOMPILE:");
        println(text);
    }

    private void dumpCallersWithContext(long offset, String label, DecompInterface decompiler) throws Exception {
        Function function = getFunctionAt(addr(offset));
        header("CALLERS+CONTEXT: " + label + " = " + safeName(function));
        if (function == null) {
            println("<function not found>");
            return;
        }
        for (Reference ref : getReferencesTo(function.getEntryPoint())) {
            if (!ref.getReferenceType().isCall()) continue;
            Function caller = getFunctionContaining(ref.getFromAddress());
            println("CALLER: " + safeName(caller) + " at callsite " + ref.getFromAddress());
            if (caller == null) continue;
            String text = decompile(caller, decompiler);
            if (text == null) {
                println("  <decompile failed for caller>");
                continue;
            }
            // Print lines around each callsite to the target function
            String[] lines = text.split("\n");
            String callerName = function.getName();
            String callerAddr = Long.toHexString(offset);
            for (int i = 0; i < lines.length; i++) {
                if (lines[i].contains(callerName) || lines[i].contains(callerAddr)) {
                    int start = Math.max(0, i - 8);
                    int end = Math.min(lines.length, i + 12);
                    println("  --- context around call at line " + (i + 1) + " ---");
                    for (int j = start; j < end; j++) {
                        println(String.format("  %04d: %s", j + 1, lines[j]));
                    }
                    println("  ---");
                }
            }
        }
    }

    @Override
    public void run() throws Exception {
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);

        // Task 1: FUN_1400e38c0 - full decompile already done; focus on null GON entry path
        // But we re-dump it here to capture the FUN_1407b1190 null path explicitly
        dumpFunction(FUN_DISPLAY_MUTATION, "TASK1 FUN_1400e38c0 (mutation tooltip builder)", decompiler);

        // Task 2: Callers of FUN_1400a5390 (body-part inheritance helper)
        header("TASK2: Callers of FUN_1400a5390 (body-part inheritance helper)");
        Function funInherit = getFunctionAt(addr(FUN_BODY_PART_INHERIT));
        printCallers(funInherit);

        // Task 3: Callers of FUN_1400ca4a0 (birth_defect tagged partID)
        header("TASK3: Callers of FUN_1400ca4a0 (birth_defect tagged partID helper)");
        Function funBirthDefectPart = getFunctionAt(addr(FUN_BIRTH_DEFECT_PART));
        printCallers(funBirthDefectPart);

        // Task 4: Callers of FUN_1400c17f0 (birth_defects list)
        header("TASK4: Callers of FUN_1400c17f0 (birth_defects list helper)");
        Function funBirthDefectsList = getFunctionAt(addr(FUN_BIRTH_DEFECTS_LIST));
        printCallers(funBirthDefectsList);

        // Task 5: Callers of FUN_14022d360 + context
        dumpCallersWithContext(FUN_CAT_DESERIALIZER, "FUN_14022d360 (cat deserializer)", decompiler);

        // Task 6: FUN_14073ab50 - called right after CatData+0x8a8 is set
        dumpFunction(FUN_POST_ASSIGN_0x8a8, "TASK6 FUN_14073ab50 (post-0x8a8 assignment)", decompiler);

        // Task 7: FUN_1400d1470 - builds from mutation list
        dumpFunction(FUN_MUTATION_LIST_BUILD, "TASK7 FUN_1400d1470 (mutation list build helper)", decompiler);

        // Task 8: FUN_1400c9810 - iterates the mutation container
        dumpFunction(FUN_MUTATION_ITER, "TASK8 FUN_1400c9810 (mutation container iterator)", decompiler);

        // Task 9: FUN_1407b1190 - GON entry lookup (what happens on null/no GON entry)
        dumpFunction(FUN_GON_LOOKUP, "TASK9 FUN_1407b1190 (GON entry lookup by partID)", decompiler);

        header("DIRECTION 42 PROBE COMPLETE");
    }
}

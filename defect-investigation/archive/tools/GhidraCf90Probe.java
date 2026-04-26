// Focused probe for FUN_14022cf90 call sites in CatData serialization.
// @category Mewgenics

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.CodeUnit;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;

public class GhidraCf90Probe extends GhidraScript {

    private static final long FUN_CAT_SERIALIZER = 0x14022d360L;
    private static final long FUN_CF90 = 0x14022cf90L;
    private static final long FUN_D100 = 0x14022d100L;
    private static final long FUN_EQUIPMENT = 0x14022b1f0L;
    private static final long FUN_BODY_PARTS = 0x14022ce10L;

    private static final int DECOMPILE_TIMEOUT = 120;
    private static final int CONTEXT_LINES = 12;
    private static final int DISASM_CONTEXT = 8;

    private Address addr(long offset) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(offset);
    }

    private String safeName(Function function) {
        return function == null ? "<null>" : function.getName() + " @ " + function.getEntryPoint();
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

    private void printMatchingContext(String text, String pattern) {
        String[] lines = text.split("\n");
        for (int i = 0; i < lines.length; i++) {
            if (!lines[i].contains(pattern)) {
                continue;
            }
            int start = Math.max(0, i - CONTEXT_LINES);
            int end = Math.min(lines.length, i + CONTEXT_LINES + 1);
            println("");
            println("--- context for pattern: " + pattern + " at decompile line " + (i + 1) + " ---");
            for (int j = start; j < end; j++) {
                println(String.format("%04d: %s", j + 1, lines[j]));
            }
        }
    }

    private void dumpFunctionContexts(long functionOffset, String[] patterns, DecompInterface decompiler)
            throws Exception {
        Function function = getFunctionAt(addr(functionOffset));
        header("DECOMPILE CONTEXTS: " + safeName(function));
        if (function == null) {
            println("Function not found");
            return;
        }
        String text = decompile(function, decompiler);
        if (text == null) {
            println("Decompile failed");
            return;
        }
        for (String pattern : patterns) {
            if (!text.contains(pattern)) {
                println("No decompile match for pattern: " + pattern);
                continue;
            }
            printMatchingContext(text, pattern);
        }
    }

    private void listCallers(long targetOffset, DecompInterface decompiler) throws Exception {
        Function target = getFunctionAt(addr(targetOffset));
        header("CALLERS OF: " + safeName(target));
        if (target == null) {
            println("Target not found");
            return;
        }
        for (Reference reference : getReferencesTo(target.getEntryPoint())) {
            if (!reference.getReferenceType().isCall()) {
                continue;
            }
            Function caller = getFunctionContaining(reference.getFromAddress());
            println(safeName(caller) + " from " + reference.getFromAddress());
            if (caller == null) {
                continue;
            }
            String text = decompile(caller, decompiler);
            if (text != null) {
                printMatchingContext(text, target.getName());
            }
        }
    }

    private void dumpDisassemblyAroundCalls(long targetOffset) {
        Function target = getFunctionAt(addr(targetOffset));
        header("DISASSEMBLY CALL CONTEXTS FOR: " + safeName(target));
        if (target == null) {
            println("Target not found");
            return;
        }
        for (Reference reference : getReferencesTo(target.getEntryPoint())) {
            if (!reference.getReferenceType().isCall()) {
                continue;
            }
            Address callAddress = reference.getFromAddress();
            println("");
            println("--- call at " + callAddress + " ---");
            Instruction instruction = getInstructionAt(callAddress);
            for (int i = 0; i < DISASM_CONTEXT && instruction != null; i++) {
                instruction = instruction.getPrevious();
            }
            for (int i = 0; i < DISASM_CONTEXT * 2 + 1 && instruction != null; i++) {
                String marker = instruction.getAddress().equals(callAddress) ? " >>> " : "     ";
                CodeUnit codeUnit = instruction;
                println(marker + codeUnit.getAddress() + "  " + codeUnit);
                instruction = instruction.getNext();
            }
        }
    }

    @Override
    public void run() throws Exception {
        DecompInterface decompiler = openDecompiler();
        header("KNOWN FUNCTIONS");
        println(safeName(getFunctionAt(addr(FUN_CAT_SERIALIZER))));
        println(safeName(getFunctionAt(addr(FUN_CF90))));
        println(safeName(getFunctionAt(addr(FUN_D100))));
        println(safeName(getFunctionAt(addr(FUN_EQUIPMENT))));
        println(safeName(getFunctionAt(addr(FUN_BODY_PARTS))));

        listCallers(FUN_CF90, decompiler);
        listCallers(FUN_D100, decompiler);
        listCallers(FUN_EQUIPMENT, decompiler);

        dumpDisassemblyAroundCalls(FUN_CF90);

        dumpFunctionContexts(
            FUN_CAT_SERIALIZER,
            new String[] {
                "FUN_14022ce10",
                "FUN_14022cf90",
                "FUN_14022d100",
                "FUN_14022b1f0",
                "+ 0x6f0",
                "+ 0x70c",
                "+ 0x728",
                "+ 0x7a8",
                "+ 0x910",
                "+ 0x9b0",
                "*param_2 == 0",
                "*param_2 - 1U < 2",
            },
            decompiler
        );
    }
}

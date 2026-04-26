// Search the analyzed Mewgenics binary for the specific cat-face runtime paths.
// @category Mewgenics

import java.util.ArrayList;
import java.util.List;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.symbol.Reference;

public class GhidraHeadlessProbe extends GhidraScript {

    private static final long TARGET_RANGE_START = 0x140730000L;
    private static final long TARGET_RANGE_END = 0x140740000L;
    private static final long[] KNOWN_FUNCTIONS = new long[] {
        0x140737FF0L,
        0x140737360L,
        0x140734760L,
        0x140739740L,
        0x14073AB50L,
        0x14073BD80L,
        0x14073F220L,
        0x1407395C0L,
        0x14073FC10L,
        0x1401F6B40L,
        0x1400BC240L,
    };
    private static final String[] SEARCH_PATTERNS = new String[] {
        "+ 0x8a8",
        "+ 0x910",
        "+ 0x938",
        "+ 0x960",
        "+ 0x988",
        "+ 0x9b0",
        "+ 0xa10",
        "+ 0xa70",
        "+ 0xad0",
        "+ 0xb30",
        "+ 0xc10",
        "param_1[0x115]",
        "SetDefaultFacePassive",
        "default_face",
        "FUN_1400bc240",
        "FUN_14073fc10",
        "FUN_140737360",
        "FUN_14073bd80",
    };
    private static final int MAX_RESULTS_PER_PATTERN = 20;

    private Address toAddress(long offset) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(offset);
    }

    private String safeName(Function function) {
        if (function == null) {
            return "None";
        }
        return function.getName() + " @ " + function.getEntryPoint();
    }

    private void printHeader(String title) {
        println("");
        println("==============================================================================");
        println(title);
        println("==============================================================================");
    }

    private DecompInterface openDecompiler() {
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        return decompiler;
    }

    private String decompile(Function function, DecompInterface decompiler) throws Exception {
        DecompileResults result = decompiler.decompileFunction(function, 60, monitor);
        if (!result.decompileCompleted()) {
            return null;
        }
        return result.getDecompiledFunction().getC();
    }

    private void dumpFunction(long offset, DecompInterface decompiler) throws Exception {
        Function function = getFunctionAt(toAddress(offset));
        printHeader("Function " + safeName(function));
        if (function == null) {
            println("missing function");
            return;
        }
        String text = decompile(function, decompiler);
        if (text == null) {
            println("decompile failed");
            return;
        }
        println(text);
    }

    private void listCallers(long offset) {
        Function function = getFunctionAt(toAddress(offset));
        printHeader("Callers of " + safeName(function));
        if (function == null) {
            println("missing function");
            return;
        }
        Reference[] references = getReferencesTo(function.getEntryPoint());
        for (Reference reference : references) {
            if (!reference.getReferenceType().isCall()) {
                continue;
            }
            Function caller = getFunctionContaining(reference.getFromAddress());
            println(safeName(caller) + " from " + reference.getFromAddress());
        }
    }

    private void searchPatterns(DecompInterface decompiler) throws Exception {
        printHeader("Pattern Search In Decompiled Functions");
        FunctionIterator functions = currentProgram.getFunctionManager().getFunctions(true);
        List<String>[] found = new ArrayList[SEARCH_PATTERNS.length];
        for (int i = 0; i < SEARCH_PATTERNS.length; i++) {
            found[i] = new ArrayList<String>();
        }

        while (functions.hasNext() && !monitor.isCancelled()) {
            Function function = functions.next();
            long entry = function.getEntryPoint().getOffset();
            if (entry < TARGET_RANGE_START || entry >= TARGET_RANGE_END) {
                continue;
            }
            String text = decompile(function, decompiler);
            if (text == null) {
                continue;
            }
            String[] lines = text.split("\n");
            for (int patternIndex = 0; patternIndex < SEARCH_PATTERNS.length; patternIndex++) {
                String pattern = SEARCH_PATTERNS[patternIndex];
                if (!text.contains(pattern) || found[patternIndex].size() >= MAX_RESULTS_PER_PATTERN) {
                    continue;
                }
                StringBuilder builder = new StringBuilder();
                builder.append("match in ").append(safeName(function)).append("\n");
                for (int lineIndex = 0; lineIndex < lines.length; lineIndex++) {
                    if (!lines[lineIndex].contains(pattern)) {
                        continue;
                    }
                    int start = Math.max(0, lineIndex - 4);
                    int end = Math.min(lines.length, lineIndex + 5);
                    for (int snippetIndex = start; snippetIndex < end; snippetIndex++) {
                        builder.append(String.format("%04d: %s%n", snippetIndex + 1, lines[snippetIndex]));
                    }
                    builder.append("---\n");
                }
                found[patternIndex].add(builder.toString());
            }
        }

        for (int patternIndex = 0; patternIndex < SEARCH_PATTERNS.length; patternIndex++) {
            println("");
            println("--- pattern: " + SEARCH_PATTERNS[patternIndex] + " ---");
            if (found[patternIndex].isEmpty()) {
                println("no matches");
                continue;
            }
            for (String block : found[patternIndex]) {
                println(block);
            }
        }
    }

    @Override
    public void run() throws Exception {
        DecompInterface decompiler = openDecompiler();
        printHeader("Known Functions");
        for (long offset : KNOWN_FUNCTIONS) {
            println(safeName(getFunctionAt(toAddress(offset))));
        }
        for (long offset : KNOWN_FUNCTIONS) {
            dumpFunction(offset, decompiler);
        }
        listCallers(0x140739740L);
        listCallers(0x140737360L);
        listCallers(0x14073BD80L);
        listCallers(0x14073FC10L);
        listCallers(0x1400BC240L);
        searchPatterns(decompiler);
    }
}

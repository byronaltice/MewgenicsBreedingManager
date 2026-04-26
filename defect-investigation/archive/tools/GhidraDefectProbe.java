// Focused whole-program decompiler search for birth-defect runtime logic.
// @category Mewgenics

import java.util.ArrayList;
import java.util.List;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;

public class GhidraDefectProbe extends GhidraScript {

    private static final String[] SEARCH_PATTERNS = new String[] {
        "birth_defect",
        "MUTATION_EYES_M2_DESC",
        "MUTATION_EYEBROWS_M2_DESC",
        "MUTATION_EARS_M2_DESC",
        "blind",
        "no eyes",
        "no eyebrows",
        "no ears",
        "0xfffffffe",
        "0xFFFFFFFE",
        "4294967294",
        "-2",
        "FUN_14022ce10",
        "FUN_140734760"
    };

    private static final int MAX_MATCHES_PER_PATTERN = 40;
    private static final int DECOMPILE_TIMEOUT = 45;
    private static final int CONTEXT_LINES = 5;

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
        DecompileResults result = decompiler.decompileFunction(function, DECOMPILE_TIMEOUT, monitor);
        if (!result.decompileCompleted()) {
            return null;
        }
        return result.getDecompiledFunction().getC();
    }

    @Override
    public void run() throws Exception {
        DecompInterface decompiler = openDecompiler();
        List<String>[] found = new ArrayList[SEARCH_PATTERNS.length];
        for (int patternIndex = 0; patternIndex < SEARCH_PATTERNS.length; patternIndex++) {
            found[patternIndex] = new ArrayList<String>();
        }

        printHeader("Whole-program defect/runtime pattern search");
        FunctionIterator functions = currentProgram.getFunctionManager().getFunctions(true);
        while (functions.hasNext() && !monitor.isCancelled()) {
            Function function = functions.next();
            String text = decompile(function, decompiler);
            if (text == null) {
                continue;
            }
            String[] lines = text.split("\n");
            for (int patternIndex = 0; patternIndex < SEARCH_PATTERNS.length; patternIndex++) {
                String pattern = SEARCH_PATTERNS[patternIndex];
                if (!text.contains(pattern) || found[patternIndex].size() >= MAX_MATCHES_PER_PATTERN) {
                    continue;
                }
                StringBuilder builder = new StringBuilder();
                builder.append("match in ").append(safeName(function)).append("\n");
                for (int lineIndex = 0; lineIndex < lines.length; lineIndex++) {
                    if (!lines[lineIndex].contains(pattern)) {
                        continue;
                    }
                    int start = Math.max(0, lineIndex - CONTEXT_LINES);
                    int end = Math.min(lines.length, lineIndex + CONTEXT_LINES + 1);
                    for (int snippetIndex = start; snippetIndex < end; snippetIndex++) {
                        builder.append(String.format("%04d: %s%n", snippetIndex + 1, lines[snippetIndex]));
                    }
                    builder.append("---\n");
                }
                found[patternIndex].add(builder.toString());
            }
        }

        for (int patternIndex = 0; patternIndex < SEARCH_PATTERNS.length; patternIndex++) {
            printHeader("pattern: " + SEARCH_PATTERNS[patternIndex]);
            if (found[patternIndex].isEmpty()) {
                println("no matches");
                continue;
            }
            for (String block : found[patternIndex]) {
                println(block);
            }
        }
    }
}

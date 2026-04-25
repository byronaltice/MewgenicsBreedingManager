// Probe the MewSaveFile::Load / cat-blob decoder functions.
// @category Mewgenics

import java.util.ArrayList;
import java.util.List;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class GhidraDecoderProbe extends GhidraScript {

    // MewSaveFile::Load (has "could not load cat from save file" assertion)
    private static final long FUN_SAVEFILE_LOAD     = 0x14022dfb0L;
    // Actual cat-blob decoder (called from Load)
    private static final long FUN_CAT_DECODER       = 0x14022d360L;
    // Serializes CatData+0x60 (body-part container — 3 u32s + 14 calls to FUN_14022cd00)
    private static final long FUN_BODYPART_SER      = 0x14022ce10L;
    // THE KEY: per-body-part-slot serializer (skips slot[+0]!)
    private static final long FUN_SLOT_SERIALIZER   = 0x14022cd00L;
    // POST-LOAD processing on CatData+0x60 (called right after SerializeCatData)
    // Likely computes the slot[+0] "No Part" defect flag from loaded T data
    private static final long FUN_POST_LOAD         = 0x140734760L;
    // Called 3x at CatData+0x6f0/0x70c/0x728 — possible per-slot variant/defect serializer
    private static final long FUN_SLOT_VARIANT      = 0x14022cf90L;
    // Also called after body-part container — unclear purpose
    private static final long FUN_14022D100         = 0x14022d100L;

    private static final long[] DUMP_FUNCTIONS = new long[] {
        FUN_SLOT_VARIANT,
        FUN_14022D100,
    };

    // Patterns that would reveal how per-slot records are serialized
    private static final String[] SEARCH_PATTERNS = new String[] {
        "0x14022d",   // calls into the decoder cluster
        "0x14022b",
        "birth_defect",
        "no_part",
        "NoPart",
        "variant",
        "presence",
        "\"cat\"",
        "innate",
        "slot",
        "+ 0x8a8",
        "+ 0x910",
        "+ 0x9b0",
    };

    private static final long SEARCH_RANGE_START = 0x14022a000L;
    private static final long SEARCH_RANGE_END   = 0x14023a000L;
    private static final int  MAX_MATCHES        = 10;
    private static final int  DECOMPILE_TIMEOUT  = 90;

    // -------------------------------------------------------------------------

    private ghidra.program.model.address.Address addr(long offset) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(offset);
    }

    private String safeName(Function f) {
        return f == null ? "<null>" : f.getName() + " @ " + f.getEntryPoint();
    }

    private void header(String title) {
        println("");
        println("================================================================================");
        println(title);
        println("================================================================================");
    }

    private DecompInterface openDecompiler() {
        DecompInterface dc = new DecompInterface();
        dc.openProgram(currentProgram);
        return dc;
    }

    private String decompile(Function f, DecompInterface dc) throws Exception {
        DecompileResults r = dc.decompileFunction(f, DECOMPILE_TIMEOUT, monitor);
        return r.decompileCompleted() ? r.getDecompiledFunction().getC() : null;
    }

    private void dumpFunction(long offset, DecompInterface dc) throws Exception {
        Function f = getFunctionAt(addr(offset));
        header("DECOMPILE: " + safeName(f));
        if (f == null) { println("NOT FOUND"); return; }
        String text = decompile(f, dc);
        if (text == null) { println("DECOMPILE FAILED"); return; }
        String[] lines = text.split("\n");
        for (int i = 0; i < lines.length; i++) {
            println(String.format("%04d: %s", i + 1, lines[i]));
        }
    }

    private void listCallers(long offset) {
        Function f = getFunctionAt(addr(offset));
        header("CALLERS OF: " + safeName(f));
        if (f == null) { println("NOT FOUND"); return; }
        for (Reference ref : getReferencesTo(f.getEntryPoint())) {
            if (!ref.getReferenceType().isCall()) continue;
            Function caller = getFunctionContaining(ref.getFromAddress());
            println(safeName(caller) + "  from " + ref.getFromAddress());
        }
    }

    private void searchPatterns(DecompInterface dc) throws Exception {
        header("PATTERN SEARCH in range [" +
               Long.toHexString(SEARCH_RANGE_START) + ", " +
               Long.toHexString(SEARCH_RANGE_END) + ")");

        ghidra.program.model.listing.FunctionIterator it =
            currentProgram.getFunctionManager().getFunctions(true);

        java.util.Map<String, List<String>> found = new java.util.LinkedHashMap<>();
        for (String p : SEARCH_PATTERNS) found.put(p, new ArrayList<>());

        while (it.hasNext() && !monitor.isCancelled()) {
            Function fn = it.next();
            long entry = fn.getEntryPoint().getOffset();
            if (entry < SEARCH_RANGE_START || entry >= SEARCH_RANGE_END) continue;
            String text = decompile(fn, dc);
            if (text == null) continue;
            String[] lines = text.split("\n");
            for (String pattern : SEARCH_PATTERNS) {
                List<String> list = found.get(pattern);
                if (list.size() >= MAX_MATCHES || !text.contains(pattern)) continue;
                StringBuilder sb = new StringBuilder();
                sb.append("  match in ").append(safeName(fn)).append("\n");
                for (int i = 0; i < lines.length; i++) {
                    if (!lines[i].contains(pattern)) continue;
                    int lo = Math.max(0, i - 3), hi = Math.min(lines.length, i + 4);
                    for (int j = lo; j < hi; j++)
                        sb.append(String.format("    %04d: %s\n", j + 1, lines[j]));
                    sb.append("    ---\n");
                }
                list.add(sb.toString());
            }
        }

        for (String pattern : SEARCH_PATTERNS) {
            println("");
            println("--- pattern: " + pattern + " ---");
            List<String> matches = found.get(pattern);
            if (matches.isEmpty()) { println("  no matches"); continue; }
            for (String block : matches) println(block);
        }
    }

    @Override
    public void run() throws Exception {
        DecompInterface dc = openDecompiler();

        header("KNOWN FUNCTIONS");
        for (long offset : DUMP_FUNCTIONS)
            println(safeName(getFunctionAt(addr(offset))));

        for (long offset : DUMP_FUNCTIONS)
            dumpFunction(offset, dc);

        listCallers(FUN_CAT_DECODER);
        listCallers(FUN_BODYPART_SER);
        listCallers(FUN_SLOT_SERIALIZER);

        searchPatterns(dc);
    }
}

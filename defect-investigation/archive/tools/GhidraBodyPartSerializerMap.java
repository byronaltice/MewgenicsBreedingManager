// Dump and summarize the body-part serializer offsets.
// @category Mewgenics

import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.TreeSet;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

public class GhidraBodyPartSerializerMap extends GhidraScript {

    private static final long[] FUNCTION_OFFSETS = new long[] {
        0x14022ce10L,
        0x14022cd00L
    };
    private static final int DECOMPILE_TIMEOUT = 120;

    private Address addr(long offset) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(offset);
    }

    private String decompile(Function function, DecompInterface decompiler) throws Exception {
        DecompileResults results = decompiler.decompileFunction(function, DECOMPILE_TIMEOUT, monitor);
        if (!results.decompileCompleted()) {
            return null;
        }
        return results.getDecompiledFunction().getC();
    }

    private void printOffsetSummary(String text) {
        Pattern pattern = Pattern.compile("param_1 \\+ 0x([0-9a-fA-F]+)");
        Matcher matcher = pattern.matcher(text);
        TreeSet<Integer> offsets = new TreeSet<Integer>();
        while (matcher.find()) {
            offsets.add(Integer.parseInt(matcher.group(1), 16));
        }
        println("PARAM_1 OFFSETS:");
        int index = 0;
        for (Integer offset : offsets) {
            println(String.format("  serialized_index_candidate=%02d  param_1+0x%03x", index, offset));
            index++;
        }
    }

    @Override
    public void run() throws Exception {
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        for (long functionOffset : FUNCTION_OFFSETS) {
            Function function = getFunctionAt(addr(functionOffset));
            println("");
            println("FUNCTION: " + function.getName() + " @ " + function.getEntryPoint());
            String text = decompile(function, decompiler);
            if (text == null) {
                println("<decompile failed>");
                continue;
            }
            printOffsetSummary(text);
            println("");
            println("FULL DECOMPILE:");
            println(text);
        }
    }
}

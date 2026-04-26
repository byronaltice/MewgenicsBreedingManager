from ghidra.app.decompiler import DecompInterface
from ghidra.program.model.address import Address
from ghidra.util.task import ConsoleTaskMonitor


TARGET_RANGE_START = 0x140730000
TARGET_RANGE_END = 0x140740000
KNOWN_FUNCTIONS = [
    0x140737FF0,
    0x140739740,
    0x14073FC10,
    0x1400BC240,
]
SEARCH_PATTERNS = [
    "+ 0x910",
    "+ 0x938",
    "+ 0x960",
    "+ 0x988",
    "+ 0x9b0",
    "+ 0xc10",
    "SetDefaultFacePassive",
    "default_face",
    "FUN_1400bc240",
    "FUN_14073fc10",
]
MAX_RESULTS_PER_PATTERN = 20
DECOMPILE_TIMEOUT = 60


def to_addr(value):
    return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(value)


def get_decompiler():
    interface = DecompInterface()
    interface.openProgram(currentProgram)
    return interface


def safe_name(function):
    if function is None:
        return "None"
    return "%s @ %s" % (function.getName(), function.getEntryPoint())


def print_header(title):
    print("")
    print("=" * 78)
    print(title)
    print("=" * 78)


def dump_function(function, interface):
    print_header("Function %s" % safe_name(function))
    result = interface.decompileFunction(function, DECOMPILE_TIMEOUT, ConsoleTaskMonitor())
    if not result.decompileCompleted():
        print("Decompile failed")
        return ""
    text = result.getDecompiledFunction().getC()
    print(text)
    return text


def search_patterns(interface):
    print_header("Pattern Search In Decompiled Functions")
    found_by_pattern = {}
    listing = currentProgram.getFunctionManager().getFunctions(True)
    while listing.hasNext():
        function = listing.next()
        entry = function.getEntryPoint().getOffset()
        if entry < TARGET_RANGE_START or entry >= TARGET_RANGE_END:
            continue
        result = interface.decompileFunction(function, DECOMPILE_TIMEOUT, ConsoleTaskMonitor())
        if not result.decompileCompleted():
            continue
        text = result.getDecompiledFunction().getC()
        for pattern in SEARCH_PATTERNS:
            if pattern in text:
                found_by_pattern.setdefault(pattern, [])
                if len(found_by_pattern[pattern]) < MAX_RESULTS_PER_PATTERN:
                    found_by_pattern[pattern].append((function, text))
    for pattern in SEARCH_PATTERNS:
        print("")
        print("--- pattern: %s ---" % pattern)
        matches = found_by_pattern.get(pattern, [])
        if not matches:
            print("no matches")
            continue
        for function, text in matches:
            print("")
            print("match in %s" % safe_name(function))
            lines = text.splitlines()
            for index, line in enumerate(lines):
                if pattern in line:
                    start = max(0, index - 4)
                    end = min(len(lines), index + 5)
                    for line_index in range(start, end):
                        print("%04d: %s" % (line_index + 1, lines[line_index]))
                    print("---")


def list_callers(target_addr):
    function = getFunctionAt(to_addr(target_addr))
    print_header("Callers of %s" % safe_name(function))
    if function is None:
        print("missing function")
        return
    refs = getReferencesTo(function.getEntryPoint())
    for ref in refs:
        if not ref.getReferenceType().isCall():
            continue
        caller = getFunctionContaining(ref.getFromAddress())
        print("%s from %s" % (safe_name(caller), ref.getFromAddress()))


def run():
    interface = get_decompiler()
    print_header("Known Functions")
    for value in KNOWN_FUNCTIONS:
        function = getFunctionAt(to_addr(value))
        print(safe_name(function))
    for value in KNOWN_FUNCTIONS:
        function = getFunctionAt(to_addr(value))
        if function is not None:
            dump_function(function, interface)
    list_callers(0x140739740)
    list_callers(0x14073FC10)
    list_callers(0x1400BC240)
    search_patterns(interface)


run()

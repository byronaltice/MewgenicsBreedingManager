import std.io;
import std.mem;

enum CompactRecordCType : u8 {
    FullRecord = 0,
    NA = 1,
    Int64 = 2,
    Double = 3,
    SetTimestamp = 253,
    SelectVsid = 254,
    Reset = 255,
};

enum FullRecordSType : u8 {
    Blob = 0,
    // 1-255 decode to a CompactRecordType
    StringUtf8 = 256,
};

bitfield RecordType {
    ctype : 8;
    stype : 24;
};

struct Record {
    RecordType type;

    if(type.ctype == 0) {
        // full record
        u32 user;
        u64 length;
        match(u64(type.stype))  {
            (FullRecordSType::Blob): u8 data[length];
            (CompactRecordCType::NA): char nothing[0];
            (CompactRecordCType::Int64): u64 val;
            (CompactRecordCType::Double): double val;
            (CompactRecordCType::SetTimestamp): u64 timestamp_us;
            (CompactRecordCType::SelectVsid): u32 vsid;
            (CompactRecordCType::Reset): char nothing[0];
            (FullRecordSType::StringUtf8): char string[length];
            (_): std::error("unexpected full");
        }
    } else {
        // compact record
        $ -= 3;
        match(u8(type.ctype)) {
            (CompactRecordCType::FullRecord): std::error("tautologically impossible");
            (CompactRecordCType::NA): char nothing[0];
            (CompactRecordCType::Int64): u64 val;
            (CompactRecordCType::Double): double val;
            (CompactRecordCType::SetTimestamp): u64 timestamp_us;
            (CompactRecordCType::SelectVsid): u32 vsid;
            (CompactRecordCType::Reset): char nothing[0];
            (_): std::error("unexpected compact");
        }
    }
};

char magic[6] @ 0x00;
char version @ $;
char format @ $;

Record records[while($ < std::mem::size())] @ $;
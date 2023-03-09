import sys
import logging
from binascii import hexlify
from struct import unpack
from util import FileSignatureError
from base import XamarinBase
from xalz import XamarinCompressedAssembly

#https://github.com/xamarin/xamarin-android/blob/d0701eb75e096f53e3c070fc6cdbad6d7477afba/src/monodroid/jni/xamarin-app.hh
#https://github.com/xamarin/xamarin-android/blob/c92702619f5fabcff0ed88e09160baf9edd70f41/Documentation/project-docs/AssemblyStores.md
#https://github.com/xamarin/xamarin-android/blob/c03c953a71e140d8903ec82675178a51da538846/tools/assembly-store-reader/AssemblyStoreReader.cs

ASSEMBLY_STORE_MAGIC    = b"XABA"
HEADER_SIZE             = 0x14 # bytes
TABLE_ENTRY_SIZE        = 0x18 # bytes
HASH_ENTRY_SIZE         = 0x14 # bytes
DATA_SUFFIX             = ".so"
DEBUG_SUFFIX            = ".dbg"
CONFIG_SUFFIX           = ".xml"
CATCHALL_SUFFIX         = ".bin"

class XamarinAssemblyStoreTableEntry:
    """
    struct AssemblyStoreAssemblyDescriptor
    {
        uint32_t data_offset;
        uint32_t data_size;
        uint32_t debug_data_offset;
        uint32_t debug_data_size;
        uint32_t config_data_offset;
        uint32_t config_data_size;
    };
    """
    def from_bytes(self, data:bytes):
        "Unpack and populate from <data>, checking file signature"
        (
            self.data_offset,
            self.data_size,
            self.debug_data_offset,
            self.debug_data_size,
            self.config_data_offset,
            self.config_data_size
        ) = unpack("<IIIIII",data[:TABLE_ENTRY_SIZE])

        logging.debug(
            "Parsed table entry: data_offset=%d, data_size=%d," + \
            " debug_data_offset=%d, debug_data_size=%d," + \
            " config_data_offset=%d, config_data_size=%d",
            self.data_offset,
            self.data_size,
            self.debug_data_offset,
            self.debug_data_size,
            self.config_data_offset,
            self.config_data_size
        )
        return self

class XamarinAssemblyStoreHashTableEntry:
    """
    struct AssemblyStoreHashEntry
    {
        union {
            uint64_t hash64;
            uint32_t hash32;
        };
        uint32_t mapping_index;
        uint32_t local_store_index;
        uint32_t store_id;
    };
    """
    def from_bytes(self, data:bytes):
        "Unpack and populate from <data>, checking file signature"
        (
            self.hash,
            self.mapping_index,
            self.local_store_index,
            self.store_id
        ) = unpack("<QIII",data[:HASH_ENTRY_SIZE])

        logging.debug(
            "Parsed hash table entry: hash=%016x," + \
            " mapping_index=%d, local_store_index=%d," + \
            " store_id=%d",
            self.hash,
            self.mapping_index,
            self.local_store_index,
            self.store_id
        )
        return self

class XamarinBundledAssembly(XamarinBase):
    """
    struct AssemblyStoreHeader
    {
        uint32_t magic;
        uint32_t version;
        uint32_t local_entry_count;
        uint32_t global_entry_count;
        uint32_t store_id;
    ;
    AssemblyStoreHeader header;
    AssemblyStoreAssemblyDescriptor assemblies[header.local_entry_count];
    AssemblyStoreHashEntry hashes32[header.global_entry_count]; // only in assembly store with ID 0
    AssemblyStoreHashEntry hashes64[header.global_entry_count]; // only in assembly store with ID 0
    [DATA]
    """
    def from_bytes(self, data:bytes):
        "Unpack and populate from <data>, checking file signature"
        (
            self.magic,
            self.version,
            self.entry_count,
            self.global_entry_count,
            self.store_id
        ) = unpack("<4sIIII",data[:HEADER_SIZE])

        logging.debug(
            "Parsed header for %s: magic=%s, version=%d," + \
            " entry_count=%d, global_entry_count=%d," + \
            " store_id=%x",
            self.filepath,
            self.magic.decode('utf-8'),
            self.version,
            self.entry_count,
            self.global_entry_count,
            self.store_id
        )

        if self.magic != ASSEMBLY_STORE_MAGIC:
            raise FileSignatureError

        desc_tbl_start = HEADER_SIZE
        hash32_tbl_start = desc_tbl_start + (self.entry_count * TABLE_ENTRY_SIZE)
        hash64_tbl_start = hash32_tbl_start + (self.entry_count * HASH_ENTRY_SIZE)
        self.data_start = hash64_tbl_start + (self.entry_count * HASH_ENTRY_SIZE)

        logging.debug(
            "descriptor_table_offset=%d, hash32_table_offset=%d, hash64_table_offset=%d, data_start=%d",
            desc_tbl_start,
            hash32_tbl_start,
            hash64_tbl_start,
            self.data_start
        )

        # parse the descriptor table
        self.descriptor_table = []
        table_size = self.entry_count * TABLE_ENTRY_SIZE
        
        for i in range(desc_tbl_start, desc_tbl_start + table_size, TABLE_ENTRY_SIZE):
            logging.debug("Parsing table entry %d", (i/TABLE_ENTRY_SIZE))
            self.descriptor_table.append(
                XamarinAssemblyStoreTableEntry().from_bytes(
                    data[i:i+TABLE_ENTRY_SIZE]
                )
            )


        # parse the hash tables
        self.hash32_table = []
        self.hash64_table = []
        hash_table_size = self.entry_count * HASH_ENTRY_SIZE

        if self.store_id == 0:
            for i in range(hash32_tbl_start, hash32_tbl_start + hash_table_size, HASH_ENTRY_SIZE):
                self.hash32_table.append(
                    XamarinAssemblyStoreHashTableEntry().from_bytes(
                        data[i:i+HASH_ENTRY_SIZE]
                    )
                )

            for i in range(hash64_tbl_start, hash64_tbl_start + hash_table_size, HASH_ENTRY_SIZE):
                self.hash64_table.append(
                    XamarinAssemblyStoreHashTableEntry().from_bytes(
                        data[i:i+HASH_ENTRY_SIZE]
                    )
                )

        # gather the stores
        self.data = data[self.data_start:]

        return self

    def write(self, dirpath:str) -> None:
        "Write uncompressed data to <dirpath>"
        #TODO: PosixPath
        stores = []

        # build the hash->descriptor map
        for i in range(self.entry_count):
            #TODO: don't ignore hash32
            hash64 = self.hash64_table[i]
            # the store_index is indexed off of 1, not 0
            descriptor = self.descriptor_table[hash64.local_store_index]
            store = {
                'descriptor':descriptor,
                'hash64':hash64,
            }
            logging.debug(
                "Assigned %016x to descriptor[%d] at offset %d",
                hash64.hash,
                hash64.local_store_index,
                descriptor.data_offset
            )
            stores.append(store)
        
        files = []
        for store in stores:
            f = {}
            f['data_name'] = None
            f['debug_name'] = None
            f['config_name'] = None

            basename = hexlify(store['hash64'].hash.to_bytes(byteorder='big',length=8)).decode('utf-8')

            if store['descriptor'].data_size != 0:
                f['data_name'] = basename + DATA_SUFFIX
                offset = store['descriptor'].data_offset - self.data_start
                size = store['descriptor'].data_size
                data_lz4 = self.data[offset:offset+size]
                logging.debug("Extracted %s: start=%d, end=%d", f['data_name'], offset, offset+size)
                try:
                    f['asm'] = XamarinCompressedAssembly().from_bytes(data_lz4)
                except FileSignatureError:
                    f['asm'] = data_lz4
                    f['data_name'] = basename + CATCHALL_SUFFIX

            if store['descriptor'].debug_data_size != 0:
                f['debug_name'] = basename + DEBUG_SUFFIX
                offset = store['descriptor'].debug_data_offset - self.data_start
                size = store['descriptor'].debug_data_size
                f['debug_data'] = self.data[offset:offset+size]
                logging.debug("Extracted %s: start=%d, end=%d", f['debug_name'], offset, offset+size)

            if store['descriptor'].config_data_size != 0:
                f['config_name'] = basename + CONFIG_SUFFIX
                offset = store['descriptor'].config_data_offset - self.data_start
                size = store['descriptor'].config_data_size
                f['config_data'] = self.data[offset:offset+size]
                logging.debug("Extracted %s: start=%d, end=%d", f['config_name'], offset, offset+size)

            files.append(f)

        for f in files:
            if f['data_name'] is not None:
                if type(f['asm']) is XamarinCompressedAssembly:
                    f['asm'].write(dirpath+"/"+f['data_name'])
                else:
                    with open(dirpath+"/"+f['data_name'], "wb") as io:
                        io.write(f['asm'])
            if f['debug_name'] is not None:
                with open(dirpath+"/"+f['debug_name'], "wb") as io:
                    io.write(f['debug_data'])
            if f['config_name'] is not None:
                with open(dirpath+"/"+f['config_name'], "wb") as io:
                    io.write(f['config_data'])
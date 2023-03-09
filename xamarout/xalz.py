import sys
import logging
from struct import unpack
import lz4.block
from util import FileSignatureError
from base import XamarinBase

#https://github.com/xamarin/xamarin-android/blob/d0701eb75e096f53e3c070fc6cdbad6d7477afba/src/monodroid/jni/xamarin-app.hh
#https://github.com/x41sec/tools/blob/master/Mobile/Xamarin/Xamarin_XALZ_decompress.py
#https://www.x41-dsec.de/security/news/working/research/2020/09/22/xamarin-dll-decompression/

"""
struct CompressedAssemblyHeader
{
	uint32_t magic; // COMPRESSED_DATA_MAGIC
	uint32_t descriptor_index;
	uint32_t uncompressed_length;
};
"""

COMPRESSED_DATA_MAGIC   = b"XALZ"
HEADER_SIZE             = 0xC


class XamarinCompressedAssembly(XamarinBase):

    def from_bytes(self, data:bytes):
        "Unpack and populate from <data>, checking file signature"
        (
            self.magic,
            self.index,
            self.uncompressed_size
        ) = unpack("<4sII",data[:HEADER_SIZE])
        
        if self.magic != COMPRESSED_DATA_MAGIC:
            raise FileSignatureError
        
        logging.debug(
            "Parsed header for %s: magic=%s, index=%d, uncompressed_size=%d",
            self.filepath,
            self.magic.decode('utf-8'),
            self.index,
            self.uncompressed_size
        )

        self.data_lz4 = data[HEADER_SIZE:]
        self.data = lz4.block.decompress(self.data_lz4, uncompressed_size=self.uncompressed_size)
        return self

    def write(self, filepath:str) -> None:
        "Write uncompressed data to <filepath>"
        with open(filepath, "wb") as f:
            f.write(self.data)

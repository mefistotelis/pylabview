# -*- coding: utf-8 -*-

""" LabView RSRC file format blocks.

Interpreting content of specific block types within RSRC files.
"""

# Copyright (C) 2013 Jessica Creighton <jcreigh@femtobit.org>
# Copyright (C) 2019 Mefistotelis <mefistotelis@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import enum

from PIL import Image
from hashlib import md5
from zlib import decompress
from io import BytesIO
from ctypes import *

from LVmisc import getVersion
from LVmisc import LABVIEW_COLOR_PALETTE
from LVmisc import RSRCStructure
from LVmisc import eprint

class BLOCK_COMPRESSION(enum.Enum):
    NONE = 0
    ZLIB = 1
    TEST = 2


class BlockStart(RSRCStructure):
    _fields_ = [('int1', c_uint32),		#0
                ('int2', c_uint32),		#4
                ('int3', c_uint32),		#8
                ('offset', c_uint32),	#12
                ('int5', c_uint32),		#16
    ]

    def __init__(self, po):
        self.po = po
        pass

    def check_sanity(self):
        ret = True
        return ret


class BlockSection(RSRCStructure):
    _fields_ = [('size', c_uint32),		#0
    ]

    def __init__(self, po):
        self.po = po
        pass

    def check_sanity(self):
        ret = True
        return ret

class LVSRData(RSRCStructure):
    _fields_ = [('version', c_uint32),	#0
                ('int2', c_uint16),		#4
                ('flags', c_uint16),	#6
    ]

    def __init__(self, po):
        self.po = po
        pass

class versData(RSRCStructure):
    _fields_ = [('version', c_uint32),		#0
                ('version_text', c_uint16),	#4
                ('version_info', c_uint16),	#8
    ]

    def __init__(self, po):
        self.po = po
        pass


class Block(object):
    def __init__(self, vi, header, po):
        """ Creates new Block object, capable of retrieving Block data.
        """
        self.vi = vi
        self.header = header
        self.po = po
        self.name = bytes(header.name)
        self.count = header.count + 1
        self.raw_data = []
        start_pos = \
            self.vi.rsrc_headers[-1].rsrc_offset + \
            self.vi.binflsthead.blockinfo_offset + \
            self.header.offset
        self.vi.fh.seek(start_pos)

        blkstart = BlockStart(self.po)
        if self.vi.fh.readinto(blkstart) != sizeof(blkstart):
            raise EOFError("Could not read BlockStart data.")
        if not blkstart.check_sanity():
            raise IOError("BlockStart data sanity check failed.")
        if (self.po.verbose > 2):
            print(blkstart)
        self.start = blkstart

        self.block_pos = \
            self.vi.binflsthead.dataset_offset + \
            self.start.offset
        self.size = None

    def setSizeFromBlocks(self):
        """ Set data size of this block
         To do that, first get total dataset_size, and then decrease it to
         minimum distance between this block and all other blocks
        """
        minSize = self.vi.binflsthead.dataset_size
        for block in self.vi.blocks_arr:
            if self != block and block.block_pos > self.block_pos:
                minSize = min(minSize, block.block_pos - self.block_pos)
        self.size = minSize
        if (self.po.verbose > 1):
            print("{:s}: Block {} max data size set to {:d} bytes".format(self.po.input.name,self.name,self.size))
        return minSize

    def readRawDataSections(self, section_count=1):
        last_blksect_size = sum_size = 0
        prev_section_count = len(self.raw_data)
        for i in range(0, section_count):
            sum_size += last_blksect_size

            if (self.po.verbose > 2):
                print("{:s}: Block {} section {:d} header at pos {:d}".format(self.po.input.name,self.name,i,self.block_pos + sum_size))
            self.vi.fh.seek(self.block_pos + sum_size)

            blksect = BlockSection(self.po)
            if self.vi.fh.readinto(blksect) != sizeof(blksect):
                raise EOFError("Could not read BlockSection data for block {} at {:d}.".format(self.name,self.block_pos+sum_size))
            if not blksect.check_sanity():
                raise IOError("BlockSection data for block {} sanity check failed.".format(self.name))
            if (self.po.verbose > 2):
                print(blksect)

            sum_size += sizeof(blksect)
            # Some section data could've been already loaded; read only once
            if i >= prev_section_count:
                if (sum_size + blksect.size) > self.size:
                    raise IOError("Out of block/container data in {} ({:d} + {:d}) > {:d}"\
                      .format(self.name, sum_size, blksect.size, self.size))

                data = self.vi.fh.read(blksect.size)
                self.raw_data.append(data)
            # Set last size, padded to multiplicity of 4 bytes
            last_blksect_size = blksect.size
            if last_blksect_size % 4 > 0:
                last_blksect_size += 4 - (last_blksect_size % 4)

    def getData(self, section_num=0, useCompression=BLOCK_COMPRESSION.NONE):
        if self.size is None:
            self.setSizeFromBlocks()
        if section_num >= len(self.raw_data):
            self.readRawDataSections(section_count=section_num+1)

        data = BytesIO(self.raw_data[section_num])
        if useCompression == BLOCK_COMPRESSION.NONE:
            pass
        elif useCompression == BLOCK_COMPRESSION.ZLIB:
            size = len(self.raw_data[section_num]) - 4
            if size < 2:
                raise IOError("Unable to decompress section [%s:%d]: \
                            block-size-error - size: %d" % (self.name, section_num, size))
            usize = int.from_bytes(data.read(4), byteorder='big', signed=False)
            if (usize < size) or usize > size * 10:
                raise IOError("Unable to decompress section [%s:%d]: \
                            uncompress-size-error - size: %d - uncompress-size: %d"
                            % (self.name, section_num, size, usize))
            data = BytesIO(decompress(data.read(size)))
        elif useCompression == BLOCK_COMPRESSION.TEST: # just an experiment
            size = len(self.raw_data[section_num])
            data = BytesIO(decompress(data.read(size)))
        else:
            raise ValueError("Unsupported compression type")
        return data

    def __repr__(self):
        bldata = self.getData()
        if self.size > 32:
            d = bldata.read(31).hex() + ".."
        else:
            d = bldata.read(32).hex()
        return "<" + self.__class__.__name__ + "(" + d + ")>"

class LVSR(Block):
    def __init__(self, *args):
        return Block.__init__(self, *args)

    def getData(self, *args):
        bldata = Block.getData(self, *args)
        data = LVSRData(self.po)
        if bldata.readinto(data) != sizeof(data):
            raise EOFError("Could not parse {} data.".format(self.name))
        self.data = data
        self.version = getVersion(data.version)
        self.flags = data.flags
        self.protected = ((self.flags & 0x2000) > 0)
        self.flags = self.flags & 0xDFFF
        return bldata

class vers(Block):
    def __init__(self, *args):
        return Block.__init__(self, *args)

    def getData(self, *args):
        bldata = Block.getData(self, *args)
        self.version = getVersion(int.from_bytes(bldata.read(4), byteorder='big', signed=False))
        version_text_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        self.version_text = bldata.read(version_text_len)
        version_info_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        self.version_info = bldata.read(version_info_len)
        return bldata

class icl8(Block):
    def __init__(self, *args):
        return Block.__init__(self, *args)

    def getData(self, *args):
        return Block.getData(self, *args)

    def loadIcon(self, bitsPerPixel=8):
        icon = Image.new("RGB", (32, 32))
        bldata = self.getData()
        for y in range(0, 32):
            for x in range(0, 32):
                idx = bldata.read(1)
                icon.putpixel((x, y), LABVIEW_COLOR_PALETTE[idx])
        self.icon = icon
        return icon

class BDPW(Block):
    def __init__(self, *args):
        return Block.__init__(self, *args)

    def getData(self, *args):
        bldata = Block.getData(self, *args)
        self.password_md5 = bldata.read(16)
        self.hash_1 = bldata.read(16)
        self.hash_2 = bldata.read(16)
        return bldata

class LIBN(Block):
    def __init__(self, *args):
        return Block.__init__(self, *args)

    def getData(self, *args):
        bldata = Block.getData(self, *args)
        self.count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        content_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        self.content = bldata.read(content_len)
        return bldata

class LVzp(Block):
    def __init__(self, *args):
        return Block.__init__(self, *args)

    def getData(self, *args):
        Block.getData(self, *args)
        bldata = Block.getData(self, useCompression=BLOCK_COMPRESSION.NONE) # TODO compression not supported
        return bldata


class BDH(Block):
    def __init__(self, *args):
        return Block.__init__(self, *args)

    def getData(self, *args):
        Block.getData(self, *args)
        bldata = Block.getData(self, useCompression=BLOCK_COMPRESSION.ZLIB)
        content_len = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.content = bldata.read(content_len)
        self.hash = md5(self.content).digest()
        return bldata

BDHc = BDHb = BDH

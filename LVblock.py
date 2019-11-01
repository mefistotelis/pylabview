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

from LVmisc import *
from LVconnector import *


class BLOCK_COMPRESSION(enum.Enum):
    NONE = 0
    ZLIB = 1
    XOR = 2


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

    def checkSanity(self):
        ret = True
        return ret


class BlockSection(RSRCStructure):
    _fields_ = [('size', c_uint32),		#0
    ]

    def __init__(self, po):
        self.po = po
        pass

    def checkSanity(self):
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
        if not blkstart.checkSanity():
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
            if not blksect.checkSanity():
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

    def getRawData(self, section_num=0):
        """ Retrieves bytes object with raw data of given section

            Reads the section from input stream if neccessary
        """
        if self.size is None:
            self.setSizeFromBlocks()
        if section_num >= len(self.raw_data):
            self.readRawDataSections(section_count=section_num+1)
        return self.raw_data[section_num]

    def setRawData(self, raw_data_buf, section_num=0):
        """ Sets given bytes object as section raw data

            Extends the amount of sections if neccessary
        """
        self.size  = len(raw_data_buf)
        # Insert empty bytes in any missing sections
        if section_num >= len(self.raw_data_buf):
            self.raw_data.extend([ (section_num - len(self.raw_data) + 1) * b'' ])
        # Replace the target section
        self.raw_data[section_num] = raw_data_buf

    def parseData(self, bldata):
        if (self.po.verbose > 2):
            print("{:s}: Block {} data format isn't known; leaving raw only".format(self.po.input.name,self.name))
        pass

    def needParseData(self):
        """ Returns if the block did not had its data parsed yet

            After a call to parseData(), or asfter filling the data manually, this should
            return True. Otherwise, False.
        """
        return False

    def getData(self, section_num=0, useCompression=BLOCK_COMPRESSION.NONE):
        raw_data_section = self.getRawData(section_num)
        data = BytesIO(raw_data_section)
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
        elif useCompression == BLOCK_COMPRESSION.XOR:
            size = len(self.raw_data[section_num])
            data = BytesIO(crypto_xor(data.read(size)))
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
    """ LabView Source Release
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.data = b''
        self.version = []
        self.flags = 0
        self.protected = False

    def needParseData(self):
        return (len(self.version) < 4)

    def parseData(self, bldata):
        data = LVSRData(self.po)
        if bldata.readinto(data) != sizeof(data):
            raise EOFError("Data block too short for parsing {} data.".format(self.name))
        self.data = data
        self.version = getVersion(data.version)
        self.flags = data.flags
        self.protected = ((self.flags & 0x2000) > 0)
        self.flags = self.flags & 0xDFFF

    def getData(self, *args):
        bldata = Block.getData(self, *args)
        if self.needParseData():
            self.parseData(bldata)
            bldata.seek(0)
        return bldata

class vers(Block):
    """ Version block
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.version = []
        self.version_text = b''
        self.version_info = b''

    def needParseData(self):
        return (len(self.version) < 4)

    def parseData(self, bldata):
        self.version = getVersion(int.from_bytes(bldata.read(4), byteorder='big', signed=False))
        version_text_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        self.version_text = bldata.read(version_text_len)
        version_info_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        self.version_info = bldata.read(version_info_len)

    def getData(self, *args):
        bldata = Block.getData(self, *args)
        if self.needParseData():
            self.parseData(bldata)
            bldata.seek(0)
        return bldata

    def verMajor(self):
        if len(self.version) < 4:
            self.getData()
        return self.version['major']

    def verMinor(self):
        if len(self.version) < 4:
            self.getData()
        return self.version['minor']

    def verBugfix(self):
        if len(self.version) < 4:
            self.getData()
        return self.version['bugfix']

    def verStage(self):
        if len(self.version) < 4:
            self.getData()
        return self.version['stage_text']

    def verFlags(self):
        if len(self.version) < 4:
            self.getData()
        return self.version['flags']

    def verBuild(self):
        if len(self.version) < 4:
            self.getData()
        return self.version['build']

class icl8(Block):
    """ Icon Large 8bpp
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.icon = None

    def needParseData(self):
        return (self.icon is None)

    def parseData(self, bldata):
        icon = Image.new("RGB", (32, 32))
        for y in range(0, 32):
            for x in range(0, 32):
                idx = bldata.read(1)
                icon.putpixel((x, y), LABVIEW_COLOR_PALETTE[idx])
        self.icon = icon

    def getData(self, *args):
        """ Gets the data, without loading icon into image

            Converting icon into image is done on separate request, by loadIcon() call.
        """
        return Block.getData(self, *args)

    def loadIcon(self, bitsPerPixel=8):
        bldata = self.getData()
        if self.needParseData():
            self.parseData(bldata)
        return self.icon

class BDPW(Block):
    """ Block Diagram Password
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.password_md5 = b''
        self.hash_1 = b''
        self.hash_2 = b''

    def needParseData(self):
        return (len(self.password_md5) < 16)

    def parseData(self, bldata):
        self.password_md5 = bldata.read(16)
        self.hash_1 = bldata.read(16)
        self.hash_2 = bldata.read(16)

    def getData(self, *args):
        bldata = Block.getData(self, *args)
        if self.needParseData():
            self.parseData(bldata)
            bldata.seek(0)
        return bldata

class LIBN(Block):
    """ Library Names

        Stores names of libraries which contain this RSRC file.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.count = 0
        self.content = None

    def needParseData(self):
        return (self.content is None)

    def parseData(self, bldata):
        self.count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.content = []
        for i in range(self.count):
            content_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            self.content.append(bldata.read(content_len))

    def getData(self, *args):
        bldata = Block.getData(self, *args)
        if self.needParseData():
            self.parseData(bldata)
            bldata.seek(0)
        return bldata

class LVzp(Block):
    """ Zipped Program tree

        Used in llb-like objects created by building the project.
        Contains the whole VIs hierarchy, stored within ZIP file.

        In LV from circa 2009 and before, the ZIP was stored in plain form.
        In newer LV versions, it is encrypted by simple xor-based algorithm.
    """
    def __init__(self, *args):
        super().__init__(*args)

    def getData(self, *args):
        Block.getData(self, *args)
        bldata = Block.getData(self, useCompression=BLOCK_COMPRESSION.XOR)
        return bldata


class BDHP(Block):
    """ Block Diagram Heap (LV 7beta and older)
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.content = None
        self.hash = b''

    def needParseData(self):
        return (self.content is None)

    def parseData(self, bldata):
        content_len = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.content = bldata.read(content_len)
        self.hash = md5(self.content).digest()

    def getData(self, *args):
        Block.getData(self, *args)
        bldata = Block.getData(self, useCompression=BLOCK_COMPRESSION.NONE)
        if self.needParseData():
            self.parseData(bldata)
            bldata.seek(0)
        return bldata

class BDH(Block):
    """ Block Diagram Heap (LV 7 and newer)

        Stored in "BDHx"-block. It uses a binary tree format to store hierarchy
        structures. They use a kind of "xml-tags" to open and close objects.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.content = None
        self.hash = b''

    def needParseData(self):
        return (self.content is None)

    def parseData(self, bldata):
        content_len = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.content = bldata.read(content_len)
        self.hash = md5(self.content).digest()

    def getData(self, *args):
        Block.getData(self, *args)
        bldata = Block.getData(self, useCompression=BLOCK_COMPRESSION.ZLIB)
        if self.needParseData():
            self.parseData(bldata)
            bldata.seek(0)
        return bldata

BDHc = BDHb = BDH

class VCTP(Block):
    """ Virtual Connectors / Terminal Points

        All terminals used by the .VI and the terminals of the .VI itself are stored
        in this block.

        The VCTP contains bottom-up objects. This means that objects can inherit
        from previous defined objects. So to define a cluster they first define
        every element and than add a cluster-object with a index-table containing
        all previously defined elements used by the cluster.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.count = 0
        self.content = None

    def needParseData(self):
        return (self.content is None)

    def parseData(self, bldata):
        self.count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.content = []
        pos = bldata.tell()
        for i in range(self.count):
            bldata.seek(pos)
            obj_len = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            obj_flags = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            obj_type = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            bldata.seek(pos)
            obj = newConnectorObject(self.vi, bldata, pos, obj_len, obj_flags, obj_type, self.po)
            self.content.append(obj)
            pos += obj_len

    def getData(self, *args):
        Block.getData(self, *args)
        bldata = Block.getData(self, useCompression=BLOCK_COMPRESSION.ZLIB)
        if self.needParseData():
            self.parseData(bldata)
            bldata.seek(0)
        return bldata

    def getClientConnectorsByType(self, conn_obj):
        self.getData() # Make sure the block is parsed
        return conn_obj.getClientConnectorsByType()

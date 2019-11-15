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
import re
import os

from PIL import Image
from hashlib import md5
from zlib import compress, decompress
from io import BytesIO
import xml.etree.ElementTree as ET
from ctypes import *

from LVmisc import *
from LVconnector import *


class BLOCK_CODING(enum.Enum):
    NONE = 0
    ZLIB = 1
    XOR = 2


class BlockHeader(RSRCStructure):
    _fields_ = [('name', c_ubyte * 4),	#0
                ('count', c_uint32),	#4
                ('offset', c_uint32),	#8
    ]

    def __init__(self, po):
        self.po = po
        pass

    def check_sanity(self):
        ret = True
        return ret


class BlockSectionStart(RSRCStructure):
    _fields_ = [('int1', c_uint32),		#0
                ('int2', c_uint32),		#4
                ('int3', c_uint32),		#8
                ('offset', c_uint32),	#12
                ('int5', c_uint32),		#16
    ]

    def __init__(self, po):
        self.po = po
        self.int2 = 0xFFFFFFFF
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
    def __init__(self, vi, po):
        """ Creates new Block object, capable of retrieving Block data.
        """
        self.vi = vi
        self.po = po
        # set by initWith*()
        self.header = None
        self.name = None
        self.sections = {}
        self.section_loaded = -1
        self.section_requested = 0
        # set by getRawData(); size of cummulative data for all sections in the block
        self.size = None

    def initWithRSRC(self, header):
        self.header = header
        self.name = bytes(header.name)
        self.section_loaded = -1

        start_pos = \
            self.vi.rsrc_headers[-1].rsrc_offset + \
            self.vi.binflsthead.blockinfo_offset + \
            self.header.offset

        fh = self.vi.rsrc_fh
        fh.seek(start_pos)

        self.sections = {}
        for i in range(header.count + 1):
            section = SimpleNamespace()
            section.start = BlockSectionStart(self.po)
            section.raw_data = None
            section.block_pos = None
            if fh.readinto(section.start) != sizeof(section.start):
                raise EOFError("Could not read BlockSectionStart data.")
            if (self.po.verbose > 2):
                print(section.start)
            if not section.start.checkSanity():
                raise IOError("BlockSectionStart data sanity check failed.")
            if section.start.int1 in self.sections:
                raise IOError("BlockSectionStart of given int1 exists twice.")
            section.block_pos = \
                self.vi.rsrc_headers[-1].dataset_offset + \
                section.start.offset
            self.sections[section.start.int1] = section

        self.section_requested = min(self.sections.keys())

        if (self.po.verbose > 2):
            print("{:s}: Block {} has {:d} sections".format(self.vi.src_fname,self.name,len(self.sections)))

    def initWithXML(self, block_elem):
        self.name = block_elem.tag.encode("utf-8")
        while len(self.name) < 4: self.name += b' '
        self.header = BlockHeader(self.po)
        self.header.name = (c_ubyte * 4).from_buffer_copy(self.name)
        self.section_loaded = -1

        self.sections = {}
        for i, section_elem in enumerate(block_elem):
            if (section_elem.tag != "Section"):
                raise AttributeError("Block contains something else than 'Section'")
            idx = int(section_elem.get("Index"))

            section = SimpleNamespace()
            section.start = BlockSectionStart(self.po)
            section.raw_data = None
            section.block_pos = None
            section.start.int1 = idx
            if section.start.int1 in self.sections:
                raise IOError("BlockSectionStart of given int1 exists twice.")
            self.sections[section.start.int1] = section

            self.section_requested = idx
            fmt = section_elem.get("Format")
            if fmt == "bin":
                if (self.po.verbose > 2):
                    print("{:s}: For Block {} section {:d}, reading BIN file '{}'"\
                      .format(self.vi.src_fname,self.name,idx,section_elem.get("File")))
                bin_path = os.path.dirname(self.vi.src_fname)
                if len(bin_path) > 0:
                    bin_fname = bin_path + '/' + section_elem.get("File")
                else:
                    bin_fname = section_elem.get("File")
                with open(bin_fname, "rb") as bin_fh:
                    data_buf = bin_fh.read()
                    self.setData(data_buf, section_num=idx)
            # TODO add support of XML section data
            else:
                raise NotImplementedError("Unsupported Block {} Section {:d} Format '{}'.".format(self.name,idx,fmt))

        self.header.count = len(self.sections) - 1
        self.section_requested = min(self.sections.keys())
        self.section_loaded = -1
        pass

    def setSizeFromBlocks(self):
        """ Set data size of this block

         To do that, first get total dataset_size, and then decrease it to
         minimum distance between this block and all other blocks.
         This assumes that blocks are stored as a whole, with all sections
         after each other, without interleaving with sections from other blocks.
         Blocks and sections don't have to be ordered though.
        """
        minSize = self.vi.rsrc_headers[-1].dataset_size
        # Do the minimalizing job only if all section have the position set
        if None not in [ section.block_pos for section in self.sections.values() ]:
            self_min_section_block_pos = min(section.block_pos for section in self.sections.values())
            for block in self.vi.blocks_arr:
                block_min_section_block_pos = min(section.block_pos for section in block.sections.values())
                if (self != block) and (block_min_section_block_pos > self_min_section_block_pos):
                    minSize = min(minSize, block_min_section_block_pos - self_min_section_block_pos)
        self.size = minSize
        if (self.po.verbose > 1):
            print("{:s}: Block {} max data size set to {:d} bytes".format(self.vi.src_fname,self.name,self.size))
        return minSize

    def readRawDataSections(self, section_count=None):
        last_blksect_size = sum_size = 0
        if section_count is None:
            section_count = min(self.sections.keys()) + 1
        # Get minimal starting offset of a section
        first_section_start_offset = min(section.start.offset for section in self.sections.values())

        fh = self.vi.rsrc_fh
        for i, section in sorted(self.sections.items()):
            if i >= section_count: break
            sum_size += last_blksect_size

            if (self.po.verbose > 2):
                print("{:s}: Block {} section {:d} header at pos {:d}".format(self.vi.src_fname,self.name,i,section.block_pos))
            fh.seek(section.block_pos)

            blksect = BlockSection(self.po)
            # This check assumes that all sections are written after each other in an array
            # It seem to be always the case, though file format does not mandate that
            if (section.start.offset - first_section_start_offset) + sizeof(blksect) > self.size:
                raise IOError("Requested {} section count too large; no data for secion {:d} header ({} > {})."\
                      .format(self.name, i, section.start.offset + sizeof(blksect), self.size))
            if fh.readinto(blksect) != sizeof(blksect):
                raise EOFError("Could not read BlockSection data for block {} at {:d}.".format(self.name,section.block_pos))
            if not blksect.checkSanity():
                raise IOError("BlockSection data for block {} sanity check failed.".format(self.name))
            if (self.po.verbose > 2):
                print(blksect)

            sum_size += sizeof(blksect)
            # Some section data could've been already loaded; read only once
            if section.raw_data is None:
                if (sum_size + blksect.size) > self.size:
                    raise IOError("Out of block/container data in {} ({:d} + {:d}) > {:d}"\
                      .format(self.name, sum_size, blksect.size, self.size))

                data = fh.read(blksect.size)
                section.raw_data = data
            # Set last size, padded to multiplicity of 4 bytes
            last_blksect_size = blksect.size
            if last_blksect_size % 4 > 0:
                last_blksect_size += 4 - (last_blksect_size % 4)

    def getRawData(self, section_num=None):
        """ Retrieves bytes object with raw data of given section

            Reads the section from input stream if neccessary
        """
        if section_num is None:
            section_num = min(self.sections.keys())
        if self.size is None:
            self.setSizeFromBlocks()

        if section_num not in self.sections:
                    raise IOError("Within block {} there is no section number {:d}"\
                      .format(self.name, section_num))
        if self.sections[section_num].raw_data is None:
            self.readRawDataSections(section_count=section_num+1)
        return self.sections[section_num].raw_data

    def setRawData(self, raw_data_buf, section_num=None):
        """ Sets given bytes object as section raw data

            Extends the amount of sections if neccessary
        """
        if section_num is None:
            section_num = min(self.sections.keys())
        # If changing currently loaded section, mark it as not loaded anymore
        if self.section_loaded == section_num:
            self.section_loaded = -1
        # Insert empty bytes in any missing sections
        if section_num not in self.sections:
            section = SimpleNamespace()
            section.start = BlockSectionStart(self.po)
            section.start.int1 = section_num
            section.raw_data = b''
            self.sections[section_num] = section
        # Replace the target section
        self.sections[section_num].raw_data = raw_data_buf

    def getSection(self, section_num=None):
        """ Retrieves section of given number, or first one

            Does not force data read
        """
        if section_num is None:
            section_num = min(self.sections.keys())
        if section_num not in self.sections:
                    raise IOError("Within block {} there is no section number {:d}"\
                      .format(self.name, section_num))
        return self.sections[section_num]

    def parseRSRCData(self, bldata):
        """ Implements setting block properties from Byte Stream of a section

            Called by parseSection() to set the specific section as loaded.
        """
        if (self.po.verbose > 2):
            print("{:s}: Block {} data format is not known; leaving raw only".format(self.vi.src_fname,self.name))
        pass

    def parseData(self, section_num=-1):
        if section_num == -1:
            section_num = self.section_requested
        else:
            self.section_requested = section_num
        if self.needParseData():
            bldata = self.getData(section_num=section_num, use_coding=BLOCK_CODING.NONE)
            self.parseRSRCData(bldata)
        self.section_loaded = self.section_requested

    def needParseData(self):
        """ Returns if the block needs its data to be parsed

            After a call to parseData(), or after filling the data manually, this should
            return True. Otherwise, False.
        """
        return (len(self.sections) > 0) and (self.section_loaded != self.section_requested)

    def getData(self, section_num=0, use_coding=BLOCK_CODING.NONE):
        raw_data_section = self.getRawData(section_num)
        data = BytesIO(raw_data_section)
        if use_coding == BLOCK_CODING.NONE:
            pass
        elif use_coding == BLOCK_CODING.ZLIB:
            size = len(raw_data_section) - 4
            if size < 2:
                raise IOError("Unable to decompress section [%s:%d]: " \
                            "block-size-error - size: %d" % (self.name, section_num, size))
            usize = int.from_bytes(data.read(4), byteorder='big', signed=False)
            # Acording to zlib docs, max theoretical compression ration is 1032:1
            if (usize < size) or usize > size * 1032:
                raise IOError("Unable to decompress section [%s:%d]: " \
                            "uncompress-size-error - size: %d - uncompress-size: %d"
                            % (self.name, section_num, size, usize))
            data = BytesIO(decompress(data.read(size)))
        elif use_coding == BLOCK_CODING.XOR:
            size = len(raw_data_section)
            data = BytesIO(crypto_xor(data.read(size)))
        else:
            raise ValueError("Unsupported compression type")
        return data

    def setData(self, data_buf, section_num=0, use_coding=BLOCK_CODING.NONE):
        if use_coding == BLOCK_CODING.NONE:
            raw_data_section = data_buf
            pass
        elif use_coding == BLOCK_CODING.ZLIB:
            size = len(data_buf)
            raw_data_section = int(size).to_bytes(4, byteorder='big')
            raw_data_section += compress(data_buf)
        elif use_coding == BLOCK_CODING.XOR:
            raw_data_section = crypto_xor(data_buf) # TODO make proper encrypt algorithm; this one is decrypt
        else:
            raise ValueError("Unsupported compression type")
        self.setRawData(raw_data_section, section_num=section_num)

    def saveRSRCData(self, fh):
        # Header is to be filled while saving Info part, so the value below is overwritten
        self.header.count = len(self.sections) - 1

        sect_starts = []
        for snum, section in self.sections.items():

            # Store the dataset offset in proper structure
            section.start.offset = fh.tell() - \
            self.vi.rsrc_headers[-1].dataset_offset
            section.start.int1 = snum

            if (self.po.verbose > 2):
                print(section.start)
            if not section.start.checkSanity():
                raise IOError("BlockSectionStart data sanity check failed.")

            blksect = BlockSection(self.po)
            blksect.size = len(section.raw_data)
            fh.write((c_ubyte * sizeof(blksect)).from_buffer_copy(blksect))
            fh.write(section.raw_data)
            if blksect.size % 4 > 0:
                padding_len = 4 - (blksect.size % 4)
                fh.write((b'\0' * padding_len))
            sect_starts.append(section.start)

        return sect_starts

    def exportXMLTree(self):
        """ Export the file data into XML tree
        """
        pretty_name = self.name.decode(encoding='UTF-8')
        pretty_name = re.sub('[^a-zA-Z0-9_-]+', '', pretty_name)
        block_fpath = os.path.dirname(self.po.xml)
        elem = ET.Element(pretty_name)
        elem.text = "\n"
        elem.tail = "\n"
        for snum, section in self.sections.items():
            if len(self.sections) == 1:
                block_fname = "{:s}_{:s}.bin".format(self.po.filebase, pretty_name)
            else:
                block_fname = "{:s}_{:s}{:d}.bin".format(self.po.filebase, pretty_name, snum)
            if len(block_fpath) > 0:
                block_fname = block_fpath + '/' + block_fname
            bldata = self.getData(section_num=snum)
            with open(block_fname, "wb") as block_fd:
                block_fd.write(bldata.read())
            subelem = ET.SubElement(elem,"Section")
            subelem.tail = "\n"
            subelem.set("Index", str(snum))
            subelem.set("Format", "bin")
            subelem.set("File", block_fname)
        return elem

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

    def parseRSRCData(self, bldata):
        data = LVSRData(self.po)
        if bldata.readinto(data) != sizeof(data):
            raise EOFError("Data block too short for parsing {} data.".format(self.name))
        self.data = data
        self.version = getVersion(data.version)
        self.flags = data.flags
        self.protected = ((self.flags & 0x2000) > 0)
        self.flags = self.flags & 0xDFFF

    def getData(self, section_num=0, use_coding=BLOCK_CODING.NONE):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=0, use_coding=BLOCK_CODING.NONE):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)

    def saveRSRCData(self, fh):
        # Unlike other sections, this one has int2 zeroed out
        for snum, section in self.sections.items():
            section.start.int2 = 0

        return Block.saveRSRCData(self, fh)


class vers(Block):
    """ Version block
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.version = []
        self.version_text = b''
        self.version_info = b''

    def parseRSRCData(self, bldata):
        self.version = getVersion(int.from_bytes(bldata.read(4), byteorder='big', signed=False))
        version_text_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        self.version_text = bldata.read(version_text_len)
        version_info_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        self.version_info = bldata.read(version_info_len)

    def getData(self, section_num=0, use_coding=BLOCK_CODING.NONE):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=0, use_coding=BLOCK_CODING.NONE):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)

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

    def parseRSRCData(self, bldata):
        icon = Image.new("RGB", (32, 32))
        for y in range(0, 32):
            for x in range(0, 32):
                idx = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
                icon.putpixel((x, y), LABVIEW_COLOR_PALETTE[idx])
        self.icon = icon

    def getData(self, section_num=0, use_coding=BLOCK_CODING.NONE):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=0, use_coding=BLOCK_CODING.NONE):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)

    def loadIcon(self, bitsPerPixel=8):
        self.parseData()
        return self.icon


class BDPW(Block):
    """ Block Diagram Password
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.password = None
        self.password_md5 = b''
        self.hash_1 = b''
        self.hash_2 = b''
        self.salt_iface_idx = None
        self.salt = None

    def parseRSRCData(self, bldata):
        self.password_md5 = bldata.read(16)
        self.hash_1 = bldata.read(16)
        self.hash_2 = bldata.read(16)

    def getData(self, section_num=0, use_coding=BLOCK_CODING.NONE):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=0, use_coding=BLOCK_CODING.NONE):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)

    @staticmethod
    def getPasswordSaltFromTerminalCounts(numberCount, stringCount, pathCount):
        salt = int(numberCount).to_bytes(4, byteorder='little')
        salt += int(stringCount).to_bytes(4, byteorder='little')
        salt += int(pathCount).to_bytes(4, byteorder='little')
        return salt

    def scanForHashSalt(self, presalt_data=b'', postsalt_data=b''):
        salt = b''
        vers = self.vi.get('vers')
        if vers is None:
            if (po.verbose > 0):
                eprint("{:s}: Warning: Block '{}' not found; using empty password salt".format(self.vi.src_fname,'vers'))
            self.salt = salt
            return salt
        if vers.verMajor() >= 12:
            # Figure out the salt
            salt_iface_idx = None
            VCTP = self.vi.get_or_raise('VCTP')
            interfaceEnumerate = self.vi.connectorEnumerate(fullType=CONNECTOR_FULL_TYPE.Terminal)
            # Connectors count if one of the interfaces is the source of salt; usually it's the last interface, so check in reverse
            for i, iface_idx, iface_obj in reversed(interfaceEnumerate):
                term_connectors = VCTP.getClientConnectorsByType(iface_obj)
                salt = BDPW.getPasswordSaltFromTerminalCounts(len(term_connectors['number']), len(term_connectors['string']), len(term_connectors['path']))
                md5_hash_1 = md5(presalt_data + salt + postsalt_data).digest()
                if md5_hash_1 == self.hash_1:
                    if (self.po.verbose > 1):
                        print("{:s}: Found matching salt {}, interface {:d}/{:d}".format(self.vi.src_fname,salt.hex(),i+1,len(interfaceEnumerate)))
                    salt_iface_idx = iface_idx
                    break

            self.salt_iface_idx = salt_iface_idx

            if salt_iface_idx is not None:
                term_connectors = VCTP.getClientConnectorsByType(VCTP.content[salt_iface_idx])
                salt = BDPW.getPasswordSaltFromTerminalCounts(len(term_connectors['number']), len(term_connectors['string']), len(term_connectors['path']))
            else:
                # For LV14, this should only be used for a low percentage of VIs which have the salt zeroed out
                # But in case the terminal counting algorithm isn't perfect or future format changes affect it, that will also be handy
                print("{:s}: No matching salt found by Interface scan; doing brute-force scan".format(self.vi.src_fname))
                for i in range(256*256*256):
                    numberCount = 0
                    stringCount = 0
                    pathCount = 0
                    for b in range(8):
                        numberCount |= (i & (2 ** (3*b+0))) >> (2*b+0)
                        stringCount |= (i & (2 ** (3*b+1))) >> (2*b+1)
                        pathCount   |= (i & (2 ** (3*b+2))) >> (2*b+2)
                    salt = BDPW.getPasswordSaltFromTerminalCounts(numberCount, stringCount, pathCount)
                    md5_hash_1 = md5(presalt_data + salt + postsalt_data).digest()
                    if md5_hash_1 == self.hash_1:
                        if (self.po.verbose > 1):
                            print("{:s}: Found matching salt {} via brute-force".format(self.vi.src_fname,salt.hex()))
                        break
        self.salt = salt
        return salt

    def findHashSalt(self, password_md5, LIBN_content, LVSR_content, force_scan=False):
        if force_scan:
            self.salt_iface_idx = None
            self.salt = None
        if self.salt_iface_idx is not None:
            # If we've previously found an interface on which the salt is based, use that interface
            VCTP = self.vi.get_or_raise('VCTP')
            term_connectors = VCTP.getClientConnectorsByType(VCTP.content[self.salt_iface_idx])
            salt = BDPW.getPasswordSaltFromTerminalCounts(len(term_connectors['number']), len(term_connectors['string']), len(term_connectors['path']))
        elif self.salt is not None:
            # If we've previously brute-forced the salt, use that same salt
            salt = self.salt
        else:
            # If we didn't determined the salt yet, do  a scan
            salt = self.scanForHashSalt(presalt_data=password_md5+LIBN_content+LVSR_content)
        return salt

    def setPassword(self, password_text=None, password_md5=None, store=True):
        """ Sets new password, without recalculating hashes
        """
        if password_text is not None:
            if store:
                self.password = password_text
            newPassBin = password_text.encode('utf-8')
            password_md5 = md5(newPassBin).digest()
        else:
            if store:
                self.password = None
        if password_md5 is None:
            raise ValueError("Requested to set password, but no new password provided in text nor md5 form")
        if store:
            self.password_md5 = password_md5
        return password_md5


    def recalculateHash1(self, password_md5=None, store=True):
        """ Calculates the value of hash_1, either stores it or only returns

            Re-calculation is made using previously computed salt if available, or newly computed on first run.
            Supplying custom password on first run will lead to inability to find salt; fortunately,
            first run is quite early, during validation of parsed data.
        """
        if password_md5 is None:
            password_md5 = self.password_md5
        # get VI-versions container;
        # 'LVSR' for Version 6,7,8,...
        # 'LVIN' for Version 5
        LVSR = self.vi.get_one_of_or_raise('LVSR', 'LVIN')

        # If library name is missing, we don't fail, just use empty (verified on LV14 VIs)
        LIBN = self.vi.get_one_of('LIBN')
        if LIBN is not None and LIBN.count > 0:
            LIBN_content = b':'.join(LIBN.content)
        else:
            LIBN_content = b''

        LVSR_content = LVSR.getRawData()

        if (self.po.verbose > 2):
            print("{:s}: LIBN_content: {}".format(self.vi.src_fname,LIBN_content))
            print("{:s}: LVSR_content md5: {:s}".format(self.vi.src_fname,md5(LVSR_content).digest().hex()))

        salt = self.findHashSalt(password_md5, LIBN_content, LVSR_content)

        hash1_data = password_md5 + LIBN_content + LVSR_content + salt

        md5_hash_1 = md5(hash1_data).digest()
        if store:
            self.hash_1 = md5_hash_1
        return md5_hash_1

    def recalculateHash2(self, md5_hash_1=None, store=True):
        """ Calculates the value of hash_2, either stores it or only returns

            Re-calculation is made using previously computed hash_1
            and BDH block if the VI file
        """
        if md5_hash_1 is None:
            md5_hash_1 = self.hash_1

        # get block-diagram container;
        # 'BDHc' for LV 10,11,12
        # 'BDHb' for LV 7,8
        # 'BDHP' for LV 5,6,7beta
        BDH = self.vi.get_one_of('BDHc', 'BDHb', 'BDHP')

        if BDH is not None:
            BDH_hash = BDH.getContentHash()
            hash2_data = md5_hash_1 + BDH_hash
        else:
            # If there's no BDH, go with empty string (verified on LV14 VIs)
            hash2_data = b''

        md5_hash_2 = md5(hash2_data).digest()
        if store:
            self.hash_2 = md5_hash_2
        return md5_hash_2


class LIBN(Block):
    """ Library Names

        Stores names of libraries which contain this RSRC file.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.count = 0
        self.content = None

    def parseRSRCData(self, bldata):
        self.count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.content = []
        for i in range(self.count):
            content_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            self.content.append(bldata.read(content_len))

    def getData(self, section_num=0, use_coding=BLOCK_CODING.NONE):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=0, use_coding=BLOCK_CODING.NONE):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)


class LVzp(Block):
    """ Zipped Program tree

        Used in llb-like objects created by building the project.
        Contains the whole VIs hierarchy, stored within ZIP file.

        In LV from circa 2009 and before, the ZIP was stored in plain form.
        In newer LV versions, it is encrypted by simple xor-based algorithm.
    """
    def __init__(self, *args):
        super().__init__(*args)

    def getData(self, section_num=0, use_coding=BLOCK_CODING.XOR):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=0, use_coding=BLOCK_CODING.XOR):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)


class BDHP(Block):
    """ Block Diagram Heap (LV 7beta and older)
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.content = None

    def parseRSRCData(self, bldata):
        content_len = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.content = bldata.read(content_len)

    def getData(self, section_num=0, use_coding=BLOCK_CODING.NONE):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=0, use_coding=BLOCK_CODING.NONE):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)

    def getContentHash(self):
        return md5(self.content).digest()

class BDH(Block):
    """ Block Diagram Heap (LV 7 and newer)

        Stored in "BDHx"-block. It uses a binary tree format to store hierarchy
        structures. They use a kind of "xml-tags" to open and close objects.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.content = None

    def parseRSRCData(self, bldata):
        content_len = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.content = bldata.read(content_len)

    def getData(self, section_num=0, use_coding=BLOCK_CODING.ZLIB):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=0, use_coding=BLOCK_CODING.ZLIB):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)

    def getContentHash(self):
        return md5(self.content).digest()

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

    def parseConnector(self, bldata, pos):
        bldata.seek(pos)
        obj_len = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        obj_flags = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        obj_type = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        bldata.seek(pos)
        obj = newConnectorObject(self.vi, bldata, len(self.content), pos, obj_len, obj_flags, obj_type, self.po)
        self.content.append(obj)
        return obj.index, obj_len

    def parseRSRCData(self, bldata):
        self.count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.content = []
        pos = bldata.tell()
        for i in range(self.count):
            obj_idx, obj_len = self.parseConnector(bldata, pos)
            pos += obj_len

    def getData(self, section_num=0, use_coding=BLOCK_CODING.ZLIB):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=0, use_coding=BLOCK_CODING.ZLIB):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)

    def getClientConnectorsByType(self, conn_obj):
        self.getData() # Make sure the block is parsed
        type_list = conn_obj.getClientConnectorsByType()
        if (self.po.verbose > 1):
            print("{:s}: Terminal {:d} connectors: {:s}={:d} {:s}={:d} {:s}={:d} {:s}={:d} {:s}={:d}"\
              .format(self.vi.src_fname,conn_obj.index,\
              'number',len(type_list['number']),\
              'path',len(type_list['path']),\
              'string',len(type_list['string']),\
              'compound',len(type_list['compound']),\
              'other',len(type_list['other'])))
        return type_list

# -*- coding: utf-8 -*-

""" LabView RSRC file format blocks.

Classes for interpreting content of specific block types within RSRC files.
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
from LVinstrument import *
from LVresource import *

class BLOCK_CODING(enum.Enum):
    NONE = 0
    ZLIB = 1
    XOR = 2


class BlockHeader(RSRCStructure):
    _fields_ = [('ident', c_ubyte * 4),	#0 4-byte block identifier
                ('count', c_uint32),	#4 Amount of sections for that block
                ('offset', c_uint32),	#8 Offset to the array of BlockSectionStart structs
    ]

    def __init__(self, po):
        self.po = po
        pass

    def checkSanity(self):
        ret = True
        return ret


class BlockSectionStart(RSRCStructure):
    """ Info Header of a section

        Stores location of its data, but also name offset and index
    """
    _fields_ = [('section_idx', c_int32),	#0
                ('name_offset', c_uint32),	#4 Offset to the text name of this section; only some sections have text names
                ('int3', c_uint32),		#8
                ('data_offset', c_uint32),	#12 Offset to BlockSectionData (and the raw data which follows it) of this section
                ('int5', c_uint32),		#16
    ]

    def __init__(self, po):
        self.po = po
        self.name_offset = 0xFFFFFFFF
        pass

    def checkSanity(self):
        ret = True
        return ret


class BlockSectionData(RSRCStructure):
    """ Header for raw data of a section within a block

        Stores only size of the raw data which follows.
    """
    _fields_ = [('size', c_uint32),		#0
    ]

    def __init__(self, po):
        self.po = po
        pass

    def checkSanity(self):
        ret = True
        return ret


class versData(RSRCStructure):
    _fields_ = [('version', c_uint32),		#0
                ('version_text', c_uint16),	#4
                ('version_info', c_uint16),	#8
    ]

    def __init__(self, po):
        self.po = po
        pass


class Section(object):
    def __init__(self, vi, po):
        """ Creates new Section object, represention one of possible contents of a Block.

        Support of a section is mostly implemented in Block, so there isn't much here.
        """
        self.vi = vi
        self.po = po
        self.start = BlockSectionStart(self.po)
        # Raw data of the section, from just after BlockSectionData struct; not decrypted nor decompressed
        self.raw_data = None
        # Position of BlockSectionData for this section within RSRC file
        self.block_pos = None
        # Section name text string, from Info section
        self.name_text = None


class Block(object):
    """ Generic block
    """
    def __init__(self, vi, po):
        """ Creates new Block object, capable of retrieving Block data.
        """
        self.vi = vi
        self.po = po
        # set by initWith*()
        self.header = None
        self.ident = None
        self.sections = {}
        self.section_loaded = None
        self.section_requested = 0
        # set by getRawData(); size of cummulative data for all sections in the block
        self.size = None
        if self.__doc__:
            self.full_name = " {:s} ".format(self.__doc__.split('\n')[0].strip())
        else:
            self.full_name = ""

    def createSection(self):
        section = Section(self.vi, self.po)
        return section

    def initWithRSRCEarly(self, header):
        """ Early part of block loading from RSRC file

        At the point it is executed, other sections are inaccessible.
        """
        self.header = header
        self.ident = bytes(header.ident)
        self.section_loaded = None

        start_pos = \
            self.vi.rsrc_headers[-1].rsrc_info_offset + \
            self.vi.binflsthead.blockinfo_offset + \
            self.header.offset

        fh = self.vi.rsrc_fh
        fh.seek(start_pos)

        self.sections = {}
        for i in range(header.count + 1):
            section = self.createSection()
            if fh.readinto(section.start) != sizeof(section.start):
                raise EOFError("Could not read BlockSectionStart data.")
            if (self.po.verbose > 2):
                print(section.start)
            if not section.start.checkSanity():
                raise IOError("BlockSectionStart data sanity check failed.")
            if section.start.section_idx in self.sections:
                raise IOError("BlockSectionStart of given section_idx exists twice.")
            section.block_pos = \
                self.vi.rsrc_headers[-1].rsrc_data_offset + \
                section.start.data_offset
            self.sections[section.start.section_idx] = section

        self.section_requested = self.defaultSectionNumber()

        if (self.po.verbose > 2):
            print("{:s}: Block {} has {:d} sections".format(self.vi.src_fname,self.ident,len(self.sections)))

    def initWithRSRCLate(self):
        """ Late part of block loading from RSRC file

        Can access some basic data from other sections.
        """
        fh = self.vi.rsrc_fh
        # After BlockSectionStart list, there is Block Section Names list; only some sections have a name
        names_start = self.vi.getPositionOfBlockSectionNames()
        names_end = self.vi.getPositionOfBlockInfoEnd()
        for section in self.sections.values():
            if section.start.name_offset == 0xFFFFFFFF: # This value means no name
                continue
            if names_start + section.start.name_offset >= names_end:
                raise IOError("Section Name position exceeds RSRC Info size.")
            fh.seek(names_start + section.start.name_offset)
            name_text_len = int.from_bytes(fh.read(1), byteorder='big', signed=False)
            section.name_text = fh.read(name_text_len)


    def initWithXMLSection(self, section, section_elem):
        """ Imports section data from XML

            Generic code, used when section is stored as raw data.
            This can be overloaded to support actually parsed section formats.

            After this call, and then a call to initWithXMLLate(), raw_data for
            this section should be set. Since the 'late' method will be in most
            cases useless for XML, it is good to set that data at end of this function.
        """
        snum = section.start.section_idx
        fmt = section_elem.get("Format")
        if fmt == "bin":# Format="bin" - the content is stored separately as raw binary data
            if (self.po.verbose > 2):
                print("{:s}: For Block {} section {:d}, reading BIN file '{}'"\
                  .format(self.vi.src_fname,self.ident,snum,section_elem.get("File")))
            bin_path = os.path.dirname(self.vi.src_fname)
            if len(bin_path) > 0:
                bin_fname = bin_path + '/' + section_elem.get("File")
            else:
                bin_fname = section_elem.get("File")
            with open(bin_fname, "rb") as bin_fh:
                data_buf = bin_fh.read()
            self.setData(data_buf, section_num=snum)
        else:
            raise NotImplementedError("Unsupported Block {} Section {:d} Format '{}'.".format(self.ident,snum,fmt))
        pass


    def initWithXMLEarly(self, block_elem):
        """ Early part of block loading from XML file

        At the point it is executed, other blocks and sections are inaccessible.
        """
        self.ident = getRsrcTypeFromPrettyStr(block_elem.tag)
        self.header = BlockHeader(self.po)
        self.header.ident = (c_ubyte * 4).from_buffer_copy(self.ident)
        self.section_loaded = None

        self.sections = {}
        for i, section_elem in enumerate(block_elem):
            if (section_elem.tag != "Section"):
                raise AttributeError("Block contains something else than 'Section'")
            snum = int(section_elem.get("Index"))
            block_int5 = section_elem.get("Int5")
            name_text = section_elem.get("Name")

            section = self.createSection()
            section.start.section_idx = snum
            if block_int5 is not None:
                section.start.int5 = int(block_int5, 0)

            if name_text is not None:
                section.name_text = name_text.encode(self.vi.textEncoding)
            if section.start.section_idx in self.sections:
                raise IOError("BlockSectionStart of given section_idx exists twice.")
            self.sections[section.start.section_idx] = section

            self.section_requested = snum
            self.initWithXMLSection(section, section_elem)

        self.header.count = len(self.sections) - 1
        pass

    def initWithXMLLate(self):
        """ Late part of block loading from XML file

        Can access some basic data from other blocks and sections.
        Not really needed, but kept for symmetry with RSRC loading functions.
        """
        self.section_requested = self.defaultSectionNumber()
        self.section_loaded = None
        pass

    def setSizeFromBlocks(self):
        """ Set data size of this block

         To do that, first get total rsrc_data_size, and then decrease it to
         minimum distance between this block and all other blocks.
         This assumes that blocks are stored as a whole, with all sections
         after each other, without interleaving with sections from other blocks.
         Blocks and sections don't have to be ordered though.
        """
        minSize = self.vi.rsrc_headers[-1].rsrc_data_size
        # Do the minimalizing job only if all section have the position set
        if None not in [ section.block_pos for section in self.sections.values() ]:
            self_min_section_block_pos = min(section.block_pos for section in self.sections.values())
            for ident, block in self.vi.blocks.items():
                block_min_section_block_pos = min(section.block_pos for section in block.sections.values())
                if (self != block) and (block_min_section_block_pos > self_min_section_block_pos):
                    minSize = min(minSize, block_min_section_block_pos - self_min_section_block_pos)
        self.size = minSize
        if (self.po.verbose > 1):
            print("{:s}: Block {} max data size set to {:d} bytes".format(self.vi.src_fname,self.ident,self.size))
        return minSize

    def readRawDataSections(self, section_count=None):
        last_blksect_size = sum_size = 0
        if section_count is None:
            section_count = self.defaultSectionNumber() + 1
        rsrc_data_size = self.vi.rsrc_headers[-1].rsrc_data_size

        fh = self.vi.rsrc_fh
        for snum, section in sorted(self.sections.items()):
            if snum >= section_count: break
            sum_size += last_blksect_size

            if section.block_pos is None:
                raise RuntimeError("Block {} section {} have no block position computed".format(self.ident,snum))
            if (self.po.verbose > 2):
                print("{:s}: Block {} section {} header at pos {:d}".format(self.vi.src_fname,self.ident,snum,section.block_pos))

            fh.seek(section.block_pos)

            blksect = BlockSectionData(self.po)
            # This check assumes that all sections are written after each other in an array
            # It seem to be always the case, though file format does not mandate that
            if section.start.data_offset + sizeof(BlockSectionData) > rsrc_data_size:
                raise IOError("Requested {} section {:d} data offset exceeds size of data block ({} > {})."\
                      .format(self.ident, i, section.start.data_offset + sizeof(BlockSectionData), rsrc_data_size))
            if fh.readinto(blksect) != sizeof(blksect):
                raise EOFError("Could not read BlockSectionData struct for block {} at {:d}.".format(self.ident,section.block_pos))
            if not blksect.checkSanity():
                raise IOError("BlockSectionData struct for block {} sanity check failed.".format(self.ident))
            if (self.po.verbose > 2):
                print(blksect)

            sum_size += sizeof(blksect)
            # Some section data could have been already loaded; read only once
            if section.raw_data is None:
                if (sum_size + blksect.size) > rsrc_data_size:
                    raise IOError("Out of block/container data in {} ({:d} + {:d}) > {:d}"\
                      .format(self.ident, sum_size, blksect.size, self.size))

                data = fh.read(blksect.size)
                section.raw_data = data
            # Set last size, padded to multiplicity of 4 bytes
            last_blksect_size = blksect.size
            if last_blksect_size % 4 > 0:
                last_blksect_size += 4 - (last_blksect_size % 4)

    def hasRawData(self, section_num=None):
        """ Returns whether given section has raw data set
        """
        if section_num is None:
            section_num = self.defaultSectionNumber()
        return (self.sections[section_num].raw_data is not None)

    def getRawData(self, section_num=None):
        """ Retrieves bytes object with raw data of given section

            Reads the section from input stream if neccessary
        """
        if section_num is None:
            section_num = self.defaultSectionNumber()
        if self.size is None:
            self.setSizeFromBlocks()

        if section_num not in self.sections:
                    raise IOError("Within block {} there is no section number {:d}"\
                      .format(self.ident, section_num))
        if self.sections[section_num].raw_data is None:
            self.readRawDataSections(section_count=section_num+1)
        return self.sections[section_num].raw_data

    def setRawData(self, raw_data_buf, section_num=None):
        """ Sets given bytes object as section raw data

            Extends the amount of sections if neccessary
        """
        if section_num is None:
            section_num = self.defaultSectionNumber()
        # If changing currently loaded section, mark it as not loaded anymore
        if self.section_loaded == section_num:
            self.section_loaded = None
        # Insert empty bytes in any missing sections
        if section_num not in self.sections:
            section = self.createSection()
            section.start.section_idx = section_num
            self.sections[section_num] = section
        # Replace the target section
        self.sections[section_num].raw_data = raw_data_buf

    def getSection(self, section_num=None):
        """ Retrieves section of given number, or first one

            Does not force data read
        """
        if section_num is None:
            section_num = self.self.defaultSectionNumber()
        if section_num not in self.sections:
                    raise IOError("Within block {} there is no section number {:d}"\
                      .format(self.ident, section_num))
        return self.sections[section_num]

    def parseRSRCData(self, section_num, bldata):
        """ Implements setting block properties from Byte Stream of a section

        Called by parseData() to set the specific section as loaded.
        """
        if (self.po.verbose > 2):
            print("{:s}: Block {} data format is not known; leaving raw only".format(self.vi.src_fname,self.ident))
        pass

    def parseXMLData(self, section_num=None):
        """ Implements setting block properties from properties of a section, set from XML

            Called by parseData() to set the specific section as loaded.
        """
        if section_num is None:
            section_num = self.section_loaded

        self.updateSectionData(section_num=section_num)
        pass

    def parseData(self, section_num=None):
        """ Parse data of specific section and place it as Block properties

        The given section will be set as both requested and loaded.
        """
        if section_num is None:
            section_num = self.section_requested
        else:
            self.section_requested = section_num

        if self.needParseData():
            if self.vi.dataSource == "rsrc" or self.hasRawData(section_num=section_num):
                bldata = self.getData(section_num=section_num)
                self.parseRSRCData(section_num, bldata)
            elif self.vi.dataSource == "xml":
                self.parseXMLData(section_num=section_num)

        self.section_loaded = self.section_requested

    def updateSectionData(self, section_num=None, avoid_recompute=False):
        """ Updates RAW data stored in given section to any changes in properties

        The avoid_recompute flag should be implemented to allow doing partial update,
        without using data outside of the block. If this flag is used, then it is expected
        that the data will be re-saved later, when other blocks will be accessible
        and any externally dependdent values can be re-computed.
        """
        if section_num is None:
            section_num = self.section_loaded

        if self.sections[section_num].raw_data is None:
            raise RuntimeError("Block {} section {} has no raw data generation method".format(self.ident,section_num))
        pass

    def updateData(self):
        """ Updates RAW data stored in the block to any changes in properties

        Updates raw data for all sections. Though current change in properties
        are only kept for current section.
        """
        skip_sections = []
        # If we already had a properly parsed section, store its data first
        if not self.needParseData():
            self.updateSectionData()
            skip_sections.append(self.section_requested)
        prev_section_num = self.section_requested

        for section_num in self.sections:
            if section_num in skip_sections: continue
            self.parseData(section_num=section_num)
            self.updateSectionData(section_num=section_num)

        self.section_requested = prev_section_num
        pass

    def needParseData(self):
        """ Returns if the block needs its data to be parsed

            After a call to parseData(), or after filling the data manually, this should
            return True. Otherwise, False.
        """
        return (len(self.sections) > 0) and (self.section_loaded != self.section_requested)

    def checkSanity(self):
        """ Checks whether properties of this object and all sub-object are sane

        Sane objects have values of properties within expected bounds.
        This call expacted all the objects to be already parsed during the call.
        """
        ret = True
        return ret

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        if section_num is None:
            section_num = self.section_requested
        raw_data_section = self.getRawData(section_num)
        data = BytesIO(raw_data_section)
        if use_coding == BLOCK_CODING.NONE:
            pass
        elif use_coding == BLOCK_CODING.ZLIB:
            size = len(raw_data_section) - 4
            if size < 2:
                raise IOError("Unable to decompress section [%s:%d]: " \
                            "block-size-error - size: %d" % (self.ident, section_num, size))
            usize = int.from_bytes(data.read(4), byteorder='big', signed=False)
            # Acording to zlib docs, max theoretical compression ration is 1032:1
            if ( (size > 32) and (usize < (size*9) // 10) ) or (usize > size * 1032):
                raise IOError("Unable to decompress section [%s:%d]: " \
                            "uncompress-size-error - size: %d - uncompress-size: %d"
                            % (self.ident, section_num, size, usize))
            data = BytesIO(decompress(data.read(size)))
        elif use_coding == BLOCK_CODING.XOR:
            size = len(raw_data_section)
            data = BytesIO(crypto_xor8320_decrypt(data.read(size)))
        else:
            raise ValueError("Unsupported compression type")
        return data

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        if section_num is None:
            section_num = self.section_requested

        if use_coding == BLOCK_CODING.NONE:
            raw_data_section = data_buf
            pass
        elif use_coding == BLOCK_CODING.ZLIB:
            size = len(data_buf)
            raw_data_section = int(size).to_bytes(4, byteorder='big')
            raw_data_section += compress(data_buf)
        elif use_coding == BLOCK_CODING.XOR:
            raw_data_section = crypto_xor8320_encrypt(data_buf)
        else:
            raise ValueError("Unsupported compression type")

        self.setRawData(raw_data_section, section_num=section_num)

    def saveRSRCData(self, fh, section_names):
        # Header is to be filled while saving Info part, so the value below is overwritten
        self.header.count = len(self.sections) - 1
        rsrc_head = self.vi.rsrc_headers[-1]

        # Failed try of filling names in the same order as LabView; maybe we'll try again later
        #for snum, section in sorted(self.sections.items(), key=lambda t: abs(t[0])):

        sect_starts = []
        for snum, section in self.sections.items():
            if section.raw_data is None:
                raise RuntimeError("No raw data set in block {} section {}".format(self.ident,snum))

            # Store the dataset offset in proper structure
            section.start.data_offset = fh.tell() - rsrc_head.rsrc_data_offset
            section.start.section_idx = snum

            # Names are filled in different order when saved by LabView.
            # The order shouldn't really matter for anything, but makes files
            # generated by the tool harder to compare to originals.
            if section.name_text is not None:
                section.start.name_offset = len(section_names)
                section_names.extend(int(len(section.name_text)).to_bytes(1, byteorder='big'))
                section_names.extend(section.name_text)
            else:
                section.start.name_offset = 0xFFFFFFFF

            if (self.po.verbose > 2):
                print(section.start)
            if not section.start.checkSanity():
                raise IOError("BlockSectionStart data sanity check failed.")

            blksect = BlockSectionData(self.po)
            blksect.size = len(section.raw_data)
            fh.write((c_ubyte * sizeof(blksect)).from_buffer_copy(blksect))
            fh.write(section.raw_data)
            if blksect.size % 4 > 0:
                padding_len = 4 - (blksect.size % 4)
                fh.write((b'\0' * padding_len))
            sect_starts.append(section.start)

        return sect_starts

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        """ Export one section into XML tree

        This should be overloaded by specific blocks implementation to store data
        in a parsed form, instead of the raw binary which the base function stores.
        """
        block_fname = "{:s}.{:s}".format(fname_base,"bin")
        bldata = self.getData(section_num=snum)
        with open(block_fname, "wb") as block_fd:
            block_fd.write(bldata.read())

        section_elem.set("Format", "bin")
        section_elem.set("File", os.path.basename(block_fname))

    def exportXMLTree(self, simple_bin=False):
        """ Export the file data into XML tree
        """
        pretty_ident = getPrettyStrFromRsrcType(self.ident)
        block_fpath = os.path.dirname(self.po.xml)

        elem = ET.Element(pretty_ident)
        if len(self.full_name) > 0:
            comment_elem = ET.Comment(self.full_name)
            comment_elem.tail = "\n"
            elem.append(comment_elem)
        else:
            elem.text = "\n"
        elem.tail = "\n"
        for snum, section in self.sections.items():
            section_elem = ET.SubElement(elem,"Section")
            section_elem.tail = "\n"
            section_elem.set("Index", str(snum))

            if self.vi.ftype == FILE_FMT_TYPE.LLB:
                block_int5 = section.start.int5
            else:
                block_int5 = None

            if section.name_text is not None:
                section_elem.set("Name", section.name_text.decode(self.vi.textEncoding))
            if block_int5 is not None:
                section_elem.set("Int5", "0x{:08X}".format(block_int5))

            # Prepare a base for file names of any files created by the export
            if len(self.sections) == 1:
                fname_base = "{:s}_{:s}".format(self.po.filebase, pretty_ident)
            else:
                if snum >= 0:
                    snum_str = str(snum)
                else:
                    snum_str = 'm' + str(-snum)
                fname_base = "{:s}_{:s}{:s}".format(self.po.filebase, pretty_ident, snum_str)
            if len(block_fpath) > 0:
                fname_base = block_fpath + '/' + fname_base

            if not simple_bin:
                # The rest of the data may be set by a block-specific (overloaded) method
                self.exportXMLSection(section_elem, snum, section, fname_base)
            else:
                # Call base function, not the overloaded version for specific block
                Block.exportXMLSection(self, section_elem, snum, section, fname_base)

        return elem

    def defaultSectionNumber(self):
        """ Gives section index of a default section.

        Default section is the one with lowest index (its absolute value).
        That section is set as active, and its data is used to set properties
        of this block.
        """
        return min(self.sections.keys(), key=abs)

    def __repr__(self):
        bldata = self.getData()
        if self.size > 32:
            d = bldata.read(31).hex() + ".."
        else:
            d = bldata.read(32).hex()
        return "<" + self.__class__.__name__ + "(" + d + ")>"


class SingleIntBlock(Block):
    """ Block with raw data representing single integer value

    To be used as parser for several blocks.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.value = None
        self.byteorder = 'big'
        self.size = 4
        self.base = 10
        self.signed = False

    def parseRSRCData(self, section_num, bldata):
        self.value = int.from_bytes(bldata.read(self.size), byteorder=self.byteorder, signed=self.signed)

    def updateSectionData(self, section_num=None, avoid_recompute=False):
        if section_num is None:
            section_num = self.section_loaded

        data_buf = int(self.value).to_bytes(self.size, byteorder=self.byteorder)

        if (len(data_buf) != self.size) and not avoid_recompute:
            raise RuntimeError("Block {} section {} generated binary data of invalid size"\
              .format(self.ident,section_num))

        self.setData(data_buf, section_num=section_num)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)

    def initWithXMLSection(self, section, section_elem):
        snum = section.start.section_idx
        fmt = section_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For Block {} section {:d}, reading inline XML data"\
                  .format(self.vi.src_fname,self.ident,snum))
            self.value = int(section_elem.get("Value"), 0)

            self.updateSectionData(section_num=snum,avoid_recompute=True)
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        self.parseData(section_num=snum)

        if self.base == 16:
            section_elem.set("Value", "0x{:x}".format(self.value))
        else:
            section_elem.set("Value", "{:d}".format(self.value))

        section_elem.set("Format", "inline")

    def getValue(self):
        self.parseData()
        return self.value


class MUID(SingleIntBlock):
    def __init__(self, *args):
        super().__init__(*args)
        self.byteorder = 'big'
        self.size = 4
        self.base = 10
        self.signed = False


class FPSE(SingleIntBlock):
    """ Front Panel SE
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.byteorder = 'big'
        self.size = 4
        self.base = 10
        self.signed = False


class FPTD(SingleIntBlock):
    """ Front Panel TD
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.byteorder = 'big'
        self.size = 2
        self.base = 10
        self.signed = False


class BDSE(SingleIntBlock):
    """ Block Diagram SE
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.byteorder = 'big'
        self.size = 4
        self.base = 10
        self.signed = False


class CONP(SingleIntBlock):
    """ Connector type map
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.byteorder = 'big'
        self.size = 2
        self.base = 10
        self.signed = False


class CPC2(SingleIntBlock):
    def __init__(self, *args):
        super().__init__(*args)
        self.byteorder = 'big'
        self.size = 2
        self.base = 10
        self.signed = False


class FLAG(SingleIntBlock):
    def __init__(self, *args):
        super().__init__(*args)
        self.byteorder = 'big'
        self.size = 1
        self.base = 16
        self.signed = False


class SingleStringBlock(Block):
    """ Block with raw data representing single string value

    To be used as parser for several blocks.
    """
    def __init__(self, *args):
        super().__init__(*args)
        # Amount of bytes the size of this string uses
        self.size_len = 1
        self.content = []
        self.eoln = '\r\n'

    def parseRSRCData(self, section_num, bldata):
        string_len = int.from_bytes(bldata.read(self.size_len), byteorder='big', signed=False)
        content = bldata.read(string_len)
        # Need to divide decoded string, as single \n or \r may be there only due to the endoding
        # Also, ignore encoding errors - some strings are encoded with exotic code pages, as they
        # just use native code page of the operating system (which in case of Windows, varies).
        content_str = content.decode(self.vi.textEncoding, errors="ignore")
        # Somehow, these strings can contain various EOLN chars, even if \r\n is the most often used one
        # To avoid creating different files from XML, we have to detect the proper EOLN to use
        if content_str.count('\r\n') > content_str.count('\n\r'):
            self.eoln = '\r\n'
        elif content_str.count('\n\r') > 0:
            self.eoln = '\n\r'
        elif content_str.count('\n') > content_str.count('\r'):
            self.eoln = '\n'
        elif content_str.count('\r') > 0:
            self.eoln = '\r'
        else:
            # Set the most often used one as default
            self.eoln = '\r\n'

        self.content = [s.encode(self.vi.textEncoding) for s in content_str.split(self.eoln)]

    def updateSectionData(self, section_num=None, avoid_recompute=False):
        if section_num is None:
            section_num = self.section_loaded

        # There is no need to decode while joining
        content_bytes = self.eoln.encode(self.vi.textEncoding).join(self.content)
        data_buf = int(len(content_bytes)).to_bytes(self.size_len, byteorder='big')
        data_buf += content_bytes

        expect_str_len = sum(len(line) for line in self.content)
        expect_eoln_len = len(self.eoln) * max(len(self.content)-1,0)
        if (len(data_buf) != self.size_len+expect_str_len+expect_eoln_len) and not avoid_recompute:
            raise RuntimeError("Block {} section {} generated binary data of invalid size"\
              .format(self.ident,section_num))

        self.setData(data_buf, section_num=section_num)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)

    def initWithXMLSection(self, section, section_elem):
        snum = section.start.section_idx
        fmt = section_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For Block {} section {:d}, reading inline XML data"\
                  .format(self.vi.src_fname,self.ident,snum))
            self.eoln = section_elem.get("EOLN").replace("CR",'\r').replace("LF",'\n')
            self.content = []

            for i, subelem in enumerate(section_elem):
                if (subelem.tag == "String"):
                    if subelem.text is not None:
                        self.content.append(subelem.text.encode(self.vi.textEncoding))
                    else:
                        self.content.append(b'')
                else:
                    raise AttributeError("Section contains unexpected tag")

            self.updateSectionData(section_num=snum,avoid_recompute=True)
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        self.parseData(section_num=snum)

        section_elem.text = "\n"

        # Store the EOLN used as an attribute
        EOLN_type = self.eoln.replace('\r',"CR").replace('\n',"LF")
        section_elem.set("EOLN", "{:s}".format(EOLN_type))

        for line in self.content:
            subelem = ET.SubElement(section_elem,"String")
            subelem.tail = "\n"

            pretty_string = line.decode(self.vi.textEncoding)
            subelem.text = pretty_string

        section_elem.set("Format", "inline")

class TITL(SingleStringBlock):
    """ Title
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.size_len = 1


class STRG(SingleStringBlock):
    """ String description
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.size_len = 4


class STR(Block):
    """ Short String / Input definition?

    This block seem to have different meaning depending on the kind of RSRC file
    it is in. For LLBs, it is just a simple string, like a label. For VIs,
    it contains binary data before the string.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.text = b''

    def parseRSRCData(self, section_num, bldata):
        if self.vi.ftype == FILE_FMT_TYPE.LLB:
            string_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            self.text = bldata.read(string_len)
        else: # File format is unknown
            Block.parseRSRCData(self, section_num, bldata)

    def updateSectionData(self, section_num=None, avoid_recompute=False):
        if section_num is None:
            section_num = self.section_loaded

        data_buf = b''
        if self.vi.ftype == FILE_FMT_TYPE.LLB:
            pass # no additional data - only one string
        else:
            Block.updateSectionData(self, section_num=section_num, avoid_recompute=avoid_recompute)
            return #TODO create the proper binary data for STR in other file types

        data_buf += int(len(self.text)).to_bytes(1, byteorder='big')
        data_buf += self.text

        self.setData(data_buf, section_num=section_num)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)

    def initWithXMLSection(self, section, section_elem):
        snum = section.start.section_idx
        fmt = section_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For Block {} section {:d}, reading inline XML data"\
                  .format(self.vi.src_fname,self.ident,snum))

            self.text = section_elem.get("Text").encode(self.vi.textEncoding)

            self.updateSectionData(section_num=snum,avoid_recompute=True)
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        self.parseData(section_num=snum)

        if self.vi.ftype == FILE_FMT_TYPE.LLB:
            pass # no additional data - only one string
        else:
            Block.exportXMLSection(self, section_elem, snum, section, fname_base)
            return #TODO create the proper XML data for STR in other file types

        string_val = self.text.decode(self.vi.textEncoding)
        section_elem.set("Text", string_val)

        section_elem.set("Format", "inline")


class DFDS(Block):
    """ Default Fill of Data Space
    """
    def __init__(self, *args):
        super().__init__(*args)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)


class GCDI(Block):
    def __init__(self, *args):
        super().__init__(*args)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)


class CPMp(Block):
    def __init__(self, *args):
        super().__init__(*args)
        self.content = []
        self.field1 = 0

    def parseRSRCData(self, section_num, bldata):
        count = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        self.field1 = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        self.content = []
        for i in range(count):
            value = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            self.content.append(value)

    def updateSectionData(self, section_num=None, avoid_recompute=False):
        if section_num is None:
            section_num = self.section_loaded

        data_buf = int(len(self.content)).to_bytes(1, byteorder='big')
        data_buf += int(self.field1).to_bytes(1, byteorder='big')
        for value in self.content:
            data_buf += int(value).to_bytes(2, byteorder='big')

        if (len(data_buf) != 2+2*len(self.content)) and not avoid_recompute:
            raise RuntimeError("Block {} section {} generated binary data of invalid size"\
              .format(self.ident,section_num))

        self.setData(data_buf, section_num=section_num)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)


class TM80(Block):
    """ Data Space Type Map
    """
    pass


class LIvi(Block):
    """ Link Information of vi

    Stored dependencies between this VI and other VIs, classes and libraries.
    """
    pass


class LVIN(Block):
    """ LabView Instrument

    Instrument block from LabView 5; in later versions, called
    "old instrument", and replaced functionally by 'LVSR'.
    """
    pass


class LVSR(Block):
    """ LabView Save Record

    Structure named SAVERECORD is LV6 sources.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.version = []
        self.execFlags = 0
        self.protected = False
        self.field08 = 0
        self.field0C = 0
        self.flags10 = 0
        self.field12 = 0
        self.buttonsHidden = 0
        self.frontpFlags = 0
        self.instrState = 0
        self.execState = 0
        self.execPrio = 0
        self.viType = 0
        self.field24 = 0
        self.field28 = 0
        self.field2C = 0
        self.field30 = 0
        self.viSignature = b''
        self.field44 = 0
        self.field48 = 0
        self.field4C = 0
        self.field4E = 0
        self.field50_md5 = b''
        self.libpass_text = None
        self.libpass_md5 = b''
        self.field70 = 0
        self.field74 = 0
        self.field78_md5 = b''
        self.inlineStg = 0
        self.field8C = 0
        self.field90 = b''

    def parseRSRCData(self, section_num, bldata):
        # Size of the data seem to be 120, 136 or 137
        # Data before byte 120 does not move - so it's always safe to read
        data = LVSRData(self.po)
        if bldata.readinto(data) not in [120, 136, 137, sizeof(LVSRData)]:
            raise EOFError("Data block too short for parsing {} data.".format(self.ident))

        self.version = decodeVersion(data.version)
        self.protected = ((data.execFlags & VI_EXEC_FLAGS.LibProtected.value) != 0)
        self.execFlags = data.execFlags & (~VI_EXEC_FLAGS.LibProtected.value)
        self.field08 = int(data.field08)
        self.field0C = int(data.field0C)
        self.flags10 = int(data.flags10)
        self.field12 = int(data.field12)
        self.buttonsHidden = int(data.buttonsHidden)
        self.frontpFlags = int(data.frontpFlags)
        self.instrState = int(data.instrState)
        self.execState = int(data.execState)
        self.execPrio = int(data.execPrio)
        self.viType = int(data.viType)
        self.field24 = int(data.field24)
        self.field28 = int(data.field28)
        self.field2C = int(data.field2C)
        self.field30 = int(data.field30)
        self.viSignature = bytes(data.viSignature)
        self.field44 = int(data.field44)
        self.field48 = int(data.field48)
        self.field4C = int(data.field4C)
        self.field4E = int(data.field4E)
        self.field50_md5 = bytes(data.field50_md5)
        self.libpass_md5 = bytes(data.libpass_md5)
        self.libpass_text = None
        self.field70 = int(data.field70)
        self.field74 = int(data.field74)
        # Additional data, exists only in newer versions
        # sizeof(LVSR) per version: 8.6b7->120 9.0b25->120 9.0->120 10.0b84->120 10.0->136 11.0.1->136 12.0->136 13.0->136 14.0->137

        if isGreaterOrEqVersion(self.version, 10, 0, stage='release'):
            self.field78_md5 = bytes(data.field78_md5)
        if isGreaterOrEqVersion(self.version, 14):
            self.inlineStg = int(data.inlineStg)
        if isGreaterOrEqVersion(self.version, 15):
            self.field8C = int(data.field8C)
        # Any data added in future versions
        self.field90 = bldata.read()

    def updateSectionData(self, section_num=None, avoid_recompute=False):
        if section_num is None:
            section_num = self.section_loaded

        data_buf = int(encodeVersion(self.version)).to_bytes(4, byteorder='big')
        data_execFlags = (self.execFlags & (~VI_EXEC_FLAGS.LibProtected.value)) | \
          (VI_EXEC_FLAGS.LibProtected.value if self.protected else 0)
        data_buf += int(data_execFlags).to_bytes(4, byteorder='big')
        data_buf += int(self.field08).to_bytes(4, byteorder='big')
        data_buf += int(self.field0C).to_bytes(4, byteorder='big')
        data_buf += int(self.flags10).to_bytes(2, byteorder='big')
        data_buf += int(self.field12).to_bytes(2, byteorder='big')
        data_buf += int(self.buttonsHidden).to_bytes(2, byteorder='big')
        data_buf += int(self.frontpFlags).to_bytes(2, byteorder='big')
        data_buf += int(self.instrState).to_bytes(4, byteorder='big')
        data_buf += int(self.execState).to_bytes(4, byteorder='big')
        data_buf += int(self.execPrio).to_bytes(2, byteorder='big')
        data_buf += int(self.viType).to_bytes(2, byteorder='big')
        data_buf += int(self.field24).to_bytes(4, byteorder='big', signed=True)
        data_buf += int(self.field28).to_bytes(4, byteorder='big')
        data_buf += int(self.field2C).to_bytes(4, byteorder='big')
        data_buf += int(self.field30).to_bytes(4, byteorder='big')
        data_buf += self.viSignature
        data_buf += int(self.field44).to_bytes(4, byteorder='big')
        data_buf += int(self.field48).to_bytes(4, byteorder='big')
        data_buf += int(self.field4C).to_bytes(2, byteorder='big')
        data_buf += int(self.field4E).to_bytes(2, byteorder='big')
        data_buf += self.field50_md5
        if self.libpass_text is not None:
            pass #TODO re-compute md5 from pass
        data_buf += self.libpass_md5
        data_buf += int(self.field70).to_bytes(4, byteorder='big')
        data_buf += int(self.field74).to_bytes(4, byteorder='big', signed=True)
        if isGreaterOrEqVersion(self.version, 10, 0, stage='release'):
            data_buf += self.field78_md5
        if isGreaterOrEqVersion(self.version, 14):
            data_buf += int(self.inlineStg).to_bytes(1, byteorder='big')
        if isGreaterOrEqVersion(self.version, 15):
            data_buf += b'\0' * 3
            data_buf += int(self.field8C).to_bytes(4, byteorder='big')
        data_buf += self.field90

        if len(data_buf) not in [120, 136, 137, sizeof(LVSRData)+len(self.field90)] and not avoid_recompute:
            raise RuntimeError("Block {} section {} generated binary data of invalid size"
              .format(self.ident,section_num))

        self.setData(data_buf, section_num=section_num)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)

    def initWithXMLSection(self, section, section_elem):
        snum = section.start.section_idx
        fmt = section_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For Block {} section {:d}, reading inline XML data"\
                  .format(self.vi.src_fname,self.ident,snum))
            self.field90 = b''

            # We really expect only one of each sub-elements
            for i, subelem in enumerate(section_elem):
                if (subelem.tag == "Version"):
                    ver = {}
                    ver['major'] = int(subelem.get("Major"), 0)
                    ver['minor'] = int(subelem.get("Minor"), 0)
                    ver['bugfix'] = int(subelem.get("Bugfix"), 0)
                    ver['stage_text'] = subelem.get("Stage")
                    ver['build'] = int(subelem.get("Build"), 0)
                    ver['flags'] = int(subelem.get("Flags"), 0)
                    self.version = ver
                elif (subelem.tag == "Library"):
                    self.protected = int(subelem.get("Protected"), 0)
                    password_text = subelem.get("Password")
                    password_hash = subelem.get("PasswordHash")
                    if password_text is not None:
                        password_bin = password_text.encode(self.vi.textEncoding)
                        self.libpass_text = password_text
                        self.libpass_md5 = md5(password_bin).digest()
                    else:
                        self.libpass_md5 = bytes.fromhex(password_hash)
                    pass
                elif (subelem.tag == "Execution"):
                    self.execState = int(subelem.get("State"), 0)
                    self.execPrio = int(subelem.get("Priority"), 0)
                    self.execFlags = importXMLBitfields(VI_EXEC_FLAGS, subelem)
                elif (subelem.tag == "ButtonsHidden"):
                    self.buttonsHidden = importXMLBitfields(VI_BTN_HIDE_FLAGS, subelem)
                elif (subelem.tag == "Instrument"):
                    self.viType = valFromEnumOrIntString(VI_TYPE, subelem.get("Type"))
                    tmphash = subelem.get("Signature")
                    self.viSignature = bytes.fromhex(tmphash)
                    self.instrState = importXMLBitfields(VI_IN_ST_FLAGS, subelem)
                elif (subelem.tag == "FrontPanel"):
                    self.frontpFlags = importXMLBitfields(VI_FP_FLAGS, subelem)
                elif (subelem.tag == "Unknown"):
                    self.field08 = int(subelem.get("Field08"), 0)
                    self.field0C = int(subelem.get("Field0C"), 0)
                    self.flags10 = int(subelem.get("Flags10"), 0)
                    self.field12 = int(subelem.get("Field12"), 0)
                    self.field24 = int(subelem.get("Field24"), 0)
                    self.field28 = int(subelem.get("Field28"), 0)
                    self.field2C = int(subelem.get("Field2C"), 0)
                    self.field30 = int(subelem.get("Field30"), 0)
                    self.field44 = int(subelem.get("Field44"), 0)
                    self.field48 = int(subelem.get("Field48"), 0)
                    self.field4C = int(subelem.get("Field4C"), 0)
                    self.field4E = int(subelem.get("Field4E"), 0)
                    field50_hash = subelem.get("Field50Hash")
                    self.field50_md5 = bytes.fromhex(field50_hash)
                    self.field70 = int(subelem.get("Field70"), 0)
                    self.field74 = int(subelem.get("Field74"), 0)
                    # Additional data, exists only in some versions
                    field78_hash = subelem.get("Field78Hash")
                    if field78_hash is not None:
                        self.field78_md5 = bytes.fromhex(field78_hash)
                    inlineStg = subelem.get("InlineStg")
                    if inlineStg is not None:
                        self.inlineStg = int(inlineStg, 0)
                    field8C = subelem.get("Field8C")
                    if field8C is not None:
                        self.field8C = int(field8C, 0)

                elif (subelem.tag == "Field90"):
                    bin_path = os.path.dirname(self.vi.src_fname)
                    if len(bin_path) > 0:
                        bin_fname = bin_path + '/' + subelem.get("File")
                    else:
                        bin_fname = subelem.get("File")
                    with open(bin_fname, "rb") as part_fh:
                        self.field90 = part_fh.read()
                else:
                    raise AttributeError("Section contains unexpected tag")

            self.updateSectionData(section_num=snum,avoid_recompute=True)
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        self.parseData(section_num=snum)

        section_elem.text = "\n"
        subelem = ET.SubElement(section_elem,"Version")
        subelem.tail = "\n"
        subelem.set("Major", "{:d}".format(self.version['major']))
        subelem.set("Minor", "{:d}".format(self.version['minor']))
        subelem.set("Bugfix", "{:d}".format(self.version['bugfix']))
        subelem.set("Stage", "{:s}".format(self.version['stage_text']))
        subelem.set("Build", "{:d}".format(self.version['build']))
        subelem.set("Flags", "0x{:X}".format(self.version['flags']))

        subelem = ET.SubElement(section_elem,"Library")
        subelem.tail = "\n"
        subelem.set("Protected", "{:d}".format(self.protected))
        subelem.set("PasswordHash", self.libpass_md5.hex())
        subelem.set("HashType", "MD5")

        subelem = ET.SubElement(section_elem,"Execution")
        subelem.tail = "\n"
        subelem.set("State", "{:d}".format(self.execState))
        subelem.set("Priority", "{:d}".format(self.execPrio))
        exportXMLBitfields(VI_EXEC_FLAGS, subelem, self.execFlags, \
          skip_mask=VI_EXEC_FLAGS.LibProtected.value)

        subelem = ET.SubElement(section_elem,"ButtonsHidden")
        subelem.tail = "\n"
        exportXMLBitfields(VI_BTN_HIDE_FLAGS, subelem, self.buttonsHidden)

        subelem = ET.SubElement(section_elem,"Instrument")
        subelem.tail = "\n"
        subelem.set("Type", "{:s}".format(stringFromValEnumOrInt(VI_TYPE, self.viType)))
        subelem.set("Signature", self.viSignature.hex())
        exportXMLBitfields(VI_IN_ST_FLAGS, subelem, self.instrState)

        subelem = ET.SubElement(section_elem,"FrontPanel")
        subelem.tail = "\n"
        exportXMLBitfields(VI_FP_FLAGS, subelem, self.frontpFlags)

        subelem = ET.SubElement(section_elem,"Unknown")
        subelem.tail = "\n"

        subelem.set("Field08", "{:d}".format(self.field08))
        subelem.set("Field0C", "{:d}".format(self.field0C))
        subelem.set("Flags10", "{:d}".format(self.flags10))
        subelem.set("Field12", "{:d}".format(self.field12))
        subelem.set("Field24", "{:d}".format(self.field24))
        subelem.set("Field28", "{:d}".format(self.field28))
        subelem.set("Field2C", "{:d}".format(self.field2C))
        subelem.set("Field30", "{:d}".format(self.field30))
        subelem.set("Field44", "{:d}".format(self.field44))
        subelem.set("Field48", "{:d}".format(self.field48))
        subelem.set("Field4C", "{:d}".format(self.field4C))
        subelem.set("Field4E", "{:d}".format(self.field4E))
        subelem.set("Field50Hash", self.field50_md5.hex())
        subelem.set("Field70", "{:d}".format(self.field70))
        subelem.set("Field74", "{:d}".format(self.field74))
        # Additional data, exists only in some versions
        subelem.set("Field78Hash", self.field78_md5.hex())
        # Additional data, exists only in some versions
        subelem.set("InlineStg", "{:d}".format(self.inlineStg))
        subelem.set("Field8C", "{:d}".format(self.field8C))

        if len(self.field90) > 0:
            subelem = ET.SubElement(section_elem,"Field90")
            subelem.tail = "\n"

            part_fname = "{:s}_{:s}.{:s}".format(fname_base,subelem.tag,"bin")
            with open(part_fname, "wb") as part_fd:
                part_fd.write(self.field90)
            subelem.set("Format", "bin")
            subelem.set("File", os.path.basename(part_fname))

        section_elem.set("Format", "inline")

    def getVersion(self):
        self.parseData()
        return self.version


class vers(Block):
    """ Version block
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.version = []
        self.version_text = b''
        self.version_info = b''

    def parseRSRCData(self, section_num, bldata):
        self.version = decodeVersion(int.from_bytes(bldata.read(4), byteorder='big', signed=False))
        version_text_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        self.version_text = bldata.read(version_text_len)
        # TODO Is the string null-terminated? or that's length of another string?
        version_unk_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        if version_unk_len != 0:
            raise AttributeError("Always zero value 1 is not zero")
        version_info_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        self.version_info = bldata.read(version_info_len)
        # TODO Is the string null-terminated? or that's length of another string?
        version_unk_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        if version_unk_len != 0:
            raise AttributeError("Always zero value 2 is not zero")

    def updateSectionData(self, section_num=None, avoid_recompute=False):
        if section_num is None:
            section_num = self.section_loaded

        data_buf = int(encodeVersion(self.version)).to_bytes(4, byteorder='big')
        data_buf += int(len(self.version_text)).to_bytes(1, byteorder='big')
        data_buf += self.version_text + b'\0'
        data_buf += int(len(self.version_info)).to_bytes(1, byteorder='big')
        data_buf += self.version_info + b'\0'

        if (len(data_buf) != 4 + 2+len(self.version_text) + 2+len(self.version_info)) and not avoid_recompute:
            raise RuntimeError("Block {} section {} generated binary data of invalid size"\
              .format(self.ident,section_num))

        self.setData(data_buf, section_num=section_num)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)

    def initWithXMLSection(self, section, section_elem):
        snum = section.start.section_idx
        fmt = section_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For Block {} section {:d}, reading inline XML data"\
                  .format(self.vi.src_fname,self.ident,snum))

            # We really expect only one "Password" sub-element
            for i, subelem in enumerate(section_elem):
                if (subelem.tag != "Version"):
                    raise AttributeError("Section contains something else than 'Version'")

                ver = {}
                ver['major'] = int(subelem.get("Major"), 0)
                ver['minor'] = int(subelem.get("Minor"), 0)
                ver['bugfix'] = int(subelem.get("Bugfix"), 0)
                ver['stage_text'] = subelem.get("Stage")
                ver['build'] = int(subelem.get("Build"), 0)
                ver['flags'] = int(subelem.get("Flags"), 0)
                self.version_text = subelem.get("Text").encode(self.vi.textEncoding)
                self.version_info = subelem.get("Info").encode(self.vi.textEncoding)
                self.version = ver

            self.updateSectionData(section_num=snum,avoid_recompute=True)
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        self.parseData(section_num=snum)

        section_elem.text = "\n"
        subelem = ET.SubElement(section_elem,"Version")
        subelem.tail = "\n"

        subelem.set("Major", "{:d}".format(self.version['major']))
        subelem.set("Minor", "{:d}".format(self.version['minor']))
        subelem.set("Bugfix", "{:d}".format(self.version['bugfix']))
        subelem.set("Stage", "{:s}".format(self.version['stage_text']))
        subelem.set("Build", "{:d}".format(self.version['build']))
        subelem.set("Flags", "0x{:X}".format(self.version['flags']))
        subelem.set("Text", "{:s}".format(self.version_text.decode(self.vi.textEncoding)))
        subelem.set("Info", "{:s}".format(self.version_info.decode(self.vi.textEncoding)))

        section_elem.set("Format", "inline")

    def getVersion(self):
        self.parseData()
        return self.version

    def getVerText(self):
        self.parseData()
        return self.version_text

    def getVerInfo(self):
        self.parseData()
        return self.version_info


class ICON(Block):
    """ Icon 32x32 1bpp
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.width = 32
        self.height = 32
        self.bpp = 1
        self.icon = None

    def parseRSRCData(self, section_num, bldata):
        icon = Image.new("P", (self.width, self.height))
        img_palette = [ 0 ] * (3*256)
        if self.bpp == 8:
            lv_color_palette = LABVIEW_COLOR_PALETTE_256
        elif self.bpp == 4:
            lv_color_palette = LABVIEW_COLOR_PALETTE_16
        else:
            lv_color_palette = LABVIEW_COLOR_PALETTE_2
        for i, rgb in enumerate(lv_color_palette):
            img_palette[3*i+0] = (rgb >> 16) & 0xFF
            img_palette[3*i+1] = (rgb >>  8) & 0xFF
            img_palette[3*i+2] = (rgb >>  0) & 0xFF
        icon.putpalette(img_palette, rawmode='RGB')
        img_data = bldata.read(int(self.width * self.height * self.bpp / 8))
        if self.bpp == 8:
            pass
        elif self.bpp == 4:
            img_data8 = bytearray(self.width * self.height)
            for i, px in enumerate(img_data):
                img_data8[2*i+0] = (px >> 4) & 0xF
                img_data8[2*i+1] = (px >> 0) & 0xF
            img_data = img_data8
        elif self.bpp == 1:
            img_data8 = bytearray(self.width * self.height)
            for i, px in enumerate(img_data):
                img_data8[8*i+0] = (px >> 7) & 0x1
                img_data8[8*i+1] = (px >> 6) & 0x1
                img_data8[8*i+2] = (px >> 5) & 0x1
                img_data8[8*i+3] = (px >> 4) & 0x1
                img_data8[8*i+4] = (px >> 3) & 0x1
                img_data8[8*i+5] = (px >> 2) & 0x1
                img_data8[8*i+6] = (px >> 1) & 0x1
                img_data8[8*i+7] = (px >> 0) & 0x1
            img_data = img_data8
        else:
            raise ValueError("Unsupported icon BPP")

        icon.putdata(img_data)
        # Pixel-by-pixel method, for reference (slower than all-at-once)
        #for y in range(0, self.height):
        #    for x in range(0, self.width):
        #        icon.putpixel((x, y), bldata.read(1))
        self.icon = icon

    def updateSectionData(self, section_num=None, avoid_recompute=False):
        if section_num is None:
            section_num = self.section_loaded

        data_buf = bytes(self.icon.getdata())
        data_len = (self.width * self.height * self.bpp) // 8

        if self.bpp == 8:
            pass
        elif self.bpp == 4:
            data_buf8 = bytearray(data_len)
            for i in range(data_len):
                data_buf8[i] = (data_buf[2*i+0] << 4) | (data_buf[2*i+1] << 0)
            data_buf = data_buf8
        elif self.bpp == 1:
            data_buf8 = bytearray(data_len)
            for i in range(data_len):
                data_buf8[i] = (data_buf[8*i+0] << 7) | (data_buf[8*i+1] << 6) | \
                    (data_buf[8*i+2] << 5) | (data_buf[8*i+3] << 4) | \
                    (data_buf[8*i+4] << 3) | (data_buf[8*i+5] << 2) | \
                    (data_buf[8*i+6] << 1) | (data_buf[8*i+7] << 0)
            data_buf = data_buf8
        else:
            raise ValueError("Unsupported icon BPP")

        if len(data_buf) < data_len:
            data_buf += b'\0' * (data_len - len(data_buf))
        self.setData(data_buf, section_num=section_num)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)

    def loadIcon(self):
        self.parseData()
        return self.icon

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        block_fname = "{:s}.{:s}".format(fname_base,"png")

        self.parseData(section_num=snum)
        with open(block_fname, "wb") as block_fd:
            self.icon.save(block_fd, format="PNG")

        section_elem.set("Format", "png")
        section_elem.set("File", os.path.basename(block_fname))

    def initWithXMLSection(self, section, section_elem):
        snum = section.start.section_idx
        fmt = section_elem.get("Format")
        if fmt == "png": # Format="png" - the content is stored separately as image file
            if (self.po.verbose > 2):
                print("{:s}: For Block {} section {:d}, reading PNG file '{}'"\
                  .format(self.vi.src_fname,self.ident,snum,section_elem.get("File")))
            bin_path = os.path.dirname(self.vi.src_fname)
            if len(bin_path) > 0:
                bin_fname = bin_path + '/' + section_elem.get("File")
            else:
                bin_fname = section_elem.get("File")
            with open(bin_fname, "rb") as png_fh:
                icon = Image.open(png_fh)
                self.icon = icon
                icon.getdata() # to make sure the file gets loaded
            self.updateSectionData(section_num=snum,avoid_recompute=True)
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass


class icl8(ICON):
    """ Icon Large 32x32 8bpp
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.width = 32
        self.height = 32
        self.bpp = 8


class icl4(ICON):
    """ Icon Large 32x32 4bpp
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.width = 32
        self.height = 32
        self.bpp = 4


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

    def createSection(self):
        section = Section(self.vi, self.po)
        # In this block, sections have some additional properties besides the raw data
        section.password = None
        section.salt_iface_idx = None
        section.salt = None
        return section

    def parseRSRCData(self, section_num, bldata):
        self.password_md5 = bldata.read(16)
        self.hash_1 = bldata.read(16)
        self.hash_2 = bldata.read(16)

        # In this block, sections have some additional properties besides the raw data
        section = self.sections[section_num]
        self.password = section.password
        self.salt_iface_idx = section.salt_iface_idx
        self.salt = section.salt

    def updateSectionData(self, section_num=None, avoid_recompute=False):
        if section_num is None:
            section_num = self.section_loaded

        if not avoid_recompute:
            self.recalculateHash1()
            self.recalculateHash2()

        data_buf = self.password_md5
        data_buf += self.hash_1
        data_buf += self.hash_2

        if (len(data_buf) != 48) and not avoid_recompute:
            raise RuntimeError("Block {} section {} generated binary data of invalid size"\
              .format(self.ident,section_num))

        self.setData(data_buf, section_num=section_num)

        # In this block, sections have some additional properties besides the raw data
        section = self.sections[section_num]
        section.password = self.password
        section.salt_iface_idx = self.salt_iface_idx
        section.salt = self.salt

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        self.parseData(section_num=snum)
        self.recalculateHash1(store=False) # this is needed to find salt
        self.recognizePassword()

        section_elem.text = "\n"
        subelem = ET.SubElement(section_elem,"Password")
        subelem.tail = "\n"

        if self.password is not None:
            subelem.set("Text", self.password)
        else:
            subelem.set("Hash", self.password_md5.hex())
            subelem.set("HashType", "MD5")
        if self.salt_iface_idx is not None:
            subelem.set("SaltSource", str(self.salt_iface_idx))
        else:
            subelem.set("SaltData", self.salt.hex())

        section_elem.set("Format", "inline")

    def initWithXMLSection(self, section, section_elem):
        snum = section.start.section_idx
        fmt = section_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For Block {} section {:d}, reading inline XML data"\
                  .format(self.vi.src_fname,self.ident,snum))
            # We really expect only one "Password" sub-element
            for i, subelem in enumerate(section_elem):
                if (subelem.tag != "Password"):
                    raise AttributeError("Section contains something else than 'Password'")

                pass_text = subelem.get("Text")
                pass_hash = subelem.get("Hash")
                if pass_text is not None:
                    self.setPassword(password_text=pass_text)
                else:
                    self.setPassword(password_md5=bytes.fromhex(pass_hash))

                salt_iface_idx = subelem.get("SaltSource")
                salt_data = subelem.get("SaltData")
                if salt_iface_idx is not None:
                    self.salt_iface_idx = int(salt_iface_idx, 0)
                else:
                    self.salt = bytes.fromhex(salt_data)
            self.updateSectionData(section_num=snum,avoid_recompute=True)
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)

    @staticmethod
    def getPasswordSaltFromTerminalCounts(numberCount, stringCount, pathCount):
        salt = int(numberCount).to_bytes(4, byteorder='little')
        salt += int(stringCount).to_bytes(4, byteorder='little')
        salt += int(pathCount).to_bytes(4, byteorder='little')
        return salt

    def scanForHashSalt(self, presalt_data=b'', postsalt_data=b''):
        salt = b''
        ver = self.vi.getFileVersion()
        if not isGreaterOrEqVersion(ver, major=1):
            if (po.verbose > 0):
                eprint("{:s}: Warning: No version block found; assuming oldest format, with empty password salt".format(self.vi.src_fname))
            self.salt = salt
            return salt
        if isGreaterOrEqVersion(ver, major=12):
            # Figure out the salt
            salt_iface_idx = None
            VCTP = self.vi.get_or_raise('VCTP')
            interfaceEnumerate = self.vi.connectorEnumerate(fullType=CONNECTOR_FULL_TYPE.Function)
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
            VCTP_content = VCTP.getContent()
            term_connectors = VCTP.getClientConnectorsByType(VCTP_content[self.salt_iface_idx])
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
            newPassBin = password_text.encode(self.vi.textEncoding)
            password_md5 = md5(newPassBin).digest()
        else:
            if store:
                self.password = None
        if password_md5 is None:
            raise ValueError("Requested to set password, but no new password provided in text nor md5 form")
        if store:
            self.password_md5 = password_md5
        return password_md5


    def recognizePassword(self, password_md5=None, store=True):
        """ Gets password from MD5 hash, if the password is a common one
        """
        if password_md5 is None:
            password_md5 = self.password_md5
        found_pass = None
        for test_pass in ['', 'qwerty', 'password', '111111', '12345678', 'abc123', '1234567', 'password1', '12345', '123']:
            test_pass_bin = test_pass.encode(self.vi.textEncoding)
            test_md5 = md5(test_pass_bin).digest()
            if password_md5 == test_md5:
                found_pass = test_pass
                break
        if (store):
            self.password = found_pass
        return found_pass


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
        if LIBN is not None:
            LIBN_content = b':'.join(LIBN.getContent())
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
        self.content = None

    def parseRSRCData(self, section_num, bldata):
        count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.content = []
        for i in range(count):
            content_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            self.content.append(bldata.read(content_len))

    def updateSectionData(self, section_num=None, avoid_recompute=False):
        if section_num is None:
            section_num = self.section_loaded

        data_buf = int(len(self.content)).to_bytes(4, byteorder='big')
        for name in self.content:
            data_buf += int(len(name)).to_bytes(1, byteorder='big')
            data_buf += name

        if (len(data_buf) < 5) and not avoid_recompute:
            raise RuntimeError("Block {} section {} generated binary data of invalid size"\
              .format(self.ident,section_num))

        self.setData(data_buf, section_num=section_num)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)

    def initWithXMLSection(self, section, section_elem):
        snum = section.start.section_idx
        fmt = section_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For Block {} section {:d}, reading inline XML data"\
                  .format(self.vi.src_fname,self.ident,snum))
            self.content = []
            # There can be multiple "Library" sub-elements
            for i, subelem in enumerate(section_elem):
                if (subelem.tag != "Library"):
                    raise AttributeError("Section contains something else than 'Library'")

                name_text = subelem.get("Name")
                self.content.append(name_text.encode(self.vi.textEncoding))

            self.updateSectionData(section_num=snum,avoid_recompute=True)
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        self.parseData(section_num=snum)

        section_elem.text = "\n"
        for name in self.content:
            subelem = ET.SubElement(section_elem,"Library")
            subelem.tail = "\n"
            subelem.set("Name", name.decode(self.vi.textEncoding))

        section_elem.set("Format", "inline")

    def getContent(self):
        self.parseData()
        return self.content


class LVzp(Block):
    """ LabView Zipped Program tree

    Used in llb-like objects created by building the project.
    Contains the whole VIs hierarchy, stored within ZIP file.

    In LV from circa 2009 and before, the ZIP was stored in plain form.
    In newer LV versions, it is encrypted by simple xor-based algorithm.
    """
    def __init__(self, *args):
        super().__init__(*args)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.XOR):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.XOR):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)


class BDHP(Block):
    """ Block Diagram Heap

    This block is spcific to LV 7beta and older.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.content = None

    def parseRSRCData(self, section_num, bldata):
        content_len = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.content = bldata.read(content_len)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)

    def getContent(self):
        self.parseData()
        return self.content

    def getContentHash(self):
        self.parseData()
        return md5(self.content).digest()

class BDH(Block):
    """ Block Diagram Heap

    Stored in "BDHx"-block. It uses a binary tree format to store hierarchy
    structures. They use a kind of "xml-tags" to open and close objects.
    This block is specific to LV 7 and newer.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.content = None

    def parseRSRCData(self, section_num, bldata):
        content_len = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.content = bldata.read(content_len)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)

    def getContent(self):
        self.parseData()
        return self.content

    def getContentHash(self):
        self.parseData()
        return md5(self.content).digest()

BDHc = BDHb = BDH


class FPH(Block):
    """ Front Panel Heap

    Stored in "FPHx"-block.
    This implementation is for LV 7 and newer.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.content = None

    def parseRSRCData(self, section_num, bldata):
        content_len = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.content = bldata.read(content_len)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)

    def getContent(self):
        self.parseData()
        return self.content

FPHc = FPHb = FPH


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
        self.content = []
        self.unflatten = []

    def parseRSRCConnector(self, bldata, pos):
        bldata.seek(pos)
        obj_type, obj_flags, obj_len = ConnectorObject.parseRSRCDataHeader(bldata)
        if (self.po.verbose > 2):
            print("{:s}: Block {} connector {:d}, at 0x{:04x}, type 0x{:02x} flags 0x{:02x} len {:d}"\
              .format(self.vi.src_fname, self.ident, len(self.content), pos, obj_type, obj_flags, obj_len))
        if obj_len < 4:
            eprint("{:s}: Warning: Connector {:d} type 0x{:02x} data size {:d} too small to be valid"\
              .format(self.vi.src_fname, len(self.content), obj_type, obj_len))
            obj_type = CONNECTOR_FULL_TYPE.Void
        obj = newConnectorObject(self.vi, len(self.content), obj_flags, obj_type, self.po)
        self.content.append(obj)
        bldata.seek(pos)
        obj.initWithRSRC(bldata, obj_len)
        return obj.index, obj_len

    def parseRSRCData(self, section_num, bldata):
        self.content = []
        # First we have count of connectors, and then the connectors themselves
        count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        pos = bldata.tell()
        for i in range(count):
            obj_idx, obj_len = self.parseRSRCConnector(bldata, pos)
            pos += obj_len
        # After that,there is a list
        self.unflatten = []
        count = readVariableSizeField(bldata)
        for i in range(count):
            val = readVariableSizeField(bldata)
            self.unflatten.append(val)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        bldata = Block.getData(self, section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        Block.setData(self, data_buf, section_num=section_num, use_coding=use_coding)

    def initWithXMLSection(self, section, section_elem):
        snum = section.start.section_idx
        fmt = section_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            self.content = []
            self.unflatten = []
            if (self.po.verbose > 2):
                print("{:s}: For Block {} section {:d}, reading inline XML data"\
                  .format(self.vi.src_fname,self.ident,snum))
            for subelem in section_elem:
                if (subelem.tag == "Connector"):
                    obj_idx = int(subelem.get("Index"), 0)
                    obj_type = valFromEnumOrIntString(CONNECTOR_FULL_TYPE, subelem.get("Type"))
                    obj_flags = importXMLBitfields(CONNECTOR_FLAGS, subelem)
                    obj = newConnectorObject(self.vi, obj_idx, obj_flags, obj_type, self.po)
                    # Grow the list if needed (the connectors may be in wrong order)
                    if obj_idx >= len(self.content):
                        self.content.extend([None] * (obj_idx - len(self.content) + 1))
                    self.content[obj_idx] = obj
                    # Set connector data based on XML properties
                    obj.initWithXML(subelem)
                elif (subelem.tag == "UnFlatten"):
                    self.unflatten += [int(itm,0) for itm in subelem.text.split()]
                else:
                    raise AttributeError("Section contains unexpected tag")

            self.updateSectionData(section_num=snum,avoid_recompute=True)
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass

    def updateSectionData(self, section_num=None, avoid_recompute=False):
        if section_num is None:
            section_num = self.section_loaded

        data_buf = int(len(self.content)).to_bytes(4, byteorder='big')
        for i, connobj in enumerate(self.content):
            bldata = connobj.getData()
            data_buf += bldata.read()

        data_buf += int(len(self.unflatten)).to_bytes(2, byteorder='big')
        for i, val in enumerate(self.unflatten):
            data_buf += int(val).to_bytes(2, byteorder='big')

        if (len(data_buf) < 4 + 4*len(self.content)) and not avoid_recompute:
            raise RuntimeError("Block {} section {} generated binary data of invalid size"\
              .format(self.ident,section_num))

        self.setData(data_buf, section_num=section_num)

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        self.parseData(section_num=snum)

        section_elem.text = "\n"

        for connobj in self.content:
            subelem = ET.SubElement(section_elem,"Connector")
            subelem.tail = "\n"

            subelem.set("Index", str(connobj.index))
            subelem.set("Type", "{:s}".format(stringFromValEnumOrInt(CONNECTOR_FULL_TYPE, connobj.otype)))

            if not self.po.raw_connectors:
                connobj.exportXML(subelem, fname_base)
                connobj.exportXMLFinish(subelem)
            else:
                ConnectorObject.exportXML(connobj, subelem, fname_base)
                ConnectorObject.exportXMLFinish(connobj, subelem)

        subelem = ET.SubElement(section_elem,"UnFlatten")
        subelem.tail = "\n"

        strlist = ""
        for i, val in enumerate(self.unflatten):
            if i % 16 == 0: strlist += "\n"
            strlist += " {:3d}".format(val)
        subelem.text = strlist

        section_elem.set("Format", "inline")

    def parseData(self, section_num=None):
        # Besides the normal parsing, also parse sub-objects
        Block.parseData(self, section_num=section_num)
        for connobj in self.content:
            connobj.parseData()

    def checkSanity(self):
        ret = True
        for connobj in self.content:
            if not connobj.checkSanity():
                ret = False
        for i, val in enumerate(self.unflatten):
            if val >= len(self.content):
                if (self.po.verbose > 1):
                    eprint("{:s}: Warning: Unflatten index {:d} exceeds connectors count {:d}"\
                      .format(self.vi.src_fname,i,len(self.content)))
                ret = False
        return ret

    def getContent(self):
        self.parseData()
        return self.content

    def getClientConnectorsByType(self, conn_obj):
        self.parseData() # Make sure the block is parsed
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

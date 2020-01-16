# -*- coding: utf-8 -*-

""" LabView RSRC file format blocks.

Classes for interpreting content of specific block types within RSRC files.
"""

# Copyright (C) 2013 Jessica Creighton <jcreigh@femtobit.org>
# Copyright (C) 2019 Mefistotelis <mefistotelis@gmail.com>
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

import enum
import re
import os

from PIL import Image
from hashlib import md5
from zlib import compress, decompress
from io import BytesIO
from ctypes import *

from LVmisc import *
import LVxml as ET
from LVconnector import *
from LVinstrument import *
import LVheap
import LVrsrcontainer

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
        # Whether RAW data has been updated and RSRC parsing is required to update properties
        self.raw_data_updated = False
        # Whether any properties have been updated and preparation of new RAW data is required
        self.parsed_data_updated = False
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
        # Currently active section; the block will return properties of active section
        self.active_section_num = None
        # Size of cummulative data for all sections in the block; set by getRawData()
        self.size = None
        if self.__doc__:
            self.full_name = " {:s} ".format(self.__doc__.split('\n')[0].strip())
        else:
            self.full_name = ""

    def createSection(self):
        """ Creates a new section, without adding it to block

        To be overloaded for setting any initial properties, if neccessary.
        """
        section = Section(self.vi, self.po)
        return section

    def initWithRSRCEarly(self, header):
        """ Early part of block loading from RSRC file

        At the point it is executed, other sections are inaccessible.
        After this call, active section will be set to default section.

        :param BlockHeader header: Struct with header of this block from RSRC file
        """
        self.header = header
        self.ident = bytes(header.ident)
        self.active_section_num = None

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

        self.setActiveSectionNum( self.defaultSectionNumber() )

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
        for snum, section in self.sections.items():
            if section.start.name_offset == 0xFFFFFFFF: # This value means no name
                continue
            if names_start + section.start.name_offset >= names_end:
                raise IOError("Block {} section {:d} Name position exceeds RSRC Info size.".format(self.ident,snum))
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
        self.active_section_num = None

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

            self.active_section_num = snum
            self.initWithXMLSection(section, section_elem)
            self.active_section_num = None

        self.header.count = len(self.sections) - 1

        self.setActiveSectionNum( self.defaultSectionNumber() )

        if (self.po.verbose > 2):
            print("{:s}: Block {} has {:d} sections".format(self.vi.src_fname,self.ident,len(self.sections)))

    def initWithXMLLate(self):
        """ Late part of block loading from XML file

        Can access some basic data from other blocks and sections.
        Useful only if properties needs an update after other blocks are accessible.
        """
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
        if self.po.verbose > 1:
            if (self.size is not None):
                print("{:s}: Block {} max data size set to {:d} bytes".format(self.vi.src_fname,self.ident,self.size))
            else:
                print("{:s}: Block {} max data size not deterimed".format(self.vi.src_fname,self.ident))
        return minSize

    def setSizeFromExpectedSizes(self):
        """ Set data size of this block

         Uses expected size computation from sections.
        """
        expSize = 0
        for snum, section in self.sections.items():
            sectSize += self.expectedRSRCSize(section_num=snum)
            expSize += sectSize
        self.size = expSize
        if (self.po.verbose > 1):
            print("{:s}: Block {} max data size set to {:d} bytes".format(self.vi.src_fname,self.ident,self.size))
        return minSize

    def readRawDataSections(self, section_count=None):
        """ Reads raw data of sections from input file, up to given number

        :param int section_count: Limit of section_num values; only sections
            with number lower that given section_count parameter are affected.
            If not provided, the method will only read data for default section.
            To make sure all sections are in memory and input file will no longer
            be used, use the count of 0xffffffff.
        """
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
                section.raw_data_updated = True
            # Set last size, padded to multiplicity of 4 bytes
            last_blksect_size = blksect.size
            if last_blksect_size % 4 > 0:
                last_blksect_size += 4 - (last_blksect_size % 4)

    def hasRawData(self, section_num=None):
        """ Returns whether given section has raw data set
        """
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]
        return (section.raw_data is not None)

    def getRawData(self, section_num=None):
        """ Retrieves bytes object with raw data of given section

            Reads the section from input stream if neccessary.
        """
        if section_num is None:
            section_num = self.active_section_num
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
            section_num = self.active_section_num
        # Insert empty structure if the requested section is missing
        if section_num not in self.sections:
            section = self.createSection()
            section.start.section_idx = section_num
            self.sections[section_num] = section
        # Replace the target section
        section = self.sections[section_num]
        section.raw_data = raw_data_buf
        section.raw_data_updated = True

    def getSection(self, section_num=None):
        """ Retrieves section of given number, or first one

            Does not force data read
        """
        if section_num is None:
            section_num = self.active_section_num
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
        """ Implements setting derivate block properties, from properties of a section set from XML

            Called by parseData() to set the specific section as loaded.
        """
        if section_num is None:
            section_num = self.active_section_num

        self.updateSectionData(section_num=section_num)
        pass

    def parseData(self, section_num=None):
        """ Parse data of specific section and place it as Block properties

        The given section will be set as both requested and loaded.
        """
        if section_num is None:
            section_num = self.active_section_num
        else:
            self.active_section_num = section_num

        if self.needParseData():
            if self.vi.dataSource == "rsrc" or self.hasRawData(section_num=section_num):
                bldata = self.getData(section_num=section_num)
                self.parseRSRCData(section_num, bldata)
            elif self.vi.dataSource == "xml":
                self.parseXMLData(section_num=section_num)
        pass

    def updateSectionData(self, section_num=None):
        """ Updates RAW data stored in given section to any changes in properties
        """
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        if section.raw_data is None:
            raise RuntimeError("Block {} section {} has no raw data generation method".format(self.ident,section_num))
        pass

    def updateData(self):
        """ Updates RAW data stored in the block to any changes in properties

        Updates raw data for all sections.
        """
        for section_num in self.sections:
            self.parseData(section_num=section_num)
            self.updateSectionData(section_num=section_num)
        pass

    def needParseData(self, section_num=None):
        """ Returns if a section needs its data to be parsed

            After a call to parseData(), or after filling the data manually, this should
            return True. Otherwise, False.
        """
        if section_num is None:
            section_num = self.active_section_num
        if section_num not in self.sections:
            return False
        section = self.sections[section_num]

        # if RAW data was not even loaded yet, trigger parsing as well
        if self.vi.dataSource == "rsrc" and not self.hasRawData():
            return True

        return section.raw_data_updated or section.parsed_data_updated

    def checkSanity(self):
        """ Checks whether properties of this object and all sub-object are sane

        Sane objects have values of properties within expected bounds.
        All the objects are expected to be already parsed during the call.
        """
        ret = True
        return ret

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        """ Retrieve file stream with raw data of specific section of this block

        This will return raw data buffer, uncompressed and decrypted if neccessary,
        and wrapped by BytesIO.

        :param int section_num: Section for which the raw data buffer will be returned.
            If not provided, active section will be assumed.
        """
        if section_num is None:
            section_num = self.active_section_num
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
            if ( (size > 16) and (usize < (size*5) // 10) ) or \
               ( (size > 128) and (usize < (size*9) // 10) ) or (usize > size * 1032):
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
        """ Set raw data of specific section of this block

        This will set raw data buffer, and mark the buffer as requiring parsing raw data.
        It requires the input raw data to be uncompressed and decrypted.

        :param int section_num: Section for which the raw data buffer will be set.
            If not provided, raw data for active section will be set.
        """
        if section_num is None:
            section_num = self.active_section_num

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
        """ Save raw data stored within sections to the RSRC file

        This writes the raw data buffers into file handle. All sections are written.
        If properties of any object were modified after load, then raw data must be re-created
        before this call.
        """
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
                raise IOError("BlockSectionStart data sanity check failed in block {} section {}".format(self.ident,snum))

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
        """ Export the block properties into XML tree

        All sections are exported by this method.
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

            if self.vi.ftype == LVrsrcontainer.FILE_FMT_TYPE.LLB:
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
                super().exportXMLSection(section_elem, snum, section, fname_base)

        return elem

    def defaultSectionNumber(self):
        """ Gives section index of a default section.

        Default section is the one with lowest index (its absolute value).
        That section is set as active, and its data is used to set properties
        of this block.
        """
        return min(self.sections.keys(), key=abs)

    def listSectionNumbers(self):
        """ Lists all section numbers for existing sections.
        """
        return self.sections.keys()

    def setActiveSectionNum(self, section_num):
        """ Sets the currently active section.

        The block will return properties of active section.
        """
        self.active_section_num = section_num

    def __getattr__(self, name):
        """ Access to active section properties
        """
        try:
            section_num = object.__getattribute__(self,'active_section_num')
            section = object.__getattribute__(self,'sections')[section_num]
            if hasattr(section, name):
                return getattr(section, name)
        except:
            pass
        return super().__getattr__(name)

    def __setattr__(self, name, value):
        """ Setting of active section properties
        """
        try:
            section_num = object.__getattribute__(self,'active_section_num')
            section = object.__getattribute__(self,'sections')[section_num]
            if hasattr(section, name):
                setattr(section, name, value)
                return
        except:
            pass
        super().__setattr__(name, value)

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
    def createSection(self):
        section = super().createSection()
        section.byteorder = 'big'
        section.size = 4
        section.base = 10
        section.signed = False
        section.value = None
        return section

    def parseRSRCData(self, section_num, bldata):
        section = self.sections[section_num]

        section.value = int.from_bytes(bldata.read(section.size), byteorder=section.byteorder, signed=section.signed)

    def updateSectionData(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        data_buf = int(section.value).to_bytes(section.size, byteorder=section.byteorder)

        if (len(data_buf) != section.size):
            raise RuntimeError("Block {} section {} generated binary data of invalid size"\
              .format(self.ident,section_num))

        self.setData(data_buf, section_num=section_num)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)

    def initWithXMLSection(self, section, section_elem):
        snum = section.start.section_idx
        fmt = section_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For Block {} section {:d}, reading inline XML data"\
                  .format(self.vi.src_fname,self.ident,snum))
            section.value = int(section_elem.get("Value"), 0)
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        self.parseData(section_num=snum)

        if section.base == 16:
            section_elem.set("Value", "0x{:x}".format(section.value))
        else:
            section_elem.set("Value", "{:d}".format(section.value))

        section_elem.set("Format", "inline")

    def getValue(self):
        self.parseData()
        return self.value


class MUID(SingleIntBlock):
    def createSection(self):
        section = super().createSection()
        section.byteorder = 'big'
        section.size = 4
        section.base = 10
        section.signed = False
        return section


class FPSE(SingleIntBlock):
    """ Front Panel Size Estimate
    """
    def createSection(self):
        section = super().createSection()
        section.byteorder = 'big'
        section.size = 4
        section.base = 10
        section.signed = False
        return section


class FPTD(SingleIntBlock):
    """ Front Panel TD
    """
    def createSection(self):
        section = super().createSection()
        section.byteorder = 'big'
        section.size = 2
        section.base = 10
        section.signed = False
        return section


class BDSE(SingleIntBlock):
    """ Block Diagram Size Estimate
    """
    def createSection(self):
        section = super().createSection()
        section.byteorder = 'big'
        section.size = 4
        section.base = 10
        section.signed = False
        return section


class CONP(SingleIntBlock):
    """ Connector type map
    """
    def createSection(self):
        section = super().createSection()
        section.byteorder = 'big'
        section.size = 2
        section.base = 10
        section.signed = False
        return section


class CPC2(SingleIntBlock):
    def createSection(self):
        section = super().createSection()
        section.byteorder = 'big'
        section.size = 2
        section.base = 10
        section.signed = False
        return section


class FLAG(SingleIntBlock):
    def createSection(self):
        section = super().createSection()
        section.byteorder = 'big'
        section.size = 1
        section.base = 16
        section.signed = False
        return section


class SingleStringBlock(Block):
    """ Block with raw data representing single string value

    To be used as parser for several blocks.
    """
    def createSection(self):
        section = super().createSection()
        # Amount of bytes the size of this string uses
        section.size_len = 1
        section.content = []
        section.eoln = '\r\n'
        return section

    def parseRSRCData(self, section_num, bldata):
        section = self.sections[section_num]

        string_len = int.from_bytes(bldata.read(section.size_len), byteorder='big', signed=False)
        content = bldata.read(string_len)
        # Need to divide decoded string, as single \n or \r may be there only due to the endoding
        # Also, ignore encoding errors - some strings are encoded with exotic code pages, as they
        # just use native code page of the operating system (which in case of Windows, varies).
        content_str = content.decode(self.vi.textEncoding, errors="ignore")
        # Somehow, these strings can contain various EOLN chars, even if \r\n is the most often used one
        # To avoid creating different files from XML, we have to detect the proper EOLN to use
        if content_str.count('\r\n') > content_str.count('\n\r'):
            section.eoln = '\r\n'
        elif content_str.count('\n\r') > 0:
            section.eoln = '\n\r'
        elif content_str.count('\n') > content_str.count('\r'):
            section.eoln = '\n'
        elif content_str.count('\r') > 0:
            section.eoln = '\r'
        else:
            # Set the most often used one as default
            section.eoln = '\r\n'

        section.content = [s.encode(self.vi.textEncoding) for s in content_str.split(section.eoln)]

    def updateSectionData(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        # There is no need to decode while joining
        content_bytes = section.eoln.encode(self.vi.textEncoding).join(section.content)
        data_buf = int(len(content_bytes)).to_bytes(section.size_len, byteorder='big')
        data_buf += content_bytes

        expect_str_len = sum(len(line) for line in section.content)
        expect_eoln_len = len(section.eoln) * max(len(section.content)-1,0)
        if (len(data_buf) != section.size_len+expect_str_len+expect_eoln_len):
            raise RuntimeError("Block {} section {} generated binary data of invalid size"\
              .format(self.ident,section_num))

        self.setData(data_buf, section_num=section_num)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)

    def initWithXMLSection(self, section, section_elem):
        snum = section.start.section_idx
        fmt = section_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For Block {} section {:d}, reading inline XML data"\
                  .format(self.vi.src_fname,self.ident,snum))
            section.eoln = section_elem.get("EOLN").replace("CR",'\r').replace("LF",'\n')
            section.content = []

            for i, subelem in enumerate(section_elem):
                if (subelem.tag == "String"):
                    if subelem.text is not None:
                        section.content.append(subelem.text.encode(self.vi.textEncoding))
                    else:
                        section.content.append(b'')
                else:
                    raise AttributeError("Section contains unexpected tag")
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        self.parseData(section_num=snum)

        section_elem.text = "\n"

        # Store the EOLN used as an attribute
        EOLN_type = section.eoln.replace('\r',"CR").replace('\n',"LF")
        section_elem.set("EOLN", "{:s}".format(EOLN_type))

        for line in section.content:
            subelem = ET.SubElement(section_elem,"String")
            subelem.tail = "\n"

            pretty_string = line.decode(self.vi.textEncoding)
            subelem.text = pretty_string

        section_elem.set("Format", "inline")

class TITL(SingleStringBlock):
    """ Title
    """
    def createSection(self):
        section = super().createSection()
        section.size_len = 1
        return section


class STRG(SingleStringBlock):
    """ String description
    """
    def createSection(self):
        section = super().createSection()
        section.size_len = 4
        return section


class STR(Block):
    """ Short String / Input definition?

    This block seem to have different meaning depending on the kind of RSRC file
    it is in. For LLBs, it is just a simple string, like a label. For VIs,
    it contains binary data before the string.
    """
    def createSection(self):
        section = super().createSection()
        section.text = b''
        return section

    def parseRSRCData(self, section_num, bldata):
        section = self.sections[section_num]

        if self.vi.ftype == LVrsrcontainer.FILE_FMT_TYPE.LLB:
            string_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            section.text = bldata.read(string_len)
        else: # File format is unknown
            Block.parseRSRCData(self, section_num, bldata)

    def updateSectionData(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        data_buf = b''
        if self.vi.ftype == LVrsrcontainer.FILE_FMT_TYPE.LLB:
            pass # no additional data - only one string
        else:
            Block.updateSectionData(self, section_num=section_num)
            return #TODO create the proper binary data for STR in other file types

        data_buf += int(len(section.text)).to_bytes(1, byteorder='big')
        data_buf += section.text

        self.setData(data_buf, section_num=section_num)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)

    def initWithXMLSection(self, section, section_elem):
        snum = section.start.section_idx
        fmt = section_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For Block {} section {:d}, reading inline XML data"\
                  .format(self.vi.src_fname,self.ident,snum))

            section.text = section_elem.get("Text").encode(self.vi.textEncoding)
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        self.parseData(section_num=snum)

        if self.vi.ftype == LVrsrcontainer.FILE_FMT_TYPE.LLB:
            pass # no additional data - only one string
        else:
            super().exportXMLSection(section_elem, snum, section, fname_base)
            return #TODO create the proper XML data for STR in other file types

        string_val = section.text.decode(self.vi.textEncoding)
        section_elem.set("Text", string_val)

        section_elem.set("Format", "inline")


class DFDS(Block):
    """ Default Fill of Data Space
    """
    def createSection(self):
        section = super().createSection()
        return section

    def getData(self, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)


class GCDI(Block):
    def createSection(self):
        section = super().createSection()
        return section

    def getData(self, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)


class CPMp(Block):
    """ Connection Points Map
    """
    def createSection(self):
        section = super().createSection()
        section.content = []
        section.field1 = 0
        return section

    def parseRSRCData(self, section_num, bldata):
        section = self.sections[section_num]

        count = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        section.field1 = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        section.content = []
        for i in range(count):
            value = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            section.content.append(value)

    def updateSectionData(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        data_buf = int(len(section.content)).to_bytes(1, byteorder='big')
        data_buf += int(section.field1).to_bytes(1, byteorder='big')
        for value in section.content:
            data_buf += int(value).to_bytes(2, byteorder='big')

        if (len(data_buf) != 2+2*len(section.content)):
            raise RuntimeError("Block {} section {} generated binary data of invalid size"\
              .format(self.ident,section_num))

        self.setData(data_buf, section_num=section_num)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)


class TM80(Block):
    """ Data Space Type Map
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.defaultBlockCoding = BLOCK_CODING.NONE

    def createSection(self):
        section = super().createSection()
        return section

    def initWithRSRCLate(self):
        ver = self.vi.getFileVersion()
        if isGreaterOrEqVersion(ver, 10,0,0):
            # This block is encoded only in some versions of LV
            self.defaultBlockCoding = BLOCK_CODING.ZLIB
        super().initWithRSRCLate()
        pass

    def initWithXMLLate(self):
        ver = self.vi.getFileVersion()
        if isGreaterOrEqVersion(ver, 10,0,0):
            # This block is encoded only in some versions of LV
            self.defaultBlockCoding = BLOCK_CODING.ZLIB
            for snum in self.sections:
                # Force-encode any already stored data; otherwise we would run
                # into decompression error when trying to get the data
                coded_data = self.getRawData(section_num=snum)
                if coded_data is not None:
                    self.setData(coded_data, section_num=snum)
        super().initWithXMLLate()
        pass

    def getData(self, section_num=None, use_coding=None):
        if use_coding is None:
            use_coding = self.defaultBlockCoding
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=None):
        if use_coding is None:
            use_coding = self.defaultBlockCoding
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)


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
    def createSection(self):
        section = super().createSection()
        section.version = []
        section.execFlags = 0
        section.protected = False
        section.field08 = 0
        section.field0C = 0
        section.flags10 = 0
        section.field12 = 0
        section.buttonsHidden = 0
        section.frontpFlags = 0
        section.instrState = 0
        section.execState = 0
        section.execPrio = 0
        section.viType = 0
        section.field24 = 0
        section.field28 = 0
        section.field2C = 0
        section.field30 = 0
        section.viSignature = b''
        section.field44 = 0
        section.field48 = 0
        section.field4C = 0
        section.field4E = 0
        section.field50_md5 = b''
        section.libpass_text = None
        section.libpass_md5 = b''
        section.field70 = 0
        section.field74 = 0
        section.field78_md5 = b''
        section.inlineStg = 0
        section.field8C = 0
        section.field90 = b''
        return section

    def parseRSRCData(self, section_num, bldata):
        section = self.sections[section_num]

        # Size of the data seem to be 120, 136 or 137
        # Data before byte 120 does not move - so it's always safe to read
        data = LVSRData(self.po)
        if bldata.readinto(data) not in [120, 136, 137, sizeof(LVSRData)]:
            raise EOFError("Data block too short for parsing {} data.".format(self.ident))

        section.version = decodeVersion(data.version)
        section.protected = ((data.execFlags & VI_EXEC_FLAGS.LibProtected.value) != 0)
        section.execFlags = data.execFlags & (~VI_EXEC_FLAGS.LibProtected.value)
        section.field08 = int(data.field08)
        section.field0C = int(data.field0C)
        section.flags10 = int(data.flags10)
        section.field12 = int(data.field12)
        section.buttonsHidden = int(data.buttonsHidden)
        section.frontpFlags = int(data.frontpFlags)
        section.instrState = int(data.instrState)
        section.execState = int(data.execState)
        section.execPrio = int(data.execPrio)
        section.viType = int(data.viType)
        section.field24 = int(data.field24)
        section.field28 = int(data.field28)
        section.field2C = int(data.field2C)
        section.field30 = int(data.field30)
        section.viSignature = bytes(data.viSignature)
        section.field44 = int(data.field44)
        section.field48 = int(data.field48)
        section.field4C = int(data.field4C)
        section.field4E = int(data.field4E)
        section.field50_md5 = bytes(data.field50_md5)
        section.libpass_md5 = bytes(data.libpass_md5)
        section.libpass_text = None
        section.field70 = int(data.field70)
        section.field74 = int(data.field74)
        # Additional data, exists only in newer versions
        # sizeof(LVSR) per version: 8.6b7->120 9.0b25->120 9.0->120 10.0b84->120 10.0->136 11.0.1->136 12.0->136 13.0->136 14.0->137

        if isGreaterOrEqVersion(section.version, 10,0, stage='release'):
            section.field78_md5 = bytes(data.field78_md5)
        if isGreaterOrEqVersion(section.version, 14,0):
            section.inlineStg = int(data.inlineStg)
        if isGreaterOrEqVersion(section.version, 15,0):
            section.field8C = int(data.field8C)
        # Any data added in future versions
        section.field90 = bldata.read()

    def updateSectionData(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        data_buf = int(encodeVersion(section.version)).to_bytes(4, byteorder='big')
        data_execFlags = (section.execFlags & (~VI_EXEC_FLAGS.LibProtected.value)) | \
          (VI_EXEC_FLAGS.LibProtected.value if section.protected else 0)
        data_buf += int(data_execFlags).to_bytes(4, byteorder='big')
        data_buf += int(section.field08).to_bytes(4, byteorder='big')
        data_buf += int(section.field0C).to_bytes(4, byteorder='big')
        data_buf += int(section.flags10).to_bytes(2, byteorder='big')
        data_buf += int(section.field12).to_bytes(2, byteorder='big')
        data_buf += int(section.buttonsHidden).to_bytes(2, byteorder='big')
        data_buf += int(section.frontpFlags).to_bytes(2, byteorder='big')
        data_buf += int(section.instrState).to_bytes(4, byteorder='big')
        data_buf += int(section.execState).to_bytes(4, byteorder='big')
        data_buf += int(section.execPrio).to_bytes(2, byteorder='big')
        data_buf += int(section.viType).to_bytes(2, byteorder='big')
        data_buf += int(section.field24).to_bytes(4, byteorder='big', signed=True)
        data_buf += int(section.field28).to_bytes(4, byteorder='big')
        data_buf += int(section.field2C).to_bytes(4, byteorder='big')
        data_buf += int(section.field30).to_bytes(4, byteorder='big')
        data_buf += section.viSignature
        data_buf += int(section.field44).to_bytes(4, byteorder='big')
        data_buf += int(section.field48).to_bytes(4, byteorder='big')
        data_buf += int(section.field4C).to_bytes(2, byteorder='big')
        data_buf += int(section.field4E).to_bytes(2, byteorder='big')
        data_buf += section.field50_md5
        if section.libpass_text is not None:
            pass #TODO re-compute md5 from pass
        data_buf += section.libpass_md5
        data_buf += int(section.field70).to_bytes(4, byteorder='big')
        data_buf += int(section.field74).to_bytes(4, byteorder='big', signed=True)
        if isGreaterOrEqVersion(section.version, 10,0, stage='release'):
            data_buf += section.field78_md5
        if isGreaterOrEqVersion(section.version, 14,0):
            data_buf += int(section.inlineStg).to_bytes(1, byteorder='big')
        if isGreaterOrEqVersion(section.version, 15,0):
            data_buf += b'\0' * 3
            data_buf += int(section.field8C).to_bytes(4, byteorder='big')
        data_buf += section.field90

        if len(data_buf) not in [120, 136, 137, sizeof(LVSRData)+len(section.field90)]:
            raise RuntimeError("Block {} section {} generated binary data of invalid size"
              .format(self.ident,section_num))

        self.setData(data_buf, section_num=section_num)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)

    def initWithXMLSection(self, section, section_elem):
        snum = section.start.section_idx
        fmt = section_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For Block {} section {:d}, reading inline XML data"\
                  .format(self.vi.src_fname,self.ident,snum))
            section.field90 = b''

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
                    section.version = ver
                elif (subelem.tag == "Library"):
                    section.protected = int(subelem.get("Protected"), 0)
                    password_text = subelem.get("Password")
                    password_hash = subelem.get("PasswordHash")
                    if password_text is not None:
                        password_bin = password_text.encode(self.vi.textEncoding)
                        section.libpass_text = password_text
                        section.libpass_md5 = md5(password_bin).digest()
                    else:
                        section.libpass_md5 = bytes.fromhex(password_hash)
                    pass
                elif (subelem.tag == "Execution"):
                    section.execState = int(subelem.get("State"), 0)
                    section.execPrio = int(subelem.get("Priority"), 0)
                    section.execFlags = importXMLBitfields(VI_EXEC_FLAGS, subelem)
                elif (subelem.tag == "ButtonsHidden"):
                    section.buttonsHidden = importXMLBitfields(VI_BTN_HIDE_FLAGS, subelem)
                elif (subelem.tag == "Instrument"):
                    section.viType = valFromEnumOrIntString(VI_TYPE, subelem.get("Type"))
                    tmphash = subelem.get("Signature")
                    section.viSignature = bytes.fromhex(tmphash)
                    section.instrState = importXMLBitfields(VI_IN_ST_FLAGS, subelem)
                elif (subelem.tag == "FrontPanel"):
                    section.frontpFlags = importXMLBitfields(VI_FP_FLAGS, subelem)
                elif (subelem.tag == "Unknown"):
                    section.field08 = int(subelem.get("Field08"), 0)
                    section.field0C = int(subelem.get("Field0C"), 0)
                    section.flags10 = int(subelem.get("Flags10"), 0)
                    section.field12 = int(subelem.get("Field12"), 0)
                    section.field24 = int(subelem.get("Field24"), 0)
                    section.field28 = int(subelem.get("Field28"), 0)
                    section.field2C = int(subelem.get("Field2C"), 0)
                    section.field30 = int(subelem.get("Field30"), 0)
                    section.field44 = int(subelem.get("Field44"), 0)
                    section.field48 = int(subelem.get("Field48"), 0)
                    section.field4C = int(subelem.get("Field4C"), 0)
                    section.field4E = int(subelem.get("Field4E"), 0)
                    field50_hash = subelem.get("Field50Hash")
                    section.field50_md5 = bytes.fromhex(field50_hash)
                    section.field70 = int(subelem.get("Field70"), 0)
                    section.field74 = int(subelem.get("Field74"), 0)
                    # Additional data, exists only in some versions
                    field78_hash = subelem.get("Field78Hash")
                    if field78_hash is not None:
                        section.field78_md5 = bytes.fromhex(field78_hash)
                    inlineStg = subelem.get("InlineStg")
                    if inlineStg is not None:
                        section.inlineStg = int(inlineStg, 0)
                    field8C = subelem.get("Field8C")
                    if field8C is not None:
                        section.field8C = int(field8C, 0)

                elif (subelem.tag == "Field90"):
                    bin_path = os.path.dirname(self.vi.src_fname)
                    if len(bin_path) > 0:
                        bin_fname = bin_path + '/' + subelem.get("File")
                    else:
                        bin_fname = subelem.get("File")
                    with open(bin_fname, "rb") as part_fh:
                        section.field90 = part_fh.read()
                else:
                    raise AttributeError("Section contains unexpected tag")
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        self.parseData(section_num=snum)

        section_elem.text = "\n"
        subelem = ET.SubElement(section_elem,"Version")
        subelem.tail = "\n"
        subelem.set("Major", "{:d}".format(section.version['major']))
        subelem.set("Minor", "{:d}".format(section.version['minor']))
        subelem.set("Bugfix", "{:d}".format(section.version['bugfix']))
        subelem.set("Stage", "{:s}".format(section.version['stage_text']))
        subelem.set("Build", "{:d}".format(section.version['build']))
        subelem.set("Flags", "0x{:X}".format(section.version['flags']))

        subelem = ET.SubElement(section_elem,"Library")
        subelem.tail = "\n"
        subelem.set("Protected", "{:d}".format(section.protected))
        subelem.set("PasswordHash", section.libpass_md5.hex())
        subelem.set("HashType", "MD5")

        subelem = ET.SubElement(section_elem,"Execution")
        subelem.tail = "\n"
        subelem.set("State", "{:d}".format(section.execState))
        subelem.set("Priority", "{:d}".format(section.execPrio))
        exportXMLBitfields(VI_EXEC_FLAGS, subelem, section.execFlags, \
          skip_mask=VI_EXEC_FLAGS.LibProtected.value)

        subelem = ET.SubElement(section_elem,"ButtonsHidden")
        subelem.tail = "\n"
        exportXMLBitfields(VI_BTN_HIDE_FLAGS, subelem, section.buttonsHidden)

        subelem = ET.SubElement(section_elem,"Instrument")
        subelem.tail = "\n"
        subelem.set("Type", "{:s}".format(stringFromValEnumOrInt(VI_TYPE, section.viType)))
        subelem.set("Signature", section.viSignature.hex())
        exportXMLBitfields(VI_IN_ST_FLAGS, subelem, section.instrState)

        subelem = ET.SubElement(section_elem,"FrontPanel")
        subelem.tail = "\n"
        exportXMLBitfields(VI_FP_FLAGS, subelem, section.frontpFlags)

        subelem = ET.SubElement(section_elem,"Unknown")
        subelem.tail = "\n"

        subelem.set("Field08", "{:d}".format(section.field08))
        subelem.set("Field0C", "{:d}".format(section.field0C))
        subelem.set("Flags10", "{:d}".format(section.flags10))
        subelem.set("Field12", "{:d}".format(section.field12))
        subelem.set("Field24", "{:d}".format(section.field24))
        subelem.set("Field28", "{:d}".format(section.field28))
        subelem.set("Field2C", "{:d}".format(section.field2C))
        subelem.set("Field30", "{:d}".format(section.field30))
        subelem.set("Field44", "{:d}".format(section.field44))
        subelem.set("Field48", "{:d}".format(section.field48))
        subelem.set("Field4C", "{:d}".format(section.field4C))
        subelem.set("Field4E", "{:d}".format(section.field4E))
        subelem.set("Field50Hash", section.field50_md5.hex())
        subelem.set("Field70", "{:d}".format(section.field70))
        subelem.set("Field74", "{:d}".format(section.field74))
        # Additional data, exists only in some versions
        subelem.set("Field78Hash", section.field78_md5.hex())
        # Additional data, exists only in some versions
        subelem.set("InlineStg", "{:d}".format(section.inlineStg))
        subelem.set("Field8C", "{:d}".format(section.field8C))

        if len(section.field90) > 0:
            subelem = ET.SubElement(section_elem,"Field90")
            subelem.tail = "\n"

            part_fname = "{:s}_{:s}.{:s}".format(fname_base,subelem.tag,"bin")
            with open(part_fname, "wb") as part_fd:
                part_fd.write(section.field90)
            subelem.set("Format", "bin")
            subelem.set("File", os.path.basename(part_fname))

        section_elem.set("Format", "inline")

    def getVersion(self):
        self.parseData()
        return self.version


class vers(Block):
    """ Version block
    """
    def createSection(self):
        section = super().createSection()
        section.version = []
        section.version_text = b''
        section.version_info = b''
        return section

    def parseRSRCData(self, section_num, bldata):
        section = self.sections[section_num]

        section.version = decodeVersion(int.from_bytes(bldata.read(4), byteorder='big', signed=False))
        version_text_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        section.version_text = bldata.read(version_text_len)
        # TODO Is the string null-terminated? or that's length of another string?
        version_unk_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        if version_unk_len != 0:
            raise AttributeError("Always zero value 1 is not zero")
        version_info_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        section.version_info = bldata.read(version_info_len)
        # TODO Is the string null-terminated? or that's length of another string?
        version_unk_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        if version_unk_len != 0:
            raise AttributeError("Always zero value 2 is not zero")

    def updateSectionData(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        data_buf = int(encodeVersion(section.version)).to_bytes(4, byteorder='big')
        data_buf += int(len(section.version_text)).to_bytes(1, byteorder='big')
        data_buf += section.version_text + b'\0'
        data_buf += int(len(section.version_info)).to_bytes(1, byteorder='big')
        data_buf += section.version_info + b'\0'

        if (len(data_buf) != 4 + 2+len(section.version_text) + 2+len(section.version_info)):
            raise RuntimeError("Block {} section {} generated binary data of invalid size"\
              .format(self.ident,section_num))

        self.setData(data_buf, section_num=section_num)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)

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
                section.version_text = subelem.get("Text").encode(self.vi.textEncoding)
                section.version_info = subelem.get("Info").encode(self.vi.textEncoding)
                section.version = ver
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        self.parseData(section_num=snum)

        section_elem.text = "\n"
        subelem = ET.SubElement(section_elem,"Version")
        subelem.tail = "\n"

        subelem.set("Major", "{:d}".format(section.version['major']))
        subelem.set("Minor", "{:d}".format(section.version['minor']))
        subelem.set("Bugfix", "{:d}".format(section.version['bugfix']))
        subelem.set("Stage", "{:s}".format(section.version['stage_text']))
        subelem.set("Build", "{:d}".format(section.version['build']))
        subelem.set("Flags", "0x{:X}".format(section.version['flags']))
        subelem.set("Text", "{:s}".format(section.version_text.decode(self.vi.textEncoding)))
        subelem.set("Info", "{:s}".format(section.version_info.decode(self.vi.textEncoding)))

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
    def createSection(self):
        section = super().createSection()
        section.width = 32
        section.height = 32
        section.bpp = 1
        section.icon = None
        return section

    def parseRSRCData(self, section_num, bldata):
        section = self.sections[section_num]

        icon = Image.new("P", (section.width, section.height))
        img_palette = [ 0 ] * (3*256)
        if section.bpp == 8:
            lv_color_palette = LABVIEW_COLOR_PALETTE_256
        elif section.bpp == 4:
            lv_color_palette = LABVIEW_COLOR_PALETTE_16
        else:
            lv_color_palette = LABVIEW_COLOR_PALETTE_2
        for i, rgb in enumerate(lv_color_palette):
            img_palette[3*i+0] = (rgb >> 16) & 0xFF
            img_palette[3*i+1] = (rgb >>  8) & 0xFF
            img_palette[3*i+2] = (rgb >>  0) & 0xFF
        icon.putpalette(img_palette, rawmode='RGB')
        img_data = bldata.read(int(section.width * section.height * section.bpp / 8))
        if section.bpp == 8:
            pass
        elif section.bpp == 4:
            img_data8 = bytearray(section.width * section.height)
            for i, px in enumerate(img_data):
                img_data8[2*i+0] = (px >> 4) & 0xF
                img_data8[2*i+1] = (px >> 0) & 0xF
            img_data = img_data8
        elif section.bpp == 1:
            img_data8 = bytearray(section.width * section.height)
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
        #for y in range(0, section.height):
        #    for x in range(0, section.width):
        #        icon.putpixel((x, y), bldata.read(1))
        section.icon = icon

    def updateSectionData(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        data_buf = bytes(section.icon.getdata())
        data_len = (section.width * section.height * section.bpp) // 8

        if section.bpp == 8:
            pass
        elif section.bpp == 4:
            data_buf8 = bytearray(data_len)
            for i in range(data_len):
                data_buf8[i] = (data_buf[2*i+0] << 4) | (data_buf[2*i+1] << 0)
            data_buf = data_buf8
        elif section.bpp == 1:
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
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)

    def loadIcon(self):
        self.parseData()
        return self.icon

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        block_fname = "{:s}.{:s}".format(fname_base,"png")

        self.parseData(section_num=snum)
        with open(block_fname, "wb") as block_fd:
            section.icon.save(block_fd, format="PNG")

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
                section.icon = icon
                icon.getdata() # to make sure the file gets loaded
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass


class icl8(ICON):
    """ Icon Large 32x32 8bpp
    """
    def createSection(self):
        section = super().createSection()
        section.width = 32
        section.height = 32
        section.bpp = 8
        return section


class icl4(ICON):
    """ Icon Large 32x32 4bpp
    """
    def createSection(self):
        section = super().createSection()
        section.width = 32
        section.height = 32
        section.bpp = 4
        return section


class BDPW(Block):
    """ Block Diagram Password
    """
    def createSection(self):
        section = super().createSection()
        section.password = None
        section.password_md5 = b''
        section.hash_1 = b''
        section.hash_2 = b''
        section.salt_iface_idx = None
        section.salt = None
        return section

    def parseRSRCData(self, section_num, bldata):
        section = self.sections[section_num]

        section.password_md5 = bldata.read(16)
        section.hash_1 = bldata.read(16)
        section.hash_2 = bldata.read(16)

    def updateSectionData(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        if True:
            self.recalculateHash1(section_num=section_num)
            self.recalculateHash2(section_num=section_num)

        data_buf = section.password_md5
        data_buf += section.hash_1
        data_buf += section.hash_2

        if (len(data_buf) != 48):
            raise RuntimeError("Block {} section {} generated binary data of invalid size"\
              .format(self.ident,section_num))

        self.setData(data_buf, section_num=section_num)

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        self.parseData(section_num=snum)
        self.recalculateHash1(section_num=snum, store=False) # this is needed to find salt
        self.recognizePassword(section_num=snum)

        section_elem.text = "\n"
        subelem = ET.SubElement(section_elem,"Password")
        subelem.tail = "\n"

        if section.password is not None:
            subelem.set("Text", section.password)
        else:
            subelem.set("Hash", section.password_md5.hex())
            subelem.set("HashType", "MD5")
        if section.salt_iface_idx is not None:
            subelem.set("SaltSource", str(section.salt_iface_idx))
        else:
            subelem.set("SaltData", section.salt.hex())

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
                    self.setPassword(section_num=snum, password_text=pass_text)
                else:
                    self.setPassword(section_num=snum, password_md5=bytes.fromhex(pass_hash))

                salt_iface_idx = subelem.get("SaltSource")
                salt_data = subelem.get("SaltData")
                if salt_iface_idx is not None:
                    section.salt_iface_idx = int(salt_iface_idx, 0)
                else:
                    section.salt = bytes.fromhex(salt_data)
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)

    @staticmethod
    def getPasswordSaltFromTerminalCounts(numberCount, stringCount, pathCount):
        salt = int(numberCount).to_bytes(4, byteorder='little')
        salt += int(stringCount).to_bytes(4, byteorder='little')
        salt += int(pathCount).to_bytes(4, byteorder='little')
        return salt

    def scanForHashSalt(self, section_num, presalt_data=b'', postsalt_data=b''):
        section = self.sections[section_num]

        salt = b''
        ver = self.vi.getFileVersion()
        if not isGreaterOrEqVersion(ver, 1,0):
            if (po.verbose > 0):
                eprint("{:s}: Warning: No version block found; assuming oldest format, with empty password salt".format(self.vi.src_fname))
            section.salt = salt
            return salt
        if isGreaterOrEqVersion(ver, 12,0):
            # Figure out the salt
            salt_iface_idx = None
            VCTP = self.vi.get_or_raise('VCTP')
            interfaceEnumerate = self.vi.connectorEnumerate(fullType=CONNECTOR_FULL_TYPE.Function)
            # Connectors count if one of the interfaces is the source of salt; usually it's the last interface, so check in reverse
            for i, iface_idx, iface_obj in reversed(interfaceEnumerate):
                term_connectors = VCTP.getClientConnectorsByType(iface_obj)
                salt = BDPW.getPasswordSaltFromTerminalCounts(len(term_connectors['number']), len(term_connectors['string']), len(term_connectors['path']))
                md5_hash_1 = md5(presalt_data + salt + postsalt_data).digest()
                if md5_hash_1 == section.hash_1:
                    if (self.po.verbose > 1):
                        print("{:s}: Found matching salt {}, interface {:d}/{:d}".format(self.vi.src_fname,salt.hex(),i+1,len(interfaceEnumerate)))
                    salt_iface_idx = iface_idx
                    break

            section.salt_iface_idx = salt_iface_idx

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
                    if md5_hash_1 == section.hash_1:
                        if (self.po.verbose > 1):
                            print("{:s}: Found matching salt {} via brute-force".format(self.vi.src_fname,salt.hex()))
                        break
        section.salt = salt
        return salt

    def findHashSalt(self, section_num, password_md5, LIBN_content, LVSR_content, force_scan=False):
        section = self.sections[section_num]

        if force_scan:
            section.salt_iface_idx = None
            section.salt = None
        if section.salt_iface_idx is not None:
            # If we've previously found an interface on which the salt is based, use that interface
            VCTP = self.vi.get_or_raise('VCTP')
            VCTP_content = VCTP.getContent()
            term_connectors = VCTP.getClientConnectorsByType(VCTP_content[section.salt_iface_idx])
            salt = BDPW.getPasswordSaltFromTerminalCounts(len(term_connectors['number']), len(term_connectors['string']), len(term_connectors['path']))
        elif section.salt is not None:
            # If we've previously brute-forced the salt, use that same salt
            salt = section.salt
        else:
            # If we didn't determined the salt yet, do  a scan
            salt = self.scanForHashSalt(section_num, presalt_data=password_md5+LIBN_content+LVSR_content)
        return salt

    def setPassword(self, section_num, password_text=None, password_md5=None, store=True):
        """ Sets new password, without recalculating hashes
        """
        section = self.sections[section_num]

        if password_text is not None:
            if store:
                section.password = password_text
            newPassBin = password_text.encode(self.vi.textEncoding)
            password_md5 = md5(newPassBin).digest()
        else:
            if store:
                section.password = None
        if password_md5 is None:
            raise ValueError("Requested to set password, but no new password provided in text nor md5 form")
        if store:
            section.password_md5 = password_md5
        return password_md5


    def recognizePassword(self, section_num, password_md5=None, store=True):
        """ Gets password from MD5 hash, if the password is a common one
        """
        section = self.sections[section_num]

        if password_md5 is None:
            password_md5 = section.password_md5
        found_pass = None
        for test_pass in ['', 'qwerty', 'password', '111111', '12345678', 'abc123', '1234567', 'password1', '12345', '123']:
            test_pass_bin = test_pass.encode(self.vi.textEncoding)
            test_md5 = md5(test_pass_bin).digest()
            if password_md5 == test_md5:
                found_pass = test_pass
                break
        if (store):
            section.password = found_pass
        return found_pass


    def recalculateHash1(self, section_num=None, password_md5=None, store=True):
        """ Calculates the value of hash_1, either stores it or only returns

            Re-calculation is made using previously computed salt if available, or newly computed on first run.
            Supplying custom password on first run will lead to inability to find salt; fortunately,
            first run is quite early, during validation of parsed data.
        """
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        if password_md5 is None:
            password_md5 = section.password_md5
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

        salt = self.findHashSalt(section_num, password_md5, LIBN_content, LVSR_content)

        hash1_data = password_md5 + LIBN_content + LVSR_content + salt

        md5_hash_1 = md5(hash1_data).digest()
        if store:
            section.hash_1 = md5_hash_1
        return md5_hash_1

    def recalculateHash2(self, section_num=None, md5_hash_1=None, store=True):
        """ Calculates the value of hash_2, either stores it or only returns

            Re-calculation is made using previously computed hash_1
            and BDH block if the VI file
        """
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        if md5_hash_1 is None:
            md5_hash_1 = section.hash_1

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
            section.hash_2 = md5_hash_2
        return md5_hash_2


class LIBN(Block):
    """ Library Names

    Stores names of libraries which contain this RSRC file.
    """
    def createSection(self):
        section = super().createSection()
        section.content = None
        return section

    def parseRSRCData(self, section_num, bldata):
        section = self.sections[section_num]

        count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.content = []
        for i in range(count):
            content_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            section.content.append(bldata.read(content_len))

    def updateSectionData(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        data_buf = int(len(section.content)).to_bytes(4, byteorder='big')
        for name in section.content:
            data_buf += int(len(name)).to_bytes(1, byteorder='big')
            data_buf += name

        if (len(data_buf) < 5):
            raise RuntimeError("Block {} section {} generated binary data of invalid size"\
              .format(self.ident,section_num))

        self.setData(data_buf, section_num=section_num)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)

    def initWithXMLSection(self, section, section_elem):
        snum = section.start.section_idx
        fmt = section_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For Block {} section {:d}, reading inline XML data"\
                  .format(self.vi.src_fname,self.ident,snum))
            section.content = []
            # There can be multiple "Library" sub-elements
            for i, subelem in enumerate(section_elem):
                if (subelem.tag != "Library"):
                    raise AttributeError("Section contains something else than 'Library'")

                name_text = subelem.get("Name")
                section.content.append(name_text.encode(self.vi.textEncoding))
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        self.parseData(section_num=snum)

        section_elem.text = "\n"
        for name in section.content:
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
    def createSection(self):
        section = super().createSection()
        return section

    def getData(self, section_num=None, use_coding=BLOCK_CODING.XOR):
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.XOR):
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)


class BDHP(Block):
    """ Block Diagram Heap

    This block is spcific to LV 7beta and older.
    """
    def createSection(self):
        section = super().createSection()
        section.content = None
        return section

    def parseRSRCData(self, section_num, bldata):
        section = self.sections[section_num]

        content_len = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.content = bldata.read(content_len)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.NONE):
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.NONE):
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)

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
    def createSection(self):
        section = super().createSection()
        section.content = None
        return section

    def parseRSRCData(self, section_num, bldata):
        section = self.sections[section_num]

        content_len = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.content = bldata.read(content_len)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)

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

    def createSection(self):
        section = super().createSection()
        section.objects = []
        return section

    def getTopClassEn(self, section, obj_idx):
        """ Return classId of top object with class

        From a list of object indexes, this function will return class id
        of the one nearest to top which has a 'class' attribute.
        """
        for i in reversed(obj_idx):
            obj = section.objects[i]
            if LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__class.value in obj.attribs:
                return obj.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__class.value]
        return LVheap.SL_CLASS_TAGS.SL__oHExt

    def getTopParentNode(self, section, obj_idx):
        """ Return top HeapNode from given list
        """
        if len(section.objects) < 1:
            return None
        i = obj_idx[-1]
        return section.objects[i]

    def parseRSRCHeap(self, section, bldata, parentNode):
        startPos = bldata.tell()
        cmd = bldata.read(2)

        sizeSpec = (cmd[0] >> 5) & 7
        hasAttrList = (cmd[0] >> 4) & 1
        scopeInfo = (cmd[0] >> 2) & 3
        rawTagId = cmd[1] | ((cmd[0] & 3) << 8)

        if rawTagId == 1023:
            tagId = int.from_bytes(bldata.read(4), byteorder='big', signed=True)
        else:
            tagId = rawTagId - 31

        tagEn = LVheap.tagIdToEnum(tagId, parentNode)

        i = len(section.objects)
        obj = LVheap.createObjectNode(self.vi, self.po, parentNode, tagEn, scopeInfo)
        section.objects.append(obj)
        if scopeInfo != LVheap.NODE_SCOPE.TagClose:
            parentNode = obj
        obj.parseRSRCData(bldata, hasAttrList, sizeSpec)
        if scopeInfo != LVheap.NODE_SCOPE.TagOpen:
            parentNode = parentNode.parent
        dataLen = bldata.tell() - startPos

        # TODO Should we re-read the bytes and set raw data inside the obj?
        #bldata.seek(startPos)
        #dataBuf = bldata.read(dataLen)

        return parentNode, dataLen

    def parseRSRCData(self, section_num, bldata):
        section = self.sections[section_num]

        section.objects = []
        content_len = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

        parentNode = None
        tot_len = 0
        while tot_len < content_len:
            parentNode, entry_len = self.parseRSRCHeap(section, bldata, parentNode)
            if entry_len <= 0:
                print("{:s}: Block {} section {:d}, has not enough data for complete heap"\
                  .format(self.vi.src_fname,self.ident,section_num))
                break
            tot_len += entry_len

        if parentNode != None:
            eprint("{}: Warning: In block {}, heap did not closed all tags"\
              .format(self.vi.src_fname, self.ident))

    def updateSectionData(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        for obj in section.objects:
            if not obj.raw_data_updated:
                obj.updateData()

        data_buf = b''
        for i, obj in enumerate(section.objects):
            bldata = obj.getData()
            data_buf += bldata.read()

        data_buf = int(len(data_buf)).to_bytes(4, byteorder='big') + data_buf

        if (len(data_buf) < 4 + 2*len(section.objects)):
            raise RuntimeError("Block {} section {} generated binary data of invalid size"\
              .format(self.ident,section_num))

        self.setData(data_buf, section_num=section_num)

    def initWithXMLHeap(self, section, elem, parentNode):
        tagEn = LVheap.tagNameToEnum(elem.tag, parentNode)
        if tagEn is None:
            raise AttributeError("Unrecognized tag in heap XML; tag '{}', parent tag '{}'"\
              .format(elem.tag, parentNode.tagEn.name))
        scopeInfo = LVheap.autoScopeInfoFromET(elem)
        obj = LVheap.createObjectNode(self.vi, self.po, parentNode, tagEn, scopeInfo)
        section.objects.append(obj)

        obj.initWithXML(elem)

        for subelem in elem:
            self.initWithXMLHeap(section, subelem, obj)

        if obj.scopeInfo == LVheap.NODE_SCOPE.TagOpen.value:
            scopeInfo = LVheap.NODE_SCOPE.TagClose.value
            obj = LVheap.createObjectNode(self.vi, self.po, parentNode, tagEn, scopeInfo)
            section.objects.append(obj)
            #obj.initWithXML(elem) # No init needed for closing tag


    def initWithXMLSection(self, section, section_elem):
        snum = section.start.section_idx
        fmt = section_elem.get("Format")
        if fmt == "xml": # Format="xml" - the content is stored in a separate XML file
            if (self.po.verbose > 2):
                print("{:s}: For Block {} section {:d}, reading separate XML file '{}'"\
                  .format(self.vi.src_fname,self.ident,snum,section_elem.get("File")))
            xml_path = os.path.dirname(self.vi.src_fname)
            if len(xml_path) > 0:
                xml_fname = xml_path + '/' + section_elem.get("File")
            else:
                xml_fname = section_elem.get("File")
            tree = ET.parse(xml_fname)
            section.objects = []
            self.initWithXMLHeap(section, tree.getroot(), None)
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        block_fname = "{:s}.{:s}".format(fname_base,"xml")

        root = None
        parent_elems = []
        elem = None
        for i, obj in enumerate(section.objects):
            scopeInfo = obj.getScopeInfo()
            if elem is None:
                tagName = LVheap.tagEnToName(obj.tagEn, obj.parent)
                elem = ET.Element(tagName)
                root = elem
                parent_elems.append(root)
            elif scopeInfo == LVheap.NODE_SCOPE.TagClose:
                if obj.parent is not None:
                    tagName = LVheap.tagEnToName(obj.parent.tagEn, obj.parent.parent)
                else:
                    tagName = 'no_parent_tag_found'
                elem = parent_elems.pop()
                if elem.tag != tagName:
                    eprint("{}: Warning: In block {}, closing tag {} instead of {}"\
                      .format(self.vi.src_fname, self.ident, tagName, elem.tag))
            else:
                tagName = LVheap.tagEnToName(obj.tagEn, obj.parent)
                elem = ET.SubElement(parent_elems[-1], tagName)

            obj.exportXML(elem, scopeInfo, "{:s}_{:04d}".format(fname_base,i))

            if scopeInfo == LVheap.NODE_SCOPE.TagOpen:
                parent_elems.append(elem)

        ET.pretty_element_tree_heap(root)

        if (self.po.verbose > 1):
            print("{}: Writing XML for block {}".format(self.vi.src_fname, self.ident))
        tree = ET.ElementTree(root)
        with open(block_fname, "wb") as block_fd:
            tree.write(block_fd, encoding='utf-8', xml_declaration=True)

        section_elem.set("Format", "xml")
        section_elem.set("File", os.path.basename(block_fname))

    def getData(self, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)

    def getContent(self):
        self.updateData()
        bldata = self.getData()
        content_len = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        content = bldata.read(content_len)
        return content

    def getContentHash(self):
        content = self.getContent()
        return md5(content).digest()

FPHb = FPH


class FPHc(Block):
    """ Front Panel Heap ver c
    """
    def getData(self, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)

    def getContent(self):
        bldata = self.getData()
        content_len = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        content = bldata.read(content_len)
        return content


class VCTP(Block):
    """ Virtual Connectors / Terminal Points

    All terminals used by the .VI and the terminals of the .VI itself are stored
    in this block.

    The VCTP contains bottom-up objects. This means that objects can inherit
    from previous defined objects. So to define a cluster they first define
    every element and than add a cluster-object with a index-table containing
    all previously defined elements used by the cluster.
    """
    def createSection(self):
        section = super().createSection()
        section.content = []
        section.unflatten = []
        return section

    def parseRSRCConnector(self, section_num, bldata, pos):
        section = self.sections[section_num]

        bldata.seek(pos)
        obj_type, obj_flags, obj_len = ConnectorObject.parseRSRCDataHeader(bldata)
        if (self.po.verbose > 2):
            print("{:s}: Block {} connector {:d}, at 0x{:04x}, type 0x{:02x} flags 0x{:02x} len {:d}"\
              .format(self.vi.src_fname, self.ident, len(section.content), pos, obj_type, obj_flags, obj_len))
        if obj_len < 4:
            eprint("{:s}: Warning: Connector {:d} type 0x{:02x} data size {:d} too small to be valid"\
              .format(self.vi.src_fname, len(section.content), obj_type, obj_len))
            obj_type = CONNECTOR_FULL_TYPE.Void
        obj = newConnectorObject(self.vi, len(section.content), obj_flags, obj_type, self.po)
        section.content.append(obj)
        bldata.seek(pos)
        obj.initWithRSRC(bldata, obj_len)
        return obj.index, obj_len

    def parseRSRCData(self, section_num, bldata):
        section = self.sections[section_num]

        section.content = []
        # First we have count of connectors, and then the connectors themselves
        count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        pos = bldata.tell()
        for i in range(count):
            obj_idx, obj_len = self.parseRSRCConnector(section_num, bldata, pos)
            pos += obj_len
        # After that,there is a list
        section.unflatten = []
        count = readVariableSizeFieldU2p2(bldata)
        for i in range(count):
            val = readVariableSizeFieldU2p2(bldata)
            section.unflatten.append(val)

    def getData(self, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)

    def initWithXMLSection(self, section, section_elem):
        snum = section.start.section_idx
        fmt = section_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            section.content = []
            section.unflatten = []
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
                    if obj_idx >= len(section.content):
                        section.content.extend([None] * (obj_idx - len(section.content) + 1))
                    section.content[obj_idx] = obj
                    # Set connector data based on XML properties
                    obj.initWithXML(subelem)
                elif (subelem.tag == "UnFlatten"):
                    section.unflatten += [int(itm,0) for itm in subelem.text.split()]
                else:
                    raise AttributeError("Section contains unexpected tag")
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass

    def updateSectionData(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        for connobj in section.content:
            if not connobj.raw_data_updated:
                connobj.updateData()

        data_buf = int(len(section.content)).to_bytes(4, byteorder='big')
        for i, connobj in enumerate(section.content):
            bldata = connobj.getData()
            data_buf += bldata.read()

        data_buf += int(len(section.unflatten)).to_bytes(2, byteorder='big')
        for i, val in enumerate(section.unflatten):
            data_buf += int(val).to_bytes(2, byteorder='big')

        if (len(data_buf) < 4 + 4*len(section.content)):
            raise RuntimeError("Block {} section {} generated binary data of invalid size"\
              .format(self.ident,section_num))

        self.setData(data_buf, section_num=section_num)

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        self.parseData(section_num=snum)

        section_elem.text = "\n"

        for connobj in section.content:
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
        for i, val in enumerate(section.unflatten):
            if i % 16 == 0: strlist += "\n"
            strlist += " {:3d}".format(val)
        subelem.text = strlist

        section_elem.set("Format", "inline")

    def parseData(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        # Besides the normal parsing, also parse sub-objects
        Block.parseData(self, section_num=section_num)
        for connobj in section.content:
            connobj.parseData()

    def checkSanity(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        ret = True
        for connobj in section.content:
            if not connobj.checkSanity():
                ret = False
        for i, val in enumerate(section.unflatten):
            if val >= len(section.content):
                if (self.po.verbose > 1):
                    eprint("{:s}: Warning: Unflatten index {:d} exceeds connectors count {:d}"\
                      .format(self.vi.src_fname,i,len(section.content)))
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


class VICD(Block):
    """ Virtual Instrument Compiled Data
    """
    def createSection(self):
        section = super().createSection()
        return section

    def getData(self, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=BLOCK_CODING.ZLIB):
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)

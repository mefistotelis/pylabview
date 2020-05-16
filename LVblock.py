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
import io
import os
import zlib

from PIL import Image
from hashlib import md5
from types import SimpleNamespace
from ctypes import *

from LVmisc import *
import LVxml as ET
from LVdatatype import *
from LVinstrument import *
import LVclasses
import LVdatafill
import LVlinkinfo
import LVheap
import LVparts
import LVrsrcontainer

class BLOCK_CODING(enum.Enum):
    NONE = 0
    COMP = 1
    ZLIB = 2
    XOR = 3


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
        # Section name text bytes, from Info section
        self.name_text = None
        # Section name object, in case it's not a simple text
        self.name_obj = None


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
            self.full_name = self.__doc__.split('\n')[0].strip()
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
        if self.po.file_map:
            pretty_ident = getPrettyStrFromRsrcType(self.ident)

        fh = self.vi.rsrc_fh
        fh.seek(start_pos)

        self.sections = {}
        for i in range(header.count + 1):
            section = self.createSection()
            if fh.readinto(section.start) != sizeof(section.start):
                raise EOFError("Could not read BlockSectionStart data")
            if self.po.file_map:
                self.vi.rsrc_map.append( (fh.tell(), sizeof(section.start), \
                  "{}[{},{}]".format(type(section.start).__name__,pretty_ident,section.start.section_idx),) )
            if (self.po.verbose > 2):
                print(section.start)
            if not section.start.checkSanity():
                raise IOError("BlockSectionStart data sanity check failed")
            if section.start.section_idx in self.sections:
                raise IOError("BlockSectionStart of given section_idx exists twice")
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
        if self.po.file_map:
            pretty_ident = getPrettyStrFromRsrcType(self.ident)
        # After BlockSectionStart list, there is Block Section Names list; only some sections have a name
        names_start = self.vi.getPositionOfBlockSectionNames()
        names_end = self.vi.getPositionOfBlockInfoEnd()
        for snum, section in self.sections.items():
            if section.start.name_offset == 0xFFFFFFFF: # This value means no name
                continue
            if names_start + section.start.name_offset >= names_end:
                raise IOError("Block {} section {:d} Name position exceeds RSRC Info size".format(self.ident,snum))
            fh.seek(names_start + section.start.name_offset)
            name_text_len = int.from_bytes(fh.read(1), byteorder='big', signed=False)
            section.name_text = fh.read(name_text_len)
            if self.po.file_map:
                self.vi.rsrc_map.append( (fh.tell(), 1+name_text_len, \
                  "{}[{},{}]".format("NameOfSection",pretty_ident,section.start.section_idx),) )
            section.name_obj = None
            if len(section.name_text) >= 12 and section.name_text[0:4] == b'PTH0':
                totlen = int.from_bytes(section.name_text[4:8], byteorder='big', signed=False)
                if len(section.name_text) >= totlen + 4 + 4:
                    section.name_obj = LVclasses.LVPath0(self.vi, self.po)
                    bldata = io.BytesIO(section.name_text)
                    section.name_obj.parseRSRCData(bldata)


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
            raise NotImplementedError("Unsupported Block {} Section {:d} Format '{}'".format(self.ident,snum,fmt))
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
                raise IOError("BlockSectionStart of given section_idx exists twice")
            self.sections[section.start.section_idx] = section

            for subelem in section_elem:
                if (subelem.tag == "NameObject"):
                    section.name_obj = LVclasses.LVPath0(self.vi, self.po)
                    section.name_obj.initWithXML(subelem)
                    if section.name_text is not None:
                        eprint("{:s}: Warning: Block {} section {} has both 'Name' attrib and 'NameObject' tag."\
                          .format(self.vi.src_fname,self.ident,i))
                    section.name_text = section.name_obj.prepareRSRCData()
                    break

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
        if self.po.file_map:
            pretty_ident = getPrettyStrFromRsrcType(self.ident)
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
                raise IOError("Requested {} section {:d} data offset exceeds size of data block ({} > {})"\
                      .format(self.ident, i, section.start.data_offset + sizeof(BlockSectionData), rsrc_data_size))
            if fh.readinto(blksect) != sizeof(blksect):
                raise EOFError("Could not read BlockSectionData struct for block {} at {:d}".format(self.ident,section.block_pos))
            if not blksect.checkSanity():
                raise IOError("BlockSectionData struct for block {} sanity check failed".format(self.ident))
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
                if self.po.file_map:
                    self.vi.rsrc_map.append( (fh.tell(), sizeof(blksect)+len(section.raw_data), \
                      "{}[{},{}]".format(type(blksect).__name__,pretty_ident,section.start.section_idx),) )
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

        if self.needParseData(section_num=section_num):
            section = self.sections[section_num]
            if self.vi.dataSource == "rsrc" or self.hasRawData(section_num=section_num):
                bldata = self.getData(section_num=section_num)
                self.parseRSRCData(section_num, bldata)
                section.raw_data_updated = False
            elif self.vi.dataSource == "xml":
                self.parseXMLData(section_num=section_num)
                section.parsed_data_updated = False
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
        data = io.BytesIO(raw_data_section)
        if use_coding == BLOCK_CODING.NONE:
            pass
        elif use_coding == BLOCK_CODING.COMP:
            size = len(raw_data_section) - 4
            if size < 2:
                raise IOError("Unable to decompress block {} section {}: "\
                            "block-size-error - size: {}".format(self.ident, section_num, size))
            usize = int.from_bytes(data.read(4), byteorder='big', signed=False)
            # Every 8 bytes result in at least one mask byte, so ratio is 9/8 to 8/1, and up to 7 bytes of input padded
            if ( usize > size * 8 or (usize+7) < (size * 8) // 9 ):
                raise IOError("Unable to decompress block {} section {}: "\
                            "uncompress-size-error - size: {} - uncompress-size: {}"\
                            .format(self.ident, section_num, size, usize))
            data = io.BytesIO(zcomp_zeromsk8_decompress(data.read(size), usize))
        elif use_coding == BLOCK_CODING.ZLIB:
            size = len(raw_data_section) - 4
            if size < 2:
                raise IOError("Unable to decompress block {} section {}: "\
                            "block-size-error - size: {}".format(self.ident, section_num, size))
            usize = int.from_bytes(data.read(4), byteorder='big', signed=False)
            # Acording to zlib docs, max theoretical compression ration is 1032:1
            if ( (size > 16) and (usize < (size*5) // 10) ) or \
               ( (size > 128) and (usize < (size*9) // 10) ) or (usize > size * 1032):
                raise IOError("Unable to decompress block {} section {}: "\
                            "uncompress-size-error - size: {} - uncompress-size: {}"\
                            .format(self.ident, section_num, size, usize))
            data = io.BytesIO(zlib.decompress(data.read(size)))
        elif use_coding == BLOCK_CODING.XOR:
            size = len(raw_data_section)
            data = io.BytesIO(crypto_xor8320_decrypt(data.read(size)))
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
        elif use_coding == BLOCK_CODING.COMP:
            size = len(data_buf)
            raw_data_section = int(size).to_bytes(4, byteorder='big')
            raw_data_section += zcomp_zeromsk8_compress(data_buf)
        elif use_coding == BLOCK_CODING.ZLIB:
            size = len(data_buf)
            raw_data_section = int(size).to_bytes(4, byteorder='big')
            raw_data_section += zlib.compress(data_buf)
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

            if section.name_obj is not None:
                section.name_text = section.name_obj.prepareRSRCData()

            # Names are filled in different order when saved by LabView.
            # The order shouldn't really matter for anything, but makes files
            # generated by the tool harder to compare to originals.
            if section.name_text is not None:
                section.start.name_offset = len(section_names)
                section_names.extend( preparePStr(section.name_text, 1, self.po) )
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
        if (self.po.verbose > 1):
            print("{}: Writing block {} section {} to '{}'".format(self.vi.src_fname,self.ident,snum,block_fname))
        with open(block_fname, "wb") as block_fh:
            block_fh.write(bldata.read())

        section_elem.set("Format", "bin")
        section_elem.set("File", os.path.basename(block_fname))

    def exportFilesBase(self, snum, section):
        """ Prepare a base for file names of any files created by data export
        """
        pretty_ident = getPrettyStrFromRsrcType(self.ident)
        block_fpath = os.path.dirname(self.po.xml)

        fname_base = self.po.filebase
        if self.po.keep_names:
            if section.name_obj is not None and len(section.name_obj.content) >= 2:
                fname_base = "/".join([text_val.decode(self.vi.textEncoding, errors="ignore") for text_val in section.name_obj.content])
                fname_base = os.path.splitext(fname_base)[0]
            elif section.name_text is not None and len(section.name_text) >= 2:
                fname_base = section.name_text.decode(self.vi.textEncoding, errors="ignore")
                fname_base = os.path.splitext(fname_base)[0]
        # Every OS has a set of characters which are not valid for use in file names
        fname_base = re.sub('[\\/*?:<>|\x00-\x1f]+', '-', fname_base)
        if len(fname_base) > 0:
            if fname_base[0] == '-': fname_base = 'm' + fname_base[1:]
            elif fname_base[0] == '+': fname_base = 'p' + fname_base[1:]

        if len(self.sections) == 1:
            fname_base = "{:s}_{:s}".format(fname_base, pretty_ident)
        else:
            if snum >= 0:
                snum_str = str(snum)
            else:
                snum_str = 'm' + str(-snum)
            fname_base = "{:s}_{:s}{:s}".format(fname_base, pretty_ident, snum_str)
        if len(block_fpath) > 0:
            fname_base = block_fpath + '/' + fname_base
        return fname_base

    def exportXMLTree(self, simple_bin=False):
        """ Export the block properties into XML tree

        All sections are exported by this method.
        """
        ver = self.vi.getFileVersion()
        pretty_ident = getPrettyStrFromRsrcType(self.ident)

        elem = ET.Element(pretty_ident)
        if len(self.full_name) > 0:
            comment_elem = ET.Comment(" {:s} ".format(self.full_name))
            elem.append(comment_elem)
        for snum, section in self.sections.items():
            section_elem = ET.SubElement(elem,"Section")
            section_elem.set("Index", str(snum))

            if self.vi.ftype == LVrsrcontainer.FILE_FMT_TYPE.LLB or isSmallerVersion(ver, 8,0,0):
                # Vefied to be non-zero in LV7.1 files, is zero in LV8.6 files
                block_int5 = section.start.int5
            else:
                block_int5 = None

            fname_base = self.exportFilesBase(snum, section)

            if section.name_obj is not None:
                subelem = ET.SubElement(section_elem,"NameObject")

                section.name_obj.exportXML(subelem, fname_base)

            elif section.name_text is not None:
                section_elem.set("Name", section.name_text.decode(self.vi.textEncoding))
            if block_int5 is not None:
                section_elem.set("Int5", "0x{:08X}".format(block_int5))

            if not simple_bin:
                # The rest of the data may be set by a block-specific (overloaded) method
                self.exportXMLSection(section_elem, snum, section, fname_base)
            else:
                # Call base function, not the overloaded version for specific block
                # And _really_ use the base Block, not super() - that doesn't guarantee
                # we get raw form, plus Block itself doesn't have this in superclass.
                Block.exportXMLSection(self, section_elem, snum, section, fname_base)

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
        if self.size is None:
            d = bldata.read(31).hex()
            if len(d) == 2*31:
                d += ".."
        elif self.size > 32:
            d = bldata.read(31).hex() + ".."
        else:
            d = bldata.read(32).hex()
        return "<" + self.__class__.__name__ + "(" + d + ")>"


class CompleteBlock(Block):
    """ Block with support of parse fails and variable coding method

    Provides a standard handling of exceptions for blocks.
    Allows a block to be plain or encoded, depending on LV version.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.default_block_coding = BLOCK_CODING.NONE

    def createSection(self):
        section = super().createSection()
        section.parse_failed = False
        section.storage_format = "inline"
        return section

    def setDefaultEncoding(self):
        self.default_block_coding = BLOCK_CODING.NONE

    def parseRSRCSectionData(self, section_num, bldata):
        raise NotImplementedError("Parsing the block is not implemented")

    def parseRSRCData(self, section_num, bldata):
        section = self.sections[section_num]
        section.parse_failed = False
        startpos = bldata.tell()
        bldata.seek(0, io.SEEK_END)
        totlen = bldata.tell()
        bldata.seek(startpos)
        try:
            self.parseRSRCSectionData(section_num, bldata)
        except Exception as e:
            section.parse_failed = True
            eprint("{:s}: Warning: Block {} section {} parse exception: {}."\
                .format(self.vi.src_fname,self.ident,section_num,str(e)))
            #raise # useful for debug
        if bldata.tell() < totlen:
            section.parse_failed = True
            eprint("{:s}: Warning: Block {} section {} size is {} and does not match parsed size {}"\
              .format(self.vi.src_fname, self.ident, section_num, totlen, bldata.tell()))
        if section.parse_failed:
            bldata.seek(startpos)
            Block.parseRSRCData(self, section_num, bldata)
        pass

    def initWithRSRCLate(self):
        self.setDefaultEncoding()
        super().initWithRSRCLate()

    def prepareRSRCData(self, section_num):
        raise NotImplementedError("Re-creating binary is not implemented")

    def updateSectionData(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        # Do not re-create raw data if parsing failed and we still have the original
        if (section.parse_failed and self.hasRawData(section_num)):
            eprint("{:s}: Warning: Block {} section {} left in original raw form, without re-building"\
              .format(self.vi.src_fname,self.ident,section_num))
            return

        data_buf = b''
        try:
            data_buf = self.prepareRSRCData(section_num)
        except Exception as e:
            section.parse_failed = True
            eprint("{:s}: Warning: Block {} section {} binary prepare exception: {}."\
                .format(self.vi.src_fname,self.ident,section_num,str(e)))
            #raise # useful for debug

        # Do not re-create raw data if parsing failed and we still have the original
        if section.parse_failed:
            if not self.hasRawData(section_num):
                raise RuntimeError("Block {} section {} could not prepare binary data"\
                    .format(self.ident,section_num))
            else:
                eprint("{:s}: Warning: Block {} section {} left in original raw form, without re-building"\
                  .format(self.vi.src_fname,self.ident,section_num))
            return

        exp_whole_len = self.expectedRSRCSize(section_num)
        if (exp_whole_len is not None) and (len(data_buf) != exp_whole_len):
            raise RuntimeError("Block {} section {} generated binary data of invalid size ({} instead of {})"\
              .format(self.ident, section_num, len(data_buf), exp_whole_len))

        self.setData(data_buf, section_num=section_num)

    def expectedRSRCSize(self, section_num):
        return None

    def initWithXMLSectionData(self, section, section_elem):
        raise NotImplementedError("Inintialization from XML is not implemented")

    def initWithImageSectionData(self, section, section_elem, image, block_fh):
        raise NotImplementedError("Inintialization from Image is not implemented")

    def initWithXMLSection(self, section, section_elem):
        snum = section.start.section_idx
        section.parse_failed = False
        fmt = section_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For Block {} section {:d}, reading inline XML data"\
                  .format(self.vi.src_fname,self.ident,snum))
            self.initWithXMLSectionData(section, section_elem)
        elif fmt == "xml": # Format="xml" - the content is stored in a separate XML file
            if (self.po.verbose > 2):
                print("{:s}: For Block {} section {:d}, reading separate XML file '{}'"\
                  .format(self.vi.src_fname,self.ident,snum,section_elem.get("File")))
            xml_path = os.path.dirname(self.vi.src_fname)
            if len(xml_path) > 0:
                xml_fname = xml_path + '/' + section_elem.get("File")
            else:
                xml_fname = section_elem.get("File")
            try:
                tree = ET.parse(xml_fname)
            except Exception as e:
                section.parse_failed = True
                raise RuntimeError("XML file '{}' parsing exception: {}".format(section_elem.get("File"),str(e)))
            self.initWithXMLSectionData(section, tree.getroot())
        elif fmt == "png": # Format="png" - the content is stored separately as image file
            if (self.po.verbose > 2):
                print("{:s}: For Block {} section {:d}, reading PNG file '{}'"\
                  .format(self.vi.src_fname,self.ident,snum,section_elem.get("File")))
            bin_path = os.path.dirname(self.vi.src_fname)
            if len(bin_path) > 0:
                bin_fname = bin_path + '/' + section_elem.get("File")
            else:
                bin_fname = section_elem.get("File")
            with open(bin_fname, "rb") as png_fh:
                image = Image.open(png_fh)
                image.getdata() # to make sure the file gets loaded; everything is lazy nowadays
                self.initWithImageSectionData(section, section_elem, image, png_fh)
        else:
            section.parse_failed = True
            Block.initWithXMLSection(self, section, section_elem)
        pass

    def initWithXMLLate(self):
        currEncoding = self.default_block_coding
        self.setDefaultEncoding()
        if currEncoding != self.default_block_coding:
            # This block changed its expected encoding; we may need to update raw data
            for snum in self.sections:
                if not self.hasRawData(section_num=snum):
                    continue
                coded_data = self.getData(section_num=snum, use_coding=currEncoding)
                if coded_data is not None:
                    self.setData(coded_data.read(), section_num=snum)
        super().initWithXMLLate()

    def exportXMLSectionData(self, section_elem, section_num, section, fname_base):
        raise NotImplementedError("Export of XML is not implemented")

    def exportImageSectionData(self, section_elem, block_fh, section_num, section, fname_base):
        raise NotImplementedError("Export of image is not implemented")

    def exportXMLSection(self, section_elem, section_num, section, fname_base):
        self.parseData(section_num=section_num)

        storage_format = section.storage_format
        if section.parse_failed:
            storage_format = "raw"

        try:
            if storage_format == "inline":
                if (self.po.verbose > 1):
                    print("{}: Writing inline XML for block {} section {:d}"\
                      .format(self.vi.src_fname, self.ident, section_num))

                self.exportXMLSectionData(section_elem, section_num, section, fname_base)
                section_elem.set("Format", "inline")
            elif storage_format == "xml":
                if (self.po.verbose > 1):
                    print("{}: Writing separate XML for block {} section {:d}"\
                      .format(self.vi.src_fname, self.ident, section_num))

                block_fname = "{:s}.{:s}".format(fname_base,"xml")

                root = ET.Element("SectionRoot")
                self.exportXMLSectionData(root, section_num, section, fname_base)

                ET.pretty_element_tree_heap(root)

                tree = ET.ElementTree(root)
                with open(block_fname, "wb") as block_fh:
                    if (self.po.verbose > 1):
                        print("{}: Storing block {} section {:d} xml in '{}'"\
                          .format(self.vi.src_fname,self.ident,section_num,block_fname))
                    tree.write(block_fh, encoding='utf-8', xml_declaration=True)

                section_elem.set("Format", "xml")
                section_elem.set("File", os.path.basename(block_fname))
            elif storage_format == "png":
                if (self.po.verbose > 1):
                    print("{}: Writing Image file for block {} section {:d}"\
                      .format(self.vi.src_fname, self.ident, section_num))

                block_fname = "{:s}.{:s}".format(fname_base,"png")

                with open(block_fname, "wb") as block_fh:
                    if (self.po.verbose > 1):
                        print("{}: Storing block {} section {} image in '{}'"\
                          .format(self.vi.src_fname,self.ident,section_num,block_fname))
                    self.exportImageSectionData(section_elem, block_fh, section_num, section, fname_base)

                section_elem.set("Format", "png")
                section_elem.set("File", os.path.basename(block_fname))
            elif storage_format == "raw":
                Block.exportXMLSection(self, section_elem, section_num, section, fname_base)
            else:
                raise NotImplementedError("Unknown block storage format")
        except Exception as e:
            eprint("{:s}: Warning: Block {} section {} XML export exception: {}."\
                .format(self.vi.src_fname,self.ident,section_num,str(e)))
            #raise # useful for debug
            Block.exportXMLSection(self, section_elem, section_num, section, fname_base)
            return

    def getData(self, section_num=None, use_coding=None):
        if use_coding is None:
            use_coding = self.default_block_coding
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=None):
        if use_coding is None:
            use_coding = self.default_block_coding
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)


class VarCodingBlock(Block):
    """ Block with variable coding method

    Allows a block to be plain or encoded, depending on LV version.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.default_block_coding = BLOCK_CODING.NONE

    def setDefaultEncoding(self):
        ver = self.vi.getFileVersion()
        if isGreaterOrEqVersion(ver, 6,0,0):
            self.default_block_coding = BLOCK_CODING.ZLIB
        else:
            self.default_block_coding = BLOCK_CODING.NONE

    def initWithRSRCLate(self):
        self.setDefaultEncoding()
        super().initWithRSRCLate()

    def initWithXMLLate(self):
        currEncoding = self.default_block_coding
        self.setDefaultEncoding()
        if currEncoding != self.default_block_coding:
            # This block changed its expected encoding; we may need to update raw data
            for snum in self.sections:
                if not self.hasRawData(section_num=snum):
                    continue
                coded_data = self.getData(section_num=snum, use_coding=currEncoding)
                if coded_data is not None:
                    self.setData(coded_data.read(), section_num=snum)
        super().initWithXMLLate()

    def getData(self, section_num=None, use_coding=None):
        if use_coding is None:
            use_coding = self.default_block_coding
        bldata = super().getData(section_num=section_num, use_coding=use_coding)
        return bldata

    def setData(self, data_buf, section_num=None, use_coding=None):
        if use_coding is None:
            use_coding = self.default_block_coding
        super().setData(data_buf, section_num=section_num, use_coding=use_coding)


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

    def getValue(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]
        self.parseData(section_num=section_num)
        return section.value


class MUID(SingleIntBlock):
    """ Map Unique Identifier

    Stores UID of LoadRefMap object.
    Equal to the maximum uid property value used in the vi file.
    Every time any object within the VI changes, it receives a new uid value.
    """
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


class FPTD(CompleteBlock):
    """ Front Panel Type for DataLog

    Contains list of types, with exactly one
    type inside. The type points to DataLog
    TypeDesc.

    The content is different for pre-LV7.0 format VIs.
    There, the type definition seem to be stored directly?
    """
    def createSection(self):
        section = super().createSection()
        section.value = None
        return section

    def isSingleTDIndex(self):
        """ Returns whether the block contains a single type index in consolidated list.

        The block contains single TD index for LV 8.6.0, it does not for LV6.0.1
        """
        ver = self.vi.getFileVersion()
        return isGreaterOrEqVersion(ver, 7,0,0)

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]
        section.value = None

        if self.isSingleTDIndex():
            section.value = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        else:
            #TODO currently we do not know how to parse old version of FPTD block
            raise NotImplementedError("Parsing LV6 and older form of the block is not implemented")
        pass

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]

        data_buf = b''
        if self.isSingleTDIndex():
            data_buf += int(section.value).to_bytes(2, byteorder='big', signed=False)
        else:
            #TODO currently we do not know how to parse old version of FPTD block
            raise NotImplementedError("Preparing data for LV6 and older form of the block is not implemented")
        return data_buf

    def expectedRSRCSize(self, section_num):
        if self.isSingleTDIndex():
            exp_whole_len = 2
        else:
            exp_whole_len = None
        return exp_whole_len

    def initWithXMLSectionData(self, section, section_elem):
        section.content = []

        for subelem in section_elem:
            if (subelem.tag == "NameObject"):
                pass # Items parsed somewhere else
            elif (subelem.tag == "TypeDesc"):
                val = int(subelem.get("TypeID"), 0)
                section.value = val
            else:
                raise AttributeError("Section contains unexpected tag")
        pass

    def exportXMLSectionData(self, section_elem, section_num, section, fname_base):
        if self.isSingleTDIndex():
            subelem = ET.SubElement(section_elem,"TypeDesc")

            subelem.set("TypeID", "{:d}".format(section.value))
        else:
            #TODO currently we do not know how to parse old version of FPTD block
            raise NotImplementedError("Exporting XML for LV6 and older form of the block is not implemented")
        pass

    def getValue(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]
        self.parseData(section_num=section_num)
        return section.value


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


class FLAG(SingleIntBlock):
    def createSection(self):
        section = super().createSection()
        section.byteorder = 'big'
        section.size = 1
        section.base = 16
        section.signed = False
        return section


class CONP(CompleteBlock):
    """ Connector Port Type Map

    Contains list of types. For VIs, with exactly one
    type inside; for LLBs it stores more.
    The Type Descriptor stored is of type Function and contains a list
    of types used in connectors bound to terminal point on the VI icon.
    In LV7.1 the block is CPTM.
    """
    def createSection(self):
        section = super().createSection()
        section.value = None
        return section

    def isSingleTDIndex(self):
        return self.vi.ftype != LVrsrcontainer.FILE_FMT_TYPE.LLB

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]
        section.value = None

        if self.isSingleTDIndex():
            section.value = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        else:
            #TODO currently we do not know how to parse complex form of CONP block
            raise NotImplementedError("Parsing complex form of the block is not implemented")
        pass

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]

        data_buf = b''
        if self.isSingleTDIndex():
            data_buf += int(section.value).to_bytes(2, byteorder='big', signed=False)
        else:
            #TODO currently we do not know how to parse complex form of CONP block
            raise NotImplementedError("Preparing binary data for complex form of the block is not implemented")
        return data_buf

    def expectedRSRCSize(self, section_num):
        if self.isSingleTDIndex():
            exp_whole_len = 2
        else:
            exp_whole_len = None
        return exp_whole_len

    def initWithXMLSectionData(self, section, section_elem):
        section.content = []
        for subelem in section_elem:
            if (subelem.tag == "NameObject"):
                pass # Items parsed somewhere else
            elif (subelem.tag == "TypeDesc"):
                val = int(subelem.get("TypeID"), 0)
                section.value = val
            else:
                raise AttributeError("Section contains unexpected tag")

    def exportXMLSectionData(self, section_elem, section_num, section, fname_base):
        if self.isSingleTDIndex():
            subelem = ET.SubElement(section_elem,"TypeDesc")

            subelem.set("TypeID", "{:d}".format(section.value))
        else:
            #TODO currently we do not know how to parse complex form of CONP block
            raise NotImplementedError("Exporting XML for complex form of the block is not implemented")
        pass

    def getValue(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]
        self.parseData(section_num=section_num)
        return section.value


class CPTM(Block):
    """ Connector Port Type Map

    Contains list of types.
    """
    pass


class CPC2(CONP):
    """ Connector Port Content Type v2

    Contains list of types. For VIs, with exactly one
    type inside; for LLBs it stores more.
    The Type Descriptor stored is of type Function and contains a list
    of types used in connectors bound to terminal point on the VI icon.

    The type pointed is also used for calculating
    salt for Block Diagram password.
    In LV7.1 the block is CPCT.
    """
    pass


class CPCT(Block):
    """ Connector Port Content Type

    Contains list of types.
    """
    pass


class CPD2(CONP):
    """ Connector Port DI v2

    Contains list of types. For VIs, with exactly one
    type inside; for LLBs it stores more.
    The Type Descriptor stored is related to CONP and CPC2.

    In LV7.1 the block is CPDI.
    """
    pass


class CPDI(Block):
    """ Connector Port DI

    Contains list of types.
    The Type Descriptor stored is related to CPTM and CPCT.
    """
    pass


class SingleStringBlock(CompleteBlock):
    """ Block with raw data representing single string value

    This base class is to be used as parser for several blocks.
    The blocks are assumed to store a text string; but if binary data is found
    instead, then the block is stored as sting of hex values.
    """
    def createSection(self):
        section = super().createSection()
        # Amount of bytes the size of this string uses
        section.size_len = 1
        section.content = []
        section.eoln = '\r\n'
        return section

    def setDefaultEncoding(self):
        self.default_block_coding = BLOCK_CODING.NONE

    @staticmethod
    def isBinaryString(content):
        text_chars = len(re.findall(b"[\r\n\t\x20-\xfe]", content))
        binary_chars = len(content) - text_chars
        if len(content) > 4:
            return binary_chars > len(content) / 10
        else:
            return binary_chars > 0

    @staticmethod
    def parseSingleBinaryString(content):
        remain = content
        chunks = []
        while len(remain) > 0:
            match = re.search(b"[\t\x20-\xfe]{6}", remain)
            if not match:
                chunk = SimpleNamespace()
                chunk.storage = "hex"
                chunk.content = remain
                chunks.append(chunk)
                break
            hex_end = match.start()
            if hex_end > 0:
                chunk = SimpleNamespace()
                chunk.storage = "hex"
                chunk.content = remain[:hex_end]
                chunks.append(chunk)
            str_end = match.end()
            if str_end > hex_end: # always true
                chunk = SimpleNamespace()
                chunk.storage = "text"
                chunk.content = remain[hex_end:str_end]
                chunks.append(chunk)
            remain = remain[str_end:]
        smaller_chunks = []
        for chunk in chunks:
            if chunk.storage != "hex" or len(chunk.content) <= 512:
                smaller_chunks.append(chunk)
                continue
            num_parts = (len(chunk.content) + 511) // 512
            part_len = (len(chunk.content) + num_parts - 1) // num_parts
            remain = chunk.content
            for i in range(num_parts):
                part_chunk = SimpleNamespace()
                part_chunk.storage = chunk.storage
                part_chunk.content = remain[:part_len]
                smaller_chunks.append(part_chunk)
                remain = remain[part_len:]

        return smaller_chunks

    @staticmethod
    def parseSingleTextString(content, textEncoding):
        # Need to divide decoded string, as single \n or \r may be there only due to the endoding
        # Also, ignore encoding errors - some strings are encoded with exotic code pages, as they
        # just use native code page of the operating system (which in case of Windows, varies).
        content_str = content.decode(textEncoding, errors="ignore")
        # Somehow, these strings can contain various EOLN chars, even if \r\n is the most often used one
        # To avoid creating different files from XML, we have to detect the proper EOLN to use
        if content_str.count('\r\n') > content_str.count('\n\r'):
            eoln = '\r\n'
        elif content_str.count('\n\r') > 0:
            eoln = '\n\r'
        elif content_str.count('\n') > content_str.count('\r'):
            eoln = '\n'
        elif content_str.count('\r') > 0:
            eoln = '\r'
        else:
            # Set the most often used one as default
            eoln = '\r\n'

        chunks = []
        for line in content_str.split(eoln):
            chunk = SimpleNamespace()
            chunk.storage = "text"
            chunk.content = line.encode(textEncoding)
            chunks.append(chunk)
        return chunks, eoln

    @staticmethod
    def parseSingleString(content, textEncoding):
        if SingleStringBlock.isBinaryString(content):
            chunks = SingleStringBlock.parseSingleBinaryString(content)
            eoln = ''
        else:
            chunks, eoln = SingleStringBlock.parseSingleTextString(content, textEncoding)
        return chunks, eoln

    @staticmethod
    def prepareSingleString(chunks, eoln, textEncoding):
        return eoln.encode(textEncoding).join(chunk.content for chunk in chunks)

    @staticmethod
    def initWithXMLSingleStringChunk(chunk_elem, textEncoding):
        chunk = SimpleNamespace()
        storage = chunk_elem.get("Storage")
        if storage is None:
            chunk.storage = "text"
        elif storage in ("hex", "text",):
            chunk.storage = storage
        else:
            raise AttributeError("Section contains string with unexpected storage type")
        if chunk.storage == "hex":
            line = chunk_elem.text
            if line is not None:
                line = bytes.fromhex(line)
        else:
            line = chunk_elem.text
            if line is not None:
                line = line.encode(textEncoding)
        if line is not None:
            chunk.content = line
        else:
            chunk.content = b''
        return chunk

    @staticmethod
    def initWithXMLSingleString(string_elem, textEncoding):
        chunks = []
        if string_elem.find("Chunk") is None:
            # No chunks - the whole string is stored directly
            chunk = SingleStringBlock.initWithXMLSingleStringChunk(string_elem, textEncoding)
            chunks.append(chunk)
            return chunks, None
        eoln = string_elem.get("EOLN").replace("CR",'\r').replace("LF",'\n')
        for i, subelem in enumerate(string_elem):
            if (subelem.tag == "Chunk"):
                chunk = SingleStringBlock.initWithXMLSingleStringChunk(subelem, textEncoding)
                chunks.append(chunk)
            else:
                pass # No exception - we may want to add more tags parsed elswhere
        return chunks, eoln

    @staticmethod
    def exportXMLSingleString(chunks, eoln, textEncoding, string_elem):
        # If we have multiple chunks, store the EOLN used as an attribute
        if len(chunks) > 1:
            EOLN_type = eoln.replace('\r',"CR").replace('\n',"LF")
            string_elem.set("EOLN", "{:s}".format(EOLN_type))

        for chunk in chunks:
            if len(chunks) > 1:
                subelem = ET.SubElement(string_elem,"Chunk")
            else:
                subelem = string_elem # If only single chunk, then store it directly
            if chunk.storage == "text":
                pretty_string = chunk.content.decode(textEncoding)
            elif chunk.storage == "hex":
                pretty_string = chunk.content.hex()
                subelem.set("Storage", "{:s}".format(chunk.storage))
            else:
                raise AttributeError("Unsupported storage type")

            subelem.text = pretty_string
        pass

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]
        section.eoln = '\r\n'
        section.content = []

        string_len = int.from_bytes(bldata.read(section.size_len), byteorder='big', signed=False)
        content = bldata.read(string_len)
        chunks, eoln = self.parseSingleString(content, self.vi.textEncoding)
        if eoln is not None:
            section.eoln = eoln
        section.content.extend(chunks)

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]
        data_buf  = b''
        # There is no need to decode while joining
        content_bytes = self.prepareSingleString(section.content, section.eoln, self.vi.textEncoding)
        data_buf += len(content_bytes).to_bytes(section.size_len, byteorder='big', signed=False)
        data_buf += content_bytes
        return data_buf

    def expectedRSRCSize(self, section_num):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        exp_whole_len = section.size_len
        exp_whole_len += sum(len(chunk.content) for chunk in section.content)
        exp_whole_len += len(section.eoln) * max(len(section.content)-1,0)
        return exp_whole_len

    def initWithXMLSectionData(self, section, section_elem):
        section.eoln = '\r\n'
        section.content = []

        for i, subelem in enumerate(section_elem):
            if (subelem.tag == "NameObject"):
                pass # Items parsed somewhere else
            elif (subelem.tag == "String"):
                chunks, eoln = self.initWithXMLSingleString(subelem, self.vi.textEncoding)
                if eoln is not None:
                    section.eoln = eoln
                section.content.extend(chunks)
            else:
                raise AttributeError("Section contains unexpected tag")
        pass

    def exportXMLSectionData(self, section_elem, section_num, section, fname_base):
        string_elem = ET.SubElement(section_elem,"String")
        self.exportXMLSingleString(section.content, section.eoln, self.vi.textEncoding, string_elem)
        pass


class DLGH(SingleStringBlock):
    """ Dialog HTML
    """
    def createSection(self):
        section = super().createSection()
        section.size_len = 1
        return section


class ERRH(SingleStringBlock):
    """ Error HTML
    """
    def createSection(self):
        section = super().createSection()
        section.size_len = 1
        return section


class HLPT(SingleStringBlock):
    """ Help Tag
    """
    def createSection(self):
        section = super().createSection()
        section.size_len = 4
        return section

class MItm(SingleStringBlock):
    """ M. Item
    """
    def createSection(self):
        section = super().createSection()
        section.size_len = 4
        section.prop1 = 0
        section.prop2 = 0
        return section

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]
        section.content = []
        section.prop1 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.prop2 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        super().parseRSRCSectionData(section_num, bldata)

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]
        data_buf = b''
        data_buf += int(section.prop1).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.prop2).to_bytes(4, byteorder='big', signed=False)
        data_buf += super().prepareRSRCData(section_num)
        return data_buf

    def expectedRSRCSize(self, section_num):
        section = self.sections[section_num]
        exp_whole_len = 4
        exp_whole_len += 4
        exp_whole_len += super().expectedRSRCSize(section_num)
        return exp_whole_len

    def initWithXMLSectionData(self, section, section_elem):
        tmpprop = section_elem.get("Prop1")
        if tmpprop is not None:
            section.prop1 = int(tmpprop, 0)
        tmpprop = section_elem.get("Prop2")
        if tmpprop is not None:
            section.prop2 = int(tmpprop, 0)
        super().initWithXMLSectionData(section, section_elem)

    def exportXMLSectionData(self, section_elem, section_num, section, fname_base):
        section_elem.set("Prop1", "{:d}".format(section.prop1))
        section_elem.set("Prop2", "{:d}".format(section.prop2))
        super().exportXMLSectionData(section_elem, section_num, section, fname_base)


class NODH(SingleStringBlock):
    """ NOD HTML
    """
    def createSection(self):
        section = super().createSection()
        section.size_len = 1
        return section


class NOEG(SingleStringBlock):
    """ NOEG String
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


class TITL(SingleStringBlock):
    """ Title of the file
    """
    def createSection(self):
        section = super().createSection()
        section.size_len = 1
        return section


class STR(SingleStringBlock):
    """ Short String / Input definition?

    This block seem to have different meaning depending on the kind of RSRC file
    it is in. For LLBs, it is just a simple string, like a label. For VIs,
    it contains binary data before the string.
    """
    def createSection(self):
        section = super().createSection()
        section.size_len = 1
        return section

    def isSingleShortString(self):
        ver = self.vi.getFileVersion()
        return (self.vi.ftype == LVrsrcontainer.FILE_FMT_TYPE.LLB) or isSmallerVersion(ver, 8,0,0)

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]
        section.eoln = '\r\n'
        section.content = []

        if self.isSingleShortString():
            super().parseRSRCSectionData(section_num, bldata)
        else: # File format is unknown
            raise NotImplementedError("No support for parsing the STR data")
        pass

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]
        data_buf  = b''
        if self.isSingleShortString():
            data_buf += super().prepareRSRCData(section_num)
        else: # File format is unknown
            raise NotImplementedError("No support for preparing data for the STR data")
        return data_buf


class StringListBlock(SingleStringBlock):
    """ Generic List of Strings
    """
    def createSection(self):
        section = super().createSection()
        del(section.eoln) # we overload all the uses, and now store that within .content
        section.count_len = 2
        section.size_len = 1
        section.padding_len = 1
        return section

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]
        section.content = []

        count = int.from_bytes(bldata.read(section.count_len), byteorder='big', signed=False)
        for i in range(count):
            strEntry = SimpleNamespace()
            strEntry.eoln = '\r\n'
            strEntry.chunks = []
            section.content.append(strEntry)

            string_len = int.from_bytes(bldata.read(section.size_len), byteorder='big', signed=False)
            content_bytes = bldata.read(string_len)
            chunks, eoln = self.parseSingleString(content_bytes, self.vi.textEncoding)
            # Handle padding
            uneven_len = (len(content_bytes)+section.size_len) % section.padding_len
            if uneven_len > 0:
                bldata.read(section.padding_len - uneven_len)

            if eoln is not None:
                strEntry.eoln = eoln
            strEntry.chunks = chunks
        pass

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]
        data_buf  = b''
        data_buf += len(section.content).to_bytes(section.count_len, byteorder='big', signed=False)
        for strEntry in section.content:
            # There is no need to decode while joining
            content_bytes = self.prepareSingleString(strEntry.chunks, strEntry.eoln, self.vi.textEncoding)
            data_buf += len(content_bytes).to_bytes(section.size_len, byteorder='big', signed=False)
            data_buf += content_bytes
            uneven_len = (len(content_bytes)+section.size_len) % section.padding_len
            if uneven_len > 0:
                data_buf += b'\0' * (section.padding_len - uneven_len)
        return data_buf

    def expectedRSRCSize(self, section_num):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        exp_whole_len = 0
        exp_whole_len += section.count_len
        for strEntry in section.content:
            string_len = section.size_len
            string_len += sum(len(chunk.content) for chunk in strEntry.chunks)
            string_len += len(strEntry.eoln) * max(len(strEntry.chunks)-1,0)
            uneven_len = string_len % section.padding_len
            if uneven_len > 0:
                string_len += section.padding_len - uneven_len
            exp_whole_len += string_len
        return exp_whole_len

    def initWithXMLSectionData(self, section, section_elem):
        section.eoln = '\r\n'
        section.content = []

        for i, subelem in enumerate(section_elem):
            if (subelem.tag == "NameObject"):
                pass # Items parsed somewhere else
            elif (subelem.tag == "String"):
                strEntry = SimpleNamespace()
                strEntry.eoln = '\r\n'
                strEntry.chunks = []
                section.content.append(strEntry)
                chunks, eoln = self.initWithXMLSingleString(subelem, self.vi.textEncoding)
                if eoln is not None:
                    strEntry.eoln = eoln
                strEntry.chunks = chunks
            else:
                raise AttributeError("Section contains unexpected tag")
        pass

    def exportXMLSectionData(self, section_elem, section_num, section, fname_base):
        for strEntry in section.content:
            string_elem = ET.SubElement(section_elem,"String")
            self.exportXMLSingleString(strEntry.chunks, strEntry.eoln, self.vi.textEncoding, string_elem)
        pass


class CPST(StringListBlock):
    """ C. P. Strings
    """
    def createSection(self):
        section = super().createSection()
        section.count_len = 4
        section.size_len = 1
        section.padding_len = 1
        return section


class DNmsh(StringListBlock):
    """ D. Name Strings List
    """
    def createSection(self):
        section = super().createSection()
        section.count_len = 2
        section.size_len = 1
        section.padding_len = 1
        return section


class HDbsh(StringListBlock):
    """ Help Database item

    Stores list of strings, though with exactly one string inside.
    """
    def createSection(self):
        section = super().createSection()
        section.count_len = 4
        section.size_len = 4
        section.padding_len = 4
        return section


class LSTsh(StringListBlock):
    """ Short Strings List
    """
    def createSection(self):
        section = super().createSection()
        section.count_len = 4
        section.size_len = 4
        section.padding_len = 1
        return section

    def getVarPadding(self):
        # In some versions of LV, this block has padding
        # No padding in LV14.0
        # but lvapp from LV11 which has vers set to LV0.0 does have it
        # LVRS files which don't have version block at all, go without padding
        # Some MNU files from LV14 also have no vers block and no padding
        if self.vi.ftype == LVrsrcontainer.FILE_FMT_TYPE.RFilesService:
            return 1
        vers = self.vi.get('vers')
        if vers is None:
            return 1
        ver = self.vi.getFileVersion()
        if isSmallerVersion(ver, 11,0,0,0):
            return 4
        return 1

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]
        section.padding_len = self.getVarPadding()
        super().parseRSRCSectionData(section_num, bldata)

    def initWithXMLLate(self):
        for snum in self.sections:
            section = self.sections[snum]
            section.padding_len = self.getVarPadding()
        super().initWithXMLLate()


class STRsh(StringListBlock):
    """ Short Strings List
    """
    def createSection(self):
        section = super().createSection()
        section.count_len = 2
        section.size_len = 1
        section.padding_len = 1
        return section


class FDFL(Block):
    """ FDFL Strings

    Pairs text names and lists of 4-byte identifiers.
    """
    def createSection(self):
        section = super().createSection()
        return section


class LinkObjRefs(CompleteBlock):
    """ LinkObj Identity Refs
    """
    def createSection(self):
        section = super().createSection()
        section.ident = b'UNKN'
        section.content = []
        section.unk1 = b''
        section.unk2 = b''
        return section

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]
        ver = self.vi.getFileVersion()
        # nextLinkInfo: 1-root item, 2-list continues, 3-list end
        nextLinkInfo = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        if nextLinkInfo != 1:
            raise AttributeError("List of LinkObjects incorrectly tarted with {}".format(nextLinkInfo))
        section.ident = bldata.read(4)
        if isSmallerVersion(ver, 14,0,0,3):
            section.unk1 = readPStr(bldata, 2, self.po)
            wordlen = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            section.unk2 = bldata.read(2 * wordlen)
        else:
            section.unk1 = b''
            section.unk2 = b''
        # The count isn't that important as there's "next" info before each item
        count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        while True:
            nextLinkInfo = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            if nextLinkInfo != 2:
                break
            ctnrstart = bldata.tell()
            lnkobj_ident = bldata.read(4)
            client = LVlinkinfo.newLinkObject(self.vi, section.ident, lnkobj_ident, self.po)
            section.content.append(client)
            bldata.seek(ctnrstart)
            client.parseRSRCData(bldata)
        if nextLinkInfo != 3:
            if len(section.content) > 0:
                client = section.content[-1]
                raise AttributeError("List of LinkObjects incorrectly ended with {} after {}".format(nextLinkInfo,client.ident))
            else:
                raise AttributeError("List of LinkObjects incorrectly ended with {} and is empty".format(nextLinkInfo))
        if len(section.content) != count:
            raise AttributeError("List announced {} refs, but had {} instead".format(count,len(section.content)))
        pass

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]
        ver = self.vi.getFileVersion()
        data_buf = b''
        data_buf += int(1).to_bytes(2, byteorder='big', signed=False) # nextLinkInfo
        data_buf += section.ident
        if isSmallerVersion(ver, 14,0,0,3):
            data_buf += preparePStr(section.unk1, 2, self.po)
            data_buf += int(len(section.unk2)/2).to_bytes(2, byteorder='big', signed=False)
            data_buf += section.unk2
        data_buf += len(section.content).to_bytes(4, byteorder='big', signed=False)
        for client in section.content:
            data_buf += int(2).to_bytes(2, byteorder='big', signed=False) # nextLinkInfo
            data_buf += client.prepareRSRCData(start_offs=len(data_buf))
        data_buf += int(3).to_bytes(2, byteorder='big', signed=False) # nextLinkInfo
        return data_buf

    def expectedRSRCSize(self, section_num):
        section = self.sections[section_num]
        ver = self.vi.getFileVersion()
        exp_whole_len = 0
        exp_whole_len += 2 + 4
        if isSmallerVersion(ver, 14,0,0,3):
            str_len = 1 + len(section.unk1)
            uneven_len = str_len % 2
            if uneven_len > 0:
                str_len += 2 - uneven_len
            exp_whole_len += str_len
            exp_whole_len += 2 + len(section.unk2)
        exp_whole_len += 4
        for client in section.content:
            cli_len = client.expectedRSRCSize()
            if cli_len is None:
                return None
            exp_whole_len += 2
            exp_whole_len += cli_len
        exp_whole_len += 2
        return exp_whole_len

    def initWithXMLList(self, section, list_elem):
        section.ident = getRsrcTypeFromPrettyStr(list_elem.tag)
        unk1 = list_elem.get("Unk1")
        if unk1 is not None:
            section.unk1 = unk1.encode(self.vi.textEncoding)
        unk2 = list_elem.get("Unk2")
        if unk2 is not None:
            section.unk2 = bytes.fromhex(unk2)
        for subelem in list_elem:
            lnkobj_ident = getRsrcTypeFromPrettyStr(subelem.tag)
            client = LVlinkinfo.newLinkObject(self.vi, section.ident, lnkobj_ident, self.po)
            section.content.append(client)
            client.initWithXML(subelem)
        pass

    def initWithXMLSectionData(self, section, section_elem):
        section.content = []
        section.unk1 = b''
        section.unk2 = b''

        rootLoaded = False
        for subelem in section_elem:
            if (subelem.tag == "NameObject"):
                pass # Items parsed somewhere else
            elif not rootLoaded:
                # We can have only one root tag
                self.initWithXMLList(section, subelem)
                rootLoaded = True
            else:
                raise AttributeError("Section contains unexpected tag")
        pass

    def initWithXMLLate(self):
        super().initWithXMLLate()
        for snum in self.sections:
            section = self.sections[snum]
            for client in section.content:
                client.initWithXMLLate()
        pass

    def exportXMLSectionData(self, section_elem, section_num, section, fname_base):
        pretty_ident = getPrettyStrFromRsrcType(section.ident)
        list_elem = ET.SubElement(section_elem, pretty_ident)
        if len(section.unk1) > 0 or len(section.unk2) > 0:
            list_elem.set("Unk1", section.unk1.decode(self.vi.textEncoding))
            list_elem.set("Unk2", section.unk2.hex())
        for client in section.content:
            if len(client.full_name) > 0:
                comment_elem = ET.Comment(" {:s} ".format(client.full_name))
                list_elem.append(comment_elem)
            subelem = ET.SubElement(list_elem,"LinkObject")
            client.exportXML(subelem, fname_base)
        pass


class LIfp(LinkObjRefs):
    """ LinkObj Refs for Front Panel
    """
    def createSection(self):
        section = super().createSection()
        section.ident = b'FPHP'
        return section


class LIbd(LinkObjRefs):
    """ LinkObj Refs for Block diagram
    """
    def createSection(self):
        section = super().createSection()
        section.ident = b'BDHP'
        return section


class LIds(LinkObjRefs):
    """ LinkObj Refs for Data Space
    """
    def createSection(self):
        section = super().createSection()
        section.ident = b'VIDS'
        return section


class LIvi(LinkObjRefs):
    """ LinkObj Refs for VI

    Stored dependencies between this VI and other VIs, classes and libraries.
    """
    def createSection(self):
        section = super().createSection()
        section.ident = b'LVIN'
        return section


class DFDS(CompleteBlock):
    """ Default Fill of Data Space
    """
    def createSection(self):
        section = super().createSection()
        section.parse_failed = False
        section.content = []
        return section

    def setDefaultEncoding(self):
        ver = self.vi.getFileVersion()
        # Verified uncompressed in LV7.1.0, ZLIB compressed in LV8.6
        if isGreaterOrEqVersion(ver, 8,0,0):
            self.default_block_coding = BLOCK_CODING.ZLIB
        else:
            self.default_block_coding = BLOCK_CODING.NONE

    def isSpecialDSTMCluster(self, tmItm):
        return (tmItm.flags & (0x0010|0x0020|0x0040|0x0004)) != 0

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]
        TM = self.vi.get_one_of('TM80', 'DSTM')
        ver = self.vi.getFileVersion()

        section.content = []
        if TM is None:
            raise RuntimeError("No type map block to put default data into types")
        elif isGreaterOrEqVersion(ver, 8,0,0,1):
            TypeMap = TM.getTypeMap()

            for tmEntry in TypeMap:
                df = None
                if (tmEntry.flags & 0x0008) != 0 or \
                   (tmEntry.flags & 0x0800) != 0 or \
                   (tmEntry.flags & 0x0400) != 0:
                    continue
                if (tmEntry.flags & 0x2000) != 0 or \
                   (tmEntry.flags & 0x0001) != 0:
                    try:
                        df = LVdatafill.newDataFillObjectWithTD(self.vi, tmEntry.index, tmEntry.flags, tmEntry.td, self.po)
                        section.content.append(df)
                        df.initWithRSRC(bldata)
                    except Exception as e:
                        tdType = tmEntry.td.fullType()
                        raise RuntimeError("Data type {}: {}".format(enumOrIntToName(tdType), str(e)))
                    pass
                elif tmEntry.td.fullType() == TD_FULL_TYPE.Cluster and self.isSpecialDSTMCluster(tmEntry):
                    # This is Special DSTM Cluster
                    try:
                        df = LVdatafill.newSpecialDSTMClusterWithTD(self.vi, tmEntry.index, tmEntry.flags, tmEntry.td, self.po)
                        section.content.append(df)
                        df.initWithRSRC(bldata)
                    except Exception as e:
                        tdType = tmEntry.td.fullType()
                        raise RuntimeError("Special DSTM {}: {}".format(enumOrIntToName(tdType), str(e)))
                    pass
                else:
                    # No default value for this TD
                    pass
        else:
            raise NotImplementedError("No support for the LV7.1 default data format")
        pass

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]
        data_buf = b''
        for df in section.content:
            data_buf += df.prepareRSRCData()
        return data_buf

    def expectedRSRCSize(self, section_num):
        section = self.sections[section_num]
        exp_whole_len = 0
        for df in section.content:
            df_len = df.expectedRSRCSize()
            if df_len is None:
                exp_whole_len = None
                break
            exp_whole_len += df_len
        return exp_whole_len

    def initWithXMLSectionData(self, section, section_elem):
        section.content = []

        for subelem in section_elem:
            if (subelem.tag == "NameObject"):
                continue # Items parsed somewhere else
            if (subelem.tag == "SpecialDSTMCluster"):
                # Special condition for special cluster - its type is just Cluster
                tdType = TD_FULL_TYPE.Cluster
                df = LVdatafill.SpecialDSTMCluster(self.vi, tdType, None, self.po)
            else:
                # Normal processing for everything else
                df = LVdatafill.newDataFillObjectWithTag(self.vi, subelem.tag, self.po)
            df.initWithXML(subelem)
            section.content.append(df)
        pass

    def initWithXMLLate(self):
        super().initWithXMLLate()
        ver = self.vi.getFileVersion()
        TM = self.vi.get_one_of('TM80', 'DSTM')
        if TM is None:
            TypeMap = None
        elif isGreaterOrEqVersion(ver, 8,0,0,1):
            TypeMap = TM.getTypeMap()
        else:
            TypeMap = None
        for snum in self.sections:
            section = self.sections[snum]
            df_idx = 0
            if TypeMap is not None and not section.parse_failed:
                for tmEntry in TypeMap:
                    dtHasFill = False
                    if (tmEntry.flags & 0x0008) != 0 or \
                       (tmEntry.flags & 0x0800) != 0 or \
                       (tmEntry.flags & 0x0400) != 0:
                        continue
                    if (tmEntry.flags & 0x2000) != 0 or \
                       (tmEntry.flags & 0x0001) != 0:
                        dtHasFill = True
                    elif tmEntry.td.fullType() == TD_FULL_TYPE.Cluster and self.isSpecialDSTMCluster(tmEntry):
                        dtHasFill = True
                    else:
                        pass
                    if dtHasFill:
                        if df_idx >= len(section.content):
                            raise AttributeError("Cannot apply Type Map to Default Fill; amounts of types exceed fills")
                        df = section.content[df_idx]
                        df_idx += 1
                        df.setTD(tmEntry.td, tmEntry.index, tmEntry.flags)
                if df_idx != len(section.content):
                    raise AttributeError("Cannot apply Type Map to Default Fill; amounts of types does not match")
            # Now all TDs are propagated
            for df in section.content:
                df.initWithXMLLate()
        pass

    def exportXMLSectionData(self, section_elem, section_num, section, fname_base):
        for df in section.content:
            # For some old LV versions type map index may not make sense; but we are not supporting them ATM
            if df.index >= 0:
                comment_elem = ET.Comment(" Data for TypeID {:d} ".format(df.index))
                section_elem.append(comment_elem)

            subelem = ET.SubElement(section_elem, df.getXMLTagName())

            df.exportXML(subelem, fname_base)
        pass


class GCDI(VarCodingBlock):
    def createSection(self):
        section = super().createSection()
        return section

    def setDefaultEncoding(self):
        self.default_block_coding = BLOCK_CODING.ZLIB


class CGRS(VarCodingBlock):
    """ Conglomerate Resource

    Stores a RSRC file, though the file inside is not stand-alone - has no info section.
    """
    def createSection(self):
        section = super().createSection()
        return section

    def setDefaultEncoding(self):
        self.default_block_coding = BLOCK_CODING.ZLIB


class CPMp(CompleteBlock):
    """ Connection Points Map
    """
    def createSection(self):
        section = super().createSection()
        section.content = []
        section.field1 = 0
        return section

    def setDefaultEncoding(self):
        self.default_block_coding = BLOCK_CODING.NONE

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]

        count = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        section.field1 = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        section.content = []
        for i in range(count):
            value = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            section.content.append(value)

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]

        data_buf = len(section.content).to_bytes(1, byteorder='big')
        data_buf += int(section.field1).to_bytes(1, byteorder='big')
        for value in section.content:
            data_buf += int(value).to_bytes(2, byteorder='big')
        return data_buf

    def expectedRSRCSize(self, section_num):
        section = self.sections[section_num]
        exp_whole_len = 0
        exp_whole_len += 1 + 1
        exp_whole_len += 2 * len(section.content)
        return exp_whole_len

    def initWithXMLSectionData(self, section, section_elem):
        section.content = []

        section.field1 = int(section_elem.get("Field1"), 0)
        if (self.po.verbose > 2):
            print("{:s}: For Block {} section {:d}, reading inline XML data"\
              .format(self.vi.src_fname,self.ident,snum))
        for subelem in section_elem:
            if (subelem.tag == "NameObject"):
                pass # Items parsed somewhere else
            elif (subelem.tag == "TypeDesc"):
                val = int(subelem.get("Flags"), 0)
                if val == -1: val = 65535
                section.content.append(val)
            else:
                raise AttributeError("Section contains unexpected tag")
        pass

    def exportXMLSectionData(self, section_elem, section_num, section, fname_base):
        section_elem.set("Field1", "{:d}".format(section.field1))

        for i, val in enumerate(section.content):
            subelem = ET.SubElement(section_elem,"TypeDesc")

            if val == 65535:
                val = -1
                subelem.set("Flags", "{:d}".format(val))
            else:
                subelem.set("Flags", "0x{:04X}".format(val))

        if len(section.content) == 0:
            comment_elem = ET.Comment("List of TypeDescs is empty")
            section_elem.append(comment_elem)
        pass


class FTAB(Block):
    """ Font Table

    """
    def createSection(self):
        section = super().createSection()
        return section


class HIST(Block):
    """ Changes History

    """
    def createSection(self):
        section = super().createSection()
        return section


class HLPP(Block):
    """ Help Path

    """
    def createSection(self):
        section = super().createSection()
        return section


class LPTH(Block):
    """ L. Path

    """
    def createSection(self):
        section = super().createSection()
        return section


class HLPW(Block):
    """ Help Website URL

    """
    def createSection(self):
        section = super().createSection()
        return section


class SCSR(CompleteBlock):
    """ Syntax Checker Digest

    """
    def createSection(self):
        section = super().createSection()
        section.content = []
        section.flags = 0
        return section

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]
        section.content = []

        section.flags = int.from_bytes(bldata.read(4), byteorder='little', signed=False)
        digest = bldata.read(16)
        section.content.append(digest)

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]

        data_buf = b''
        data_buf += int(section.flags).to_bytes(4, byteorder='little', signed=False)
        for digest in section.content:
            data_buf += digest[:16]
        return data_buf

    def expectedRSRCSize(self, section_num):
        exp_whole_len = 0
        exp_whole_len += 4
        exp_whole_len += 16
        return exp_whole_len

    def initWithXMLSectionData(self, section, section_elem):
        section.content = []

        section.flags = int(section_elem.get("Flags"), 0)
        for subelem in section_elem:
            if (subelem.tag == "NameObject"):
                pass # Items parsed somewhere else
            elif (subelem.tag == "Digest"):
                digest = bytes.fromhex(subelem.text)
                section.content.append(digest)
            else:
                raise AttributeError("Section contains unexpected tag")
        pass

    def exportXMLSectionData(self, section_elem, section_num, section, fname_base):
        section_elem.set("Flags", "0x{:04X}".format(section.flags))
        for digest in section.content:
            subelem = ET.SubElement(section_elem,"Digest")
            subelem.text = digest.hex()
        pass


class DTHP(CompleteBlock):
    """ Data Types for Heap

        Defines Type Descriptors used within Heaps (FP and BD).
        In LV8.0.0.1 and newer, the block only contains starting index and count
        within the VCTP section of the slice which is used in Heaps. The slice
        used by heaps is always at end of VCTP - so index + count from this section
        is actually equal to total amount of entries stored in VCTP.
    """
    def createSection(self):
        section = super().createSection()
        section.indexShift = 0
        section.tdCount = 0
        section.content = []
        return section

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]
        ver = self.vi.getFileVersion()
        section.indexShift = 0
        section.tdCount = 0
        section.content = []

        if isGreaterOrEqVersion(ver, 8,0,0,1):
            section.tdCount = readVariableSizeFieldU2p2(bldata)
            # If there is no count provided, then there is no shift
            # LV14 writes it like this; though it doesn't support this while reading
            # it reads the non existing value anyway, which really reads padding
            if section.tdCount > 0:
                section.indexShift = readVariableSizeFieldU2p2(bldata)
        else:
            #TODO make support for the 7.1 format
            raise NotImplementedError("Parsing the block from LV7.1 and older is not implemented")
        pass

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]
        ver = self.vi.getFileVersion()

        data_buf = b''
        if isGreaterOrEqVersion(ver, 8,0,0,1):
            data_buf += prepareVariableSizeFieldU2p2(section.tdCount)
            if section.tdCount > 0:
                data_buf += prepareVariableSizeFieldU2p2(section.indexShift)
        else:
            #TODO make support for the 7.1 format
            raise NotImplementedError("Preparing binary data for LV7.1 and older is not implemented")
        return data_buf

    def expectedRSRCSize(self, section_num):
        section = self.sections[section_num]
        ver = self.vi.getFileVersion()

        if isGreaterOrEqVersion(ver, 8,0,0,1):
            exp_whole_len = 0
            exp_whole_len += 2
            if section.tdCount > 0:
                exp_whole_len += 2
        else:
            exp_whole_len = None
        return exp_whole_len

    def initWithXMLSectionData(self, section, section_elem):
        section.content = []

        for subelem in section_elem:
            if (subelem.tag == "NameObject"):
                pass # Items parsed somewhere else
            elif (subelem.tag == "TypeDescSlice"):
                section.indexShift = int(subelem.get("IndexShift"), 0)
                section.tdCount = int(subelem.get("Count"), 0)
            else:
                raise AttributeError("Section contains unexpected tag")

    def exportXMLSectionData(self, section_elem, section_num, section, fname_base):
        ver = self.vi.getFileVersion()

        if isGreaterOrEqVersion(ver, 8,0,0,1):
            # This is only for a comment, allowed to return None
            VCTP = self.vi.get('VCTP')

            for i in range(section.tdCount):
                tdIndex = section.indexShift + i
                td = None
                if VCTP is not None:
                    td = VCTP.getTopType(tdIndex)
                if td is not None:
                    comment_elem = ET.Comment(" Heap TypeID {:2d} = Consolidated TypeID {:2d}: {} "\
                      .format(i+1, tdIndex, enumOrIntToName(td.fullType())))
                else:
                    comment_elem = ET.Comment(" Heap TypeID {:2d} = Consolidated TypeID {:2d} "\
                      .format(i+1, tdIndex))
                section_elem.append(comment_elem)

            subelem = ET.SubElement(section_elem,"TypeDescSlice")

            subelem.set("IndexShift", "{:d}".format(section.indexShift))
            subelem.set("Count", "{:d}".format(section.tdCount))
        else:
            #TODO make support for the 7.1 format
            raise NotImplementedError("Exporting XML for LV7.1 and older is not implemented")
        pass

    def getHeapTD(self, heapTypeId, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        self.parseData(section_num=section_num)
        section = self.sections[section_num]

        VCTP = self.vi.get('VCTP')
        if VCTP is None:
            return None
        if heapTypeId < 1 or heapTypeId > section.tdCount:
            return None
        tdIndex = section.indexShift + heapTypeId - 1
        return VCTP.getTopType(tdIndex)


class DSTM(VarCodingBlock):
    """ Data Space Type Map
    """
    def createSection(self):
        section = super().createSection()
        section.content = []
        return section

    def setDefaultEncoding(self):
        ver = self.vi.getFileVersion()
        # Verified uncompressed in LV7.1.0, compressed in LV8.6
        if isGreaterOrEqVersion(ver, 8,0,0):
            self.default_block_coding = BLOCK_CODING.ZLIB
        else:
            self.default_block_coding = BLOCK_CODING.NONE

    def getMinTypeId(self, section_num=None):
        """ Returns minimal TypeID mapped in this section
        """
        return 1

    def getMaxTypeId(self, section_num=None):
        """ Returns TypeID of first item above ones mapped in this section
        """
        return 1+len(section.content)

    def getTypeEntry(self, tme_index, section_num=None):
        return None

    def getTypeMap(self, section_num=None):
        return []

class TM80(VarCodingBlock):
    """ Data Space Type Map LV8.0+

    Used for LV 8.0 and newer.
    """
    def createSection(self):
        section = super().createSection()
        section.indexShift = 0
        section.content = []
        # flag 0x0004 -> IsFPDCOOpData
        # flag 0x0010 -> IsChartHist
        return section

    def setDefaultEncoding(self):
        ver = self.vi.getFileVersion()
        if isGreaterOrEqVersion(ver, 10,0,0):
            self.default_block_coding = BLOCK_CODING.ZLIB
        else:
            self.default_block_coding = BLOCK_CODING.NONE

    def parseRSRCData(self, section_num, bldata):
        section = self.sections[section_num]

        section.content = []
        count = readVariableSizeFieldU2p2(bldata)
        if count > 0:
            section.indexShift = readVariableSizeFieldU2p2(bldata)
        for i in range(count):
            val = readVariableSizeFieldU2p2(bldata)
            section.content.append(val)

    def initWithXMLSection(self, section, section_elem):
        snum = section.start.section_idx
        fmt = section_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            section.content = []
            section.indexShift = int(section_elem.get("IndexShift"), 0)
            if (self.po.verbose > 2):
                print("{:s}: For Block {} section {:d}, reading inline XML data"\
                  .format(self.vi.src_fname,self.ident,snum))
            self.content = []
            for subelem in section_elem:
                if (subelem.tag == "NameObject"):
                    pass # Items parsed somewhere else
                elif (subelem.tag == "Client"):
                    val = int(subelem.get("Flags"), 0)
                    # Grow the list if needed (the labels may be in wrong order)
                    section.content.append(val)
                else:
                    raise AttributeError("Section contains unexpected tag")
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass

    def updateSectionData(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        data_buf = prepareVariableSizeFieldU2p2(len(section.content))
        data_buf += prepareVariableSizeFieldU2p2(section.indexShift)
        for val in section.content:
            data_buf += prepareVariableSizeFieldU2p2(val)

        if (len(data_buf) < 2 + 2*len(section.content)):
            raise RuntimeError("Block {} section {} generated binary data of invalid size"\
              .format(self.ident,section_num))

        self.setData(data_buf, section_num=section_num)

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        self.parseData(section_num=snum)
        # This is only for a comment, allowed to return None
        VCTP = self.vi.get('VCTP')

        section_elem.set("IndexShift", "{:d}".format(section.indexShift))

        for i, val in enumerate(section.content):
            td = None
            tdIndex = section.indexShift + i
            if VCTP is not None:
                td = VCTP.getTopType(tdIndex)
            if td is not None:
                comment_elem = ET.Comment(" TypeID {:d}: {} "\
                  .format(tdIndex, enumOrIntToName(td.fullType())))
            else:
                comment_elem = ET.Comment(" TypeID {:d} "\
                  .format(tdIndex))
            section_elem.append(comment_elem)

            subelem = ET.SubElement(section_elem,"Client")

            subelem.set("Flags", "0x{:04X}".format(val))

        if len(section.content) == 0:
            comment_elem = ET.Comment("List of types is empty")
            section_elem.append(comment_elem)

        section_elem.set("Format", "inline")

    def getTypeEntry(self, tme_index, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        self.parseData(section_num=section_num)
        section = self.sections[section_num]

        VCTP = self.vi.get_or_raise('VCTP')

        if True:
            i = tme_index
            val = section.content[i]
            tmEntry = SimpleNamespace()
            tmEntry.index = section.indexShift + i
            tmEntry.flags = val
            tmEntry.td = VCTP.getTopType(tmEntry.index)
            if tmEntry.td is None:
                eprint("{:s}: Warning: Block {} section {} references VCTP type {}+{} which does not exist."\
                  .format(self.vi.src_fname,self.ident,section_num,section.indexShift,i))

        return tmEntry

    def getMinTypeId(self, section_num=None):
        """ Returns minimal TypeID mapped in this section
        """
        if section_num is None:
            section_num = self.active_section_num
        self.parseData(section_num=section_num)
        section = self.sections[section_num]

        return section.indexShift

    def getMaxTypeId(self, section_num=None):
        """ Returns TypeID of first item above ones mapped in this section
        """
        if section_num is None:
            section_num = self.active_section_num
        self.parseData(section_num=section_num)
        section = self.sections[section_num]

        return section.indexShift + len(section.content)

    def getTypeMap(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        self.parseData(section_num=section_num)
        section = self.sections[section_num]

        VCTP = self.vi.get_or_raise('VCTP')

        typeMap = []
        for i, val in enumerate(section.content):
            tmEntry = SimpleNamespace()
            tmEntry.index = section.indexShift + i
            tmEntry.flags = val
            tmEntry.td = VCTP.getTopType(tmEntry.index)
            if tmEntry.td is None:
                eprint("{:s}: Warning: Block {} section {} references VCTP type {}+{} which does not exist."\
                  .format(self.vi.src_fname,self.ident,section_num,section.indexShift,i))
            else:
                typeMap.append(tmEntry)

        return typeMap


class LVIN(Block):
    """ LabView Instrument

    Instrument block from LabView 5; in later versions, called
    "old instrument", and replaced functionally by 'LVSR'.
    """
    def createSection(self):
        section = super().createSection()
        section.version = []
        return section

    def getVersion(self):
        self.parseData()
        raise NotImplementedError("Parsing of the {} block is unfinished".format(self.ident))
        #return self.version


class LVSR(CompleteBlock):
    """ LabView Save Record

    Structure named SAVERECORD is LV6 sources.
    """
    def createSection(self):
        section = super().createSection()
        section.version = decodeVersion(0x0)
        section.execFlags = 0
        section.protected = False
        section.viFlags2 = 0
        section.field0C = 0
        section.flags10 = 0
        # flags10 & 0x0100 -> read DSTM block
        # flags10 & 0x0200 -> read VICD block
        # flags10 & 0x0400 -> read DsEL block
        section.field12 = 0
        section.buttonsHidden = 0
        section.frontpFlags = 0
        section.instrState = 0
        section.execState = 0
        section.execPrio = 0
        section.viType = 0
        section.prefExecSyst = 0
        section.field28 = 0
        section.field2C = 0
        section.field30 = 0
        section.viSignature = b''
        section.alignGridFP = 0
        section.alignGridBD = 0
        section.field4C = 0
        section.ctrlIndStyle = 0
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

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]

        # Size of the data increses with further versions
        # Data before byte 68 does not move - so it's always safe to read
        data = LVSRData(self.po)
        dataLen = bldata.readinto(data)
        if dataLen not in [68, 96, 120, 136, 137, sizeof(LVSRData)]:
            raise EOFError("Data block length {} too small for parsing {} data".format(dataLen, self.ident))

        section.version = decodeVersion(data.version)
        section.protected = ((data.execFlags & VI_EXEC_FLAGS.LibProtected.value) != 0)
        section.execFlags = data.execFlags & (~VI_EXEC_FLAGS.LibProtected.value)
        section.viFlags2 = int(data.viFlags2)
        section.field0C = int(data.field0C)
        section.flags10 = int(data.flags10)
        section.field12 = int(data.field12)
        section.buttonsHidden = int(data.buttonsHidden)
        section.frontpFlags = int(data.frontpFlags)
        section.instrState = int(data.instrState)
        section.execState = int(data.execState)
        section.execPrio = int(data.execPrio)
        section.viType = int(data.viType)
        section.prefExecSyst = int(data.prefExecSyst)
        section.field28 = int(data.field28)
        section.field2C = int(data.field2C)
        section.field30 = int(data.field30)
        section.viSignature = bytes(data.viSignature)
        # Additional data, exists only in newer versions
        # sizeof(LVSR) per version: 6.0.1->68 7.1.0->96 8.6b7->120 9.0b25->120 9.0->120 10.0b84->120 10.0->136 11.0.1->136 12.0->136 13.0->136 14.0->137
        if isGreaterOrEqVersion(section.version, 7,0):
            section.alignGridFP = int(data.alignGridFP)
            section.alignGridBD = int(data.alignGridBD)
            section.field4C = int(data.field4C)
            section.ctrlIndStyle = int(data.ctrlIndStyle)
            section.field50_md5 = bytes(data.field50_md5)
        if isGreaterOrEqVersion(section.version, 8,0):
            section.libpass_md5 = bytes(data.libpass_md5)
            section.libpass_text = None
            section.field70 = int(data.field70)
            section.field74 = int(data.field74)
        if isGreaterOrEqVersion(section.version, 10,0, stage='release'):
            section.field78_md5 = bytes(data.field78_md5)
        if isGreaterOrEqVersion(section.version, 14,0):
            section.inlineStg = int(data.inlineStg)
        if isGreaterOrEqVersion(section.version, 15,0):
            section.field8C = int(data.field8C)
        # Any data added in future versions
        section.field90 = bldata.read()

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]
        data_buf = b''
        data_buf += int(encodeVersion(section.version)).to_bytes(4, byteorder='big')
        data_execFlags = (section.execFlags & (~VI_EXEC_FLAGS.LibProtected.value)) | \
          (VI_EXEC_FLAGS.LibProtected.value if section.protected else 0)
        data_buf += int(data_execFlags).to_bytes(4, byteorder='big')
        data_buf += int(section.viFlags2).to_bytes(4, byteorder='big')
        data_buf += int(section.field0C).to_bytes(4, byteorder='big')
        data_buf += int(section.flags10).to_bytes(2, byteorder='big')
        data_buf += int(section.field12).to_bytes(2, byteorder='big')
        data_buf += int(section.buttonsHidden).to_bytes(2, byteorder='big')
        data_buf += int(section.frontpFlags).to_bytes(2, byteorder='big')
        data_buf += int(section.instrState).to_bytes(4, byteorder='big')
        data_buf += int(section.execState).to_bytes(4, byteorder='big')
        data_buf += int(section.execPrio).to_bytes(2, byteorder='big')
        data_buf += int(section.viType).to_bytes(2, byteorder='big')
        data_buf += int(section.prefExecSyst).to_bytes(4, byteorder='big', signed=True)
        data_buf += int(section.field28).to_bytes(4, byteorder='big')
        data_buf += int(section.field2C).to_bytes(4, byteorder='big')
        data_buf += int(section.field30).to_bytes(4, byteorder='big')
        data_buf += section.viSignature
        if isGreaterOrEqVersion(section.version, 7,0):
            data_buf += int(section.alignGridFP).to_bytes(4, byteorder='big')
            data_buf += int(section.alignGridBD).to_bytes(4, byteorder='big')
            data_buf += int(section.field4C).to_bytes(2, byteorder='big')
            data_buf += int(section.ctrlIndStyle).to_bytes(2, byteorder='big')
            data_buf += section.field50_md5
        if isGreaterOrEqVersion(section.version, 8,0):
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
        return data_buf

    def expectedRSRCSize(self, section_num):
        section = self.sections[section_num]
        ver = self.vi.getFileVersion()
        exp_whole_len = 68

        if isGreaterOrEqVersion(section.version, 7,0):
            exp_whole_len += 28
        if isGreaterOrEqVersion(section.version, 8,0):
            exp_whole_len += 24
        if isGreaterOrEqVersion(section.version, 10,0, stage='release'):
            exp_whole_len += 16 # total 136
        if isGreaterOrEqVersion(section.version, 14,0):
            exp_whole_len += 1 # total 137
        if isGreaterOrEqVersion(section.version, 15,0):
            exp_whole_len += 3 + 4
        exp_whole_len += len(section.field90)
        return exp_whole_len

    def initWithXMLSectionData(self, section, section_elem):
        section.content = []
        section.field90 = b''

        # We really expect only one of each sub-elements
        for i, subelem in enumerate(section_elem):
            if (subelem.tag == "NameObject"):
                pass # Items parsed somewhere else
            elif (subelem.tag == "Version"):
                ver = {}
                ver['major'] = int(subelem.get("Major"), 0)
                ver['minor'] = int(subelem.get("Minor"), 0)
                ver['bugfix'] = int(subelem.get("Bugfix"), 0)
                ver['stage_text'] = subelem.get("Stage")
                ver['build'] = int(subelem.get("Build"), 0)
                ver['flags'] = int(subelem.get("Flags"), 0)
                section.version = ver
                # the call below sets numeric 'stage' from text; we do not care for actual encoding
                encodeVersion(section.version)
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
                section.prefExecSyst = int(subelem.get("PrefExecSyst"), 0)
                section.execFlags = importXMLBitfields(VI_EXEC_FLAGS, subelem)
            elif (subelem.tag == "Execution2"):
                section.viFlags2 = importXMLBitfields(VI_FLAGS2, subelem)
            elif (subelem.tag == "ButtonsHidden"):
                section.buttonsHidden = importXMLBitfields(VI_BTN_HIDE_FLAGS, subelem)
            elif (subelem.tag == "Instrument"):
                section.viType = valFromEnumOrIntString(VI_TYPE, subelem.get("Type"))
                tmphash = subelem.get("Signature")
                section.viSignature = bytes.fromhex(tmphash)
                section.instrState = importXMLBitfields(VI_IN_ST_FLAGS, subelem)
            elif (subelem.tag == "FrontPanel"):
                section.ctrlIndStyle = int(subelem.get("CtrlIndStyle"), 0)
                section.frontpFlags = importXMLBitfields(VI_FP_FLAGS, subelem)
            elif (subelem.tag == "Flags0C"):
                section.field0C = importXMLBitfields(VI_FLAGS0C, subelem)
            elif (subelem.tag == "Flags12"):
                section.field12 = importXMLBitfields(VI_FLAGS12, subelem)
            elif (subelem.tag == "Unknown"):
                section.flags10 = int(subelem.get("Flags10"), 0)
                section.field28 = int(subelem.get("Field28"), 0)
                section.field2C = int(subelem.get("Field2C"), 0)
                section.field30 = int(subelem.get("Field30"), 0)
                section.alignGridFP = int(subelem.get("AlignGridFP"), 0)
                section.alignGridBD = int(subelem.get("AlignGridBD"), 0)
                section.field4C = int(subelem.get("Field4C"), 0)
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
        pass

    def exportXMLSectionData(self, section_elem, section_num, section, fname_base):
        subelem = ET.SubElement(section_elem,"Version")
        subelem.set("Major", "{:d}".format(section.version['major']))
        subelem.set("Minor", "{:d}".format(section.version['minor']))
        subelem.set("Bugfix", "{:d}".format(section.version['bugfix']))
        subelem.set("Stage", "{:s}".format(section.version['stage_text']))
        subelem.set("Build", "{:d}".format(section.version['build']))
        subelem.set("Flags", "0x{:X}".format(section.version['flags']))

        subelem = ET.SubElement(section_elem,"Library")
        subelem.set("Protected", "{:d}".format(section.protected))
        subelem.set("PasswordHash", section.libpass_md5.hex())
        subelem.set("HashType", "MD5")

        subelem = ET.SubElement(section_elem,"Execution")
        subelem.set("State", "{:d}".format(section.execState))
        subelem.set("Priority", "{:d}".format(section.execPrio))
        subelem.set("PrefExecSyst", "{:d}".format(section.prefExecSyst))
        exportXMLBitfields(VI_EXEC_FLAGS, subelem, section.execFlags, \
          skip_mask=VI_EXEC_FLAGS.LibProtected.value)

        subelem = ET.SubElement(section_elem,"Execution2")
        exportXMLBitfields(VI_FLAGS2, subelem, section.viFlags2)

        subelem = ET.SubElement(section_elem,"ButtonsHidden")
        exportXMLBitfields(VI_BTN_HIDE_FLAGS, subelem, section.buttonsHidden)

        subelem = ET.SubElement(section_elem,"Instrument")
        subelem.set("Type", "{:s}".format(stringFromValEnumOrInt(VI_TYPE, section.viType)))
        subelem.set("Signature", section.viSignature.hex())
        exportXMLBitfields(VI_IN_ST_FLAGS, subelem, section.instrState)

        subelem = ET.SubElement(section_elem,"FrontPanel")
        subelem.set("CtrlIndStyle", "{:d}".format(section.ctrlIndStyle))
        exportXMLBitfields(VI_FP_FLAGS, subelem, section.frontpFlags)

        subelem = ET.SubElement(section_elem,"Flags0C")
        exportXMLBitfields(VI_FLAGS0C, subelem, section.field0C)

        subelem = ET.SubElement(section_elem,"Flags12")
        exportXMLBitfields(VI_FLAGS12, subelem, section.field12)

        subelem = ET.SubElement(section_elem,"Unknown")

        subelem.set("Flags10", "{:d}".format(section.flags10))
        subelem.set("Field28", "{:d}".format(section.field28))
        subelem.set("Field2C", "{:d}".format(section.field2C))
        subelem.set("Field30", "{:d}".format(section.field30))
        subelem.set("AlignGridFP", "{:d}".format(section.alignGridFP))
        subelem.set("AlignGridBD", "{:d}".format(section.alignGridBD))
        subelem.set("Field4C", "{:d}".format(section.field4C))
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

            part_fname = "{:s}_{:s}.{:s}".format(fname_base,subelem.tag,"bin")
            if (self.po.verbose > 1):
                print("{}: Writing block {} section {} part to '{}'".format(self.vi.src_fname,self.ident,snum,part_fname))
            with open(part_fname, "wb") as part_fh:
                part_fh.write(section.field90)
            subelem.set("Format", "bin")
            subelem.set("File", os.path.basename(part_fname))
        pass

    def getVersion(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]
        self.parseData(section_num=section_num)
        return section.version


class vers(Block):
    """ Version block
    """
    def createSection(self):
        section = super().createSection()
        section.version = []
        section.version_text = b''
        section.version_info = b''
        section.comment = b''
        return section

    def parseRSRCData(self, section_num, bldata):
        section = self.sections[section_num]

        section.version = decodeVersion(int.from_bytes(bldata.read(4), byteorder='big', signed=False))
        version_text_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        section.version_text = bldata.read(version_text_len)
        # TODO Is the string null-terminated? or that's length of another string?
        version_unk_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        if version_unk_len != 0:
            raise AttributeError("Block {} section {} always zero value 1 is {} instead of {}"\
             .format(self.ident,section_num,version_unk_len,0))
        version_info_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        section.version_info = bldata.read(version_info_len)
        comment_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        section.comment = bldata.read(comment_len)
        if isGreaterOrEqVersion(self.version, 8,6,0) and comment_len != 0:
            eprint("Warning: Block {} section {} comment length is {} instead of {}"\
             .format(self.ident,section_num,comment_len,0))

    def updateSectionData(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        data_buf = int(encodeVersion(section.version)).to_bytes(4, byteorder='big')
        data_buf += preparePStr(section.version_text, 1, self.po)
        data_buf += b'\0'
        data_buf += preparePStr(section.version_info, 1, self.po)
        data_buf += preparePStr(section.comment, 1, self.po)

        if len(data_buf) != 4 + 1+len(section.version_text) + 1 +\
          1+len(section.version_info) + 1+len(section.comment):
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
                if (subelem.tag == "NameObject"):
                    pass # Items parsed somewhere else
                elif (subelem.tag == "Version"):
                    ver = {}
                    ver['major'] = int(subelem.get("Major"), 0)
                    ver['minor'] = int(subelem.get("Minor"), 0)
                    ver['bugfix'] = int(subelem.get("Bugfix"), 0)
                    ver['stage_text'] = subelem.get("Stage")
                    ver['build'] = int(subelem.get("Build"), 0)
                    ver['flags'] = int(subelem.get("Flags"), 0)
                    section.version_text = subelem.get("Text").encode(self.vi.textEncoding)
                    section.version_info = subelem.get("Info").encode(self.vi.textEncoding)
                    section.comment = subelem.get("Comment").encode(self.vi.textEncoding)
                    section.version = ver
                    # the call below sets numeric 'stage' from text; we do not care for actual encoding
                    encodeVersion(section.version)
                else:
                    raise AttributeError("Section contains something else than 'Version'")
        else:
            Block.initWithXMLSection(self, section, section_elem)
        pass

    def exportXMLSection(self, section_elem, section_num, section, fname_base):
        self.parseData(section_num=section_num)

        subelem = ET.SubElement(section_elem,"Version")

        subelem.set("Major", "{:d}".format(section.version['major']))
        subelem.set("Minor", "{:d}".format(section.version['minor']))
        subelem.set("Bugfix", "{:d}".format(section.version['bugfix']))
        subelem.set("Stage", "{:s}".format(section.version['stage_text']))
        subelem.set("Build", "{:d}".format(section.version['build']))
        subelem.set("Flags", "0x{:X}".format(section.version['flags']))
        subelem.set("Text", "{:s}".format(section.version_text.decode(self.vi.textEncoding)))
        subelem.set("Info", "{:s}".format(section.version_info.decode(self.vi.textEncoding)))
        subelem.set("Comment", "{:s}".format(section.comment.decode(self.vi.textEncoding)))

        section_elem.set("Format", "inline")

    def getVersion(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]
        self.parseData(section_num=section_num)
        return section.version

    def getVerText(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]
        self.parseData(section_num=section_num)
        return section.version_text

    def getVerInfo(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]
        self.parseData(section_num=section_num)
        return section.version_info


class ImageBlock(CompleteBlock):
    """ Block with image
    """
    def createSection(self):
        section = super().createSection()
        section.storage_format = "png"
        section.image = None
        return section

    def setDefaultEncoding(self):
        self.default_block_coding = BLOCK_CODING.NONE

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]
        section.image = None

        image = Image.open(bldata)
        section.image = image
        image.getdata() # to make sure the file gets loaded; everything is lazy nowadays

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]

        bldata = BytesIO()
        section.image.save(bldata, format="PNG")
        bldata.seek(0)
        data_buf = bldata.read()
        return data_buf

    def initWithImageSectionData(self, section, section_elem, image, block_fh):
        section.image = image

    def exportImageSectionData(self, section_elem, block_fh, section_num, section, fname_base):
        section.image.save(block_fh, format="PNG")

    def loadImage(self):
        """ Loads and returns the image stored in this block.

        In case you modify that image, remeber to mark parsed_data_updated.
        """
        self.parseData()
        return self.image


class PNGI(ImageBlock):
    """ PNG Image
    """
    def createSection(self):
        section = super().createSection()
        section.padding_len = 0
        section.media_compressed = None
        return section

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]

        start_pos = bldata.tell()
        super().parseRSRCSectionData(section_num, bldata)
        # Allow up to 16 bytes of padding
        padding = bldata.read(16)
        section.padding_len = max(len(padding) - 4, 0)

        # Our image is loaded; but also store the original data to avoid re-compressing
        img_len = bldata.tell() - start_pos - section.padding_len
        bldata.seek(start_pos)
        section.media_compressed = bldata.read(img_len)
        bldata.read(section.padding_len)

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]

        data_buf = b''
        if section.parsed_data_updated:
            section.media_compressed = None
        if section.media_compressed is not None:
            # Do not recompress the file if there is no need, use original data
            data_buf += section.media_compressed
        else:
            data_buf += super().prepareRSRCData(section_num)
        data_buf += b'\0' * section.padding_len
        return data_buf

    def initWithImageSectionData(self, section, section_elem, image, block_fh):
        section.padding_len = int(section_elem.get("PaddingLength"), 0)
        super().initWithImageSectionData(section, section_elem, image, block_fh)
        # Besides the interpreted image, also store the original data to avoid re-compressing
        block_fh.seek(0)
        section.media_compressed = block_fh.read()

    def exportImageSectionData(self, section_elem, block_fh, section_num, section, fname_base):
        section_elem.set("PaddingLength", "{:d}".format(section.padding_len))
        if section.parsed_data_updated:
            section.media_compressed = None
        if section.media_compressed is not None:
            # Do not recompress the file if there is no need, use original data
            block_fh.write(section.media_compressed)
        else:
            super().exportImageSectionData(section_elem, block_fh, section_num, section, fname_base)


class MNGI(PNGI):
    """ MNG Image
    """
    def createSection(self):
        section = super().createSection()
        return section


class ICON(ImageBlock):
    """ Icon 32x32 1bpp
    """
    def createSection(self):
        section = super().createSection()
        section.width = 32
        section.height = 32
        section.bpp = 1
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
        section.image = icon

    def updateSectionData(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        data_buf = bytes(section.image.getdata())
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


class ICNsh(ICON):
    """ Icon Large Double 32x64 1bpp
    """
    def createSection(self):
        section = super().createSection()
        section.width = 32
        section.height = 64
        section.bpp = 1
        return section


class icssh(ICON):
    """ Icon Small 16x16 1bpp
    """
    def createSection(self):
        section = super().createSection()
        section.width = 16
        section.height = 16
        section.bpp = 1
        return section


class CURS(ICON):
    """ Cursor 16x34 1bpp
    """
    def createSection(self):
        section = super().createSection()
        section.width = 16
        section.height = 34
        section.bpp = 1
        return section


class ics4(ICON):
    """ Icon Small 16x16 4bpp
    """
    def createSection(self):
        section = super().createSection()
        section.width = 16
        section.height = 16
        section.bpp = 4
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


class ics8(ICON):
    """ Icon Small 16x16 8bpp
    """
    def createSection(self):
        section = super().createSection()
        section.width = 16
        section.height = 16
        section.bpp = 8
        return section


class icl8(ICON):
    """ Icon Large 32x32 8bpp
    """
    def createSection(self):
        section = super().createSection()
        section.width = 32
        section.height = 32
        section.bpp = 8
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
        section.salt_source = None
        section.salt_td_flat_idx = None
        section.salt = None
        return section

    def hasHash2(self):
        """ Returns whether the block should have hash_2 stored.

        Tested not to be there in LV7.1, is there in LV8.6b7
        """
        ver = self.vi.getFileVersion()
        return isGreaterOrEqVersion(ver, 8,0,0)

    def parseRSRCData(self, section_num, bldata):
        section = self.sections[section_num]

        section.password_md5 = bldata.read(16)
        section.hash_1 = bldata.read(16)
        if self.hasHash2():
            section.hash_2 = bldata.read(16)
        else:
            section.hash_2 = b''

    def updateSectionData(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        if True:
            self.recalculateHash1(section_num=section_num)
        if self.hasHash2():
            self.recalculateHash2(section_num=section_num)

        data_buf = section.password_md5
        data_buf += section.hash_1
        if self.hasHash2():
            data_buf += section.hash_2

        exp_whole_len = self.expectedRSRCSize(section_num)
        if (len(data_buf) != exp_whole_len):
            eprint("{:s}: Warning: Block {} section {} generated binary data of size {:d}, expected {:d}"\
              .format(self.vi.src_fname,self.ident,section_num,len(data_buf),exp_whole_len))

        self.setData(data_buf, section_num=section_num)

    def expectedRSRCSize(self, section_num):
        exp_whole_len = 16 + 16
        if self.hasHash2():
            exp_whole_len += 16
        return exp_whole_len

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        self.parseData(section_num=snum)
        try:
            self.recalculateHash1(section_num=snum, store=False) # this is needed to find salt
            self.recognizePassword(section_num=snum)
        except Exception as e:
            eprint("{:s}: Warning: Block {} section {} could not be fully parametrized: {}"\
              .format(self.vi.src_fname,self.ident,snum,str(e)))
            pass

        subelem = ET.SubElement(section_elem,"Password")

        if section.password is not None:
            subelem.set("Text", section.password)
        else:
            subelem.set("Hash", section.password_md5.hex())
            subelem.set("HashType", "MD5")
        if section.salt_source is not None:
            subelem.set("SaltSource", section.salt_source)
        # TODO If CPC2 stores the proper TypeDesc, we should mark this somehow and not store this TypeID here
        if section.salt_td_flat_idx is not None:
            subelem.set("SaltFlatTypeID", str(section.salt_td_flat_idx))
        elif section.salt is not None:
            subelem.set("SaltData", section.salt.hex())
        else:
            subelem.set("RawHash1", section.hash_1.hex())
            subelem.set("RawHash2", section.hash_2.hex())

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
                if (subelem.tag == "NameObject"):
                    pass # Items parsed somewhere else
                elif (subelem.tag == "Password"):
                    pass_text = subelem.get("Text")
                    pass_hash = subelem.get("Hash")
                    if pass_text is not None:
                        self.setPassword(section_num=snum, password_text=pass_text)
                    else:
                        self.setPassword(section_num=snum, password_md5=bytes.fromhex(pass_hash))

                    section.salt_source = subelem.get("SaltSource")
                    salt_td_flat_idx = subelem.get("SaltFlatTypeID")
                    salt_data = subelem.get("SaltData")
                    if salt_td_flat_idx is not None:
                        section.salt_td_flat_idx = int(salt_td_flat_idx, 0)
                    elif salt_data is not None:
                        section.salt = bytes.fromhex(salt_data)
                    else:
                        section.salt = None
                    # Raw hashes are stored when something was seriously wrong and nothing else was computed
                    rawhash = subelem.get("RawHash1")
                    if rawhash is not None:
                        section.hash_1 = bytes.fromhex(rawhash)
                    rawhash = subelem.get("RawHash2")
                    if rawhash is not None:
                        section.hash_2 = bytes.fromhex(rawhash)
                else:
                    raise AttributeError("Section contains something else than 'Password'")
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
        salt_source = "None"
        ver = self.vi.getFileVersion()
        if not isGreaterOrEqVersion(ver, 1,0):
            if (po.verbose > 0):
                eprint("{:s}: Warning: No version block found; assuming oldest format, with empty password salt".format(self.vi.src_fname))
            section.salt = salt
            return salt
        if isGreaterOrEqVersion(ver, 12,0):
            # Figure out the salt
            salt_td_flat_idx = None
            VCTP = self.vi.get_or_raise('VCTP')
            CPC2 = self.vi.get('CPC2')
            if CPC2 is not None:
                iface_obj = VCTP.getTopType(CPC2.getValue())
                if True:
                    term_typedescs = VCTP.getClientTypeDescsByType(iface_obj)
                    salt = BDPW.getPasswordSaltFromTerminalCounts(len(term_typedescs['number']), len(term_typedescs['string']), len(term_typedescs['path']))
                    md5_hash_1 = md5(presalt_data + salt + postsalt_data).digest()
                    if md5_hash_1 == section.hash_1:
                        if (self.po.verbose > 1):
                            print("{:s}: Found matching salt {}, interface from {}".format(self.vi.src_fname,salt.hex(),CPC2.ident))
                        salt_td_flat_idx = iface_obj.index
                        salt_source = "CPC2"
            if salt_td_flat_idx is None:
                interfaceEnumerate = self.vi.consolidatedTDEnumerate(fullType=TD_FULL_TYPE.Function)
                # Check if one of the interfaces is the source of salt; usually it's the last interface, so check in reverse
                for i, iface_idx, iface_obj in reversed(interfaceEnumerate):
                    term_typedescs = VCTP.getClientTypeDescsByType(iface_obj)
                    salt = BDPW.getPasswordSaltFromTerminalCounts(len(term_typedescs['number']), len(term_typedescs['string']), len(term_typedescs['path']))
                    md5_hash_1 = md5(presalt_data + salt + postsalt_data).digest()
                    if md5_hash_1 == section.hash_1:
                        if (self.po.verbose > 1):
                            print("{:s}: Found matching salt {}, interface {:d}/{:d}".format(self.vi.src_fname,salt.hex(),i+1,len(interfaceEnumerate)))
                        salt_td_flat_idx = iface_idx
                        salt_source = "TD"
                        break

            section.salt_td_flat_idx = salt_td_flat_idx

            if salt_td_flat_idx is not None:
                salt_iface = VCTP.getFlatType(salt_td_flat_idx)
                term_typedescs = VCTP.getClientTypeDescsByType(salt_iface)
                salt = BDPW.getPasswordSaltFromTerminalCounts(len(term_typedescs['number']), len(term_typedescs['string']), len(term_typedescs['path']))
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
                        salt_source = "Brute"
                        break
        section.salt = salt
        section.salt_source = salt_source
        return salt

    def findHashSalt(self, section_num, password_md5, LIBN_content, LVSR_content, force_scan=False):
        section = self.sections[section_num]

        if force_scan:
            section.salt_td_flat_idx = None
            section.salt = None
        if section.salt_td_flat_idx is not None:
            # If we've previously found an interface on which the salt is based, use that interface
            VCTP = self.vi.get_or_raise('VCTP')
            salt_iface = VCTP.getFlatType(section.salt_td_flat_idx)
            term_typedescs = VCTP.getClientTypeDescsByType(salt_iface)
            salt = BDPW.getPasswordSaltFromTerminalCounts(len(term_typedescs['number']), len(term_typedescs['string']), len(term_typedescs['path']))
        elif section.salt is not None:
            # If we've previously brute-forced the salt, use that same salt
            salt = section.salt
        else:
            # If we didn't determined the salt yet, do  a scan
            salt = self.scanForHashSalt(section_num, presalt_data=password_md5+LIBN_content+LVSR_content)
        return salt

    def setPassword(self, section_num=None, password_text=None, password_md5=None, store=True):
        """ Sets new password, without recalculating hashes
        """
        if section_num is None:
            section_num = self.active_section_num
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

        LVSR.updateData()
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


class LIBN(CompleteBlock):
    """ Library Names

    Stores names of libraries which contain this RSRC file.
    """
    def createSection(self):
        section = super().createSection()
        section.content = None
        return section

    def setDefaultEncoding(self):
        self.default_block_coding = BLOCK_CODING.NONE

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]
        section.content = []

        count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        if count > self.po.typedesc_list_limit:
            raise RuntimeError("String list consists of {:d} tags, limit is {:d}"\
              .format(count,self.po.typedesc_list_limit))
        for i in range(count):
            name = readPStr(bldata, 1, self.po)
            section.content.append(name)
        pass

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]

        data_buf = b''
        data_buf += int(len(section.content)).to_bytes(4, byteorder='big', signed=False)
        for name in section.content:
            data_buf += preparePStr(name, 1, self.po)
        return data_buf

    def expectedRSRCSize(self, section_num):
        section = self.sections[section_num]
        exp_whole_len = 4
        for name in section.content:
            exp_whole_len += 1+len(name)
        return exp_whole_len

    def initWithXMLSectionData(self, section, section_elem):
        section.content = []

        # There can be multiple "Library" sub-elements
        for i, subelem in enumerate(section_elem):
            if (subelem.tag == "NameObject"):
                pass # Items parsed somewhere else
            elif (subelem.tag == "Library"):
                name_text = subelem.text
                if name_text is not None:
                    name = name_text.encode(self.vi.textEncoding)
                else:
                    name = b''
                section.content.append(name)
            else:
                raise AttributeError("Section contains something else than 'Library'")
        pass

    def exportXMLSectionData(self, section_elem, section_num, section, fname_base):
        for name in section.content:
            subelem = ET.SubElement(section_elem,"Library")
            subelem.text = name.decode(self.vi.textEncoding)
        pass

    def getContent(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        self.parseData(section_num=section_num)
        section = self.sections[section_num]
        return section.content


class LVzp(VarCodingBlock):
    """ LabView Zipped Program tree

    Used in llb-like objects created by building the project.
    Contains the whole VIs hierarchy, stored within ZIP file.

    In LV from circa 2009 and before, the ZIP was stored in plain form.
    In newer LV versions, it is encrypted by simple xor-based algorithm.
    """
    def createSection(self):
        section = super().createSection()
        return section

    def setDefaultEncoding(self):
        self.default_block_coding = BLOCK_CODING.XOR


class PRT(CompleteBlock):
    """ Print settings

    """
    def createSection(self):
        section = super().createSection()
        return section

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]

        section.field00 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field04 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field08 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field0C = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field10 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field14 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field18 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field1C = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field20 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        # 0x20000=fp scaling, 0x40000=bd scaling, 0x80000=print header
        section.flags = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field28 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.orientation = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field30 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field34 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field38 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field3C = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.marginUnit = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field44 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field48 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.marginTop = struct.unpack('>f', bldata.read(4))[0]
        section.marginLeft = struct.unpack('>f', bldata.read(4))[0]
        section.marginBottom = struct.unpack('>f', bldata.read(4))[0]
        section.marginRight = struct.unpack('>f', bldata.read(4))[0]
        section.field5C = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field60 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field64 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field68 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field6C = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field70 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.headerContents = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field78 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field7C = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.driverPaperSize = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field84 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field88 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field8C = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field90 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.field94 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

        raise NotImplementedError("Parsing the block is not fully implemented")

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]

        data_buf = b''
        data_buf += int(section.field00).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field04).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field08).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field0C).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field10).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field14).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field18).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field1C).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field20).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.flags).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field28).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.orientation).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field30).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field34).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field38).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field3C).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.marginUnit).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field44).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field48).to_bytes(4, byteorder='big', signed=False)
        data_buf += struct.pack('>f', section.marginTop)
        data_buf += struct.pack('>f', section.marginLeft)
        data_buf += struct.pack('>f', section.marginBottom)
        data_buf += struct.pack('>f', section.marginRight)
        data_buf += int(section.field5C).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field60).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field64).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field68).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field6C).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field70).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.headerContents).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field78).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field7C).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.driverPaperSize).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field84).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field88).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field8C).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field90).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(section.field94).to_bytes(4, byteorder='big', signed=False)
        return data_buf

    def initWithXMLSectionData(self, section, section_elem):
        section.content = []

        # There can be multiple "Library" sub-elements
        for i, subelem in enumerate(section_elem):
            if (subelem.tag == "NameObject"):
                pass # Items parsed somewhere else
            elif (subelem.tag == "Options1"):
                tmp = subelem.get("Field00")
                section.field00 = int(tmp, 0)
                tmp = subelem.get("Field04")
                section.field04 = int(tmp, 0)
                tmp = subelem.get("Field08")
                section.field08 = int(tmp, 0)
                tmp = subelem.get("Field0C")
                section.field0C = int(tmp, 0)
                tmp = subelem.get("Field10")
                section.field10 = int(tmp, 0)
                tmp = subelem.get("Field14")
                section.field14 = int(tmp, 0)
                tmp = subelem.get("Field18")
                section.field18 = int(tmp, 0)
                tmp = subelem.get("Field1C")
                section.field1C = int(tmp, 0)
                tmp = subelem.get("Field20")
                section.field20 = int(tmp, 0)
                tmp = subelem.get("Flags")
                section.flags = int(tmp, 0)
                tmp = subelem.get("Field28")
                section.field28 = int(tmp, 0)
                tmp = subelem.get("Orientation")
                section.orientation = int(tmp, 0)
                tmp = subelem.get("Field30")
                section.field30 = int(tmp, 0)
                tmp = subelem.get("Field34")
                section.field34 = int(tmp, 0)
                tmp = subelem.get("Field38")
                section.field38 = int(tmp, 0)
                tmp = subelem.get("Field3C")
                section.field3C = int(tmp, 0)
                tmp = subelem.get("MarginUnit")
                section.marginUnit = int(tmp, 0)
                tmp = subelem.get("Field44")
                section.field44 = int(tmp, 0)
                tmp = subelem.get("Field48")
                section.field48 = int(tmp, 0)
                tmp = subelem.get("Field4C")
                section.field4C = int(tmp, 0)
            elif (subelem.tag == "Margins"):
                tmp = subelem.get("Top")
                section.marginTop = float(tmp)
                tmp = subelem.get("Left")
                section.marginLeft = float(tmp)
                tmp = subelem.get("Bottom")
                section.marginBottom = float(tmp)
                tmp = subelem.get("Right")
                section.marginRight = float(tmp)
            elif (subelem.tag == "Options2"):
                tmp = subelem.get("Field5C")
                section.field5C = int(tmp, 0)
                tmp = subelem.get("Field60")
                section.field60 = int(tmp, 0)
                tmp = subelem.get("Field64")
                section.field64 = int(tmp, 0)
                tmp = subelem.get("Field68")
                section.field68 = int(tmp, 0)
                tmp = subelem.get("Field6C")
                section.field6C = int(tmp, 0)
                tmp = subelem.get("Field70")
                section.field70 = int(tmp, 0)
                tmp = subelem.get("HeaderContents")
                section.headerContents = int(tmp, 0)
                tmp = subelem.get("Field78")
                section.field78 = int(tmp, 0)
                tmp = subelem.get("Field7C")
                section.field7C = int(tmp, 0)
                tmp = subelem.get("DriverPaperSize")
                section.driverPaperSize = int(tmp, 0)
                tmp = subelem.get("Field84")
                section.field84 = int(tmp, 0)
                tmp = subelem.get("Field88")
                section.field88 = int(tmp, 0)
                tmp = subelem.get("Field8C")
                section.field8C = int(tmp, 0)
                tmp = subelem.get("Field90")
                section.field90 = int(tmp, 0)
                tmp = subelem.get("Field94")
                section.field94 = int(tmp, 0)
            else:
                raise AttributeError("Section contains unexpected tag")
        pass

    def exportXMLSectionData(self, section_elem, section_num, section, fname_base):
        subelem = ET.SubElement(section_elem,"Options1")
        subelem.set("Field00", "{:d}".format(section.field00))
        subelem.set("Field04", "{:d}".format(section.field04))
        subelem.set("Field08", "{:d}".format(section.field08))
        subelem.set("Field0C", "{:d}".format(section.field0C))
        subelem.set("Field10", "{:d}".format(section.field10))
        subelem.set("Field14", "{:d}".format(section.field14))
        subelem.set("Field18", "{:d}".format(section.field18))
        subelem.set("Field1C", "{:d}".format(section.field1C))
        subelem.set("Field20", "{:d}".format(section.field20))
        subelem.set("Flags", "{:d}".format(section.flags))
        subelem.set("Field28", "{:d}".format(section.field28))
        subelem.set("Orientation", "{:d}".format(section.orientation))
        subelem.set("Field30", "{:d}".format(section.field30))
        subelem.set("Field35", "{:d}".format(section.field34))
        subelem.set("Field38", "{:d}".format(section.field38))
        subelem.set("Field3C", "{:d}".format(section.field3C))
        subelem.set("MarginUnit", "{:d}".format(section.marginUnit))
        subelem.set("Field44", "{:d}".format(section.field44))
        subelem.set("Field48", "{:d}".format(section.field48))
        subelem = ET.SubElement(section_elem,"Margins")
        subelem.set("Top", "{:g}".format(section.marginTop))
        subelem.set("Left", "{:g}".format(section.marginLeft))
        subelem.set("Bottom", "{:g}".format(section.marginBottom))
        subelem.set("Right", "{:g}".format(section.marginRight))
        subelem = ET.SubElement(section_elem,"Options2")
        subelem.set("Field5C", "{:d}".format(section.field5C))
        subelem.set("Field60", "{:d}".format(section.field60))
        subelem.set("Field64", "{:d}".format(section.field64))
        subelem.set("Field68", "{:d}".format(section.field68))
        subelem.set("Field6C", "{:d}".format(section.field6C))
        subelem.set("Field70", "{:d}".format(section.field70))
        subelem.set("HeaderContents", "{:d}".format(section.headerContents))
        subelem.set("Field78", "{:d}".format(section.field78))
        subelem.set("Field7C", "{:d}".format(section.field7C))
        subelem.set("DriverPaperSize", "{:d}".format(section.driverPaperSize))
        subelem.set("Field84", "{:d}".format(section.field84))
        subelem.set("Field88", "{:d}".format(section.field88))
        subelem.set("Field8C", "{:d}".format(section.field8C))
        subelem.set("Field90", "{:d}".format(section.field90))
        subelem.set("Field94", "{:d}".format(section.field94))
        pass


class BNID(Block):
    """ B. N. Identifier

    """
    def createSection(self):
        section = super().createSection()
        return section


class NUID(Block):
    """ N. U. Identifier

    """
    def createSection(self):
        section = super().createSection()
        return section


class SUID(Block):
    """ S. U. Identifier

    """
    def createSection(self):
        section = super().createSection()
        return section


class HeapVerP(CompleteBlock):
    """ BD/FP Heap version P
    """
    def createSection(self):
        section = super().createSection()
        section.storage_format = "xml"
        section.content = None
        return section

    def setDefaultEncoding(self):
        self.default_block_coding = BLOCK_CODING.NONE

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]

        content_len = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        section.content = bldata.read(content_len)

    def getContent(self):
        self.updateData()
        bldata = self.getData()
        content_len = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        content = bldata.read(content_len)
        return content

    def getContentHash(self):
        content = self.getContent()
        return md5(content).digest()


class HeapVerb(CompleteBlock):
    """ BD/FP Heap version b
    """
    def createSection(self):
        section = super().createSection()
        section.storage_format = "xml"
        section.objects = []
        return section

    def setDefaultEncoding(self):
        self.default_block_coding = BLOCK_CODING.ZLIB

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

        if scopeInfo == LVheap.NODE_SCOPE.TagClose and parentNode is not None:
            parentNode = parentNode.parent

        tagEn = LVheap.tagIdToEnum(tagId, parentNode)

        i = len(section.objects)
        obj = LVheap.createObjectNode(self.vi, self.po, parentNode, tagEn, scopeInfo)
        section.objects.append(obj)
        if parentNode is not None:
            parentNode.childs.append(obj)
        obj.parseRSRCData(bldata, hasAttrList, sizeSpec)
        if scopeInfo == LVheap.NODE_SCOPE.TagOpen:
            parentNode = obj
        dataLen = bldata.tell() - startPos

        # TODO Should we re-read the bytes and set raw data inside the obj?
        #bldata.seek(startPos)
        #dataBuf = bldata.read(dataLen)

        return parentNode, dataLen

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]

        section.objects = []
        content_len = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

        parentNode = None
        tot_len = 0
        while tot_len < content_len:
            parentNode, entry_len = self.parseRSRCHeap(section, bldata, parentNode)
            if entry_len <= 0:
                raise RuntimeError("Not enough raw data for complete heap")
            tot_len += entry_len

        if parentNode != None:
            eprint("{}: Warning: In block {}, heap did not closed all tags"\
              .format(self.vi.src_fname, self.ident))
        pass

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]

        for obj in section.objects:
            if not obj.raw_data_updated:
                obj.updateData()

        data_buf = b''
        for i, obj in enumerate(section.objects):
            bldata = obj.getData()
            data_buf += bldata.read()

        data_buf = int(len(data_buf)).to_bytes(4, byteorder='big') + data_buf
        return data_buf

    def expectedRSRCSize(self, section_num):
        section = self.sections[section_num]
        exp_whole_len = 0
        for obj in section.objects:
            #TODO implement and use expected size
            #exp_whole_len += obj.expectedRSRCSize()
            bldata = obj.getData()
            exp_whole_len += len(bldata.read())
        exp_whole_len += 4
        return exp_whole_len

    def initWithXMLHeap(self, section, elem, parentNode):
        tagEn = LVheap.tagNameToEnum(elem.tag, parentNode)
        if tagEn is None:
            raise AttributeError("Unrecognized tag in heap XML; tag '{}', parent tag '{}'"\
              .format(elem.tag, parentNode.tagEn.name))
        scopeInfo = LVheap.autoScopeInfoFromET(elem)
        obj = LVheap.createObjectNode(self.vi, self.po, parentNode, tagEn, scopeInfo)
        section.objects.append(obj)
        if parentNode is not None:
            parentNode.childs.append(obj)

        obj.initWithXML(elem)

        for subelem in elem:
            self.initWithXMLHeap(section, subelem, obj)

        if obj.scopeInfo == LVheap.NODE_SCOPE.TagOpen.value:
            scopeInfo = LVheap.NODE_SCOPE.TagClose.value
            obj = LVheap.createObjectNode(self.vi, self.po, parentNode, tagEn, scopeInfo)
            section.objects.append(obj)
            if parentNode is not None:
                parentNode.childs.append(obj)
            #obj.initWithXML(elem) # No init needed for closing tag

    def initWithXMLSectionData(self, section, section_elem):
        section.objects = []

        self.initWithXMLHeap(section, section_elem, None)

    def exportXMLSectionData(self, section_elem, section_num, section, fname_base):
        root = section_elem
        parent_elems = []
        elem = None
        for i, obj in enumerate(section.objects):
            scopeInfo = obj.getScopeInfo()
            tagName = LVheap.tagEnToName(obj.tagEn, obj.parent)
            if elem is None:
                elem = root
                elem.tag = tagName
            elif scopeInfo == LVheap.NODE_SCOPE.TagClose:
                elem = parent_elems.pop()
                if elem.tag != tagName:
                    eprint("{}: Warning: In block {}, closing tag {} instead of {}"\
                      .format(self.vi.src_fname, self.ident, tagName, elem.tag))
            else:
                # Having two root items would crash here. And that's good, we can't have two roots.
                elem = ET.SubElement(parent_elems[-1], tagName)

            obj.exportXML(elem, scopeInfo, "{:s}_{:04d}".format(fname_base,i))

            if scopeInfo == LVheap.NODE_SCOPE.TagOpen:
                parent_elems.append(elem)

        if len(parent_elems) > 0:
            eprint("{}: Warning: In block {}, heap structure is not a valid XML tree"\
              .format(self.vi.src_fname, self.ident))
        pass

    def initWithXMLLate(self):
        super().initWithXMLLate()
        for snum in self.sections:
            section = self.sections[snum]
            for obj in section.objects:
                obj.initWithXMLLate()
        pass

    def getContent(self):
        self.updateData()
        bldata = self.getData()
        content_len = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        content = bldata.read(content_len)
        return content

    def getContentHash(self):
        content = self.getContent()
        return md5(content).digest()


class HeapVerc(CompleteBlock):
    """ BD/FP Heap version c
    """
    def createSection(self):
        section = super().createSection()
        section.storage_format = "xml"
        section.content = None
        return section

    def setDefaultEncoding(self):
        self.default_block_coding = BLOCK_CODING.ZLIB

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]
        section.content = None

        content_len = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        container_start = bldata.tell()

        bldata.seek(content_len)
        data_len = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

        data_start = content_len - data_len
        container_len = content_len - data_len - container_start

        #raw_subdata = bldata.read(data_len)
        #blsubdata = io.BytesIO(raw_subdata)
        #bldata.seek(container_start)

        section.objects = []
        #TODO parse heap data

        # Read the raw data
        bldata.seek(container_start)
        section.content = bldata.read(content_len)

    def getContent(self):
        self.updateData()
        bldata = self.getData()
        content_len = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        content = bldata.read(content_len)
        return content

    def getContentHash(self):
        content = self.getContent()
        return md5(content).digest()


class BDHP(HeapVerP):
    """ Block Diagram Heap

    This block is spcific to LV 7beta and older.
    """
    pass


class FPHP(HeapVerP):
    """ Front Panel Heap

    This block is spcific to LV 7beta and older.
    """
    pass


class BDHb(HeapVerb):
    """ Block Diagram Heap ver b
    """
    pass


class FPHb(HeapVerb):
    """ Front Panel Heap ver b

    Stored in "FPHx"-block.
    This implementation is for LV 7 and newer.
    """
    pass


class BDHc(HeapVerc):
    """ Block Diagram Heap ver c

    Stored in "BDHx"-block. It uses a binary tree format to store hierarchy
    structures. They use a kind of "xml-tags" to open and close objects.
    """
    pass


class FPHc(HeapVerc):
    """ Front Panel Heap ver c

    Stored in "FPHx"-block. It uses a binary tree format to store hierarchy
    structures. They use a kind of "xml-tags" to open and close objects.
    """
    pass


class RTSG(CompleteBlock):
    """ Runtime Signature Guid

    """
    def createSection(self):
        section = super().createSection()
        section.content = []
        return section

    def setDefaultEncoding(self):
        self.default_block_coding = BLOCK_CODING.NONE

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]
        section.content = []

        guid = bldata.read(16)
        section.content.append(guid)

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]

        data_buf = b''
        for guid in section.content:
            data_buf += guid[:16]
        return data_buf

    def expectedRSRCSize(self, section_num):
        exp_whole_len = 0
        exp_whole_len += 16
        return exp_whole_len

    def initWithXMLSectionData(self, section, section_elem):
        section.content = []

        for subelem in section_elem:
            if (subelem.tag == "NameObject"):
                pass # Items parsed somewhere else
            elif (subelem.tag == "Guid"):
                guid = bytes.fromhex(subelem.text)
                section.content.append(guid)
            else:
                raise AttributeError("Section contains unexpected tag")
        pass

    def exportXMLSectionData(self, section_elem, section_num, section, fname_base):
        for guid in section.content:
            subelem = ET.SubElement(section_elem,"Guid")
            subelem.text = guid.hex()
        pass


class GCPR(CompleteBlock):
    """ Generated Code Profiler settings

    """
    def createSection(self):
        section = super().createSection()
        section.content = []
        return section

    def setDefaultEncoding(self):
        self.default_block_coding = BLOCK_CODING.NONE

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]
        section.content = []

        section.prop1 = int.from_bytes(bldata.read(4), byteorder='big', signed=True)
        section.propBool4 = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        section.propBool5 = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        section.propBool6 = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        section.propBool7 = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        section.propBool8 = int.from_bytes(bldata.read(1), byteorder='big', signed=False)

        count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        for i in range(count):
            client = SimpleNamespace()
            client.prop1 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            client.prop2 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            client.prop3 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            client.prop4 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            client.prop5 = readLStr(bldata, 1, self.po)
            section.content.append(client)
        pass

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]

        data_buf = b''

        data_buf += int(section.prop1).to_bytes(4, byteorder='big', signed=True)
        data_buf += int(section.propBool4).to_bytes(1, byteorder='big', signed=False)
        data_buf += int(section.propBool5).to_bytes(1, byteorder='big', signed=False)
        data_buf += int(section.propBool6).to_bytes(1, byteorder='big', signed=False)
        data_buf += int(section.propBool7).to_bytes(1, byteorder='big', signed=False)
        data_buf += int(section.propBool8).to_bytes(1, byteorder='big', signed=False)

        data_buf += len(section.content).to_bytes(4, byteorder='big', signed=False)
        for client in section.content:
            data_buf += int(client.prop1).to_bytes(4, byteorder='big', signed=False)
            data_buf += int(client.prop2).to_bytes(4, byteorder='big', signed=False)
            data_buf += int(client.prop3).to_bytes(4, byteorder='big', signed=False)
            data_buf += int(client.prop4).to_bytes(4, byteorder='big', signed=False)
            data_buf += prepareLStr(client.prop5, 1, self.po)

        return data_buf

    def expectedRSRCSize(self, section_num):
        section = self.sections[section_num]
        exp_whole_len = 0
        exp_whole_len += 4 + 5 * 1
        exp_whole_len += 4
        for client in section.content:
            exp_whole_len += 4 + 4 + 4 + 4
            exp_whole_len += 4 + len(client.prop5)
        return exp_whole_len

    def initWithXMLSectionData(self, section, section_elem):
        section.content = []

        section.prop1 = section_elem.get("Prop1")
        section.propBool4 = section_elem.get("PropBool4")
        section.propBool5 = section_elem.get("PropBool5")
        section.propBool6 = section_elem.get("PropBool6")
        section.propBool7 = section_elem.get("PropBool7")
        section.propBool8 = section_elem.get("PropBool8")

        for subelem in section_elem:
            if (subelem.tag == "NameObject"):
                pass # Items parsed somewhere else
            elif (subelem.tag == "NodeData"):
                client = SimpleNamespace()
                client.prop1 = subelem.get("Prop1")
                client.prop2 = subelem.get("Prop2")
                client.prop3 = subelem.get("Prop3")
                client.prop4 = subelem.get("Prop4")
                if subelem.text is not None:
                    elem_text = ET.unescape_safe_store_element_text(subelem.text)
                    client.prop5 = elem_text.encode(self.vi.textEncoding)
                else:
                    client.prop5 = b''
                section.content.append(client)
            else:
                raise AttributeError("Section contains unexpected tag")
        pass

    def exportXMLSectionData(self, section_elem, section_num, section, fname_base):
        section_elem.set("Prop1", "{:d}".format(section.prop1))
        section_elem.set("PropBool4", "{:d}".format(section.propBool4))
        section_elem.set("PropBool5", "{:d}".format(section.propBool5))
        section_elem.set("PropBool6", "{:d}".format(section.propBool6))
        section_elem.set("PropBool7", "{:d}".format(section.propBool7))
        section_elem.set("PropBool8", "{:d}".format(section.propBool8))

        for client in section.content:
            subelem = ET.SubElement(section_elem,"NodeData")
            subelem.set("Prop1", "{:d}".format(client.prop1))
            subelem.set("Prop2", "{:d}".format(client.prop2))
            subelem.set("Prop3", "{:d}".format(client.prop3))
            subelem.set("Prop4", "{:d}".format(client.prop4))
            pretty_string = client.prop5.decode(self.vi.textEncoding)
            ET.safe_store_element_text(subelem, pretty_string)
        pass


class UCRF(VarCodingBlock):
    """ Uncompressed Resource File

        Keeps content of files within LLB library.
    """
    def createSection(self):
        section = super().createSection()
        return section

    def setDefaultEncoding(self):
        self.default_block_coding = BLOCK_CODING.NONE

    def exportXMLSection(self, section_elem, snum, section, fname_base):
        fext = "rsrc"
        if self.po.keep_names:
            fname_split = os.path.splitext(section.name_text.decode(self.vi.textEncoding, errors="ignore"))
            fext_try = ""
            if len(fname_split) >= 2:
                fext_try = fname_split[1][1:]
                fext_try = re.sub('[\\/\r\n*:<>|\0]+', '-', fext_try)
                fext_try = fext_try.strip('.- ')
            if len(fext_try) > 0:
                fext = fext_try
        bldata = self.getData(section_num=snum)
        # Check what kind of RSRC file we have, to give it proper extension
        rsrchead = LVrsrcontainer.RSRCHeader(self.po)
        if bldata.readinto(rsrchead) == sizeof(rsrchead):
            if rsrchead.checkSanity():
                fext = LVrsrcontainer.getFileExtByType(rsrchead.ftype)
        bldata.seek(0)
        block_fname = "{:s}.{:s}".format(fname_base,fext)
        with open(block_fname, "wb") as block_fh:
            if (self.po.verbose > 1):
                print("{}: Writing block {} section {} to '{}'".format(self.vi.src_fname,self.ident,snum,block_fname))
            block_fh.write(bldata.read())

        section_elem.set("Format", "bin")
        section_elem.set("File", os.path.basename(block_fname))

    def exportFilesBase(self, snum, section):
        block_fpath = os.path.dirname(self.po.xml)

        if self.po.keep_names and section.name_text is not None and len(section.name_text) > 1:
            fname_base = section.name_text.decode(self.vi.textEncoding, errors="ignore")
            fname_split = os.path.splitext(fname_base)
            fname_base = fname_split[0]
        else:
            fname_base = self.po.filebase
        # Every OS has a set of characters which are not valid for use in file names
        fname_base = re.sub('[\\/*?:<>|\x00-\x1f]+', '-', fname_base)
        if len(fname_base) > 0:
            if fname_base[0] == '-': fname_base = 'm' + fname_base[1:]
            elif fname_base[0] == '+': fname_base = 'p' + fname_base[1:]

        if self.po.keep_names:
            all_section_names = [ sect.name_text for sect in self.sections.values() ]
            if all_section_names.count(section.name_text) == 1:
                fname_base = "{:s}".format(fname_base)
            else:
                if snum >= 0:
                    snum_str = str(snum)
                else:
                    snum_str = 'm' + str(-snum)
                fname_base = "{:s}_{:s}".format(fname_base, snum_str)
        else:
            pretty_ident = getPrettyStrFromRsrcType(self.ident)
            if len(self.sections) == 1:
                fname_base = "{:s}_{:s}".format(fname_base, pretty_ident)
            else:
                if snum >= 0:
                    snum_str = str(snum)
                else:
                    snum_str = 'm' + str(-snum)
                fname_base = "{:s}_{:s}{:s}".format(fname_base, pretty_ident, snum_str)

        if len(block_fpath) > 0:
            fname_base = block_fpath + '/' + fname_base
        return fname_base


class CPRF(UCRF):
    """ 'Comp' Compressed Resource File

        Keeps content of files within LLB library.
    """
    def createSection(self):
        section = super().createSection()
        return section

    def setDefaultEncoding(self):
        self.default_block_coding = BLOCK_CODING.COMP


class ZCRF(UCRF):
    """ ZLib Compressed Resource File

        Keeps content of files within LLB library.
    """
    def createSection(self):
        section = super().createSection()
        return section

    def setDefaultEncoding(self):
        self.default_block_coding = BLOCK_CODING.ZLIB


class DLG3(UCRF):
    """ Dialog Resource File

        Used in Resource Packages like lvapp, lvstring, etc.
    """
    def createSection(self):
        section = super().createSection()
        return section

    def setDefaultEncoding(self):
        self.default_block_coding = BLOCK_CODING.NONE


class VCTP(CompleteBlock):
    """ VI Consolidated Data Types

    All data types used by the .VI and the data types of the .VI itself are stored
    in this block.

    The VCTP contains bottom-up objects. This means that objects can inherit
    from previous defined objects. So to define a cluster they first define
    every element and then add a cluster-object with a index-table containing
    all previously defined elements used by the cluster.
    """
    def createSection(self):
        section = super().createSection()
        section.content = []
        section.topLevel = []
        return section

    def setDefaultEncoding(self):
        self.default_block_coding = BLOCK_CODING.ZLIB

    def parseRSRCTypeDesc(self, section_num, bldata, pos):
        section = self.sections[section_num]

        bldata.seek(pos)
        obj_type, obj_flags, obj_len = TDObject.parseRSRCDataHeader(bldata)
        if (self.po.verbose > 2):
            print("{:s}: Block {} TypeDesc {:d}, at 0x{:04x}, type 0x{:02x} flags 0x{:02x} len {:d}"\
              .format(self.vi.src_fname, self.ident, len(section.content), pos, obj_type, obj_flags, obj_len))
        if obj_len < 4:
            eprint("{:s}: Warning: TypeDesc {:d} type 0x{:02x} data size {:d} too small to be valid"\
              .format(self.vi.src_fname, len(section.content), obj_type, obj_len))
            obj_type = TD_FULL_TYPE.Void
        obj = newTDObject(self.vi, len(section.content), obj_flags, obj_type, self.po)

        clientTD = SimpleNamespace()
        clientTD.index = -1 # Nested clients have index -1
        clientTD.flags = 0 # Only Type Mapped entries have it non-zero
        clientTD.nested = obj
        section.content.append(clientTD)
        bldata.seek(pos)
        obj.initWithRSRC(bldata, obj_len) # No need to set topTypeList within VCTP
        return obj.index, obj_len

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]
        section.content = []
        # First we have count of TDs, and then the TypeDescs themselves
        count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        pos = bldata.tell()
        for i in range(count):
            obj_idx, obj_len = self.parseRSRCTypeDesc(section_num, bldata, pos)
            pos += obj_len
        # After that, there is a list
        section.topLevel = []
        count = readVariableSizeFieldU2p2(bldata)
        for i in range(count):
            val = readVariableSizeFieldU2p2(bldata)
            section.topLevel.append(val)
        pass

    def expectedRSRCSize(self, section_num):
        exp_whole_len = None
        return exp_whole_len

    def initWithXMLSectionData(self, section, section_elem):
        section.content = []
        section.topLevel = []
        for subelem in section_elem:
            if (subelem.tag == "NameObject"):
                pass # Items parsed somewhere else
            elif (subelem.tag == "TypeDesc"):
                obj_idx = len(section.content)
                obj_type = valFromEnumOrIntString(TD_FULL_TYPE, subelem.get("Type"))
                obj_flags = importXMLBitfields(TYPEDESC_FLAGS, subelem)
                obj = newTDObject(self.vi, obj_idx, obj_flags, obj_type, self.po)
                clientTD = SimpleNamespace()
                clientTD.index = -1 # Nested clients have index -1
                clientTD.flags = 0 # Only Type Mapped entries have it non-zero
                clientTD.nested = obj
                section.content.append(clientTD)
                # Set TypeDesc data based on XML properties
                obj.initWithXML(subelem)
            elif (subelem.tag == "TopLevel"):
                for subtlelem in subelem:
                    if (subtlelem.tag == "TypeDesc"):
                        i = int(subtlelem.get("Index"), 0) - 1
                        val = int(subtlelem.get("FlatTypeID"), 0)
                        # Grow the list if needed (the labels may be in wrong order)
                        if i >= len(self.topLevel):
                            self.topLevel.extend([None] * (i - len(self.topLevel) + 1))
                        self.topLevel[i] = val
                    else:
                        raise AttributeError("TopLevel within Section contains unexpected tag")
            else:
                raise AttributeError("Section contains unexpected tag")
        pass

    def initWithXMLLate(self):
        super().initWithXMLLate()
        for snum in self.sections:
            section = self.sections[snum]
            for clientTD in section.content:
                clientTD.nested.initWithXMLLate()
        pass

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]

        for clientTD in section.content:
            if not clientTD.nested.raw_data_updated:
                clientTD.nested.updateData()

        data_buf = b''
        data_buf += len(section.content).to_bytes(4, byteorder='big')
        for i, clientTD in enumerate(section.content):
            bldata = clientTD.nested.getData()
            data_buf += bldata.read()

        data_buf += int(len(section.topLevel)).to_bytes(2, byteorder='big')
        for i, val in enumerate(section.topLevel):
            data_buf += int(val).to_bytes(2, byteorder='big')
        return data_buf

    def exportXMLSectionData(self, section_elem, section_num, section, fname_base):
        for clientTD in section.content:
            if len(clientTD.nested.full_name) > 0:
                comment_elem = ET.Comment(" FlatTypeID {:d}: {} "\
                  .format(clientTD.nested.index, clientTD.nested.full_name))
            else:
                comment_elem = ET.Comment(" FlatTypeID {:d}: {} "\
                  .format(clientTD.nested.index,"Type Descriptor"))
            section_elem.append(comment_elem)
            subelem = ET.SubElement(section_elem,"TypeDesc")

            subelem.set("Type", "{:s}".format(stringFromValEnumOrInt(TD_FULL_TYPE, clientTD.nested.otype)))

            if not self.po.raw_connectors:
                clientTD.nested.exportXML(subelem, fname_base)
                clientTD.nested.exportXMLFinish(subelem)
            else:
                TDObject.exportXML(clientTD.nested, subelem, fname_base)
                TDObject.exportXMLFinish(clientTD.nested, subelem)

        toplstelem = ET.SubElement(section_elem,"TopLevel")
        comment_elem = ET.Comment(" When Consolidated Type is referred to in other blocks, the TypeID is Index from this list ")
        toplstelem.append(comment_elem)

        for i, val in enumerate(self.topLevel):
            subelem = ET.SubElement(toplstelem,"TypeDesc")

            subelem.set("Index", "{:d}".format(i+1))
            subelem.set("FlatTypeID", "{:d}".format(val))
        pass

    def parseData(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        # Besides the normal parsing, also parse sub-objects
        needParse = self.needParseData(section_num=section_num)
        Block.parseData(self, section_num=section_num)
        if needParse:
            for clientTD in section.content:
                clientTD.nested.parseData()
            self.commentSpecialTypes(section_num)

    def checkSanity(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        ret = True
        for clientTD in section.content:
            if not clientTD.nested.checkSanity():
                ret = False
        for i, val in enumerate(section.topLevel):
            if val >= len(section.content):
                if (self.po.verbose > 1):
                    eprint("{:s}: Warning: TopLevel index {:d} exceeds flat TD count {:d}"\
                      .format(self.vi.src_fname,i,len(section.content)))
                ret = False
        return ret

    def commentSpecialTypes(self, section_num):
        """ Set lists of values to special types

        This finds data types with VI options, and sets their comments so that
        they're easier to understand within the XML file.
        """
        section = self.sections[section_num]
        topRange = range(1,len(section.topLevel)+1)
        # If we have Type Map, check only items which are there
        TM = self.vi.get_one_of('TM80', 'DSTM')
        if TM is not None:
            topRange = range(TM.getMinTypeId(), TM.getMaxTypeId())
        # Make flat range, leaving only valid entries to avoid multiplying checks
        flatRange = []
        for typeId in topRange:
            flatIdx = len(section.topLevel)+1
            if typeId >= 1 and typeId <= len(section.topLevel):
                flatIdx = section.topLevel[typeId-1]
            if flatIdx >= len(section.content):
                continue
            flatRange.append(flatIdx)
        # Now find the special types
        from LVdatatype import TD_FULL_TYPE
        for flatIdx in flatRange:
            clientTD = section.content[flatIdx]
            if clientTD.nested.fullType() != TD_FULL_TYPE.RepeatedBlock or clientTD.nested.getNumRepeats() != 51:
                continue
            clientTD.nested.setDataFillComments( {e.value: e.name for e in LVparts.DSINIT} )
            break
        for flatIdx in flatRange:
            clientTD = section.content[flatIdx]
            if clientTD.nested.fullType() != TD_FULL_TYPE.RepeatedBlock:
                continue
            td_clust = None
            for cli_idx, td_idx, td_obj, td_flags in clientTD.nested.clientsEnumerate():
                td_clust = td_obj
            if td_clust is None or td_clust.fullType() != TD_FULL_TYPE.Cluster:
                continue
            match = True
            for cli_idx, td_idx, td_obj, td_flags in td_clust.clientsEnumerate():
                if cli_idx >= len(LVparts.DCO._fields_):
                    match = False
                    break
                expectedCType = LVparts.DCO._fields_[cli_idx][1]
                expectedType = ctypeToFullTypeEnum(expectedCType)
                if expectedType is not None and td_obj.fullType() != expectedType:
                    match = False
                    break
            if match:
                td_clust.setDataFillComments( {i: e[0] for i,e in enumerate(LVparts.DCO._fields_)} )
            break

    def getContent(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        self.parseData(section_num=section_num)
        section = self.sections[section_num]
        return section.content

    def getClientTypeDescsByType(self, conn_obj):
        self.parseData() # Make sure the block is parsed
        type_list = conn_obj.getClientTypeDescsByType()
        if (self.po.verbose > 1):
            print("{:s}: Terminal {:d} TypeDesc: {:s}={:d} {:s}={:d} {:s}={:d} {:s}={:d} {:s}={:d}"\
              .format(self.vi.src_fname,conn_obj.index,\
              'number',len(type_list['number']),\
              'path',len(type_list['path']),\
              'string',len(type_list['string']),\
              'compound',len(type_list['compound']),\
              'other',len(type_list['other'])))
        return type_list

    def getFlatType(self, flatIdx, section_num=None):
        """ Retrieves type of given flat list index

        It is better to call types by their top index - this is how mosts
        functions are doing. But when we need a type from the underlying
        flat list, this is the function to use.
        """
        if section_num is None:
            section_num = self.active_section_num
        self.parseData(section_num=section_num)
        section = self.sections[section_num]
        clientTD = section.content[flatIdx]
        return clientTD.nested

    def getTopType(self, idx, section_num=None):
        """ Retrieves top type of given index
        """
        if section_num is None:
            section_num = self.active_section_num
        self.parseData(section_num=section_num)
        section = self.sections[section_num]
        if idx < 1:
            return None
        idx -= 1
        if len(section.topLevel) <= idx:
            return None
        flatIdx = section.topLevel[idx]
        if len(section.content) <= flatIdx:
            return None
        clientTD = section.content[flatIdx]
        return clientTD.nested


class VICD(CompleteBlock):
    """ Virtual Instrument Compiled Data / VI Code

    This section stores the CPU bytecode generated by a compiler,
    usually LLVM. It is an equivalent of OBJ file. The code
    is linked with OS-specific parts stored within LVRT when
    the project is executed.
    """
    def createSection(self):
        section = super().createSection()
        # Exported file Content Map
        section.ct_map = []
        # Properties at beginning
        section.initProcOffset = 0
        section.codeID = b''
        section.pTabOffset = 0
        section.codeFlags = 0
        section.version = 0
        section.verifier = b''
        section.numberOfBasicBlocks = 0
        section.compilerOptimizationLevel = 0
        section.hostCodeEntryVI = 0
        section.codeEndOffset = 0
        section.signatureName = 0
        # The actual code
        section.content = b''
        section.patches = b''
        # Properties at end
        section.endVerifier = b''
        section.endProp1 = 0
        section.endSignatureName = 0
        section.endLocalLVRTCodeBlocks = 0
        section.endCodeEndOffset = 0
        section.endProp5 = 0
        return section

    def setDefaultEncoding(self):
        ver = self.vi.getFileVersion()
        # verified NONE in 5.1, ZLIB in 8.6
        if isGreaterOrEqVersion(ver, 8,0,0,3):
            self.default_block_coding = BLOCK_CODING.ZLIB
        else:
            self.default_block_coding = BLOCK_CODING.NONE

    @staticmethod
    def addMapEntry(section, fh, eSize, eName, eKind):
        """ Adds element to a MAP array for the file.

        Uses name mangling from MsVS. Not that I like it, it's just the most
        popular ATM - disassembler will read them.
        """
        eArr = "PA" if  eKind.endswith("[]") else ""
        if eKind.startswith("i8"):
            fullName = "?{}@@3{}CA".format(eName, eArr)
        elif eKind.startswith("i16"):
            fullName = "?{}@@3{}FA".format(eName, eArr)
        elif eKind.startswith("i32"):
            fullName = "?{}@@3{}HA".format(eName, eArr)
        elif eKind.startswith("i64"):
            fullName = "?{}@@3{}_JA".format(eName, eArr)
        elif eKind.startswith("u8"):
            fullName = "?{}@@3{}EA".format(eName, eArr)
        elif eKind.startswith("u16"):
            fullName = "?{}@@3{}GA".format(eName, eArr)
        elif eKind.startswith("u32"):
            fullName = "?{}@@3{}IA".format(eName, eArr)
        elif eKind.startswith("u64"):
            fullName = "?{}@@3{}_KA".format(eName, eArr)
        else:
            fullName = "{}".format(eName)
        section.ct_map.append( (fh.tell()-eSize, eSize, fullName,) )

    @staticmethod
    def printMap(section, fh):
        fh.write("  Address         Publics by Value\n\n")
        for e in section.ct_map:
            fh.write(" {:04X}:{:08X}       {:s}\n".format(1,e[0],e[2]))
        pass

    def parseRSRCSectionData(self, section_num, bldata):
        ver = self.vi.getFileVersion()
        section = self.sections[section_num]
        section.ct_map = []

        headStartPos = bldata.tell()
        initProcOffset = bldata.read(4)
        self.addMapEntry(section, bldata, 4, "initProcOffset", "u32")
        section.codeID = bldata.read(4)
        self.addMapEntry(section, bldata, 4, "codeID", "u8[]")
        archDependLen = 8 if self.isX64(section_num) else 4
        archEndianness = 'little' if self.isLE(section_num) else 'big'
        if isGreaterOrEqVersion(ver, 12,0,0,0):# Should be False for LV 11,0,0,4, True for 14,0,0,3
            section.initProcOffset = int.from_bytes(initProcOffset, byteorder=archEndianness, signed=False)
            section.pTabOffset = int.from_bytes(bldata.read(4), byteorder=archEndianness, signed=False)
            self.addMapEntry(section, bldata, 4, "pTabOffset", "u32")
            section.codeFlags = int.from_bytes(bldata.read(4), byteorder=archEndianness, signed=False)
            self.addMapEntry(section, bldata, 4, "codeFlags", "u32")
            section.version = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            self.addMapEntry(section, bldata, 4, "version", "u32")
            section.verifier = bldata.read(4)
            self.addMapEntry(section, bldata, 4, "verifier", "u8[]")
            section.numberOfBasicBlocks = int.from_bytes(bldata.read(4), byteorder=archEndianness, signed=False)
            self.addMapEntry(section, bldata, 4, "numberOfBasicBlocks", "u32")
            section.compilerOptimizationLevel = int.from_bytes(bldata.read(4), byteorder=archEndianness, signed=False)
            self.addMapEntry(section, bldata, 4, "compilerOptimizationLevel", "u32")
            section.hostCodeEntryVI = int.from_bytes(bldata.read(4), byteorder=archEndianness, signed=False)
            self.addMapEntry(section, bldata, 4, "hostCodeEntryVI", "u32")
            section.codeEndOffset = int.from_bytes(bldata.read(archDependLen), byteorder=archEndianness, signed=False)
            self.addMapEntry(section, bldata, archDependLen, "codeEndOffset", "u64" if archDependLen == 8 else "u32")
            section.signatureName = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            self.addMapEntry(section, bldata, 4, "signatureName", "u32")
        else: # Lowest version tested with this is LV 6,0,0,2
            section.initProcOffset = int.from_bytes(initProcOffset, byteorder=archEndianness, signed=False)
            section.pTabOffset = int.from_bytes(bldata.read(4), byteorder=archEndianness, signed=False)
            self.addMapEntry(section, bldata, 4, "pTabOffset", "u32")
            section.codeFlags = int.from_bytes(bldata.read(4), byteorder=archEndianness, signed=False)
            self.addMapEntry(section, bldata, 4, "codeFlags", "u32")
            section.version = int.from_bytes(bldata.read(4), byteorder='big', signed=False) # doesn't seem to really be version
            self.addMapEntry(section, bldata, 4, "version", "u32")
            section.verifier = bldata.read(4)
            self.addMapEntry(section, bldata, 4, "verifier", "u8[]")
            section.numberOfBasicBlocks = int.from_bytes(bldata.read(4), byteorder=archEndianness, signed=False)
            self.addMapEntry(section, bldata, 4, "numberOfBasicBlocks", "u32")
            section.codeEndOffset = int.from_bytes(bldata.read(archDependLen), byteorder=archEndianness, signed=False)
            self.addMapEntry(section, bldata, archDependLen, "codeEndOffset", "u64" if archDependLen == 8 else "u32")
            section.hostCodeEntryVI = int.from_bytes(bldata.read(4), byteorder=archEndianness, signed=False)
            self.addMapEntry(section, bldata, 4, "hostCodeEntryVI", "u32")
            section.signatureName = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            self.addMapEntry(section, bldata, 4, "signatureName", "u32")
        headLen = bldata.tell() - headStartPos
        section.content = bldata.read(section.pTabOffset - headLen)
        self.addMapEntry(section, bldata, section.pTabOffset - headLen, "codeBlob", "VarElemLenArray")
        section.patches = bldata.read(section.codeEndOffset - section.pTabOffset)
        self.addMapEntry(section, bldata, section.codeEndOffset - section.pTabOffset, "patch_{}".format(0), "VarElemLenArray")

        section.endVerifier = bldata.read(4)
        self.addMapEntry(section, bldata, 4, "endVerifier", "u8[]")
        section.endProp1 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        if isGreaterOrEqVersion(ver, 7,0,0,0):# Should be False for LV 6,0,0,2, True for 7,1,0,3
            #TODO inconsistency - signatureName doesn't have arch-dependant size
            section.endSignatureName = int.from_bytes(bldata.read(archDependLen), byteorder='big', signed=False)
            self.addMapEntry(section, bldata, archDependLen, "endSignatureName", "u64" if archDependLen == 8 else "u32")
            section.endLocalLVRTCodeBlocks = int.from_bytes(bldata.read(archDependLen), byteorder='big', signed=False)
            self.addMapEntry(section, bldata, archDependLen, "endLocalLVRTCodeBlocks", "u64" if archDependLen == 8 else "u32")
        #TODO inconsistency - codeEndOffset has arch-dependant size
        section.endCodeEndOffset = int.from_bytes(bldata.read(4), byteorder=archEndianness, signed=False)
        self.addMapEntry(section, bldata, 4, "endCodeEndOffset", "u32")
        if isGreaterOrEqVersion(ver, 12,0,0,0):# Should be False for 11,0,0,4, True for 14,0,0,3
            #TODO maybe it's just for 64-bit arch? a missing part of endCodeEndOffset?
            section.endProp5 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            self.addMapEntry(section, bldata, 4, "endProp5", "u32")
        pass

    def exportXMLSectionData(self, section_elem, section_num, section, fname_base):
        subelem = ET.SubElement(section_elem,"General")

        subelem.set("CodeID", getPrettyStrFromRsrcType(section.codeID))
        subelem.set("CodeFlags", "0x{:X}".format(section.codeFlags))
        subelem.set("Version", "0x{:X}".format(section.version))
        subelem.set("CompilerOptimizationLevel", "{:d}".format(section.compilerOptimizationLevel))
        subelem.set("Verifier", getPrettyStrFromRsrcType(section.verifier))

        subelem = ET.SubElement(section_elem,"Code")
        subelem.set("InitProcOffset", "0x{:X}".format(section.initProcOffset))
        subelem.set("PTabOffset", "0x{:X}".format(section.pTabOffset))
        subelem.set("NumberOfBasicBlocks", "{:d}".format(section.numberOfBasicBlocks))
        subelem.set("HostCodeEntryVI", "0x{:X}".format(section.hostCodeEntryVI))
        subelem.set("CodeEndOffset", "0x{:X}".format(section.codeEndOffset))
        subelem.set("SignatureName", "0x{:X}".format(section.signatureName))

        map_fname = "{:s}.{:s}".format(fname_base,"map")
        if (self.po.verbose > 1):
            print("{}: Writing code MAP file for block {} section {:d}"\
              .format(self.vi.src_fname, self.ident, section_num))
        with open(map_fname, "w") as map_fh:
            self.printMap(section, map_fh)

        raise NotImplementedError("The block is only partially exported as XML")

    def checkSanity(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]

        ret = True
        if section.initProcOffset >= section.pTabOffset:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: InitProcOffset 0x{:X} exceeds PTabOffset 0x{:X}"\
                  .format(self.vi.src_fname, section.initProcOffset, section.pTabOffset))
            ret = False
        if section.pTabOffset >= section.codeEndOffset:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: PTabOffset 0x{:X} exceeds CodeEndOffset 0x{:X}"\
                  .format(self.vi.src_fname, section.pTabOffset, section.codeEndOffset))
            ret = False
        if section.codeEndOffset != section.endCodeEndOffset:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: Copies of CodeEndOffset are different (0x{:X} and 0x{:X})"\
                  .format(self.vi.src_fname, section.codeEndOffset, section.endCodeEndOffset))
            ret = False
        if section.verifier not in (b'code',):
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: Verifier property {} is not known"\
                  .format(self.vi.src_fname, section.verifier))
            ret = False
        if section.endVerifier not in (b'CODE',):
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: EndVerifier property {} is not known"\
                  .format(self.vi.src_fname, section.endVerifier))
            ret = False
        return ret

    def isX64(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]
        return ( section.codeID in (b'wx64', b'ux64', b'mx64',) )

    def isLE(self, section_num=None):
        if section_num is None:
            section_num = self.active_section_num
        section = self.sections[section_num]
        return ( section.codeID in (b'i386', b'wx64', b'ux86', b'ux64',\
          b'm386', b'mx64', b'PWNT', b'axwn', b'axlx', b'axdu', b'ARM ',) )


class VITS(CompleteBlock):
    """ Virtual Instrument Tag Strings
    """
    def createSection(self):
        section = super().createSection()
        section.parse_failed = False
        section.content = []
        section.endianness = 'big'
        return section

    def parseRSRCSectionData(self, section_num, bldata):
        section = self.sections[section_num]
        ver = self.vi.getFileVersion()
        section.content = []
        section.endianness = 'big'

        # Get count of tags; endianness was wrong in some versions
        if isGreaterOrEqVersion(ver, 6,1,0,4):
            count = int.from_bytes(bldata.read(4), byteorder=section.endianness, signed=False)
        else:
            # We can't be sure whether the enianness in this version is correct or not. We have to check that
            count = int.from_bytes(bldata.read(4), byteorder=section.endianness, signed=False)
            if (count & 0xFFFF0000) != 0:
                count = int.from_bytes(count.to_bytes(4, byteorder=section.endianness), byteorder='little', signed=False)
                section.endianness = 'little'
        if count > self.po.typedesc_list_limit:
            raise RuntimeError("Tag String list consists of {:d} tags, limit is {:d}"\
              .format(count,self.po.typedesc_list_limit))

        for i in range(count):
            val = SimpleNamespace()
            val.name = readLStr(bldata, 1, self.po)
            if isSmallerVersion(ver, 6,5,0,2):
                bldata.read(4)
            val.obj = LVdatafill.newDataFillObject(self.vi, TD_FULL_TYPE.LVVariant, None, self.po)
            val.obj.useConsolidatedTypes = False
            val.obj.initWithRSRC(bldata)
            section.content.append(val)
        pass

    def prepareRSRCData(self, section_num):
        section = self.sections[section_num]
        ver = self.vi.getFileVersion()
        data_buf = b''
        # Endianness was wrong in some versions
        data_buf += len(section.content).to_bytes(4, byteorder=section.endianness, signed=False)
        for val in section.content:
            data_buf += prepareLStr(val.name, 1, self.po)
            if isSmallerVersion(ver, 6,5,0,2):
                data_buf += ( b'\0' * 4 )
            data_buf += val.obj.prepareRSRCData()
        return data_buf

    def expectedRSRCSize(self, section_num):
        exp_whole_len = None
        return exp_whole_len

    def initWithXMLSectionData(self, section, section_elem):
        section.content = []
        section.endianness = 'big'

        endianness = section_elem.get("Endianness")
        if endianness in ('little','big',):
            section.endianness = endianness
        for subelem in section_elem:
            if (subelem.tag == "NameObject"):
                continue # Items parsed somewhere else

            val = SimpleNamespace()
            name_str = subelem.get("Name")
            val.name = name_str.encode(self.vi.textEncoding)
            val.obj = LVdatafill.newDataFillObjectWithTag(self.vi, subelem.tag, self.po)
            val.obj.useConsolidatedTypes = False
            val.obj.initWithXML(subelem)
            section.content.append(val)
        pass

    def initWithXMLLate(self):
        super().initWithXMLLate()
        for snum in self.sections:
            section = self.sections[snum]
            for val in section.content:
                val.obj.initWithXMLLate()
        pass

    def exportXMLSectionData(self, section_elem, section_num, section, fname_base):
        if section.endianness != 'big':
            section_elem.set("Endianness", section.endianness)
        for i, val in enumerate(section.content):
            subelem = ET.SubElement(section_elem, "Object")
            subelem.set("Name", val.name.decode(self.vi.textEncoding))

            val.obj.exportXML(subelem, fname_base)
        pass

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" LabView RSRC file parser - Resource Container.

    Can read content of the main headers and list of resources within RSRC files.
"""

# Copyright (C) 2013 Jessica Creighton <jcreigh@femtobit.org>
# Copyright (C) 2019 Mefistotelis <mefistotelis@gmail.com>
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

import sys
import re
import os
import enum
import binascii
from ctypes import *
from hashlib import md5

import LVblock
import LVdatatype
import LVxml as ET
from LVmisc import *

class FILE_FMT_TYPE(enum.Enum):
    NONE = 0
    Control = 1
    DLog = 2
    ClassLib = 3
    Project = 4
    Library = 5
    PackedProjLib = 6
    LLB = 7
    MenuPalette = 8
    TemplateControl = 9
    TemplateVI = 10
    Xcontrol = 11
    UsrIfaceResrc = 12
    RFilesService = 13
    RFilesOld = 14
    Subroutine = 15
    VI = 16
    Zero = 17


class RSRCHeader(RSRCStructure):
    _fields_ = [('rsrc_id1', c_ubyte * 6),		#0
                ('rsrc_fmtver', c_ushort),			#6
                ('rsrc_type', c_ubyte * 4),		#8 4-byte identifier of file type
                ('rsrc_id4', c_ubyte * 4),		#12
                ('rsrc_info_offset', c_uint32),	#16 Offset from beginning of the file to RSRC header before the Info part
                ('rsrc_info_size', c_uint32),	#20
                ('rsrc_data_offset', c_uint32),#24 Offset from beginning of the file to RSRC header before the Data part
                ('rsrc_data_size', c_uint32),	#28, sizeof is 32
    ]

    def __init__(self, po, fmtver=3):
        self.po = po
        self.rsrc_fmtver = fmtver
        if fmtver >= 3:
            self.rsrc_id1 = (c_ubyte * sizeof(self.rsrc_id1)).from_buffer_copy(b'RSRC\r\n')
        else:
            self.rsrc_id1 = (c_ubyte * sizeof(self.rsrc_id1)).from_buffer_copy(b'RSRC\0\0')
        self.rsrc_type = (c_ubyte * sizeof(self.rsrc_type)).from_buffer_copy(b'LVIN')
        self.rsrc_id4 = (c_ubyte * sizeof(self.rsrc_id4)).from_buffer_copy(b'LBVW')
        self.ftype = FILE_FMT_TYPE.NONE
        self.rsrc_data_offset = sizeof(self)
        self.starts = []

    def checkSanity(self):
        ret = True
        if bytes(self.rsrc_id1)  == b'RSRC\r\n':
            pass
        elif self.rsrc_fmtver <= 2 and bytes(self.rsrc_id1) == b'RSRC\0\0':
            pass
        else:
            if (self.po.verbose > 0):
                eprint("{:s}: RSRC Header field '{:s}' has unexpected value: {}".format(self.po.rsrc,'id1',bytes(self.rsrc_id1)))
            ret = False
        self.ftype = recognizeFileTypeFromRsrcType(self.rsrc_type)
        if self.ftype == FILE_FMT_TYPE.NONE:
            if (self.po.verbose > 0):
                eprint("{:s}: RSRC Header field '{:s}' has unexpected value: {}".format(self.po.rsrc,'rsrc_type',bytes(self.rsrc_type)))
            ret = False
        if bytes(self.rsrc_id4) == b'LBVW':
            pass
        elif self.ftype == FILE_FMT_TYPE.RFilesOld and bytes(self.rsrc_id4) == b'ResC':
            pass
        elif self.rsrc_fmtver <= 2 and bytes(self.rsrc_id4) == b'\0\0\0\0':
            # VI format from LV2.5
            pass
        else:
            if (self.po.verbose > 0):
                eprint("{:s}: RSRC Header field '{:s}' has unexpected value: {}".format(self.po.rsrc,'id4',bytes(self.rsrc_id4)))
            ret = False
        if self.rsrc_data_offset < sizeof(self):
            if (self.po.verbose > 0):
                eprint("{:s}: RSRC Header field '{:s}' has unexpected value: {}".format(self.po.rsrc,'rsrc_data_offset',self.rsrc_data_offset))
            ret = False
        return ret


class BlockInfoListHeader(RSRCStructure):
    _fields_ = [('dataset_int1', c_uint32),		#0
                ('dataset_int2', c_uint32),		#4
                ('dataset_int3', c_uint32),		#8
                ('blockinfo_offset', c_uint32),	#12
                ('blockinfo_size', c_uint32),	#16
    ]

    def __init__(self, po):
        self.po = po
        self.dataset_int3 = sizeof(RSRCHeader) # 32; assuming it's size
        self.blockinfo_offset = sizeof(RSRCHeader) + sizeof(self)
        pass

    def checkSanity(self):
        ret = True
        if self.dataset_int3 != sizeof(RSRCHeader):
            if (self.po.verbose > 0):
                eprint("{:s}: BlockInfo List Header field '{:s}' has outranged value: {:d}".format(self.po.rsrc,'dataset_int3',self.dataset_int3))
            ret = False
        if self.blockinfo_offset != sizeof(RSRCHeader) + sizeof(self):
            if (self.po.verbose > 0):
                eprint("{:s}: BlockInfo List Header field '{:s}' has outranged value: {:d}".format(self.po.rsrc,'blockinfo_offset',self.blockinfo_offset))
            ret = False
        return ret


class BlockInfoHeader(RSRCStructure):
    _fields_ = [('blockinfo_count', c_uint32),	#0
    ]

    def __init__(self, po):
        self.po = po
        pass

    def checkSanity(self):
        ret = True
        if self.blockinfo_count > 4096: # Arbitrary limit - hard to tell whether it makes sense
            if (self.po.verbose > 0):
                eprint("{:s}: BlockInfo Header field '{:s}' has outranged value: {:d}".format(self.po.rsrc,'blockinfo_count',self.blockinfo_count))
            ret = False
        return ret


def getRsrcTypeForFileType(ftype):
    """ Gives 4-byte file identifier from FILE_FMT_TYPE member
    """
    file_type = {
        FILE_FMT_TYPE.Control: b'LVCC',
        FILE_FMT_TYPE.DLog: b'LVDL',
        FILE_FMT_TYPE.ClassLib: b'CLIB',
        FILE_FMT_TYPE.Project: b'LVPJ',
        FILE_FMT_TYPE.Library: b'LIBR',
        FILE_FMT_TYPE.PackedProjLib: b'LIBP',
        FILE_FMT_TYPE.LLB: b'LVAR',
        FILE_FMT_TYPE.MenuPalette: b'LMNU',
        FILE_FMT_TYPE.RFilesService: b'LVRS',
        FILE_FMT_TYPE.RFilesOld: b'rsc ',
        FILE_FMT_TYPE.TemplateControl: b'sVCC',
        FILE_FMT_TYPE.TemplateVI: b'sVIN',
        FILE_FMT_TYPE.Xcontrol: b'LVXC',
        FILE_FMT_TYPE.UsrIfaceResrc: b'iUWl',
        FILE_FMT_TYPE.Subroutine: b'LVSB',
        FILE_FMT_TYPE.VI: b'LVIN',
        FILE_FMT_TYPE.Zero: b'\0\0\0\0',
    }.get(ftype, b'')
    return file_type


def recognizeFileTypeFromRsrcType(rsrc_type):
    """ Gives FILE_FMT_TYPE member from given 4-byte file identifier
    """
    rsrc_type_id = bytes(rsrc_type)
    for ftype in FILE_FMT_TYPE:
        curr_rsrc_type_id = getRsrcTypeForFileType(ftype)
        if len(curr_rsrc_type_id) > 0 and (curr_rsrc_type_id == rsrc_type_id):
            return ftype
    return FILE_FMT_TYPE.NONE


def getFileExtByType(ftype):
    """ Returns file extension associated with given FILE_FMT_TYPE member
    """
    fext = {
        FILE_FMT_TYPE.Control: 'ctl',
        FILE_FMT_TYPE.DLog: 'dlog',
        FILE_FMT_TYPE.ClassLib: 'lvclass',
        FILE_FMT_TYPE.Project: 'lvproj',
        FILE_FMT_TYPE.PackedProjLib: 'lvlibp',
        FILE_FMT_TYPE.Library: 'lvlib',
        FILE_FMT_TYPE.LLB: 'llb',
        FILE_FMT_TYPE.MenuPalette: 'mnu',
        FILE_FMT_TYPE.TemplateControl: 'ctt',
        FILE_FMT_TYPE.TemplateVI: 'vit',
        FILE_FMT_TYPE.Xcontrol: 'xctl',
        FILE_FMT_TYPE.UsrIfaceResrc: 'uir',
        FILE_FMT_TYPE.Subroutine: 'lsb',
        FILE_FMT_TYPE.VI: 'vi',
    }.get(ftype, 'rsrc')
    return fext

def getExistingRSRCFileWithBase(filebase):
    """ Returns file extension associated with given FILE_FMT_TYPE member
    """
    for ftype in FILE_FMT_TYPE:
        fext = getFileExtByType(ftype)
        fname = filebase + '.' + fext
        if os.path.isfile(fname):
            return fname
    return ""

class VI():
    def __init__(self, po, rsrc_fh=None, xml_root=None, text_encoding='utf-8'):
        self.rsrc_fh = None
        self.src_fname = ""
        self.xml_root = None
        self.po = po
        self.rsrc_headers = []
        self.fmtver = 3
        self.ftype = FILE_FMT_TYPE.NONE
        self.textEncoding = text_encoding
        self.blocks = None
        self.rsrc_map = []
        self.order_names = None

        if rsrc_fh is not None:
            self.dataSource = "rsrc"
            self.readRSRC(rsrc_fh)
        elif xml_root is not None:
            self.dataSource = "xml"
            self.readXML(xml_root, po.xml)
        else:
            self.dataSource = "new"

    def readRSRCList(self, fh):
        """ Read all RSRC headers from input file and check their sanity.
            After this function, `self.rsrc_headers` is filled with a list of RSRC Headers.
        """
        rsrc_headers = []
        curr_rsrc_pos = -1
        next_rsrc_pos = 0
        while curr_rsrc_pos != next_rsrc_pos:
            curr_rsrc_pos = next_rsrc_pos
            fh.seek(curr_rsrc_pos)
            rsrchead = RSRCHeader(self.po)
            if fh.readinto(rsrchead) != sizeof(rsrchead):
                raise EOFError("Could not read RSRC {:d} Header.".format(len(rsrc_headers)))
            if self.po.print_map == "RSRC":
                self.rsrc_map.append( (fh.tell(), sizeof(rsrchead), \
                  "{}[{}]".format(type(rsrchead).__name__,len(rsrc_headers)),) )
            if (self.po.verbose > 2):
                print(rsrchead)
            if not rsrchead.checkSanity():
                raise IOError("RSRC {:d} Header sanity check failed.".format(len(rsrc_headers)))
            # The last header has offset equal to its start
            if rsrchead.rsrc_info_offset >= curr_rsrc_pos:
                next_rsrc_pos = rsrchead.rsrc_info_offset
            else:
                raise IOError("Invalid position of next item after parsing RSRC {:d} Header: {:d}".format(len(rsrc_headers),rsrchead.rsrc_info_offset))
            rsrc_headers.append(rsrchead)
        self.rsrc_headers = rsrc_headers
        return (len(rsrc_headers) > 0)

    def readRSRCBlockInfo(self, fh):
        """ Read all Block-Infos from the input file.
            The Block-Infos are within last RSRC inside the file.
            This function requires `self.rsrc_headers` to be filled.
            The function returns a list of Block Headers.
        """
        blkinf_rsrchead = self.rsrc_headers[-1]
        # We expect two rsrc_headers in the RSRC file
        # Format version and file type should be identical in both headers
        self.fmtver = blkinf_rsrchead.rsrc_fmtver
        self.ftype = blkinf_rsrchead.ftype

        # Set file position just after Block-Infos RSRC header
        fh.seek(blkinf_rsrchead.rsrc_info_offset + sizeof(blkinf_rsrchead))

        # Read Block-Infos List Header located after last RSRC header
        binflsthead = BlockInfoListHeader(self.po)
        if fh.readinto(binflsthead) != sizeof(binflsthead):
            raise EOFError("Could not read BlockInfoList header.")
        if self.po.print_map == "RSRC":
            self.rsrc_map.append( (fh.tell(), sizeof(binflsthead), \
              "{}".format(type(binflsthead).__name__),) )
        if (self.po.verbose > 2):
            print(binflsthead)
        if not binflsthead.checkSanity():
            raise IOError("BlockInfoList Header sanity check failed.")
        self.binflsthead = binflsthead

        fh.seek(blkinf_rsrchead.rsrc_info_offset + binflsthead.blockinfo_offset)

        binfhead = BlockInfoHeader(self.po)
        if fh.readinto(binfhead) != sizeof(binfhead):
            raise EOFError("Could not read BlockInfo header.")
        if self.po.print_map == "RSRC":
            self.rsrc_map.append( (fh.tell(), sizeof(binfhead),
              "{}".format(type(binfhead).__name__),) )
        if not binfhead.checkSanity():
            raise IOError("BlockInfo Header sanity check failed.")
        if (self.po.verbose > 2):
            print(binfhead)

        tot_blockinfo_count = binfhead.blockinfo_count + 1

        # Read Block Headers
        block_headers = []
        for i in range(0, tot_blockinfo_count):
            block_head = LVblock.BlockHeader(self.po)
            if fh.readinto(block_head) != sizeof(block_head):
                raise EOFError("Could not read BlockInfo header.")
            if self.po.print_map == "RSRC":
                pretty_ident = getPrettyStrFromRsrcType(block_head.ident)
                self.rsrc_map.append( (fh.tell(), sizeof(block_head), \
                  "{}[{}]".format(type(block_head).__name__,pretty_ident),) )

            if (self.po.verbose > 2):
                print(block_head)
            if not block_head.checkSanity():
                raise IOError("Block Header sanity check failed.")
            #t['Count'] = reader.readUInt32() + 1
            #t['Offset'] = blkinf_rsrchead.rsrc_info_offset + binflsthead.blockinfo_offset + reader.readUInt32()
            block_headers.append(block_head)

        if self.po.print_map == "RSRC":
            self.rsrc_map.append( (fh.tell(), sizeof(BlockInfoHeader)+tot_blockinfo_count*sizeof(LVblock.BlockHeader), \
              "BlockInfo",))

        return block_headers

    def readRSRCBlockData(self, fh, block_headers):
        """ Read data sections for all Blocks from the input file.
            This function requires `block_headers` to be passed.
            After this function, `self.blocks` is filled.
        """
        # Create Array of Block; use classes defined within LVblock namespace to read data
        # specific to given block type; when block ident is unrecognized, create generic block
        blocks_arr = []
        for i, block_head in enumerate(block_headers):
            pretty_ident = getPrettyStrFromRsrcType(block_head.ident)
            bfactory = getattr(LVblock, pretty_ident, None)
            # Block may depend on some other informational blocks (ie. version info)
            # so give each block reference to the vi object
            if isinstance(bfactory, type):
                if (self.po.verbose > 1):
                    print("{:s}: Block '{:s}' index {:d} recognized".format(self.src_fname,pretty_ident,i))
                block = bfactory(self, self.po)
            else:
                block = LVblock.Block(self, self.po)
            block.initWithRSRCEarly(block_head)
            blocks_arr.append(block)

        # Create Array of Block Data
        blocks = {}
        for i, block in enumerate(blocks_arr):
            blocks[block.ident] = block
        self.blocks = blocks

        # Late part of initialization, which requires all blocks to be already present
        for block in self.blocks.values():
            block.initWithRSRCLate()

        # Now when everything is ready, parse the blocks data
        for block in self.blocks.values():
            block.parseData()

        self.rememberRSRCNamesOrder()

        # Do final integrations which establish dependencies betweebn blocks
        for block in self.blocks.values():
            block.integrateData()

        return (len(blocks) > 0)

    def readRSRC(self, fh):
        self.rsrc_fh = fh
        self.src_fname = fh.name
        self.rsrc_map = []
        self.readRSRCList(fh)
        block_headers = self.readRSRCBlockInfo(fh)
        self.readRSRCBlockData(fh, block_headers)
        self.checkSanity()
        pass

    def forceCompleteReadRSRC(self):
        """ Ensured read of all data possibly needed from input file

        This function can be called after readRSRC(). After this call,
        any further calls will not result in accessing the input RSRC
        file, as all data will be loaded to memory.
        """
        for block in self.blocks.values():
            block.readRawDataSections(section_count=0xffffffff)
        pass

    def rememberRSRCNamesOrder(self):
        """ Remembers information on section names order, if it is needed

        Check if order of section names matches order of section headers.
        If it does not, set property with the unexpected order.
        """
        ordered_blocks = self.getBlocksSaveOrder()
        # Prepare list of sections sorted by name offset
        blockNamesOrder = {}
        for block in ordered_blocks:
            for snum, section in block.enumerateRSRCSectionsWithNames():
                blockNamesOrder[section.start.name_offset] = (block.ident,snum,)
        blockNamesOrder = [itm[1] for itm in sorted(blockNamesOrder.items())]
        # Use that list to check whether names are in order
        blockNamesSorted = True
        i = 0
        for block in ordered_blocks:
            for snum, section in block.enumerateRSRCSectionsWithNames():
                if i >= len(blockNamesOrder): break
                if blockNamesOrder[i] != (block.ident,snum,):
                    blockNamesSorted = False
                    break
                i += 1
        if not blockNamesSorted:
            if (self.po.verbose > 0):
                print("{:s}: Names of sections are not ordered the same as actual sections".format(self.po.rsrc))
            self.order_names = blockNamesOrder
        else:
            self.order_names = None
        pass

    def readXMLBlockData(self):
        """ Read data sections for all Blocks from the input file.
            After this function, `self.blocks` is filled.
        """
        blocks_arr = []
        for i, block_elem in enumerate(self.xml_root):
            if block_elem.tag in ("SpecialOrder",): continue # Special tags, not treated as Blocks
            ident = block_elem.tag
            bfactory = getattr(LVblock, ident, None)
            # Block may depend on some other informational blocks (ie. version info)
            # so give each block reference to the vi object
            if isinstance(bfactory, type):
                if (self.po.verbose > 1):
                    print("{:s}: Block {:s} recognized".format(self.src_fname,ident))
                block = bfactory(self, self.po)
            else:
                block = LVblock.Block(self, self.po)
            block.initWithXMLEarly(block_elem)
            blocks_arr.append(block)
        self.blocks_arr = blocks_arr

        # Create Array of Block Data
        blocks = {}
        for i, block in enumerate(self.blocks_arr):
            blocks[block.ident] = block
        self.blocks = blocks

        # Late part of initialization, which requires all blocks to be already present
        for block in self.blocks.values():
            block.initWithXMLLate()

        # Now when everything is ready, parse the blocks data
        for block in self.blocks.values():
            block.parseData()

        # Do final integrations which establish dependencies betweebn blocks
        for block in self.blocks.values():
            block.integrateData()

        return (len(blocks) > 0)

    def readXMLOrder(self, elem):
        order_elem = elem.find("SpecialOrder")
        if order_elem is None:
            return
        blockNamesOrder = []
        names_elem = order_elem.find("Names")
        if names_elem is not None:
            for i, blkref_elem in enumerate(names_elem):
                ident = getRsrcTypeFromPrettyStr(blkref_elem.tag)
                snum = blkref_elem.get("Index")
                if snum is None:
                    snum = 0
                else:
                    snum = int(snum,0)
                blockNamesOrder.append( (ident,snum,) )
        if len(blockNamesOrder) > 0:
            self.order_names = blockNamesOrder
        else:
            self.order_names = None
        pass

    def readXML(self, xml_root, xml_fname):
        self.xml_root = xml_root
        self.src_fname = xml_fname
        if self.xml_root.tag != 'RSRC':
            raise AttributeError("Root tag of the XML is not 'RSRC'")

        fmtver_str = self.xml_root.get("FormatVersion")
        self.fmtver = int(fmtver_str, 0)
        pretty_type_str = self.xml_root.get("Type")
        if pretty_type_str is not None:
            rsrc_type_id = getRsrcTypeFromPrettyStr(pretty_type_str)
        else:
            pretty_type_str = self.xml_root.get("TypeHex")
            rsrc_type_id = bytes.fromhex(pretty_type_str)
        self.ftype = recognizeFileTypeFromRsrcType(rsrc_type_id)

        encoding_str = self.xml_root.get("Encoding")
        if encoding_str is not None:
            self.textEncoding = encoding_str

        self.rsrc_headers = []
        rsrchead = RSRCHeader(self.po, fmtver=self.fmtver)
        rsrchead.rsrc_type = (c_ubyte * sizeof(rsrchead.rsrc_type)).from_buffer_copy(rsrc_type_id)
        if self.fmtver <= 2 and self.ftype == FILE_FMT_TYPE.VI:
            rsrchead.rsrc_id4 = (c_ubyte * sizeof(rsrchead.rsrc_id4)).from_buffer_copy(b'\0\0\0\0')
        self.rsrc_headers.append(rsrchead)
        rsrchead = RSRCHeader(self.po, fmtver=self.fmtver)
        rsrchead.rsrc_type = (c_ubyte * sizeof(rsrchead.rsrc_type)).from_buffer_copy(rsrc_type_id)
        if self.fmtver <= 2 and self.ftype == FILE_FMT_TYPE.VI:
            rsrchead.rsrc_id4 = (c_ubyte * sizeof(rsrchead.rsrc_id4)).from_buffer_copy(b'\0\0\0\0')
        self.rsrc_headers.append(rsrchead)

        self.binflsthead = BlockInfoListHeader(self.po)

        dataset_int1 = self.xml_root.get("Int1")
        if dataset_int1 is not None:
            self.binflsthead.dataset_int1 = int(dataset_int1, 0)
        dataset_int2 = self.xml_root.get("Int2")
        if dataset_int2 is not None:
            self.binflsthead.dataset_int2 = int(dataset_int2, 0)

        self.readXMLBlockData()
        self.readXMLOrder(self.xml_root)
        self.checkSanity()
        pass

    def updateRSRCData(self):
        """ Updates RAW data stored in each block to changes in properties
        """
        for block in self.blocks.values():
            block.updateData()

    @staticmethod
    def blkrefCountSameIdent(blkref_list, idx):
        if idx >= len(blkref_list):
            return 0
        firstref = blkref_list[idx]
        count = 1
        for blkref in blkref_list[idx+1:]:
            if blkref[0] != firstref[0]:
                break
            count += 1
        return count

    @staticmethod
    def blkrefSortBlocks(shuffled_blocks, sorted_blkref_list):
        """ Gives list of blocks sorted to match given order of references
        """
        bridx = 0
        blocks_cache = []
        sorted_blocks = []
        for block in shuffled_blocks:
            # If we're beyond the list to sort, just add in current order
            if bridx >= len(sorted_blkref_list):
                blocks_cache.append(block)
                continue
            blkref = sorted_blkref_list[bridx]
            # If we're on a block we have in cache, add it from cache
            while True:
                cached_block = next((blk for blk in blocks_cache if blk.ident == blkref[0]), None)
                if cached_block is None:
                    break
                blocks_cache.remove(cached_block)
                sorted_blocks.append(cached_block)
                bridx += VI.blkrefCountSameIdent(sorted_blkref_list, bridx)
                if bridx >= len(sorted_blkref_list):
                    break
                blkref = sorted_blkref_list[bridx]
            if bridx >= len(sorted_blkref_list): # In case we moved beyond known ordering
                blocks_cache.append(block)
                continue
            # If we're on the block expected by sorting, add it now
            if block.ident == blkref[0]:
                sorted_blocks.append(block)
                bridx += VI.blkrefCountSameIdent(sorted_blkref_list, bridx)
                continue
            # If the current block is expected later in sorting, add it to cache
            if block.ident in [ blkref[0] for blkref in sorted_blkref_list[bridx:] ]:
                blocks_cache.append(block)
                continue
            # If we're here, the current block is not present in sorting list
            if True:
                sorted_blocks.append(block)
                bridx += VI.blkrefCountSameIdent(sorted_blkref_list, bridx)
                continue
        sorted_blocks.extend(blocks_cache)
        return sorted_blocks

    def saveRSRCData(self, fh):
        ver = self.getFileVersion()
        # Write header, though it is not completely filled yet
        rsrchead = self.rsrc_headers[0]
        fh.write((c_ubyte * sizeof(rsrchead)).from_buffer_copy(rsrchead))

        # Prepare list of blocks; this sets blocks order which we will use
        all_blocks = self.getBlocksSaveOrder()

        # Also create mutable array which will become the names block
        section_names = bytearray()

        # First, let's store names section in proper order
        if True:
            if self.order_names is None:
                all_blocks_for_names = all_blocks
                for block in all_blocks_for_names:
                    block.saveRSRCNames(section_names)
            else:
                all_blocks_for_names = self.blkrefSortBlocks(all_blocks, self.order_names)
                for block in all_blocks_for_names:
                    sections_list = [ blkref[1] for blkref in self.order_names if block.ident == blkref[0] ]
                    block.saveRSRCNames(section_names, order_list=sections_list)

        if isGreaterOrEqVersion(ver, 7,0,0):
            # The same order is used for both data and the following header blocks
            for block in all_blocks:
                if (self.po.verbose > 0):
                    print("{}: Writing RSRC block {} data".format(self.src_fname,block.ident))
                block.header.starts = block.saveRSRCData(fh)
        else:
            # Section headers are sorted normally, but section data is different - some sections are moved to end
            data_at_end_blocks = []
            for block in all_blocks:
                if block.ident in (b'LVSR',):
                    data_at_end_blocks.insert(0,block)
                    continue
                if block.ident in (b'BDPW',):
                    data_at_end_blocks.append(block)
                    continue
                if (self.po.verbose > 0):
                    print("{}: Writing RSRC block {} data".format(self.src_fname,block.ident))
                block.header.starts = block.saveRSRCData(fh)
            for block in data_at_end_blocks:
                if (self.po.verbose > 0):
                    print("{}: Writing RSRC block {} data at end".format(self.src_fname,block.ident))
                block.header.starts = block.saveRSRCData(fh)

        rsrchead.rsrc_info_offset = fh.tell()
        rsrchead.rsrc_data_size = rsrchead.rsrc_info_offset - rsrchead.rsrc_data_offset

        return all_blocks, section_names

    def saveRSRCInfo(self, fh, all_blocks, section_names):
        rsrchead = self.rsrc_headers[-1]
        fh.write((c_ubyte * sizeof(rsrchead)).from_buffer_copy(rsrchead))

        # Compute sizes and offsets within the block to be written
        start_offs = sizeof(BlockInfoHeader) + sum(sizeof(block.header) for block in all_blocks)
        for block in all_blocks:
            # the below means the same ase block_head.count = len(self.sections) - 1
            block.header.count = len(block.header.starts) - 1
            block.header.offset = start_offs
            start_offs += sum(sizeof(sect_start) for sect_start in block.header.starts)

        binflsthead = self.binflsthead
        binflsthead.blockinfo_size = binflsthead.blockinfo_offset + start_offs
        if (self.po.verbose > 2):
            print(binflsthead)
        fh.write((c_ubyte * sizeof(binflsthead)).from_buffer_copy(binflsthead))

        binfhead = BlockInfoHeader(self.po)
        binfhead.blockinfo_count = len(self.blocks) - 1
        fh.write((c_ubyte * sizeof(binfhead)).from_buffer_copy(binfhead))

        for block in all_blocks:
            if (self.po.verbose > 0):
                print("{}: Writing RSRC Info block {} header at 0x{:04X}".format(self.src_fname,bytes(block.header.ident),fh.tell()))
            if (self.po.verbose > 2):
                print(block.header)
            if not block.header.checkSanity():
                raise IOError("Block Header sanity check failed.")
            fh.write((c_ubyte * sizeof(block.header)).from_buffer_copy(block.header))

        for block in all_blocks:
            if (self.po.verbose > 0):
                print("{}: Writing RSRC Info block {} section starts at 0x{:04X}".format(self.src_fname,bytes(block.header.ident),fh.tell()))
            for s, sect_start in enumerate(block.header.starts):
                fh.write((c_ubyte * sizeof(sect_start)).from_buffer_copy(sect_start))

        # Section names as Pascal strings
        if (self.po.verbose > 0):
            print("{}: Writing RSRC Info section names at 0x{:04X}".format(self.src_fname,fh.tell()))
        fh.write(section_names)

        rsrchead.rsrc_info_offset = self.rsrc_headers[0].rsrc_info_offset
        rsrchead.rsrc_info_size = fh.tell() - rsrchead.rsrc_info_offset
        self.rsrc_headers[0].rsrc_info_size = rsrchead.rsrc_info_size
        rsrchead.rsrc_data_size = self.rsrc_headers[0].rsrc_data_size
        pass

    def resaveRSRCHeaders(self, fh):
        rsrchead = self.rsrc_headers[0]
        if (self.po.verbose > 2):
            print(rsrchead)
        fh.seek(0)
        fh.write((c_ubyte * sizeof(rsrchead)).from_buffer_copy(rsrchead))
        rsrchead = self.rsrc_headers[-1]
        if (self.po.verbose > 2):
            print(rsrchead)
        fh.seek(rsrchead.rsrc_info_offset)
        fh.write((c_ubyte * sizeof(rsrchead)).from_buffer_copy(rsrchead))
        pass

    def saveRSRC(self, fh):
        self.src_fname = fh.name
        self.updateRSRCData()
        all_blocks, section_names = self.saveRSRCData(fh)
        self.saveRSRCInfo(fh, all_blocks, section_names)
        self.resaveRSRCHeaders(fh)
        pass

    def exportXMLRoot(self):
        """ Creates root of the XML export tree
        """
        ver = self.getFileVersion()
        elem = ET.Element('RSRC')
        elem.set("FormatVersion", "{:d}".format(self.fmtver))
        rsrc_type_id = getRsrcTypeForFileType(self.ftype)
        if any((c < ord(' ') or c > ord('~')) for c in rsrc_type_id):
            elem.set("TypeHex", rsrc_type_id.hex())
        else:
            elem.set("Type", rsrc_type_id.decode('ascii'))
        elem.set("Encoding", self.textEncoding)

        if self.ftype == FILE_FMT_TYPE.LLB or isSmallerVersion(ver, 7,0,0):
            dataset_int1 = self.binflsthead.dataset_int1
        else:
            dataset_int1 = None
        if dataset_int1 is not None:
            elem.set("Int1", "0x{:08X}".format(dataset_int1))

        # The value is verified to be used in LV6.0.1, unused in LV8.6
        if self.ftype == FILE_FMT_TYPE.LLB or isSmallerVersion(ver, 7,0,0):
            dataset_int2 = self.binflsthead.dataset_int2
        else:
            dataset_int2 = None
        if dataset_int2 is not None:
            elem.set("Int2", "0x{:08X}".format(dataset_int2))

        return elem

    def exportXMLOrder(self, elem):
        if self.order_names is None:
            return
        order_elem = ET.SubElement(elem,"SpecialOrder")
        comment_elem = ET.Comment(" {:s} ".format("Provides information on how items were ordered in the RSRC file"))
        order_elem.append(comment_elem)
        if self.order_names is not None:
            subelem = ET.SubElement(order_elem,"Names")
            for blockref in self.order_names:
                pretty_ident = getPrettyStrFromRsrcType(blockref[0])
                blkref_elem = ET.Element(pretty_ident)
                blkref_elem.set("Index", str(blockref[1]))
                subelem.append(blkref_elem)
        pass

    def exportBinBlocksXMLTree(self):
        """ Export the file data into BIN files with XML glue
        """
        elem = self.exportXMLRoot()

        for ident, block in self.blocks.items():
            if (self.po.verbose > 0):
                print("{}: Writing BIN block {}".format(self.src_fname,ident))
            subelem = block.exportXMLTree(simple_bin=True)
            elem.append(subelem)

        ET.pretty_element_tree_heap(elem)
        return elem

    def exportXMLTree(self):
        """ Export the file data into XML tree
        """
        elem = self.exportXMLRoot()

        for ident, block in self.blocks.items():
            if (self.po.verbose > 0):
                print("{}: Writing block {}".format(self.src_fname,ident))
            subelem = block.exportXMLTree()
            elem.append(subelem)

        self.exportXMLOrder(elem)
        ET.pretty_element_tree_heap(elem)
        return elem

    def checkSanity(self):
        ret = True
        for ident, block in self.blocks.items():
            block.parseData()
            if not block.checkSanity():
                if (self.po.verbose > 0):
                    eprint("{:s}: Warning: Block {} sanity check failed!"\
                      .format(self.src_fname,ident))
                ret = False
        return ret

    def getBlockIdByBlockName(self, ident):
        for i in range(0, len(self.blockInfo)):
            if self.blockInfo[i]['BlockName'] == ident:
                return i
        return None

    def getPositionOfBlockInfoHeader(self):
        """ Gives file position at which BlockInfoHeader is located within the Info Resource

            The BlockInfoHeader is then followed by array of BlockHeader structs.
        """
        blkinf_rsrchead = self.rsrc_headers[-1]
        return blkinf_rsrchead.rsrc_info_offset + self.binflsthead.blockinfo_offset

    def getPositionOfBlockSectionStart(self):
        """ Gives file position at which BlockSectionStart structs are placed within the Info Resource

            Offsets to groups of BlockSectionStart elements are inside BlockHeader structs; this
            function can be used to validate them.
        """
        return self.getPositionOfBlockInfoHeader() + sizeof(BlockInfoHeader) + sizeof(LVblock.BlockHeader) * len(self.blocks)

    def getPositionOfBlockSectionNames(self):
        """ Gives file position at which Section Names are placed within the Info Resource
        """
        tot_sections_count = 0
        for block in self.blocks.values():
            tot_sections_count += len(block.sections)
        return self.getPositionOfBlockSectionStart() + sizeof(LVblock.BlockSectionStart) * tot_sections_count

    def getPositionOfBlockInfoEnd(self):
        """ Gives file position at which the Info Resource ends
        """
        blkinf_rsrchead = self.rsrc_headers[-1]
        return blkinf_rsrchead.rsrc_info_offset + blkinf_rsrchead.rsrc_info_size

    def consolidatedTDEnumerate(self, mainType=None, fullType=None):
        VCTP = self.get_or_raise('VCTP')
        typeList = VCTP.getContent()
        out_list = []
        for conn_idx, clientTD in enumerate(typeList):
            if mainType is not None and clientTD.nested.mainType() != mainType:
                continue
            if fullType is not None and clientTD.nested.fullType() != fullType:
                continue
            out_list.append( (len(out_list), conn_idx, clientTD.nested,) )
        return out_list

    def getHeapTD(self, heapTypeId):
        DTHP = self.get('DTHP')
        if DTHP is None:
            return None
        return DTHP.getHeapTD(heapTypeId)

    def setNewPassword(self, password_text=None, password_md5=None):
        """ Calculates password
        """
        BDPW = self.get_or_raise('BDPW')
        BDPW.parseData()
        BDPW.recalculateHash1(store=False) # this is needed to find salt
        if password_text == "":
            # If removing password, also remove protected flag
            LVSR = self.get('LVSR')
            if LVSR is not None:
                LVSR.parseData()
                LVSR.protected = False
                LVSR.updateSectionData()
        BDPW.setPassword(password_text=password_text, password_md5=password_md5, store=True)
        #BDPW.recalculateHash1(store=True) # called by updateSectionData()
        #BDPW.recalculateHash2(store=True) # called by updateSectionData()
        BDPW.updateSectionData()
        return BDPW

    def printRSRCMap(self):
        # BlockSectionStart elements are really independent; but let's put them into some parent
        # for clarity. After all, all versions of LV create these next to each other.
        parent_beg = 0xffffffff
        parent_end = 0x0
        for mapItem in self.rsrc_map:
            if re.match(r"BlockSectionStart\[.+\]", mapItem[2]):
                parent_beg = min(parent_beg, mapItem[0]-mapItem[1])
                parent_end = max(parent_end, mapItem[0])
        if parent_beg < parent_end:
            self.rsrc_map.append( (parent_end, parent_end-parent_beg, \
              "BlockSectionStarts",) )
        # Put section data into a parent as well
        parent_beg = 0xffffffff
        parent_end = 0x0
        for mapItem in self.rsrc_map:
            if re.match(r"BlockSectionData\[.+\]", mapItem[2]):
                parent_beg = min(parent_beg, mapItem[0]-mapItem[1])
                parent_end = max(parent_end, mapItem[0])
        if parent_beg < parent_end:
            self.rsrc_map.append( (parent_end, parent_end-parent_beg, \
              "BlockData",) )
        # Names block also should have one parent
        parent_beg = 0xffffffff
        parent_end = 0x0
        for mapItem in self.rsrc_map:
            if re.match(r"NameOf.+\[.+\]", mapItem[2]):
                parent_beg = min(parent_beg, mapItem[0]-mapItem[1])
                parent_end = max(parent_end, mapItem[0])
        if parent_beg < parent_end:
            self.rsrc_map.append( (parent_end, parent_end-parent_beg, \
              "NameStrings",) )
        parents = []
        rsrc_map_sorted = sorted(self.rsrc_map, key=lambda x: (x[0]-x[1], -x[1], len(x[2])))
        for mapItem in rsrc_map_sorted:
            while len(parents) > 0:
                parItem = parents[-1]
                if parItem[0] > mapItem[0]-mapItem[1]:
                    break
                parents.pop()
            parents.append(mapItem)
            print("{:08X}: {:>{}s}{:s} (size:{:d})".format(mapItem[0]-mapItem[1],"",2*(len(parents)-1),mapItem[2],mapItem[1]))
        pass

    def isLoaded(self):
        return (self.blocks is not None)

    def get(self, ident):
        if isinstance(ident, str):
            ident = getRsrcTypeFromPrettyStr(ident)
        if ident in self.blocks:
            return self.blocks[ident]
        return None

    def get_one_of(self, *identv):
        for ident in identv:
            if isinstance(ident, str):
                ident = getRsrcTypeFromPrettyStr(ident)
            if ident in self.blocks:
                return self.blocks[ident]
        return None

    def get_or_raise(self, ident):
        if isinstance(ident, str):
            ident = getRsrcTypeFromPrettyStr(ident)
        if ident in self.blocks:
            return self.blocks[ident]
        raise LookupError("Block {} not found in RSRC file.".format(ident))

    def get_one_of_or_raise(self, *identv):
        for ident in identv:
            if isinstance(ident, str):
                ident = getRsrcTypeFromPrettyStr(ident)
            if ident in self.blocks:
                return self.blocks[ident]
        raise LookupError("None of blocks {} found in RSRC file.".format(",".join(identv)))

    def getBlocksSaveOrder(self):
        """ Returns list of blocks in the order they should be saved
        """
        return self.blocks.values()

    def getFileVersion(self):
        """ Gets file version array from any existing version block
        """
        vers = self.get_one_of('LVSR', 'vers') # TODO add LVIN when its supported
        if vers is not None:
            ver = vers.getVersion()
        else:
            # No version found - return all fields zeroed out
            ver = decodeVersion(0x0)
        return ver


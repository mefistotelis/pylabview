#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" LabView RSRC files reader.

Experimental tool.
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

__version__ = "0.0.2"
__author__ = "Jessica Creighton, Mefistotelis"
__license__ = "GPL"

import sys
import re
import os
import enum
import argparse
import binascii
import configparser
import xml.etree.ElementTree as ET
from ctypes import *
from hashlib import md5

import LVblock
import LVconnector
from LVmisc import eprint
from LVmisc import RSRCStructure

class FILE_FMT_TYPE(enum.Enum):
    NONE = 0
    Control = 1
    DLog = 2
    ClassLib = 3
    Project = 4
    Library = 5
    LLB = 6
    MenuPalette = 7
    TemplateControl = 8
    TemplateVI = 9
    Xcontrol = 10
    VI = 11


class RSRCHeader(RSRCStructure):
    _fields_ = [('id1', c_ubyte * 6),		#0
                ('id2', c_ushort),			#6
                ('file_type', c_ubyte * 4),	#8
                ('id4', c_ubyte * 4),		#12
                ('rsrc_offset', c_uint32),	#16
                ('rsrc_size', c_uint32),	#20
                ('dataset_offset', c_uint32),#24
                ('dataset_size', c_uint32),	#28, sizeof is 32
    ]

    def __init__(self, po):
        self.po = po
        self.id1 = (c_ubyte * sizeof(self.id1)).from_buffer_copy(b'RSRC\r\n')
        self.id2 = 3
        self.file_type = (c_ubyte * sizeof(self.file_type)).from_buffer_copy(b'LVIN')
        self.id4 = (c_ubyte * sizeof(self.id4)).from_buffer_copy(b'LBVW')
        self.ftype = FILE_FMT_TYPE.NONE
        self.dataset_offset = sizeof(self)
        self.starts = []

    def check_sanity(self):
        ret = True
        if bytes(self.id1) != b'RSRC\r\n':
            if (self.po.verbose > 0):
                eprint("{:s}: RSRC Header field '{:s}' has unexpected value: {}".format(self.po.rsrc,'id1',bytes(self.id1)))
            ret = False
        self.ftype = recognizeFileType(self.file_type)
        if self.ftype == FILE_FMT_TYPE.NONE:
            if (self.po.verbose > 0):
                eprint("{:s}: RSRC Header field '{:s}' has unexpected value: {}".format(self.po.rsrc,'file_type',bytes(self.file_type)))
            ret = False
        if bytes(self.id4) != b'LBVW':
            if (self.po.verbose > 0):
                eprint("{:s}: RSRC Header field '{:s}' has unexpected value: {}".format(self.po.rsrc,'id4',bytes(self.id4)))
            ret = False
        if self.dataset_offset < sizeof(self):
            if (self.po.verbose > 0):
                eprint("{:s}: RSRC Header field '{:s}' has unexpected value: {}".format(self.po.rsrc,'dataset_offset',dataset_offset))
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

    def check_sanity(self):
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

    def check_sanity(self):
        ret = True
        if self.blockinfo_count > 4096: # Arbitrary limit - hard to tell whether it makes sense
            if (self.po.verbose > 0):
                eprint("{:s}: BlockInfo Header field '{:s}' has outranged value: {:d}".format(self.po.rsrc,'blockinfo_count',self.blockinfo_count))
            ret = False
        return ret


def getIdForFileType(ftype):
    """ Gives 4-byte file identifier from FILE_FMT_TYPE member
    """
    file_type = {
        FILE_FMT_TYPE.Control: b'LVCC',
        FILE_FMT_TYPE.DLog: b'LVDL',
        FILE_FMT_TYPE.ClassLib: b'CLIB',
        FILE_FMT_TYPE.Project: b'LVPJ',
        FILE_FMT_TYPE.Library: b'LIBR',
        FILE_FMT_TYPE.LLB: b'LVAR',
        FILE_FMT_TYPE.MenuPalette: b'LMNU',
        FILE_FMT_TYPE.TemplateControl: b'sVCC',
        FILE_FMT_TYPE.TemplateVI: b'sVIN',
        FILE_FMT_TYPE.Xcontrol: b'LVXC',
        FILE_FMT_TYPE.VI: b'LVIN',
    }.get(ftype, b'')
    return file_type


def recognizeFileType(file_type):
    """ Gives FILE_FMT_TYPE member from given 4-byte file identifier
    """
    file_type_id = bytes(file_type)
    for ftype in FILE_FMT_TYPE:
        curr_file_type_id = getIdForFileType(ftype)
        if len(curr_file_type_id) > 0 and (curr_file_type_id == file_type_id):
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
        FILE_FMT_TYPE.Library: 'lvlib',
        FILE_FMT_TYPE.LLB: 'llb',
        FILE_FMT_TYPE.MenuPalette: 'mnu',
        FILE_FMT_TYPE.TemplateControl: 'ctt',
        FILE_FMT_TYPE.TemplateVI: 'vit',
        FILE_FMT_TYPE.Xcontrol: 'xctl',
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
    def __init__(self, po, rsrc_fh=None, xml_root=None):
        self.rsrc_fh = None
        self.src_fname = ""
        self.xml_root = None
        self.po = po
        self.rsrc_headers = []
        self.ftype = FILE_FMT_TYPE.NONE

        if rsrc_fh is not None:
            self.readRSRC(rsrc_fh)
        elif xml_root is not None:
            self.readXML(xml_root, po.xml)

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
            if (self.po.verbose > 2):
                print(rsrchead)
            if not rsrchead.check_sanity():
                raise IOError("RSRC {:d} Header sanity check failed.",format(len(rsrc_headers)))
            # The last header has offset equal to its start
            if rsrchead.rsrc_offset >= curr_rsrc_pos:
                next_rsrc_pos = rsrchead.rsrc_offset
            else:
                raise IOError("Invalid position of next item after parsing RSRC {:d} Header: {:d}".format(len(rsrc_headers),rsrchead.rsrc_offset))
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
        # File type should be identical in both headers
        self.ftype = blkinf_rsrchead.ftype

        # Set file position just after Block-Infos RSRC header
        fh.seek(blkinf_rsrchead.rsrc_offset + sizeof(blkinf_rsrchead))

        # Read Block-Infos List Header located after last RSRC header
        binflsthead = BlockInfoListHeader(self.po)
        if fh.readinto(binflsthead) != sizeof(binflsthead):
            raise EOFError("Could not read BlockInfoList header.")
        if (self.po.verbose > 2):
            print(binflsthead)
        if not binflsthead.check_sanity():
            raise IOError("BlockInfoList Header sanity check failed.")
        self.binflsthead = binflsthead

        fh.seek(blkinf_rsrchead.rsrc_offset + binflsthead.blockinfo_offset)

        binfhead = BlockInfoHeader(self.po)
        if fh.readinto(binfhead) != sizeof(binfhead):
            raise EOFError("Could not read BlockInfo header.")
        if not binfhead.check_sanity():
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
            if (self.po.verbose > 2):
                print(block_head)
            if not block_head.check_sanity():
                raise IOError("Block Header sanity check failed.")
            #t['Count'] = reader.readUInt32() + 1
            #t['Offset'] = blkinf_rsrchead.rsrc_offset + binflsthead.blockinfo_offset + reader.readUInt32()
            block_headers.append(block_head)
        return block_headers

    def readRSRCBlockData(self, fh, block_headers):
        """ Read data sections for all Blocks from the input file.
            This function requires `block_headers` to be passed.
            After this function, `self.blocks` is filled.
        """
        # Create Array of Block; use classes defined within LVblock namespace to read data
        # specific to given block type; when block name is unrecognized, create generic block
        blocks_arr = []
        for i, block_head in enumerate(block_headers):
            name = bytes(block_head.name).decode("utf-8")
            bfactory = getattr(LVblock, name, None)
            # Block may depend on some other informational blocks (ie. version info)
            # so give each block reference to the vi object
            if isinstance(bfactory, type):
                if (self.po.verbose > 1):
                    print("{:s}: Block '{:s}' index {:d} recognized".format(self.src_fname,name,i))
                block = bfactory(self, self.po)
            else:
                block = LVblock.Block(self, self.po)
            block.initWithRSRC(block_head)
            blocks_arr.append(block)
        self.blocks_arr = blocks_arr

        # Create Array of Block Data
        blocks = {}
        for i, block in enumerate(self.blocks_arr):
            block.parseData()
            blocks[block.name] = block
        self.blocks = blocks
        return (len(blocks) > 0)

    def readRSRC(self, fh):
        self.rsrc_fh = fh
        self.src_fname = fh.name
        self.readRSRCList(fh)
        block_headers = self.readRSRCBlockInfo(fh)
        self.readRSRCBlockData(fh, block_headers)

        self.icon = self.blocks['icl8'].loadIcon() if 'icl8' in self.blocks else None

    def readXMLBlockData(self):
        """ Read data sections for all Blocks from the input file.
            After this function, `self.blocks` is filled.
        """
        blocks_arr = []
        for i, block_elem in enumerate(self.xml_root):
            name = block_elem.tag
            bfactory = getattr(LVblock, name, None)
            # Block may depend on some other informational blocks (ie. version info)
            # so give each block reference to the vi object
            if isinstance(bfactory, type):
                if (self.po.verbose > 1):
                    print("{:s}: Block {:s} recognized".format(self.src_fname,name))
                block = bfactory(self, self.po)
            else:
                block = LVblock.Block(self, self.po)
            block.initWithXML(block_elem)
            blocks_arr.append(block)
        self.blocks_arr = blocks_arr

        self.binflsthead = BlockInfoListHeader(self.po)

        # Create Array of Block Data
        blocks = {}
        for i, block in enumerate(self.blocks_arr):
            block.parseData() #TODO make this support XML
            blocks[block.name] = block
        self.blocks = blocks
        return (len(blocks) > 0)

    def readXML(self, xml_root, xml_fname):
        self.xml_root = xml_root
        self.src_fname = xml_fname
        if self.xml_root.tag != 'RSRC':
            raise AttributeError("Root tag of the XML is not 'RSRC'")

        file_type_str = self.xml_root.get("Type")
        # TODO we will need better string-to-bytes ID conversion at some point
        # (when we have implementation of a block with space or other non-alphanum chars)
        file_type_id = file_type_str.encode("utf-8")
        self.ftype = recognizeFileType(file_type_id)

        self.rsrc_headers = []
        rsrchead = RSRCHeader(self.po)
        rsrchead.file_type = (c_ubyte * sizeof(rsrchead.file_type)).from_buffer_copy(file_type_id)
        self.rsrc_headers.append(rsrchead)
        rsrchead = RSRCHeader(self.po)
        rsrchead.file_type = (c_ubyte * sizeof(rsrchead.file_type)).from_buffer_copy(file_type_id)
        self.rsrc_headers.append(rsrchead)

        self.readXMLBlockData()

        pass

    def saveRSRCData(self, fh):
        # Write header, though it is not completely filled yet
        rsrchead = self.rsrc_headers[0]
        fh.write((c_ubyte * sizeof(rsrchead)).from_buffer_copy(rsrchead))

        for name, block in self.blocks.items():
            if (self.po.verbose > 0):
                print("{}: Writing RSRC block {} data".format(self.src_fname,name))
            block.header.starts = block.saveRSRCData(fh)

        rsrchead.rsrc_offset = fh.tell()
        rsrchead.dataset_size = rsrchead.rsrc_offset - rsrchead.dataset_offset

    def saveRSRCInfo(self, fh):
        rsrchead = self.rsrc_headers[-1]
        fh.write((c_ubyte * sizeof(rsrchead)).from_buffer_copy(rsrchead))

        binflsthead = self.binflsthead
        binflsthead.blockinfo_size = sum(sizeof(block.header) for name, block in self.blocks.items())#TODO FIX
        if (self.po.verbose > 2):
            print(binflsthead)
        fh.write((c_ubyte * sizeof(binflsthead)).from_buffer_copy(binflsthead))

        binfhead = BlockInfoHeader(self.po)
        binfhead.blockinfo_count = len(self.blocks) - 1
        fh.write((c_ubyte * sizeof(binfhead)).from_buffer_copy(binfhead))

        block_headers = []
        for name, block in self.blocks.items():
            block_head = block.header
            fh.write((c_ubyte * sizeof(block_head)).from_buffer_copy(block_head))
            block_headers.append(block_head)

        for i, block_head in enumerate(block_headers):
            if (self.po.verbose > 0):
                print("{}: Writing RSRC block {} starts".format(self.src_fname,bytes(block_head.name)))
            for s, sect_start in enumerate(block_head.starts):
                fh.write((c_ubyte * sizeof(sect_start)).from_buffer_copy(sect_start))

        #for i, block_head in enumerate(block_headers):
        #    if (self.po.verbose > 0):
        #        print("{}: Writing RSRC block {} info".format(self.src_fname,bytes(block_head.name)))
        #    if (self.po.verbose > 2):
        #        print(block.header)
        #    if not block.header.check_sanity():
        #        raise IOError("Block Header sanity check failed.")
        #    fh.write((c_ubyte * sizeof(block_head)).from_buffer_copy(block_head))

        # Footer - len and filename
        if (self.po.verbose > 0):
            print("{}: Writing RSRC footer".format(self.src_fname))
        fname = os.path.basename(self.src_fname)
        footer = int(len(fname)).to_bytes(1, byteorder='big')
        footer += fname.encode("utf-8")
        fh.write(footer)

        rsrchead.rsrc_offset = self.rsrc_headers[0].rsrc_offset
        rsrchead.rsrc_size = fh.tell() - rsrchead.rsrc_offset
        self.rsrc_headers[0].rsrc_size = rsrchead.rsrc_size
        rsrchead.dataset_size = self.rsrc_headers[0].dataset_size
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
        fh.seek(rsrchead.rsrc_offset)
        fh.write((c_ubyte * sizeof(rsrchead)).from_buffer_copy(rsrchead))
        pass

    def saveRSRC(self, fh):
        self.src_fname = fh.name
        self.saveRSRCData(fh)
        self.saveRSRCInfo(fh)
        self.resaveRSRCHeaders(fh)
        pass

    def exportBinBlocksXMLTree(self):
        """ Export the file data into BIN files with XML glue
        """
        elem = ET.Element('RSRC')
        elem.text = "\n"

        for name, block in self.blocks.items():
            if (self.po.verbose > 0):
                print("{}: Writing BIN block {}".format(self.src_fname,name))
            # Call base function, not the overloaded version for specific block
            subelem = LVblock.Block.exportXMLTree(block)
            elem.append(subelem)

        return elem

    def exportXMLTree(self):
        """ Export the file data into XML tree
        """
        elem = ET.Element('RSRC')
        elem.text = "\n"
        elem.tail = "\n"
        file_type_id = getIdForFileType(self.ftype)
        elem.set("Type", file_type_id.decode("utf-8"))

        for name, block in self.blocks.items():
            if (self.po.verbose > 0):
                print("{}: Writing block {}".format(self.src_fname,name))
            subelem = block.exportXMLTree()
            elem.append(subelem)

        return elem

    def getBlockIdByBlockName(self, name):
        for i in range(0, len(self.blockInfo)):
            if self.blockInfo[i]['BlockName'] == name:
                return i
        return None

    def connectorEnumerate(self, mainType=None, fullType=None):
        VCTP = self.get_or_raise('VCTP')
        VCTP.parseData() # Make sure the block is parsed
        out_list = []
        for conn_idx, conn_obj in enumerate(VCTP.content):
            if mainType is not None and conn_obj.mainType() != mainType:
                continue
            if fullType is not None and conn_obj.fullType() != fullType:
                continue
            out_list.append( (len(out_list), conn_idx, conn_obj,) )
        return out_list

    def setNewPassword(self, password_text=None, password_md5=None):
        """ Calculates password
        """
        BDPW = self.get_or_raise('BDPW')
        BDPW.setPassword(password_text=password_text, password_md5=password_md5, store=True)
        BDPW.recalculateHash1(store=True)
        BDPW.recalculateHash2(store=True)
        return BDPW

    def get(self, name):
        if isinstance(name, str):
            name = name.encode('utf-8')
        if name in self.blocks:
            return self.blocks[name]
        return None

    def get_one_of(self, *namev):
        for name in namev:
            if isinstance(name, str):
                name = name.encode('utf-8')
            if name in self.blocks:
                return self.blocks[name]
        return None

    def get_or_raise(self, name):
        if isinstance(name, str):
            name = name.encode('utf-8')
        if name in self.blocks:
            return self.blocks[name]
        raise LookupError("Block {} not found in RSRC file.".format(name))

    def get_one_of_or_raise(self, *namev):
        for name in namev:
            if isinstance(name, str):
                name = name.encode('utf-8')
            if name in self.blocks:
                return self.blocks[name]
        raise LookupError("None of blocks {} found in RSRC file.".format(",".join(namev)))


def main():
    """ Main executable function.

    Its task is to parse command line options and call a function which performs requested command.
    """
    # Parse command line options

    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('-i', '--rsrc', '--vi', default="", type=str,
            help="name of the LabView RSRC file, VI or other")

    parser.add_argument('-m', '--xml', default="", type=str,
            help="name of the main XML file of extracted VI dataset;" \
            "default is RSRC file name with extension changed to xml")

    parser.add_argument('-v', '--verbose', action='count', default=0,
            help="increases verbosity level; max level is set by -vvv")

    subparser = parser.add_mutually_exclusive_group(required=True)

    subparser.add_argument('-l', '--list', action='store_true',
            help="list content of RSRC file")

    subparser.add_argument('-d', '--dump', action='store_true',
            help="dump items from RSRC file into XML and BINs, with minimal" \
            " parsing of the data inside")

    subparser.add_argument('-x', '--extract', action='store_true',
            help="extract content of RSRC file into XMLs, parsing all blocks" \
            " which structure is known")

    subparser.add_argument('-c', '--create', action='store_true',
            help="create RSRC file using information from XMLs")

    subparser.add_argument('-n', '--info', action='store_true',
            help="print general information about RSRC file")

    subparser.add_argument('-p', '--password', default=None, type=str,
            help="change password and re-compute checksums within RSRC file;" \
            " save changes in-place, to the RSRC file")

    subparser.add_argument('--version', action='version', version="%(prog)s {version} by {author}"
              .format(version=__version__,author=__author__),
            help="display version information and exit")

    po = parser.parse_args()

    if len(po.xml) > 0:
        po.filebase = os.path.splitext(os.path.basename(po.xml))[0]
    elif len(po.rsrc) > 0:
        po.filebase = os.path.splitext(os.path.basename(po.rsrc))[0]
    else:
        raise FileNotFoundError("Input file was not provided neither as RSRC or XML.")

    if po.list:

        if len(po.rsrc) == 0:
            raise FileNotFoundError("Only RSRC file listing is currently supported.")

        if (po.verbose > 0):
            print("{}: Starting file parse for RSRC listing".format(po.rsrc))
        with open(po.rsrc, "rb") as rsrc_fh:
            vi = VI(po, rsrc_fh=rsrc_fh)

        print("{}\t{}".format("name","content"))
        for name, block in vi.blocks.items():
            pretty_name = block.name.decode(encoding='UTF-8')
            print("{}\t{}".format(pretty_name,str(block)))

    elif po.dump:

        if len(po.xml) == 0:
            po.xml = po.filebase + ".xml"
        if len(po.rsrc) == 0:
            po.rsrc = getExistingRSRCFileWithBase(po.filebase)
        if len(po.rsrc) == 0:
            raise FileNotFoundError("No supported RSRC file was found despite checking all extensions.")

        if (po.verbose > 0):
            print("{}: Starting file parse for RSRC dumping".format(po.rsrc))
        with open(po.rsrc, "rb") as rsrc_fh:
            vi = VI(po, rsrc_fh=rsrc_fh)

            root = vi.exportBinBlocksXMLTree()

        if (po.verbose > 0):
            print("{}: Writing binding XML".format(po.xml))
        tree = ET.ElementTree(root)
        with open(po.xml, "wb") as xml_fh:
            tree.write(xml_fh, encoding='utf-8', xml_declaration=True)

    elif po.extract:

        if len(po.xml) == 0:
            po.xml = po.filebase + ".xml"
        if len(po.rsrc) == 0:
            po.rsrc = getExistingRSRCFileWithBase(po.filebase)
        if len(po.rsrc) == 0:
            raise FileNotFoundError("No supported RSRC file was found despite checking all extensions.")

        if (po.verbose > 0):
            print("{}: Starting file parse for RSRC extraction".format(po.rsrc))
        with open(po.rsrc, "rb") as rsrc_fh:
            vi = VI(po, rsrc_fh=rsrc_fh)

            root = vi.exportXMLTree()

        if (po.verbose > 0):
            print("{}: Writing binding XML".format(po.xml))
        tree = ET.ElementTree(root)
        with open(po.xml, "wb") as xml_fh:
            tree.write(xml_fh, encoding='utf-8', xml_declaration=True)

    elif po.create:

        if len(po.xml) == 0:
            po.xml = po.filebase + ".xml"

        if (po.verbose > 0):
            print("{}: Starting file parse for RSRC creation".format(po.rsrc))
        tree = ET.parse(po.xml)
        vi = VI(po, xml_root=tree.getroot())

        if len(po.rsrc) == 0:
            po.rsrc = po.filebase + "." + getFileExtByType(vi.ftype)

        with open(po.rsrc, "wb") as rsrc_fh:
            vi.saveRSRC(rsrc_fh)

    elif po.password is not None:

        if len(po.rsrc) == 0:
            raise FileNotFoundError("Only RSRC file listing is currently supported.")

        if (po.verbose > 0):
            print("{}: Starting file parse for password print".format(po.rsrc))
        with open(po.rsrc, "rb") as rsrc_fh:
            vi = VI(po, rsrc_fh=rsrc_fh)

        BDPW = vi.get('BDPW')
        if BDPW is not None:
            print("{:s}: Stored password data".format(po.rsrc))
            print("  password md5: {:s}".format(BDPW.password_md5.hex()))
            print("  hash_1      : {:s}".format(BDPW.hash_1.hex()))
            print("  hash_2      : {:s}".format(BDPW.hash_2.hex()))
            password_md5 = BDPW.password_md5
        else:
            print("{:s}: password block '{:s}' not found".format(po.rsrc,'BDPW'))
            password_md5 = None

        if password_md5 is not None:
            BDPW = vi.setNewPassword(password_md5=password_md5)
            print("{:s}: How re-computed hashes look like".format(po.rsrc))
            print("  password md5: {:s}".format(BDPW.password_md5.hex()))
            print("  hash_1      : {:s}".format(BDPW.hash_1.hex()))
            print("  hash_2      : {:s}".format(BDPW.hash_2.hex()))

        BDPW = vi.setNewPassword(password_text=po.password)
        if BDPW is not None:
            print("{:s}: How given password would look like".format(po.rsrc))
            print("  password md5: {:s}".format(BDPW.password_md5.hex()))
            print("  hash_1      : {:s}".format(BDPW.hash_1.hex()))
            print("  hash_2      : {:s}".format(BDPW.hash_2.hex()))

    else:

        raise NotImplementedError('Unsupported command.')

if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        eprint("Error: "+str(ex))
        raise
        sys.exit(10)

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

__version__ = "0.0.1"
__author__ = "Jessica Creighton, Mefistotelis"
__license__ = "GPL"

import sys
import re
import os
import enum
import argparse
import binascii
import configparser
from ctypes import *
from hashlib import md5

import LVblock
#from Block import *
from LVmisc import eprint
from LVmisc import RSRCStructure
from LVmisc import StrToHex

class FILE_FMT_TYPE(enum.Enum):
    NONE = 0
    VI = 1
    LLB = 2

class RSRCHeader(RSRCStructure):
    _fields_ = [('id1', c_ubyte * 6),		#0
                ('id2', c_ushort),			#6
                ('file_type', c_ubyte * 4),	#8
                ('id4', c_ubyte * 4),		#12
                ('rsrc_offset', c_uint32),	#16
                ('rsrc_size', c_uint32),	#20
    ]

    def __init__(self, po):
        self.po = po
        self.id1 = (c_ubyte * sizeof(self.id1)).from_buffer_copy(b'RSRC\r\n')
        self.id2 = 3
        self.file_type = (c_ubyte * sizeof(self.file_type)).from_buffer_copy(b'LVIN')
        self.id4 = (c_ubyte * sizeof(self.id4)).from_buffer_copy(b'LBVW')
        self.ftype = FILE_FMT_TYPE.NONE

    def check_sanity(self):
        ret = True
        if bytes(self.id1) != b'RSRC\r\n':
            if (po.verbose > 0):
                eprint("{:s}: RSRC Header field '{:s}' has unexpected value: {}".format(po.input.name,'id1',bytes(self.id1)))
            ret = False
        if bytes(self.file_type) == b'LVIN':
            self.ftype = FILE_FMT_TYPE.VI
        elif bytes(self.file_type) == b'LVAR':
            self.ftype = FILE_FMT_TYPE.LLB
        else:
            if (po.verbose > 0):
                eprint("{:s}: RSRC Header field '{:s}' has unexpected value: {}".format(po.input.name,'file_type',bytes(self.file_type)))
            ret = False
        if bytes(self.id4) != b'LBVW':
            if (po.verbose > 0):
                eprint("{:s}: RSRC Header field '{:s}' has unexpected value: {}".format(po.input.name,'id4',bytes(self.id4)))
            ret = False
        return ret


class BlockInfoListHeader(RSRCStructure):
    _fields_ = [('dataset_offset', c_uint32),	#0
                ('dataset_size', c_uint32),		#4
                ('dataset_int1', c_uint32),		#8
                ('dataset_int2', c_uint32),		#12
                ('dataset_int3', c_uint32),		#16
                ('blockinfo_offset', c_uint32),	#20
                ('blockinfo_size', c_uint32),	#24
    ]

    def __init__(self, po):
        self.po = po
        pass

    def check_sanity(self):
        ret = True
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
            if (po.verbose > 0):
                eprint("{:s}: BlockInfo Header field '{:s}' has outranged value: {:d}".format(po.input.name,'blockinfo_count',blockinfo_count))
            ret = False
        return ret


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


class VI():
    def __init__(self, fh, po):
        self.fh = fh
        self.po = po
        self.rsrc_headers = []
        self.block_headers = []

        self.readVI()

    def readRSRCList(self):
        """ Read all RSRC headers from input file and check their sanity.
            After this function, `self.rsrc_headers` is filled with a list of RSRC Headers.
        """
        fh = self.fh
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

    def readBlockInfos(self):
        """ Read all Block-Infos from the input file.
            The Block-Infos are within last RSRC inside the file.
            This function requires `self.rsrc_headers` to be filled.
            After this function, `self.block_headers` is filled with a list of Block Headers.
        """
        fh = self.fh
        blkinf_rsrchead = self.rsrc_headers[-1]

        # Set file position just after Block-Infos RSRC header
        fh.seek(blkinf_rsrchead.rsrc_offset + sizeof(blkinf_rsrchead))

        # Read Block-Infos List Header located after last RSRC header
        binflsthead = BlockInfoListHeader(self.po)
        if fh.readinto(binflsthead) != sizeof(binflsthead):
            raise EOFError("Could not read BlockInfoList header.")
        if not binflsthead.check_sanity():
            raise IOError("BlockInfoList Header sanity check failed.")
        if (self.po.verbose > 2):
            print(binflsthead)
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
            block_head = BlockHeader(self.po)
            if fh.readinto(block_head) != sizeof(block_head):
                raise EOFError("Could not read BlockInfo header.")
            if (self.po.verbose > 2):
                print(block_head)
            if not block_head.check_sanity():
                raise IOError("Block Header sanity check failed.")
            #t['Count'] = reader.readUInt32() + 1
            #t['Offset'] = blkinf_rsrchead.rsrc_offset + binflsthead.blockinfo_offset + reader.readUInt32()
            block_headers.append(block_head)
        self.block_headers = block_headers
        return (len(block_headers) > 0)

    def readBlockData(self):
        """ Read data sections for all Blocks from the input file.
            This function requires `self.block_headers` to be filled.
        """
        fh = self.fh
        # Create Array of Block Factories, either generic or able to read data specific to given block type
        blocks_arr = []
        for i, block_head in enumerate(self.block_headers):
            name = bytes(block_head.name).decode("utf-8")
            bfactory = getattr(LVblock, name, None)
            if isinstance(bfactory, type):
                if (self.po.verbose > 1):
                    print("{:s}: Block {:s} recognized".format(self.po.input.name,name))
                block = bfactory(self, block_head, self.po)
            else:
                block = LVblock.Block(self, block_head, self.po)
            blocks_arr.append(block)
        self.blocks_arr = blocks_arr

        # Create Array of Block Data
        blocks = {}
        for i, block in enumerate(self.blocks_arr):
            block.getData()
            blocks[block.name] = block
        self.blocks = blocks
        return (len(blocks) > 0)

    def readVI(self):
        self.readRSRCList()
        self.readBlockInfos()
        self.readBlockData()

        self.icon = self.blocks['icl8'].loadIcon() if 'icl8' in self.blocks else None

    def getBlockIdByBlockName(self, name):
        for i in range(0, len(self.blockInfo)):
            if self.blockInfo[i]['BlockName'] == name:
                return i
        return None

    def calcPassword(self, newPassword="", write=False):
        if 'LVSR' in self.blocks:
            LVSR = self.blocks['LVSR']
        else:
            LVSR = None

        if 'BDHc' in self.blocks:
            BDH = self.blocks['BDHc']
        if 'BDHb' in self.blocks:
            BDH = self.blocks['BDHb']
        else:
            BDH = None

        if 'LIBN' in self.blocks:
            LIBN_content = self.blocks['LIBN'].content
        else:
            LIBN_content = ""

        if LVSR is None:
            if (self.po.verbose > 0):
                eprint("{:s}: Block {:s} not found in parsed data".format(self.po.input.name,'LVSR'))
            return False

        if BDH is None:
            if (self.po.verbose > 0):
                eprint("{:s}: Block {:s} not found in parsed data".format(self.po.input.name,'BDHb/c'))
            return False

        md5Password = md5(newPassword).digest()
        md5Hash1 = md5(md5Password + LIBN_content + LVSR.raw_data[0]).digest()
        md5Hash2 = md5(md5Hash1 + BDH.hash).digest()

        out = {}
        out['password'] = newPassword
        out['password_md5'] = md5Password
        out['hash_1'] = md5Hash1
        out['hash_2'] = md5Hash2
        self.m_password_set = out
        return True

    def get(self, name):
        if name in self.blocks:
            return self.blocks[name]
        return None

def main():
    """ Main executable function.

    Its task is to parse command line options and call a function which performs requested command.
    """
    # Parse command line options

    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('-i', '--input', required=True, type=argparse.FileType('rb'),
            help='name of the input LabView RSRC file')

    parser.add_argument("-v", "--verbose", action="count", default=0,
            help="Increases verbosity level; max level is set by -vvv")

    subparser = parser.add_mutually_exclusive_group()

    subparser.add_argument("-l", "--list", action="store_true",
            help="list content of RSRC file")

    subparser.add_argument("-x", "--extract", action="store_true",
            help="extract items within RSRC file")

    subparser.add_argument("--version", action='version', version="%(prog)s {version} by {author}"
              .format(version=__version__,author=__author__),
            help="Display version information and exit")

    po = parser.parse_args()

    #TODO react to command
    vi = VI(po.input, po)

    #t = vi.getBlockContentById(vi.getBlockIdByBlockName("BDPW"))
    #open("dumps/" + n + ".dmp", "w").write(t.base_stream.read())
    #vi.getIcon().save('tmp.png')
    BDPW = vi.get('BDPW')
    if BDPW is not None:
        print("password md5: " + StrToHex(BDPW.password_md5))
        print("hash_1      : " + StrToHex(BDPW.hash_1))
        print("hash_2      : " + StrToHex(BDPW.hash_2))
    else:
        print("{:s}: password block '{:s}' not found".format(po.input.name,'BDPW'))
    if vi.calcPassword(""):
        print("password md5: " + StrToHex(vi.m_password_set['password_md5']))
        print("hash_1      : " + StrToHex(vi.m_password_set['hash_1']))
        print("hash_2      : " + StrToHex(vi.m_password_set['hash_2']))
    #print(vi.get("vers").version)
    #print(vi.get("LVSR").version)
    #vi.icon.save("out.png")

if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        eprint("Error: "+str(ex))
        raise
        sys.exit(10)

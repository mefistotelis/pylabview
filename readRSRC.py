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

__version__ = "0.0.3"
__author__ = "Jessica Creighton, Mefistotelis"
__license__ = "GPL"

import sys
import re
import os
import argparse
import xml.etree.ElementTree as ET

import LVblock
import LVconnector
from LVresource import *
from LVmisc import eprint


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

    # Store base name - without path and extension
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

        print("{}\t{}".format("ident","content"))
        for ident, block in vi.blocks.items():
            pretty_ident = block.ident.decode(encoding='UTF-8')
            print("{}\t{}".format(pretty_ident,str(block)))

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

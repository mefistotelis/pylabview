# -*- coding: utf-8 -*-

""" LabView RSRC file format ref connectors.

    Virtual Connectors and Terminal Points are stored inside VCTP block.
"""

# Copyright (C) 2013 Jessica Creighton <jcreigh@femtobit.org>
# Copyright (C) 2019 Mefistotelis <mefistotelis@gmail.com>
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.


import enum

from hashlib import md5
from io import BytesIO
from types import SimpleNamespace
from ctypes import *

from LVmisc import *
from LVblock import *
import LVclasses
import LVheap
import LVdatatype



class LinkObjBase:
    """ Generic base for LinkObject Identities.

    Provides methods to be overriden in inheriting classes.
    """
    def __init__(self, vi, ident, po):
        """ Creates new link object.
        """
        self.vi = vi
        self.po = po
        self.ident = ident

    def parseRSRCData(self, bldata):
        """ Parses binary data chunk from RSRC file.

        Receives file-like block data handle positioned at ident.
        The handle gives access to binary data which is associated with the link object.
        Parses the binary data, filling properties.
        """
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        """ Fills binary data chunk for RSRC file which is associated with the link object.

        Creates bytes with binary data, starting with ident.
        """
        data_buf = b''
        return data_buf

    def expectedRSRCSize(self):
        """ Returns data size expected to be returned by prepareRSRCData().
        """
        exp_whole_len = 4
        return exp_whole_len

    def initWithXML(self, conn_elem):
        """ Parses XML branch to fill properties of the link object.

        Receives ElementTree branch starting at tag associated with the link object.
        Parses the XML attributes, filling properties.
        """
        pass

    def exportXML(self, conn_elem, fname_base):
        """ Fills XML branch with properties of the link object.

        Receives ElementTree branch starting at tag associated with the link object.
        Sets the XML attributes, using properties from self.
        """
        pass

    def checkSanity(self):
        ret = True
        return ret


class OldImplementationForRework:
    def parseRSRCLORefFPP(self, section_num, client, bldata):
        client.ident = bldata.read(4)
        count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        for i in range(count):
            # TODO this needs figuring out
            unkval1 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            unkval2 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            objstart = bldata.tell()
            objident = bldata.read(4)
            bldata.seek(objstart)
            if objident == b'PTH0':
                obj = LVclasses.LVPath0(self.vi, self.po)
                obj.parseRSRCData(bldata)
                client.content.append(obj)
            else:
                eprint("{:s}: Warning: Block {} section {} container {} references unrecognized class {}."\
                  .format(self.vi.src_fname,self.ident,section_num,client.ident,objident))
            unkval3 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            unkval4 = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            unkval5 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            unkval6 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            unkval7 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            unkval11 = bldata.read(24)
        pass

    def parseRSRCLORefDDP(self, section_num, client, bldata):
        client.ident = bldata.read(4)
        unkbase1 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

        names = []
        for i in range(count):
            strlen = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            namestr = bldata.read(strlen)
            names.append(namestr)
        if (bldata.tell() % 2) > 0:
            bldata.read(1) # Padding byte

        for i in range(count):
            # TODO this needs figuring out
            objstart = bldata.tell()
            objident = bldata.read(4)
            bldata.seek(objstart)
            if objident == b'PTH0':
                obj = LVclasses.LVPath0(self.vi, self.po)
                obj.parseRSRCData(bldata)
                client.content.append(obj)
            else:
                eprint("{:s}: Warning: Block {} section {} container {} references unrecognized class {}."\
                  .format(self.vi.src_fname,self.ident,section_num,client.ident,objident))
            unkval3 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            unkval4 = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            unkval5 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            unkval6 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            unkval7 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            unkval11 = bldata.read(24)
        pass

    def parseRSRCLORefIUV(self, section_num, client, bldata):
        client.ident = bldata.read(4)
        if (bldata.tell() % 4) > 0:
            bldata.read(4 - (bldata.tell() % 4)) # Padding bytes
        count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

        names = []
        for i in range(count):
            strlen = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            namestr = bldata.read(strlen)
            names.append(namestr)
        if (bldata.tell() % 2) > 0:
            bldata.read(1) # Padding byte

        for i in range(count):
            # TODO this needs figuring out
            objstart = bldata.tell()
            objident = bldata.read(4)
            bldata.seek(objstart)
            if objident == b'PTH0':
                obj = LVclasses.LVPath0(self.vi, self.po)
                obj.parseRSRCData(bldata)
                client.content.append(obj)
            else:
                eprint("{:s}: Warning: Block {} section {} container {} references unrecognized class {}."\
                  .format(self.vi.src_fname,self.ident,section_num,client.ident,objident))
            if i == 0:
                unkval3 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                unkval4 = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
                unkval5 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
                unkval6 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                unkval7 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
                unkval11 = bldata.read(30)
            else:
                unkval3 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        pass

    def initWithXMLLORef(self, client, section_elem):
        client.ident = getRsrcTypeFromPrettyStr(section_elem.tag)
        for subelem in section_elem:
            subclient = SimpleNamespace()
            self.initNewClient(subclient)
            client.content.append(subclient)
            self.initWithXMLLORef(client, subelem)
        pass

    def exportXMLLORef(self, section_elem, client, fname_base):
        pretty_ident = getPrettyStrFromRsrcType(client.ident)
        subelem = ET.SubElement(section_elem, pretty_ident)
        for subclient in client.content:
            if isinstance(subclient, LVclasses.LVObject):
                subelem = ET.SubElement(section_elem,"RefObject")
                subclient.exportXML(subelem, fname_base)
            else:
                self.exportXMLLORef(subelem, subclient, fname_base)
        pass


def newLinkObject(vi, list_ident, ident, po):
    """ Calls proper constructor to create link object.
    """
    if   ident in (b'DSDS',) or list_ident in (b'VIDS',) and ident in (b'VIDS',):
        ctor = None
    elif ident in (b'DSEF',) or list_ident in (b'VIDS',) and ident in (b'XFun',):
        ctor = None
    elif ident in (b'DSCN',) or list_ident in (b'VIDS',) and ident in (b'LVSB',):
        ctor = None
    elif ident in (b'DSSC',) or list_ident in (b'VIDS',) and ident in (b'SFTB',):
        ctor = None
    elif ident in (b'DSCB',):
        ctor = None
    elif ident in (b'DSSV',):
        ctor = None
    elif ident in (b'VIVI',) or list_ident in (b'LVIN',) and ident in (b'LVIN',):
        ctor = None
    elif ident in (b'VIPR',) or list_ident in (b'LVIN',) and ident in (b'LVPR',):
        ctor = None
    elif ident in (b'VIPV',) or list_ident in (b'LVIN',) and ident in (b'POLY',):
        ctor = None
    elif ident in (b'VICC',) or list_ident in (b'LVCC',) and ident in (b'LVCC',b'CCCC',):
        ctor = None
    elif ident in (b'BSVR',):
        ctor = None
    elif ident in (b'VIAV',):
        ctor = None
    elif ident in (b'TDCC',) or list_ident in (b'FPHP',) and ident in (b'LVCC',):
        ctor = None
    elif ident in (b'VIPV',b'POLY',):
        ctor = None
    elif ident in (b'FPPI',):
        ctor = None#self.parseRSRCLORefFPP(section_num, client, bldata)
    elif ident in (b'DDPI',):
        ctor = None#self.parseRSRCLORefDDP(section_num, client, bldata)
    elif ident in (b'VRPI',):
        ctor = None
    elif ident in (b'VIPI',):
        ctor = None
    elif ident in (b'RVPI',):
        ctor = None
    #elif ident in (b'IUVI',):
        ctor = None#self.parseRSRCLORefIUV(section_num, client, bldata)
    else:
        raise AttributeError("List {} contains unrecognized class {}".format(list_ident,ident))
    if ctor is None:
        raise NotImplementedError("List {} contains unimplemented class {}".format(list_ident,ident))
    return ctor(vi, conn_obj, reftype, po)

# -*- coding: utf-8 -*-

""" LabView RSRC file format common classes.

    Classes used in various parts of the RSRC file.
"""

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
import LVconnector

class LVObject:
    def __init__(self, vi, po):
        """ Creates new object.
        """
        self.vi = vi
        self.po = po

    def parseRSRCData(self, bldata):
        """ Parses binary data chunk from RSRC file.

        Receives file-like block data handle positioned at place to read.
        Parses the binary data, filling properties of self.
        """
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        """ Fills binary data chunk for RSRC file which is associated with the connector.

        Must create byte buffer of the whole data for this object.
        """
        data_buf = b''
        return data_buf

    def expectedRSRCSize(self):
        """ Returns data size expected to be returned by prepareRSRCData().
        """
        exp_whole_len = 0
        return exp_whole_len

    def initWithXML(self, obj_elem):
        """ Parses XML branch to fill properties of the object.

        Receives ElementTree branch starting at tag associated with the connector.
        Parses the XML attributes, filling properties of this object.
        """
        pass

    def exportXML(self, obj_elem, fname_base):
        """ Fills XML branch with properties of the object.

        Receives ElementTree branch starting at tag associated with the connector.
        Sets the XML attributes, using properties from this object.
        """
        pass


class LVPath0(LVObject):
    """ Path object, sometimes used instead of simple file name
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.content = []
        self.ident = b''

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        totlen = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.content = []
        for i in range(count):
            text_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            text_val = bldata.read(text_len)
            self.content.append(text_val)
        ctlen = 4 + sum(1+len(text_val) for text_val in self.content)
        if ctlen != totlen:
            eprint("{:s}: Warning: LVPath0 has unexpected size, {} != {}"\
              .format(self.vi.src_fname, ctlen, totlen))
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = bytes(self.ident)
        totlen = 4 + sum(1+len(text_val) for text_val in self.content)
        data_buf += int(totlen).to_bytes(4, byteorder='big')
        data_buf += len(self.content).to_bytes(4, byteorder='big')
        for text_val in self.content:
            data_buf += len(text_val).to_bytes(1, byteorder='big')
            data_buf += bytes(text_val)
        return data_buf

    def initWithXML(self, obj_elem):
        self.content = []
        self.ident = getRsrcTypeFromPrettyStr(obj_elem.get("Ident"))
        for i, subelem in enumerate(obj_elem):
            if (subelem.tag == "String"):
                if subelem.text is not None:
                    self.content.append(subelem.text.encode(self.vi.textEncoding))
                else:
                    self.content.append(b'')
            else:
                raise AttributeError("LVPath0 subtree contains unexpected tag")
        pass

    def exportXML(self, obj_elem, fname_base):
        obj_elem.set("Ident",  getPrettyStrFromRsrcType(self.ident))
        for text_val in self.content:
            subelem = ET.SubElement(obj_elem,"String")
            subelem.tail = "\n"

            pretty_string = text_val.decode(self.vi.textEncoding)
            subelem.text = pretty_string
        pass


class LVVariant(LVObject):
    """ Object with variant type data
    """
    def __init__(self, index, *args):
        super().__init__(*args)
        self.clients2 = []
        self.varver = 0x0
        self.hasvaritem2 = 0
        self.varitem2 = None
        self.index = index

    def parseRSRCTypeDef(self, bldata, pos):
        bldata.seek(pos)
        obj_type, obj_flags, obj_len = LVconnector.ConnectorObject.parseRSRCDataHeader(bldata)
        if (self.po.verbose > 2):
            print("{:s}: Object {:d} sub {:d}, at 0x{:04x}, type 0x{:02x} flags 0x{:02x} len {:d}"\
              .format(self.vi.src_fname, self.index, len(self.clients2), pos, obj_type, obj_flags, obj_len))
        if obj_len < 4:
            eprint("{:s}: Warning: Object {:d} type 0x{:02x} data size {:d} too small to be valid"\
              .format(self.vi.src_fname, len(self.clients2), obj_type, obj_len))
            obj_type = LVconnector.CONNECTOR_FULL_TYPE.Void
        obj = LVconnector.newConnectorObject(self.vi, -1, obj_flags, obj_type, self.po)
        client = SimpleNamespace()
        client.flags = 0
        client.index = -1
        client.nested = obj
        self.clients2.append(client)
        bldata.seek(pos)
        obj.initWithRSRC(bldata, obj_len)
        return obj.index, obj_len

    def parseRSRCVariant(self, bldata):
        varver = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.varver = varver
        varcount = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        if varcount > self.po.connector_list_limit:
            eprint("{:s}: Warning: LVVariant {:d} has {:d} clients; truncating"\
              .format(self.vi.src_fname, self.index, varcount))
            varcount = self.po.connector_list_limit
        pos = bldata.tell()
        for i in range(varcount):
            obj_idx, obj_len = self.parseRSRCTypeDef(bldata, pos)
            pos += obj_len
            if obj_len < 4:
                eprint("{:s}: Warning: LVVariant {:d} data size too small for all clients"\
                  .format(self.vi.src_fname, self.index))
                break
        hasvaritem2 = readVariableSizeFieldU2p2(bldata)
        self.hasvaritem2 = hasvaritem2
        self.varitem2 = b''
        if hasvaritem2 != 0:
            self.varitem2 = bldata.read(6)
        pass

    def parseRSRCData(self, bldata):
        self.clients2 = []
        self.varitem2 = None
        self.parseRSRCVariant(bldata)
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = int(self.varver).to_bytes(4, byteorder='big')
        varcount = sum(1 for client in self.clients2 if client.index == -1)
        data_buf += int(varcount).to_bytes(4, byteorder='big')
        for client in self.clients2:
            if client.index != -1:
                continue
            client.nested.updateData(avoid_recompute=avoid_recompute)
            data_buf += client.nested.raw_data
        hasvaritem2 = self.hasvaritem2
        data_buf += int(hasvaritem2).to_bytes(2, byteorder='big')
        if hasvaritem2 != 0:
            data_buf += self.varitem2
        return data_buf

    def initWithXML(self, obj_elem):
        self.varver = int(obj_elem.get("VarVer"), 0)
        self.hasvaritem2 = int(obj_elem.get("HasVarItem2"), 0)
        varitem2 = obj_elem.get("VarItem2")
        if varitem2 is not None:
            self.varitem2 = bytes.fromhex(varitem2)
        for subelem in obj_elem:
            if (subelem.tag == "DataType"):
                obj_idx = int(subelem.get("Index"), 0)
                obj_type = valFromEnumOrIntString(LVconnector.CONNECTOR_FULL_TYPE, subelem.get("Type"))
                obj_flags = importXMLBitfields(LVconnector.CONNECTOR_FLAGS, subelem)
                obj = LVconnector.newConnectorObject(self.vi, obj_idx, obj_flags, obj_type, self.po)
                # Grow the list if needed (the connectors may be in wrong order)
                client = SimpleNamespace()
                client.flags = 0
                client.index = -1
                client.nested = obj
                self.clients2.append(client)
                # Set connector data based on XML properties
                obj.initWithXML(subelem)
            else:
                raise AttributeError("LVVariant subtree contains unexpected tag")
        pass

    def exportXML(self, obj_elem, fname_base):
        obj_elem.tag = "LVVariant"
        obj_elem.set("VarVer", "0x{:08X}".format(self.varver))
        obj_elem.set("HasVarItem2", "{:d}".format(self.hasvaritem2))
        if self.hasvaritem2 != 0:
            obj_elem.set("VarItem2", "{:s}".format(self.varitem2.hex()))
        idx = -1
        for client in self.clients2:
            if client.index != -1:
                continue
            idx += 1
            fname_cli = "{:s}_{:04d}".format(fname_base, idx)
            subelem = ET.SubElement(obj_elem,"DataType")

            subelem.set("Index", str(idx))
            subelem.set("Type", stringFromValEnumOrInt(LVconnector.CONNECTOR_FULL_TYPE, client.nested.otype))

            client.nested.exportXML(subelem, fname_cli)
            client.nested.exportXMLFinish(subelem)
        pass

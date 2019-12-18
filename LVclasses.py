# -*- coding: utf-8 -*-

""" LabView RSRC file format common classes.

    Classes used in various parts of the RSRC file.
"""

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

from hashlib import md5
from io import BytesIO
from types import SimpleNamespace
from ctypes import *

from LVmisc import *
from LVblock import *
import LVconnector

def LVVariant_parseRSRCConnector(conn_obj, bldata, pos):
        bldata.seek(pos)
        obj_type, obj_flags, obj_len = LVconnector.ConnectorObject.parseRSRCDataHeader(bldata)
        if (conn_obj.po.verbose > 2):
            print("{:s}: Connector {:d} sub {:d}, at 0x{:04x}, type 0x{:02x} flags 0x{:02x} len {:d}"\
              .format(conn_obj.vi.src_fname, conn_obj.index, len(conn_obj.clients), pos, obj_type, obj_flags, obj_len))
        if obj_len < 4:
            eprint("{:s}: Warning: Connector {:d} type 0x{:02x} data size {:d} too small to be valid"\
              .format(conn_obj.vi.src_fname, len(conn_obj.clients), obj_type, obj_len))
            obj_type = LVconnector.CONNECTOR_FULL_TYPE.Void
        obj = LVconnector.newConnectorObject(conn_obj.vi, -1, obj_flags, obj_type, conn_obj.po)
        client = SimpleNamespace()
        client.flags = 0
        client.index = -1
        client.nested = obj
        conn_obj.clients.append(client)
        bldata.seek(pos)
        obj.initWithRSRC(bldata, obj_len)
        return obj.index, obj_len

def LVVariant_parseRSRCData(conn_obj, bldata):
        varver = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        conn_obj.varver = varver
        varcount = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        if varcount > conn_obj.po.connector_list_limit:
            eprint("{:s}: Warning: Connector {:d} type 0x{:02x} has {:d} clients; truncating"\
              .format(conn_obj.vi.src_fname, conn_obj.index, conn_obj.otype, varcount))
            varcount = conn_obj.po.connector_list_limit
        pos = bldata.tell()
        for i in range(varcount):
            obj_idx, obj_len = LVVariant_parseRSRCConnector(conn_obj, bldata, pos)
            pos += obj_len
            if obj_len < 4:
                eprint("{:s}: Warning: Connector {:d} type 0x{:02x} data size too small for all clients"\
                  .format(conn_obj.vi.src_fname, conn_obj.index, conn_obj.otype))
                break
        hasvaritem2 = readVariableSizeField(bldata)
        conn_obj.hasvaritem2 = hasvaritem2
        conn_obj.varitem2 = b''
        if hasvaritem2 != 0:
            conn_obj.varitem2 = bldata.read(6)
        pass

def LVVariant_prepareRSRCData(conn_obj, avoid_recompute=False):
        data_buf = int(conn_obj.varver).to_bytes(4, byteorder='big')
        varcount = sum(1 for client in conn_obj.clients if client.index == -1)
        data_buf += int(varcount).to_bytes(4, byteorder='big')
        for client in conn_obj.clients:
            if client.index != -1:
                continue
            client.nested.updateData(avoid_recompute=avoid_recompute)
            data_buf += client.nested.raw_data
        hasvaritem2 = conn_obj.hasvaritem2
        data_buf += int(hasvaritem2).to_bytes(2, byteorder='big')
        if hasvaritem2 != 0:
            data_buf += conn_obj.varitem2
        return data_buf

def LVVariant_initWithXML(conn_obj, obj_elem):
        conn_obj.varver = int(obj_elem.get("VarVer"), 0)
        conn_obj.hasvaritem2 = int(obj_elem.get("HasVarItem2"), 0)
        varitem2 = obj_elem.get("VarItem2")
        if varitem2 is not None:
            conn_obj.varitem2 = bytes.fromhex(varitem2)
        for subelem in obj_elem:
            if (subelem.tag == "DataType"):
                obj_idx = int(subelem.get("Index"), 0)
                obj_type = valFromEnumOrIntString(LVconnector.CONNECTOR_FULL_TYPE, subelem.get("Type"))
                obj_flags = importXMLBitfields(LVconnector.CONNECTOR_FLAGS, subelem)
                obj = LVconnector.newConnectorObject(conn_obj.vi, obj_idx, obj_flags, obj_type, conn_obj.po)
                # Grow the list if needed (the connectors may be in wrong order)
                client = SimpleNamespace()
                client.flags = 0
                client.index = -1
                client.nested = obj
                conn_obj.clients.append(client)
                # Set connector data based on XML properties
                obj.initWithXML(subelem)
            else:
                #raise AttributeError("LVVariant subtree contains unexpected tag")
                pass #TODO no exception until LVVariant has its own class
        pass

def LVVariant_exportXML(conn_obj, obj_elem, fname_base):
        obj_elem.set("VarVer", "0x{:08X}".format(conn_obj.varver))
        obj_elem.set("HasVarItem2", "{:d}".format(conn_obj.hasvaritem2))
        if conn_obj.hasvaritem2 != 0:
            obj_elem.set("VarItem2", "{:s}".format(conn_obj.varitem2.hex()))
        idx = -1
        for client in self.clients:
            if client.index != -1:
                continue
            idx += 1
            fname_cli = "{:s}_{:04d}".format(fname_base, idx)
            subelem = ET.SubElement(obj_elem,"DataType")

            subelem.set("Index", str(idx))
            subelem.set("Type", "{:s}".format(stringFromValEnumOrInt(LVconnector.CONNECTOR_FULL_TYPE, client.nested.otype)))

            client.nested.exportXML(subelem, fname_cli)
            client.nested.exportXMLFinish(subelem)
        pass

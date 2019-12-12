# -*- coding: utf-8 -*-

""" LabView RSRC file format ref connectors.

    Virtual Connectors and Terminal Points are stored inside VCTP block.
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

from hashlib import md5
from io import BytesIO
from types import SimpleNamespace
from ctypes import *

from LVmisc import *
from LVblock import *


class CONNECTOR_REF_TYPE(enum.IntEnum):
    DataLogFile =	0x01
    Occurrence =	0x04
    TCPConnection =	0x05
    ControlRefnum =	0x08
    DataSocket =	0x0D
    UDPConnection =	0x10
    NotifierRefnum =	0x11
    Queue =	0x12
    IrDAConnection =	0x13
    Channel =	0x14
    SharedVariable =	0x15
    EventRegistration =	0x17
    UserEvent =	0x19
    Class =	0x1E
    BluetoothConnectn =	0x1F
    DataValueRef =	0x20
    FIFORefnum =	0x21


class RefGeneric:
    """ Generic base for Connectors of type Reference.

    Provides methods to be overriden in inheriting classes.
    """
    def __init__(self, vi, conn_obj, reftype, po):
        """ Creates new Connector Reference object.
        """
        self.vi = vi
        self.po = po
        self.conn_obj = conn_obj

    def parseRSRCData(self, bldata):
        """ Parses binary data chunk from RSRC file.

        Receives file-like block data handle positioned just after RefType.
        The handle gives access to binary data which is associated with the connector.
        Parses the binary data, filling properties of self.conn_obj.
        Must parse the whole data, until the expected end (or the position where label starts).
        """
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        """ Fills binary data chunk for RSRC file which is associated with the connector.

        Receives file-like block data handle positioned just after RefType.
        Must create the whole data, until the expected end (or the position where label starts).
        """
        data_buf = b''
        return data_buf

    def expectedRSRCSize(self):
        """ Returns data size expected to be returned by prepareRSRCData().
        """
        exp_whole_len = 0
        return exp_whole_len

    def initWithXML(self, conn_elem):
        """ Parses XML branch to fill properties of the connector.

        Receives ElementTree branch starting at tag associated with the connector.
        Parses the XML attributes, filling properties of self.conn_obj.
        Should parse only attributes of the tag received, without enumerating children.
        """
        pass

    def initWithXMLClient(self, client, conn_subelem):
        """ Parses XML branch to fill properties of the connector client.

        Receives ElementTree branch starting at tag associated with the connector client.
        Also receives new client object to be filled with the new data.
        Should parse attributes of the tag received, filling properties in the client object.
        """
        pass

    def exportXML(self, conn_elem, fname_base):
        """ Fills XML branch with properties of the connector.

        Receives ElementTree branch starting at tag associated with the connector.
        Sets the XML attributes, using properties from self.conn_obj.
        Should set only attributes of the tag received, without adding clients.
        """
        pass

    def exportXMLClient(self, client, conn_subelem, fname_base):
        """ Fills XML branch to with properties of the connector client.

        Receives ElementTree branch starting at tag associated with the connector client.
        Also receives client object to be exported.
        Should set attributes of the tag received, using properties in the client object.
        """
        pass

    def checkSanity(self):
        ret = True
        return ret


class RefOccurrence(RefGeneric):
    def __init__(self, *args):
        super().__init__(*args)


class RefTCPConnection(RefGeneric):
    def __init__(self, *args):
        super().__init__(*args)


class RefControlRefnum(RefGeneric):
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        count = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        # Create _separate_ empty namespace for each connector
        clients = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            cli_idx = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            cli_flags = 0
            clients[i].index = cli_idx
            clients[i].flags = cli_flags
        self.conn_obj.ctlflags = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.conn_obj.clients = clients
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(len(self.conn_obj.clients)).to_bytes(2, byteorder='big')
        for client in self.conn_obj.clients:
            data_buf += int(client.index).to_bytes(2, byteorder='big')
        data_buf += int(self.conn_obj.ctlflags).to_bytes(4, byteorder='big')
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 2 + 2 * len(self.conn_obj.clients)
        exp_whole_len += 4
        return exp_whole_len

    def initWithXML(self, conn_elem):
        self.conn_obj.ctlflags = int(conn_elem.get("CtlFlags"), 0)
        pass

    def initWithXMLClient(self, client, conn_subelem):
        pass

    def exportXML(self, conn_elem, fname_base):
        conn_elem.set("CtlFlags", "0x{:04X}".format(self.conn_obj.ctlflags))
        pass

    def exportXMLClient(self, client, conn_subelem, fname_base):
        pass

    def checkSanity(self):
        ret = True
        if len(self.conn_obj.clients) > 1:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: Connector {:d} type 0x{:02x} reftype {:d} should not have clients, but it does"\
                  .format(self.vi.src_fname,self.conn_obj.index,self.conn_obj.otype,self.conn_obj.reftype))
            ret = False
        return ret


class RefDataSocket(RefGeneric):
    def __init__(self, *args):
        super().__init__(*args)


class RefUDPConnection(RefGeneric):
    def __init__(self, *args):
        super().__init__(*args)


class RefNotifierRefnum(RefGeneric):
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        count = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        # Create _separate_ empty namespace for each connector
        clients = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            cli_idx = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            cli_flags = 0
            clients[i].index = cli_idx
            clients[i].flags = cli_flags
        self.conn_obj.clients = clients
        pass

    def checkSanity(self):
        ret = True
        if len(self.conn_obj.clients) > 1:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: Connector {:d} type 0x{:02x} reftype {:d} should not have clients, but it does"\
                  .format(self.vi.src_fname,self.conn_obj.index,self.conn_obj.otype,self.conn_obj.reftype))
            ret = False
        return ret


class RefQueue(RefGeneric):
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        count = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        # Create _separate_ empty namespace for each connector
        clients = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            cli_idx = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            cli_flags = 0
            clients[i].index = cli_idx
            clients[i].flags = cli_flags
        self.conn_obj.clients = clients
        pass

    def checkSanity(self):
        ret = True
        if len(self.conn_obj.clients) > 1:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: Connector {:d} type 0x{:02x} reftype {:d} should not have clients, but it does"\
                  .format(self.vi.src_fname,self.conn_obj.index,self.conn_obj.otype,self.conn_obj.reftype))
            ret = False
        return ret


class RefDataLogFile(RefQueue):
    pass


class RefIrDAConnection(RefGeneric):
    def __init__(self, *args):
        super().__init__(*args)


class RefChannel(RefGeneric):
    def __init__(self, *args):
        super().__init__(*args)


class RefSharedVariable(RefGeneric):
    def __init__(self, *args):
        super().__init__(*args)


class RefEventRegistration(RefGeneric):
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        tmp1 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        count = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        # Create _separate_ empty namespace for each connector
        clients = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            # dont know this data!
            tmp3 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            tmp4 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            tmp5 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            cli_idx = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            cli_flags = 0
            clients[i].index = cli_idx
            clients[i].flags = cli_flags
            clients[i].tmp3 = tmp3
            clients[i].tmp4 = tmp4
            clients[i].tmp5 = tmp5
        self.conn_obj.tmp1 = tmp1
        self.conn_obj.clients = clients
        pass

    def checkSanity(self):
        ret = True
        if self.conn_obj.tmp1 != 0:
            ret = False
        if len(self.conn_obj.clients) < 1:
            ret = False
        return ret


class RefUserEvent(RefQueue):
    pass


class RefClass(RefGeneric):
    def __init__(self, *args):
        super().__init__(*args)


class RefBluetoothConnectn(RefGeneric):
    def __init__(self, *args):
        super().__init__(*args)


class RefDataValueRef(RefGeneric):
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        count = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        # Create _separate_ empty namespace for each connector
        clients = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            # dont know this data!
            cli_idx = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            cli_flags = 0
            clients[i].index = cli_idx
            clients[i].flags = cli_flags
        self.conn_obj.valflags = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        self.conn_obj.clients = clients
        pass

    def checkSanity(self):
        ret = True
        if len(self.conn_obj.clients) > 1:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: Connector {:d} type 0x{:02x} reftype {:d} should not have clients, but it does"\
                  .format(self.vi.src_fname,self.conn_obj.index,self.conn_obj.otype,self.conn_obj.reftype))
            ret = False
        return ret


class RefFIFORefnum(RefNotifierRefnum):
    pass


def newConnectorObjectRef(vi, conn_obj, reftype, po):
    ctor = {
        CONNECTOR_REF_TYPE.DataLogFile: RefDataLogFile,
        CONNECTOR_REF_TYPE.Occurrence: RefOccurrence,
        CONNECTOR_REF_TYPE.TCPConnection: RefTCPConnection,
        CONNECTOR_REF_TYPE.ControlRefnum: RefControlRefnum,
        CONNECTOR_REF_TYPE.DataSocket: RefDataSocket,
        CONNECTOR_REF_TYPE.UDPConnection: RefUDPConnection,
        CONNECTOR_REF_TYPE.NotifierRefnum: RefNotifierRefnum,
        CONNECTOR_REF_TYPE.Queue: RefQueue,
        CONNECTOR_REF_TYPE.IrDAConnection: RefIrDAConnection,
        CONNECTOR_REF_TYPE.Channel: RefChannel,
        CONNECTOR_REF_TYPE.SharedVariable: RefSharedVariable,
        CONNECTOR_REF_TYPE.EventRegistration: RefEventRegistration,
        CONNECTOR_REF_TYPE.UserEvent: RefUserEvent,
        CONNECTOR_REF_TYPE.Class: RefClass,
        CONNECTOR_REF_TYPE.BluetoothConnectn: RefBluetoothConnectn,
        CONNECTOR_REF_TYPE.DataValueRef: RefDataValueRef,
        CONNECTOR_REF_TYPE.FIFORefnum: RefFIFORefnum,
    }.get(reftype, None)
    if ctor is None:
        return None
    return ctor(vi, conn_obj, reftype, po)

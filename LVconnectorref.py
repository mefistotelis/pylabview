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


class REFNUM_TYPE(enum.IntEnum):
    Generic =	0
    DataLog =	1
    ByteStream =	2
    Device =	3
    Occurrence =	4
    TCPNetConn =	5 # TCP Network Connection
    Unused6 =	6
    AutoRef =	7
    LVObjCtl =	8
    Menu =	9
    Unused10 =	10
    Imaq =	11
    Unused12 =	12
    DataSocket =	13
    VisaRef =	14
    IVIRef =	15
    UDPNetConn =	16 # UDP Network Connection
    NotifierRef =	17
    Queue =	18
    IrdaNetConn =	19 # Irda Network Connnection
    UsrDefined =	20
    UsrDefndTag =	21 # User Defined Tag
    Unused22 =	22
    EventReg =	23 # Event Registration
    DotNet =	24
    UserEvent =	25
    Unused26 =	26
    Callback =	27
    Unused28 =	28
    UsrDefTagFlt =	29 # User Defined Tag Flatten
    UDClassInst =	30
    BluetoothCon =	31 # Bluetooth Connectn
    DataValueRef =	32
    FIFORef =	33
    TDMSFile =	34




class RefnumBase:
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


class RefnumOccurrence(RefnumBase):
    def __init__(self, *args):
        super().__init__(*args)


class RefnumTCPNetConn(RefnumBase):
    def __init__(self, *args):
        super().__init__(*args)


class RefnumLVObjCtl(RefnumBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.conn_obj.ctlflags = 0

    def parseRSRCData(self, bldata):
        count = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        # Create _separate_ empty namespace for each connector
        clients = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            cli_idx = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            cli_flags = 0
            clients[i].index = cli_idx
            clients[i].flags = cli_flags
        self.conn_obj.ctlflags = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        count = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        self.conn_obj.unkcount = count # TODO figure out the count and read entries after it (example file: ConfigureFXP.vi)
        self.conn_obj.clients = clients
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(len(self.conn_obj.clients)).to_bytes(2, byteorder='big')
        for client in self.conn_obj.clients:
            data_buf += int(client.index).to_bytes(2, byteorder='big')
        data_buf += int(self.conn_obj.ctlflags).to_bytes(2, byteorder='big')
        data_buf += int(self.conn_obj.unkcount).to_bytes(2, byteorder='big')
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 2 + 2 * len(self.conn_obj.clients)
        exp_whole_len += 2 + 2
        return exp_whole_len

    def initWithXML(self, conn_elem):
        self.conn_obj.ctlflags = int(conn_elem.get("CtlFlags"), 0)
        pass

    def exportXML(self, conn_elem, fname_base):
        conn_elem.set("CtlFlags", "0x{:04X}".format(self.conn_obj.ctlflags))
        pass

    def checkSanity(self):
        ret = True
        if len(self.conn_obj.clients) > 1:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: Connector {:d} type 0x{:02x} reftype {:d} should not have clients, but it does"\
                  .format(self.vi.src_fname,self.conn_obj.index,self.conn_obj.otype,self.conn_obj.reftype))
            ret = False
        return ret


class RefnumDataSocket(RefnumBase):
    def __init__(self, *args):
        super().__init__(*args)


class RefnumUDPNetConn(RefnumBase):
    def __init__(self, *args):
        super().__init__(*args)


class RefnumNotifierRef(RefnumBase):
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

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(len(self.conn_obj.clients)).to_bytes(2, byteorder='big')
        for client in self.conn_obj.clients:
            data_buf += int(client.index).to_bytes(2, byteorder='big')
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 2 + 2 * len(self.conn_obj.clients)
        return exp_whole_len

    def checkSanity(self):
        ret = True
        if len(self.conn_obj.clients) > 1:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: Connector {:d} type 0x{:02x} reftype {:d} should not have clients, but it does"\
                  .format(self.vi.src_fname,self.conn_obj.index,self.conn_obj.otype,self.conn_obj.reftype))
            ret = False
        return ret


class RefnumQueue(RefnumBase):
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        count = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        # Create _separate_ empty namespace for each connector
        clients = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            cli_idx = readVariableSizeField(bldata)
            cli_flags = 0
            clients[i].index = cli_idx
            clients[i].flags = cli_flags
        self.conn_obj.clients = clients
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(len(self.conn_obj.clients)).to_bytes(2, byteorder='big')
        for client in self.conn_obj.clients:
            data_buf += int(client.index).to_bytes(2, byteorder='big')
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 2 + 2 * len(self.conn_obj.clients)
        return exp_whole_len

    def checkSanity(self):
        ret = True
        if len(self.conn_obj.clients) > 1:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: Connector {:d} type 0x{:02x} reftype {:d} should not have clients, but it does"\
                  .format(self.vi.src_fname,self.conn_obj.index,self.conn_obj.otype,self.conn_obj.reftype))
            ret = False
        return ret


class RefnumDataLog(RefnumQueue):
    pass


class RefnumIrdaNetConn(RefnumBase):
    def __init__(self, *args):
        super().__init__(*args)


class RefnumUsrDefined(RefnumBase):
    def __init__(self, *args):
        super().__init__(*args)


class RefnumUsrDefndTag(RefnumBase):
    def __init__(self, *args):
        super().__init__(*args)


class RefnumEventReg(RefnumBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.conn_obj.field0 = 0

    def parseRSRCData(self, bldata):
        field0 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        count = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        # Create _separate_ empty namespace for each connector
        clients = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            # dont know this data!
            cfield0 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            cfield2 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            cfield4 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            cli_idx = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            cli_flags = 0
            clients[i].index = cli_idx
            clients[i].flags = cli_flags
            clients[i].cfield0 = cfield0
            clients[i].cfield2 = cfield2
            clients[i].cfield4 = cfield4
        self.conn_obj.field0 = field0
        self.conn_obj.clients = clients
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(self.conn_obj.field0).to_bytes(2, byteorder='big')
        data_buf += int(len(self.conn_obj.clients)).to_bytes(2, byteorder='big')
        for client in self.conn_obj.clients:
            data_buf += int(client.cfield0).to_bytes(2, byteorder='big')
            data_buf += int(client.cfield2).to_bytes(2, byteorder='big')
            data_buf += int(client.cfield4).to_bytes(2, byteorder='big')
            data_buf += int(client.index).to_bytes(2, byteorder='big')
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 2 + 2 + 8 * len(self.conn_obj.clients)
        return exp_whole_len

    def initWithXML(self, conn_elem):
        self.conn_obj.field0 = int(conn_elem.get("Field0"), 0)
        pass

    def initWithXMLClient(self, client, conn_subelem):
        client.cfield0 = int(conn_subelem.get("CField0"), 0)
        client.cfield2 = int(conn_subelem.get("CField2"), 0)
        client.cfield4 = int(conn_subelem.get("CField4"), 0)
        pass

    def exportXML(self, conn_elem, fname_base):
        conn_elem.set("Field0", "0x{:04X}".format(self.conn_obj.field0))
        pass

    def exportXMLClient(self, client, conn_subelem, fname_base):
        conn_elem.set("CField0", "0x{:04X}".format(client.cfield0))
        conn_elem.set("CField2", "0x{:04X}".format(client.cfield2))
        conn_elem.set("CField4", "0x{:04X}".format(client.cfield4))
        pass

    def checkSanity(self):
        ret = True
        if self.conn_obj.field0 != 0:
            ret = False
        if len(self.conn_obj.clients) < 1:
            ret = False
        return ret


class RefnumUserEvent(RefnumQueue):
    pass


class RefnumUDClassInst(RefnumBase):
    def __init__(self, *args):
        super().__init__(*args)


class RefnumBluetoothCon(RefnumBase):
    def __init__(self, *args):
        super().__init__(*args)


class RefnumDataValueRef(RefnumBase):
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


class RefnumFIFORef(RefnumNotifierRef):
    pass


def newConnectorObjectRef(vi, conn_obj, reftype, po):
    ctor = {
        REFNUM_TYPE.DataLog: RefnumDataLog,
        REFNUM_TYPE.Occurrence: RefnumOccurrence,
        REFNUM_TYPE.TCPNetConn: RefnumTCPNetConn,
        REFNUM_TYPE.LVObjCtl: RefnumLVObjCtl,
        REFNUM_TYPE.DataSocket: RefnumDataSocket,
        REFNUM_TYPE.UDPNetConn: RefnumUDPNetConn,
        REFNUM_TYPE.NotifierRef: RefnumNotifierRef,
        REFNUM_TYPE.Queue: RefnumQueue,
        REFNUM_TYPE.IrdaNetConn: RefnumIrdaNetConn,
        REFNUM_TYPE.UsrDefined: RefnumUsrDefined,
        REFNUM_TYPE.UsrDefndTag: RefnumUsrDefndTag,
        REFNUM_TYPE.EventReg: RefnumEventReg,
        REFNUM_TYPE.UserEvent: RefnumUserEvent,
        REFNUM_TYPE.UDClassInst: RefnumUDClassInst,
        REFNUM_TYPE.BluetoothCon: RefnumBluetoothCon,
        REFNUM_TYPE.DataValueRef: RefnumDataValueRef,
        REFNUM_TYPE.FIFORef: RefnumFIFORef,
    }.get(reftype, None)
    if ctor is None:
        return None
    return ctor(vi, conn_obj, reftype, po)

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
    """ Generic base for Connectors of type Refnum.

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


class RefnumBase_SimpleCliList(RefnumBase):
    """ Base class for Refnum Connectors storing simple list of Client Index values

    Used with the Queue Operations functions to store data in a queue.
    Some of related controls: "Dequeue Element", "Enqueue Element", "Flush Queue", "Obtain Queue".
    """
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


class RefnumDataLog(RefnumBase_SimpleCliList):
    """ Data Log File Refnum Connector

    Connector of "Data Log File Refnum" Front Panel control.
    Can store only one client.
    """
    def __init__(self, *args):
        super().__init__(*args)

    def checkSanity(self):
        ret = True
        if len(self.conn_obj.clients) > 1:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: Connector {:d} type 0x{:02x} reftype {:d} should not have more than one client, has {}"\
                  .format(self.vi.src_fname,self.conn_obj.index,self.conn_obj.otype,self.conn_obj.reftype,len(self.conn_obj.clients)))
            ret = False
        return ret


class RefnumByteStream(RefnumBase):
    """ Byte Stream File Refnum Connector

    Connector of "Byte Stream File Refnum" Front Panel control.
    Used to open or create a file in one VI and perform I/O operations in another VI.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumDevice(RefnumBase):
    """ Device Refnum Connector

    Usage unknown.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumOccurrence(RefnumBase):
    """ Occurrence Refnum Connector

    Connector of "Occurrence Refnum" Front Panel control.
    Used to set or wait for the occurrence function in another VI.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumTCPNetConn(RefnumBase):
    """ TCP Network Connection Refnum Connector

    Connector of "TCP Network Connection Refnum" Front Panel control.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumAutoRef(RefnumBase):
    """ Automation Refnum Connector

    Connector of "Automation Refnum Refnum" Front Panel control.
    Used to open a reference to an ActiveX Server Object and pass it as a parameter to another VI.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumLVObjCtl(RefnumBase):
    """ LVObject/Control Refnum Connector

    Connector of "Control Refnum" Front Panel control.
    Used to open a reference to a front panel control/indicator and pass the reference to another VI.
    """
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


class RefnumMenu(RefnumBase):
    """ Menu Refnum Connector

    Connector of "Menu Refnum" Front Panel control.
    Used to pass a VI menu reference to a subVI.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumImaq(RefnumBase):
    """ IMAQ Session Refnum Connector

    Used with the Image Acquisition VIs.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumDataSocket(RefnumBase):
    """ DataSocket Refnum Connector

    Connector of "DataSocket Refnum" Front Panel control.
    Used to open a reference to a data connection.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumVisaRef(RefnumBase):
    """ Visa Refnum Connector

    Usage unknown.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumIVIRef(RefnumBase):
    """ VI Refnum Connector

    Connector of "VI Refnum" Front Panel control.
    Used to open a reference to a VI and pass it as a parameter to another VI.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumUDPNetConn(RefnumBase):
    """ UDP Network Connection Refnum Connector

    Connector of "UDP Network Connection Refnum" Front Panel control.
    Used to uniquely identify a UDP socket.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumNotifierRef(RefnumBase):
    """ Notifier Refnum Connector

    Used with the Notifier Operations functions to suspend the execution
    until receive data from another section or another VI.
    Some of related controls: "Cancel Notification", "Get Notifier Status", "Obtain Notifier", "Send Notification".
    """
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
    """ Queue Refnum Connector

    Used with the Queue Operations functions to store data in a queue.
    Some of related controls: "Dequeue Element", "Enqueue Element", "Flush Queue", "Obtain Queue".
    """
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


class RefnumIrdaNetConn(RefnumBase):
    """ IrDA Network Connection Refnum Connector

    Connector of "IrDA Network Connection Refnum" Front Panel control.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumUsrDefined(RefnumBase):
    """ User Defined Refnum Connector

    Usage unknown.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumUsrDefndTag(RefnumBase):
    """ User Defined Tag Refnum Connector

    Usage unknown.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumEventReg(RefnumBase):
    """ Event Callback Refnum Connector

    Connector of "Event Callback Refnum" Front Panel control.
    Used to unregister or re-register the event callback.
    """
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


class RefnumDotNet(RefnumBase):
    """ .NET Refnum Connector

    Connector of ".NET Refnum" Front Panel control.
    Used to launch Select .NET Constructor dialog box and select an assembly.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumUserEvent(RefnumBase_SimpleCliList):
    """ User Event Callback Refnum Connector

    Usage unknown.
    """
    pass


class RefnumCallback(RefnumBase):
    """ Callback Refnum Connector

    Usage unknown.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumUsrDefTagFlt(RefnumBase):
    """ User Defined Tag Flatten Refnum Connector

    Usage unknown.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumUDClassInst(RefnumBase):
    """ User Defined Class Inst Refnum Connector

    Usage unknown.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumBluetoothCon(RefnumBase):
    """ Bluetooth Network Connection Refnum Connector

    Connector of "Bluetooth Network Connection Refnum" Front Panel control.
    Used with the Bluetooth VIs and functions, to open connection.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumDataValueRef(RefnumBase):
    """ Data Value Refnum Connector

    Connector created as output of "Data Value Reference" Front Panel control.
    Used with the In Place Element structure when you want to operate on a data value without
    requiring the LabVIEW compiler to copy the data values and maintain those values in memory.
    """
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
    """ FIFO Refnum Connector

    Usage unknown.
    """
    pass


class RefnumTDMSFile(RefnumBase):
    """ TDMS File Refnum Connector

    Used with TDMS Streaming VIs and functions to read and write waveforms to binary measurement files (.tdms).
    """
    def __init__(self, *args):
        super().__init__(*args)


def newConnectorObjectRef(vi, conn_obj, reftype, po):
    ctor = {
        REFNUM_TYPE.DataLog: RefnumDataLog,
        REFNUM_TYPE.ByteStream: RefnumByteStream,
        REFNUM_TYPE.Device: RefnumDevice,
        REFNUM_TYPE.Occurrence: RefnumOccurrence,
        REFNUM_TYPE.TCPNetConn: RefnumTCPNetConn,
        REFNUM_TYPE.AutoRef: RefnumAutoRef,
        REFNUM_TYPE.LVObjCtl: RefnumLVObjCtl,
        REFNUM_TYPE.Menu: RefnumMenu,
        REFNUM_TYPE.Imaq: RefnumImaq,
        REFNUM_TYPE.DataSocket: RefnumDataSocket,
        REFNUM_TYPE.VisaRef: RefnumVisaRef,
        REFNUM_TYPE.IVIRef: RefnumIVIRef,
        REFNUM_TYPE.UDPNetConn: RefnumUDPNetConn,
        REFNUM_TYPE.NotifierRef: RefnumNotifierRef,
        REFNUM_TYPE.Queue: RefnumQueue,
        REFNUM_TYPE.IrdaNetConn: RefnumIrdaNetConn,
        REFNUM_TYPE.UsrDefined: RefnumUsrDefined,
        REFNUM_TYPE.UsrDefndTag: RefnumUsrDefndTag,
        REFNUM_TYPE.EventReg: RefnumEventReg,
        REFNUM_TYPE.DotNet: RefnumDotNet,
        REFNUM_TYPE.UserEvent: RefnumUserEvent,
        REFNUM_TYPE.Callback: RefnumCallback,
        REFNUM_TYPE.UsrDefTagFlt: RefnumUsrDefTagFlt,
        REFNUM_TYPE.UDClassInst: RefnumUDClassInst,
        REFNUM_TYPE.BluetoothCon: RefnumBluetoothCon,
        REFNUM_TYPE.DataValueRef: RefnumDataValueRef,
        REFNUM_TYPE.FIFORef: RefnumFIFORef,
        REFNUM_TYPE.TDMSFile: RefnumTDMSFile,
    }.get(reftype, None)
    if ctor is None:
        return None
    return ctor(vi, conn_obj, reftype, po)

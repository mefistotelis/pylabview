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
import LVclasses
import LVheap
import LVdatatype

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
    UsrDefndTag =	21 # User Defined Tag; also includes DAQmx type
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


class LV_INTERNAL_REFNUM_TYPE_NAMES(LVheap.ENUM_TAGS):
    """ Names of Refnum types from LV

    This maps the names of Refnum types this tool uses to names LV uses
    internally. All values from REFNUM_TYPE should be mapped here.
    """
    Generic =	REFNUM_TYPE.Generic
    DataLog =	REFNUM_TYPE.DataLog
    ByteStream =	REFNUM_TYPE.ByteStream
    Device =	REFNUM_TYPE.Device
    Occurrence =	REFNUM_TYPE.Occurrence
    TCPNetConn =	REFNUM_TYPE.TCPNetConn
    Unused6 =	REFNUM_TYPE.Unused6
    AutoRef =	REFNUM_TYPE.AutoRef
    LVObjCtl =	REFNUM_TYPE.LVObjCtl
    Menu =		REFNUM_TYPE.Menu
    Unused10 =	REFNUM_TYPE.Unused10
    Imaq =		REFNUM_TYPE.Imaq
    Unused12 =	REFNUM_TYPE.Unused12
    DataSocket =	REFNUM_TYPE.DataSocket
    VisaRef =	REFNUM_TYPE.VisaRef
    IVIRef =	REFNUM_TYPE.IVIRef
    UDPNetConn =	REFNUM_TYPE.UDPNetConn
    NotifierRef =	REFNUM_TYPE.NotifierRef
    Queue =		REFNUM_TYPE.Queue
    IrdaNetConn =	REFNUM_TYPE.IrdaNetConn
    UsrDefined =	REFNUM_TYPE.UsrDefined
    UsrDefndTag =	REFNUM_TYPE.UsrDefndTag
    Unused22 =	REFNUM_TYPE.Unused22
    EventReg =	REFNUM_TYPE.EventReg
    DotNet =	REFNUM_TYPE.DotNet
    UserEvent =	REFNUM_TYPE.UserEvent
    Unused26 =	REFNUM_TYPE.Unused26
    Callback =	REFNUM_TYPE.Callback
    Unused28 =	REFNUM_TYPE.Unused28
    UsrDefTagFlt =	REFNUM_TYPE.UsrDefTagFlt
    UDClassInst =	REFNUM_TYPE.UDClassInst
    BluetoothCon =	REFNUM_TYPE.BluetoothCon
    DataValueRef =	REFNUM_TYPE.DataValueRef
    FIFORef =	REFNUM_TYPE.FIFORef
    TDMSFile =	REFNUM_TYPE.TDMSFile


class RefnumBase:
    """ Generic base for Connectors of type Refnum.

    Provides methods to be overriden in inheriting classes.
    """
    def __init__(self, vi, blockref, td_obj, reftype, po):
        """ Creates new Connector Reference object.
        """
        self.vi = vi
        self.blockref = blockref
        self.po = po
        self.td_obj = td_obj

    def __repr__(self):
        d = self.__dict__.copy()
        del d['vi']
        del d['po']
        del d['td_obj']
        from pprint import pformat
        return type(self).__name__ + pformat(d, indent=0, compact=True, width=512)

    def parseRSRCData(self, bldata):
        """ Parses binary data chunk from RSRC file.

        Receives file-like block data handle positioned just after RefType.
        The handle gives access to binary data which is associated with the connector.
        Parses the binary data, filling properties of self.td_obj.
        Must parse the whole data, until the expected end (or the position where label starts).
        """
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        """ Fills binary data chunk for RSRC file which is associated with the connector.

        Creates bytes with binary data to be positioned just after RefType.
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
        Parses the XML attributes, filling properties of self.td_obj.
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

    def initWithXMLItem(self, item, conn_subelem):
        """ Parses XML branch to fill properties of the items associated to connector.

        Should parse attributes of the tag received, filling properties in the item object.
        """
        raise AttributeError("Connector of this refcount type does not support item tag")

    def exportXML(self, conn_elem, fname_base):
        """ Fills XML branch with properties of the connector.

        Receives ElementTree branch starting at tag associated with the connector.
        Sets the XML attributes, using properties from self.td_obj.
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

    def exportXMLItem(self, item, conn_subelem, fname_base):
        """ Fills XML branch to with properties of the connector item.

        Should set attributes of the tag received, using properties in the item object.
        """
        raise AttributeError("Connector of this refcount type does not support item tag")

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
            cli_idx = readVariableSizeFieldU2p2(bldata)
            cli_flags = 0
            clients[i].index = cli_idx
            clients[i].flags = cli_flags
        self.td_obj.clients = clients
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(len(self.td_obj.clients)).to_bytes(2, byteorder='big')
        for client in self.td_obj.clients:
            data_buf += int(client.index).to_bytes(2, byteorder='big')
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 2 + 2 * len(self.td_obj.clients)
        return exp_whole_len


class RefnumBase_SimpleCliSingle(RefnumBase_SimpleCliList):
    def __init__(self, *args):
        super().__init__(*args)

    def checkSanity(self):
        ret = True
        if len(self.td_obj.clients) > 1:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} reftype {:d} should not have more than one client, has {}"\
                  .format(self.vi.src_fname,self.td_obj.index,self.td_obj.otype,self.td_obj.reftype,len(self.td_obj.clients)))
            ret = False
        return ret


class RefnumBase_RC(RefnumBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.td_obj.ident = b'UNKN'
        self.td_obj.firstclient = 0

    def parseRSRCTypeOMId(self, bldata):
        pass

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        self.parseRSRCTypeOMId(bldata)
        # The next thing to read here is LVVariant
        if isGreaterOrEqVersion(ver, 8,5,0,4) and \
          (isSmallerVersion(ver, 8,5,1,1) or isGreaterOrEqVersion(ver, 8,6,0,1)):
            obj = LVclasses.LVVariant(len(self.td_obj.objects), self.vi, self.blockref, self.po)
            self.td_obj.objects.append(obj)
            obj.parseRSRCData(bldata)
        pass

    def prepareRSRCTypeOMId(self, avoid_recompute=False):
        data_buf = b''
        return data_buf

    def prepareRSRCData(self, avoid_recompute=False):
        if not avoid_recompute:
            ver = self.vi.getFileVersion()
        else:
            ver = decodeVersion(0x09000000)
        data_buf = self.prepareRSRCTypeOMId(avoid_recompute=avoid_recompute)
        # Now LVVariant
        if isGreaterOrEqVersion(ver, 8,5,0,4) and \
          (isSmallerVersion(ver, 8,5,1,1) or isGreaterOrEqVersion(ver, 8,6,0,1)):
            for obj in self.td_obj.objects:
                if not isinstance(obj, LVclasses.LVVariant):
                    continue
                data_buf += obj.prepareRSRCData(avoid_recompute=avoid_recompute)
                break
        return data_buf

    def expectedRSRCTypeOMIdSize(self):
        exp_whole_len = 0
        return exp_whole_len

    def expectedRSRCSize(self):
        ver = self.vi.getFileVersion()

        exp_whole_len = self.expectedRSRCTypeOMIdSize()

        if isGreaterOrEqVersion(ver, 8,5,0,4) and \
          (isSmallerVersion(ver, 8,5,1,1) or isGreaterOrEqVersion(ver, 8,6,0,1)):
            for obj in self.td_obj.objects:
                if not isinstance(obj, LVclasses.LVVariant):
                    continue
                exp_whole_len += obj.expectedRSRCSize()
                break
        return exp_whole_len

    def initWithXML(self, conn_elem):
        self.td_obj.ident = conn_elem.get("Ident").encode(encoding='ascii')
        self.td_obj.firstclient = int(conn_elem.get("FirstClient"), 0)
        pass

    def exportXML(self, conn_elem, fname_base):
        conn_elem.set("Ident", "{:s}".format(self.td_obj.ident.decode(encoding='ascii')))
        conn_elem.set("FirstClient", "{:d}".format(self.td_obj.firstclient))
        pass


class RefnumBase_RCIOOMId(RefnumBase_RC):
    """ Base class for RCIOOMId types

    This class and descendants do not need to re-define methods prepared in base class.
    It should be enough to overload *TypeOMId*() methods.
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCTypeOMIdStart(self, bldata):
        ver = self.vi.getFileVersion()
        # The data start with a string, 1-byte length, padded to mul of 2
        strlen = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        self.td_obj.ident = bldata.read(strlen)
        if ((strlen+1) % 2) > 0:
            bldata.read(1) # Padding byte
        # This value should be either 0 or 1
        if isGreaterOrEqVersion(ver, 8,2,0,4) and \
          (isSmallerVersion(ver, 8,2,1,1) or isGreaterOrEqVersion(ver, 8,5,0,1)):
            firstclient = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        else:
            firstclient = 0
        self.td_obj.firstclient = firstclient
        self.td_obj.clients = []
        if firstclient != 0:
            client = SimpleNamespace()
            client.index = readVariableSizeFieldU2p2(bldata)
            client.flags = 0
            self.td_obj.clients.append(client)
        pass

    def parseRSRCTypeOMId(self, bldata):
        self.parseRSRCTypeOMIdStart(bldata)

    def prepareRSRCTypeOMIdStart(self, avoid_recompute=False):
        if not avoid_recompute:
            ver = self.vi.getFileVersion()
        else:
            ver = decodeVersion(0x09000000)
        data_buf = b''
        strlen = len(self.td_obj.ident)
        data_buf += int(strlen).to_bytes(1, byteorder='big')
        data_buf += self.td_obj.ident
        if ((strlen+1) % 2) > 0:
            data_buf += b'\0' # padding
        if isGreaterOrEqVersion(ver, 8,2,0,4) and \
          (isSmallerVersion(ver, 8,2,1,1) or isGreaterOrEqVersion(ver, 8,5,0,1)):
            firstclient = self.td_obj.firstclient
            data_buf += int(firstclient).to_bytes(2, byteorder='big')
        else:
            firstclient = 0
        # Make list of clients which reference other connectors
        ref_clients = []
        for client in self.td_obj.clients:
            if client.index >= 0:
                ref_clients.append(client.index)
        if firstclient != 0 and len(ref_clients) == 0:
            eprint("{:s}: Warning: TD {:d} type 0x{:02x} marked as firstclient but no clients"\
              .format(self.vi.src_fname, self.td_obj.index, self.td_obj.otype))
            ref_clients.append(0)
        if firstclient != 0:
            data_buf += int(ref_clients[0]).to_bytes(2, byteorder='big')
            ref_clients = ref_clients[1:]
        return data_buf, ref_clients, firstclient

    def prepareRSRCTypeOMId(self, avoid_recompute=False):
        data_buf, ref_clients, firstclient = self.prepareRSRCTypeOMIdStart(avoid_recompute=avoid_recompute)
        if len(ref_clients) > 0:
            eprint("{:s}: Warning: TD {:d} type 0x{:02x} has more clients than supported"\
              .format(self.vi.src_fname, self.td_obj.index, self.td_obj.otype))
        return data_buf

    def expectedRSRCTypeOMIdStartSize(self):
        ver = self.vi.getFileVersion()
        exp_whole_len = 0
        strlen = len(self.td_obj.ident)
        exp_whole_len += 1 + strlen
        if ((strlen+1) % 2) > 0:
            exp_whole_len += 1
        if isGreaterOrEqVersion(ver, 8,2,0,4) and \
          (isSmallerVersion(ver, 8,2,1,1) or isGreaterOrEqVersion(ver, 8,5,0,1)):
            firstclient = self.td_obj.firstclient
            exp_whole_len += 2
        else:
            firstclient = 0
        # Make list of clients which reference other connectors
        ref_clients = []
        for client in self.td_obj.clients:
            if client.index >= 0:
                ref_clients.append(client.index)
        if firstclient != 0 and len(ref_clients) > 0:
            exp_whole_len += ( 2 if (ref_clients[0] <= 0x7fff) else 4 )
            ref_clients = ref_clients[1:]
        return exp_whole_len, ref_clients, firstclient

    def expectedRSRCTypeOMIdSize(self):
        exp_whole_len, ref_clients, firstclient = self.expectedRSRCTypeOMIdStartSize()
        return exp_whole_len


class RefnumDataLog(RefnumBase_SimpleCliSingle):
    """ Data Log File Refnum Connector

    Connector of "Data Log File Refnum" Front Panel control.
    Can store only one client.
    """
    pass


class RefnumGeneric(RefnumBase):
    """ Generic Refnum Connector

    Usage unknown.
    """
    # This refnum has no additional data stored
    pass


class RefnumByteStream(RefnumBase):
    """ Byte Stream File Refnum Connector

    Connector of "Byte Stream File Refnum" Front Panel control.
    Used to open or create a file in one VI and perform I/O operations in another VI.
    """
    # This refnum has no additional data stored
    pass


class RefnumDevice(RefnumBase):
    """ Device Refnum Connector

    Usage unknown.
    """
    # This refnum is untested
    pass


class RefnumOccurrence(RefnumBase):
    """ Occurrence Refnum Connector

    Connector of "Occurrence Refnum" Front Panel control.
    Used to set or wait for the occurrence function in another VI.
    """
    # This refnum has no additional data stored
    pass


class RefnumTCPNetConn(RefnumBase):
    """ TCP Network Connection Refnum Connector

    Connector of "TCP Network Connection Refnum" Front Panel control.
    """
    # This refnum has no additional data stored
    pass


class RefnumAutoRef(RefnumBase):
    """ Automation Refnum Connector

    Connector of "Automation Refnum" Front Panel control.
    Used to open a reference to an ActiveX Server Object and pass it as a parameter to another VI.
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        ref_flags = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        count = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        # Create _separate_ empty namespace for each connector
        items = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            items[i].uid = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            items[i].classID0 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            items[i].classID4 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            items[i].classID6 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            items[i].classID8 = int.from_bytes(bldata.read(8), byteorder='big', signed=False)
        if ref_flags != 0:
            self.td_obj.field20 = int.from_bytes(bldata.read(4), byteorder='big', signed=True)
            self.td_obj.field24 = int.from_bytes(bldata.read(4), byteorder='big', signed=True)
        else:
            self.td_obj.field20 = 0
            self.td_obj.field24 = 0
        self.td_obj.items = items
        self.td_obj.ref_flags = ref_flags
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(self.td_obj.ref_flags).to_bytes(1, byteorder='big', signed=False)
        data_buf += len(self.td_obj.items).to_bytes(1, byteorder='big', signed=False)
        for guid in self.td_obj.items:
            data_buf += int(guid.uid).to_bytes(4, byteorder='big')
            data_buf += int(guid.classID0).to_bytes(4, byteorder='big', signed=False)
            data_buf += int(guid.classID4).to_bytes(2, byteorder='big', signed=False)
            data_buf += int(guid.classID6).to_bytes(2, byteorder='big', signed=False)
            data_buf += int(guid.classID8).to_bytes(8, byteorder='big', signed=False)
        if self.td_obj.ref_flags != 0:
            data_buf += int(self.td_obj.field20).to_bytes(4, byteorder='big', signed=True)
            data_buf += int(self.td_obj.field24).to_bytes(4, byteorder='big', signed=True)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 1
        exp_whole_len += 1 + (4+4+2+2+8) * len(self.td_obj.items)
        if self.td_obj.ref_flags != 0:
            exp_whole_len += 4 + 4
        return exp_whole_len

    def initWithXML(self, conn_elem):
        self.td_obj.ref_flags = int(conn_elem.get("RefFlags"), 0)
        self.td_obj.field20 = int(conn_elem.get("Field20"), 0)
        self.td_obj.field24 = int(conn_elem.get("Field24"), 0)
        pass

    def initWithXMLItem(self, item, conn_subelem):
        item.uid = int(conn_subelem.get("UID"), 0)
        classIdStr = conn_subelem.get("ClassID")
        if classIdStr is not None:
            classIdParts = classIdStr.split('-')
        else:
            classIdParts = []
        if len(classIdParts) > 0:
            item.classID0 = int(classIdParts[0], 16)
        if len(classIdParts) > 1:
            item.classID4 = int(classIdParts[1], 16)
        if len(classIdParts) > 2:
            item.classID6 = int(classIdParts[2], 16)
        if len(classIdParts) > 3:
            item.classID8 = int(classIdParts[3], 16)
        pass

    def exportXML(self, conn_elem, fname_base):
        conn_elem.set("RefFlags", "0x{:02X}".format(self.td_obj.ref_flags))
        conn_elem.set("Field20", "{:d}".format(self.td_obj.field20))
        conn_elem.set("Field24", "{:d}".format(self.td_obj.field24))
        pass

    def exportXMLItem(self, item, conn_subelem, fname_base):
        conn_subelem.set("UID", "0x{:02X}".format(item.uid))
        conn_subelem.set("ClassID", "{:08X}-{:04X}-{:04X}-{:016X}"\
              .format(item.classID0,item.classID4,item.classID6,item.classID8))
        pass


class RefnumLVObjCtl(RefnumBase):
    """ LVObject/Control Refnum Connector

    Connector of "Control Refnum" Front Panel control.
    Used to open a reference to a front panel control/indicator and pass the reference to another VI.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.td_obj.ctlflags = 0
        self.td_obj.hasitem = 0
        self.td_obj.itmident = b'UNKN'

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        count = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        # Create _separate_ empty namespace for each connector
        clients = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            cli_idx = readVariableSizeFieldU2p2(bldata)
            cli_flags = 0
            clients[i].index = cli_idx
            clients[i].flags = cli_flags
        self.td_obj.clients = clients
        # end of ContainerOMId data
        self.td_obj.ctlflags = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        items = [ ]
        if isGreaterOrEqVersion(ver, 8,0):
            hasitem = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        else:
            hasitem = 0
        if hasitem != 0:
            # Some early versions of LV8 have the identifier in reverted endianness; probably no need to support
            self.td_obj.itmident = bldata.read(4)
            items = readQualifiedName(bldata, self.po)
        self.td_obj.hasitem = hasitem
        self.td_obj.items = [ ]
        for strval in items:
            item = SimpleNamespace()
            item.strval = strval
            self.td_obj.items.append(item)
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        if not avoid_recompute:
            ver = self.vi.getFileVersion()
        else:
            ver = decodeVersion(0x09000000)
        data_buf = b''
        data_buf += int(len(self.td_obj.clients)).to_bytes(2, byteorder='big')
        for client in self.td_obj.clients:
            data_buf += int(client.index).to_bytes(2, byteorder='big')
        data_buf += int(self.td_obj.ctlflags).to_bytes(2, byteorder='big')
        if not isGreaterOrEqVersion(ver, 8,0):
            # For LV versions below 8.0, the data buffer ends here
            return data_buf
        data_buf += int(self.td_obj.hasitem).to_bytes(2, byteorder='big')
        if self.td_obj.hasitem != 0:
            data_buf += self.td_obj.itmident
            data_buf += prepareQualifiedName([item.strval for item in self.td_obj.items], self.po)
        return data_buf

    def expectedRSRCSize(self):
        ver = self.vi.getFileVersion()
        exp_whole_len = 2 + 2 * len(self.td_obj.clients)
        exp_whole_len += 2
        if isGreaterOrEqVersion(ver, 8,0):
            exp_whole_len += 2
            if self.td_obj.hasitem != 0:
                exp_whole_len += len(self.td_obj.itmident)
                exp_whole_len += 4 + sum((1+len(item.strval)) for item in self.td_obj.items)
        return exp_whole_len

    def initWithXML(self, conn_elem):
        self.td_obj.ctlflags = int(conn_elem.get("CtlFlags"), 0)
        self.td_obj.hasitem = int(conn_elem.get("HasItem"), 0)
        itmident = conn_elem.get("ItmIdent")
        if itmident is not None:
            self.td_obj.itmident = getRsrcTypeFromPrettyStr(itmident)
        elif self.td_obj.hasitem != 0:
            eprint("{:s}: Warning: TD {:d} type 0x{:02x} reftype {:d} marked as HasItem, but no ItmIdent"\
              .format(self.vi.src_fname,self.td_obj.index,self.td_obj.otype,self.td_obj.reftype))
        pass

    def initWithXMLItem(self, item, conn_subelem):
        item.strval = conn_subelem.get("Text").encode(self.vi.textEncoding)
        pass

    def exportXML(self, conn_elem, fname_base):
        ver = self.vi.getFileVersion()
        conn_elem.set("CtlFlags", "0x{:04X}".format(self.td_obj.ctlflags))
        conn_elem.set("HasItem", "{:d}".format(self.td_obj.hasitem))
        if isGreaterOrEqVersion(ver, 8,0):
            if self.td_obj.hasitem != 0:
                conn_elem.set("ItmIdent", getPrettyStrFromRsrcType(self.td_obj.itmident))
        pass

    def exportXMLItem(self, item, conn_subelem, fname_base):
        conn_subelem.set("Text", "{:s}".format(item.strval.decode(self.vi.textEncoding)))
        pass

    def checkSanity(self):
        ret = True
        if len(self.td_obj.clients) > 1:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} reftype {:d} should not have clients, but it does"\
                  .format(self.vi.src_fname,self.td_obj.index,self.td_obj.otype,self.td_obj.reftype))
            ret = False
        return ret


class RefnumMenu(RefnumBase):
    """ Menu Refnum Connector

    Connector of "Menu Refnum" Front Panel control.
    Used to pass a VI menu reference to a subVI.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumImaq(RefnumBase_RCIOOMId):
    """ IMAQ Session Refnum Connector

    Used with the Image Acquisition VIs.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.td_obj.ident = b'IMAQ'


class RefnumDataSocket(RefnumBase):
    """ DataSocket Refnum Connector

    Connector of "DataSocket Refnum" Front Panel control.
    Used to open a reference to a data connection.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumVisaRef(RefnumBase_RCIOOMId):
    """ Visa Refnum Connector

    Usage unknown. Use example in "VISA Resource Name NI_Silver.ctl".
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.td_obj.ident = b'Instr'


class RefnumIVIRef(RefnumBase_RCIOOMId):
    """ VI Refnum Connector

    Connector of "VI Refnum" Front Panel control.
    Used to open a reference to a VI and pass it as a parameter to another VI.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.td_obj.ident = b'IVI'

    def parseRSRCTypeOMId(self, bldata):
        self.parseRSRCTypeOMIdStart(bldata)
        ver = self.vi.getFileVersion()

        cli_count = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        for i in range(cli_count):
            client = SimpleNamespace()
            client.index = readVariableSizeFieldU2p2(bldata)
            client.flags = 0
            self.td_obj.clients.append(client)
        pass

    def prepareRSRCTypeOMId(self, avoid_recompute=False):
        data_buf, ref_clients, firstclient = self.prepareRSRCTypeOMIdStart(avoid_recompute=avoid_recompute)
        data_buf += int(len(ref_clients)).to_bytes(2, byteorder='big')
        for cli_index in ref_clients:
            data_buf += prepareVariableSizeFieldU2p2(cli_index)
        return data_buf

    def expectedRSRCTypeOMIdSize(self):
        exp_whole_len, ref_clients, firstclient = self.expectedRSRCTypeOMIdStartSize()
        exp_whole_len += 2
        for cli_index in ref_clients:
            exp_whole_len += ( 2 if (ref_clients[0] <= 0x7fff) else 4 )
        return exp_whole_len

    def initWithXML(self, conn_elem):
        super().initWithXML(conn_elem)
        # Clients import is covered in TDObjectRef
        pass

    def exportXML(self, conn_elem, fname_base):
        super().exportXML(conn_elem, fname_base)
        # Clients export is covered in TDObjectRef
        pass


class RefnumUDPNetConn(RefnumBase):
    """ UDP Network Connection Refnum Connector

    Connector of "UDP Network Connection Refnum" Front Panel control.
    Used to uniquely identify a UDP socket.
    """
    pass


class RefnumNotifierRef(RefnumBase_SimpleCliSingle):
    """ Notifier Refnum Connector

    Used with the Notifier Operations functions to suspend the execution
    until receive data from another section or another VI.
    Some of related controls: "Cancel Notification", "Get Notifier Status", "Obtain Notifier", "Send Notification".
    """
    pass


class RefnumQueue(RefnumBase_SimpleCliSingle):
    """ Queue Refnum Connector

    Used with the Queue Operations functions to store data in a queue.
    Some of related controls: "Dequeue Element", "Enqueue Element", "Flush Queue", "Obtain Queue".
    """
    pass


class RefnumIrdaNetConn(RefnumBase):
    """ IrDA Network Connection Refnum Connector

    Connector of "IrDA Network Connection Refnum" Front Panel control.
    """
    pass


class RefnumUsrDefined(RefnumBase_RCIOOMId):
    """ User Defined Refnum Connector

    Usage unknown.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.td_obj.typeName = b''

    def parseRSRCTypeOMId(self, bldata):
        self.parseRSRCTypeOMIdStart(bldata)
        # The data continues with a string, 1-byte length, padded to mul of 2
        strlen = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        self.td_obj.typeName = bldata.read(strlen)
        if ((strlen+1) % 2) > 0:
            bldata.read(1) # Padding byte
        pass

    def prepareRSRCTypeOMId(self, avoid_recompute=False):
        data_buf, ref_clients, firstclient = self.prepareRSRCTypeOMIdStart(avoid_recompute=avoid_recompute)
        if len(ref_clients) > 0:
            eprint("{:s}: Warning: TD {:d} type 0x{:02x} has more clients than supported"\
              .format(self.vi.src_fname, self.td_obj.index, self.td_obj.otype))
        strlen = len(self.td_obj.typeName)
        data_buf += int(strlen).to_bytes(1, byteorder='big')
        data_buf += self.td_obj.typeName
        if ((strlen+1) % 2) > 0:
            data_buf += b'\0' # padding
        return data_buf

    def expectedRSRCTypeOMIdSize(self):
        exp_whole_len, ref_clients, firstclient = self.expectedRSRCTypeOMIdStartSize()
        strlen = len(self.td_obj.typeName)
        exp_whole_len += 1 + strlen
        if ((strlen+1) % 2) > 0:
            exp_whole_len += 1
        return exp_whole_len

    def initWithXML(self, conn_elem):
        super().initWithXML(conn_elem)
        self.td_obj.typeName = conn_elem.get("TypeName").encode(encoding='ascii')
        pass

    def exportXML(self, conn_elem, fname_base):
        super().exportXML(conn_elem, fname_base)
        conn_elem.set("TypeName", "{:s}".format(self.td_obj.typeName.decode(encoding='ascii')))
        pass


class RefnumUsrDefndTag(RefnumUsrDefined):
    """ User Defined Tag Refnum Connector

    Usage unknown.
    """
    pass


class RefnumEventReg(RefnumBase):
    """ Event Callback Refnum Connector

    Connector of "Event Callback Refnum" Front Panel control.
    Used to unregister or re-register the event callback.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.td_obj.field0 = 0

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
        self.td_obj.field0 = field0
        self.td_obj.clients = clients
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(self.td_obj.field0).to_bytes(2, byteorder='big')
        data_buf += int(len(self.td_obj.clients)).to_bytes(2, byteorder='big')
        for client in self.td_obj.clients:
            data_buf += int(client.cfield0).to_bytes(2, byteorder='big')
            data_buf += int(client.cfield2).to_bytes(2, byteorder='big')
            data_buf += int(client.cfield4).to_bytes(2, byteorder='big')
            data_buf += int(client.index).to_bytes(2, byteorder='big')
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 2 + 2 + 8 * len(self.td_obj.clients)
        return exp_whole_len

    def initWithXML(self, conn_elem):
        self.td_obj.field0 = int(conn_elem.get("Field0"), 0)
        pass

    def initWithXMLClient(self, client, conn_subelem):
        client.cfield0 = int(conn_subelem.get("CField0"), 0)
        client.cfield2 = int(conn_subelem.get("CField2"), 0)
        client.cfield4 = int(conn_subelem.get("CField4"), 0)
        pass

    def exportXML(self, conn_elem, fname_base):
        conn_elem.set("Field0", "0x{:04X}".format(self.td_obj.field0))
        pass

    def exportXMLClient(self, client, conn_subelem, fname_base):
        conn_subelem.set("CField0", "0x{:04X}".format(client.cfield0))
        conn_subelem.set("CField2", "0x{:04X}".format(client.cfield2))
        conn_subelem.set("CField4", "0x{:04X}".format(client.cfield4))
        pass

    def checkSanity(self):
        ret = True
        if self.td_obj.field0 != 0:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} reftype {:d} field0 expected zero, has {}"\
                  .format(self.vi.src_fname,self.td_obj.index,self.td_obj.otype,self.td_obj.reftype,self.td_obj.field0))
            ret = False
        return ret


class RefnumDotNet(RefnumBase):
    """ .NET Refnum Connector

    Connector of ".NET Refnum" Front Panel control.
    Used to launch Select .NET Constructor dialog box and select an assembly.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.td_obj.assemblyName = None
        self.td_obj.dnTypeName = None
        self.td_obj.field0 = 0
        self.td_obj.dnflags = 0

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        self.td_obj.assemblyName = None
        self.td_obj.dnTypeName = None
        self.td_obj.field0 = 0
        if isGreaterOrEqVersion(ver, 8,1,1):
            dnflags = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            self.td_obj.dnflags = (dnflags & ~0x01)
            if (dnflags & 0x01) != 0:
                strlen = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                self.td_obj.dnTypeName = bldata.read(strlen)
        else:
            field0 = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            dnflags = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            self.td_obj.field0 = field0
            self.td_obj.dnflags = (dnflags & ~0x03)
            if (dnflags & 0x01) != 0:
                strlen = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
                self.td_obj.assemblyName = bldata.read(strlen)
                if ((strlen+1) % 2) > 0:
                    bldata.read(1) # Padding byte
            if (dnflags & 0x02) != 0:
                strlen = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
                self.td_obj.dnTypeName = bldata.read(strlen)
                if ((strlen+1) % 2) > 0:
                    bldata.read(1) # Padding byte
    pass

    def prepareRSRCData(self, avoid_recompute=False):
        if not avoid_recompute:
            ver = self.vi.getFileVersion()
        else:
            ver = decodeVersion(0x09000000)
        data_buf = b''
        if isGreaterOrEqVersion(ver, 8,1,1):
            dnTypeName = self.td_obj.dnTypeName

            dnflags = (self.td_obj.dnflags & ~0x01)
            if dnTypeName is not None:
                dnflags |= 0x01
            data_buf += int(dnflags).to_bytes(4, byteorder='big')

            if dnTypeName is not None:
                data_buf += int(len(dnTypeName)).to_bytes(4, byteorder='big')
                data_buf += dnTypeName
        else:
            data_buf += int(self.td_obj.field0).to_bytes(1, byteorder='big')
            assemblyName = self.td_obj.assemblyName
            dnTypeName = self.td_obj.dnTypeName

            dnflags = (self.td_obj.dnflags & ~0x03)
            if assemblyName is not None:
                dnflags |= 0x01
            if dnTypeName is not None:
                dnflags |= 0x02
            data_buf += int(dnflags).to_bytes(1, byteorder='big')

            if assemblyName is not None:
                strlen = len(assemblyName)
                data_buf += int(strlen).to_bytes(1, byteorder='big')
                data_buf += assemblyName
                if ((strlen+1) % 2) > 0:
                    data_buf += b'\0' # padding

            if dnTypeName is not None:
                strlen = len(dnTypeName)
                data_buf += int(strlen).to_bytes(1, byteorder='big')
                data_buf += dnTypeName
                if ((strlen+1) % 2) > 0:
                    data_buf += b'\0' # padding
        return data_buf

    def expectedRSRCSize(self):
        ver = self.vi.getFileVersion()
        exp_whole_len = 0

        if isGreaterOrEqVersion(ver, 8,1,1):
            exp_whole_len += 4
            dnTypeName = self.td_obj.dnTypeName
            if dnTypeName is not None:
                exp_whole_len += 4+len(dnTypeName)
        else:
            exp_whole_len += 1 + 1
            assemblyName = self.td_obj.assemblyName
            if assemblyName is not None:
                strlen = len(assemblyName)
                if ((strlen+1) % 2) > 0:
                    strlen += 1
                exp_whole_len += 1+strlen
            dnTypeName = self.td_obj.dnTypeName
            if dnTypeName is not None:
                strlen = len(dnTypeName)
                if ((strlen+1) % 2) > 0:
                    strlen += 1
                exp_whole_len += 1+strlen

        return exp_whole_len

    def initWithXML(self, conn_elem):
        field0 = conn_elem.get("Field0")
        if field0 is not None:
            self.td_obj.field0 = int(field0, 0)
        self.td_obj.dnflags = int(conn_elem.get("dNetFlags"), 0)

        assemblyNameStr = conn_elem.get("AssemblyName")
        if assemblyNameStr is not None:
            self.td_obj.assemblyName = assemblyNameStr.encode(encoding=self.vi.textEncoding)

        dnTypeNameStr = conn_elem.get("dNetTypeName")
        if dnTypeNameStr is not None:
            self.td_obj.dnTypeName = dnTypeNameStr.encode(encoding=self.vi.textEncoding)

        pass

    def exportXML(self, conn_elem, fname_base):
        if self.td_obj.field0 != 0:
            conn_elem.set("Field0", "0x{:04X}".format(self.td_obj.field0))
        conn_elem.set("dNetFlags", "0x{:02X}".format(self.td_obj.dnflags))
        if self.td_obj.assemblyName is not None:
            conn_elem.set("AssemblyName", self.td_obj.assemblyName.decode(self.vi.textEncoding))
        if self.td_obj.dnTypeName is not None:
            conn_elem.set("dNetTypeName", self.td_obj.dnTypeName.decode(self.vi.textEncoding))
        pass



class RefnumUserEvent(RefnumBase_SimpleCliSingle):
    """ User Event Callback Refnum Connector

    Usage unknown.
    """
    pass


class RefnumCallback(RefnumBase_RCIOOMId):
    """ Callback Refnum Connector

    Usage unknown.
    Unlike others RCIOOMId types, this one does not store
    a variant. So base methods had to be re-defined.
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.parseRSRCTypeOMId(bldata)
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = self.prepareRSRCTypeOMId(avoid_recompute=avoid_recompute)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = self.expectedRSRCTypeOMIdSize()
        return exp_whole_len


class RefnumUsrDefTagFlt(RefnumBase_RCIOOMId):
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
        self.td_obj.field0 = 0
        self.td_obj.field2 = 0
        self.td_obj.multiItem = 0

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        self.td_obj.field0 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        if isSmallerVersion(ver, 8,6,1):
            self.td_obj.field2 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        # Now there is a string, 1-byte length, padded to mul of 2; but it may consists of sub-strings
        items = []
        totlen = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        itempos = bldata.tell()
        if True:
            item = SimpleNamespace()
            item.text =  bldata.read(totlen)
        if len(item.text) < 1:
            multiItem = 0
        elif item.text[-1] != 0:
            multiItem = 0
        else:
            multiItem = 1
        self.td_obj.multiItem = multiItem
        if multiItem != 0:
            bldata.seek(itempos)
            rdlen = 0
            while rdlen < totlen:
                strlen = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
                rdlen += strlen + 1
                if strlen == 0:
                    break
                item = SimpleNamespace()
                item.text =  bldata.read(strlen)
                items.append(item)
        else:
            # Just one item - and we've already loaded it
            items.append(item)

        if ((totlen+1) % 2) > 0:
            bldata.read(1) # Padding byte
        self.td_obj.items = items
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        if not avoid_recompute:
            ver = self.vi.getFileVersion()
        else:
            ver = decodeVersion(0x09000000)
        data_buf = int(self.td_obj.field0).to_bytes(2, byteorder='big')
        if isSmallerVersion(ver, 8,6,1):
            data_buf += int(self.td_obj.field2).to_bytes(4, byteorder='big')
        items = self.td_obj.items.copy()
        if self.td_obj.multiItem == 0:
            if len(items) > 1:
                self.td_obj.multiItem = 1
        if self.td_obj.multiItem != 0:
            # In multi-item mode, we store additional length at start and '\0' at end
            totlen = sum( (1+len(item.text)) for item in items ) + 1
            data_buf += int(totlen).to_bytes(1, byteorder='big')
            for item in items:
                strlen = len(item.text)
                data_buf += int(strlen).to_bytes(1, byteorder='big')
                data_buf += item.text
            data_buf += b'\0' # empty strlen marks end of list
        else:
            # Make sure we have at least one item to store
            if len(items) < 1:
                item = SimpleNamespace()
                item.text =  b''
                items.append(item)
            for item in items: # we made sure there is exactly one item
                strlen = len(item.text)
                totlen = strlen
                data_buf += int(strlen).to_bytes(1, byteorder='big')
                data_buf += item.text
        if ((totlen+1) % 2) > 0:
            data_buf += b'\0' # Padding byte
        return data_buf

    def expectedRSRCSize(self):
        ver = self.vi.getFileVersion()
        exp_whole_len = 0
        exp_whole_len += 2
        if isSmallerVersion(ver, 8,6,1):
            exp_whole_len += 4
        items = self.td_obj.items
        if self.td_obj.multiItem != 0 or len(items) > 1:
            exp_whole_len += 1
            totlen = sum( (1+len(item.text)) for item in items ) + 1
        elif len(items) > 0:
            totlen = sum( (1+len(item.text)) for item in items )
        else:
            totlen = 1
        if ((totlen+1) % 2) > 0:
            totlen += 1
        exp_whole_len += totlen
        return exp_whole_len

    def initWithXML(self, conn_elem):
        self.td_obj.field0 = int(conn_elem.get("Field0"), 0)
        field2 = conn_elem.get("Field0")
        if field2 is not None:
            self.td_obj.field2 = int(field2, 0)
        self.td_obj.multiItem = int(conn_elem.get("MultiItem"), 0)
        pass

    def initWithXMLItem(self, item, conn_subelem):
        itemStr = conn_subelem.get("Text")
        item.text = itemStr.encode(encoding=self.vi.textEncoding)
        pass

    def exportXML(self, conn_elem, fname_base):
        conn_elem.set("Field0", "0x{:04X}".format(self.td_obj.field0))
        if self.td_obj.field2 != 0:
            conn_elem.set("Field2", "0x{:04X}".format(self.td_obj.field2))
        conn_elem.set("MultiItem", "{:d}".format(self.td_obj.multiItem))
        pass

    def exportXMLItem(self, item, conn_subelem, fname_base):
        conn_subelem.set("Text", item.text.decode(self.vi.textEncoding))
        pass


class RefnumBluetoothCon(RefnumBase):
    """ Bluetooth Network Connection Refnum Connector

    Connector of "Bluetooth Network Connection Refnum" Front Panel control.
    Used with the Bluetooth VIs and functions, to open connection.
    """
    def __init__(self, *args):
        super().__init__(*args)


class RefnumDataValueRef(RefnumBase_SimpleCliSingle):
    """ Data Value Refnum Connector

    Connector created as output of "Data Value Reference" Front Panel control.
    Used with the In Place Element structure when you want to operate on a data value without
    requiring the LabVIEW compiler to copy the data values and maintain those values in memory.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.td_obj.isExternal = 0

    def parseRSRCData(self, bldata):
        super().parseRSRCData(bldata)
        self.td_obj.isExternal = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = super().prepareRSRCData(avoid_recompute=avoid_recompute)
        data_buf += int(self.td_obj.isExternal).to_bytes(1, byteorder='big')
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = super().expectedRSRCSize()
        exp_whole_len += 1
        return exp_whole_len

    def initWithXML(self, conn_elem):
        super().initWithXML(conn_elem)
        self.td_obj.dnflags = int(conn_elem.get("IsExternal"), 0)

    def exportXML(self, conn_elem, fname_base):
        super().exportXML(conn_elem, fname_base)
        conn_elem.set("IsExternal", "0x{:02X}".format(self.td_obj.isExternal))

    def checkSanity(self):
        ret = super().checkSanity()
        return ret


class RefnumFIFORef(RefnumBase_SimpleCliSingle):
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


def refnumEnToName(refnumEn):
    """ Return text name for REFNUM_TYPE element
    """
    if LV_INTERNAL_REFNUM_TYPE_NAMES.has_value(int(refnumEn)):
        lvrefEn = LV_INTERNAL_REFNUM_TYPE_NAMES(refnumEn)
        refnName = lvrefEn.name
    elif isinstance(refnumEn, REFNUM_TYPE):
        refnName = refnumEn.name
        raise NotImplementedError("Value {} not in {}.".format(refnumEn.name,LV_INTERNAL_REFNUM_TYPE_NAMES.__name__))
    else:
        refnName = "Refnum{:02X}".format(refnumEn)
    return refnName


def refnumNameToEnum(refnName):
    """ Return REFNUM_TYPE element for given text name
    """
    refnumEn = None

    if LV_INTERNAL_REFNUM_TYPE_NAMES.has_name(refnName):
        lvrefEn = LV_INTERNAL_REFNUM_TYPE_NAMES[refnName]
        refnumEn = REFNUM_TYPE(lvrefEn.value)

    # no direct conversion from REFNUM_TYPE names
    # These would be probllematic as it has no has_name().
    if refnumEn is None:
        tagParse = re.match("^Refnum([0-9A-F]{2,4})$", refnName)
        if tagParse is not None:
            refnumEn = int(tagParse[1], 16)

    return refnumEn


def newTDObjectRef(vi, blockref, td_obj, reftype, po):
    """ Calls proper constructor to create refnum connector object.

    If tjis function returns NULL for a specific reftype, then refnum connector
    of that type will not be parsed and will be stored as BIN file.
    """
    ctor = {
        REFNUM_TYPE.Generic: RefnumGeneric,
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
    return ctor(vi, blockref, td_obj, reftype, po)

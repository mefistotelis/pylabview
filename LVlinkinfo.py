# -*- coding: utf-8 -*-

""" LabView RSRC file format Link Object Refs.

    Support of Link Identities storage.
"""

# Copyright (C) 2019-2020 Mefistotelis <mefistotelis@gmail.com>
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
    def __init__(self, vi, list_ident, ident, po):
        """ Creates new link object.
        """
        self.vi = vi
        self.po = po
        self.ident = ident
        self.list_ident = list_ident
        self.content = None
        if self.__doc__:
            self.full_name = " {:s} ".format(self.__doc__.split('\n')[0].strip())
        else:
            self.full_name = ""
        self.qualName = None
        self.pathRef = None
        self.linkSaveFlag = None

    def parsePathRef(self, bldata):
        startPos = bldata.tell()
        clsident = bldata.read(4)
        if clsident == b'PTH0':
            pathRef = LVclasses.LVPath0(self.vi, self.po)
        elif clsident in (b'PTH1', b'PTH2',):
            pathRef = LVclasses.LVPath1(self.vi, self.po)
        else:
            raise RuntimeError("{:s} {} contains path data of unrecognized class {}"\
          .format(type(self).__name__,self.ident,clsident))
        bldata.seek(startPos)
        pathRef.parseRSRCData(bldata)
        return pathRef

    def parseBasicLinkSaveInfo(self, bldata):
        ver = self.vi.getFileVersion()

        if (bldata.tell() % 4) > 0:
            bldata.read(4 - (bldata.tell() % 4)) # Padding bytes

        self.qualName = readQualifiedName(bldata, self.po)

        if (bldata.tell() % 2) > 0:
            bldata.read(2 - (bldata.tell() % 2)) # Padding bytes

        self.pathRef = self.parsePathRef(bldata)

        if isGreaterOrEqVersion(ver, 8,5,0,1):
            if isGreaterOrEqVersion(ver, 8,6,0,1):
                self.linkSaveFlag = bldata.read(4)
            else:
                self.linkSaveFlag = bldata.read(1)
        pass

    def parseVILinkRefInfo(self, bldata):
        ver = self.vi.getFileVersion()
        self.viLinkFieldA = 0
        self.viLinkLibVersion = 0
        self.viLinkField4 = 0
        self.viLinkFieldB = b''
        self.viLinkFieldC = b''
        self.viLinkFieldD = 0

        flagBt = 0xff
        if isGreaterOrEqVersion(ver, 14,0,0,3):
            flagBt = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        if flagBt != 0xff:
            self.viLinkFieldA = flagBt & 1
            self.viLinkLibVersion = (flagBt >> 1) & 0x1F
            self.viLinkField4 = flagBt >> 6
        else:
            if isGreaterOrEqVersion(ver, 8,0,0,3):
                self.viLinkField4 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                self.viLinkLibVersion = int.from_bytes(bldata.read(8), byteorder='big', signed=False)
            else:
                self.viLinkField4 = 1
                self.viLinkLibVersion = 0
            self.viLinkFieldB = bldata.read(4)
            self.viLinkFieldC = bldata.read(4)
            self.viLinkFieldD = int.from_bytes(bldata.read(4), byteorder='big', signed=True)
        pass

    def parseTypedLinkSaveInfo(self, bldata):
        ver = self.vi.getFileVersion()
        self.typedLinkFlags = None
        self.typedLinkTD = None

        if isGreaterOrEqVersion(ver, 8,0,0,1):
            self.parseBasicLinkSaveInfo(bldata)

            clientTD = SimpleNamespace()
            clientTD.index = readVariableSizeFieldU2p2(bldata)
            clientTD.flags = 0 # Only Type Mapped entries have it non-zero
            self.typedLinkTD = clientTD

            self.parseVILinkRefInfo(bldata)

            if isGreaterOrEqVersion(ver, 12,0,0,3):
                self.typedLinkFlags = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        else:
            raise NotImplementedError("LinkObj {} TypedLinkSaveInfo parse for LV7 not implemented"\
              .format(self.ident))
        pass

    def parseLinkOffsetList(self, bldata):
        count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        if count > self.po.connector_list_limit:
            raise RuntimeError("{:s} {} Offset List length {} exceeds limit"\
              .format(type(self).__name__, self.ident, count))
        offsetList = []
        for i in range(count):
            offs = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            offsetList.append(offs)
        return offsetList

    def parseOffsetLinkSaveInfo(self, bldata):
        ver = self.vi.getFileVersion()
        self.offsetList = []

        self.parseTypedLinkSaveInfo(bldata)

        if isGreaterOrEqVersion(ver, 8,2,0,3):
            self.offsetList = self.parseLinkOffsetList(bldata)
        pass

    def parseHeapToVILinkSaveInfo(self, bldata):
        ver = self.vi.getFileVersion()
        self.pathRef2 = None

        self.parseOffsetLinkSaveInfo(bldata)

        if isGreaterOrEqVersion(ver, 8,2,0,3):
            self.pathRef2 = self.parsePathRef(bldata)
        print("{:s} {} content: {} {} {}"\
              .format(type(self).__name__, self.ident, self.pathRef, self.offsetList, self.pathRef2))
        pass

    def parseUDClassAPILinkCache(self, bldata):
        ver = self.vi.getFileVersion()
        self.apiLinkLibVersion = 0
        self.apiLinkIsInternal = 0
        self.apiLinkBool2 = 1

        if (bldata.tell() % 4) > 0:
            bldata.read(4 - (bldata.tell() % 4)) # Padding bytes

        if isGreaterOrEqVersion(ver, 8,0,0,1):
            self.apiLinkLibVersion = int.from_bytes(bldata.read(8), byteorder='big', signed=False)
        else:
            self.apiLinkLibVersion = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

        if isSmallerVersion(ver, 8,0,0,4):
            bldata.read(4)

        self.apiLinkIsInternal = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        if isGreaterOrEqVersion(ver, 8,1,0,2):
            self.apiLinkBool2 = int.from_bytes(bldata.read(1), byteorder='big', signed=False)

        if isGreaterOrEqVersion(ver, 9,0,0,2):
            self.apiLinkCallParentNodes = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        else:
            self.apiLinkCallParentNodes = 0

        self.apiLinkContent = readLStr(bldata, 1, self.po)

    def parseUDClassHeapAPISaveInfo(self, bldata):
        ver = self.vi.getFileVersion()
        if isGreaterOrEqVersion(ver, 8,0,0,3):
            self.parseBasicLinkSaveInfo(bldata)
            self.parseUDClassAPILinkCache(bldata)
        else:
            self.parseBasicLinkSaveInfo(bldata)

        if (bldata.tell() % 4) > 0:
            bldata.read(4 - (bldata.tell() % 4)) # Padding bytes

        # Not sure if that list is OffsetList, but has the same structure
        self.apiLinkCacheList = self.parseLinkOffsetList(bldata)

    def parseRSRCData(self, bldata):
        """ Parses binary data chunk from RSRC file.

        Receives file-like block data handle positioned at ident.
        The handle gives access to binary data which is associated with the link object.
        Parses the binary data, filling properties.
        """
        self.ident = bldata.read(4)

    def prepareRSRCData(self, avoid_recompute=False):
        """ Fills binary data chunk for RSRC file which is associated with the link object.

        Creates bytes with binary data, starting with ident.
        """
        data_buf = b''
        data_buf += self.ident[:4]
        raise NotImplementedError("LinkObj {} binary creation not implemented"\
          .format(self.ident))
        return data_buf

    def expectedRSRCSize(self):
        """ Returns data size expected to be returned by prepareRSRCData().
        """
        exp_whole_len = 4
        return exp_whole_len

    def initWithXML(self, lnkobj_elem):
        """ Parses XML branch to fill properties of the link object.

        Receives ElementTree branch starting at tag associated with the link object.
        Parses the XML attributes, filling properties.
        """
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)

    def exportXML(self, lnkobj_elem, fname_base):
        """ Fills XML branch with properties of the link object.

        Receives ElementTree branch starting at tag associated with the link object.
        Sets the XML attributes, using properties from self.
        """
        pretty_ident = getPrettyStrFromRsrcType(self.ident)
        lnkobj_elem.tag = pretty_ident
        raise NotImplementedError("LinkObj {} XML export not implemented"\
          .format(self.ident))

    def checkSanity(self):
        ret = True
        return ret


class LinkObjInstanceVIToNamespacerVI(LinkObjBase):
    """ InstanceVI To NamespacerVI Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToAssembly(LinkObjBase):
    """ Heap To Assembly Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToAssembly(LinkObjBase):
    """ VI To Assembly Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToEIOLink(LinkObjBase):
    """ VI To EIO Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToEIOLink(LinkObjBase):
    """ Heap To EIO Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToCCSymbolLink(LinkObjBase):
    """ VI To CCSymbol Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToFileLink(LinkObjBase):
    """ VI To File Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToFileNoWarnLink(LinkObjBase):
    """ VI To FileNoWarn Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToFilePathLink(LinkObjBase):
    """ VI To FilePath Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToFilePathLink(LinkObjBase):
    """ Heap To FilePath Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjXNodeToFilePathLink(LinkObjBase):
    """ XNode To FilePath Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToGenVI(LinkObjBase):
    """ VI To Gen VI Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToInstantiationVI(LinkObjBase):
    """ VI To InstantiationVI Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjInstantiationVIToGenVI(LinkObjBase):
    """ InstantiationVI To GenVI Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToVINamedLink(LinkObjBase):
    """ VI To VINamed Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToLibraryDataLink(LinkObjBase):
    """ VI To LibraryDataLink Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToMSLink(LinkObjBase):
    """ VI To MSLink Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjTypeDefToCCLink(LinkObjBase):
    """ TypeDef To CC Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        self.parseHeapToVILinkSaveInfo(bldata)


class LinkObjHeapToXCtlInterface(LinkObjBase):
    """ Heap To XCtlInterface Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjXCtlToXInterface(LinkObjBase):
    """ XCtlToXInterface Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToXCtlInterface(LinkObjBase):
    """ VI To XCtlInterface Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToXNodeInterface(LinkObjBase):
    """ VI To XNodeInterface Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToXNodeProjectItemLink(LinkObjBase):
    """ VI To XNodeProjectItem Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToXNodeProjectItemLink(LinkObjBase):
    """ Heap To XNodeProjectItem Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjActiveXVIToTypeLib(LinkObjBase):
    """ ActiveXVIToTypeLib Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToLib(LinkObjBase):
    """ VI To Lib Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjUDClassDDOToUDClassAPILink(LinkObjBase):
    """ UDClassDDO To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.content = []

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        self.parseUDClassHeapAPISaveInfo(bldata)
        pass

    def exportXML(self, lnkobj_elem, fname_base):
        pretty_ident = getPrettyStrFromRsrcType(self.ident)
        lnkobj_elem.tag = pretty_ident
        for client in self.content:
            if isinstance(client, LVclasses.LVObject):#TODO is this condition needed?
                subelem = ET.SubElement(lnkobj_elem,"RefObject")
                client.exportXML(subelem, fname_base)
            else:
                subelem = ET.SubElement(lnkobj_elem,"LOObject")
                client.exportXML(subelem, fname_base)
        raise NotImplementedError("LinkObj {} export not fully implemented"\
          .format(self.ident))
        pass


class LinkObjDDODefaultDataToUDClassAPILink(LinkObjBase):
    """ DDODefaultData To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.content = []

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
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
                self.content.append(obj)
            else:
                raise RuntimeError("LinkObj {} refers to unrecognized class {}"\
                  .format(self.ident,objident))
            unkval3 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            unkval4 = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            unkval5 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            unkval6 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            unkval7 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            unkval11 = bldata.read(24)
        pass

    def exportXML(self, lnkobj_elem, fname_base):
        pretty_ident = getPrettyStrFromRsrcType(self.ident)
        lnkobj_elem.tag = pretty_ident
        for client in self.content:
            if isinstance(client, LVclasses.LVObject):#TODO is this condition needed?
                subelem = ET.SubElement(lnkobj_elem,"RefObject")
                client.exportXML(subelem, fname_base)
            else:
                subelem = ET.SubElement(lnkobj_elem,"LOObject")
                client.exportXML(subelem, fname_base)
        raise NotImplementedError("LinkObj {} export not fully implemented"\
          .format(self.ident))
        pass


class LinkObjHeapObjToUDClassAPILink(LinkObjBase):
    """ HeapObj To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToUDClassAPILink(LinkObjBase):
    """ VI To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjDataValueRefVIToUDClassAPILink(LinkObjBase):
    """ DataValueRefVI To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToVariableAbsoluteLink(LinkObjBase):
    """ VI To VariableAbsolute Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToVariableRelativeLink(LinkObjBase):
    """ VI To VariableRelative Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToVariableAbsoluteLink(LinkObjBase):
    """ Heap To VariableAbsolute Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToVariableRelativeLink(LinkObjBase):
    """ Heap To VariableRelative Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjDSToVariableAbsoluteLink(LinkObjBase):
    """ DS To VariableAbsolute Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjDSToVariableRelativeLink(LinkObjBase):
    """ DS To VariableRelative Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjDSToDSLink(LinkObjBase):
    """ DS To DS Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjDSToExtFuncLink(LinkObjBase):
    """ DS To ExtFunc Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjDSToCINLink(LinkObjBase):
    """ DS To CIN Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjDSToScriptLink(LinkObjBase):
    """ DS To Script Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjDSToCallByRefLink(LinkObjBase):
    """ DS To CallByRef Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjDSToStaticVILink(LinkObjBase):
    """ DS To StaticVI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToStdVILink(LinkObjBase):
    """ VI To StdVI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToProgRetLink(LinkObjBase):
    """ VI To ProgRet Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToPolyLink(LinkObjBase):
    """ VI To Poly Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToCCLink(LinkObjBase):
    """ VI To CC Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToStaticVILink(LinkObjBase):
    """ VI To StaticVI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToAdaptiveVILink(LinkObjBase):
    """ VI To AdaptiveVI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToCCSymbolLink(LinkObjBase):
    """ Heap To CCSymbol Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjIUseToVILink(LinkObjBase):
    """ IUse To VI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.content = []

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        self.content = []

        self.ident = bldata.read(4)

        #self.parseBasicLinkSaveInfo(bldata)

        if (bldata.tell() % 4) > 0:
            bldata.read(4 - (bldata.tell() % 4)) # Padding bytes

        self.qualName = readQualifiedName(bldata, self.po)

        if (bldata.tell() % 2) > 0:
            bldata.read(2 - (bldata.tell() % 2)) # Padding bytes

        for i in range(len(self.qualName)):
            # TODO this needs figuring out
            objstart = bldata.tell()
            objident = bldata.read(4)
            bldata.seek(objstart)
            if objident == b'PTH0':
                obj = LVclasses.LVPath0(self.vi, self.po)
                obj.parseRSRCData(bldata)
                self.content.append(obj)
            else:
                raise RuntimeError("LinkObj {} refers to unrecognized class {}"\
                  .format(self.ident,objident))
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

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        for subelem in lnkobj_elem:
            cli_ident = getRsrcTypeFromPrettyStr(subelem.tag)
            client = newLinkObject(self.vi, self.ident, cli_ident, self.po)
            self.content.append(client)
            client.initWithXML(subelem)
        pass

    def exportXML(self, lnkobj_elem, fname_base):
        pretty_ident = getPrettyStrFromRsrcType(self.ident)
        lnkobj_elem.tag = pretty_ident
        for client in self.content:
            if isinstance(client, LVclasses.LVObject):#TODO is this condition needed?
                subelem = ET.SubElement(lnkobj_elem,"RefObject")
                client.exportXML(subelem, fname_base)
            else:
                subelem = ET.SubElement(lnkobj_elem,"LOObject")
                client.exportXML(subelem, fname_base)
        raise NotImplementedError("LinkObj {} XML export not fully implemented"\
          .format(self.ident))
        pass


def newLinkObject(vi, list_ident, ident, po):
    """ Calls proper constructor to create link object.
    """
    if ident in (b'IVOV',):
        ctor = LinkObjInstanceVIToNamespacerVI
    elif ident in (b'DNDA',):
        ctor = LinkObjHeapToAssembly
    elif ident in (b'DNVA',):
        ctor = LinkObjVIToAssembly
    elif ident in (b'EiVr',):
        ctor = LinkObjVIToEIOLink
    elif ident in (b'HpEr',):
        ctor = LinkObjHeapToEIOLink
    elif ident in (b'V2CC',):
        ctor = LinkObjVIToCCSymbolLink
    elif ident in (b'VIFl',):
        ctor = LinkObjVIToFileLink
    elif ident in (b'VIFN',):
        ctor = LinkObjVIToFileNoWarnLink
    elif ident in (b'VIXF',):
        ctor = LinkObjVIToFilePathLink
    elif ident in (b'HOXF',):
        ctor = LinkObjHeapToFilePathLink
    elif ident in (b'XNFP',):
        ctor = LinkObjXNodeToFilePathLink
    elif ident in (b'VIGV',):
        ctor = LinkObjVIToGenVI
    elif ident in (b'VIIV',):
        ctor = LinkObjVIToInstantiationVI
    elif ident in (b'IVGV',):
        ctor = LinkObjInstantiationVIToGenVI
    elif ident in (b'VTVN',):
        ctor = LinkObjVIToVINamedLink
    elif ident in (b'V2LD',):
        ctor = LinkObjVIToLibraryDataLink
    elif ident in (b'VIMS',):
        ctor = LinkObjVIToMSLink
    elif ident in (b'TDCC',) or list_ident in (b'FPHP',) and ident in (b'LVCC',):
        ctor = LinkObjTypeDefToCCLink
    elif ident in (b'HXCI',):
        ctor = LinkObjHeapToXCtlInterface
    elif ident in (b'XCXI',):
        ctor = LinkObjXCtlToXInterface
    elif ident in (b'VIXC',):
        ctor = LinkObjVIToXCtlInterface
    elif ident in (b'VIXN',):
        ctor = LinkObjVIToXNodeInterface
    elif ident in (b'XVPR',):
        ctor = LinkObjVIToXNodeProjectItemLink
    elif ident in (b'XHPR',):
        ctor = LinkObjHeapToXNodeProjectItemLink
    elif ident in (b'AXVT',):
        ctor = LinkObjActiveXVIToTypeLib
    elif ident in (b'VILB',):
        ctor = LinkObjVIToLib
    elif ident in (b'FPPI',):
        ctor = LinkObjUDClassDDOToUDClassAPILink
    elif ident in (b'DDPI',):
        ctor = LinkObjDDODefaultDataToUDClassAPILink
    elif ident in (b'VRPI',):
        ctor = LinkObjHeapObjToUDClassAPILink
    elif ident in (b'VIPI',):
        ctor = LinkObjVIToUDClassAPILink
    elif ident in (b'RVPI',):
        ctor = LinkObjDataValueRefVIToUDClassAPILink
    elif ident in (b'VIVr',):
        ctor = LinkObjVIToVariableAbsoluteLink
    elif ident in (b'VIVl',):
        ctor = LinkObjVIToVariableRelativeLink
    elif ident in (b'HpVr',):
        ctor = LinkObjHeapToVariableAbsoluteLink
    elif ident in (b'HpVL',):
        ctor = LinkObjHeapToVariableRelativeLink
    elif ident in (b'DSVr',):
        ctor = LinkObjDSToVariableAbsoluteLink
    elif ident in (b'DSVl',):
        ctor = LinkObjDSToVariableRelativeLink
    elif ident in (b'DSDS',) or list_ident in (b'VIDS',) and ident in (b'VIDS',):
        ctor = LinkObjDSToDSLink
    elif ident in (b'DSEF',) or list_ident in (b'VIDS',) and ident in (b'XFun',):
        ctor = LinkObjDSToExtFuncLink
    elif ident in (b'DSCN',) or list_ident in (b'VIDS',) and ident in (b'LVSB',):
        ctor = LinkObjDSToCINLink
    elif ident in (b'DSSC',) or list_ident in (b'VIDS',) and ident in (b'SFTB',):
        ctor = LinkObjDSToScriptLink
    elif ident in (b'DSCB',):
        ctor = LinkObjDSToCallByRefLink
    elif ident in (b'DSSV',):
        ctor = LinkObjDSToStaticVILink
    elif ident in (b'VIVI',) or list_ident in (b'LVIN',) and ident in (b'LVIN',):
        ctor = LinkObjVIToStdVILink
    elif ident in (b'VIPR',) or list_ident in (b'LVIN',) and ident in (b'LVPR',):
        ctor = LinkObjVIToProgRetLink
    elif ident in (b'VIPV',) or list_ident in (b'LVIN',) and ident in (b'POLY',):
        ctor = LinkObjVIToPolyLink
    elif ident in (b'VICC',) or list_ident in (b'LVCC',) and ident in (b'LVCC',b'CCCC',):
        ctor = LinkObjVIToCCLink
    elif ident in (b'BSVR',):
        ctor = LinkObjVIToStaticVILink
    elif ident in (b'VIAV',):
        ctor = LinkObjVIToAdaptiveVILink
    elif ident in (b'H2CC',):
        ctor = LinkObjHeapToCCSymbolLink
    elif ident in (b'IUVI',):
        ctor = LinkObjIUseToVILink
    else:
        raise AttributeError("List {} contains unrecognized class {}".format(list_ident,ident))

    return ctor(vi, list_ident, ident, po)

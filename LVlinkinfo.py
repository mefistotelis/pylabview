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
                self.linkSaveFlag = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            else:
                self.linkSaveFlag = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        pass

    def prepareBasicLinkSaveInfo(self, start_offs):
        ver = self.vi.getFileVersion()
        data_buf = b''
        if (start_offs+len(data_buf)) % 4 > 0:
            padding_len = 4 - ((start_offs+len(data_buf)) % 4)
            data_buf += (b'\0' * padding_len)

        data_buf += prepareQualifiedName(self.qualName, self.po)

        if (start_offs+len(data_buf)) % 2 > 0:
            padding_len = 2 - ((start_offs+len(data_buf)) % 2)
            data_buf += (b'\0' * padding_len)

        data_buf += self.pathRef.prepareRSRCData()

        if isGreaterOrEqVersion(ver, 8,5,0,1):
            if isGreaterOrEqVersion(ver, 8,6,0,1):
                data_buf += int(self.linkSaveFlag).to_bytes(4, byteorder='big', signed=False)
            else:
                data_buf += int(self.linkSaveFlag).to_bytes(1, byteorder='big', signed=False)
        return data_buf

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

    def prepareVILinkRefInfo(self, start_offs):
        ver = self.vi.getFileVersion()
        data_buf = b''

        flagBt = 0xff
        if isGreaterOrEqVersion(ver, 14,0,0,3):
            if (self.viLinkFieldA <= 1) and (self.viLinkLibVersion <= 0x1F) and (self.viLinkField4 <= 0x3):
                flagBt = self.viLinkFieldA = (self.viLinkFieldA & 1)
                flagBt |= (self.viLinkLibVersion & 0x1F) << 1
                flagBt |= (self.viLinkField4 & 0x3) << 6
            data_buf += int(flagBt).to_bytes(1, byteorder='big', signed=False)

        if flagBt != 0xff:
            pass
        else:
            if isGreaterOrEqVersion(ver, 8,0,0,3):
                data_buf += int(self.viLinkField4).to_bytes(4, byteorder='big', signed=False)
                data_buf += int(self.viLinkLibVersion).to_bytes(8, byteorder='big', signed=False)
            data_buf += self.viLinkFieldB[:4]
            data_buf += self.viLinkFieldC[:4]
            data_buf += int(self.viLinkFieldD).to_bytes(4, byteorder='big', signed=True)
        return data_buf

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

    def prepareTypedLinkSaveInfo(self, start_offs):
        ver = self.vi.getFileVersion()
        data_buf = b''

        if isGreaterOrEqVersion(ver, 8,0,0,1):
            data_buf += self.prepareBasicLinkSaveInfo(start_offs+len(data_buf))

            clientTD = self.typedLinkTD
            data_buf += prepareVariableSizeFieldU2p2(clientTD.index)

            data_buf += self.prepareVILinkRefInfo(start_offs+len(data_buf))

            if isGreaterOrEqVersion(ver, 12,0,0,3):
                data_buf +=  int(self.typedLinkFlags).to_bytes(4, byteorder='big', signed=False)
        else:
            raise NotImplementedError("LinkObj {} TypedLinkSaveInfo binary preparation for LV7 not implemented"\
              .format(self.ident))
        return data_buf

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

    def prepareLinkOffsetList(self, offsetList, start_offs):
        data_buf = b''
        data_buf += len(offsetList).to_bytes(4, byteorder='big', signed=False)
        for offs in offsetList:
            data_buf += int(offs).to_bytes(4, byteorder='big', signed=False)
        return data_buf

    def parseOffsetLinkSaveInfo(self, bldata):
        ver = self.vi.getFileVersion()
        self.offsetList = []

        self.parseTypedLinkSaveInfo(bldata)

        if isGreaterOrEqVersion(ver, 8,2,0,3):
            self.offsetList = self.parseLinkOffsetList(bldata)
        pass

    def prepareOffsetLinkSaveInfo(self, start_offs):
        ver = self.vi.getFileVersion()
        data_buf = b''

        data_buf += self.prepareTypedLinkSaveInfo(start_offs+len(data_buf))

        if isGreaterOrEqVersion(ver, 8,2,0,3):
            data_buf += self.prepareLinkOffsetList(self.offsetList, start_offs+len(data_buf))
        return data_buf

    def parseHeapToVILinkSaveInfo(self, bldata):
        ver = self.vi.getFileVersion()
        self.pathRef2 = None

        self.parseOffsetLinkSaveInfo(bldata)

        if isGreaterOrEqVersion(ver, 8,2,0,3):
            self.pathRef2 = self.parsePathRef(bldata)

        if (self.po.verbose > 2):
            print("{:s} {} content: {} {} {}"\
              .format(type(self).__name__, self.ident, self.pathRef, self.offsetList, self.pathRef2))
        pass

    def prepareHeapToVILinkSaveInfo(self, start_offs):
        ver = self.vi.getFileVersion()
        data_buf = b''

        data_buf += self.prepareOffsetLinkSaveInfo(start_offs+len(data_buf))

        if isGreaterOrEqVersion(ver, 8,2,0,3):
            data_buf += self.pathRef2.prepareRSRCData()
        return data_buf

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

    def prepareUDClassAPILinkCache(self, start_offs):
        ver = self.vi.getFileVersion()
        data_buf = b''

        if (start_offs+len(data_buf)) % 4 > 0:
            padding_len = 4 - ((start_offs+len(data_buf)) % 4)
            data_buf += (b'\0' * padding_len) # Padding bytes

        if isGreaterOrEqVersion(ver, 8,0,0,1):
            data_buf += int(self.apiLinkLibVersion).to_bytes(8, byteorder='big', signed=False)
        else:
            data_buf += int(self.apiLinkLibVersion).to_bytes(4, byteorder='big', signed=False)

        if isSmallerVersion(ver, 8,0,0,4):
            data_buf += (b'\0' * 4)

        data_buf += int(self.apiLinkIsInternal).to_bytes(1, byteorder='big', signed=False)
        if isGreaterOrEqVersion(ver, 8,1,0,2):
            data_buf += int(self.apiLinkBool2).to_bytes(1, byteorder='big', signed=False)

        if isGreaterOrEqVersion(ver, 9,0,0,2):
            data_buf += int(self.apiLinkCallParentNodes).to_bytes(1, byteorder='big', signed=False)

        data_buf += prepareLStr(self.apiLinkContent, 1, self.po)
        return data_buf

    def parseUDClassHeapAPISaveInfo(self, bldata):
        ver = self.vi.getFileVersion()

        if isGreaterOrEqVersion(ver, 8,0,0,3):
            self.parseBasicLinkSaveInfo(bldata)
            self.parseUDClassAPILinkCache(bldata)
        else:
            self.parseBasicLinkSaveInfo(bldata)
            self.apiLinkLibVersion = 0
            self.apiLinkIsInternal = 0
            self.apiLinkBool2 = 1

        if (bldata.tell() % 4) > 0:
            bldata.read(4 - (bldata.tell() % 4)) # Padding bytes

        # Not sure if that list is OffsetList, but has the same structure
        self.apiLinkCacheList = self.parseLinkOffsetList(bldata)

        if (self.po.verbose > 2):
            print("{:s} {} content: {} {} {}"\
              .format(type(self).__name__, self.ident, self.pathRef, self.apiLinkLibVersion, self.apiLinkCacheList))
        pass

    def prepareUDClassHeapAPISaveInfo(self, start_offs):
        ver = self.vi.getFileVersion()
        data_buf = b''

        if (self.po.verbose > 2):
            print("{:s} {} content: {} {} {}"\
              .format(type(self).__name__, self.ident, self.pathRef, self.apiLinkLibVersion, self.apiLinkCacheList))

        if isGreaterOrEqVersion(ver, 8,0,0,3):
            data_buf += self.prepareBasicLinkSaveInfo(start_offs+len(data_buf))
            data_buf += self.prepareUDClassAPILinkCache(start_offs+len(data_buf))
        else:
            data_buf += self.prepareBasicLinkSaveInfo(start_offs+len(data_buf))

        if (start_offs+len(data_buf)) % 4 > 0:
            padding_len = 4 - ((start_offs+len(data_buf)) % 4)
            data_buf += (b'\0' * padding_len) # Padding bytes

        # Not sure if that list is OffsetList, but has the same structure
        data_buf += self.prepareLinkOffsetList(self.apiLinkCacheList, start_offs+len(data_buf))
        return data_buf

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


class LinkObjInstncVIToNamspcrVI(LinkObjBase):
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

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareUDClassHeapAPISaveInfo(start_offs+len(data_buf))
        return data_buf

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
        self.parseUDClassHeapAPISaveInfo(bldata)
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareUDClassHeapAPISaveInfo(start_offs+len(data_buf))
        return data_buf

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
        self.pathRef2 = None
        self.iuseStr = b''

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        self.pathRef2 = None

        self.ident = bldata.read(4)

        if isGreaterOrEqVersion(ver, 8,2,0,3):
            self.parseHeapToVILinkSaveInfo(bldata)
        else:
            self.parseOffsetLinkSaveInfo(bldata)

        if isGreaterOrEqVersion(ver, 8,0,0,1):
            self.iuseStr = readPStr(bldata, 2, self.po)
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        ver = self.vi.getFileVersion()
        data_buf = b''

        data_buf += self.ident[:4]

        if isGreaterOrEqVersion(ver, 8,2,0,3):
            data_buf += self.prepareHeapToVILinkSaveInfo(start_offs+len(data_buf))
        else:
            data_buf += self.prepareOffsetLinkSaveInfo(start_offs+len(data_buf))

        if isGreaterOrEqVersion(ver, 8,0,0,1):
            data_buf += preparePStr(self.iuseStr, 2, self.po)
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        raise NotImplementedError("LinkObj {} XML import not fully implemented"\
          .format(self.ident))
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


class LinkObjPIUseToPolyLink(LinkObjBase):
    """ PIUse To Poly Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.pathRef2 = None
        self.iuseStr = b''

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        self.pathRef2 = None

        self.ident = bldata.read(4)

        if isGreaterOrEqVersion(ver, 8,2,0,3):
            self.parseHeapToVILinkSaveInfo(bldata)
        else:
            self.parseOffsetLinkSaveInfo(bldata)

        if isGreaterOrEqVersion(ver, 8,0,0,1):
            self.iuseStr = readPStr(bldata, 2, self.po)
        pass

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        raise NotImplementedError("LinkObj {} XML import not fully implemented"\
          .format(self.ident))
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


class LinkObjNonVINonHeapToTypedefLink(LinkObjBase):
    """ NonVINonHeap To Typedef Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjCCSymbolLink(LinkObjBase):
    """ CCSymbol Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapNamedLink(LinkObjBase):
    """ HeapNamed Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjFilePathLink(LinkObjBase):
    """ FilePath Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjRCFilePathLink(LinkObjBase):
    """ RCFilePath Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToFileLink(LinkObjBase):
    """ Heap To File Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToFileNoWarnLink(LinkObjBase):
    """ Heap To FileNoWarn Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToRCFileLink(LinkObjBase):
    """ VI To RCFile Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjIUseToInstantiationVILink(LinkObjBase):
    """ IUse To InstantiationVI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjGenIUseToGenVILink(LinkObjBase):
    """ GenIUse To GenVI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjNodeToEFLink(LinkObjBase):
    """ Node To EF Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToVILink(LinkObjBase):
    """ Heap To VI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjPIUseToPolyLink(LinkObjBase):
    """ PIUse To Poly Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjIUseToProgRetLink(LinkObjBase):
    """ IUse To ProgRet Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjStaticVIRefToVILink(LinkObjBase):
    """ StaticVIRef To VI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjNodeToCINLink(LinkObjBase):
    """ Node To CIN Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjNodeToScriptLink(LinkObjBase):
    """ Node To Script Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjStaticCallByRefToVILink(LinkObjBase):
    """ StaticCallByRef To VI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToRCFileLink(LinkObjBase):
    """ Heap To RCFile Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToVINamedLink(LinkObjBase):
    """ Heap To VINamed Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToLibraryDataLink(LinkObjBase):
    """ Heap To LibraryData Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjMSNToMSLink(LinkObjBase):
    """ MSN To MS Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjMSToMSImplVILink(LinkObjBase):
    """ MS To MSImplVI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjMSCallByRefToMSLink(LinkObjBase):
    """ MSCallByRef To MS Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjMathScriptLink(LinkObjBase):
    """ MathScript Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjFBoxLineToInstantnVILink(LinkObjBase):
    """ FBoxLine To InstantiationVI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjOMHeapToResource(LinkObjBase):
    """ OMHeap To Resource Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjOMVIToResource(LinkObjBase):
    """ OMVI To Resource Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjOMExtResLink(LinkObjBase):
    """ OMExtRes Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjGIToAbstractVI(LinkObjBase):
    """ GI To AbstractVI Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjGIToAbilityVI(LinkObjBase):
    """ GI To AbilityVI Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjXIToPropertyVI(LinkObjBase):
    """ XI To PropertyVI Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjXIToMethodVI(LinkObjBase):
    """ XI To MethodVI Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjGInterfaceLink(LinkObjBase):
    """ GInterface Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjXInterfaceLink(LinkObjBase):
    """ XInterface Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjXCtlInterfaceLink(LinkObjBase):
    """ XCtl Interface Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjXNodeInterfaceLink(LinkObjBase):
    """ XNode Interface Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToContainerItemLink(LinkObjBase):
    """ VI To ContainerItem Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToContainerItemLink(LinkObjBase):
    """ Heap To ContainerItem Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjContainerItemLinkObj(LinkObjBase):
    """ ContainerItem Link Obj
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjXNodeProjectItemLinkObj(LinkObjBase):
    """ XNode ProjectItem Link Obj
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjXNodeToExtFuncLink(LinkObjBase):
    """ XNode To ExtFunc Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjXNodeToVILink(LinkObjBase):
    """ XNode To VI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjActiveXBDToTypeLib(LinkObjBase):
    """ ActiveX BD To TypeLib
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjActiveXTLibLinkObj(LinkObjBase):
    """ ActiveX TLib Link Obj
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjXNodeToXInterface(LinkObjBase):
    """ XNode To XInterface Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjUDClassLibInheritsLink(LinkObjBase):
    """ UDClassLibInherits Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjUDClassLibToVILink(LinkObjBase):
    """ UDClassLib To VI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjUDClassLibToMemberVILink(LinkObjBase):
    """ UDClassLib To MemberVI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjUDClassLibToPrivDataCtlLink(LinkObjBase):
    """ UDClassLib To PrivDataCtl Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToUDClassAPILink(LinkObjBase):
    """ Heap To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjDynInfoToUDClassAPILink(LinkObjBase):
    """ DynInfo To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjPropNodeItemToUDClassAPILink(LinkObjBase):
    """ PropNodeItem To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjCreOrDesRefToUDClassAPILink(LinkObjBase):
    """ CreateOrDestroyRef To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjDDOToUDClassAPILink(LinkObjBase):
    """ DDO To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjAPIToAPILink(LinkObjBase):
    """ API To API Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjAPIToNearestImplVILink(LinkObjBase):
    """ API To NearestImplVI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjAPIToChildAPILink(LinkObjBase):
    """ API To ChildAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToUDClassAPILink(LinkObjBase):
    """ Heap To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjMemberVIItem(LinkObjBase):
    """ MemberVIItem Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjUDClassLibrary(LinkObjBase):
    """ UDClassLibrary Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToXNodeInterface(LinkObjBase):
    """ Heap To XNodeInterface Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToGInterface(LinkObjBase):
    """ Heap To GInterface Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


def newLinkObject(vi, list_ident, ident, po):
    """ Calls proper constructor to create link object.
    """
    if ident in (b'IVOV',):
        ctor = LinkObjInstncVIToNamspcrVI
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
    elif ident in (b'.2TD',):
        ctor = LinkObjNonVINonHeapToTypedefLink
    elif ident in (b'CCLO',):
        ctor = LinkObjCCSymbolLink
    elif ident in (b'HpEx',):
        ctor = LinkObjHeapNamedLink
    elif ident in (b'XFil',):
        ctor = LinkObjFilePathLink
    elif ident in (b'RFil',):
        ctor = LinkObjRCFilePathLink
    elif ident in (b'HpFl',):
        ctor = LinkObjHeapToFileLink
    elif ident in (b'HpFN',):
        ctor = LinkObjHeapToFileNoWarnLink
    elif ident in (b'VIRC',):
        ctor = LinkObjVIToRCFileLink
    elif ident in (b'IUIV',):
        ctor = LinkObjIUseToInstantiationVILink
    elif ident in (b'GUGV',):
        ctor = LinkObjGenIUseToGenVILink
    elif ident in (b'NEXF',):
        ctor = LinkObjNodeToEFLink
    elif ident in (b'HVIR',):
        ctor = LinkObjHeapToVILink
    elif ident in (b'PUPV',):
        ctor = LinkObjPIUseToPolyLink
    elif ident in (b'IUPR',):
        ctor = LinkObjIUseToProgRetLink
    elif ident in (b'SVVI',):
        ctor = LinkObjStaticVIRefToVILink
    elif ident in (b'NCIN',):
        ctor = LinkObjNodeToCINLink
    elif ident in (b'NSCR',):
        ctor = LinkObjNodeToScriptLink
    elif ident in (b'SCVI',):
        ctor = LinkObjStaticCallByRefToVILink
    elif ident in (b'RCFL',):
        ctor = LinkObjHeapToRCFileLink
    elif ident in (b'HpVI',):
        ctor = LinkObjHeapToVINamedLink
    elif ident in (b'H2LD',):
        ctor = LinkObjHeapToLibraryDataLink
    elif ident in (b'MNMS',):
        ctor = LinkObjMSNToMSLink
    elif ident in (b'MSIM',):
        ctor = LinkObjMSToMSImplVILink
    elif ident in (b'CBMS',):
        ctor = LinkObjMSCallByRefToMSLink
    elif ident in (b'MUDF',):
        ctor = LinkObjMathScriptLink
    elif ident in (b'FBIV',):
        ctor = LinkObjFBoxLineToInstantnVILink
    elif ident in (b'OBDR',):
        ctor = LinkObjOMHeapToResource
    elif ident in (b'OVIR',):
        ctor = LinkObjOMVIToResource
    elif ident in (b'OXTR',):
        ctor = LinkObjOMExtResLink
    elif ident in (b'GIVI',):
        ctor = LinkObjGIToAbstractVI
    elif ident in (b'GIAY',):
        ctor = LinkObjGIToAbilityVI
    elif ident in (b'XIPY',):
        ctor = LinkObjXIToPropertyVI
    elif ident in (b'XIMD',):
        ctor = LinkObjXIToMethodVI
    elif ident in (b'LIBR',):
        ctor = LinkObjGInterfaceLink
    elif ident in (b'XINT',):
        ctor = LinkObjXInterfaceLink
    elif ident in (b'LVXC',):
        ctor = LinkObjXCtlInterfaceLink
    elif ident in (b'XNDI',):
        ctor = LinkObjXNodeInterfaceLink
    elif ident in (b'VICI',):
        ctor = LinkObjVIToContainerItemLink
    elif ident in (b'HpCI',):
        ctor = LinkObjHeapToContainerItemLink
    elif ident in (b'CILO',):
        ctor = LinkObjContainerItemLinkObj
    elif ident in (b'XPLO',):
        ctor = LinkObjXNodeProjectItemLinkObj
    elif ident in (b'XNEF',):
        ctor = LinkObjXNodeToExtFuncLink
    elif ident in (b'XNVI',):
        ctor = LinkObjXNodeToVILink
    elif ident in (b'AXDT',):
        ctor = LinkObjActiveXBDToTypeLib
    elif ident in (b'AXTL',):
        ctor = LinkObjActiveXTLibLinkObj
    elif ident in (b'XNXI',):
        ctor = LinkObjXNodeToXInterface
    elif ident in (b'HEIR',):
        ctor = LinkObjUDClassLibInheritsLink
    elif ident in (b'C2vi',):
        ctor = LinkObjUDClassLibToVILink
    elif ident in (b'C2VI',):
        ctor = LinkObjUDClassLibToMemberVILink
    elif ident in (b'C2Pr',):
        ctor = LinkObjUDClassLibToPrivDataCtlLink
    elif ident in (b'HOPI',):
        ctor = LinkObjHeapToUDClassAPILink
    elif ident in (b'DyOM',):
        ctor = LinkObjDynInfoToUDClassAPILink
    elif ident in (b'PNOM',):
        ctor = LinkObjPropNodeItemToUDClassAPILink
    elif ident in (b'DRPI',):
        ctor = LinkObjCreOrDesRefToUDClassAPILink
    elif ident in (b'DOPI',):
        ctor = LinkObjDDOToUDClassAPILink
    elif ident in (b'AP2A',):
        ctor = LinkObjAPIToAPILink
    elif ident in (b'AP2I',):
        ctor = LinkObjAPIToNearestImplVILink
    elif ident in (b'AP2C',):
        ctor = LinkObjAPIToChildAPILink
    elif ident in (b'UDPI',):
        ctor = LinkObjHeapToUDClassAPILink
    elif ident in (b'CMem',):
        ctor = LinkObjMemberVIItem
    elif ident in (b'CLIB',):
        ctor = LinkObjUDClassLibrary
    elif ident in (b'HXNI',):
        ctor = LinkObjHeapToXNodeInterface
    elif ident in (b'GINT',):
        ctor = LinkObjHeapToGInterface
    else:
        raise AttributeError("List {} contains unrecognized class {}".format(list_ident,ident))

    return ctor(vi, list_ident, ident, po)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" LabView RSRC files modder.

Modifies XML version of RSRC files. Checks if XML is correct,
recovers missing or damaged parts.
"""

# Copyright (C) 2019-2020 Mefistotelis <mefistotelis@gmail.com>
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

__version__ = "0.0.1"
__author__ = "Mefistotelis"
__license__ = "MIT"

import sys
import re
import os
import argparse
import enum
from types import SimpleNamespace

import LVparts
from LVparts import PARTID, DSINIT
import LVxml as ET
from LVmisc import eprint

class FUNC_OPTS(enum.IntEnum):
    changed = 0

def representsInt(s):
    """ Checks if given string represents an integer.
    """
    try: 
        int(s)
        return True
    except ValueError:
        return False
    except TypeError:
        return False

def strToList(s):
    """ Parses given string representing a comma separated list in brackets.
    """
    try: 
        list_str = s.strip()
    except AttributeError:
        return None
    if list_str[0] != '(' or list_str[-1] != ')':
        return None
    list_str = list_str[1:-1].split(',')
    # We only need lists of integers
    for i in range(len(list_str)): 
        list_str[i] = int(list_str[i].strip(), 0)
    return list_str

def representsList(s):
    """ Checks if given string represents a comma separated list in brackets.
    """
    return strToList(s) is not None

def attribValToStr(val):
    if isinstance(val, str):
        strVal = val
    else:
        strVal = "{}".format(val)
    return strVal

def attribValFromStr(strVal, typeExample):
    if isinstance(typeExample, int):
        val = int(strVal, 0)
    else:
        val = strVal
    return val

def tagValToStr(val):
    if isinstance(val, str):
        strVal = val
    elif isinstance(val, (list, tuple)):
        strVal = '(' + ', '.join([str(x) for x in val]) + ')'
    else:
        strVal = "{}".format(val)
    return strVal

def boundsOverlap(rect1, rect2):
    """ Checks whether two rectangles overlap.

    Rectangles are defined as (x1,y1,x2,y2,).
    """
    if rect1[0] > rect2[2] or rect1[2] < rect2[0]:
        return False # Outside in vertical axis
    if rect1[1] > rect2[3] or rect1[3] < rect2[1]:
        return False # Outside in horizonal axis
    return True

def elemFindOrCreate(parentElem, elemName, fo, po, pos=-1):
    elem = parentElem.find(elemName)
    if elem is None:
        if pos == -1:
            elem = ET.SubElement(parentElem, elemName)
        else:
            elem = ET.Element(elemName)
            parentElem.insert(pos,elem)
        fo[FUNC_OPTS.changed] = True
    return elem

def attribGetOrSetDefault(elem, attrName, defVal, fo, po):
    """ Retrieves attribute value, setting default if not exist or wrong type.

    If the defVal type is integer, returned attibute is also converted to integer.
    """
    strVal = elem.get(attrName)
    if isinstance(defVal, int) and not representsInt(strVal):
        strVal = None
    if strVal is None:
        if defVal is not None:
            strVal = attribValToStr(defVal)
            elem.set(attrName, strVal)
        else:
            strVal = None
            elem.attrib.pop(attrName, None) # remove attrib, no exception if doesn't exist
        fo[FUNC_OPTS.changed] = True
    attrVal = attribValFromStr(strVal, defVal)
    return attrVal

def elemTextSetValue(elem, val, fo, po):
    """ Sets given value as content of the element.

    Returns string representation of the value set.
    """
    if val is not None:
        strVal = tagValToStr(val)
    else:
        strVal = None
    if elem.text != strVal:
        elem.text = strVal
        fo[FUNC_OPTS.changed] = True
    return strVal

def elemTextGetOrSetDefault(elem, defVal, fo, po):
    """ Retrieves value of element text, setting default if not exist or wrong type.

    If the defVal type is integer or list, returned attibute is also converted to that type.
    """
    attrVal = elem.text
    if isinstance(defVal, int):
         if not representsInt(attrVal):
            attrVal = None
    elif isinstance(defVal, (list, tuple)):
         if not representsList(attrVal):
            attrVal = None
    if attrVal is None:
        attrVal = elemTextSetValue(elem, defVal, fo, po)
    if isinstance(defVal, int):
        attrVal = int(attrVal, 0)
    return attrVal

def elemFindOrCreateWithAttribsAndTags(parentElem, elemName, attrs, tags, fo, po, parentPos=None):
    elem = None
    xpathAttrs = "".join([ "[@{}='{}']".format(attr[0],attribValToStr(attr[1])) for attr in attrs ] )
    if parentPos is not None:
        xpathAttrs += "["+str(parentPos)+"]"
    #elem_list = filter(lambda x: attrVal in x.get(attrName), parentElem.findall(".//{}[@{}='{}']".format(elemName,attrName)))
    elem_list = parentElem.findall(".//{}{}".format(elemName,xpathAttrs))
    for chk_elem in elem_list:
        matchFail = False
        for tag in tags:
            sub_elem = chk_elem.find(tag[0])
            if tag[1] is None:
                if sub_elem is not None and sub_elem.text is not None and sub_elem.text.strip() != '':
                    matchFail = True
            elif sub_elem is not None and sub_elem.text != tagValToStr(tag[1]):
                matchFail = True
            if matchFail:
                break
        if matchFail:
            continue
        elem = chk_elem
        break
    createdNew = False
    if elem is None:
        elem = ET.SubElement(parentElem, elemName)
        fo[FUNC_OPTS.changed] = True
        createdNew = True
    if (po.verbose > 1):
        print("{:s}: {} \"{}/{}\", attribs: {} sub-tags: {}".format(po.xml, "Creating new" if createdNew else "Reusing existing",parentElem.tag,elemName,attrs,tags))
    for attr in attrs:
        attrName = attr[0]
        attrVal = attr[1]
        attribGetOrSetDefault(elem, attrName, attrVal, fo, po)
    for tag in tags:
        if tag[1] is not None:
            sub_elem = elemFindOrCreate(elem, tag[0], fo, po)
            elemTextGetOrSetDefault(sub_elem, tag[1], fo, po)
        else:
            sub_elem = elem.find(tag[0])
            if sub_elem is not None:
                elem.remove(sub_elem)
    return elem

def getDFDSRecord(RSRC, typeID, po):
    """ Returns DFDS entry for given typeID.
    """
    DS_entry = RSRC.find("./DFDS/Section/DataFill[@TypeID='{}']".format(typeID))
    if DS_entry is None:
        return None
    return DS_entry

def getDSInitRecord(RSRC, po):
    """ Returns DSInit, which is a record of 51 integers of initialized data.

    Returns Element containing the values sub-tree.
    """
    DFDS = RSRC.find('./DFDS/Section')
    if DFDS is None:
        return None
    # Usually what we need will just be the first DFDS item. And even if not,
    # it's always first item with 51 ints inside. So instead of going though
    # type map and VCTP, we can localise the proper type directly.
    DSI_candidates = []
    DSI_candidates.extend( DFDS.findall('./DataFill/RepeatedBlock/I32/../..') )
    DSI_candidates.extend( DFDS.findall('./DataFill/Cluster/RepeatedBlock/I32/../../..') )
    for DSInit in DSI_candidates:
        NonCommentFields = list(filter(lambda f: f.tag is not ET.Comment, DSInit.findall(".//RepeatedBlock[1]/*")))
        # The element needs to have exactly 51 sub-elements, all Int32
        if len(NonCommentFields) == 51 and len(DSInit.findall('.//RepeatedBlock[1]/I32')) == 51:
            return DSInit
    # No matching type in DFDS
    return None

def getDSInitEntry(RSRC, entryId, po, DSInit=None):
    """ Returns DSInit entry value.
    """
    if DSInit is None:
        DSInit = getDSInitRecord(RSRC, po)
    if DSInit is None:
        return None
    entry_elem = DSInit.find("./RepeatedBlock[1]/I32["+str(int(entryId+1))+"]")
    if entry_elem is None:
        entry_elem = DSInit.find("./Cluster[1]/RepeatedBlock[1]/I32["+str(int(entryId+1))+"]")
    if entry_elem is None:
        return None
    return int(entry_elem.text,0)

def getFpDCOTable(RSRC, po, TM80_IndexShift=None, FpDCOTable_TypeID=None):
    """ Returns DCO Table from DataSpace.
    """
    if FpDCOTable_TypeID is None:
        if TM80_IndexShift is None:
            TM80 = RSRC.find("./TM80/Section")
            if TM80 is not None:
                TM80_IndexShift = TM80.get("IndexShift")
                if TM80_IndexShift is not None:
                    TM80_IndexShift = int(TM80_IndexShift, 0)
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.fpdcoTableTMI, po)
            if val_TMI is not None:
                FpDCOTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
    if FpDCOTable_TypeID is None:
        return None
    FpDCOTable = getDFDSRecord(RSRC, FpDCOTable_TypeID, po)
    return FpDCOTable

def getFpDCOTableAsList(RSRC, po, TM80_IndexShift=None, FpDCOTable_TypeID=None):
    """ Returns DCO Table from DataSpace, as list of Structs.
    """
    FpDCOTable = getFpDCOTable(RSRC, po, TM80_IndexShift=TM80_IndexShift, FpDCOTable_TypeID=FpDCOTable_TypeID)
    FpDCOList = []
    if FpDCOTable is None:
        return FpDCOList
    for FpDCO in FpDCOTable.findall("./RepeatedBlock/Cluster"):
        DCO = dict()
        FpDCO_FieldList = list(filter(lambda f: f.tag is not ET.Comment, FpDCO.findall("./*")))
        for idx,field in enumerate(LVparts.DCO._fields_):
            fldName = field[0]
            fldType = field[1]
            fldVal = FpDCO_FieldList[idx].text
            if re.match(r"^c_u?int[0-9]+(_[lb]e)?$", fldType.__name__) or \
               re.match(r"^c_u?byte$", fldType.__name__) or \
               re.match(r"^c_u?short(_[lb]e)?$", fldType.__name__) or \
               re.match(r"^c_u?long(_[lb]e)?$", fldType.__name__):
                fldVal = int(fldVal,0)
            elif fldType in ("c_float","c_double","c_longdouble",):
                fldVal = float(fldVal)
            elif re.match(r"^c_u?byte_Array_[0-9]+$", fldType.__name__):
                fldVal = bytes.fromhex(fldVal)
            DCO[fldName] = fldVal
        FpDCOList.append(DCO)
    return FpDCOList

def getFpDCOEntry(RSRC, dcoIndex, po, TM80_IndexShift=None, FpDCOTable_TypeID=None):
    """ Returns DCO entry from DataSpace.
    """
    FpDCOTable = getFpDCOTable(RSRC, po, TM80_IndexShift=TM80_IndexShift, FpDCOTable_TypeID=FpDCOTable_TypeID)
    if FpDCOTable is None:
        return None
    FpDCO = FpDCOTable.find("./RepeatedBlock/Cluster["+str(dcoIndex)+"]")
    return FpDCO

def getProbeTable(RSRC, po, TM80_IndexShift=None, ProbeTable_TypeID=None):
    """ Returns Probe Table from DataSpace.
    """
    if ProbeTable_TypeID is None:
        if TM80_IndexShift is None:
            TM80 = RSRC.find("./TM80/Section")
            if TM80 is not None:
                TM80_IndexShift = TM80.get("IndexShift")
                if TM80_IndexShift is not None:
                    TM80_IndexShift = int(TM80_IndexShift, 0)
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.probeTableTMI, po)
            if val_TMI is not None:
                ProbeTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
    if ProbeTable_TypeID is None:
        return None
    ProbeTable = getDFDSRecord(RSRC, ProbeTable_TypeID, po)
    return ProbeTable

def vers_Fix(RSRC, vers, ver, fo, po):
    sect_index = vers.get("Index")
    if sect_index is not None:
        sect_index = int(sect_index, 0)
    if sect_index not in (4,7,8,9,10,):
        sect_index = 4
        vers.set("Index","{}".format(sect_index))
        fo[FUNC_OPTS.changed] = True
    if vers.find("Version") is None:
        nver = ET.SubElement(vers, "Version")
        for attr_name in ("Major", "Minor", "Bugfix", "Stage", "Build", "Flags",):
            nver.set(attr_name, ver.get(attr_name))
        nver.set("Text", "")
        nver.set("Info", "{}.{}".format(ver.get("Major"), ver.get("Minor")))
        fo[FUNC_OPTS.changed] = True
    return fo[FUNC_OPTS.changed]

def elemCheckOrCreate_partList_arrayElement(parent, fo, po, aeClass="cosm", \
      aePartID=1, aeObjFlags=None, aeMasterPart=None, aeHowGrow=None, aeBounds=None, \
      aeImageResID=None, aeFgColor=None, aeBgColor=None):

    searchTags = []
    searchTags.append( ("partID", int(aePartID),) )
    if aeMasterPart is not None:
        searchTags.append( ("masterPart", int(aeMasterPart),) )
    else:
        searchTags.append( ("masterPart", None,) )
    arrayElement = elemFindOrCreateWithAttribsAndTags(parent, "SL__arrayElement", \
      ( ("class", aeClass,), ), searchTags, fo, po)
    attribGetOrSetDefault(arrayElement, "class", aeClass, fo, po)
    attribGetOrSetDefault(arrayElement, "uid", 1, fo, po)

    if aeObjFlags is not None:
        objFlags = elemFindOrCreate(arrayElement, "objFlags", fo, po, pos=0)
        elemTextGetOrSetDefault(objFlags, aeObjFlags, fo, po)

    partID = elemFindOrCreate(arrayElement, "partID", fo, po)
    elemTextGetOrSetDefault(partID, int(aePartID), fo, po)

    if aeMasterPart is not None:
        masterPart = elemFindOrCreate(arrayElement, "masterPart", fo, po)
        elemTextGetOrSetDefault(masterPart, aeMasterPart, fo, po)

    if aeHowGrow is not None:
        howGrow = elemFindOrCreate(arrayElement, "howGrow", fo, po)
        elemTextGetOrSetDefault(howGrow, aeHowGrow, fo, po)

    if aeBounds is not None:
        bounds = elemFindOrCreate(arrayElement, "bounds", fo, po)
        elemTextGetOrSetDefault(bounds, aeBounds, fo, po)

    if aeImageResID is not None:
        image = elemFindOrCreate(arrayElement, "image", fo, po)
        attribGetOrSetDefault(image, "class", "Image", fo, po)
        ImageResID = elemFindOrCreate(image, "ImageResID", fo, po)
        elemTextGetOrSetDefault(ImageResID, aeImageResID, fo, po)

    if aeFgColor is not None:
        fgColor = elemFindOrCreate(arrayElement, "fgColor", fo, po)
        elemTextGetOrSetDefault(fgColor, "{:08X}".format(aeFgColor), fo, po)

    if aeBgColor is not None:
        bgColor = elemFindOrCreate(arrayElement, "bgColor", fo, po)
        elemTextGetOrSetDefault(bgColor, "{:08X}".format(aeBgColor), fo, po)

    return arrayElement

def elemCheckOrCreate_table_arrayElement(parent, fo, po, aeClass="SubCosm", \
      aeObjFlags=None, aeBounds=None, \
      aeImageResID=None, aeFgColor=None, aeBgColor=None, parentPos=None):

    searchTags = []
    arrayElement = elemFindOrCreateWithAttribsAndTags(parent, "SL__arrayElement", \
      ( ("class", aeClass,), ), searchTags, fo, po, parentPos=parentPos)
    attribGetOrSetDefault(arrayElement, "class", aeClass, fo, po)

    if aeObjFlags is not None:
        objFlags = elemFindOrCreate(arrayElement, "objFlags", fo, po, pos=0)
        elemTextGetOrSetDefault(objFlags, aeObjFlags, fo, po)

    if aeBounds is not None:
        bounds = elemFindOrCreate(arrayElement, "Bounds", fo, po)
        elemTextGetOrSetDefault(bounds, aeBounds, fo, po)

    if aeFgColor is not None:
        fgColor = elemFindOrCreate(arrayElement, "FGColor", fo, po)
        elemTextGetOrSetDefault(fgColor, "{:08X}".format(aeFgColor), fo, po)

    if aeBgColor is not None:
        bgColor = elemFindOrCreate(arrayElement, "BGColor", fo, po)
        elemTextGetOrSetDefault(bgColor, "{:08X}".format(aeBgColor), fo, po)

    if aeImageResID is not None:
        image = elemFindOrCreate(arrayElement, "Image", fo, po)
        attribGetOrSetDefault(image, "class", "Image", fo, po)
        ImageResID = elemFindOrCreate(image, "ImageResID", fo, po)
        elemTextGetOrSetDefault(ImageResID, aeImageResID, fo, po)

    return arrayElement

def elemCheckOrCreate_table_arrayElementImg(parent, fo, po, aeClass="Image", \
      aeImageResID=None, parentPos=None):

    searchTags = []
    arrayElement = elemFindOrCreateWithAttribsAndTags(parent, "SL__arrayElement", \
      ( ("class", aeClass,), ), searchTags, fo, po, parentPos=parentPos)
    attribGetOrSetDefault(arrayElement, "class", aeClass, fo, po)

    if aeImageResID is not None:
        ImageResID = elemFindOrCreate(arrayElement, "ImageResID", fo, po)
        elemTextGetOrSetDefault(ImageResID, aeImageResID, fo, po)

    return arrayElement

def getConsolidatedTopType(RSRC, typeID, po):
    VCTP = RSRC.find("./VCTP/Section")
    if VCTP is None:
        return None
    VCTP_TopTypeDesc = VCTP.find("./TopLevel/TypeDesc[@Index='{}']".format(typeID))
    if VCTP_TopTypeDesc is None:
        return None
    VCTP_FlatTypeID = VCTP_TopTypeDesc.get("FlatTypeID")
    if VCTP_FlatTypeID is None:
        return None
    VCTP_FlatTypeID = int(VCTP_FlatTypeID, 0)
    VCTP_FlatTypeDesc = VCTP.find("./TypeDesc["+str(VCTP_FlatTypeID+1)+"]")
    return VCTP_FlatTypeDesc

def getConsolidatedFlatType(RSRC, flatTypeID, po):
    VCTP = RSRC.find("./VCTP/Section")
    if VCTP is None:
        return None
    VCTP_FlatTypeDesc = VCTP.find("./TypeDesc["+str(flatTypeID+1)+"]")
    return VCTP_FlatTypeDesc

def valueOfTypeToXML(valueType, val, po):
    """ Returns dict of values for its XML representation of given type

    Returns dict with tag:value pairs, text property of the base element is under "tagText" key.
    """
    if valueType in ("Boolean", "BooleanU16",):
        valDict = { "tagText" : str(val) }
    elif valueType in ("NumInt8", "NumInt16", "NumInt32", "NumInt64",):
        valDict = { "tagText" : str(val) }
    elif valueType in ("NumUInt8", "NumUInt16", "NumUInt32", "NumUInt64",\
      "UnitUInt8", "UnitUInt16", "UnitUInt32",):
        valDict = { "tagText" : str(val) }
    elif valueType in ("NumFloat32", "NumFloat64", "NumFloatExt",\
      "UnitFloat32", "UnitFloat64", "UnitFloatExt"):
        valDict = { "tagText" : str(val) }
    elif valueType in ("NumComplex64", "NumComplex128", "NumComplexExt",\
      "UnitComplex64", "UnitComplex128", "UnitComplexExt",):
        valDict = { "real" : str(val[0]), "imaginary" : str(val[1]) }
    else:
        valDict = { "tagText" : str(val) }
    return valDict

def valueTypeGetDefaultRange(valueType, po):
    if valueType in ("Boolean", "BooleanU16",):
        stdMin = 0
        stdMax = 1
        stdInc = 1
    elif valueType == "NumInt8":
        stdMin = -128
        stdMax = 127
        stdInc = 1
    elif valueType == "NumInt16":
        stdMin = -32768
        stdMax = 32767
        stdInc = 1
    elif valueType == "NumInt32":
        stdMin = -2147483648
        stdMax = 2147483647
        stdInc = 1
    elif valueType == "NumInt64":
        stdMin = -9223372036854775808
        stdMax = 9223372036854775807
        stdInc = 1
    elif valueType == "NumUInt8":
        stdMin = 0
        stdMax = 255
        stdInc = 1
    elif valueType == "NumUInt16":
        stdMin = 0
        stdMax = 65535
        stdInc = 1
    elif valueType == "NumUInt32":
        stdMin = 0
        stdMax = 4294967295
        stdInc = 1
    elif valueType == "NumUInt64":
        stdMin = 0
        stdMax = 18446744073709551615
        stdInc = 1
    elif valueType == "NumFloat32":
        stdMin = -3.402823466E+38
        stdMax = 3.402823466E+38
        stdInc = 0.1
    elif valueType == "NumFloat64":
        stdMin = -1.7976931348623158E+308
        stdMax = 1.7976931348623158E+308
        stdInc = 0.1
    elif valueType == "NumFloatExt":
        stdMin = None
        stdMax = None
        stdInc = 0.1
    elif valueType == "NumComplex64":
        stdMin = (-3.402823466E+38, -3.402823466E+38,)
        stdMax = (3.402823466E+38, 3.402823466E+38,)
        stdInc = (0.1, 0.1,)
    elif valueType == "NumComplex128":
        stdMin = (-1.7976931348623158E+308, -1.7976931348623158E+308)
        stdMax = (1.7976931348623158E+308, 1.7976931348623158E+308)
        stdInc = (0.1, 0.1,)
    elif valueType == "NumComplexExt":
        stdMin = None
        stdMax = None
        stdInc = (0.1, 0.1,)
    #elif valueType == "UnitUInt8":
    #elif valueType == "UnitUInt16":
    #elif valueType == "UnitUInt32":
    #elif valueType == "UnitFloat32":
    #elif valueType == "UnitFloat64":
    #elif valueType == "UnitFloatExt":
    #elif valueType == "UnitComplex64":
    #elif valueType == "UnitComplex128":
    #elif valueType == "UnitComplexExt":
    else:
        stdMin = None
        stdMax = None
        stdInc = None
    return stdMin, stdMax, stdInc

def elemCheckOrCreate_ddo_content(ddo, fo, po, aeDdoObjFlags=None, aeBounds=None, \
          aeDdoTypeID=None, aeMouseWheelSupport=None, aeMinButSize=None, \
          valueType="Boolean", aeStdNumMin=None, aeStdNumMax=None, aeStdNumInc=None, \
          aeSavedSize=None):
    """ Fils content of pre-created DDO tag
    """

    if aeDdoObjFlags is not None:
        ddo_objFlags = elemFindOrCreate(ddo, "objFlags", fo, po, pos=0)
        elemTextGetOrSetDefault(ddo_objFlags, aeDdoObjFlags, fo, po)

    if aeBounds is not None:
        ddo_bounds = elemFindOrCreate(ddo, "bounds", fo, po)
        elemTextGetOrSetDefault(ddo_bounds, aeBounds, fo, po)

    partsList = None
    if aeDdoTypeID is not None: # Only root element has no type and no parts list
        partsList = elemFindOrCreate(ddo, "partsList", fo, po)
        attribGetOrSetDefault(partsList, "elements", 0, fo, po)

        ddo_TypeDesc = elemFindOrCreate(ddo, "typeDesc", fo, po)
        elemTextGetOrSetDefault(ddo_TypeDesc, "TypeID({})".format(aeDdoTypeID), fo, po)

    if aeMouseWheelSupport is not None:
        ddo_MouseWheelSupport = elemFindOrCreate(ddo, "MouseWheelSupport", fo, po)
        elemTextGetOrSetDefault(ddo_MouseWheelSupport, aeMouseWheelSupport, fo, po)

    if aeMinButSize is not None:
        ddo_MinButSize = elemFindOrCreate(ddo, "MinButSize", fo, po)
        elemTextGetOrSetDefault(ddo_MinButSize, aeMinButSize, fo, po)

    if aeStdNumMin is not None:
        ddo_StdNumMin = elemFindOrCreate(ddo, "StdNumMin", fo, po)
        aeStdNumMin_dict = valueOfTypeToXML(valueType, aeStdNumMin, po)
        for tagName, tagValue in aeStdNumMin_dict.items():
            if tagName == "tagText":
                elemTextGetOrSetDefault(ddo_StdNumMin, tagValue, fo, po)
                continue
            tmp_subtag = elemFindOrCreate(ddo_StdNumMin, tagName, fo, po)
            elemTextGetOrSetDefault(tmp_subtag, tagValue, fo, po)

    if aeStdNumMax is not None:
        ddo_StdNumMax = elemFindOrCreate(ddo, "StdNumMax", fo, po)
        aeStdNumMax_dict = valueOfTypeToXML(valueType, aeStdNumMax, po)
        for tagName, tagValue in aeStdNumMax_dict.items():
            if tagName == "tagText":
                elemTextGetOrSetDefault(ddo_StdNumMax, tagValue, fo, po)
                continue
            tmp_subtag = elemFindOrCreate(ddo_StdNumMax, tagName, fo, po)
            elemTextGetOrSetDefault(tmp_subtag, tagValue, fo, po)

    if aeStdNumInc is not None:
        ddo_StdNumInc = elemFindOrCreate(ddo, "StdNumInc", fo, po)
        aeStdNumInc_dict = valueOfTypeToXML(valueType, aeStdNumInc, po)
        for tagName, tagValue in aeStdNumInc_dict.items():
            if tagName == "tagText":
                elemTextGetOrSetDefault(ddo_StdNumInc, tagValue, fo, po)
                continue
            tmp_subtag = elemFindOrCreate(ddo_StdNumInc, tagName, fo, po)
            elemTextGetOrSetDefault(tmp_subtag, tagValue, fo, po)

    paneHierarchy = None
    if valueType == "Cluster": # Some types have sub-lists of objects
        ddo_ddoList = elemFindOrCreate(ddo, "ddoList", fo, po)
        attribGetOrSetDefault(ddo_ddoList, "elements", 0, fo, po)

        paneHierarchy = elemFindOrCreate(ddo, "paneHierarchy", fo, po)
        attribGetOrSetDefault(paneHierarchy, "class", "pane", fo, po)
        attribGetOrSetDefault(paneHierarchy, "uid", 1, fo, po)

    if aeSavedSize is not None:
        ddo_savedSize = elemFindOrCreate(ddo, "savedSize", fo, po)
        elemTextGetOrSetDefault(ddo_savedSize, aeSavedSize, fo, po)

    return partsList, paneHierarchy

def elemCheckOrCreate_zPlaneList_arrayElement(parent, fo, po, aeClass="fPDCO", \
          aeTypeID=1, aeObjFlags=None, aeDdoClass="stdBool", aeConNum=None, \
          aeTermListLength=None):

    searchTags = []
    searchTags.append( ("typeDesc", "TypeID({})".format(aeTypeID),) )
    arrayElement = elemFindOrCreateWithAttribsAndTags(parent, "SL__arrayElement", \
      ( ("class", aeClass,), ), searchTags, fo, po)
    attribGetOrSetDefault(arrayElement, "class", aeClass, fo, po)
    attribGetOrSetDefault(arrayElement, "uid", 1, fo, po)

    if aeObjFlags is not None:
        objFlags = elemFindOrCreate(arrayElement, "objFlags", fo, po, pos=0)
        elemTextGetOrSetDefault(objFlags, aeObjFlags, fo, po)

    typeDesc = elemFindOrCreate(arrayElement, "typeDesc", fo, po)
    elemTextGetOrSetDefault(typeDesc, "TypeID({})".format(aeTypeID), fo, po)

    ddo = elemFindOrCreate(arrayElement, "ddo", fo, po)
    attribGetOrSetDefault(ddo, "class", aeDdoClass, fo, po)
    attribGetOrSetDefault(ddo, "uid", 1, fo, po)

    # Not having a "conNum" set seem to actually mean it's equal to 0, which
    # means it is set. The value with the meaning of 'unset' is -1.
    if aeConNum is not None:
        conNum = elemFindOrCreate(arrayElement, "conNum", fo, po)
        elemTextGetOrSetDefault(conNum, aeConNum, fo, po)

    if aeTermListLength is not None:
        termListLength = elemFindOrCreate(arrayElement, "termListLength", fo, po)
        elemTextGetOrSetDefault(termListLength, aeTermListLength, fo, po)

    # Now content of 'arrayElement/ddo'
    return arrayElement, ddo

def getConnectorPortsCount(RSRC, ver, fo, po):
    """ Returns amount of connector ports the RSRC uses.
    """
    # Get the value from connectors TypeDesc
    VCTP = RSRC.find("./VCTP/Section")
    if VCTP is not None:
        TypeDesc = None
        CONP_TypeDesc = RSRC.find("./CONP/Section/TypeDesc")
        if CONP_TypeDesc is not None:
            CONP_TypeID = CONP_TypeDesc.get("TypeID")
            if CONP_TypeID is not None:
                CONP_TypeID = int(CONP_TypeID, 0)
            if CONP_TypeID is not None:
                TypeDesc = getConsolidatedTopType(RSRC, CONP_TypeID, po)
            if TypeDesc.get("Type") != "Function":
                # In .ctl files, this can reference TypeDef instead of Function
                eprint("{:s}: CONP references incorrect TD entry".format(po.xml))
                TypeDesc = None
        #TODO We could also detect the type with connectors by finding "Function" TDs, without CONP
        if TypeDesc is not None:
            count = len(TypeDesc.findall("./TypeDesc"))
        if count is not None:
            if count >= 1 and count <= 28:
                if (po.verbose > 1):
                    print("{:s}: Getting connector ports count for \"conPane/cons\" from VCTP Function entries".format(po.xml))
            else:
                    count = None
    # If failed, get the value from DSInit
    if count is None:
        count = getDSInitEntry(RSRC, DSINIT.nConnections, po)
        if count is not None:
            if count >= 1 and count <= 28:
                if (po.verbose > 1):
                    print("{:s}: Getting connector ports count for \"conPane/cons\" from DSInit Record".format(po.xml))
            else:
                    count = None
    return count

def getConnectorPortsFixedCount(RSRC, ver, fo, po):
    """ Returns amount of connector ports the RSRC uses.

    If the value is invalid, fixes it.
    """
    count = getConnectorPortsCount(RSRC, ver, fo, po)
    if count is not None:
        # Terminal patterns nly allow specific amounts of connectors
        if count > 12 and count < 16: count = 16
        if count > 16 and count < 20: count = 20
        if count > 20 and count < 28: count = 28
        if count >= 1 and count <= 28:
            return count
    return 12 # A default value if no real one found (4815 is the most popular pattern)

def recountHeapElements(RSRC, Heap, ver, fo, po):
    """ Updates 'elements' attributes in the Heap tree
    """
    elems = Heap.findall(".//*[@elements]")
    # The 'cons' tag does not store amount of elements inside, or rather - trivial entries are skipped
    cons_elem = Heap.find(".//conPane/cons")
    if cons_elem is not None:
        count = None
        if cons_elem in elems: elems.remove(cons_elem)
        count = getConnectorPortsFixedCount(RSRC, ver, fo, po)
        count_str = str(count)
        if (cons_elem.get("elements") != count_str):
            cons_elem.set("elements", count_str)
    # For the rest = count the elements
    for elem in elems:
        count = len(elem.findall("SL__arrayElement"))
        count_str = str(count)
        if elem.get("elements") != count_str:
            elem.set("elements", count_str)
            fo[FUNC_OPTS.changed] = True
    return fo[FUNC_OPTS.changed]

def checkOrCreateParts_Pane(RSRC, partsList, parentObjFlags, labelText, fo, po):
    """ Checks content of the 'root/paneHierarchy/partsList' element
    """
    # NAME_LABEL properties taken from empty VI file created in LV14
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1511754, aeMasterPart=PARTID.CONTENT_AREA, aeHowGrow=5,
      aeBounds=[0,0,15,27], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 1028, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\""+labelText+"\"", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "bgColor", fo, po), "{:08X}".format(0x01000000), fo, po)

    # Y_SCROLLBAR properties taken from empty VI file created in LV14
    objFlags = 0x0d72
    if (parentObjFlags & 0x0008) == 0x0008: # if vert scrollbar marked as disabled
        objFlags |= 0x1008
    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.Y_SCROLLBAR, aeObjFlags=objFlags, aeMasterPart=PARTID.CONTENT_AREA, aeHowGrow=194, \
      aeBounds=[0,1077,619,1093], aeImageResID=0, aeBgColor=0x00B3B3B3)

    # X_SCROLLBAR properties taken from empty VI file created in LV14
    objFlags = 0x1d73
    if (parentObjFlags & 0x0004) == 0x0004: # if horiz scrollbar marked as disabled
        objFlags |= 0x1008
    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.X_SCROLLBAR, aeObjFlags=objFlags, aeMasterPart=PARTID.CONTENT_AREA, aeHowGrow=56, \
      aeBounds=[619,0,635,1077], aeImageResID=0, aeBgColor=0x00B3B3B3)

    # EXTRA_FRAME_PART properties taken from empty VI file created in LV14
    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.EXTRA_FRAME_PART, aeObjFlags=7543, aeMasterPart=PARTID.CONTENT_AREA, aeHowGrow=10,
      aeBounds=[619,1077,635,1093], aeImageResID=-365, aeFgColor=0x00B3B3B3, aeBgColor=0x00B3B3B3)

    # CONTENT_AREA properties taken from empty VI file created in LV14
    contentArea = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.CONTENT_AREA, aeObjFlags=4211, aeMasterPart=None, aeHowGrow=120, \
      aeBounds=[0,0,619,1077], aeImageResID=-704, aeFgColor=0x00E2E2E2, aeBgColor=0x00E2E2E2)

    # ANNEX properties taken from empty VI file created in LV14
    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="annex", \
      aePartID=PARTID.ANNEX)

    return contentArea

def checkOrCreateParts_MultiCosm(RSRC, partsList, parentObjFlags, fo, po):
    """ Checks content of partsList sub-element of bigMultiCosm type
    """
    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="SubCosm", \
      aePartID=None, aeObjFlags=None, aeMasterPart=None, aeHowGrow=None, \
      aeBounds=[0,0,17,17], aeImageResID=-404, aeFgColor=0x001E4B00, aeBgColor=0x001E4B00)

    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="SubCosm", \
      aePartID=None, aeObjFlags=None, aeMasterPart=None, aeHowGrow=None, \
      aeBounds=[0,0,17,17], aeImageResID=-404, aeFgColor=0x001E4B00, aeBgColor=0x001E4B00)

    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="SubCosm", \
      aePartID=None, aeObjFlags=None, aeMasterPart=None, aeHowGrow=None, \
      aeBounds=[0,0,17,17], aeImageResID=-404, aeFgColor=0x001E4B00, aeBgColor=0x001E4B00)

    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="SubCosm", \
      aePartID=None, aeObjFlags=None, aeMasterPart=None, aeHowGrow=None, \
      aeBounds=[0,0,17,17], aeImageResID=-404, aeFgColor=0x001E4B00, aeBgColor=0x001E4B00)


def checkOrCreateParts_stdBool_control(RSRC, partsList, parentObjFlags, labelText, fo, po):
    """ Checks content of partsList element of Boolean Control type
    """
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1507655, aeMasterPart=PARTID.BOOLEAN_BUTTON, aeHowGrow=4096,
      aeBounds=[0,5,15,46], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 17412, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\""+labelText+"\"", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "bgColor", fo, po), "{:08X}".format(0x01000000), fo, po)

    boolLight = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.BOOLEAN_LIGHT, aeObjFlags=2354, aeMasterPart=PARTID.BOOLEAN_BUTTON, aeHowGrow=3840, \
      aeBounds=[27,35,38,50], aeImageResID=None, aeFgColor=0x001E4B00, aeBgColor=0x001E4B00)
    boolLight_table = elemFindOrCreate(boolLight, "table", fo, po)
    attribGetOrSetDefault(boolLight_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElement(boolLight_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,11,15], aeImageResID=-406, aeFgColor=0x001E4B00, aeBgColor=0x001E4B00, parentPos=1)
    elemCheckOrCreate_table_arrayElement(boolLight_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,11,15], aeImageResID=-406, aeFgColor=0x0064FF00, aeBgColor=0x0064FF00, parentPos=2)
    elemCheckOrCreate_table_arrayElement(boolLight_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,11,15], aeImageResID=-406, aeFgColor=0x001E4B00, aeBgColor=0x001E4B00, parentPos=3)
    elemCheckOrCreate_table_arrayElement(boolLight_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,11,15], aeImageResID=-406, aeFgColor=0x0064FF00, aeBgColor=0x0064FF00, parentPos=4)

    boolButton = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.BOOLEAN_BUTTON, aeObjFlags=2326, aeMasterPart=None, aeHowGrow=240, \
      aeBounds=[22,5,43,55], aeImageResID=None, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC)
    boolButton_table = elemFindOrCreate(boolButton, "table", fo, po)
    attribGetOrSetDefault(boolButton_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElement(boolButton_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,21,50], aeImageResID=-407, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC, parentPos=1)
    elemCheckOrCreate_table_arrayElement(boolButton_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,21,50], aeImageResID=-407, aeFgColor=0x00969696, aeBgColor=0x00969696, parentPos=2)
    elemCheckOrCreate_table_arrayElement(boolButton_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,21,50], aeImageResID=-407, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC, parentPos=3)
    elemCheckOrCreate_table_arrayElement(boolButton_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,21,50], aeImageResID=-407, aeFgColor=0x00969696, aeBgColor=0x00969696, parentPos=4)

    boolGlyph = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.BOOLEAN_SHADOW, aeObjFlags=2359, aeMasterPart=PARTID.BOOLEAN_BUTTON, aeHowGrow=3840, \
      aeBounds=[22,5,48,60], aeImageResID=None, aeFgColor=0x00B3B3B3, aeBgColor=0x00B3B3B3)
    boolGlyph_table = elemFindOrCreate(boolGlyph, "table", fo, po)
    attribGetOrSetDefault(boolGlyph_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElement(boolGlyph_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,26,55], aeImageResID=-444, aeFgColor=0x00B3B3B3, aeBgColor=0x00B3B3B3, parentPos=1)
    elemCheckOrCreate_table_arrayElement(boolGlyph_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,26,55], aeImageResID=0, aeFgColor=0x00B3B3B3, aeBgColor=0x00B3B3B3, parentPos=2)
    elemCheckOrCreate_table_arrayElement(boolGlyph_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,26,55], aeImageResID=-444, aeFgColor=0x00B3B3B3, aeBgColor=0x00B3B3B3, parentPos=3)
    elemCheckOrCreate_table_arrayElement(boolGlyph_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,26,55], aeImageResID=0, aeFgColor=0x00B3B3B3, aeBgColor=0x00B3B3B3, parentPos=4)

    boolDivot = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.BOOLEAN_DIVOT, aeObjFlags=2359, aeMasterPart=PARTID.BOOLEAN_BUTTON, aeHowGrow=3840, \
      aeBounds=[17,0,48,60], aeImageResID=None, aeFgColor=0x00B3B3B3, aeBgColor=0x00B3B3B3)
    boolDivot_table = elemFindOrCreate(boolDivot, "table", fo, po)
    attribGetOrSetDefault(boolDivot_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElement(boolDivot_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,31,60], aeImageResID=-408, aeFgColor=0x00B3B3B3, aeBgColor=0x00B3B3B3, parentPos=1)

    # ANNEX properties taken from empty VI file created in LV14
    annexPart = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="annex", \
      aePartID=PARTID.ANNEX)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "refListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "hGrowNodeListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "rsrcID", fo, po), 21001, fo, po)

    return boolButton

def checkOrCreateParts_stdBool_indicator(RSRC, partsList, parentObjFlags, labelText, fo, po):
    """ Checks content of partsList element of Boolean Indicator type
    """
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1507655, aeMasterPart=PARTID.BOOLEAN_BUTTON, aeHowGrow=4096,
      aeBounds=[0,0,15,50], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 17412, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\""+labelText+"\"", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "bgColor", fo, po), "{:08X}".format(0x01000000), fo, po)

    boolButton = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.BOOLEAN_BUTTON, aeObjFlags=2324, aeMasterPart=None, aeHowGrow=240, \
      aeBounds=[19,2,36,19], aeImageResID=None, aeFgColor=0x001E4B00, aeBgColor=0x001E4B00)
    boolButton_table = elemFindOrCreate(boolButton, "table", fo, po)
    attribGetOrSetDefault(boolButton_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElement(boolButton_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,17,17], aeImageResID=-404, aeFgColor=0x001E4B00, aeBgColor=0x001E4B00, parentPos=1)
    elemCheckOrCreate_table_arrayElement(boolButton_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,17,17], aeImageResID=-404, aeFgColor=0x0064FF00, aeBgColor=0x0064FF00, parentPos=2)
    elemCheckOrCreate_table_arrayElement(boolButton_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,17,17], aeImageResID=-404, aeFgColor=0x001E4B00, aeBgColor=0x001E4B00, parentPos=3)
    elemCheckOrCreate_table_arrayElement(boolButton_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,17,17], aeImageResID=-404, aeFgColor=0x0064FF00, aeBgColor=0x0064FF00, parentPos=4)

    boolGlyph = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.BOOLEAN_GLYPH, aeObjFlags=2359, aeMasterPart=PARTID.BOOLEAN_BUTTON, aeHowGrow=3840, \
      aeBounds=[17,0,38,21], aeImageResID=None, aeFgColor=0x00B3B3B3, aeBgColor=0x00006600)
    boolGlyph_table = elemFindOrCreate(boolGlyph, "table", fo, po)
    attribGetOrSetDefault(boolGlyph_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElement(boolGlyph_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,21,21], aeImageResID=-411, aeFgColor=0x00B3B3B3, aeBgColor=0x00006600, parentPos=1)
    elemCheckOrCreate_table_arrayElement(boolGlyph_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,21,21], aeImageResID=-411, aeFgColor=0x00B3B3B3, aeBgColor=0x0000FF00, parentPos=2)
    elemCheckOrCreate_table_arrayElement(boolGlyph_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,21,21], aeImageResID=-411, aeFgColor=0x00B3B3B3, aeBgColor=0x00009900, parentPos=3)
    elemCheckOrCreate_table_arrayElement(boolGlyph_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,21,21], aeImageResID=-411, aeFgColor=0x00B3B3B3, aeBgColor=0x00009900, parentPos=4)

    # ANNEX properties taken from empty VI file created in LV14
    annexPart = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="annex", \
      aePartID=PARTID.ANNEX)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "refListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "hGrowNodeListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "rsrcID", fo, po), 21012, fo, po)

    return boolButton

def checkOrCreateParts_stdNum_control(RSRC, partsList, parentObjFlags, labelText, fo, po):
    """ Checks content of partsList element of Numeric Control type
    """
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1507654, aeMasterPart=PARTID.FRAME, aeHowGrow=4096,
      aeBounds=[0,11,15,52], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 17412, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\""+labelText+"\"", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "bgColor", fo, po), "{:08X}".format(0x01000000), fo, po)

    numText = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="numLabel", \
      aePartID=PARTID.NUMERIC_TEXT, aeObjFlags=264498, aeMasterPart=PARTID.FRAME, aeHowGrow=240, \
      aeBounds=[19,15,34,61], aeImageResID=-239, aeFgColor=0x00FAFAFA, aeBgColor=0x00FAFAFA)
    numText_textRec = elemFindOrCreate(numText, "textRec", fo, po)
    attribGetOrSetDefault(numText_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(numText_textRec, "mode", fo, po), 8389634, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(numText_textRec, "bgColor", fo, po), "{:08X}".format(0x00FAFAFA), fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(numText, "format", fo, po), "\"%#_g\"", fo, po)

    numIncr = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.INCREMENT, aeObjFlags=2358, aeMasterPart=PARTID.FRAME, aeHowGrow=12288, \
      aeBounds=[14,0,26,12], aeImageResID=None, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC)
    numIncr_table = elemFindOrCreate(numIncr, "table", fo, po)
    attribGetOrSetDefault(numIncr_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElement(numIncr_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,12,12], aeImageResID=-413, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC, parentPos=1)
    elemCheckOrCreate_table_arrayElement(numIncr_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,12,12], aeImageResID=-413, aeFgColor=0x00969696, aeBgColor=0x00969696, parentPos=2)

    numDecr = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.DECREMENT, aeObjFlags=2354, aeMasterPart=PARTID.FRAME, aeHowGrow=12288, \
      aeBounds=[26,0,38,12], aeImageResID=None, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC)
    numDecr_table = elemFindOrCreate(numDecr, "table", fo, po)
    attribGetOrSetDefault(numDecr_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElement(numDecr_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,12,12], aeImageResID=-414, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC, parentPos=1)
    elemCheckOrCreate_table_arrayElement(numDecr_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,12,12], aeImageResID=-414, aeFgColor=0x00969696, aeBgColor=0x00969696, parentPos=2)

    numRadix = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="multiCosm", \
      aePartID=PARTID.RADIX, aeObjFlags=6458, aeMasterPart=PARTID.FRAME, aeHowGrow=4288, \
      aeBounds=[19,15,34,21], aeImageResID=None, aeFgColor=0x00D9DADC, aeBgColor=0x007586A0)
    numRadix_table = elemFindOrCreate(numRadix, "table", fo, po)
    attribGetOrSetDefault(numRadix_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElementImg(numRadix_table, fo, po, aeClass="Image", aeImageResID=-2000, parentPos=1)
    elemCheckOrCreate_table_arrayElementImg(numRadix_table, fo, po, aeClass="Image", aeImageResID=-2001, parentPos=2)
    elemCheckOrCreate_table_arrayElementImg(numRadix_table, fo, po, aeClass="Image", aeImageResID=-2002, parentPos=3)
    elemCheckOrCreate_table_arrayElementImg(numRadix_table, fo, po, aeClass="Image", aeImageResID=-2003, parentPos=4)
    elemCheckOrCreate_table_arrayElementImg(numRadix_table, fo, po, aeClass="Image", aeImageResID=-2095, parentPos=5)

    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.FRAME, aeObjFlags=2327, aeMasterPart=None, aeHowGrow=240, \
      aeBounds=[15,11,38,65], aeImageResID=-412, aeFgColor=0x00B3B3B3, aeBgColor=0x01000000)

    # ANNEX properties taken from empty VI file created in LV14
    annexPart = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="annex", \
      aePartID=PARTID.ANNEX)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "refListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "hGrowNodeListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "rsrcID", fo, po), 21003, fo, po)

    return numText

def checkOrCreateParts_stdNum_indicator(RSRC, partsList, parentObjFlags, labelText, fo, po):
    """ Checks content of partsList element of Numeric Indicator type
    """
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1507654, aeMasterPart=PARTID.FRAME, aeHowGrow=4096,
      aeBounds=[0,0,15,50], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 17412, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\""+labelText+"\"", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "bgColor", fo, po), "{:08X}".format(0x01000000), fo, po)

    numText = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="numLabel", \
      aePartID=PARTID.NUMERIC_TEXT, aeObjFlags=264498, aeMasterPart=PARTID.FRAME, aeHowGrow=240, \
      aeBounds=[19,4,34,50], aeImageResID=-239, aeFgColor=0x00D2D2D2, aeBgColor=0x00D2D2D2)
    numText_textRec = elemFindOrCreate(numText, "textRec", fo, po)
    attribGetOrSetDefault(numText_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(numText_textRec, "mode", fo, po), 8389634, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(numText_textRec, "bgColor", fo, po), "{:08X}".format(0x00D2D2D2), fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(numText, "format", fo, po), "\"%#_g\"", fo, po)

    numIncr = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.INCREMENT, aeObjFlags=6458, aeMasterPart=PARTID.FRAME, aeHowGrow=12288, \
      aeBounds=[14,-11,26,1], aeImageResID=None, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC)
    numIncr_table = elemFindOrCreate(numIncr, "table", fo, po)
    attribGetOrSetDefault(numIncr_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElement(numIncr_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,12,12], aeImageResID=-413, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC, parentPos=1)
    elemCheckOrCreate_table_arrayElement(numIncr_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,12,12], aeImageResID=-413, aeFgColor=0x00969696, aeBgColor=0x00969696, parentPos=2)

    numDecr = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.DECREMENT, aeObjFlags=6458, aeMasterPart=PARTID.FRAME, aeHowGrow=12288, \
      aeBounds=[26,-11,38,1], aeImageResID=None, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC)
    numDecr_table = elemFindOrCreate(numDecr, "table", fo, po)
    attribGetOrSetDefault(numDecr_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElement(numDecr_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,12,12], aeImageResID=-414, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC, parentPos=1)
    elemCheckOrCreate_table_arrayElement(numDecr_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,12,12], aeImageResID=-414, aeFgColor=0x00969696, aeBgColor=0x00969696, parentPos=2)

    numRadix = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="multiCosm", \
      aePartID=PARTID.RADIX, aeObjFlags=6458, aeMasterPart=PARTID.FRAME, aeHowGrow=4288, \
      aeBounds=[19,4,34,10], aeImageResID=None, aeFgColor=0x00D9DADC, aeBgColor=0x007586A0)
    numRadix_table = elemFindOrCreate(numRadix, "table", fo, po)
    attribGetOrSetDefault(numRadix_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElementImg(numRadix_table, fo, po, aeClass="Image", aeImageResID=-2000, parentPos=1)
    elemCheckOrCreate_table_arrayElementImg(numRadix_table, fo, po, aeClass="Image", aeImageResID=-2001, parentPos=2)
    elemCheckOrCreate_table_arrayElementImg(numRadix_table, fo, po, aeClass="Image", aeImageResID=-2002, parentPos=3)
    elemCheckOrCreate_table_arrayElementImg(numRadix_table, fo, po, aeClass="Image", aeImageResID=-2003, parentPos=4)
    elemCheckOrCreate_table_arrayElementImg(numRadix_table, fo, po, aeClass="Image", aeImageResID=-2095, parentPos=5)

    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.FRAME, aeObjFlags=2327, aeMasterPart=None, aeHowGrow=240, \
      aeBounds=[15,0,38,54], aeImageResID=-412, aeFgColor=0x00B3B3B3, aeBgColor=0x01000000)

    # ANNEX properties taken from empty VI file created in LV14
    annexPart = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="annex", \
      aePartID=PARTID.ANNEX)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "refListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "hGrowNodeListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "rsrcID", fo, po), 21004, fo, po)

    return numText

def checkOrCreateParts_stdClust_control(RSRC, partsList, parentObjFlags, labelText, fo, po):
    """ Checks content of partsList element of Cluster Control type
    """
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.CAPTION, aeObjFlags=1507654, aeMasterPart=PARTID.FRAME, aeHowGrow=4096,
      aeBounds=[0,0,15,33], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "flags", fo, po), 1536, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 17412, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\""+labelText+"\"", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "bgColor", fo, po), "{:08X}".format(0x01000000), fo, po)

    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1511758, aeMasterPart=PARTID.FRAME, aeHowGrow=4096,
      aeBounds=[16,-37,31,-4], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "flags", fo, po), 1536, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 17412, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\""+labelText+"\"", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "bgColor", fo, po), "{:08X}".format(0x01000000), fo, po)

    contentArea = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.CONTENT_AREA, aeObjFlags=2359, aeMasterPart=PARTID.FRAME, aeHowGrow=240, \
      aeBounds=[21,4,210,140], aeImageResID=0, aeFgColor=0x00A6A6A6, aeBgColor=0x00A6A6A6)

    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.CONTENT_AREA, aeObjFlags=2359, aeMasterPart=PARTID.FRAME, aeHowGrow=240, \
      aeBounds=[21,4,210,140], aeImageResID=0, aeFgColor=0x00A6A6A6, aeBgColor=0x00A6A6A6)

    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.FRAME, aeObjFlags=2327, aeMasterPart=None, aeHowGrow=240, \
      aeBounds=[17,0,214,144], aeImageResID=-412, aeFgColor=0x00B3B3B3, aeBgColor=0x01000000)

    # ANNEX properties taken from empty VI file created in LV14
    annexPart = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="annex", \
      aePartID=PARTID.ANNEX)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "refListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "hGrowNodeListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "rsrcID", fo, po), 21607, fo, po)

    return contentArea


def FPHb_Fix(RSRC, FPHP, ver, fo, po):
    block_name = "FPHb"

    attribGetOrSetDefault(FPHP, "Index", 0, fo, po)
    sect_format = FPHP.get("Format")
    if sect_format not in ("xml",):
        FPHP.set("Format","xml")
        if len(RSRC.findall("./"+block_name+"/Section")) <= 1:
            snum_str = ""
        else:
            if sect_index >= 0:
                snum_str = str(sect_index)
            else:
                snum_str = 'm' + str(-sect_index)
        fname_base = "{:s}_{:s}{:s}".format(po.filebase, block_name, snum_str)
        FPHP.set("File","{:s}.xml".format(fname_base))
        fo[FUNC_OPTS.changed] = True

    rootObject = elemFindOrCreate(FPHP, "SL__rootObject", fo, po)
    attribGetOrSetDefault(rootObject, "class", "oHExt", fo, po)
    attribGetOrSetDefault(rootObject, "uid", 1, fo, po)

    root = elemFindOrCreate(rootObject, "root", fo, po)
    attribGetOrSetDefault(root, "class", "supC", fo, po)
    attribGetOrSetDefault(root, "uid", 1, fo, po)

    pBounds = elemFindOrCreate(rootObject, "pBounds", fo, po)
    elemTextGetOrSetDefault(pBounds, [46,0,681,1093], fo, po)
    dBounds = elemFindOrCreate(rootObject, "dBounds", fo, po)
    elemTextGetOrSetDefault(dBounds, [0,0,0,0], fo, po)

    origin = elemFindOrCreate(rootObject, "origin", fo, po)
    elemTextGetOrSetDefault(origin, [327,105], fo, po)

    instrStyle = elemFindOrCreate(rootObject, "instrStyle", fo, po)
    elemTextGetOrSetDefault(instrStyle, 31, fo, po)

    blinkList = elemFindOrCreate(rootObject, "blinkList", fo, po)
    attribGetOrSetDefault(blinkList, "elements", 0, fo, po)

    # Now content of the 'root' element

    root_partsList, root_paneHierarchy = elemCheckOrCreate_ddo_content(root, fo, po,
      aeDdoObjFlags=65536, aeBounds=[0,0,0,0], aeMouseWheelSupport=0, \
      valueType="Cluster", aeSavedSize=[0,0,0,0])

    root_conPane = elemFindOrCreate(root, "conPane", fo, po)
    attribGetOrSetDefault(root_conPane, "class", "conPane", fo, po)
    attribGetOrSetDefault(root_conPane, "uid", 1, fo, po)

    root_keyMappingList = elemFindOrCreate(root, "keyMappingList", fo, po)
    attribGetOrSetDefault(root_keyMappingList, "class", "keyMapList", fo, po)
    attribGetOrSetDefault(root_keyMappingList, "uid", 1, fo, po)
    attribGetOrSetDefault(root_keyMappingList, "ScopeInfo", 0, fo, po)

    # Now content of the 'root/conPane' element

    root_conPane_conId = elemFindOrCreate(root_conPane, "conId", fo, po)

    conCount = getConnectorPortsFixedCount(RSRC, ver, fo, po)
    #TODO we could set conId better by considering inputs vs outputs
    if conCount <= 1: conId = 4800
    elif conCount <= 2: conId = 4801
    elif conCount <= 3: conId = 4803
    elif conCount <= 4: conId = 4806
    elif conCount <= 5: conId = 4807
    elif conCount <= 6: conId = 4810
    elif conCount <= 7: conId = 4811
    elif conCount <= 8: conId = 4812
    elif conCount <= 9: conId = 4813
    elif conCount <= 10: conId = 4826
    elif conCount <= 11: conId = 4829
    elif conCount <= 12: conId = 4815
    elif conCount <= 16: conId = 4833
    elif conCount <= 20: conId = 4834
    elif conCount <= 28: conId = 4835
    else: conId = 4815 # Most widely used
    elemTextGetOrSetDefault(root_conPane_conId, conId, fo, po)

    root_conPane_cons = elemFindOrCreate(root_conPane, "cons", fo, po)
    attribGetOrSetDefault(root_conPane_cons, "elements", 0, fo, po)
    # The rest of 'root/conPane' will be filled later, after UIDs are made unique

    # Now content of the 'root/paneHierarchy' element

    objFlags = 0x050d51 # in new empty VI it's 0x0260834
    if False: #TODO if horiz scrollbar disabled
        objFlags |= 0x0004
    if False: #TODO if vert scrollbar disabled
        objFlags |= 0x0008
    paneHierarchy_objFlags = elemFindOrCreate(root_paneHierarchy, "objFlags", fo, po)
    paneHierarchy_objFlags_val = elemTextGetOrSetDefault(paneHierarchy_objFlags, objFlags, fo, po)

    paneHierarchy_howGrow = elemFindOrCreate(root_paneHierarchy, "howGrow", fo, po)
    elemTextGetOrSetDefault(paneHierarchy_howGrow, 240, fo, po)

    paneHierarchy_bounds = elemFindOrCreate(root_paneHierarchy, "bounds", fo, po)
    elemTextGetOrSetDefault(paneHierarchy_bounds, [46,0,681,1093], fo, po)

    paneHierarchy_partsList = elemFindOrCreate(root_paneHierarchy, "partsList", fo, po)
    attribGetOrSetDefault(paneHierarchy_partsList, "elements", 0, fo, po)

    paneHierarchy_paneFlags = elemFindOrCreate(root_paneHierarchy, "paneFlags", fo, po)
    elemTextGetOrSetDefault(paneHierarchy_paneFlags, 331089, fo, po)

    paneHierarchy_minPaneSize = elemFindOrCreate(root_paneHierarchy, "minPaneSize", fo, po)
    elemTextGetOrSetDefault(paneHierarchy_minPaneSize, [1,1], fo, po)

    paneHierarchy_docBounds = elemFindOrCreate(root_paneHierarchy, "docBounds", fo, po)
    elemTextGetOrSetDefault(paneHierarchy_docBounds, [0,0,619,1077], fo, po)

    paneHierarchy_zPlaneList = elemFindOrCreate(root_paneHierarchy, "zPlaneList", fo, po)
    attribGetOrSetDefault(paneHierarchy_zPlaneList, "elements", 0, fo, po)

    paneHierarchy_image = elemFindOrCreate(root_paneHierarchy, "image", fo, po)
    attribGetOrSetDefault(paneHierarchy_image, "class", "Image", fo, po)

    # Now content of the 'root/paneHierarchy/image' element

    paneHierarchy_image_ImageResID = elemFindOrCreate(paneHierarchy_image, "ImageResID", fo, po)
    elemTextGetOrSetDefault(paneHierarchy_image_ImageResID, 0, fo, po)

    # Now content of the 'root/paneHierarchy/partsList' element
    paneContent = checkOrCreateParts_Pane(RSRC, paneHierarchy_partsList, paneHierarchy_objFlags_val, "Pane", fo, po)

    # Now content of the 'root/paneHierarchy/zPlaneList' element
    DTHP_typeDescSlice = RSRC.find("./DTHP/Section/TypeDescSlice")
    if DTHP_typeDescSlice is not None:
        indexShift = DTHP_typeDescSlice.get("IndexShift")
        if indexShift is not None:
            indexShift = int(indexShift, 0)
        tdCount = DTHP_typeDescSlice.get("Count")
        if tdCount is not None:
            tdCount = int(tdCount, 0)
    else:
        raise NotImplementedError("DTHP should've been already re-created at this point.")

    # recover FP DCOs from a list within DFDS
    TM80_IndexShift = None
    TM80 = RSRC.find("./TM80/Section")
    if TM80 is not None:
        TM80_IndexShift = TM80.get("IndexShift")
        if TM80_IndexShift is not None:
            TM80_IndexShift = int(TM80_IndexShift, 0)

    FpDCOList = getFpDCOTableAsList(RSRC, po, TM80_IndexShift=TM80_IndexShift)

    # recover more data on FP DCOs from Heap TDs
    # Heap Types first store a list of TypeDescs used in FP, then a list of TDs used in BD
    # We need to map the first part to the DCOs we have. Connectors may be helpful here, as if they
    # are set, then they store TypeID values for types associated to the DCOs.
    heapTypeMap = {htId+1:getConsolidatedTopType(RSRC, indexShift+htId, po) for htId in range(tdCount)}

    usedTypeID = 0 # Heap TypeID values start with 1, set it before the range
    # Figure out Heap Types range for each DCO
    for DCO in reversed(FpDCOList):
        # We expect DCO type, DDO type, and then sub-types
        DCO['dcoTypeID'] = None
        DCO['ddoTypeID'] = None
        DCO['subTypeIDs'] = []
        dcoTypeID = usedTypeID + 1
        ddoTypeID = dcoTypeID + 1
        subTypeIDs = []

        if dcoTypeID not in heapTypeMap:
            eprint("{:s}: Warning: Heap TypeDesc {} expected for DCO{} does not exist"\
              .format(po.xml,dcoTypeID,DCO['dcoIndex']))
            break
        if ddoTypeID not in heapTypeMap:
            eprint("{:s}: Warning: Heap TypeDesc {} expected for DCO{}.DDO does not exist"\
              .format(po.xml,ddoTypeID,DCO['dcoIndex']))
            break
        dcoTypeDesc = heapTypeMap[dcoTypeID]
        ddoTypeDesc = heapTypeMap[ddoTypeID]
        if dcoTypeDesc != ddoTypeDesc:
            eprint("{:s}: Warning: DCO and DDO types differ: '{}' vs '{}'"\
              .format(po.xml,dcoTypeDesc.get("Type"),ddoTypeDesc.get("Type")))
        # For compound types, get sub-types
        subTypeID = ddoTypeID + 1
        if dcoTypeDesc.get("Type") == "Cluster":
            # For cluster, a type identical to each sub-type is also added directly to the DTHP list
            dcoTypeDesc_FieldList = list(filter(lambda f: f.tag is not ET.Comment, dcoTypeDesc.findall("./*")))
            for dcoSubTypeDesc_ref in reversed(dcoTypeDesc_FieldList): # The list of fields looks reverted.. Maybe it's just unsorted?
                # The content of Cluster type either stores the sub-types, or references to them
                dcoSubTypeDesc_typeId = int(dcoSubTypeDesc_ref.get("TypeID"), 0)
                if dcoSubTypeDesc_typeId == -1:
                    dcoSubTypeDesc = dcoSubTypeDesc_ref
                else:
                    dcoSubTypeDesc = getConsolidatedFlatType(RSRC, dcoSubTypeDesc_typeId, po)
                if subTypeID not in heapTypeMap:
                    eprint("{:s}: Warning: Heap TypeDesc {} expected for DCO{} sub-type does not exist"\
                      .format(po.xml,subTypeID,DCO['dcoIndex']))
                    break
                subTypeDesc = heapTypeMap[subTypeID]
                if subTypeDesc != dcoSubTypeDesc:
                    eprint("{:s}: Warning: Heap TypeDesc {} expected for DCO{} has non-matching type: '{}' instead of '{}'"\
                      .format(po.xml,subTypeID,DCO['dcoIndex'],subTypeDesc.get("Type"),dcoSubTypeDesc.get("Type")))
                    continue
                if (po.verbose > 1):
                    print("{:s}: Heap TypeDesc {} expected for DCO{} has type '{}' matching Cluster field"\
                      .format(po.xml,subTypeID,DCO['dcoIndex'],subTypeDesc.get("Type")))
                subTypeIDs.append(subTypeID)
                subTypeID += 1
        DCO['dcoTypeID'] = dcoTypeID
        DCO['ddoTypeID'] = ddoTypeID
        DCO['subTypeIDs'] = subTypeIDs
        usedTypeID = ddoTypeID + len(subTypeIDs)

    pos = [0,0]
    for DCO in reversed(FpDCOList):
        typeCtlOrInd = "indicator" if DCO['isIndicator'] != 0 else "control"
        dcoTypeDesc = None
        if DCO['dcoTypeID'] is not None:
            dcoTypeDesc = heapTypeMap[DCO['dcoTypeID']]
        if dcoTypeDesc is None:
            eprint("{:s}: Warning: DCO{} does not have dcoTypeID, not adding to FP"\
              .format(po.xml,DCO['dcoIndex']))
            continue

        if dcoTypeDesc.get("Type") == "Boolean" and DCO['isIndicator'] == 0:
            print("{:s}: Associating DCO{} TypeDesc '{}' with FpDCO {} of class '{}'"\
              .format(po.xml,DCO['dcoIndex'],dcoTypeDesc.get("Type"),typeCtlOrInd,"stdBool"))
            dcoObjFlags_val = 0x10200
            ddoObjFlags_val = 0 # 0x1: user input disabled
            labelText = dcoTypeDesc.get("Label")
            if labelText is None: labelText = "Boolean"
            dco_elem, ddo_elem = elemCheckOrCreate_zPlaneList_arrayElement(paneHierarchy_zPlaneList, fo, po, aeClass="fPDCO", \
              aeTypeID=DCO['dcoTypeID'], aeObjFlags=dcoObjFlags_val, aeDdoClass="stdBool", aeConNum=DCO['conNum'], aeTermListLength=1)
            dco_partsList, _ = elemCheckOrCreate_ddo_content(ddo_elem, fo, po, aeDdoObjFlags=ddoObjFlags_val,
              aeBounds=[pos[0],pos[1],pos[0]+48,pos[1]+60], aeDdoTypeID=DCO['ddoTypeID'], aeMouseWheelSupport=0, aeMinButSize=[50,21], \
              valueType=dcoTypeDesc.get("Type"))

            checkOrCreateParts_stdBool_control(RSRC, dco_partsList, ddoObjFlags_val, labelText, fo, po)
        elif dcoTypeDesc.get("Type") == "Boolean" and DCO['isIndicator'] != 0:
            print("{:s}: Associating DCO{} TypeDesc '{}' with FpDCO {} of class '{}'"\
              .format(po.xml,DCO['dcoIndex'],dcoTypeDesc.get("Type"),typeCtlOrInd,"stdBool"))
            dcoObjFlags_val = 0x10200 | 0x01
            ddoObjFlags_val = 1
            labelText = dcoTypeDesc.get("Label")
            if labelText is None: labelText = "Boolean"
            dco_elem, ddo_elem = elemCheckOrCreate_zPlaneList_arrayElement(paneHierarchy_zPlaneList, fo, po, aeClass="fPDCO", \
              aeTypeID=DCO['dcoTypeID'], aeObjFlags=dcoObjFlags_val, aeDdoClass="stdBool", aeConNum=DCO['conNum'], aeTermListLength=1)
            dco_partsList, _ = elemCheckOrCreate_ddo_content(ddo_elem, fo, po, aeDdoObjFlags=ddoObjFlags_val,
              aeBounds=[pos[0],pos[1],pos[0]+38,pos[1]+41], aeDdoTypeID=DCO['ddoTypeID'], aeMouseWheelSupport=0, aeMinButSize=[17,17], \
              valueType=dcoTypeDesc.get("Type"))
            checkOrCreateParts_stdBool_indicator(RSRC, dco_partsList, ddoObjFlags_val, labelText, fo, po)
        elif dcoTypeDesc.get("Type").startswith("Num") and DCO['isIndicator'] == 0:
            print("{:s}: Associating DCO{} TypeDesc '{}' with FpDCO {} of class '{}'"\
              .format(po.xml,DCO['dcoIndex'],dcoTypeDesc.get("Type"),typeCtlOrInd,"stdNum"))
            dcoObjFlags_val = 0
            ddoObjFlags_val = 0x60042
            labelText = dcoTypeDesc.get("Label")
            if labelText is None: labelText = "Numeric"
            stdNumMin, stdNumMax, stdNumInc = valueTypeGetDefaultRange(dcoTypeDesc.get("Type"), po)
            dco_elem, ddo_elem = elemCheckOrCreate_zPlaneList_arrayElement(paneHierarchy_zPlaneList, fo, po, aeClass="fPDCO", \
              aeTypeID=DCO['dcoTypeID'], aeObjFlags=dcoObjFlags_val, aeDdoClass="stdNum", aeConNum=DCO['conNum'], aeTermListLength=1)
            dco_partsList, _ = elemCheckOrCreate_ddo_content(ddo_elem, fo, po, aeDdoObjFlags=ddoObjFlags_val, \
              aeBounds=[185,581,223,622], aeDdoTypeID=DCO['ddoTypeID'], aeMouseWheelSupport=2, aeMinButSize=None, \
              valueType=dcoTypeDesc.get("Type"), aeStdNumMin=stdNumMin, aeStdNumMax=stdNumMax, aeStdNumInc=stdNumInc)
            checkOrCreateParts_stdNum_control(RSRC, dco_partsList, ddoObjFlags_val, labelText, fo, po)
        elif dcoTypeDesc.get("Type").startswith("Num") and DCO['isIndicator'] != 0:
            print("{:s}: Associating DCO{} TypeDesc '{}' with FpDCO {} of class '{}'"\
              .format(po.xml,DCO['dcoIndex'],dcoTypeDesc.get("Type"),typeCtlOrInd,"stdNum"))
            dcoObjFlags_val = 0x01
            ddoObjFlags_val = 0x60042 | 0x01
            labelText = dcoTypeDesc.get("Label")
            if labelText is None: labelText = "Numeric"
            stdNumMin, stdNumMax, stdNumInc = valueTypeGetDefaultRange(dcoTypeDesc.get("Type"), po)
            dco_elem, ddo_elem = elemCheckOrCreate_zPlaneList_arrayElement(paneHierarchy_zPlaneList, fo, po, aeClass="fPDCO", \
              aeTypeID=DCO['dcoTypeID'], aeObjFlags=dcoObjFlags_val, aeDdoClass="stdNum", aeConNum=DCO['conNum'], aeTermListLength=1)
            dco_partsList, _ = elemCheckOrCreate_ddo_content(ddo_elem, fo, po, aeDdoObjFlags=ddoObjFlags_val, \
              aeBounds=[185,581,223,622], aeDdoTypeID=DCO['ddoTypeID'], aeMouseWheelSupport=2, aeMinButSize=None, \
              valueType=dcoTypeDesc.get("Type"), aeStdNumMin=stdNumMin, aeStdNumMax=stdNumMax, aeStdNumInc=stdNumInc)
            checkOrCreateParts_stdNum_indicator(RSRC, dco_partsList, ddoObjFlags_val, labelText, fo, po)
        elif dcoTypeDesc.get("Type") == "Cluster" and DCO['isIndicator'] == 0:
            print("{:s}: Associating DCO{} TypeDesc '{}' with FpDCO {} of class '{}'"\
              .format(po.xml,DCO['dcoIndex'],dcoTypeDesc.get("Type"),typeCtlOrInd,"stdClust"))
            dcoObjFlags_val = 0
            ddoObjFlags_val = 0x00004
            labelText = dcoTypeDesc.get("Label")
            if labelText is None: labelText = "Cluster"
            dco_elem, ddo_elem = elemCheckOrCreate_zPlaneList_arrayElement(paneHierarchy_zPlaneList, fo, po, aeClass="fPDCO", \
              aeTypeID=DCO['dcoTypeID'], aeObjFlags=dcoObjFlags_val, aeDdoClass="stdClust", aeConNum=DCO['conNum'], aeTermListLength=1)
            dco_partsList, ddo_paneHierarchy = elemCheckOrCreate_ddo_content(ddo_elem, fo, po, aeDdoObjFlags=ddoObjFlags_val, \
              aeBounds=[185,581,223,622], aeDdoTypeID=DCO['ddoTypeID'], aeMouseWheelSupport=0, aeMinButSize=None, \
              valueType=dcoTypeDesc.get("Type"), aeSavedSize=[0,0,0,0])
            checkOrCreateParts_stdClust_control(RSRC, dco_partsList, ddoObjFlags_val, labelText, fo, po)
        else:
            #TODO add more types
            dco_elem = None
            dco_partsList = None
            eprint("{:s}: Warning: Heap dcoTypeDesc '{}' {} is not supported"\
              .format(po.xml,dcoTypeDesc.get("Type"),typeCtlOrInd))

    # Get expected grid alignment
    LVSR_parUnknown = RSRC.find("./LVSR/Section/Unknown")
    if LVSR_parUnknown is not None:
        gridDelta = LVSR_parUnknown.get("AlignGridFP")
    if gridDelta is not None:
        gridDelta = int(gridDelta,0)
    if gridDelta is None or gridDelta < 4 or gridDelta > 256:
        gridDelta = 12 # default value in case alignment from LVSR is suspicious
    # Get window content bounds
    paneContentBounds = paneContent.find("./bounds")
    if paneContentBounds is not None:
        paneContentBounds = paneContentBounds.text
    if paneContentBounds is not None:
        paneContentBounds = strToList(paneContentBounds)
    if paneContentBounds is None:
        paneContentBounds = [0,0,622,622]
    windowWidth = paneContentBounds[3] - paneContentBounds[1]
    # Re-compute positions of DCOs so they do not overlap and fit the window
    zPlaneList_elems = paneHierarchy_zPlaneList.findall("./SL__arrayElement[@class='fPDCO'][@uid]")
    i = 1
    while i < len(zPlaneList_elems):
        dco_elem = zPlaneList_elems[i]
        bounds_elem = dco_elem.find("./ddo/bounds")
        if bounds_elem is None:
            i += 1
            continue
        eBounds = bounds_elem.text
        if eBounds is not None:
            eBounds = strToList(eBounds)
        if eBounds is None:
            eBounds = [0,0,16,16]
            eprint("{:s}: Warning: Could not read bounds of FpDCO"\
              .format(po.xml))
        eMoved = False
        for k in range(0,i):
            overlap_elem = zPlaneList_elems[k]
            oBounds = overlap_elem.find("./ddo/bounds")
            if oBounds is not None:
                oBounds = oBounds.text
            if oBounds is not None:
                oBounds = strToList(oBounds)
            if oBounds is None:
                oBounds = [0,0,16,16]
            while boundsOverlap(eBounds, oBounds):
                eMoved = True
                eBounds[1] += gridDelta
                eBounds[3] += gridDelta
                if eBounds[3] >= windowWidth:
                    eBounds[3] -= eBounds[0]
                    eBounds[1] = 0
                    eBounds[0] += gridDelta
                    eBounds[2] += gridDelta
                    if eBounds[3] >= windowWidth:
                        break # Safety check for incredibly huge components (or small windows)
        if eMoved:
            elemTextSetValue(bounds_elem, eBounds, fo, po)
            continue
        i += 1
    return fo[FUNC_OPTS.changed]

def LIvi_Fix(RSRC, LIvi, ver, fo, po):
    LVIN = LIvi.find("LVIN")
    if LVIN is None:
        LVIN = ET.SubElement(LIvi, "LVIN")
        fo[FUNC_OPTS.changed] = True
    return fo[FUNC_OPTS.changed]

def LIfp_Fix(RSRC, LIfp, ver, fo, po):
    FPHP = LIfp.find("FPHP")
    if FPHP is None:
        FPHP = ET.SubElement(LIfp, "FPHP")
        fo[FUNC_OPTS.changed] = True
    return fo[FUNC_OPTS.changed]

def LIbd_Fix(RSRC, LIbd, ver, fo, po):
    BDHP = LIfp.find("BDHP")
    if BDHP is None:
        BDHP = ET.SubElement(LIfp, "BDHP")
        fo[FUNC_OPTS.changed] = True
    return fo[FUNC_OPTS.changed]

def TM80_Fix(RSRC, DSTM, ver, fo, po):
    return fo[FUNC_OPTS.changed]

def intRangesExcludeOne(iRanges, excludeIndex):
    if excludeIndex is None:
        return iRanges
    nRanges = []
    for rng in iRanges:
        if excludeIndex < rng.min or excludeIndex > rng.max:
            nRanges.append(rng)
            continue
        nRng = SimpleNamespace(min=rng.min,max=excludeIndex-1)
        if nRng.max - nRng.min > 0:
            nRanges.append(nRng)
        nRng = SimpleNamespace(min=excludeIndex+1,max=rng.max)
        if nRng.max - nRng.min > 0:
            nRanges.append(nRng)
    return nRanges

def intRangesExcludeBelow(iRanges, excludeIndex):
    if excludeIndex is None:
        return iRanges
    nRanges = intRangesExcludeOne(iRanges, excludeIndex)
    return [ rng for rng in nRanges if rng.min > excludeIndex ]

def intRangesOneContaining(iRanges, leaveIndex):
    if leaveIndex is None:
        return iRanges
    nRanges = []
    for rng in iRanges:
        if leaveIndex < rng.min or leaveIndex > rng.max:
            continue
        nRanges.append(nRng)
    if len(nRanges) < 1:
        return iRanges
    return nRanges

def DTHP_Fix(RSRC, DTHP, ver, fo, po):
    typeDescSlice = DTHP.find("./TypeDescSlice")
    if typeDescSlice is None:
        typeDescSlice = ET.SubElement(DTHP, "TypeDescSlice")
        fo[FUNC_OPTS.changed] = True
    indexShift = typeDescSlice.get("IndexShift")
    if indexShift is not None:
        indexShift = int(indexShift, 0)
    tdCount = typeDescSlice.get("Count")
    if tdCount is not None:
        tdCount = int(tdCount, 0)
    # We have current values, now compute proper ones
    VCTP_TypeDescList = []
    VCTP_FlatTypeDescList = None
    VCTP = RSRC.find("./VCTP/Section")
    if VCTP is not None:
        VCTP_TypeDescList = VCTP.findall("TopLevel/TypeDesc")
        VCTP_FlatTypeDescList = VCTP.findall("TypeDesc")
    # Set min possible value; we will increase it shortly
    # and max acceptable value; we will decrease it shortly
    heapRanges = [ SimpleNamespace(min=1,max=len(VCTP_TypeDescList)+1) ]
    if True: # find proper Heap TDs range
        # DTHP range is always above TM80 IndexShift
        # This is not directly enforced in code, but before Heap TypeDescs
        # there are always TypeDescs which store options, and those are
        # filled with DFDS, meaning they have to be included in TM80 range
        TM80_IndexShift = None
        TM80 = RSRC.find("./TM80/Section")
        if TM80 is not None:
            TM80_IndexShift = TM80.get("IndexShift")
            if TM80_IndexShift is not None:
                TM80_IndexShift = int(TM80_IndexShift, 0)
        heapRanges = intRangesExcludeBelow(heapRanges, TM80_IndexShift)
        # DTHP IndexShift must be high enough to not include TypeDesc from CONP
        # Since CONP type is created with new VIs it is always before any heap TDs
        CONP_TypeID = None
        CONP_TypeDesc = RSRC.find("./CONP/Section/TypeDesc")
        if CONP_TypeDesc is not None:
            CONP_TypeID = CONP_TypeDesc.get("TypeID")
            if CONP_TypeID is not None:
                CONP_TypeID = int(CONP_TypeID, 0)
        heapRanges = intRangesExcludeBelow(heapRanges, CONP_TypeID)
        # DTHP must not include TypeDesc from CPC2
        # That type is created when first connector from pane is assigned; so it's
        # sometimes placed before, sometimes after heap TDs
        CPC2_TypeID = None
        CPC2_TypeDesc = RSRC.find("./CPC2/Section/TypeDesc")
        if CPC2_TypeDesc is not None:
            CPC2_TypeID = CPC2_TypeDesc.get("TypeID")
            if CPC2_TypeID is not None:
                CPC2_TypeID = int(CPC2_TypeID, 0)
        heapRanges = intRangesExcludeOne(heapRanges, CPC2_TypeID)
        # DTHP must not include TypeDesc from PFTD
        FPTD_TypeID = None
        FPTD_TypeDesc = RSRC.find("./FPTD/Section/TypeDesc")
        if FPTD_TypeDesc is not None:
            FPTD_TypeID = FPTD_TypeDesc.get("TypeID")
            if FPTD_TypeID is not None:
                FPTD_TypeID = int(FPTD_TypeID, 0)
        heapRanges = intRangesExcludeOne(heapRanges, FPTD_TypeID)
        # DTHP must not include TypeDesc with DSInit
        DSInit = getDSInitRecord(RSRC, po)
        DSInit_TypeID = None
        if DSInit is not None:
            DSInit_TypeID = DSInit.get("TypeID")
        if DSInit_TypeID is not None:
            DSInit_TypeID = int(DSInit_TypeID, 0)
        heapRanges = intRangesExcludeOne(heapRanges, DSInit_TypeID)
        # DTHP must not include TypeDesc with Hilite Table
        HiliteTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.hiliteTableTMI, po, DSInit=DSInit)
            if val_TMI is not None and val_TMI >= 0:
                HiliteTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        heapRanges = intRangesExcludeOne(heapRanges, HiliteTable_TypeID)
        # DTHP must not include TypeDesc with Probe Table
        ProbeTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.probeTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                ProbeTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        heapRanges = intRangesExcludeOne(heapRanges, ProbeTable_TypeID)
        # DTHP must not include TypeDesc with FP DCO Table
        FpDCOTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.fpdcoTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                FpDCOTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        heapRanges = intRangesExcludeOne(heapRanges, FpDCOTable_TypeID)
        # DTHP must not include TypeDesc with Clump QE Alloc
        ClumpQEAlloc_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.clumpQEAllocTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                ClumpQEAlloc_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        heapRanges = intRangesExcludeOne(heapRanges, ClumpQEAlloc_TypeID)
        # DTHP must not include TypeDesc with VI Param Table
        VIParamTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.viParamTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                VIParamTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        heapRanges = intRangesExcludeOne(heapRanges, VIParamTable_TypeID)
        # DTHP must not include TypeDesc with Extra DCO Info
        ExtraDCOInfo_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.extraDCOInfoTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                ExtraDCOInfo_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        heapRanges = intRangesExcludeOne(heapRanges, ExtraDCOInfo_TypeID)
        # DTHP must not include TypeDesc with IO Conn Idx
        IOConnIdx_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.localInputConnIdxTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                IOConnIdx_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        heapRanges = intRangesExcludeOne(heapRanges, IOConnIdx_TypeID)
        # DTHP must not include TypeDesc with InternalHiliteTableHandleAndPtr
        InternalHiliteTableHandleAndPtr_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.internalHiliteTableHandleAndPtrTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                InternalHiliteTableHandleAndPtr_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        heapRanges = intRangesExcludeOne(heapRanges, InternalHiliteTableHandleAndPtr_TypeID)
        # DTHP must not include TypeDesc with SubVI Patch Tags
        SubVIPatchTags_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.subVIPatchTagsTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                SubVIPatchTags_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        heapRanges = intRangesExcludeOne(heapRanges, SubVIPatchTags_TypeID)
        # DTHP must not include TypeDesc with SubVI Patch
        SubVIPatch_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.subVIPatchTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                SubVIPatch_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        heapRanges = intRangesExcludeOne(heapRanges, SubVIPatch_TypeID)
        # DTHP must not include TypeDesc with Enpd Td Offsets
        EnpdTdOffsets_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.enpdTdOffsetsTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                EnpdTdOffsets_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        heapRanges = intRangesExcludeOne(heapRanges, EnpdTdOffsets_TypeID)
        # DTHP must not include TypeDesc with Sp DDO Table
        SpDDOTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.spDDOTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                SpDDOTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        heapRanges = intRangesExcludeOne(heapRanges, SpDDOTable_TypeID)
        # DTHP must not include TypeDesc with StepInto Node Idx Table
        StepIntoNodeIdxTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.stepIntoNodeIdxTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                StepIntoNodeIdxTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        heapRanges = intRangesExcludeOne(heapRanges, StepIntoNodeIdxTable_TypeID)
        # DTHP must not include TypeDesc with Hilite Idx Table
        HiliteIdxTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.hiliteIdxTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                HiliteIdxTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        heapRanges = intRangesExcludeOne(heapRanges, HiliteIdxTable_TypeID)
        # DTHP must not include TypeDesc with Generated Code Profile Result Table
        GeneratedCodeProfileResultTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.generatedCodeProfileResultTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                GeneratedCodeProfileResultTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        heapRanges = intRangesExcludeOne(heapRanges, GeneratedCodeProfileResultTable_TypeID)
        # DTHP must not include TypeDesc values pointed to by DCOs
        DCO_fields = [ field[0] for field in LVparts.DCO._fields_ ]
        FpDCOTable = getFpDCOTable(RSRC, po, TM80_IndexShift=TM80_IndexShift, FpDCOTable_TypeID=FpDCOTable_TypeID)
        if FpDCOTable is not None and TM80_IndexShift is not None:
            for FpDCO in FpDCOTable.findall("./RepeatedBlock/Cluster"):
                FpDCOFlags_TypeID = None
                FpDCODefaultDataTMI_TypeID = None
                FpDCOExtraData_TypeID = None
                # List fields without comments
                FpDCO_FieldList = list(filter(lambda f: f.tag is not ET.Comment, FpDCO.findall("./*")))
                val_TMI = FpDCO_FieldList[DCO_fields.index('flagTMI')].text
                if val_TMI is not None:
                    val_TMI = int(val_TMI,0)
                    FpDCOFlags_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
                val_TMI = FpDCO_FieldList[DCO_fields.index('defaultDataTMI')].text
                if val_TMI is not None:
                    val_TMI = int(val_TMI,0)
                    FpDCODefaultDataTMI_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
                val_TMI = FpDCO_FieldList[DCO_fields.index('extraDataTMI')].text
                if val_TMI is not None:
                    val_TMI = int(val_TMI,0)
                    FpDCOExtraData_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
                heapRanges = intRangesExcludeOne(heapRanges, FpDCOFlags_TypeID)
                heapRanges = intRangesExcludeOne(heapRanges, FpDCODefaultDataTMI_TypeID)
                heapRanges = intRangesExcludeOne(heapRanges, FpDCOExtraData_TypeID)
        # DTHP must not include TypeDesc values pointed to by ProbePoints
        ProbeTable = getProbeTable(RSRC, po, TM80_IndexShift=TM80_IndexShift, ProbeTable_TypeID=ProbeTable_TypeID)
        if ProbeTable is not None and TM80_IndexShift is not None:
            ProbeTable_FieldList = list(filter(lambda f: f.tag is not ET.Comment, ProbeTable.findall("./RepeatedBlock/I32")))
            for i in range(len(ProbeTable_FieldList)//2):
                val_TMI = ProbeTable_FieldList[2*i+1].text
                if val_TMI is not None:
                    val_TMI = int(val_TMI, 0)
                if val_TMI < 1:
                    val_TMI = None
                ProbePoint_TypeID = None
                if val_TMI is not None:
                    ProbePoint_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
                heapRanges = intRangesExcludeOne(heapRanges, ProbePoint_TypeID)
        # DTHP must not include TypeDesc values pointed to by BFAL
        if TM80_IndexShift is not None:
            for BFAL_TypeMap in RSRC.findall("./BFAL/Section/TypeMap"):
                val_TMI = BFAL_TypeMap.get("TMI")
                if val_TMI is not None:
                    val_TMI = int(val_TMI, 0)
                BFAL_TypeID = None
                if val_TMI is not None:
                    BFAL_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
                heapRanges = intRangesExcludeOne(heapRanges, BFAL_TypeID)
        # DTHP must not include TypeDesc of type "Function"
        # IndexShift must be high enough or count must be small enough to keep
        # Function TDs outside.
        nonHeapTypes = []
        for TypeDesc in VCTP_TypeDescList:
            TypeDesc_Index = TypeDesc.get("Index")
            if TypeDesc_Index is not None:
                TypeDesc_Index = int(TypeDesc_Index, 0)
            FlatTypeID = TypeDesc.get("FlatTypeID")
            if FlatTypeID is not None:
                FlatTypeID = int(FlatTypeID, 0)
            if FlatTypeID is None: continue # Something is wrong with the list
            if FlatTypeID >= len(VCTP_FlatTypeDescList): continue # Something is wrong with the list
            FlatTypeDesc = VCTP_FlatTypeDescList[FlatTypeID]
            if FlatTypeDesc.get("Type") == "Function":
                # Function type can only be part of heap types if its FlatTypeID is used two times
                # in the file, and the other use is not a heap type.
                for OtherTypeDesc in VCTP_TypeDescList:
                    OtherTypeDesc_Index = OtherTypeDesc.get("Index")
                    if OtherTypeDesc_Index is not None:
                        OtherTypeDesc_Index = int(OtherTypeDesc_Index, 0)
                    OtherFlatTypeID = OtherTypeDesc.get("FlatTypeID")
                    if OtherFlatTypeID is not None:
                        OtherFlatTypeID = int(OtherFlatTypeID, 0)
                    # Let's assume the second use of the same Function type can be in heap types
                    # So only if we are on first use of that flat type, disallow it s use in heap
                    if OtherFlatTypeID == FlatTypeID:
                        if OtherTypeDesc_Index == TypeDesc_Index:
                            nonHeapTypes.append(TypeDesc_Index)
                        break
            #TODO check if other types should be removed from heap
        for TypeDesc_Index in nonHeapTypes:
            heapRanges = intRangesExcludeOne(heapRanges, TypeDesc_Index)
    minIndexShift = 0
    maxTdCount = 0
    if (po.verbose > 1):
        print("{:s}: Possible heap TD ranges: {}"\
            .format(po.xml,heapRanges))
    for rng in heapRanges:
        if rng.max - rng.min <= maxTdCount:
            continue
        minIndexShift = rng.min
        maxTdCount = rng.max - rng.min
    if indexShift is None or indexShift < minIndexShift:
        if (po.verbose > 0):
            print("{:s}: Changing 'DTHP/TypeDescSlice' IndexShift to {}"\
                .format(po.xml,minIndexShift))
        indexShift = minIndexShift
        typeDescSlice.set("IndexShift","{}".format(indexShift))
        fo[FUNC_OPTS.changed] = True
    if tdCount is None or tdCount > maxTdCount:
        if (po.verbose > 0):
            print("{:s}: Changing 'DTHP/TypeDescSlice' Count to {}"\
                .format(po.xml,maxTdCount))
        tdCount = maxTdCount
        typeDescSlice.set("Count","{}".format(tdCount))
        fo[FUNC_OPTS.changed] = True
    return fo[FUNC_OPTS.changed]

def DFDS_Fix(RSRC, DFDS, ver, fo, po):
    return fo[FUNC_OPTS.changed]

def BDPW_Fix(RSRC, BDPW, ver, fo, po):
    return fo[FUNC_OPTS.changed]

def LVSR_Fix(RSRC, LVSR, ver, fo, po):
    return fo[FUNC_OPTS.changed]

def VCTP_Fix(RSRC, VCTP, ver, fo, po):
    return fo[FUNC_OPTS.changed]

def CONP_Fix(RSRC, CONP, ver, fo, po):
    return fo[FUNC_OPTS.changed]

def BDHb_Fix(RSRC, BDHb, ver, fo, po):
    return fo[FUNC_OPTS.changed]


LVSR_SectionDef = [
 ["LVIN",	1,0,0,	None], # not sure how old it is
 ["LVSR",	5,0,0,	LVSR_Fix], # verified for LV6.0 - LV14.0
]

vers_SectionDef = [
 ["vers",	1,0,0,	vers_Fix], # no idea about versions; this one is for LV8.6 - LV14.0
]

VCTP_SectionDef = [
 ["VCTP",	7,0,0,	VCTP_Fix], # does not exist for LV6.0, but not sure what the replacement is; correct for LV8.6 - LV14.0
]

FPHP_SectionDef = [
 ["FPHP",	1,0,0,	None], # checked to be the format for LV6.0
 ["FPHb",	7,0,0,	FPHb_Fix], # checked to be the format for LV8.6 - LV14.0
 ["FPHc",	15,0,0,	None], # not sure where the switch happened; LV14.0 supports it, but uses ver b by default
]

BDHP_SectionDef = [
 ["BDHP",	1,0,0,	None], # checked to be the format for LV6.0
 ["BDHb",	7,0,0,	BDHb_Fix], # checked to be the format for LV8.6 - LV14.0
 ["BDHc",	15,0,0,	None], # not sure where the switch happened; LV14.0 supports it, but uses ver b by default
]

LIvi_SectionDef = [
 ["LIvi",	1,0,0,	LIvi_Fix], # not sure where it started; correct for LV8.6 - LV14.0
]

LIfp_SectionDef = [
 ["LIfp",	1,0,0,	LIfp_Fix], # not sure where it started; correct for LV8.6 - LV14.0
]

LIbd_SectionDef = [
 ["LIbd",	1,0,0,	LIbd_Fix], # not sure where it started; correct for LV8.6 - LV14.0
]

DSTM_SectionDef = [
 ["DSTM",	1,0,0,	None], # correct for LV7.1 and below
 ["TM80",	8,0,0,	TM80_Fix], # correct for LV8.0 - LV14.0
]

CONP_SectionDef = [
 ["CONP",	1,0,0,	CONP_Fix], # existed at least from LV6.0
]

DTHP_SectionDef = [
 ["DTHP",	1,0,0,	DTHP_Fix], # existed at least from LV6.0
]

DFDS_SectionDef = [
 ["DFDS",	1,0,0,	DFDS_Fix], # existed at least from LV6.0
]

BDPW_SectionDef = [
 ["BDPW",	1,0,0,	BDPW_Fix], # existed at least from LV6.0
]


def getFirstSection(block_names, RSRC, po):
    # Find all blocks, regardless of version we expect them in
    all_sections = []
    for block_name in block_names:
        all_sections += RSRC.findall("./"+block_name+"/Section")
    if len(all_sections) > 0:
        return all_sections[0]
    return None

def getVersionElement(RSRC, po):
    # Get LV version
    # Find all blocks, regardless of version we expect them in
    all_sections = []
    for sec_name in ("LVSR", "vers", "LVIN",):
        all_sections += RSRC.findall("./"+sec_name+"/Section/Version")
    ver_elem = None
    if len(all_sections) > 0:
        #TODO get mostly used version instead of first one
        ver_elem = all_sections[0]
    if ver_elem is None:
        ver_elem = ET.Element("Version")
        # TODO figure out by existing tags, hard-coding only as last resort
        ver_elem.set("Major", "14")
        ver_elem.set("Minor", "0")
        ver_elem.set("Bugfix", "0")
        ver_elem.set("Stage", "release")
        ver_elem.set("Build", "36")
        ver_elem.set("Flags", "0x0")
    return ver_elem

def versionGreaterOrEq(ver, major,minor,bugfix):
    ver_major = int(ver.get("Major"), 0)
    if ver_major < major: return False
    ver_minor = int(ver.get("Minor"), 0)
    if ver_minor < minor: return False
    ver_bugfix = int(ver.get("Bugfix"), 0)
    if ver_bugfix < bugfix: return False
    return True

def getOrMakeSection(section_def, RSRC, ver, po):
    # Find all blocks, regardless of version we expect them in
    all_sections = []
    for sec_d in section_def:
        all_sections += RSRC.findall("./"+sec_d[0]+"/Section")
    if len(all_sections) > 1:
        if (po.verbose > 0):
            eprint("{:s}: Warning: Multiple sections for block <{}> were found"\
              .format(po.xml,section_def[0][0]))
    if len(all_sections) > 0:
        #TODO what if the section doesn't match the version?
        return all_sections[0]
    for sec_d in reversed(section_def):
        if versionGreaterOrEq(ver, sec_d[1],sec_d[2],sec_d[3]):
            break
    if (po.verbose > 0):
        print("{:s}: No sections found for block <{}>, making new one"\
          .format(po.xml,sec_d[0]))
    block_elem = ET.SubElement(RSRC,sec_d[0])
    section_elem = ET.SubElement(block_elem,"Section")
    section_elem.set("Index","0")
    section_elem.set("Format","inline")
    return section_elem

def getOrMakeSectionVersion(section_def, RSRC, ver, po):
    # Find all blocks, regardless of version we expect them in
    all_sections = []
    for sec_d in section_def:
        all_sections += RSRC.findall("./"+sec_d[0]+"/Section")
    # 'vers' can have multiple sections - no warning if it does
    if len(all_sections) > 0:
        #TODO select best instead of first
        return all_sections[0]
    for sec_d in reversed(section_def):
        if versionGreaterOrEq(ver, sec_d[1],sec_d[2],sec_d[3]):
            break
    if (po.verbose > 0):
        print("{:s}: No sections found for block <{}>, making new one"\
          .format(po.xml,sec_d[0]))
    block_elem = ET.SubElement(RSRC,sec_d[0])
    section_elem = ET.SubElement(block_elem,"Section")
    section_elem.set("Index","0")
    section_elem.set("Format","inline")
    return section_elem

def fixSection(section_def, RSRC, section_elem, ver, po):
    fo = 1 * [None]
    fo[FUNC_OPTS.changed] = False
    for sec_d in reversed(section_def):
        if versionGreaterOrEq(ver, sec_d[1],sec_d[2],sec_d[3]):
            break
    fixFunc = sec_d[4]
    if fixFunc is None:
        if (po.verbose > 0):
            print("{:s}: Block <{}> section has no fixer"\
              .format(po.xml,sec_d[0]))
        return False
    changed = fixFunc(RSRC, section_elem, ver, fo, po)
    if changed:
        if (po.verbose > 0):
            print("{:s}: Block <{}> section updated"\
              .format(po.xml,sec_d[0]))
    else:
        if (po.verbose > 0):
            print("{:s}: Block <{}> section already valid"\
              .format(po.xml,sec_d[0]))
    return fo[FUNC_OPTS.changed]

def makeUidsUnique(FPHP, BDHP, ver, fo, po):
    """ Makes 'uid' values unique in FP and BD

    Removes references to invalid 'uid's from the tree.
    """
    # Prepare list of all elements with 'uid's
    elems = []
    for root in (FPHP, BDHP,):
        elems.extend(root.findall(".//*[@uid]"))
    # List elements in which 'uid's are not unique
    not_unique_elems = []
    for xpath in ("./SL__rootObject/root/ddoList/SL__arrayElement","./SL__rootObject/root/conPane/cons/SL__arrayElement/ConnectionDCO"):
        not_unique_elems.extend(FPHP.findall(xpath))
    for xpath in ("./SL__rootObject/root/zPlaneList/SL__arrayElement","./SL__rootObject/root/nodeList/SL__arrayElement/termList/SL__arrayElement/dco"):
        not_unique_elems.extend(BDHP.findall(xpath))
    all_used_uids = set()
    for elem in elems:
        uidStr = elem.get("uid")
        if representsInt(uidStr):
            uid = int(uidStr,0)
            all_used_uids.add(uid)
    used_uids = set()
    used_uids.add(0)
    for elem in elems:
        # Skip elems which we do not expect to be unique
        if elem in not_unique_elems:
            continue
        uidStr = elem.get("uid")
        if representsInt(uidStr):
            uid = int(uidStr,0)
            isCorrect = (uid not in used_uids)
        else:
            uid = max(used_uids)
            isCorrect = False
        if not isCorrect:
            while uid in all_used_uids:
                uid += 1
            elem.set("uid", str(uid))
            fo[FUNC_OPTS.changed] = True
        used_uids.add(uid)
        all_used_uids.add(uid)
    # Now make sure that non-unique elems are not unique
    # First, create a map to help in getting parents of elements
    parent_map = {}
    parent_map.update({c:p for p in FPHP.iter( ) for c in p})
    parent_map.update({c:p for p in BDHP.iter( ) for c in p})
    for elem in not_unique_elems:
        uidStr = elem.get("uid")
        if representsInt(uidStr):
            uid = int(uidStr,0)
            isCorrect = (uid in used_uids)
        else:
            uid = max(used_uids)
            isCorrect = False
        if not isCorrect:
            if (po.verbose > 1):
                print("{:s}: Found reference to non-existing uid={}, removing"\
                  .format(po.xml,uid))
            # remove the reference from tree, moving up to first array; it so happens that all
            # sub-trees which we may want to remove like that are elements of arrays
            child_elem = elem
            parent_elem = parent_map[child_elem]
            while child_elem.tag != "SL__arrayElement":
                child_elem = parent_elem
                parent_elem = parent_map[child_elem]
            parent_elem.remove(child_elem)
            fo[FUNC_OPTS.changed] = True
    # Now re-create required entries in branches which content we have in not_unique_elems
    zPlaneList_elems = FPHP.findall("./SL__rootObject/root/paneHierarchy/zPlaneList/SL__arrayElement[@class='fPDCO'][@uid]")
    # Refilling of ddoList - it should have entries for all DDOs
    ddoList = FPHP.find("./SL__rootObject/root/ddoList")
    for dco_elem in reversed(zPlaneList_elems):
        uidStr = dco_elem.get("uid")
        if representsInt(uidStr):
            uid = int(uidStr,0)
        ddoref = ddoList.find("./SL__arrayElement[@uid='{}']".format(uid))
        if ddoref is None:
            ddoref = ET.SubElement(ddoList, "SL__arrayElement")
            ddoref.set("uid",str(uid))
    # Refilling of conPane - its content should correspond to connectors in VCTP pointed to by CONP, but this data
    # is also a subset of what we have stored in 'root/paneHierarchy/zPlaneList' elements
    conPane_cons = FPHP.find("./SL__rootObject/root/conPane/cons")
    # Sort the zPlaneList elements on conNum
    zPlaneList_conNums = {}
    for elem in zPlaneList_elems:
        conNum = elem.find("./conNum")
        if conNum is not None:
            conNum = conNum.text
        if conNum is None:
            conNum = 0
        else:
            conNum = int(conNum, 0)
        zPlaneList_conNums[conNum] = elem
    # Check the content to our sorted list
    entryId = 0
    prevConNum = -1
    for conNum in sorted(zPlaneList_conNums.keys()):
        zPlaneElem = zPlaneList_conNums[conNum]
        if conNum < 0: continue

        conUid = zPlaneElem.get("uid")
        if conUid is not None:
            conUid = int(conUid, 0)
        if conUid is None:
            conUid = 0

        arrayElement = conPane_cons.find("./SL__arrayElement["+str(int(entryId+1))+"]")
        if arrayElement is None:
            arrayElement = ET.SubElement(conPane_cons, "SL__arrayElement")
            fo[FUNC_OPTS.changed] = True
        attribGetOrSetDefault(arrayElement, "class", "ConpaneConnection", fo, po)
        if conNum != prevConNum+1:
            attribGetOrSetDefault(arrayElement, "index", conNum, fo, po)

        connectionDCO = elemFindOrCreateWithAttribsAndTags(arrayElement, "ConnectionDCO", \
          ( ("uid", conUid,), ), [], fo, po)

        prevConNum = conNum
        entryId += 1


    return fo[FUNC_OPTS.changed]

def checkBlocksAvailable(root, po):
    """ Check which blocks we have, print proper messages
    """
    RSRC = root
    # Get LV version
    ver = getVersionElement(RSRC, po)
    # Update version section, if required
    vers = getOrMakeSectionVersion(vers_SectionDef, RSRC, ver, po)
    fixSection(vers_SectionDef, RSRC, vers, ver, po)

    LVSR = getOrMakeSection(LVSR_SectionDef, RSRC, ver, po)
    fixSection(LVSR_SectionDef, RSRC, LVSR, ver, po)

    VCTP = getOrMakeSection(VCTP_SectionDef, RSRC, ver, po)
    fixSection(VCTP_SectionDef, RSRC, VCTP, ver, po)

    DTHP = getOrMakeSection(DTHP_SectionDef, RSRC, ver, po)
    fixSection(DTHP_SectionDef, RSRC, DTHP, ver, po)

    FPHP = getOrMakeSection(FPHP_SectionDef, RSRC, ver, po)
    fixSection(FPHP_SectionDef, RSRC, FPHP, ver, po)

    LIvi = getOrMakeSection(LIvi_SectionDef, RSRC, ver, po)
    fixSection(LIvi_SectionDef, RSRC, LIvi, ver, po)

    LIfp = getOrMakeSection(LIfp_SectionDef, RSRC, ver, po)
    fixSection(LIfp_SectionDef, RSRC, LIfp, ver, po)

    DSTM = getOrMakeSection(DSTM_SectionDef, RSRC, ver, po)
    fixSection(DSTM_SectionDef, RSRC, DSTM, ver, po)

    DFDS = getOrMakeSection(DFDS_SectionDef, RSRC, ver, po)
    fixSection(DFDS_SectionDef, RSRC, DFDS, ver, po)

    BDPW = getOrMakeSection(BDPW_SectionDef, RSRC, ver, po)
    fixSection(BDPW_SectionDef, RSRC, BDPW, ver, po)

    # No BD recovery here - make dummy, disconnected section
    BDHP = ET.Element("Section")

    fo = 1 * [None]
    fo[FUNC_OPTS.changed] = False
    makeUidsUnique(FPHP, BDHP, ver, fo, po)
    recountHeapElements(RSRC, FPHP, ver, fo, po)

    pass

def parseSubXMLs(root, po):
    """ Find blocks which refer to external XMLs, and merges all into one tree.
    """
    for i, block_elem in enumerate(root):
        for k, section_elem in enumerate(block_elem):
            fmt = section_elem.get("Format")
            if fmt == "xml": # Format="xml" - the content is stored in a separate XML file
                if (po.verbose > 1):
                    print("{:s}: For Block {} section {}, reading separate XML file '{}'"\
                      .format(po.xml,block_elem.tag,section_elem.get("Index"),section_elem.get("File")))
                xml_path = os.path.dirname(po.xml)
                if len(xml_path) > 0:
                    xml_fname = xml_path + '/' + section_elem.get("File")
                else:
                    xml_fname = section_elem.get("File")
                section_tree = ET.parse(xml_fname, parser=ET.XMLParser(target=ET.CommentedTreeBuilder()))
                subroot = section_tree.getroot()
                section_elem.append(subroot)
    pass

def resaveSubXMLs(root, po):
    """ Find blocks which refer to external XMLs, and merges all into one tree.
    """
    for i, block_elem in enumerate(root):
        for k, section_elem in enumerate(block_elem):
            fmt = section_elem.get("Format")
            if fmt == "xml": # Format="xml" - the content is stored in a separate XML file
                if (po.verbose > 1):
                    print("{:s}: For Block {} section {}, storing separate XML file '{}'"\
                      .format(po.xml,block_elem.tag,section_elem.get("Index"),section_elem.get("File")))
                xml_path = os.path.dirname(po.xml)
                if len(xml_path) > 0:
                    xml_fname = xml_path + '/' + section_elem.get("File")
                else:
                    xml_fname = section_elem.get("File")
                for subroot in section_elem:
                    ET.pretty_element_tree_heap(subroot)
                    section_tree = ET.ElementTree(subroot)
                    with open(xml_fname, "wb") as xml_fh:
                        section_tree.write(xml_fh, encoding='utf-8', xml_declaration=True)
    pass

def detachSubXMLs(root, po):
    """ Find blocks which refer to external XMLs, detach the merged sub-trees.
    """
    for i, block_elem in enumerate(root):
        for k, section_elem in enumerate(block_elem):
            fmt = section_elem.get("Format")
            if fmt == "xml": # Format="xml" - the content is stored in a separate XML file
                for subroot in section_elem:
                    section_elem.remove(subroot)
    pass

def main():
    """ Main executable function.

    Its task is to parse command line options and call a function which performs requested command.
    """
    # Parse command line options

    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('-m', '--xml', default="", type=str,
            help="name of the main XML file of extracted VI dataset")

    parser.add_argument('-v', '--verbose', action='count', default=0,
            help="increases verbosity level; max level is set by -vvv")

    parser.add_argument('--drop-section', action='append', type=str,
            help="name a section to drop just after XML loading")

    subparser = parser.add_mutually_exclusive_group(required=True)

    subparser.add_argument('-f', '--fix', action='store_true',
            help="fix the file")

    subparser.add_argument('--version', action='version', version="%(prog)s {version} by {author}"
              .format(version=__version__,author=__author__),
            help="display version information and exit")

    po = parser.parse_args()

    # Store base name - without path and extension
    if len(po.xml) > 0:
        po.filebase = os.path.splitext(os.path.basename(po.xml))[0]
    else:
        raise FileNotFoundError("Input XML file was not provided.")

    if po.fix:

        if (po.verbose > 0):
            print("{}: Starting XML file parse for RSRC fix".format(po.xml))
        tree = ET.parse(po.xml, parser=ET.XMLParser(target=ET.CommentedTreeBuilder()))
        root = tree.getroot()
        if po.drop_section is not None:
            for blkIdent in po.drop_section:
                sub_elem = root.find("./"+blkIdent)
                if sub_elem is not None:
                    root.remove(sub_elem)
        parseSubXMLs(root, po)

        checkBlocksAvailable(root, po)

        resaveSubXMLs(root, po)
        detachSubXMLs(root, po)
        ET.pretty_element_tree_heap(root)
        with open(po.xml, "wb") as xml_fh:
            tree.write(xml_fh, encoding='utf-8', xml_declaration=True)

    else:

        raise NotImplementedError("Unsupported command.")

if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        eprint("Error: "+str(ex))
        raise
        sys.exit(10)

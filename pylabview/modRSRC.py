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
import copy
from types import SimpleNamespace
from PIL import Image

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
      aeImageResID=None, aeFgColor=None, aeBgColor=None, aeRefListLength=None, \
      aeHGrowNodeListLength=None):

    assert parent is not None

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

    if aeRefListLength is not None:
        refListLength = elemFindOrCreate(arrayElement, "refListLength", fo, po)
        elemTextGetOrSetDefault(refListLength, aeRefListLength, fo, po)

    if aeHGrowNodeListLength is not None:
        hGrowNodeListLength = elemFindOrCreate(arrayElement, "hGrowNodeListLength", fo, po)
        elemTextGetOrSetDefault(hGrowNodeListLength, aeHGrowNodeListLength, fo, po)

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

def getConsolidatedTopTypeAndID(RSRC, typeID, po, VCTP=None):
    if VCTP is None:
        VCTP = RSRC.find("./VCTP/Section")
    if VCTP is None:
        return None, None
    VCTP_TopTypeDesc = VCTP.find("./TopLevel/TypeDesc[@Index='{}']".format(typeID))
    if VCTP_TopTypeDesc is None:
        return None, None
    VCTP_FlatTypeID = VCTP_TopTypeDesc.get("FlatTypeID")
    if VCTP_FlatTypeID is None:
        return None, None
    VCTP_FlatTypeID = int(VCTP_FlatTypeID, 0)
    VCTP_FlatTypeDesc = VCTP.find("./TypeDesc["+str(VCTP_FlatTypeID+1)+"]")
    return VCTP_FlatTypeDesc, VCTP_FlatTypeID

def getConsolidatedTopType(RSRC, typeID, po, VCTP=None):
    VCTP_FlatTypeDesc, _ = getConsolidatedTopTypeAndID(RSRC, typeID, po, VCTP=VCTP)
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
      "UnitFloat32", "UnitFloat64", "UnitFloatExt",):
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


def elemCheckOrCreate_paneHierarchy_content(paneHierarchy, fo, po, aeObjFlags=None, \
          aeHowGrow=None, aeBounds=None, hasParts=False, aePaneFlags=None, aeMinPaneSize=None, \
          aeOrigin=None, aeDocBounds=None, hasZPlane=True, aeImageResID=None):
    """ Fils content of pre-created paneHierarchy tag
    """
    if aeObjFlags is not None:
        ph_objFlags = elemFindOrCreate(paneHierarchy, "objFlags", fo, po)
        objFlags_val = elemTextGetOrSetDefault(ph_objFlags, aeObjFlags, fo, po)

    if aeHowGrow is not None:
        ph_howGrow = elemFindOrCreate(paneHierarchy, "howGrow", fo, po)
        elemTextGetOrSetDefault(ph_howGrow, aeHowGrow, fo, po)

    if aeBounds is not None:
        ph_bounds = elemFindOrCreate(paneHierarchy, "bounds", fo, po)
        elemTextGetOrSetDefault(ph_bounds, aeBounds, fo, po)

    if hasParts:
        ph_partsList = elemFindOrCreate(paneHierarchy, "partsList", fo, po)
        attribGetOrSetDefault(ph_partsList, "elements", 0, fo, po)

    if aePaneFlags is not None:
        ph_paneFlags = elemFindOrCreate(paneHierarchy, "paneFlags", fo, po)
        elemTextGetOrSetDefault(ph_paneFlags, aePaneFlags, fo, po)

    if aeMinPaneSize is not None:
        ph_minPaneSize = elemFindOrCreate(paneHierarchy, "minPaneSize", fo, po)
        elemTextGetOrSetDefault(ph_minPaneSize, aeMinPaneSize, fo, po)

    if aeOrigin is not None:
        ph_origin = elemFindOrCreate(paneHierarchy, "origin", fo, po)
        elemTextGetOrSetDefault(ph_origin, aeOrigin, fo, po)

    if aeDocBounds is not None:
        ph_docBounds = elemFindOrCreate(paneHierarchy, "docBounds", fo, po)
        elemTextGetOrSetDefault(ph_docBounds, aeDocBounds, fo, po)

    ph_zPlaneList = None
    if hasZPlane:
        ph_zPlaneList = elemFindOrCreate(paneHierarchy, "zPlaneList", fo, po)
        attribGetOrSetDefault(ph_zPlaneList, "elements", 0, fo, po)

    if aeImageResID is not None:
        ph_image = elemFindOrCreate(paneHierarchy, "image", fo, po)
        attribGetOrSetDefault(ph_image, "class", "Image", fo, po)

        ph_image_ImageResID = elemFindOrCreate(ph_image, "ImageResID", fo, po)
        elemTextGetOrSetDefault(ph_image_ImageResID, aeImageResID, fo, po)

    return ph_zPlaneList, ph_partsList, objFlags_val

def elemCheckOrCreate_ddo_content(ddo, fo, po, aeDdoObjFlags=None, aeBounds=None, \
          hasParts=False, aeDdoTypeID=None, aeMouseWheelSupport=None, aeMinButSize=None, \
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
    if hasParts:
        partsList = elemFindOrCreate(ddo, "partsList", fo, po)
        attribGetOrSetDefault(partsList, "elements", 0, fo, po)

    if aeDdoTypeID is not None:
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

def elemCheckOrCreate_zPlaneList_arrayElement_DDO(parent, fo, po, aeClass="fPDCO", \
          aeTypeID=1, aeObjFlags=None, aeDdoClass="stdNum", aeConNum=None, \
          aeTermListLength=None):
    """ Creates ArrayElement for top level controls
    """
    searchTags = []
    searchTags.append( ("typeDesc", "TypeID({})".format(aeTypeID),) )
    arrayElement = elemFindOrCreateWithAttribsAndTags(parent, "SL__arrayElement", \
      ( ("class", aeClass,), ), searchTags, fo, po)
    attribGetOrSetDefault(arrayElement, "class", aeClass, fo, po)
    attribGetOrSetDefault(arrayElement, "uid", 1, fo, po)

    if aeObjFlags is not None:
        objFlags = elemFindOrCreate(arrayElement, "objFlags", fo, po, pos=0)
        elemTextGetOrSetDefault(objFlags, aeObjFlags, fo, po)

    if aeTypeID is not None:
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

def elemCheckOrCreate_zPlaneList_arrayElement(parent, fo, po, aeClass="fPDCO", \
          aeTypeID=1, aeObjFlags=None, aeDdoClass="stdNum", aeConNum=None, \
          aeTermListLength=None):
    """ Creates ArrayElement for nested controls, which are not stand-alone DCOs
    """
    searchTags = []
    searchTags.append( ("typeDesc", "TypeID({})".format(aeTypeID),) )
    arrayElement = elemFindOrCreateWithAttribsAndTags(parent, "SL__arrayElement", \
      ( ("class", aeDdoClass,), ), searchTags, fo, po)
    attribGetOrSetDefault(arrayElement, "class", aeDdoClass, fo, po)
    attribGetOrSetDefault(arrayElement, "uid", 1, fo, po)

    return arrayElement, arrayElement

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

def checkOrCreateParts_RootPane(RSRC, partsList, parentObjFlags, labelText, fo, po):
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

def checkOrCreateParts_ClusterPane(RSRC, partsList, parentObjFlags, labelText, corSz, fo, po):
    """ Checks content of the 'ddo/paneHierarchy/partsList' element for Cluster DCO
    """
    # NAME_LABEL properties taken from empty VI file created in LV14
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1511754, aeMasterPart=PARTID.CONTENT_AREA, aeHowGrow=4096,
      aeBounds=[0,0,15,27], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 1028, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\""+labelText+"\"", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "bgColor", fo, po), "{:08X}".format(0x01000000), fo, po)

    # Y_SCROLLBAR properties taken from empty VI file created in LV14
    objFlags = 0x0d72
    if True: # if vert scrollbar marked as disabled
        objFlags |= 0x1000 | 0x0008 | 0x0004
    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.Y_SCROLLBAR, aeObjFlags=objFlags, aeMasterPart=PARTID.CONTENT_AREA, aeHowGrow=194, \
      aeBounds=[0,corSz[1]-8,corSz[0]-25,corSz[1]+8], aeImageResID=0, aeBgColor=0x00B3B3B3)

    # X_SCROLLBAR properties taken from empty VI file created in LV14
    objFlags = 0x1d72
    if True: # if horiz scrollbar marked as disabled
        objFlags |= 0x1000 | 0x0008 | 0x0004
    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.X_SCROLLBAR, aeObjFlags=objFlags, aeMasterPart=PARTID.CONTENT_AREA, aeHowGrow=56, \
      aeBounds=[corSz[0]-25,0,corSz[0]-9,corSz[1]-8], aeImageResID=0, aeBgColor=0x00B3B3B3)

    objFlags = 0x1d73
    if True: # if horiz scrollbar marked as disabled
        objFlags |= 0x1000 | 0x0008 | 0x0004
    # EXTRA_FRAME_PART properties taken from empty VI file created in LV14
    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.EXTRA_FRAME_PART, aeObjFlags=objFlags, aeMasterPart=PARTID.CONTENT_AREA, aeHowGrow=4096,
      aeBounds=[corSz[0]-25,corSz[1]-8,corSz[0]-9,corSz[1]+8], aeImageResID=-365, aeFgColor=0x00B3B3B3, aeBgColor=0x00B3B3B3)

    # CONTENT_AREA properties taken from empty VI file created in LV14
    contentArea = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.CONTENT_AREA, aeObjFlags=4211, aeMasterPart=None, aeHowGrow=120, \
      aeBounds=[0,0,corSz[0]-25,corSz[1]-8], aeImageResID=-704, aeFgColor=0x00969696, aeBgColor=0x00B3B3B3)

    # ANNEX properties taken from empty VI file created in LV14
    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="annex", \
      aePartID=PARTID.ANNEX, aeRefListLength=0, aeHGrowNodeListLength=0)

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

    aeObjFlags = 0x1937
    if (parentObjFlags & 0x01) != 0:
        aeObjFlags &= ~0x1000
    boolGlyph = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.BOOLEAN_SHADOW, aeObjFlags=aeObjFlags, aeMasterPart=PARTID.BOOLEAN_BUTTON, aeHowGrow=3840, \
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

    aeObjFlags = 0x1937
    if (parentObjFlags & 0x01) != 0 or True: # This whole function is for indicators
        aeObjFlags &= ~0x1000
    boolGlyph = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.BOOLEAN_GLYPH, aeObjFlags=aeObjFlags, aeMasterPart=PARTID.BOOLEAN_BUTTON, aeHowGrow=3840, \
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

def checkOrCreateParts_stdString_control(RSRC, partsList, parentObjFlags, labelText, fo, po):
    """ Checks content of partsList element of String Control type
    """
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1507654, aeMasterPart=PARTID.FRAME, aeHowGrow=4096,
      aeBounds=[0,0,15,40], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 17412, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\""+labelText+"\"", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "bgColor", fo, po), "{:08X}".format(0x01000000), fo, po)

    strRadix = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="multiCosm", \
      aePartID=PARTID.RADIX, aeObjFlags=6458, aeMasterPart=PARTID.FRAME, aeHowGrow=4104, \
      aeBounds=[21,4,33,10], aeImageResID=None, aeFgColor=0x00D9DADC, aeBgColor=0x007586A0)
    strRadix_table = elemFindOrCreate(strRadix, "table", fo, po)
    attribGetOrSetDefault(strRadix_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElementImg(strRadix_table, fo, po, aeClass="Image", aeImageResID=-2104, parentPos=1)
    elemCheckOrCreate_table_arrayElementImg(strRadix_table, fo, po, aeClass="Image", aeImageResID=-2105, parentPos=2)
    elemCheckOrCreate_table_arrayElementImg(strRadix_table, fo, po, aeClass="Image", aeImageResID=-2106, parentPos=3)
    elemCheckOrCreate_table_arrayElementImg(strRadix_table, fo, po, aeClass="Image", aeImageResID=-2107, parentPos=4)

    strRadixSh = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="multiCosm", \
      aePartID=PARTID.RADIX_SHADOW, aeObjFlags=6458, aeMasterPart=PARTID.FRAME, aeHowGrow=4288, \
      aeBounds=[19,4,36,10], aeImageResID=None, aeFgColor=0x007586A0, aeBgColor=0x007586A0)
    strRadixSh_table = elemFindOrCreate(strRadixSh, "table", fo, po)
    attribGetOrSetDefault(strRadixSh_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElementImg(strRadixSh_table, fo, po, aeClass="Image", aeImageResID=-2104, parentPos=1)
    elemCheckOrCreate_table_arrayElementImg(strRadixSh_table, fo, po, aeClass="Image", aeImageResID=-2105, parentPos=2)
    elemCheckOrCreate_table_arrayElementImg(strRadixSh_table, fo, po, aeClass="Image", aeImageResID=-2106, parentPos=3)
    elemCheckOrCreate_table_arrayElementImg(strRadixSh_table, fo, po, aeClass="Image", aeImageResID=-2107, parentPos=4)

    aeObjFlags = 0x1932 # 6450
    if (parentObjFlags & 0x01) != 0:
        aeObjFlags &= ~0x1000
    strText = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.TEXT, aeObjFlags=aeObjFlags, aeMasterPart=PARTID.FRAME, aeHowGrow=240, \
      aeBounds=[21,4,36,96], aeImageResID=-239, aeFgColor=0x00FAFAFA, aeBgColor=0x00FAFAFA)
    strText_textRec = elemFindOrCreate(strText, "textRec", fo, po)
    attribGetOrSetDefault(strText_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(strText_textRec, "mode", fo, po), 8389636, fo, po)
    #elemTextGetOrSetDefault(elemFindOrCreate(strText_textRec, "text", fo, po), "\""+strValue+"\"", fo, po) # TODO maybe fill default value?
    elemTextGetOrSetDefault(elemFindOrCreate(strText_textRec, "bgColor", fo, po), "{:08X}".format(0x00FAFAFA), fo, po)

    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.FRAME, aeObjFlags=2327, aeMasterPart=None, aeHowGrow=240, \
      aeBounds=[17,0,40,100], aeImageResID=-412, aeFgColor=0x00B3B3B3, aeBgColor=0x01000000)

    annexPart = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="annex", \
      aePartID=PARTID.ANNEX)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "refListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "hGrowNodeListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "rsrcID", fo, po), 21701, fo, po)
    if (parentObjFlags & 0x01) == 0:
        elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "annexDDOFlag", fo, po), 2, fo, po)

    return strText

def checkOrCreateParts_stdString_indicator(RSRC, partsList, parentObjFlags, labelText, fo, po):
    """ Checks content of partsList element of String Indicator type
    """
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1507654, aeMasterPart=PARTID.FRAME, aeHowGrow=4096,
      aeBounds=[0,0,15,40], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 17412, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\""+labelText+"\"", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "bgColor", fo, po), "{:08X}".format(0x01000000), fo, po)

    strRadix = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="multiCosm", \
      aePartID=PARTID.RADIX, aeObjFlags=6458, aeMasterPart=PARTID.FRAME, aeHowGrow=4104, \
      aeBounds=[21,4,33,10], aeImageResID=None, aeFgColor=0x00D9DADC, aeBgColor=0x007586A0)
    strRadix_table = elemFindOrCreate(strRadix, "table", fo, po)
    attribGetOrSetDefault(strRadix_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElementImg(strRadix_table, fo, po, aeClass="Image", aeImageResID=-2104, parentPos=1)
    elemCheckOrCreate_table_arrayElementImg(strRadix_table, fo, po, aeClass="Image", aeImageResID=-2105, parentPos=2)
    elemCheckOrCreate_table_arrayElementImg(strRadix_table, fo, po, aeClass="Image", aeImageResID=-2106, parentPos=3)
    elemCheckOrCreate_table_arrayElementImg(strRadix_table, fo, po, aeClass="Image", aeImageResID=-2107, parentPos=4)

    strRadixSh = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="multiCosm", \
      aePartID=PARTID.RADIX_SHADOW, aeObjFlags=6458, aeMasterPart=PARTID.FRAME, aeHowGrow=4288, \
      aeBounds=[19,4,36,10], aeImageResID=None, aeFgColor=0x007586A0, aeBgColor=0x007586A0)
    strRadixSh_table = elemFindOrCreate(strRadixSh, "table", fo, po)
    attribGetOrSetDefault(strRadixSh_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElementImg(strRadixSh_table, fo, po, aeClass="Image", aeImageResID=-2104, parentPos=1)
    elemCheckOrCreate_table_arrayElementImg(strRadixSh_table, fo, po, aeClass="Image", aeImageResID=-2105, parentPos=2)
    elemCheckOrCreate_table_arrayElementImg(strRadixSh_table, fo, po, aeClass="Image", aeImageResID=-2106, parentPos=3)
    elemCheckOrCreate_table_arrayElementImg(strRadixSh_table, fo, po, aeClass="Image", aeImageResID=-2107, parentPos=4)

    aeObjFlags = 0x1932 # 6450
    if (parentObjFlags & 0x01) != 0 or True: # this function is for indicators, so always clear the flag
        aeObjFlags &= ~0x1000
    strText = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.TEXT, aeObjFlags=aeObjFlags, aeMasterPart=PARTID.FRAME, aeHowGrow=240, \
      aeBounds=[21,4,36,96], aeImageResID=-239, aeFgColor=0x00D2D2D2, aeBgColor=0x00D2D2D2)
    strText_textRec = elemFindOrCreate(strText, "textRec", fo, po)
    attribGetOrSetDefault(strText_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(strText_textRec, "mode", fo, po), 8389636, fo, po)
    #elemTextGetOrSetDefault(elemFindOrCreate(strText_textRec, "text", fo, po), "\""+strValue+"\"", fo, po) # TODO maybe fill default value?
    elemTextGetOrSetDefault(elemFindOrCreate(strText_textRec, "bgColor", fo, po), "{:08X}".format(0x00D2D2D2), fo, po)

    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.FRAME, aeObjFlags=2327, aeMasterPart=None, aeHowGrow=240, \
      aeBounds=[17,0,40,100], aeImageResID=-412, aeFgColor=0x00B3B3B3, aeBgColor=0x01000000)

    annexPart = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="annex", \
      aePartID=PARTID.ANNEX)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "refListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "hGrowNodeListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "rsrcID", fo, po), 21702, fo, po)

    return strRadix

def checkOrCreateParts_stdClust_control(RSRC, partsList, parentObjFlags, labelText, corSz, fo, po):
    """ Checks content of partsList element of Cluster Control/Indicator type
    """
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1507654, aeMasterPart=PARTID.FRAME, aeHowGrow=4096,
      aeBounds=[0,0,15,corSz[1]], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "flags", fo, po), 1536, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 17412, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\""+labelText+"\"", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "bgColor", fo, po), "{:08X}".format(0x01000000), fo, po)

    contentArea = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.CONTENT_AREA, aeObjFlags=2359, aeMasterPart=PARTID.FRAME, aeHowGrow=240, \
      aeBounds=[21,4,corSz[0]-4,corSz[1]-4], aeImageResID=0, aeFgColor=0x00A6A6A6, aeBgColor=0x00A6A6A6)

    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.FRAME, aeObjFlags=2327, aeMasterPart=None, aeHowGrow=240, \
      aeBounds=[17,0,corSz[0],corSz[1]], aeImageResID=-412, aeFgColor=0x00B3B3B3, aeBgColor=0x01000000)

    # ANNEX properties taken from empty VI file created in LV14
    annexPart = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="annex", \
      aePartID=PARTID.ANNEX)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "refListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "hGrowNodeListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "rsrcID", fo, po), 21607, fo, po)

    return contentArea


def FPHb_elemCheckOrCreate_zPlaneList_DCO_size(RSRC, fo, po, heapTypeMap, corTL, fpClass, dcoName, \
      dcoTypeID, partTypeIDs, ddoTypeID, subTypeIDs, isIndicator):
    """ Gives expected size of the GUI element representing given types
    """
    dcoTypeDesc = None
    if dcoTypeID is not None and dcoTypeID in heapTypeMap.keys():
        dcoTypeDesc = heapTypeMap[dcoTypeID]
    if dcoTypeDesc is None:
        corBR = [corTL[0],corTL[1]]
    elif fpClass == "stdBool" and isIndicator == 0:
        corBR = [corTL[0]+48,corTL[1]+60]
    elif fpClass == "stdBool" and isIndicator != 0:
        corBR = [corTL[0]+38,corTL[1]+50]
    elif fpClass == "stdNum":
        corBR = [corTL[0]+38,corTL[1]+41]
    elif fpClass == "stdString":
        corBR = [corTL[0]+40,corTL[1]+100]
    elif fpClass == "stdClust":
        corBR = [corTL[0]+4,corTL[1]+4]
        corBR1 = corBR[1]
        for subTypeID in subTypeIDs:
            fpSubClass, dcoSubName = DCO_recognize_fpClass_dcoName_from_dcoTypeID(RSRC, fo, po, subTypeID)
            corBR_end = FPHb_elemCheckOrCreate_zPlaneList_DCO_size(RSRC, fo, po, heapTypeMap, \
                  corBR, fpSubClass, dcoSubName, subTypeID, [], subTypeID, [], isIndicator)
            corBR = [corBR_end[0],corBR[1]]
            corBR1 = max(corBR1,corBR_end[1])
        corBR = [corBR[0]+4,corBR1+4]
    else:
        corBR = [corTL[0],corTL[1]]
    return corBR

def FPHb_elemCheckOrCreate_zPlaneList_DCO(RSRC, paneHierarchy_zPlaneList, fo, po, \
      heapTypeMap, corTL, defineDDO, fpClass, dcoName, \
      dcoTypeID, partTypeIDs, ddoTypeID, subTypeIDs, dcoConNum, isIndicator, dataSrcIdent):
    """ Checks or creates Front Panel componennt which represents specific DCO
    """
    typeCtlOrInd = "indicator" if isIndicator != 0 else "control"
    dcoTypeDesc = None
    if dcoTypeID is not None and dcoTypeID in heapTypeMap.keys():
        dcoTypeDesc = heapTypeMap[dcoTypeID]
    if dcoTypeDesc is None:
        eprint("{:s}: Warning: {} does not have dcoTypeID, not adding to FP"\
          .format(po.xml,dataSrcIdent))
        return None, None

    print("{:s}: Associating {} TypeDesc '{}' with FpDCO {} of class '{}'"\
      .format(po.xml,dataSrcIdent,dcoTypeDesc.get("Type"),typeCtlOrInd,fpClass))

    ddoTypeDesc = None
    if ddoTypeID is not None:
        ddoTypeDesc = heapTypeMap[ddoTypeID]

    labelText = dcoTypeDesc.get("Label")
    if fpClass == "stdBool":
        dcoObjFlags_val = 0x10200
        ddoObjFlags_val = 0 # 0x1: user input disabled
        if isIndicator != 0:
            dcoObjFlags_val |= 0x01
            ddoObjFlags_val |= 0x01
        if labelText is None: labelText = "Boolean"
    elif fpClass == "stdNum":
        dcoObjFlags_val = 0
        ddoObjFlags_val = 0x60042
        if isIndicator != 0:
            dcoObjFlags_val |= 0x01
            ddoObjFlags_val |= 0x01
        if labelText is None: labelText = "Numeric"
        stdNumMin, stdNumMax, stdNumInc = valueTypeGetDefaultRange(dcoTypeDesc.get("Type"), po)
    elif fpClass == "stdString":
        dcoObjFlags_val = 0
        ddoObjFlags_val = 0x0
        if isIndicator != 0:
            dcoObjFlags_val |= 0x01
            ddoObjFlags_val |= 0x01
        if labelText is None: labelText = "String"
    elif fpClass == "stdClust":
        dcoObjFlags_val = 0
        ddoObjFlags_val = 0x00004
        if isIndicator != 0:
            dcoObjFlags_val |= 0x01
            ddoObjFlags_val |= 0x01
        if labelText is None: labelText = "Cluster"
    else:
        dcoObjFlags_val = 0
        ddoObjFlags_val = 0
        if labelText is None: labelText = "Unknown"

    ddoClass_val = fpClass
    if defineDDO:
        dco_elem, ddo_elem = elemCheckOrCreate_zPlaneList_arrayElement_DDO(paneHierarchy_zPlaneList, fo, po, aeClass="fPDCO", \
          aeTypeID=dcoTypeID, aeObjFlags=dcoObjFlags_val, aeDdoClass=ddoClass_val, aeConNum=dcoConNum, aeTermListLength=1)
    else:
        dco_elem, ddo_elem = elemCheckOrCreate_zPlaneList_arrayElement(paneHierarchy_zPlaneList, fo, po, aeClass="fPDCO", \
          aeTypeID=dcoTypeID, aeObjFlags=dcoObjFlags_val, aeDdoClass=ddoClass_val, aeConNum=dcoConNum, aeTermListLength=1)

    if fpClass == "stdBool" and isIndicator == 0:
        corBR = FPHb_elemCheckOrCreate_zPlaneList_DCO_size(RSRC, fo, po, heapTypeMap, corTL, fpClass, dcoName, dcoTypeID, partTypeIDs, ddoTypeID, subTypeIDs, isIndicator)
        ddo_partsList, _ = elemCheckOrCreate_ddo_content(ddo_elem, fo, po, aeDdoObjFlags=ddoObjFlags_val,
          aeBounds=corTL+corBR, hasParts=True, aeDdoTypeID=ddoTypeID, \
          aeMouseWheelSupport=0, aeMinButSize=[50,21], valueType=dcoTypeDesc.get("Type"))
        checkOrCreateParts_stdBool_control(RSRC, ddo_partsList, ddoObjFlags_val, labelText, fo, po)
    elif fpClass == "stdBool" and isIndicator != 0:
        corTL_mv = [corTL[0],corTL[1]+32] # Bool indicator LED is moved strongly towards the left
        corBR = FPHb_elemCheckOrCreate_zPlaneList_DCO_size(RSRC, fo, po, heapTypeMap, corTL_mv, fpClass, dcoName, dcoTypeID, partTypeIDs, ddoTypeID, subTypeIDs, isIndicator)
        ddo_partsList, _ = elemCheckOrCreate_ddo_content(ddo_elem, fo, po, aeDdoObjFlags=ddoObjFlags_val,
          aeBounds=corTL_mv+corBR, hasParts=True, aeDdoTypeID=ddoTypeID, \
          aeMouseWheelSupport=0, aeMinButSize=[17,17], valueType=dcoTypeDesc.get("Type"))
        checkOrCreateParts_stdBool_indicator(RSRC, ddo_partsList, ddoObjFlags_val, labelText, fo, po)
    elif fpClass == "stdNum" and isIndicator == 0:
        corTL_mv = [corTL[0],corTL[1]+16] # Numeric control has arrows before component bounds
        corBR = FPHb_elemCheckOrCreate_zPlaneList_DCO_size(RSRC, fo, po, heapTypeMap, corTL_mv, fpClass, dcoName, dcoTypeID, partTypeIDs, ddoTypeID, subTypeIDs, isIndicator)
        ddo_partsList, _ = elemCheckOrCreate_ddo_content(ddo_elem, fo, po, aeDdoObjFlags=ddoObjFlags_val, \
          aeBounds=corTL_mv+corBR, hasParts=True, aeDdoTypeID=ddoTypeID, \
          aeMouseWheelSupport=2, aeMinButSize=None, valueType=dcoTypeDesc.get("Type"), \
          aeStdNumMin=stdNumMin, aeStdNumMax=stdNumMax, aeStdNumInc=stdNumInc)
        checkOrCreateParts_stdNum_control(RSRC, ddo_partsList, ddoObjFlags_val, labelText, fo, po)
    elif fpClass == "stdNum" and isIndicator != 0:
        corBR = FPHb_elemCheckOrCreate_zPlaneList_DCO_size(RSRC, fo, po, heapTypeMap, corTL, fpClass, dcoName, dcoTypeID, partTypeIDs, ddoTypeID, subTypeIDs, isIndicator)
        ddo_partsList, _ = elemCheckOrCreate_ddo_content(ddo_elem, fo, po, aeDdoObjFlags=ddoObjFlags_val, \
          aeBounds=corTL+corBR, hasParts=True, aeDdoTypeID=ddoTypeID, \
          aeMouseWheelSupport=2, aeMinButSize=None, valueType=dcoTypeDesc.get("Type"), \
          aeStdNumMin=stdNumMin, aeStdNumMax=stdNumMax, aeStdNumInc=stdNumInc)
        checkOrCreateParts_stdNum_indicator(RSRC, ddo_partsList, ddoObjFlags_val, labelText, fo, po)
    elif fpClass == "stdString" and isIndicator == 0:
        corBR = FPHb_elemCheckOrCreate_zPlaneList_DCO_size(RSRC, fo, po, heapTypeMap, corTL, fpClass, dcoName, dcoTypeID, partTypeIDs, ddoTypeID, subTypeIDs, isIndicator)
        ddo_partsList, _ = elemCheckOrCreate_ddo_content(ddo_elem, fo, po, aeDdoObjFlags=ddoObjFlags_val, \
          aeBounds=corTL+corBR, hasParts=True, aeDdoTypeID=ddoTypeID, \
          aeMouseWheelSupport=3, aeMinButSize=None, valueType=dcoTypeDesc.get("Type"))
        checkOrCreateParts_stdString_control(RSRC, ddo_partsList, ddoObjFlags_val, labelText, fo, po)
    elif fpClass == "stdString" and isIndicator != 0:
        corBR = FPHb_elemCheckOrCreate_zPlaneList_DCO_size(RSRC, fo, po, heapTypeMap, corTL, fpClass, dcoName, dcoTypeID, partTypeIDs, ddoTypeID, subTypeIDs, isIndicator)
        ddo_partsList, _ = elemCheckOrCreate_ddo_content(ddo_elem, fo, po, aeDdoObjFlags=ddoObjFlags_val, \
          aeBounds=corTL+corBR, hasParts=True, aeDdoTypeID=ddoTypeID, \
          aeMouseWheelSupport=3, aeMinButSize=None, valueType=dcoTypeDesc.get("Type"))
        checkOrCreateParts_stdString_indicator(RSRC, ddo_partsList, ddoObjFlags_val, labelText, fo, po)
    elif fpClass == "stdClust": # Same code for Control and indicator
        corTL_mv = [corTL[0],corTL[1]+4] # Cluster panel frame
        corBR = FPHb_elemCheckOrCreate_zPlaneList_DCO_size(RSRC, fo, po, heapTypeMap, corTL_mv, fpClass, dcoName, dcoTypeID, partTypeIDs, ddoTypeID, subTypeIDs, isIndicator)
        corSz = [corBR[0]-corTL_mv[0]+21, corBR[1]-corTL_mv[1]+12]
        ddo_partsList, ddo_paneHierarchy = elemCheckOrCreate_ddo_content(ddo_elem, fo, po, aeDdoObjFlags=ddoObjFlags_val, \
          aeBounds=corTL_mv+[corBR[0]+21,corBR[1]], hasParts=True, aeDdoTypeID=ddoTypeID, \
          aeMouseWheelSupport=0, aeMinButSize=None, valueType=dcoTypeDesc.get("Type"), aeSavedSize=[0,0,0,0])
        checkOrCreateParts_stdClust_control(RSRC, ddo_partsList, ddoObjFlags_val, labelText, corSz, fo, po)
        ddo_ph_zPlaneList, ddo_ph_partsList, ddo_ph_objFlags_val = \
              elemCheckOrCreate_paneHierarchy_content(ddo_paneHierarchy, fo, po,
              aeObjFlags=2494736, aeHowGrow=240, aeBounds=[21,4,corSz[0]-4,corSz[1]-4], hasParts=True,
              aePaneFlags=257, aeMinPaneSize=[1,1], aeOrigin=[-4,-4],
              aeDocBounds=[corSz[0]-62,-21,corSz[0]-62-60,corSz[1]+21], hasZPlane=True, aeImageResID=0)
        # Content of the 'paneHierarchy/partsList' element
        paneContent = checkOrCreateParts_ClusterPane(RSRC, ddo_ph_partsList, ddo_ph_objFlags_val, "Pane", corSz, fo, po)
        # Content of the 'paneHierarchy/zPlaneList' element
        corCtBL = [corBR[0]-corTL_mv[0]-21, corTL_mv[1]-4]
        corCtBL = [corCtBL[0]-4, corCtBL[1]]
        for subTypeID in subTypeIDs:
            fpSubClass, dcoSubName = DCO_recognize_fpClass_dcoName_from_dcoTypeID(RSRC, fo, po, subTypeID)
            corBR = FPHb_elemCheckOrCreate_zPlaneList_DCO_size(RSRC, fo, po, heapTypeMap, [0,0], fpSubClass, dcoSubName, \
                  dcoTypeID=subTypeID, partTypeIDs=[], ddoTypeID=subTypeID, subTypeIDs=[], isIndicator=isIndicator)
            corCtBL = [corCtBL[0]-corBR[0], corCtBL[1]]
            corCtBL_mv = [corCtBL[0], corCtBL[1]] # Make a copy to be sure coords are not modified by the function
            FPHb_elemCheckOrCreate_zPlaneList_DCO(RSRC, ddo_ph_zPlaneList, fo, po, heapTypeMap, corCtBL_mv, \
                  defineDDO=False, fpClass=fpSubClass, dcoName=dcoSubName, dcoTypeID=subTypeID, partTypeIDs=[], \
                  ddoTypeID=subTypeID, subTypeIDs=[], dcoConNum=dcoConNum, isIndicator=isIndicator, \
                  dataSrcIdent="{}.{}".format(dataSrcIdent,dcoTypeDesc.get("Type")))
    else:
        #TODO add more types
        corBR = [corTL[0],corTL[1]]
        dco_elem = None
        ddo_partsList = None
        eprint("{:s}: Warning: Heap DCO '{}' creation from dcoTypeDesc '{}' {} is not supported"\
          .format(po.xml,fpClass,dcoTypeDesc.get("Type"),typeCtlOrInd))

    if defineDDO: # DDO level - order components horizontally
        if corBR[0] < 1066: # TODO this needs to be done without hard-coding width
            corTL[1] = corBR[1]
        else:
            corTL[1] = 0
            corTL[0] = corBR[0]
    else: # Nested levels - order components vertically
        if corBR[1] < 720: # TODO this needs to be done without hard-coding height
            corTL[0] = corBR[0]
        else:
            corTL[0] = 0
            corTL[1] = corBR[1]

    return dco_elem, ddo_partsList

def elemCheckOrCreate_bdroot_content(root, fo, po, aeObjFlags=None, hasPlanes=False, \
          hasNodes=False, hasSignals=False, aeBgColor=None, aeFirstNodeIdx=None,
          aeBounds=None, aeShortCount=None, aeClumpNum=None):
    """ Fils content of pre-created DDO tag
    """

    if aeObjFlags is not None:
        root_objFlags = elemFindOrCreate(root, "objFlags", fo, po, pos=0)
        elemTextGetOrSetDefault(root_objFlags, aeObjFlags, fo, po)

    zPlaneList = None
    if hasPlanes:
        zPlaneList = elemFindOrCreate(root, "zPlaneList", fo, po)
        attribGetOrSetDefault(zPlaneList, "elements", 0, fo, po)

    nodeList = None
    if hasNodes:
        nodeList = elemFindOrCreate(root, "nodeList", fo, po)
        attribGetOrSetDefault(nodeList, "elements", 0, fo, po)

    signalList = None
    if hasSignals:
        signalList = elemFindOrCreate(root, "signalList", fo, po)
        attribGetOrSetDefault(signalList, "elements", 0, fo, po)

    if aeBgColor is not None:
        bgColor = elemFindOrCreate(root, "bgColor", fo, po)
        elemTextGetOrSetDefault(bgColor, "{:08X}".format(aeBgColor), fo, po)

    if aeFirstNodeIdx is not None:
        firstNodeIdx = elemFindOrCreate(root, "firstNodeIdx", fo, po)
        elemTextGetOrSetDefault(firstNodeIdx, aeFirstNodeIdx, fo, po)

    # Now inside of the nodeList
    if nodeList is not None:
        nl_arrayElement = elemFindOrCreateWithAttribsAndTags(nodeList, "SL__arrayElement", \
          ( ("class", "sRN",), ), [], fo, po)

        if aeObjFlags is not None:
            arrayElement_objFlags = elemFindOrCreate(nl_arrayElement, "objFlags", fo, po, pos=0)
            elemTextGetOrSetDefault(arrayElement_objFlags, aeObjFlags, fo, po)

        arrayElement_termList = elemFindOrCreate(nl_arrayElement, "termList", fo, po)
        attribGetOrSetDefault(arrayElement_termList, "elements", 0, fo, po)

        if aeBounds is not None:
            arrayElement_bounds = elemFindOrCreate(nl_arrayElement, "bounds", fo, po)
            elemTextGetOrSetDefault(arrayElement_bounds, aeBounds, fo, po)

        if aeShortCount is not None:
            arrayElement_shortCount = elemFindOrCreate(nl_arrayElement, "shortCount", fo, po)
            elemTextGetOrSetDefault(arrayElement_shortCount, aeShortCount, fo, po)

        if aeClumpNum is not None:
            arrayElement_clumpNum = elemFindOrCreate(nl_arrayElement, "clumpNum", fo, po)
            elemTextGetOrSetDefault(arrayElement_clumpNum, aeClumpNum, fo, po)

    return zPlaneList, arrayElement_termList, signalList

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

    paneHierarchy_zPlaneList, paneHierarchy_partsList, paneHierarchy_objFlags_val = \
          elemCheckOrCreate_paneHierarchy_content(root_paneHierarchy, fo, po,
          aeObjFlags=objFlags, aeHowGrow=240, aeBounds=[46,0,681,1093], hasParts=True,
          aePaneFlags=331089, aeMinPaneSize=[1,1],
          aeDocBounds=[0,0,619,1077], hasZPlane=True, aeImageResID=0)

    # Now content of the 'root/paneHierarchy/partsList' element
    paneContent = checkOrCreateParts_RootPane(RSRC, paneHierarchy_partsList, paneHierarchy_objFlags_val, "Pane", fo, po)

    # Now content of the 'root/paneHierarchy/zPlaneList' element

    DTHP_typeDescSlice = RSRC.find("./DTHP/Section/TypeDescSlice")
    if DTHP_typeDescSlice is not None:
        DTHP_indexShift = DTHP_typeDescSlice.get("IndexShift")
        if DTHP_indexShift is not None:
            DTHP_indexShift = int(DTHP_indexShift, 0)
        DTHP_tdCount = DTHP_typeDescSlice.get("Count")
        if DTHP_tdCount is not None:
            DTHP_tdCount = int(DTHP_tdCount, 0)
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
    heapTypeMap = {htId+1:getConsolidatedTopType(RSRC, DTHP_indexShift+htId, po) for htId in range(DTHP_tdCount)}

    VCTP = RSRC.find("./VCTP/Section")
    if VCTP is not None:
        VCTP_TypeDescList = VCTP.findall("TopLevel/TypeDesc")
        VCTP_FlatTypeDescList = VCTP.findall("TypeDesc")
    else:
        VCTP_TypeDescList = []
        VCTP_FlatTypeDescList = []
    usedTypeID = 1 # Heap TypeID values start with 1
    # Figure out Heap Types range for each DCO
    for DCO in reversed(FpDCOList):
        dcoTDCount = 0
        DCOInfo = None
        if usedTypeID in heapTypeMap:
            dcoTDCount, DCOInfo = DCO_recognize_from_typeIDs(RSRC, fo, po, DTHP_indexShift+usedTypeID-1, DTHP_indexShift+DTHP_tdCount-1, VCTP_TypeDescList, VCTP_FlatTypeDescList)
        if DCOInfo is not None:
            # Switch typeID values to Heap Type IDs
            DCOInfo['dcoTypeID'] = DCOInfo['dcoTypeID']-DTHP_indexShift+1
            DCOInfo['partTypeIDs'] = [ typeID-DTHP_indexShift+1 for typeID in DCOInfo['partTypeIDs'] ]
            DCOInfo['ddoTypeID'] = DCOInfo['ddoTypeID']-DTHP_indexShift+1
            DCOInfo['subTypeIDs'] = [ typeID-DTHP_indexShift+1 for typeID in DCOInfo['subTypeIDs'] ]
        else:
            eprint("{:s}: Warning: Heap TypeDesc {} expected for DCO{} does not match known TD patterns"\
              .format(po.xml,usedTypeID,DCO['dcoIndex']))
            DCOInfo = { 'fpClass': "stdNum", 'dcoName': None, 'dcoTypeID': usedTypeID, 'partTypeIDs': [], 'extraTypeID': None, 'ddoTypeID': usedTypeID, 'subTypeIDs': [] }
            dcoTDCount = 1
        # Store the values inside DCO
        DCO.update(DCOInfo)
        usedTypeID += dcoTDCount

    corTL = [0,0] # Coordinates top left
    for DCO in reversed(FpDCOList):
        FPHb_elemCheckOrCreate_zPlaneList_DCO(RSRC, paneHierarchy_zPlaneList, fo, po, heapTypeMap, corTL, \
              defineDDO=True, fpClass=DCO['fpClass'], dcoName=DCO['dcoName'], dcoTypeID=DCO['dcoTypeID'], \
              partTypeIDs=DCO['partTypeIDs'], ddoTypeID=DCO['ddoTypeID'], subTypeIDs=DCO['subTypeIDs'], \
              dcoConNum=DCO['conNum'], isIndicator=DCO['isIndicator'], dataSrcIdent="DCO{}".format(DCO['dcoIndex']))

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
    BDHP = LIbd.find("BDHP")
    if BDHP is None:
        BDHP = ET.SubElement(LIbd, "BDHP")
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
        if nRng.max - nRng.min >= 0:
            nRanges.append(nRng)
        nRng = SimpleNamespace(min=excludeIndex+1,max=rng.max)
        if nRng.max - nRng.min >= 0:
            nRanges.append(nRng)
    return nRanges

def intRangesExcludeBelow(iRanges, excludeIndex):
    if excludeIndex is None:
        return iRanges
    nRanges = intRangesExcludeOne(iRanges, excludeIndex)
    return [ rng for rng in nRanges if rng.min > excludeIndex ]

def intRangesExcludeBetween(iRanges, excludeIndexMin, excludeIndexMax):
    if excludeIndexMin is None or excludeIndexMax is None:
        return iRanges
    nRanges = intRangesExcludeOne(iRanges, excludeIndexMin)
    nRanges = intRangesExcludeOne(nRanges, excludeIndexMax)
    return [ rng for rng in nRanges if (rng.max < excludeIndexMin) or (rng.min > excludeIndexMax) ]

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

def getDCOMappingForIntField(RSRC, dcoFieldName, po, TM80_IndexShift=None, FpDCOTable_TypeID=None):
    """ Returns mapping between DCO Indexes and specified integer field from the DCOs

    If given dcoFieldName represents TMI, converts it to TypeID.
    """
    if TM80_IndexShift is None:
        TM80 = RSRC.find("./TM80/Section")
        if TM80 is not None:
            TM80_IndexShift = TM80.get("IndexShift")
            if TM80_IndexShift is not None:
                TM80_IndexShift = int(TM80_IndexShift, 0)
    dcoMapping = {}
    DCO_fields = [ field[0] for field in LVparts.DCO._fields_ ]
    FpDCOTable = getFpDCOTable(RSRC, po, TM80_IndexShift=TM80_IndexShift, FpDCOTable_TypeID=FpDCOTable_TypeID)
    if FpDCOTable is not None:
            for FpDCO in FpDCOTable.findall("./RepeatedBlock/Cluster"):
                FpDCO_FieldValue = None
                # List fields without comments
                FpDCO_FieldList = list(filter(lambda f: f.tag is not ET.Comment, FpDCO.findall("./*")))
                val = FpDCO_FieldList[DCO_fields.index(dcoFieldName)].text
                if val is not None:
                    val = int(val,0)
                    if dcoFieldName.endswith("TMI"):
                        assert(TM80_IndexShift is not None) # Otherwise we wouldn't have DCO list at all
                        FpDCO_FieldValue = TM80_IndexShift + (val & 0xFFFFFF)
                    else:
                        FpDCO_FieldValue = val
                idx = FpDCO_FieldList[DCO_fields.index('dcoIndex')].text
                idx = int(idx,0)
                dcoMapping[idx] = FpDCO_FieldValue
    return dcoMapping

def getTypeDescFromMapUsingList(FlatTypeDescList, TDTopMap, po):
    """ Retrieves TypeDesc element, using mapping list and TD list

    Returns entry from FlatTypeDescList, and position of that entry.
    """
    TDTopMap_Index = TDTopMap.get("Index")
    if TDTopMap_Index is not None:
        TDTopMap_Index = int(TDTopMap_Index, 0)
    FlatTypeID = TDTopMap.get("FlatTypeID")
    if FlatTypeID is None:
        FlatTypeID = TDTopMap.get("TypeID") # For map entries within Clusters
    if FlatTypeID is not None:
        FlatTypeID = int(FlatTypeID, 0)
    if FlatTypeID is None:
        if (po.verbose > 2):
            print("{:s}: TypeDesc {} mapping entry is damaged"\
                .format(po.xml,TDTopMap_Index))
        return None, TDTopMap_Index, FlatTypeID
    if FlatTypeID >= 0 and FlatTypeID < len(FlatTypeDescList):
        TypeDesc = FlatTypeDescList[FlatTypeID]
    else:
        if (po.verbose > 2):
            print("{:s}: TypeDesc {} Flat TypeID {} is missing from flat list"\
                .format(po.xml,TDTopMap_Index,FlatTypeID))
        TypeDesc = None
    return TypeDesc, TDTopMap_Index, FlatTypeID

def getTypeDescFromIDUsingLists(TypeDescMap, FlatTypeDescList, typeID, po):
    """ Retrieves TypeDesc element, using mapping list and TD list

    Returns entry from FlatTypeDescList, and position of that entry.
    """
    for TDTopMap in TypeDescMap:
        TDTopMap_Index = TDTopMap.get("Index")
        if TDTopMap_Index is not None:
            TDTopMap_Index = int(TDTopMap_Index, 0)
        if TDTopMap_Index != typeID:
            continue
        TypeDesc, TDTopMap_Index, FlatTypeID = getTypeDescFromMapUsingList(FlatTypeDescList, TDTopMap, po)
        return TypeDesc, FlatTypeID
    return None, None

def getMaxIndexFromList(elemList, fo, po):
    val = 1
    for elem in elemList:
        elemIndex = elem.get("Index")
        if elemIndex is not None:
            elemIndex = int(elemIndex, 0)
        if elemIndex is not None:
            val = max(val, elemIndex)
    return val

def TypeDesc_equivalent(RSRC, fo, po, TypeDesc1, TypeDesc2, FlatTypeDescList, sameLabels=False):
    """ Compares two type descriptions and returns whether they're equivalent
    """
    if TypeDesc1.get("Type") != TypeDesc2.get("Type"):
        return False
    if sameLabels:
        if TypeDesc1.get("Label") != TypeDesc2.get("Label"):
            return False
    if TypeDesc1.get("Type") in ("Cluster","Array",):
        td1SubTDMapList = TypeDesc1.findall("./TypeDesc")
        td2SubTDMapList = TypeDesc2.findall("./TypeDesc")
        if len(td1SubTDMapList) != len(td2SubTDMapList):
            return False
        for i, td1SubTDMap in enumerate(td1SubTDMapList):
            td1TypeDesc, _, td1FlatTypeID = getTypeDescFromMapUsingList(FlatTypeDescList, td1SubTDMap, po)
            td2TypeDesc, _, td2FlatTypeID = getTypeDescFromMapUsingList(FlatTypeDescList, td2SubTDMapList[i], po)
            if not TypeDesc_equivalent(RSRC, fo, po, td1TypeDesc, td2TypeDesc, FlatTypeDescList, sameLabels=sameLabels):
                return False
    elif TypeDesc1.get("Type") in ("TypeDef",):
        # TypeDef directly stores a sub-type inside
        td1SubTypeDesc = TypeDesc1.find("./TypeDesc")
        td2SubTypeDesc = TypeDesc2.find("./TypeDesc")
        if not TypeDesc_equivalent(RSRC, fo, po, td1SubTypeDesc, td2SubTypeDesc, FlatTypeDescList, sameLabels=sameLabels):
            return False
    elif TypeDesc1.get("Type") == "Refnum":
        if TypeDesc1.get("RefType") != TypeDesc2.get("RefType"):
            return False
        td1SubItemList = TypeDesc1.findall("./Item")
        td2SubItemList = TypeDesc2.findall("./Item")
        if len(td1SubItemList) != len(td2SubItemList):
            return False
        for i, td1SubItem in enumerate(td1SubItemList):
            td2SubItem_attrib = td2SubItemList[i].attrib
            for td1AName, td1AVal in td1SubItem.attrib.items():
                if td1AName not in td2SubItem_attrib:
                    return False
                if td2SubItem_attrib[td1AName] != td1AVal:
                    return False
    #TODO support more types
    return True

def TypeDesc_find_unused_ranges(RSRC, fo, po, skipRm=[], VCTP_TypeDescList=None, VCTP_FlatTypeDescList=None):
    """ Searches through all TDs, looking for unused items

    Skips removal of items for specified groups - often we will want the groups to include TM80.
    """
    VCTP = RSRC.find("./VCTP/Section")
    if VCTP_TypeDescList is None:
        if VCTP is not None:
            VCTP_TypeDescList = VCTP.findall("TopLevel/TypeDesc")
        else:
            VCTP_TypeDescList = []
    if VCTP_FlatTypeDescList is None:
        if VCTP is not None:
            VCTP_FlatTypeDescList = VCTP.findall("TypeDesc")
    # Set min possible value; we will increase it shortly
    # and max acceptable value; we will decrease it shortly
    properMax = getMaxIndexFromList(VCTP_TypeDescList, fo, po)
    unusedRanges = [ SimpleNamespace(min=1,max=properMax) ]
    # find unused TD ranges
    if True:
        # We need TM80 to convert TMIs into TypeIDs
        TM80_IndexShift = None
        TM80 = RSRC.find("./TM80/Section")
        if TM80 is not None:
            TM80_IndexShift = TM80.get("IndexShift")
            if TM80_IndexShift is not None:
                TM80_IndexShift = int(TM80_IndexShift, 0)
    if "TM80" not in skipRm:
        if TM80 is not None:
            TM80_Clients = TM80.findall("./Client")
            if len(TM80_Clients) > 0:
                unusedRanges = intRangesExcludeBetween(unusedRanges, TM80_IndexShift, TM80_IndexShift+len(TM80_Clients)-1)
    if "DTHP" not in skipRm:
        DTHP_indexShift = None
        DTHP_tdCount = None
        DTHP_typeDescSlice = RSRC.find("./DTHP/Section/TypeDescSlice")
        if DTHP_typeDescSlice is not None:
            DTHP_indexShift = DTHP_typeDescSlice.get("IndexShift")
            if DTHP_indexShift is not None:
                DTHP_indexShift = int(DTHP_indexShift, 0)
            DTHP_tdCount = DTHP_typeDescSlice.get("Count")
            if DTHP_tdCount is not None:
                DTHP_tdCount = int(DTHP_tdCount, 0)
        if (DTHP_indexShift is not None) and (DTHP_tdCount is not None):
            unusedRanges = intRangesExcludeBetween(unusedRanges, DTHP_indexShift, DTHP_indexShift+DTHP_tdCount-1)
    if "CONP" not in skipRm:
        # Exclude TypeDesc pointed by CONP
        CONP_TypeID = None
        CONP_TypeDesc = RSRC.find("./CONP/Section/TypeDesc")
        if CONP_TypeDesc is not None:
            CONP_TypeID = CONP_TypeDesc.get("TypeID")
            if CONP_TypeID is not None:
                CONP_TypeID = int(CONP_TypeID, 0)
        unusedRanges = intRangesExcludeOne(unusedRanges, CONP_TypeID)
        if (po.verbose > 3):
            print("{:s}: After CONP exclusion, unused TD ranges: {}"\
                .format(po.xml,unusedRanges))
    if "CPC2" not in skipRm:
        # Exclude TypeDesc pointed by CPC2
        CPC2_TypeID = None
        CPC2_TypeDesc = RSRC.find("./CPC2/Section/TypeDesc")
        if CPC2_TypeDesc is not None:
            CPC2_TypeID = CPC2_TypeDesc.get("TypeID")
            if CPC2_TypeID is not None:
                CPC2_TypeID = int(CPC2_TypeID, 0)
        unusedRanges = intRangesExcludeOne(unusedRanges, CPC2_TypeID)
        if (po.verbose > 3):
            print("{:s}: After CPC2 exclusion, unused TD ranges: {}"\
                .format(po.xml,unusedRanges))
    if "PFTD" not in skipRm:
        # Exclude TypeDesc pointed by PFTD
        FPTD_TypeID = None
        FPTD_TypeDesc = RSRC.find("./FPTD/Section/TypeDesc")
        if FPTD_TypeDesc is not None:
            FPTD_TypeID = FPTD_TypeDesc.get("TypeID")
            if FPTD_TypeID is not None:
                FPTD_TypeID = int(FPTD_TypeID, 0)
        unusedRanges = intRangesExcludeOne(unusedRanges, FPTD_TypeID)
        if (po.verbose > 3):
            print("{:s}: After PFTD exclusion, unused TD ranges: {}"\
                .format(po.xml,unusedRanges))
    # We need DSInit for several exclusions below
    DSInit = getDSInitRecord(RSRC, po)
    if "DSInit" not in skipRm:
        # Exclude TypeDesc with DSInit
        DSInit_TypeID = None
        if DSInit is not None:
            DSInit_TypeID = DSInit.get("TypeID")
        if DSInit_TypeID is not None:
            DSInit_TypeID = int(DSInit_TypeID, 0)
        unusedRanges = intRangesExcludeOne(unusedRanges, DSInit_TypeID)
    if "HiliteTb" not in skipRm:
        # Exclude TypeDesc which contain Hilite Table
        HiliteTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.hiliteTableTMI, po, DSInit=DSInit)
            if val_TMI is not None and val_TMI >= 0:
                HiliteTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, HiliteTable_TypeID)
    if True:
        # We need probe table index not only to exclude it, but to access the items inside
        ProbeTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.probeTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                ProbeTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
    if "ProbeTb" not in skipRm:
        # Exclude TypeDesc which contain Probe Table
        unusedRanges = intRangesExcludeOne(unusedRanges, ProbeTable_TypeID)
    if "FpDcoTb" not in skipRm:
        # Exclude TypeDesc which contain FP DCO Table
        FpDCOTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.fpdcoTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                FpDCOTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, FpDCOTable_TypeID)
        if (po.verbose > 3):
            print("{:s}: After FP DCO Table exclusion, unused TD ranges: {}"\
                .format(po.xml,unusedRanges))
    if "ClumpQE" not in skipRm:
        # Exclude TypeDesc which contain Clump QE Alloc
        ClumpQEAlloc_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.clumpQEAllocTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                ClumpQEAlloc_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, ClumpQEAlloc_TypeID)
    if "VIParamTb" not in skipRm:
        # Exclude TypeDesc which contain VI Param Table
        VIParamTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.viParamTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                VIParamTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, VIParamTable_TypeID)
        if (po.verbose > 3):
            print("{:s}: After VI Param Table exclusion, unused TD ranges: {}"\
                .format(po.xml,unusedRanges))
    if "ExtraDCOInfo" not in skipRm:
        # Exclude TypeDesc which contain Extra DCO Info
        ExtraDCOInfo_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.extraDCOInfoTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                ExtraDCOInfo_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, ExtraDCOInfo_TypeID)
    if "IOConnIdx" not in skipRm:
        # Exclude TypeDesc which contain IO Conn Idx
        IOConnIdx_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.localInputConnIdxTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                IOConnIdx_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, IOConnIdx_TypeID)
    if "IntHiliteTb" not in skipRm:
        # Exclude TypeDesc which contain InternalHiliteTableHandleAndPtr
        InternalHiliteTableHandleAndPtr_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.internalHiliteTableHandleAndPtrTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                InternalHiliteTableHandleAndPtr_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, InternalHiliteTableHandleAndPtr_TypeID)
    if "SubVIPatchTags" not in skipRm:
        # Exclude TypeDesc which contain SubVI Patch Tags
        SubVIPatchTags_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.subVIPatchTagsTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                SubVIPatchTags_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, SubVIPatchTags_TypeID)
    if "SubVIPatch" not in skipRm:
        # Exclude TypeDesc which contain SubVI Patch
        SubVIPatch_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.subVIPatchTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                SubVIPatch_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, SubVIPatch_TypeID)
        if (po.verbose > 3):
            print("{:s}: After SubVI Patch exclusion, unused TD ranges: {}"\
                .format(po.xml,unusedRanges))
    if "EnpdTdOffsets" not in skipRm:
        # Exclude TypeDesc which contain Enpd Td Offsets
        EnpdTdOffsets_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.enpdTdOffsetsTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                EnpdTdOffsets_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, EnpdTdOffsets_TypeID)
    if "SpDdoTable" not in skipRm:
        # Exclude TypeDesc which contain Sp DDO Table
        SpDDOTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.spDDOTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                SpDDOTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, SpDDOTable_TypeID)
    if "StepIntoNodeIdxTb" not in skipRm:
        # Exclude TypeDesc which contain StepInto Node Idx Table
        StepIntoNodeIdxTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.stepIntoNodeIdxTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                StepIntoNodeIdxTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, StepIntoNodeIdxTable_TypeID)
    if "HiliteIdxTable" not in skipRm:
        # Exclude TypeDesc which contain Hilite Idx Table
        HiliteIdxTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.hiliteIdxTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                HiliteIdxTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, HiliteIdxTable_TypeID)
    if "GCodeProfileResultTb" not in skipRm:
        # Exclude TypeDesc which contain Generated Code Profile Result Table
        GeneratedCodeProfileResultTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.generatedCodeProfileResultTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                GeneratedCodeProfileResultTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, GeneratedCodeProfileResultTable_TypeID)
        if (po.verbose > 3):
            print("{:s}: After GCPR Table exclusion, unused TD ranges: {}"\
                .format(po.xml,unusedRanges))
    if "FpDcoTb" not in skipRm:
        # Exclude TypeDesc values pointed to by DCOs
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
                idx = FpDCO_FieldList[DCO_fields.index('dcoIndex')].text
                idx = int(idx,0)
                if (po.verbose > 3):
                    print("{:s}: After DCO{} check, excluding from unused TD ranges: {} {} {}"\
                        .format(po.xml,idx,FpDCOFlags_TypeID,FpDCODefaultDataTMI_TypeID,FpDCOExtraData_TypeID))
                unusedRanges = intRangesExcludeOne(unusedRanges, FpDCOFlags_TypeID)
                unusedRanges = intRangesExcludeOne(unusedRanges, FpDCODefaultDataTMI_TypeID)
                unusedRanges = intRangesExcludeOne(unusedRanges, FpDCOExtraData_TypeID)
    if "ProbePoints" not in skipRm:
        # Exclude TypeDesc values pointed to by ProbePoints
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
                unusedRanges = intRangesExcludeOne(unusedRanges, ProbePoint_TypeID)
        if (po.verbose > 3):
            print("{:s}: After ProbePoints exclusion, unused TD ranges: {}"\
                .format(po.xml,unusedRanges))
    if "BFAL" not in skipRm:
        # Exclude TypeDesc values pointed to by BFAL
        if TM80_IndexShift is not None:
            for BFAL_TypeMap in RSRC.findall("./BFAL/Section/TypeMap"):
                val_TMI = BFAL_TypeMap.get("TMI")
                if val_TMI is not None:
                    val_TMI = int(val_TMI, 0)
                BFAL_TypeID = None
                if val_TMI is not None:
                    BFAL_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
                unusedRanges = intRangesExcludeOne(unusedRanges, BFAL_TypeID)
        if (po.verbose > 3):
            print("{:s}: After BFAL exclusion, unused TD ranges: {}"\
                .format(po.xml,unusedRanges))
    return unusedRanges

def VCTP_add_TypeDesc_copy(RSRC, fo, po, srcTypeDesc, VCTP=None):
    """ Adds a copy of given TD to the VCTP Flat Types List

    Returns FlatTypeID of the new TD, and the TD itself.
    The function uses deep copy of given TD element, but this really results
    in shallow copy of the Type - elements inside still reference the same
    flat TDs. So in logical sense, this function adds a shallow copy.
    """
    if VCTP is None:
        VCTP = RSRC.find("./VCTP/Section")
    if VCTP is None:
        return None, None
    VCTP_FlatTypeDescList = VCTP.findall("./TypeDesc")
    dstTypeDesc = copy.deepcopy(srcTypeDesc)
    # Place the new TD tag at proper position, not at end; this is only visual improvement
    proper_flatPos = list(VCTP).index(VCTP_FlatTypeDescList[-1]) + 1
    VCTP.insert(proper_flatPos,dstTypeDesc)
    return dstTypeDesc, len(VCTP_FlatTypeDescList)

def VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, srcTypeDesc, VCTP=None):
    if VCTP is None:
        VCTP = RSRC.find("./VCTP/Section")
    if VCTP is None:
        return None, None
    dstTypeDesc, dstTypeID = None, None
    VCTP_FlatTypeDescList = VCTP.findall("./TypeDesc")
    for cmpTypeID, cmpTypeDesc in enumerate(VCTP_FlatTypeDescList):
        if (TypeDesc_equivalent(RSRC, fo, po, cmpTypeDesc, srcTypeDesc, VCTP_FlatTypeDescList, sameLabels=True)):
            dstTypeDesc, dstTypeID = cmpTypeDesc, cmpTypeID
            break
    if dstTypeDesc is None:
        dstTypeDesc, dstTypeID = VCTP_add_TypeDesc_copy(RSRC, fo, po, srcTypeDesc, VCTP=VCTP)
    return dstTypeDesc, dstTypeID

def VCTP_add_TopTypeDesc(RSRC, fo, po, srcFlatTypeID, nTopTDIndex=None, VCTP_TopLevel=None):
    """ Adds given TD to Top Types List
    """
    if VCTP_TopLevel is None:
        VCTP = RSRC.find("./VCTP/Section")
        if VCTP is not None:
            VCTP_TopLevel = VCTP.find("TopLevel")
    if VCTP_TopLevel is None:
            return None, None
    if nTopTDIndex is None:
        VCTP_TypeDescList = VCTP.findall("TopLevel/TypeDesc")
        nTopTDIndex = getMaxIndexFromList(VCTP_TypeDescList, fo, po) + 1
    elem = ET.Element("TypeDesc")
    elem.set("Index", str(nTopTDIndex))
    elem.set("FlatTypeID", str(srcFlatTypeID))
    VCTP_TopLevel.append(elem)
    return nTopTDIndex, srcFlatTypeID

def VCTP_add_TopTypeDesc_for_DTHP(RSRC, fo, po, srcTypeDesc, srcFlatTypeID, nTopTDIndex=None, VCTP_FlatTypeDescList=None, VCTP_TopLevel=None):
    """ Adds given TD to Top Types List, with sub-types

    Adds not only the given TD to Top Types List, but also its sub-TDs, in the form they're needed
    for DCO definition within within DTHP.
    Returns first and last Top TD Index used.
    """
    firstTopTDIndex, _ = VCTP_add_TopTypeDesc(RSRC, fo, po, srcFlatTypeID, nTopTDIndex=nTopTDIndex, VCTP_TopLevel=VCTP_TopLevel)
    currTopTDIndex =firstTopTDIndex + 1
    srcTDMapList = srcTypeDesc.findall("./TypeDesc[@TypeID]")
    for subTDMap in srcTDMapList:
        subTypeDesc, _, subFlatTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, subTDMap, po)
        assert(subTypeDesc is not None)
        _, currTopTDIndex = VCTP_add_TopTypeDesc_for_DTHP(RSRC, fo, po, subTypeDesc, subFlatTypeID, \
              nTopTDIndex=currTopTDIndex, VCTP_FlatTypeDescList=VCTP_FlatTypeDescList, VCTP_TopLevel=VCTP_TopLevel)
        currTopTDIndex += 1
    return firstTopTDIndex, currTopTDIndex - 1

def VCTP_add_ErrorClustTD_for_DTHP(RSRC, fo, po, VCTP):
    """ Adds Error Cluster TD to VCTP and Top Types List
    """
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Label","status")
        tmpTypeDesc.set("Format","inline")
        newStatusTypeDesc, newStatusFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","code")
        tmpTypeDesc.set("Format","inline")
        newCodeTypeDesc, newCodeFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","String")
        tmpTypeDesc.set("Prop1","0x{:04X}".format(0xFFFFFFFF))
        tmpTypeDesc.set("Label","source")
        tmpTypeDesc.set("Format","inline")
        newSrcTypeDesc, newSrcFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Label","error")
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newStatusFlatTypeID))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newCodeFlatTypeID))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newSrcFlatTypeID))
        newErrClustTypeDesc, newErrClustFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    return newErrClustTypeDesc, newErrClustFlatTypeID

def VCTP_add_BaseDatatypeTD_for_DTHP(RSRC, fo, po, fpClassEx, VCTP):
    """ Adds Base Datatype TD to VCTP and Top Types List
    """
    dcoUDCRefClass = "2D Error Bar"
    allPropsClustTDList = []
    # Preparing newGraphPropsFlatTypeID
    graphPropsFlatTypeIDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","UnitUInt16")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Projection Mode")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Orthographic","Perspective",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "EnumLabel")
            tmpLabel.text = labelStr
        newProjModeTypeDesc, newProjModeFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        graphPropsFlatTypeIDList.append(newProjModeFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","UnitUInt16")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","View Direction")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Towards X-Y Plane","Towards Y-Z Plane","Towards X-Z Plane","User Define",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "EnumLabel")
            tmpLabel.text = labelStr
        newViwDircTypeDesc, newViwDircFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        graphPropsFlatTypeIDList.append(newViwDircFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumUInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Plot Area Color")
        tmpTypeDesc.set("Format","inline")
        newPltArColTypeDesc, newPltArColFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        graphPropsFlatTypeIDList.append(newPltArColFlatTypeID)
    for labelStr in ("Fast Draw","X-Y","Y-Z","X-Z","Lighting",):
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Label",labelStr)
        tmpTypeDesc.set("Format","inline")
        newTmpTypeDesc, newTmpFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        graphPropsFlatTypeIDList.append(newTmpFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Refnum")
        tmpTypeDesc.set("RefType","LVObjCtl")
        tmpTypeDesc.set("CtlFlags","0x{:04X}".format(0x0068))
        tmpTypeDesc.set("HasItem",str(0))
        tmpTypeDesc.set("Format","inline")
        newLVOb1SubRefTypeDesc, newLVOb1SubRefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Refnum")
        tmpTypeDesc.set("RefType","LVObjCtl")
        tmpTypeDesc.set("CtlFlags","0x{:04X}".format(0x0064))
        tmpTypeDesc.set("HasItem",str(0))
        tmpTypeDesc.set("Label","3D Picture Control")
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newLVOb1SubRefFlatTypeID))
        newLVOb1RefTypeDesc, newLVOb1RefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        graphPropsFlatTypeIDList.append(newLVOb1RefFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0x0C3CFF6F8))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Graph Properties")
            tmpTDSub.set("Format","inline")
        for flatTypeID in graphPropsFlatTypeIDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_graph.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newGraphPropsTypeDesc, newGraphPropsFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        allPropsClustTDList.append(newGraphPropsFlatTypeID)
    # Preparing newPACPropsFlatTypeID - part newPlotPropsArrFlatTypeID
    plotPropsClustTDList = []
    projPropClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Draw XY","Draw YZ","Draw XZ",):
            tmpTypeDesc.set("Label",labelStr)
            newDrawTypeDesc, newDrawFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            projPropClustTDList.append(newDrawFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC0F57580))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Projection Properties")
            tmpTDSub.set("Format","inline")
        for flatTypeID in projPropClustTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_plot_projection.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newProjPropTypeDesc, newProjPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        plotPropsClustTDList.append(newProjPropFlatTypeID)
    surfPropsClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Label","Draw surface")
        tmpTypeDesc.set("Format","inline")
        newDrwSurfTypeDesc, newDrwSurfFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        surfPropsClustTDList.append(newDrwSurfFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumFloat64")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Opacity")
        tmpTypeDesc.set("Format","inline")
        newOpactTypeDesc, newOpactFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        surfPropsClustTDList.append(newOpactFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Label","Shading")
        tmpTypeDesc.set("Format","inline")
        newShadingTypeDesc, newShadingFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        surfPropsClustTDList.append(newShadingFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Specular")
        tmpTypeDesc.set("Format","inline")
        newSpclrTypeDesc, newSpclrFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        surfPropsClustTDList.append(newSpclrFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumFloat64")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        newFltTypeDesc, newFltFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumUInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        newUIntTypeDesc, newUIntFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Format","inline")
        for flatTypeID in (newFltFlatTypeID,newUIntFlatTypeID,):
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(flatTypeID))
        newColMapClustTypeDesc, newColMapClustFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if newColMapClustFlatTypeID is not None:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Array")
        tmpTypeDesc.set("Label","Color Map")
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "Dimension")
            tmpTDSub.set("Flags","0x{:02X}".format(0xFF))
            tmpTDSub.set("FixedSize","0x{:06X}".format(0xFFFFFF))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newColMapClustFlatTypeID))
        newColMapTypeDesc, newColMapFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        surfPropsClustTDList.append(newColMapFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Interpolate Color","Absolute Colormap",):
            tmpTypeDesc.set("Label",labelStr)
            newDrawTypeDesc, newDrawFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            surfPropsClustTDList.append(newDrawFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC8065020))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Surface Properties")
            tmpTDSub.set("Format","inline")
        for flatTypeID in surfPropsClustTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_plot_surface.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newSurfPropsTypeDesc, newSurfPropsFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        plotPropsClustTDList.append(newSurfPropsFlatTypeID)
    contrPropsClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumUInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Contour color")
        tmpTypeDesc.set("Format","inline")
        newContrColTypeDesc, newContrColFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        contrPropsClustTDList.append(newContrColFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","UnitUInt16")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Axis")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("X","Y","Z",):
            tmpLabel = ET.SubElement(tmpTDSub, "EnumLabel")
            tmpLabel.text = labelStr
        newAxisTypeDesc, newAxisFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        contrPropsClustTDList.append(newAxisFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Draw contour","Antialias",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            contrPropsClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumFloat32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Line Width")
        tmpTypeDesc.set("Format","inline")
        newLnWidthTypeDesc, newLnWidthFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        contrPropsClustTDList.append(newLnWidthFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","UnitUInt16")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Contour Line Style")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Solid","Dash","Dot","Dash Dot",):
            tmpLabel = ET.SubElement(tmpTDSub, "EnumLabel")
            tmpLabel.text = labelStr
        newLnStyleTypeDesc, newLnStyleFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        contrPropsClustTDList.append(newLnStyleFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","UnitUInt16")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Mode")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Levels","Intervals","Level List",):
            tmpLabel = ET.SubElement(tmpTDSub, "EnumLabel")
            tmpLabel.text = labelStr
        newModeTypeDesc, newModeFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        contrPropsClustTDList.append(newModeFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumFloat32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Levels","Intervals","Anchored At",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            contrPropsClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Anchored",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            contrPropsClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Array")
        tmpTypeDesc.set("Label","Level List")
        tmpTypeDesc.set("Format","inline")
        for i in range(1):
            tmpTDSub = ET.SubElement(tmpTypeDesc, "Dimension")
            tmpTDSub.set("Flags","0x{:02X}".format(0xFF))
            tmpTDSub.set("FixedSize","0x{:06X}".format(0xFFFFFF))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newFltFlatTypeID))
        newLvListTypeDesc, newLvListFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        contrPropsClustTDList.append(newLvListFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC3D7AD43))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Contour Properties")
            tmpTDSub.set("Format","inline")
        for flatTypeID in contrPropsClustTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_plot_contour.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newContrPropsTypeDesc, newContrPropsFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        plotPropsClustTDList.append(newContrPropsFlatTypeID)
    normlPropsClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumUInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Normal color")
        tmpTypeDesc.set("Format","inline")
        newNormColTypeDesc, newNormColFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        normlPropsClustTDList.append(newNormColFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumFloat32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Normal Length")
        tmpTypeDesc.set("Format","inline")
        newNormLenTypeDesc, newNormLenFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        normlPropsClustTDList.append(newNormLenFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumFloat32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Normal Width")
        tmpTypeDesc.set("Format","inline")
        newNormWidthTypeDesc, newNormWidthFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        normlPropsClustTDList.append(newNormWidthFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Draw Normal","Antialiasing",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            normlPropsClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC0F575EC))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Normal Properties")
            tmpTDSub.set("Format","inline")
        for flatTypeID in normlPropsClustTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_plot_normal.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newNormlPropsTypeDesc, newNormlPropsFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        plotPropsClustTDList.append(newNormlPropsFlatTypeID)
    # Preparing newPACPropsFlatTypeID - part newPlotPropsArrFlatTypeID
    pacPropsFlatTypeIDList = []
    ptLnPropsClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumUInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Color")
        tmpTypeDesc.set("Format","inline")
        newPtLnColTypeDesc, newPtLnColColFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        ptLnPropsClustTDList.append(newPtLnColColFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumFloat32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Point Size")
        tmpTypeDesc.set("Format","inline")
        newPtSizeTypeDesc, newPtSizeFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        ptLnPropsClustTDList.append(newPtSizeFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","UnitUInt16")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Points / Lines")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("None","Points","Lines","Both",):
            tmpLabel = ET.SubElement(tmpTDSub, "EnumLabel")
            tmpLabel.text = labelStr
        newPtLnVisTypeDesc, newPtLnVisFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        ptLnPropsClustTDList.append(newPtLnVisFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","UnitUInt16")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Point Style")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Point","EmptySquare","Asterisk","Diamond","EmptyCircle","Circle","X",):
            tmpLabel = ET.SubElement(tmpTDSub, "EnumLabel")
            tmpLabel.text = labelStr
        newPtStyleTypeDesc, newPtStyleFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        ptLnPropsClustTDList.append(newPtStyleFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","UnitUInt16")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Line Style")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Solid","Dash","Dot","Dash Dot",):
            tmpLabel = ET.SubElement(tmpTDSub, "EnumLabel")
            tmpLabel.text = labelStr
        newLnStyleTypeDesc, newLnStyleFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        ptLnPropsClustTDList.append(newLnStyleFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC3BBD8A7))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Points/Lines Properties")
            tmpTDSub.set("Format","inline")
        for flatTypeID in ptLnPropsClustTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_plot_point_line.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newPtLnPropsTypeDesc, newPtLnPropsFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        plotPropsClustTDList.append(newPtLnPropsFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumUInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Plot ID")
        tmpTypeDesc.set("Format","inline")
        newPlotIdTypeDesc, newPlotIdFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        plotPropsClustTDList.append(newPlotIdFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","UnitUInt16")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Coordinate System")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Cartesian","Cylindrical","Spherical",):
            tmpLabel = ET.SubElement(tmpTDSub, "EnumLabel")
            tmpLabel.text = labelStr
        newCoordSystTypeDesc, newCoordSystFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        plotPropsClustTDList.append(newCoordSystFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC8065029))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Plot Properties")
            tmpTDSub.set("Format","inline")
        for flatTypeID in plotPropsClustTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_plot_all.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newPlotPropsTypeDesc, newPlotPropsFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC806503D))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Array")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Plot Properties Array")
            tmpTDSub.set("Format","inline")
        for i in range(1):
            tmpTDSSub = ET.SubElement(tmpTDSub, "Dimension")
            tmpTDSSub.set("Flags","0x{:02X}".format(0xFF))
            tmpTDSSub.set("FixedSize","0x{:06X}".format(0xFFFFFF))
        if True:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(newPlotPropsFlatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_plot_all_array.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newPlotPropsArrTypeDesc, newPlotPropsArrFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        pacPropsFlatTypeIDList.append(newPlotPropsArrFlatTypeID)
    # Preparing newPACPropsFlatTypeID - part newValPairPropsFlatTypeID
    xValPairsClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumFloat32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Value")
        tmpTypeDesc.set("Format","inline")
        newFltValueTypeDesc, newFltValueFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Index")
        tmpTypeDesc.set("Format","inline")
        newIntIndexTypeDesc, newIntIndexFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","String")
        tmpTypeDesc.set("Prop1","0x{:04X}".format(0xFFFFFFFF))
        tmpTypeDesc.set("Label","Name")
        tmpTypeDesc.set("Format","inline")
        newStrNameTypeDesc, newStrNameFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Format","inline")
        for flatTypeID in (newFltValueFlatTypeID,newIntIndexFlatTypeID,newStrNameFlatTypeID,):
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        newXValInnerTypeDesc, newXValInnerFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Array")
        tmpTypeDesc.set("Label","Data Array")
        tmpTypeDesc.set("Format","inline")
        for i in range(1):
            tmpTDSub = ET.SubElement(tmpTypeDesc, "Dimension")
            tmpTDSub.set("Flags","0x{:02X}".format(0xFF))
            tmpTDSub.set("FixedSize","0x{:06X}".format(0xFFFFFF))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newXValInnerFlatTypeID))
        newXValDataArrTypeDesc, newXValDataArrFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        xValPairsClustTDList.append(newDrawFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Show ticks","Show grid lines",):
            tmpTypeDesc.set("Label",labelStr)
            newDrawTypeDesc, newDrawFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            xValPairsClustTDList.append(newDrawFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","UnitUInt16")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","Labels")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Value","None","Name",):
            tmpLabel = ET.SubElement(tmpTDSub, "EnumLabel")
            tmpLabel.text = labelStr
        newLabelsUntTypeDesc, newLabelsUntFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        xValPairsClustTDList.append(newLabelsUntFlatTypeID)
    if True:
        # For some reason, X have no typedef around it
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Label","X Value Pairs")
        tmpTypeDesc.set("Format","inline")
        for flatTypeID in xValPairsClustTDList:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(flatTypeID))
        newXValPairsTypeDesc, newXValPairsFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC0F5766F))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Y Value Pairs")
            tmpTDSub.set("Format","inline")
        for flatTypeID in xValPairsClustTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_value_pair_1d.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newYValPairsTypeDesc, newYValPairsFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC0F5766F))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Z Value Pairs")
            tmpTDSub.set("Format","inline")
        for flatTypeID in xValPairsClustTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_value_pair_1d.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newZValPairsTypeDesc, newZValPairsFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC342AF5A))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Value Pair Properties")
            tmpTDSub.set("Format","inline")
        for flatTypeID in (newXValPairsFlatTypeID,newYValPairsFlatTypeID,newZValPairsFlatTypeID):
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_value_pair_all.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newValPairPropsTypeDesc, newValPairPropsFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        pacPropsFlatTypeIDList.append(newValPairPropsFlatTypeID)
    # Preparing newPACPropsFlatTypeID - part newAxesPropsFlatTypeID
    gridVisibleClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Draw X-grid","Draw Y-grid","Draw Z-grid",):
            tmpTypeDesc.set("Label",labelStr)
            newDrawTypeDesc, newDrawFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            gridVisibleClustTDList.append(newDrawFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Label","Grid Visible")
        tmpTypeDesc.set("Format","inline")
        for flatTypeID in gridVisibleClustTDList:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(flatTypeID))
        newGridVisibTypeDesc, newGridVisibFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    gridColClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumUInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Color X","Color Y","Color Z",):
            tmpTypeDesc.set("Label",labelStr)
            newDrawTypeDesc, newDrawFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            gridColClustTDList.append(newDrawFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Label","Grid Color")
        tmpTypeDesc.set("Format","inline")
        for flatTypeID in gridColClustTDList:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(flatTypeID))
        newGridColTypeDesc, newGridColFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC0F576AC))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Grid  Properties")
            tmpTDSub.set("Format","inline")
        for flatTypeID in (newGridVisibFlatTypeID,newGridColFlatTypeID,):
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_axes_grid.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newValPairPropsTypeDesc, newValPairPropsFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    minorCntClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("X","Y","Z",):
            tmpTypeDesc.set("Label",labelStr)
            newAxIntTypeDesc, newAxIntFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            minorCntClustTDList.append(newAxIntFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Label","Minor Count")
        tmpTypeDesc.set("Format","inline")
        for flatTypeID in minorCntClustTDList:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(flatTypeID))
        newMinorCntColTypeDesc, newMinorCntColFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Label","Major Count")
        tmpTypeDesc.set("Format","inline")
        for flatTypeID in minorCntClustTDList:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(flatTypeID))
        newMajorCntColTypeDesc, newMajorCntColFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    mTickVisibClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("X","Y","Z",):
            tmpTypeDesc.set("Label",labelStr)
            newAxBoolTypeDesc, newAxBoolFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            mTickVisibClustTDList.append(newAxBoolFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Label","Major Ticks Visible")
        tmpTypeDesc.set("Format","inline")
        for flatTypeID in mTickVisibClustTDList:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(flatTypeID))
        newMajorTickVisTypeDesc, newMajorTickVisFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Label","Minor Ticks Visible")
        tmpTypeDesc.set("Format","inline")
        for flatTypeID in mTickVisibClustTDList:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(flatTypeID))
        newMinorTickVisTypeDesc, newMinorTickVisFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Label","Tick Color")
        tmpTypeDesc.set("Format","inline")
        for flatTypeID in gridColClustTDList:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(flatTypeID))
        newTickColTypeDesc, newTickColFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC0F576D7))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Ticks Properties")
            tmpTDSub.set("Format","inline")
        for flatTypeID in (newMajorCntColFlatTypeID,newMinorCntColFlatTypeID,newMajorTickVisFlatTypeID,newMinorTickVisFlatTypeID,newTickColFlatTypeID,):
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_axes_ticks.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newValPairPropsTypeDesc, newValPairPropsFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    minMaxRangeTDList = []
    minMaxClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumFloat32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Min","Max",):
            tmpTypeDesc.set("Label",labelStr)
            newPartTypeDesc, newPartFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        minMaxClustTDList.append(newPartFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC0F57F25))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Format","inline")
        for flatTypeID in minMaxClustTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("min_max.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        for labelStr in ("X","Y","Z","Amplitude",):
            tmpTDSub.set("Label",labelStr)
            newMinMaxTypeDesc, newMinMaxFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            minMaxRangeTDList.append(newMinMaxFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xCD273844))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","from/to cluster")
            tmpTDSub.set("Format","inline")
        for flatTypeID in minMaxRangeTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("range_cluster.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newMinMaxRngTypeDesc, newMinMaxRngFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    showCaptnsClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Show X Caption","Show Z Caption","Show Y Caption","Show Opposite X Caption","Show Opposite Y Caption","Show Opposite Z Caption",):
            tmpTypeDesc.set("Label",labelStr)
            newDrawTypeDesc, newDrawFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            showCaptnsClustTDList.append(newDrawFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Label","Show Captions")
        tmpTypeDesc.set("Format","inline")
        for flatTypeID in showCaptnsClustTDList:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(flatTypeID))
        newShowCaptnsTypeDesc, newShowCaptnsFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    captnStrClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","String")
        tmpTypeDesc.set("Prop1","0x{:04X}".format(0xFFFFFFFF))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Caption X","Caption Y","Caption Z",):
            tmpTypeDesc.set("Label",labelStr)
            newDrawTypeDesc, newDrawFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            captnStrClustTDList.append(newDrawFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Label","Captions")
        tmpTypeDesc.set("Format","inline")
        for flatTypeID in captnStrClustTDList:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(flatTypeID))
        newCaptnStrsTypeDesc, newCaptnStrsFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Label","Caption Color")
        tmpTypeDesc.set("Format","inline")
        for flatTypeID in gridColClustTDList:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(flatTypeID))
        newGridColTypeDesc, newGridColFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    captnFntSzClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumInt16")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Font Size X","Font Size Y","Font Size Z",):
            tmpTypeDesc.set("Label",labelStr)
            newDrawTypeDesc, newDrawFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            captnFntSzClustTDList.append(newDrawFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Label","Caption Font Size")
        tmpTypeDesc.set("Format","inline")
        for flatTypeID in captnFntSzClustTDList:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(flatTypeID))
        newCaptnFntSzTypeDesc, newCaptnFntSzFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC0F57723))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Caption Properties")
            tmpTDSub.set("Format","inline")
        for flatTypeID in (newShowCaptnsFlatTypeID,newCaptnStrsFlatTypeID,newGridColFlatTypeID,newCaptnFntSzFlatTypeID,):
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_axes_captions.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newMinMaxRngTypeDesc, newMinMaxRngFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    labelVisbClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Show X Labels","Show Y Labels","Show Z Labels","Show Opposite X Labels","Show Opposite Y Labels","Show Opposite Z Labels",):
            tmpTypeDesc.set("Label",labelStr)
            newBoolTypeDesc, newBoolFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            labelVisbClustTDList.append(newBoolFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Label","Label Visible")
        tmpTypeDesc.set("Format","inline")
        for flatTypeID in labelVisbClustTDList:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(flatTypeID))
        newLabelVisbTypeDesc, newLabelVisbFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Label","Label Color")
        tmpTypeDesc.set("Format","inline")
        for flatTypeID in gridColClustTDList:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(flatTypeID))
        newLabelColTypeDesc, newLabelColFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Label","Label Font Size")
        tmpTypeDesc.set("Format","inline")
        for flatTypeID in captnFntSzClustTDList:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(flatTypeID))
        newLabelFntSzTypeDesc, newLabelFntSzFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC28B6545))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Labels Properties")
            tmpTDSub.set("Format","inline")
        for flatTypeID in (newLabelVisbFlatTypeID,newLabelColFlatTypeID,newLabelFntSzFlatTypeID,):
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_axes_labels.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newMinMaxRngTypeDesc, newMinMaxRngFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC0F57746))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Auto Range On")
            tmpTDSub.set("Format","inline")
        for flatTypeID in mTickVisibClustTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_axes_autorange.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newAutoRangeTypeDesc, newAutoRangeFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xCD274C5E))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Axes Properties")
            tmpTDSub.set("Format","inline")
        for flatTypeID in (newValPairPropsFlatTypeID,newValPairPropsFlatTypeID,newMinMaxRngFlatTypeID,newMinMaxRngFlatTypeID,
              newAutoRangeFlatTypeID,newAutoRangeFlatTypeID,):
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_axes_all.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newAxesPropsTypeDesc, newAxesPropsFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        pacPropsFlatTypeIDList.append(newAxesPropsFlatTypeID)
    # Preparing newPACPropsFlatTypeID - part newCursrPropsArrFlatTypeID
    cursrPropsClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Cursor Visible","Cursor Enable",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            cursrPropsClustTDList.append(newPropFlatTypeID)
    cursrPtClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumUInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Point Color",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            cursrPtClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumFloat64")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Point Size",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            cursrPtClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Point Visible",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            cursrPtClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC0F577A1))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Cursor Point")
            tmpTDSub.set("Format","inline")
        for flatTypeID in cursrPtClustTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_cursor_point.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newCursrPtTypeDesc, newCursrPtFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        cursrPropsClustTDList.append(newCursrPtFlatTypeID)
    cursrPositClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumFloat64")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Position X","Position Y","Position Z",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            cursrPositClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTDSub.set("Type","UnitUInt16")
        tmpTDSub.set("Prop1",str(0))
        tmpTDSub.set("Label","Position Snap To")
        tmpTDSub.set("Format","inline")
        for labelStr in ("Fixed","Nearest Plot","Snap to Plot",):
            tmpLabel = ET.SubElement(tmpTDSub, "EnumLabel")
            tmpLabel.text = labelStr
        newPosSnapToTypeDesc, newPosSnapToFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        cursrPositClustTDList.append(newPosSnapToFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumUInt16")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Polsition Pick Plot",):
            tmpTypeDesc.set("Label",labelStr)
            newPoPickPlotTypeDesc, newPoPickPlotFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            cursrPositClustTDList.append(newPoPickPlotFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Position Column","Position Row",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            cursrPositClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC0F577B1))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Cursor Position")
            tmpTDSub.set("Format","inline")
        for flatTypeID in cursrPositClustTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_cursor_position.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newCursrPropsClustTypeDesc, newCursrPropsClustFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    cursrLineClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumUInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Line Color",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            cursrLineClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumFloat64")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Line Width",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            cursrLineClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Line Visible",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            cursrLineClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC0F577C4))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Cursor Line")
            tmpTDSub.set("Format","inline")
        for flatTypeID in cursrLineClustTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_cursor_line.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newCursrLineClustTypeDesc, newCursrLineClustFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    cursrPlaneClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumFloat64")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Plane Opacity",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            cursrPlaneClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumUInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Plane Color",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            cursrPlaneClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Plane YZ","Plane XZ","Plane XY",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            cursrPlaneClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC0F577DC))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Cursor Plane")
            tmpTDSub.set("Format","inline")
        for flatTypeID in cursrPlaneClustTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_cursor_plane.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newCursrPlaneClustTypeDesc, newCursrPlaneClustFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    cursrTextClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","String")
        tmpTypeDesc.set("Prop1","0x{:04X}".format(0xFFFFFFFF))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Cursor Name",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            cursrTextClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Font Size",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            cursrTextClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Show Position","Show Name",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            cursrTextClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumUInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Text Color","Back Color",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            cursrTextClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumFloat64")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Opacity",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            cursrTextClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC0F577FD))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Cursor Text")
            tmpTDSub.set("Format","inline")
        for flatTypeID in cursrTextClustTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_cursor_text.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newCursrTextClustTypeDesc, newCursrTextClustFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Label","Cursor Properties")
        tmpTypeDesc.set("Format","inline")
        for flatTypeID in newCursrTextClustTypeDesc:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        newCursrPropsClustTypeDesc, newCursrPropsClustFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC342AF5A))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Array")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Cursor Properties Array")
            tmpTDSub.set("Format","inline")
        for i in range(1):
            tmpTDSSub = ET.SubElement(tmpTDSub, "Dimension")
            tmpTDSSub.set("Flags","0x{:02X}".format(0xFF))
            tmpTDSSub.set("FixedSize","0x{:06X}".format(0xFFFFFF))
        for flatTypeID in (newCursrPropsClustFlatTypeID,):
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_cursor_all_array.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newCursrPropsArrTypeDesc, newCursrPropsArrFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        pacPropsFlatTypeIDList.append(newCursrPropsArrFlatTypeID)
    # Preparing newPACPropsFlatTypeID - part newFmtStrClustFlatTypeID
    fmtStrClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","String")
        tmpTypeDesc.set("Prop1","0x{:04X}".format(0xFFFFFFFF))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("XAxis","YAxis","ZAxis",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            fmtStrClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC2C2B1EA))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Format strings")
            tmpTDSub.set("Format","inline")
        for flatTypeID in fmtStrClustTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_format.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newFmtStrClustTypeDesc, newFmtStrClustFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        pacPropsFlatTypeIDList.append(newFmtStrClustFlatTypeID)
    # Preparing newPACPropsFlatTypeID - part newLightPropsClustFlatTypeID
    lightPropsClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Brightness",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            lightPropsClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumFloat64")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Focus","Linear Attenuation","Quadratic Attenuation",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            lightPropsClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xC2EC3091))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Lighting Properties")
            tmpTDSub.set("Format","inline")
        for flatTypeID in lightPropsClustTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","prop_lighting.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newLightPropsClustTypeDesc, newLightPropsClustFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        pacPropsFlatTypeIDList.append(newLightPropsClustFlatTypeID)
    lightsClustTDList = []
    xyzCoordClustTDList = []
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumFloat32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("X","Y","Z",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            xyzCoordClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Format","inline")
        for flatTypeID in xyzCoordClustTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("Position","Direction",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            lightsClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Label","Cluster")
        tmpTypeDesc.set("Format","inline")
        for flatTypeID in lightsClustTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        newLightsClustTypeDesc, newLightsClustFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Array")
        tmpTypeDesc.set("Nested","True")
        tmpTypeDesc.set("Label","Lights")
        tmpTypeDesc.set("Format","inline")
        for i in range(1):
            tmpTDSub = ET.SubElement(tmpTypeDesc, "Dimension")
            tmpTDSub.set("Flags","0x{:02X}".format(0xFF))
            tmpTDSub.set("FixedSize","0x{:06X}".format(0xFFFFFF))
        for flatTypeID in (newLightsClustFlatTypeID,):
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        newLightsArrTypeDesc, newLightsArrFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        pacPropsFlatTypeIDList.append(newLightsArrFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0xCD274C5E))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Plot/Axes/Cursor Properties")
            tmpTDSub.set("Format","inline")
        for newTmpFlatTypeID in pacPropsFlatTypeIDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(newTmpFlatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","all_non_graph_prop.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        allPropsClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Active Plot","Active Axis","Active Cursor",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            allPropsClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Format","inline")
        for labelStr in ("Disable Updates",):
            tmpTypeDesc.set("Label",labelStr)
            newPropTypeDesc, newPropFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            allPropsClustTDList.append(newPropFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:X}".format(0))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","All Properties")
            tmpTDSub.set("Format","inline")
        for flatTypeID in allPropsClustTDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(flatTypeID))
        for labelStr in ("3DPC_SurfacePlot.xctl","State.ctl",):
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text",labelStr)
        newAllPropsClustTypeDesc, newAllPropsClustFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    return newAllPropsClustTypeDesc, newAllPropsClustFlatTypeID

def VCTP_add_2DPlotDatatypeTD_for_DTHP(RSRC, fo, po, fpClassEx, VCTP):
    """ Adds 2D Plot Datatype TD to VCTP and Top Types List
    """
    if   fpClassEx in ("xControl:2D Error Bar Plot.vi",):
        dcoUDCRefClass = "2D Error Bar"
    elif fpClassEx in ("xControl:2D Feather Plot.vi",):
        dcoUDCRefClass = "2D Feather"
    elif fpClassEx in ("xControl:2D Compass",):
        dcoUDCRefClass = "2D Compass"
    else:
        raise RuntimeError("Unsupported fpClassEx")
    dcoFpColorProps = ["Main Frame Color","Plot Legend Color"]
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Refnum")
        tmpTypeDesc.set("RefType","UDClassInst")
        tmpTypeDesc.set("Field0","0x{:04X}".format(0))
        tmpTypeDesc.set("MultiItem",str(1))
        tmpTypeDesc.set("Label","{}.lvclass".format(dcoUDCRefClass))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "Item")
            tmpTDSub.set("Text","{}.lvclass".format(dcoUDCRefClass))
        newUDCRefTypeDesc, newUDCRefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumFloat64")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Label","X")
        tmpTypeDesc.set("Format","inline")
        newFltXTypeDesc, newFltXFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if newFltXTypeDesc is not None:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Array")
        tmpTypeDesc.set("Label","Vertex X Array")
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "Dimension")
            tmpTDSub.set("Flags","0x{:02X}".format(0xFF))
            tmpTDSub.set("FixedSize","0x{:06X}".format(0xFFFFFF))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newFltXTypeDesc))
        newArr1XTypeDesc, newArr1XFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        tmpTypeDesc.set("Label","Vertex Y Array")
        newArr1YTypeDesc, newArr1YFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if newArr1YTypeDesc is not None:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Label","Vertex Cluster")
        tmpTypeDesc.set("Format","inline")
        for newFlatTypeID in (newArr1XFlatTypeID,newArr1YFlatTypeID,):
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newFlatTypeID))
        newVertClustTypeDesc, newVertClustFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if newVertClustTypeDesc is not None:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Array")
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "Dimension")
            tmpTDSub.set("Flags","0x{:02X}".format(0xFF))
            tmpTDSub.set("FixedSize","0x{:06X}".format(0xFFFFFF))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newVertClustFlatTypeID))
        newVertClustArrTypeDesc, newVertClustArrFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Refnum")
        tmpTypeDesc.set("RefType","LVObjCtl")
        tmpTypeDesc.set("CtlFlags","0x{:04X}".format(0x0053))
        tmpTypeDesc.set("HasItem",str(0))
        tmpTypeDesc.set("Label","Plot Area Ref")
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newVertClustArrFlatTypeID))
        newLVOb1RefTypeDesc, newLVOb1RefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        tmpTypeDesc.set("Label","Z Axis Ref")
        newLVOb2RefTypeDesc, newLVOb2RefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","String")
        tmpTypeDesc.set("Prop1",str(0xFFFFFFFF))
        tmpTypeDesc.set("Label","String")
        tmpTypeDesc.set("Format","inline")
        newStrTypeDesc, newStrFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Picture")
        tmpTypeDesc.set("Prop1",str(0xFFFFFFFF))
        tmpTypeDesc.set("Label","Picture")
        tmpTypeDesc.set("Format","inline")
        newPictTypeDesc, newPictFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Label","Color Pair")
        tmpTypeDesc.set("Format","inline")
        for newFlatTypeID in (newStrFlatTypeID,newPictFlatTypeID,):
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newFlatTypeID))
        newColrPairTypeDesc, newColrPairFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if newColrPairTypeDesc is not None:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Array")
        tmpTypeDesc.set("Label","Color Pair Array")
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "Dimension")
            tmpTDSub.set("Flags","0x{:02X}".format(0xFF))
            tmpTDSub.set("FixedSize","0x{:06X}".format(0xFFFFFF))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newColrPairFlatTypeID))
        newColPaArrTypeDesc, newColPaArrFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if newColPaArrTypeDesc is not None:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Format","inline")
        for newFlatTypeID in (newColPaArrFlatTypeID,):
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newFlatTypeID))
        newColPaAClustTypeDesc, newColPaAClustFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if newColPaAClustTypeDesc:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Refnum")
        tmpTypeDesc.set("RefType","LVObjCtl")
        tmpTypeDesc.set("CtlFlags","0x{:04X}".format(0x001E))
        tmpTypeDesc.set("HasItem",str(0))
        tmpTypeDesc.set("Label","Legend Ref")
        tmpTypeDesc.set("Format","inline")
        for newFlatTypeID in (newColPaAClustFlatTypeID,):
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newFlatTypeID))
        newLVOb3RefTypeDesc, newLVOb3RefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Refnum")
        tmpTypeDesc.set("RefType","LVObjCtl")
        tmpTypeDesc.set("CtlFlags","0x{:04X}".format(0x0006))
        tmpTypeDesc.set("HasItem",str(0))
        tmpTypeDesc.set("Label","XControl Ref")
        tmpTypeDesc.set("Format","inline")
        newLVOb4RefTypeDesc, newLVOb4RefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Refnum")
        tmpTypeDesc.set("RefType","LVObjCtl")
        tmpTypeDesc.set("CtlFlags","0x{:04X}".format(0x004F))
        tmpTypeDesc.set("HasItem",str(0))
        tmpTypeDesc.set("Label","Facade Ref")
        tmpTypeDesc.set("Format","inline")
        newLVOb5RefTypeDesc, newLVOb5RefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0x0))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","UnitUInt16")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Prop1",str(0))
            tmpTDSub.set("Label","Display State Change Class")
            tmpTDSub.set("Format","inline")
        for labelStr in ("Update All (Undo)","Update General","Update Appearance", \
              "Update Format","Update Scale","Update Marker","Update Cursor","None",):
            tmpLabel = ET.SubElement(tmpTDSub, "EnumLabel")
            tmpLabel.text = labelStr
        if True:
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text","2DMathPlot State Class.ctl")
        newTDDiStChClTypeDesc, newTDDiStChClFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0x0))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Control Ref Cluster")
            tmpTDSub.set("Format","inline")
        for newFlatTypeID in (newLVOb1RefFlatTypeID,newLVOb2RefFlatTypeID,newLVOb3RefFlatTypeID,
              newLVOb4RefFlatTypeID,newLVOb5RefFlatTypeID,newTDDiStChClFlatTypeID,):
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newFlatTypeID))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "Label")
            tmpTDSub.set("Text","2DMathPlot Ctrl Act Cluster.ctl")
        newTDCtlRefTypeDesc, newTDCtlRefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0x0))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Refnum")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("RefType","Queue")
            tmpTDSub.set("Label","Control Ref Queue")
            tmpTDSub.set("Format","inline")
        if True:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(newTDCtlRefFlatTypeID))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "Label")
            tmpTDSub.set("Text","2DMathPlot Ctrl Act Queue.ctl")
        newTDDiStChClTypeDesc, newTDDiStChClFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    stateSubFlatTypeIDList = [newUDCRefFlatTypeID, newTDDiStChClFlatTypeID]
    for labelStr in dcoFpColorProps:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumUInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        newTmpTypeDesc, newTmpFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        stateSubFlatTypeIDList.append(newTmpFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0x0))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","State")
            tmpTDSub.set("Format","inline")
        for newTmpFlatTypeID in stateSubFlatTypeIDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(newTmpFlatTypeID))
        if True:
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text","{}.xctl".format(dcoUDCRefClass))
        if True:
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text","State.ctl")
        newStateTypeDesc, newStateFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    return newStateTypeDesc, newStateFlatTypeID

def VCTP_add_3DPlotDatatypeTD_for_DTHP(RSRC, fo, po, fpClassEx, VCTP):
    """ Adds 3D Plot Datatype TD to VCTP and Top Types List
    """
    if   fpClassEx in ("xControl:3D_Bar_Plot_Merge_VI.vi",):
        dcoUDCRefClass = "3D Bar"
    elif fpClassEx in ("xControl:3D_Comet_Plot_Merge_VI.vi",):
        dcoUDCRefClass = "3D Comet"
    elif fpClassEx in ("xControl:3D_Contour_Plot_Merge_VI.vi",):
        dcoUDCRefClass = "3D Contour"
    elif fpClassEx in ("xControl:3D_Mesh_Plot_Merge_VI.vi",):
        dcoUDCRefClass = "3D Mesh"
    elif fpClassEx in ("xControl:3D_Pie_Plot_Merge_VI.vi",):
        dcoUDCRefClass = "3D Pie"
    elif fpClassEx in ("xControl:3D_Quiver_Plot_Merge_VI.vi",):
        dcoUDCRefClass = "3D Quiver"
    elif fpClassEx in ("xControl:3D_Ribbon_Plot_Merge_VI.vi",):
        dcoUDCRefClass = "3D Ribbon"
    elif fpClassEx in ("xControl:3D_Scatter_Plot_Merge_VI.vi",):
        dcoUDCRefClass = "3D Scatter"
    elif fpClassEx in ("xControl:3D_Stem_Plot_Merge_VI.vi",):
        dcoUDCRefClass = "3D Stem"
    elif fpClassEx in ("xControl:3D_Surface_Plot_Merge_VI.vi",):
        dcoUDCRefClass = "3D Surface"
    elif fpClassEx in ("xControl:3D_Waterfall_Plot_Merge_VI.vi",):
        dcoUDCRefClass = "3D Waterfall"
    else:
        raise RuntimeError("Unsupported fpClassEx")
    dcoFpColorProps = ["Main Frame Color","Ramp Palette Color","Projection Palette Color"]
    if fpClassEx in ("xControl:3D_Bar_Plot_Merge_VI.vi","xControl:3D_Pie_Plot_Merge_VI.vi",):
        dcoFpColorProps.insert(0,"Plot Width")
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Refnum")
        tmpTypeDesc.set("RefType","UDClassInst")
        tmpTypeDesc.set("Field0","0x{:04X}".format(0))
        tmpTypeDesc.set("MultiItem",str(1))
        tmpTypeDesc.set("Label","{}.lvclass".format(dcoUDCRefClass))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "Item")
            tmpTDSub.set("Text","{}.lvclass".format(dcoUDCRefClass))
        newUDCRefTypeDesc, newUDCRefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Refnum")
        tmpTypeDesc.set("RefType","LVObjCtl")
        tmpTypeDesc.set("CtlFlags","0x{:04X}".format(0x0068))
        tmpTypeDesc.set("HasItem",str(0))
        tmpTypeDesc.set("Format","inline")
        newLVOb1SubRefTypeDesc, newLVOb1SubRefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Refnum")
        tmpTypeDesc.set("RefType","LVObjCtl")
        tmpTypeDesc.set("CtlFlags","0x{:04X}".format(0x0064))
        tmpTypeDesc.set("HasItem",str(0))
        tmpTypeDesc.set("Label","3D Picture Control")
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newLVOb1SubRefFlatTypeID))
        newLVOb1RefTypeDesc, newLVOb1RefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Refnum")
        tmpTypeDesc.set("RefType","LVObjCtl")
        tmpTypeDesc.set("CtlFlags","0x{:04X}".format(0x0054))
        tmpTypeDesc.set("HasItem",str(0))
        tmpTypeDesc.set("Format","inline")
        newLVOb2SubRefTypeDesc, newLVOb2SubRefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Refnum")
        tmpTypeDesc.set("RefType","LVObjCtl")
        tmpTypeDesc.set("CtlFlags","0x{:04X}".format(0x003B))
        tmpTypeDesc.set("HasItem",str(0))
        tmpTypeDesc.set("Label","Render Window Refnum")
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newLVOb2SubRefFlatTypeID))
        newLVOb2RefTypeDesc, newLVOb2RefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumFloat64")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        newFltTypeDesc, newFltFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if newFltTypeDesc is not None:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Format","inline")
        for i in range(2):
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newFltFlatTypeID))
        newArrInnerTypeDesc, newArrInnerFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if newArrInnerTypeDesc is not None:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Array")
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "Dimension")
            tmpTDSub.set("Flags","0x{:02X}".format(0xFF))
            tmpTDSub.set("FixedSize","0x{:06X}".format(0xFFFFFF))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newArrInnerFlatTypeID))
        newArr3TypeDesc, newArr3FlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Refnum")
        tmpTypeDesc.set("RefType","LVObjCtl")
        tmpTypeDesc.set("CtlFlags","0x{:04X}".format(0x0053))
        tmpTypeDesc.set("HasItem",str(0))
        tmpTypeDesc.set("Label","XY Graph")
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newArr3FlatTypeID))
        newLVOb3RefTypeDesc, newLVOb3RefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Array")
        tmpTypeDesc.set("Format","inline")
        for i in range(2):
            tmpTDSub = ET.SubElement(tmpTypeDesc, "Dimension")
            tmpTDSub.set("Flags","0x{:02X}".format(0xFF))
            tmpTDSub.set("FixedSize","0x{:06X}".format(0xFFFFFF))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newFltFlatTypeID))
        newArr4TypeDesc, newArr4FlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Refnum")
        tmpTypeDesc.set("RefType","LVObjCtl")
        tmpTypeDesc.set("CtlFlags","0x{:04X}".format(0x001A))
        tmpTypeDesc.set("HasItem",str(0))
        tmpTypeDesc.set("Label","Intensity Graph")
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newArr4FlatTypeID))
        newLVOb4RefTypeDesc, newLVOb4RefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Refnum")
        tmpTypeDesc.set("RefType","LVObjCtl")
        tmpTypeDesc.set("CtlFlags","0x{:04X}".format(0x001E))
        tmpTypeDesc.set("HasItem",str(0))
        tmpTypeDesc.set("Label","Color Legend Palette")
        tmpTypeDesc.set("Format","inline")
        newLVOb5RefTypeDesc, newLVOb5RefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Refnum")
        tmpTypeDesc.set("RefType","LVObjCtl")
        tmpTypeDesc.set("CtlFlags","0x{:04X}".format(0x001E))
        tmpTypeDesc.set("HasItem",str(0))
        tmpTypeDesc.set("Label","Projection Palette")
        tmpTypeDesc.set("Format","inline")
        newLVOb6RefTypeDesc, newLVOb6RefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Refnum")
        tmpTypeDesc.set("RefType","LVObjCtl")
        tmpTypeDesc.set("CtlFlags","0x{:04X}".format(0x0006))
        tmpTypeDesc.set("HasItem",str(0))
        tmpTypeDesc.set("Label","XControl  Ref")
        tmpTypeDesc.set("Format","inline")
        newLVOb7RefTypeDesc, newLVOb7RefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Refnum")
        tmpTypeDesc.set("RefType","LVObjCtl")
        tmpTypeDesc.set("CtlFlags","0x{:04X}".format(0x004F))
        tmpTypeDesc.set("HasItem",str(0))
        tmpTypeDesc.set("Label","Facade Ref")
        tmpTypeDesc.set("Format","inline")
        newLVOb8RefTypeDesc, newLVOb8RefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Refnum")
        tmpTypeDesc.set("RefType","LVObjCtl")
        tmpTypeDesc.set("CtlFlags","0x{:04X}".format(0x000F))
        tmpTypeDesc.set("HasItem",str(0))
        tmpTypeDesc.set("Label","Export Image Ref")
        tmpTypeDesc.set("Format","inline")
        newLVOb9RefTypeDesc, newLVOb9RefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Boolean")
        tmpTypeDesc.set("Label","Clear Data Flag")
        tmpTypeDesc.set("Format","inline")
        newClrDtFlgTypeDesc, newClrDtFlgFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0x0))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","UnitUInt16")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Prop1",str(0))
            tmpTDSub.set("Label","Display State Change Class")
            tmpTDSub.set("Format","inline")
        for labelStr in ("Update All Objects (Undo)","Update Light Object Only","Update Axis Object Only", \
              "Update Plot Object Only","Update Cursor Object Only","Update Axis Plot Cursor Objects","No Update",):
            tmpLabel = ET.SubElement(tmpTDSub, "EnumLabel")
            tmpLabel.text = labelStr
        if True:
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text","3DMathPlot State Class.ctl")
        newTDDiStChClTypeDesc, newTDDiStChClFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0x0))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","Control Ref Cluster")
            tmpTDSub.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newLVOb1RefFlatTypeID))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newLVOb2RefFlatTypeID))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newLVOb3RefFlatTypeID))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newLVOb4RefFlatTypeID))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newLVOb5RefFlatTypeID))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newLVOb6RefFlatTypeID))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newLVOb7RefFlatTypeID))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newLVOb8RefFlatTypeID))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newLVOb9RefFlatTypeID))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newClrDtFlgFlatTypeID))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newTDDiStChClFlatTypeID))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "Label")
            tmpTDSub.set("Text","3DMathPlot Ctrl Act Cluster.ctl")
        newTDCtlRefTypeDesc, newTDCtlRefFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0x0))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Refnum")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("RefType","Queue")
            tmpTDSub.set("Label","Control Ref Queue")
            tmpTDSub.set("Format","inline")
        if True:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(newTDCtlRefFlatTypeID))
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "Label")
            tmpTDSub.set("Text","3DMathPlot Ctrl Act Queue.ctl")
        newTDDiStChClTypeDesc, newTDDiStChClFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    stateSubFlatTypeIDList = [newUDCRefFlatTypeID, newTDDiStChClFlatTypeID]
    for labelStr in dcoFpColorProps:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","NumUInt32")
        tmpTypeDesc.set("Prop1",str(0))
        tmpTypeDesc.set("Format","inline")
        newTmpTypeDesc, newTmpFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        stateSubFlatTypeIDList.append(newTmpFlatTypeID)
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","TypeDef")
        tmpTypeDesc.set("Flag1","0x{:04X}".format(0x0))
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("Type","Cluster")
            tmpTDSub.set("Nested","True")
            tmpTDSub.set("Label","State")
            tmpTDSub.set("Format","inline")
        for newTmpFlatTypeID in stateSubFlatTypeIDList:
            tmpTDSSub = ET.SubElement(tmpTDSub, "TypeDesc")
            tmpTDSSub.set("TypeID",str(newTmpFlatTypeID))
        if True:
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text","{}.xctl".format(dcoUDCRefClass))
        if True:
            tmpLabel = ET.SubElement(tmpTypeDesc, "Label")
            tmpLabel.set("Text","State.ctl")
        newStateTypeDesc, newStateFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    return newStateTypeDesc, newStateFlatTypeID

def VCTP_add_XYPlotMatrixTD_for_DTHP(RSRC, fo, po, fpClassEx, VCTP):
    """ Adds Base Datatype TD to VCTP and Top Types List
    """
    newSrcFlatTypeID = 0 #TODO
    if True:
        tmpTypeDesc = ET.Element("TypeDesc")
        tmpTypeDesc.set("Type","Cluster")
        tmpTypeDesc.set("Label","error")
        tmpTypeDesc.set("Format","inline")
        if True:
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newSrcFlatTypeID))
        newErrClustTypeDesc, newErrClustFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
    return newErrClustTypeDesc, newErrClustFlatTypeID

def DCO_recognize_fpClassEx_list_from_dco_and_ex_TypeDesc(RSRC, fo, po, dcoTypeDesc, dcoFlatTypeID, \
      dcoExTypeDesc, dcoFlatExTypeID, VCTP_FlatTypeDescList=None):
    """ Recognizes DCO class using DCO and Ex typeIDs of the DCO as input
    """
    # Get list of flat types for the recognition finction
    if VCTP_FlatTypeDescList is None:
        VCTP = RSRC.find("./VCTP/Section")
        if VCTP is not None:
            VCTP_FlatTypeDescList = VCTP.findall("TypeDesc")
    matchingClasses = DCO_recognize_fpClassEx_list_from_single_TypeDesc(RSRC, fo, po, VCTP_FlatTypeDescList, dcoTypeDesc)
    if len(matchingClasses) < 1:
        return []
    if VCTP_FlatTypeDescList is None:
        return matchingClasses
    # Narrow down the list of matchingClasses based on Extra TypeID
    #TODO add the narrowing when neccessary
    return matchingClasses

def DCO_create_VCTP_heap_entries(RSRC, fo, po, dcoIndex, dcoTypeDesc, dcoFlatTypeID, \
      dcoExTypeDesc, dcoFlatExTypeID, VCTP, VCTP_TopLevel, indexShift):
    """ For a single DCO, re-creates VCTP entries with Heap Data Types, to be used for DTHP

    Given TypeDesc elements from DCO definition, it prepares required TypeDesc range
    with TDs to be used in Front Panel Heap.
    """
    nIndexShift = indexShift
    # Get class name for this DCO
    VCTP_FlatTypeDescList = VCTP.findall("TypeDesc")
    matchingClasses = DCO_recognize_fpClassEx_list_from_dco_and_ex_TypeDesc(RSRC, fo, po, dcoTypeDesc, dcoFlatTypeID, \
      dcoExTypeDesc, dcoFlatExTypeID, VCTP_FlatTypeDescList=VCTP_FlatTypeDescList)
    if len(matchingClasses) < 1: # A default to avoid the function crashing
        print("Warning: No DCO fpClass recognized from DCO TDs")
        matchingClasses.append("stdNum:Numeric")
    # Almost every entry starts with DCO TypeDesc
    hasDcoTd = not any(fpClassEx in ("grouper:Sub Panel",) for fpClassEx in matchingClasses)
    # All have DDO TypeDesc
    hasDdoTd = True
    if hasDcoTd:
        VCTP_add_TopTypeDesc(RSRC, fo, po, dcoFlatTypeID, nTopTDIndex=nIndexShift)
        nIndexShift += 1
    # Between DCO and DDO TypeDescs, there are extra types
    filterClasses = [fpClassEx for fpClassEx in matchingClasses if fpClassEx in ("radioClust:Radio Buttons",)]
    if len(filterClasses) > 0:
        matchingClasses = filterClasses
        pass # No need to process this type now, but filter it to give it priority over "Tab Control"
    filterClasses = [fpClassEx for fpClassEx in matchingClasses if fpClassEx in ("typeDef:RealMatrix.ctl","typeDef:ComplexMatrix.ctl",)]
    if len(filterClasses) > 0:
        matchingClasses = filterClasses
        dcoInnerTypeDesc = dcoTypeDesc.find("./TypeDesc[@Type]")
        nDimensions = len(dcoInnerTypeDesc.findall("./Dimension"))
        dcoSubDMap = dcoInnerTypeDesc.find("./TypeDesc[@TypeID]")
        dcoExTDMapList = dcoExTypeDesc.findall("./TypeDesc[@TypeID]")
        dcoExArrTypeDesc = None
        for dcoExTDMap in dcoExTDMapList:
            dcoExSubTypeDesc, _, dcoFlatExSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, dcoExTDMap, po)
            if dcoExSubTypeDesc.get("Type") == "Array":
                dcoExArrTypeDesc = dcoExSubTypeDesc
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","NumUInt32")
            tmpTypeDesc.set("Prop1",str(0))
            tmpTypeDesc.set("Format","inline")
            newIdxTypeDesc, newIdxFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        # Add a copy of the Array from ExtraTD
        newArrTypeDesc, newArrFlatTypeID = VCTP_add_TypeDesc_copy(RSRC, fo, po, dcoExArrTypeDesc)
        # Create Top Types
        VCTP_FlatTypeDescList = VCTP.findall("TypeDesc")
        for ndim in range(nDimensions):
            _, nIndexShift = VCTP_add_TopTypeDesc_for_DTHP(RSRC, fo, po, newIdxTypeDesc, newIdxFlatTypeID, \
                  nTopTDIndex=nIndexShift, VCTP_FlatTypeDescList=VCTP_FlatTypeDescList, VCTP_TopLevel=VCTP_TopLevel)
            nIndexShift += 1
        _, nIndexShift = VCTP_add_TopTypeDesc_for_DTHP(RSRC, fo, po, newArrTypeDesc, newArrFlatTypeID, \
              nTopTDIndex=nIndexShift, VCTP_FlatTypeDescList=VCTP_FlatTypeDescList, VCTP_TopLevel=VCTP_TopLevel)
        nIndexShift += 1
    filterClasses = [fpClassEx for fpClassEx in matchingClasses if fpClassEx in ("tabControl:Tab Control",)]
    if len(filterClasses) > 0:
        matchingClasses = filterClasses
        # Add a copy of the DCO TD
        newUntTypeDesc, newUntFlatTypeID = VCTP_add_TypeDesc_copy(RSRC, fo, po, dcoTypeDesc)
        # We need Int after that
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","NumInt32")
            tmpTypeDesc.set("Prop1",str(0))
            tmpTypeDesc.set("Format","inline")
            newNumTypeDesc, newNumFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        # Create Top Types
        VCTP_FlatTypeDescList = VCTP.findall("TypeDesc")
        _, nIndexShift = VCTP_add_TopTypeDesc_for_DTHP(RSRC, fo, po, newUntTypeDesc, newUntFlatTypeID, \
              nTopTDIndex=nIndexShift, VCTP_FlatTypeDescList=VCTP_FlatTypeDescList, VCTP_TopLevel=VCTP_TopLevel)
        nIndexShift += 1
        _, nIndexShift = VCTP_add_TopTypeDesc_for_DTHP(RSRC, fo, po, newNumTypeDesc, newNumFlatTypeID, \
              nTopTDIndex=nIndexShift, VCTP_FlatTypeDescList=VCTP_FlatTypeDescList, VCTP_TopLevel=VCTP_TopLevel)
        nIndexShift += 1
    filterClasses = [fpClassEx for fpClassEx in matchingClasses if fpClassEx in ("typeDef:LabVIEW Test - Invocation Info.ctl",
          "typeDef:LabVIEW Test - Test Data.ctl",)]
    if len(filterClasses) > 0:
        matchingClasses = filterClasses
        dcoInnerTypeDesc = dcoTypeDesc.find("./TypeDesc[@Type='Cluster']")
        newInnTypeDesc, newFlatInnTypeID = VCTP_add_TypeDesc_copy(RSRC, fo, po, dcoInnerTypeDesc)
        dcoSubTDMapList = dcoInnerTypeDesc.findall("./TypeDesc[@TypeID]")
        # Create Top Types
        VCTP_FlatTypeDescList = VCTP.findall("TypeDesc")
        if newInnTypeDesc is not None:
            VCTP_add_TopTypeDesc(RSRC, fo, po, newFlatInnTypeID, nTopTDIndex=nIndexShift, VCTP_TopLevel=VCTP_TopLevel)
            nIndexShift += 1
        for SubTDMap in reversed(dcoSubTDMapList):
            dcoSubTypeDesc, _, dcoFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, SubTDMap, po)
            VCTP_add_TopTypeDesc(RSRC, fo, po, dcoFlatSubTypeID, nTopTDIndex=nIndexShift, VCTP_TopLevel=VCTP_TopLevel)
            nIndexShift += 1
    filterClasses = [fpClassEx for fpClassEx in matchingClasses if fpClassEx in ("stdGraph:Digital Waveform Graph", \
          "stdGraph:Waveform Graph","stdGraph:Intensity Chart","stdGraph:XY Graph","stdGraph:Express XY Graph", \
          "stdGraph:Waveform Chart",)]
    if len(filterClasses) > 0:
        matchingClasses = filterClasses
        # Find or add a few basic types we will use
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","NumUInt32")
            tmpTypeDesc.set("Prop1",str(0))
            tmpTypeDesc.set("Format","inline")
            newNumUTypeDesc, newNumUFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","String")
            tmpTypeDesc.set("Prop1",str(0xFFFFFFFF))
            tmpTypeDesc.set("Format","inline")
            newStrTypeDesc, newStrFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","Boolean")
            tmpTypeDesc.set("Format","inline")
            newBoolTypeDesc, newBoolFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        # Now construct and add the compound types
        filterClasses = [fpClassEx for fpClassEx in matchingClasses if fpClassEx in ("stdGraph:Digital Waveform Graph", \
              "stdGraph:Waveform Graph","stdGraph:XY Graph","stdGraph:Express XY Graph","stdGraph:Waveform Chart",)]
        if len(filterClasses) > 0:
            matchingClasses = filterClasses
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","Cluster")
            tmpTypeDesc.set("Format","inline")
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newStrFlatTypeID))
            for i in range(2):
                tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
                tmpTDSub.set("TypeID",str(newBoolFlatTypeID))
            newClust1TypeDesc, newClust1FlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        else:
            newClust1TypeDesc, newClust1FlatTypeID = None, None
        if newClust1TypeDesc is not None:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","Array")
            tmpTypeDesc.set("Format","inline")
            tmpTDSub = ET.SubElement(tmpTypeDesc, "Dimension")
            tmpTDSub.set("Flags","0x{:02X}".format(0xFF))
            tmpTDSub.set("FixedSize","0x{:06X}".format(0xFFFFFF))
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newClust1FlatTypeID))
            newArr1TypeDesc, newArr1FlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        else:
            newArr1TypeDesc, newArr1FlatTypeID = None, None
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","Cluster")
            tmpTypeDesc.set("Format","inline")
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newStrFlatTypeID))
            for i in range(3):
                tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
                tmpTDSub.set("TypeID",str(newBoolFlatTypeID))
            newClust2TypeDesc, newClust2FlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        if newClust2TypeDesc is not None:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","Array")
            tmpTypeDesc.set("Format","inline")
            tmpTDSub = ET.SubElement(tmpTypeDesc, "Dimension")
            tmpTDSub.set("Flags","0x{:02X}".format(0xFF))
            tmpTDSub.set("FixedSize","0x{:06X}".format(0xFFFFFF))
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newClust2FlatTypeID))
            newArr2TypeDesc, newArr2FlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        else:
            newArr2TypeDesc, newArr2FlatTypeID = None, None
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","Cluster")
            tmpTypeDesc.set("Format","inline")
            for i in range(4):
                tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
                tmpTDSub.set("TypeID",str(newBoolFlatTypeID))
            newClust3TypeDesc, newClust3FlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","Array")
            tmpTypeDesc.set("Format","inline")
            tmpTDSub = ET.SubElement(tmpTypeDesc, "Dimension")
            tmpTDSub.set("Flags","0x{:02X}".format(0xFF))
            tmpTDSub.set("FixedSize","0x{:06X}".format(0xFFFFFF))
            tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
            tmpTDSub.set("TypeID",str(newStrFlatTypeID))
            newArr4TypeDesc, newArr4FlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        # Create Top Types
        VCTP_FlatTypeDescList = VCTP.findall("TypeDesc")
        if newArr1TypeDesc is not None:
            nIndexShift, _ = VCTP_add_TopTypeDesc(RSRC, fo, po, newNumUFlatTypeID, nTopTDIndex=nIndexShift)
            nIndexShift += 1
            _, nIndexShift = VCTP_add_TopTypeDesc_for_DTHP(RSRC, fo, po, newArr1TypeDesc, newArr1FlatTypeID, \
                  nTopTDIndex=nIndexShift, VCTP_FlatTypeDescList=VCTP_FlatTypeDescList, VCTP_TopLevel=VCTP_TopLevel)
            nIndexShift += 1
        if newArr2TypeDesc is not None:
            nIndexShift, _ = VCTP_add_TopTypeDesc(RSRC, fo, po, newNumUFlatTypeID, nTopTDIndex=nIndexShift)
            nIndexShift += 1
            _, nIndexShift = VCTP_add_TopTypeDesc_for_DTHP(RSRC, fo, po, newArr2TypeDesc, newArr2FlatTypeID, \
                  nTopTDIndex=nIndexShift, VCTP_FlatTypeDescList=VCTP_FlatTypeDescList, VCTP_TopLevel=VCTP_TopLevel)
            nIndexShift += 1
        if newClust3TypeDesc is not None:
            _, nIndexShift = VCTP_add_TopTypeDesc_for_DTHP(RSRC, fo, po, newClust3TypeDesc, newClust3FlatTypeID, \
                  nTopTDIndex=nIndexShift, VCTP_FlatTypeDescList=VCTP_FlatTypeDescList, VCTP_TopLevel=VCTP_TopLevel)
            nIndexShift += 1
        if newArr4TypeDesc is not None:
            # Some controls only have array, others have array followed by content TD
            if any(fpClassEx in ("stdGraph:Digital Waveform Graph",) for fpClassEx in matchingClasses):
                _, nIndexShift = VCTP_add_TopTypeDesc_for_DTHP(RSRC, fo, po, newArr4TypeDesc, newArr4FlatTypeID, \
                      nTopTDIndex=nIndexShift, VCTP_FlatTypeDescList=VCTP_FlatTypeDescList, VCTP_TopLevel=VCTP_TopLevel)
            else: # "stdGraph:Waveform Graph", "stdGraph:Intensity Chart"
                nIndexShift, _ = VCTP_add_TopTypeDesc(RSRC, fo, po, newArr4FlatTypeID, nTopTDIndex=nIndexShift)
            nIndexShift += 1
        if any(fpClassEx in ("stdGraph:Intensity Chart",) for fpClassEx in matchingClasses):
            for ndim in range(2):
                _, nIndexShift = VCTP_add_TopTypeDesc_for_DTHP(RSRC, fo, po, newNumUTypeDesc, newNumUFlatTypeID, \
                      nTopTDIndex=nIndexShift, VCTP_FlatTypeDescList=VCTP_FlatTypeDescList, VCTP_TopLevel=VCTP_TopLevel)
                nIndexShift += 1
    filterClasses = [fpClassEx for fpClassEx in matchingClasses if fpClassEx in ("stdMeasureData:Digital Waveform.ctl", \
          "stdMeasureData:Waveform",)]
    if len(filterClasses) > 0:
        matchingClasses = filterClasses
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","MeasureData")
            tmpTypeDesc.set("Flavor","TimeStamp")
            tmpTypeDesc.set("Label","t0")
            tmpTypeDesc.set("Format","inline")
            newT0TypeDesc, newT0FlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","NumFloat64")
            tmpTypeDesc.set("Prop1",str(0))
            tmpTypeDesc.set("Label","dt")
            tmpTypeDesc.set("Format","inline")
            newDtTypeDesc, newDtFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","MeasureData")
            tmpTypeDesc.set("Flavor","Digitaldata")
            tmpTypeDesc.set("Label","Y")
            tmpTypeDesc.set("Format","inline")
            newYTypeDesc, newYFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        newErrClustTypeDesc, newErrClustFlatTypeID = VCTP_add_ErrorClustTD_for_DTHP(RSRC, fo, po, VCTP=VCTP)
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","LVVariant")
            tmpTypeDesc.set("Label","attributes")
            tmpTypeDesc.set("Format","inline")
            newAttrTypeDesc, newAttrFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","Cluster")
            tmpTypeDesc.set("Format","inline")
            if True:
                tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
                tmpTDSub.set("TypeID",str(newT0FlatTypeID))
            if True:
                tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
                tmpTDSub.set("TypeID",str(newDtFlatTypeID))
            if True:
                tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
                tmpTDSub.set("TypeID",str(newYFlatTypeID))
            if True:
                tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
                tmpTDSub.set("TypeID",str(newErrClustFlatTypeID))
            if True:
                tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
                tmpTDSub.set("TypeID",str(newAttrFlatTypeID))
            newClust3TypeDesc, newClust3FlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        # Create Top Types
        VCTP_FlatTypeDescList = VCTP.findall("TypeDesc")
        if newClust3TypeDesc is not None:
            _, nIndexShift = VCTP_add_TopTypeDesc_for_DTHP(RSRC, fo, po, newClust3TypeDesc, newClust3FlatTypeID, \
                  nTopTDIndex=nIndexShift, VCTP_FlatTypeDescList=VCTP_FlatTypeDescList, VCTP_TopLevel=VCTP_TopLevel)
            nIndexShift += 1
    filterClasses = [fpClassEx for fpClassEx in matchingClasses if fpClassEx in ("tableControl:Table Control", \
          "tableControl:mergeTable.vi",)]
    if len(filterClasses) > 0:
        matchingClasses = filterClasses
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","NumUInt32")
            tmpTypeDesc.set("Prop1",str(0))
            tmpTypeDesc.set("Format","inline")
            newNumUTypeDesc, newNumUFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        # Create Top Types
        VCTP_FlatTypeDescList = VCTP.findall("TypeDesc")
        for i in range(2):
            _, nIndexShift = VCTP_add_TopTypeDesc_for_DTHP(RSRC, fo, po, newNumUTypeDesc, newNumUFlatTypeID, \
                  nTopTDIndex=nIndexShift, VCTP_FlatTypeDescList=VCTP_FlatTypeDescList, VCTP_TopLevel=VCTP_TopLevel)
            nIndexShift += 1
    # DDO TypeDesc
    if hasDdoTd:
        filterClasses = [fpClassEx for fpClassEx in matchingClasses if fpClassEx in ("stdClust:Cluster","stdClust:User Font.ctl", \
          "stdClust:Text Alignment.ctl","stdClust:Rect.ctl","stdClust:Point.ctl","stdGraph:Digital Waveform Graph",)]
        if len(filterClasses) > 0:
            _, nIndexShift = VCTP_add_TopTypeDesc_for_DTHP(RSRC, fo, po, dcoTypeDesc, dcoFlatTypeID, \
                  nTopTDIndex=nIndexShift, VCTP_FlatTypeDescList=VCTP_FlatTypeDescList, VCTP_TopLevel=VCTP_TopLevel)
            matchingClasses = filterClasses
        else:
            nIndexShift, _ = VCTP_add_TopTypeDesc(RSRC, fo, po, dcoFlatTypeID, nTopTDIndex=nIndexShift)
        nIndexShift += 1
    # Sub-types
    filterClasses = [fpClassEx for fpClassEx in matchingClasses if fpClassEx in ("radioClust:Radio Buttons",)]
    if len(filterClasses) > 0:
        matchingClasses = filterClasses
        enumLabelList = dcoTypeDesc.findall("./EnumLabel")
        newFlatTypeInfoList = []
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","Boolean")
            tmpTypeDesc.set("Format","inline")
            tmpTypeDesc.set("Label","")
        for enumLabel in enumLabelList:
            tmpTypeDesc.set("Label",enumLabel.text)
            newTypeDesc, newFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
            newFlatTypeInfoList.append((newFlatTypeID,newTypeDesc,))
        for newTypeInfo in newFlatTypeInfoList:
            _, nIndexShift = VCTP_add_TopTypeDesc_for_DTHP(RSRC, fo, po, newTypeInfo[1], newTypeInfo[0], \
                  nTopTDIndex=nIndexShift, VCTP_FlatTypeDescList=VCTP_FlatTypeDescList, VCTP_TopLevel=VCTP_TopLevel)
            nIndexShift += 1
    # Controls with UDClassInst References have additional state cluster; it is removed with FP on build
    newStateFlatTypeID = None
    filterClasses = [fpClassEx for fpClassEx in matchingClasses if fpClassEx in ("xControl:3D Line Graph.vi", \
          "xControl:3D Parametric Graph.vi","xControl:3D Surface Graph.vi",)]
    if len(filterClasses) > 0:
        matchingClasses = filterClasses
        newStateTypeDesc, newStateFlatTypeID = VCTP_add_BaseDatatypeTD_for_DTHP(RSRC, fo, po, filterClasses[0], VCTP)
    filterClasses = [fpClassEx for fpClassEx in matchingClasses if fpClassEx in ("xControl:2D Error Bar Plot.vi", \
          "xControl:2D Feather Plot.vi","xControl:2D Compass",)]
    if len(filterClasses) > 0:
        matchingClasses = filterClasses
        newStateTypeDesc, newStateFlatTypeID = VCTP_add_2DPlotDatatypeTD_for_DTHP(RSRC, fo, po, filterClasses[0], VCTP)
    filterClasses = [fpClassEx for fpClassEx in matchingClasses if fpClassEx in ("xControl:3D_Bar_Plot_Merge_VI.vi", \
          "xControl:3D_Comet_Plot_Merge_VI.vi","xControl:3D_Contour_Plot_Merge_VI.vi","xControl:3D_Mesh_Plot_Merge_VI.vi", \
          "xControl:3D_Pie_Plot_Merge_VI.vi","xControl:3D_Quiver_Plot_Merge_VI.vi","xControl:3D_Ribbon_Plot_Merge_VI.vi", \
          "xControl:3D_Scatter_Plot_Merge_VI.vi","xControl:3D_Stem_Plot_Merge_VI.vi","xControl:3D_Surface_Plot_Merge_VI.vi", \
          "xControl:3D_Waterfall_Plot_Merge_VI.vi",)]
    if len(filterClasses) > 0:
        matchingClasses = filterClasses
        newStateTypeDesc, newStateFlatTypeID = VCTP_add_3DPlotDatatypeTD_for_DTHP(RSRC, fo, po, filterClasses[0], VCTP)
    filterClasses = [fpClassEx for fpClassEx in matchingClasses if fpClassEx in ("xControl:XY Plot Matrix.vi",)]
    if len(filterClasses) > 0:
        matchingClasses = filterClasses
        newStateTypeDesc, newStateFlatTypeID = VCTP_add_XYPlotMatrixTD_for_DTHP(RSRC, fo, po, filterClasses[0], VCTP)
    if newStateFlatTypeID is not None:
        # Create Top Types
        VCTP_FlatTypeDescList = VCTP.findall("TypeDesc")
        if newStateFlatTypeID is not None:
            nIndexShift, _ = VCTP_add_TopTypeDesc(RSRC, fo, po, newStateFlatTypeID, nTopTDIndex=nIndexShift)
            nIndexShift += 1
    # Some controls have histTD type at end; if it should be used, we expect the proper TypeDesc to be already in list
    # So try to re-use existing TDs when creating it
    hasHistTD = any(fpClassEx in ("stdGraph:Intensity Chart","stdGraph:Waveform Chart",) for fpClassEx in matchingClasses)
    if hasHistTD:
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","NumInt32")
            tmpTypeDesc.set("Prop1",str(0))
            tmpTypeDesc.set("Format","inline")
            newInt32TypeDesc, newInt32FlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","NumFloat64")
            tmpTypeDesc.set("Prop1",str(0))
            tmpTypeDesc.set("Format","inline")
            newFltTypeDesc, newFltFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","Array")
            tmpTypeDesc.set("Format","inline")
            if True:
                tmpTDSub = ET.SubElement(tmpTypeDesc, "Dimension")
                tmpTDSub.set("Flags","0x{:02X}".format(0x80))
                tmpTDSub.set("FixedSize","0x{:04X}".format(0x000080))
            if True:
                tmpTDSub = ET.SubElement(tmpTypeDesc, "Dimension")
                tmpTDSub.set("Flags","0x{:02X}".format(0xFF))
                tmpTDSub.set("FixedSize","0x{:04X}".format(0xFFFFFF))
            if True:
                tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
                tmpTDSub.set("TypeID",str(newFltFlatTypeID))
            newArrFlTypeDesc, newArrFlFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","Cluster")
            tmpTypeDesc.set("Format","inline")
            for i in range(3):
                tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
                tmpTDSub.set("TypeID",str(newInt32FlatTypeID))
            if True:
                tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
                tmpTDSub.set("TypeID",str(newArrFlFlatTypeID))
            newClustIIIATypeDesc, newClustIIIAFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","NumInt16")
            tmpTypeDesc.set("Prop1",str(0))
            tmpTypeDesc.set("Format","inline")
            newInt16TypeDesc, newInt16FlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","NumUInt32")
            tmpTypeDesc.set("Prop1",str(0))
            tmpTypeDesc.set("Format","inline")
            newUInt32TypeDesc, newUInt32FlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        if True:
            tmpTypeDesc = ET.Element("TypeDesc")
            tmpTypeDesc.set("Type","Cluster")
            tmpTypeDesc.set("Format","inline")
            if True:
                tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
                tmpTDSub.set("TypeID",str(newClustIIIAFlatTypeID))
            if True:
                tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
                tmpTDSub.set("TypeID",str(newInt32FlatTypeID))
            for i in range(2):
                tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
                tmpTDSub.set("TypeID",str(newInt16FlatTypeID))
            if True:
                tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
                tmpTDSub.set("TypeID",str(newUInt32FlatTypeID))
            if True:
                tmpTDSub = ET.SubElement(tmpTypeDesc, "TypeDesc")
                tmpTDSub.set("TypeID",str(newClustIIIAFlatTypeID))
            newHistTypeDesc, newHistFlatTypeID = VCTP_find_or_add_TypeDesc_copy(RSRC, fo, po, tmpTypeDesc, VCTP=VCTP)
        # Create Top Type
        VCTP_FlatTypeDescList = VCTP.findall("TypeDesc")
        if newHistFlatTypeID is not None:
            nIndexShift, _ = VCTP_add_TopTypeDesc(RSRC, fo, po, newHistFlatTypeID, nTopTDIndex=nIndexShift)
            nIndexShift += 1
    return nIndexShift - indexShift

def DCO_recognize_fpClassEx_list_from_single_TypeDesc(RSRC, fo, po, VCTP_FlatTypeDescList, dcoTypeDesc):
    """ Recognizes DCO class using only TypeID of DCO as input

    This should be used only if more info on the DCO is not available.
    Returns a list of matching DCO extended class names, meaning class names followed by
    specific control names after a colon (fpClass:ControlName).
    """
    # Repare a list for classes
    matchingClasses = []
    # Recognize the DCO FP Class
    if dcoTypeDesc.get("Type") == "TypeDef":
        # Controls from Array/Matrix/Cluster category: Real Matrix, Complex Matrix
        match = True
        controlNames = []
        dcoInnerTypeDesc = dcoTypeDesc.find("./TypeDesc[@Type]")
        if dcoInnerTypeDesc is not None and dcoInnerTypeDesc.get("Type") == "Array":
            nDimensions = len(dcoInnerTypeDesc.findall("./Dimension"))
        else:
            nDimensions = 0
        if nDimensions < 1:
            match = False
        dcoSubTypeDescMap = dcoInnerTypeDesc.find("./TypeDesc[@TypeID]")
        if dcoSubTypeDescMap is not None:
            dcoSubTypeDesc, _, dcoFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, dcoSubTypeDescMap, po)
        else:
            dcoSubTypeDesc, dcoFlatSubTypeID = None, None
        # The type inside come from a DCO, so its type needs to be supported as well
        if dcoSubTypeDesc is None or len(DCO_recognize_fpClassEx_list_from_single_TypeDesc(RSRC, fo, po, VCTP_FlatTypeDescList, dcoSubTypeDesc)) < 1:
            match = False
        if match and dcoSubTypeDesc.get("Type") in ("NumFloat64",):
            controlNames.append("RealMatrix.ctl")
        if match and dcoSubTypeDesc.get("Type") in ("NumComplex128",):
            controlNames.append("ComplexMatrix.ctl")
        if match:
            for controlName in controlNames:
                matchingClasses.append("typeDef:"+controlName)
            matchingClasses.append("typeDef")
    if dcoTypeDesc.get("Type") == "TypeDef":
        # Controls from TestStand UI category: Invocation Info, Test Data
        match = True
        controlNames = []
        # Verify DCO Inner TypeDesc
        dcoInnerTypeDesc = dcoTypeDesc.find("./TypeDesc[@Type]")
        if dcoInnerTypeDesc is not None and dcoInnerTypeDesc.get("Type") == "Cluster":
            dcoInnerTypeDescMap = dcoInnerTypeDesc.findall("./TypeDesc[@TypeID]")
        else:
            dcoInnerTypeDescMap = []
        # Verify fields within Cluster
        if len(controlNames) < 1: # Try Invocation Info cluster
            checkPassed = 0
            for i, dcoInnTypeMap in enumerate(dcoInnerTypeDescMap):
                dcoInnTypeDesc, _, dcoFlatInnTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, dcoInnTypeMap, po)
                if dcoInnTypeDesc is None:
                    break
                if i in (0,1,): # UUT num, loop num
                    if dcoInnTypeDesc.get("Type") == "NumInt32":
                        checkPassed += 1
                elif i in (2,3,): # UUT Info, Test Name
                    if dcoInnTypeDesc.get("Type") == "String":
                        checkPassed += 1
                elif i in (4,): # Sequence Path
                    if dcoInnTypeDesc.get("Type") == "Path":
                        checkPassed += 1
            if checkPassed == 5:
                controlNames.append("LabVIEW Test - Invocation Info.ctl")
        if len(controlNames) < 1: # Try Test Data cluster
            checkPassed = 0
            for i, dcoInnTypeMap in enumerate(dcoInnerTypeDescMap):
                dcoInnTypeDesc, _, dcoFlatInnTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, dcoInnTypeMap, po)
                if dcoInnTypeDesc is None:
                    break
                if i in (0,): # PASS/FAIL Flag
                    if dcoInnTypeDesc.get("Type") == "Boolean":
                        checkPassed += 1
                if i in (1,): # Numeric Measurement
                    if dcoInnTypeDesc.get("Type") == "NumFloat64":
                        checkPassed += 1
                elif i in (2,3,): # String Measurement, Report Text
                    if dcoInnTypeDesc.get("Type") == "String":
                        checkPassed += 1
            if checkPassed == 4:
                controlNames.append("LabVIEW Test - Test Data.ctl")
        if match:
            for controlName in controlNames:
                matchingClasses.append("typeDef:"+controlName)
            matchingClasses.append("typeDef")
    if dcoTypeDesc.get("Type") == "UnitUInt32":
        # Controls from Boolean category: Radio Buttons
        match = True
        controlNames = []
        controlNames.append("Radio Buttons")
        if match:
            for controlName in controlNames:
                matchingClasses.append("radioClust:"+controlName)
            matchingClasses.append("radioClust")
    if dcoTypeDesc.get("Type") == "UnitUInt32":
        # Controls from Containers category: TabControl
        match = True
        controlNames = []
        controlNames.append("Tab Control")
        if match:
            for controlName in controlNames:
                matchingClasses.append("tabControl:"+controlName)
            matchingClasses.append("tabControl")
    if dcoTypeDesc.get("Type") in ("Cluster","Array","NumFloat64",):
        # Controls from Graph category: Digital Waveform, Waveform Chart, Waveform Graph, XY Graph, Ex XY Graph, Intensity Chart
        match = True
        controlNames = []
        # Verify DCO TypeID
        if dcoTypeDesc.get("Type") == "Cluster":
            # For control: Digital Waveform
            dcoSubTypeDescMap = dcoTypeDesc.findall("./TypeDesc[@TypeID]")
            if len(dcoSubTypeDescMap) != 4:
                match = False
            # Verify fields within Cluster
            for i, dcoSubTypeMap in enumerate(dcoSubTypeDescMap):
                dcoSubTypeDesc, _, dcoFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, dcoSubTypeMap, po)
                if dcoSubTypeDesc is None:
                    match = False
                    break
                if i in (0,1,):
                    if dcoSubTypeDesc.get("Type") != "NumFloat64":
                        match = False
                elif i in (2,):
                    if dcoSubTypeDesc.get("Type") != "Array":
                        match = False
                elif i in (3,):
                    if dcoSubTypeDesc.get("Type") != "NumInt32":
                        match = False
                if not match:
                    break
            controlNames.append("Digital Waveform Graph")
        elif dcoTypeDesc.get("Type") == "Array":
            nDimensions = len(dcoTypeDesc.findall("./Dimension"))
            dcoSubTypeMap = dcoTypeDesc.find("./TypeDesc[@TypeID]")
            if dcoSubTypeMap is not None:
                dcoSubVarTypeDesc, _, dcoFlatClusterTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, dcoSubTypeMap, po)
            else:
                dcoSubVarTypeDesc, dcoFlatClusterTypeID = None, None
            if dcoSubVarTypeDesc is not None and dcoSubVarTypeDesc.get("Type") == "NumFloat64":
                # For controls: Waveform Graph, Intensity Chart
                if   nDimensions == 1:
                    controlNames.append("Waveform Graph")
                elif nDimensions == 2:
                    controlNames.append("Intensity Chart")
                else:
                    match = False
            elif dcoSubVarTypeDesc is not None and dcoSubVarTypeDesc.get("Type") == "Cluster":
                # For controls: XY Graph (dcoSubClustTypeDesc is Cluster), Express XY Graph (dcoSubClustTypeDesc is Array)
                dcoSubClustTypeMap = dcoSubVarTypeDesc.findall("./TypeDesc[@TypeID]")
                if len(dcoSubClustTypeMap) != 2:
                    match = False
                firstType = None
                for i, dcoSubClustTypeMap in enumerate(dcoSubClustTypeMap):
                    dcoSubClustTypeDesc, _, dcoFlatSubClustTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, dcoSubTypeMap, po)
                    if dcoSubClustTypeDesc.get("Type") == "Array":
                        controlNames.append("XY Graph")
                    elif dcoSubClustTypeDesc.get("Type") == "Cluster":
                        controlNames.append("Express XY Graph")
                    else:
                        match = False
                    # All the types inside are the same
                    if firstType is None:
                        firstType = dcoSubClustTypeDesc.get("Type")
                    if dcoSubClustTypeDesc.get("Type") != firstType:
                        match = False
                    if not match:
                        break
        elif dcoTypeDesc.get("Type") == "NumFloat64":
            # For control: Waveform Chart
            controlNames.append("Waveform Chart")
        if match:
            for controlName in controlNames:
                matchingClasses.append("stdGraph:"+controlName)
            matchingClasses.append("stdGraph")
    if dcoTypeDesc.get("Type") == "Cluster":
        # Controls from Array/Matrix/Cluster category: Cluster
        # Controls from Graph Datatypes category: Point, Rect, Text Alignment, User Font
        match = True
        controlNames = []
        dcoSubTypeDescMap = dcoTypeDesc.findall("./TypeDesc")
        for TDTopMap in dcoSubTypeDescMap:
            dcoSubTypeDesc, _, dcoFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, TDTopMap, po)
            if dcoSubTypeDesc is None: continue
            # The types inside come from a DCO, so its type needs to be supported as well
            if len(DCO_recognize_fpClassEx_list_from_single_TypeDesc(RSRC, fo, po, VCTP_FlatTypeDescList, dcoSubTypeDesc)) < 1:
                match = False
        if len(controlNames) < 1:
            innerMatch = True
            if len(dcoSubTypeDescMap) != 8:
                innerMatch = False
            for i, TDTopMap in enumerate(dcoSubTypeDescMap):
                dcoSubTypeDesc, _, dcoFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, TDTopMap, po)
                if dcoSubTypeDesc is None:
                    innerMatch = False
                elif i in (0,):
                    if dcoSubTypeDesc.get("Type") != "String":
                        innerMatch = False
                elif i in (1,):
                    if dcoSubTypeDesc.get("Type") != "NumInt16":
                        innerMatch = False
                elif i >= 2:
                    if dcoSubTypeDesc.get("Type") != "Boolean":
                        innerMatch = False
                if not innerMatch:
                    break
            if innerMatch:
                controlNames.append("User Font.ctl")
        if len(controlNames) < 1:
            innerMatch = True
            if len(dcoSubTypeDescMap) != 2:
                innerMatch = False
            for i, TDTopMap in enumerate(dcoSubTypeDescMap):
                dcoSubTypeDesc, _, dcoFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, TDTopMap, po)
                if dcoSubTypeDesc is None:
                    innerMatch = False
                elif i in (0,):
                    if dcoSubTypeDesc.get("Type") != "UnitUInt16":
                        innerMatch = False
                    dcoSubTypeEnumLabels = dcoSubTypeDesc.findall("./EnumLabel")
                    if [elem.text for elem in dcoSubTypeEnumLabels] != ["left","center","right"]:
                        innerMatch = False
                elif i in (1,):
                    if dcoSubTypeDesc.get("Type") != "UnitUInt16":
                        innerMatch = False
                    dcoSubTypeEnumLabels = dcoSubTypeDesc.findall("./EnumLabel")
                    if [elem.text for elem in dcoSubTypeEnumLabels] != ["top","center","bottom"]:
                        innerMatch = False
                if not innerMatch:
                    break
            if innerMatch:
                controlNames.append("Text Alignment.ctl")
        if len(controlNames) < 1:
            innerMatch = True
            if len(dcoSubTypeDescMap) != 4:
                innerMatch = False
            for i, TDTopMap in enumerate(dcoSubTypeDescMap):
                dcoSubTypeDesc, _, dcoFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, TDTopMap, po)
                if dcoSubTypeDesc is None:
                    innerMatch = False
                elif i in (0,):
                    if dcoSubTypeDesc.get("Type") != "NumInt16":
                        innerMatch = False
                    if dcoSubTypeDesc.get("Label") != "left":
                        innerMatch = False
                elif i in (1,):
                    if dcoSubTypeDesc.get("Type") != "NumInt16":
                        innerMatch = False
                    if dcoSubTypeDesc.get("Label") != "top":
                        innerMatch = False
                elif i in (2,):
                    if dcoSubTypeDesc.get("Type") != "NumInt16":
                        innerMatch = False
                    if dcoSubTypeDesc.get("Label") != "right":
                        innerMatch = False
                elif i in (3,):
                    if dcoSubTypeDesc.get("Type") != "NumInt16":
                        innerMatch = False
                    if dcoSubTypeDesc.get("Label") != "bottom":
                        innerMatch = False
                if not innerMatch:
                    break
            if innerMatch:
                controlNames.append("Rect.ctl")
        if len(controlNames) < 1:
            innerMatch = True
            if len(dcoSubTypeDescMap) != 2:
                innerMatch = False
            for i, TDTopMap in enumerate(dcoSubTypeDescMap):
                dcoSubTypeDesc, _, dcoFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, TDTopMap, po)
                if dcoSubTypeDesc is None:
                    innerMatch = False
                elif i in (0,):
                    if dcoSubTypeDesc.get("Type") != "NumInt16":
                        innerMatch = False
                    if dcoSubTypeDesc.get("Label") != "x":
                        innerMatch = False
                elif i in (1,):
                    if dcoSubTypeDesc.get("Type") != "NumInt16":
                        innerMatch = False
                    if dcoSubTypeDesc.get("Label") != "y":
                        innerMatch = False
                if not innerMatch:
                    break
            if innerMatch:
                controlNames.append("Point.ctl")
        # If speciifc cluster type was not recognized, set the control type to generic cluster
        if len(controlNames) < 1:
            controlNames.append("Cluster")
        if match:
            for controlName in controlNames:
                matchingClasses.append("stdClust:"+controlName)
            matchingClasses.append("stdClust")
    if dcoTypeDesc.get("Type") == "MeasureData" and dcoTypeDesc.get("Flavor") in ("DigitalWaveform","Float64Waveform",):
        # Controls from I/O category: Digital Waveform, Waveform
        match = True
        controlNames = []
        if   dcoTypeDesc.get("Flavor") == "DigitalWaveform":
            controlNames.append("Digital Waveform.ctl")
        elif dcoTypeDesc.get("Flavor") == "Float64Waveform":
            controlNames.append("Waveform")
        if match:
            for controlName in controlNames:
                matchingClasses.append("stdMeasureData:"+controlName)
            matchingClasses.append("stdMeasureData")
    if dcoTypeDesc.get("Type") == "Array":
        # Controls from List Table And Tree category: Table Control, Express Table
        match = True
        controlNames = []
        if True:
            nDimensions = len(dcoTypeDesc.findall("./Dimension"))
            dcoSubTypeMap = dcoTypeDesc.find("./TypeDesc[@TypeID]")
            if dcoSubTypeMap is not None:
                dcoSubVarTypeDesc, _, dcoFlatClusterTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, dcoSubTypeMap, po)
            else:
                dcoSubVarTypeDesc, dcoFlatClusterTypeID = None, None
            if dcoSubVarTypeDesc is None or dcoSubVarTypeDesc.get("Type") not in ("String",):
                match = False
            if nDimensions != 2:
                match = False
            controlNames.append("Table Control")
            controlNames.append("mergeTable.vi")
        if match:
            for controlName in controlNames:
                matchingClasses.append("tableControl:"+controlName)
            matchingClasses.append("tableControl")

    # Controls which use three or less FP TypeDefs are left below
    if dcoTypeDesc.get("Type") == "Array":
        # Controls from 3D Graph category: Bar, Comet, Contour, LineGraph, Mesh, ParametricGraph, Pie, Quiver, Ribbon,
        #   Scatter, Stem, Surface, SurfaceGraph, Waterfall
        # Controls from Graph category: Error Bar Plot, Feather Plot, XY Plot Matrix
        match = True
        controlNames = []
        # Get the array item type
        dcoSubTDMap = dcoTypeDesc.find("./TypeDesc[@TypeID]")
        dcoSubTypeDesc, _, dcoFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, dcoSubTDMap, po)
        # Check array dimensions
        nDimensions = len(dcoTypeDesc.findall("./Dimension"))
        if nDimensions != 1:
            match = False
        # Ref type is UDClassInst
        if dcoSubTypeDesc.get("Type") != "Refnum" or dcoSubTypeDesc.get("RefType") not in ("UDClassInst",):
            match = False
        dcoSubTDItemList = dcoSubTypeDesc.findall("./Item") # we expect this list to be one item long
        if   "Base Datatype.lvclass" in [ itm.get("Text") for itm in dcoSubTDItemList ]:
            controlNames.append("3D Line Graph.vi")
            controlNames.append("3D Parametric Graph.vi")
            controlNames.append("3D Surface Graph.vi")
        elif "2D Plot Datatype.lvclass" in [ itm.get("Text") for itm in dcoSubTDItemList ]:
            controlNames.append("2D Error Bar Plot.vi")
            controlNames.append("2D Feather Plot.vi")
            controlNames.append("2D Compass")
        elif "3D Plot Datatype.lvclass" in [ itm.get("Text") for itm in dcoSubTDItemList ]:
            controlNames.append("3D_Bar_Plot_Merge_VI.vi")
            controlNames.append("3D_Comet_Plot_Merge_VI.vi")
            controlNames.append("3D_Contour_Plot_Merge_VI.vi")
            controlNames.append("3D_Mesh_Plot_Merge_VI.vi")
            controlNames.append("3D_Pie_Plot_Merge_VI.vi")
            controlNames.append("3D_Quiver_Plot_Merge_VI.vi")
            controlNames.append("3D_Ribbon_Plot_Merge_VI.vi")
            controlNames.append("3D_Scatter_Plot_Merge_VI.vi")
            controlNames.append("3D_Stem_Plot_Merge_VI.vi")
            controlNames.append("3D_Surface_Plot_Merge_VI.vi")
            controlNames.append("3D_Waterfall_Plot_Merge_VI.vi")
        elif "XY Plot Matrix Datatype.lvclass" in [ itm.get("Text") for itm in dcoSubTDItemList ]:
            controlNames.append("XY Plot Matrix.vi")
        else:
            match = False
        if match:
            for controlName in controlNames:
                matchingClasses.append("xControl:"+controlName)
            matchingClasses.append("xControl")
    if dcoTypeDesc.get("Type").startswith("Num"):
        # "stdKnob" Controls from Numeric category: Dial, Gauge, Knob, Meter
        # "stdSlide" Controls from Numeric category: Tank, Thermometer, Slide, Bar
        #   (with all variants, like: Fill Slide, Pointer Slide, Progress Bar, Graduated Bar)
        # There is no way to distinguish these two groups
        match = True
        controlNames = []
        if True:
            controlNames.append("Knob")
            controlNames.append("Dial")
            controlNames.append("Gauge")
            controlNames.append("Meter")
        if match:
            for controlName in controlNames:
                matchingClasses.append("stdKnob:"+controlName)
            matchingClasses.append("stdKnob")
        controlNames = []
        if True:
            controlNames.append("Slide")
            controlNames.append("Bar")
            controlNames.append("Tank")
            controlNames.append("Thermometer")
        if match:
            for controlName in controlNames:
                matchingClasses.append("stdSlide:"+controlName)
            matchingClasses.append("stdSlide")
    if dcoTypeDesc.get("Type") == "TypeDef":
        # Controls from TestStand UI category: Input Buffer, Sequence Context
        match = True
        controlNames = []
        dcoInnerLabel = dcoTypeDesc.find("./Label[@Text]")
        dcoInnerTypeDesc = dcoTypeDesc.find("./TypeDesc[@Type]")
        if dcoInnerTypeDesc is None or dcoInnerLabel is None:
            match = False
        elif dcoInnerTypeDesc.get("Type") == "String" and dcoInnerLabel.get("Text") == "LabVIEW Test - Input Buffer.ctl":
            controlNames.append("LabVIEW Test - Input Buffer.ctl")
        elif dcoInnerTypeDesc.get("Type") == "Refnum" and dcoInnerTypeDesc.get("RefType") == "AutoRef" and \
              dcoInnerLabel.get("Text") == "LabVIEW Test - Sequence Context.ctl":
            controlNames.append("LabVIEW Test - Sequence Context.ctl")
        else:
            match = False
        if match:
            for controlName in controlNames:
                matchingClasses.append("typeDef:"+controlName)
            matchingClasses.append("typeDef")
    if dcoTypeDesc.get("Type") == "Refnum" and dcoTypeDesc.get("RefType") in ("IVIRef","VisaRef","UsrDefndTag",):
        # Controls from I/O category: DAQmx Channel, DAQmx Task Name, FieldPoint IO, IVI Logical Name, Motion Resource,
        #   Shared Variable Control, System Configuration, VISA Resource
        match = True
        controlNames = []
        dcoSubTDMap = dcoTypeDesc.find("./TypeDesc[@TypeID]")
        dcoSubTypeDesc, _, dcoFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, dcoSubTDMap, po)
        if   dcoTypeDesc.get("RefType") == "UsrDefndTag" and dcoTypeDesc.get("TypeName") == "DSC":
            if dcoSubTypeDesc.get("TagType") == "SharedVarCtl":
                controlNames.append("Shared Variable Control")
            else:
                match = False
        elif dcoTypeDesc.get("RefType") == "UsrDefndTag" and dcoTypeDesc.get("TypeName") == "NIDAQ":
            if dcoSubTypeDesc.get("TagType") == "DAQmxTaskName":
                controlNames.append("DAQmx Task Name")
            elif dcoSubTypeDesc.get("TagType") == "DAQmxChannel":
                controlNames.append("DAQmx Channel")
            else:
                match = False
        elif dcoTypeDesc.get("RefType") == "UsrDefndTag" and dcoTypeDesc.get("TypeName") == "FieldPoint":
            if dcoSubTypeDesc.get("TagType") == "FldPointIOPoint":
                controlNames.append("FieldPoint IO Point")
            else:
                match = False
        elif dcoTypeDesc.get("RefType") == "UsrDefndTag" and dcoTypeDesc.get("TypeName") == "Motion":
            if dcoSubTypeDesc.get("TagType") == "MotionResource":
                controlNames.append("Motion Resource")
            else:
                match = False
        elif dcoTypeDesc.get("RefType") == "UsrDefndTag" and dcoTypeDesc.get("TypeName") == "nisyscfg":
            if dcoSubTypeDesc.get("TagType") not in ("UserDefined",):
                match = False
            dcoSubIdent = dcoSubTypeDesc.find("./Ident")
            if dcoSubIdent is not None and dcoSubIdent.text in ("nisyscfg",):
                controlNames.append("nisyscfg.ctl")
            else:
                match = False
        elif dcoTypeDesc.get("RefType") == "VisaRef":
            if dcoSubTypeDesc.get("TagType") == "VISArsrcName":
                controlNames.append("VISA resource name")
            else:
                match = False
        elif dcoTypeDesc.get("RefType") == "IVIRef":
            if dcoSubTypeDesc.get("TagType") == "IVILogicalName":
                controlNames.append("IVI Logical Name")
            else:
                match = False
        else:
            match = False
        tagDataType = dcoSubTypeDesc.find("./LVVariant/DataType[@Type='Void']")
        if tagDataType is None:
            match = False
        if match:
            for controlName in controlNames:
                matchingClasses.append("stdRefNum:"+controlName)
            matchingClasses.append("stdRefNum")
    if dcoTypeDesc.get("Type") == "MeasureData" and dcoTypeDesc.get("Flavor") == "TimeStamp":
        # Controls from Numeric category: Timestamp Control, Timestamp Indicator
        match = True
        controlNames = []
        if True:
            controlNames.append("Time Stamp")
        if match:
            for controlName in controlNames:
                matchingClasses.append("absTime:"+controlName)
            matchingClasses.append("absTime")
    if dcoTypeDesc.get("Type") == "String":
        # Controls from String and Path category: Combo Box
        match = True
        controlNames = []
        if True:
            controlNames.append("Combo Box")
        if match:
            for controlName in controlNames:
                matchingClasses.append("stdComboBox:"+controlName)
            matchingClasses.append("stdComboBox")
    if dcoTypeDesc.get("Type") == "Array":
        # Controls from Array/Matrix/Cluster category: Array
        match = True
        controlNames = []
        if True:
            controlNames.append("Array")
        if match:
            for controlName in controlNames:
                matchingClasses.append("indArr:"+controlName)
            matchingClasses.append("indArr")
    if dcoTypeDesc.get("Type") == "Path":
        # Controls from String And Path category: File Path Control, File Path Indicator
        match = True
        controlNames = []
        if True:
            controlNames.append("File Path")
        if match:
            for controlName in controlNames:
                matchingClasses.append("stdPath:"+controlName)
            matchingClasses.append("stdPath")

    # Controls which use two or less FP TypeDefs are left below
    if dcoTypeDesc.get("Type") == "Boolean":
        # Controls from Boolean category: Buttons, Switches and LEDs
        match = True
        controlNames = []
        if True:
            controlNames.append("Push Button")
            controlNames.append("Rocker")
            controlNames.append("Toggle Switch")
            controlNames.append("Slide Switch")
            controlNames.append("OK Button")
            controlNames.append("Cancel Button")
            controlNames.append("Stop Button")
            controlNames.append("LED")
        if match:
            for controlName in controlNames:
                matchingClasses.append("stdBool:"+controlName)
            matchingClasses.append("stdBool")
    if dcoTypeDesc.get("Type").startswith("Num"):
        # Controls from Numeric category: Numeric Control, Numeric Indicator
        # Also matches controls from Numeric category: Framed Color Box (fpClass="stdColorNum")
        # Also matches controls from Numeric category: Horizontal Scrollbar, Vertical Scrollbar (fpClass="scrollbar")
        # Also matches controls from List Table And Tree category: Listbox, Multicolumn Listbox (fpClass="listbox")
        match = True
        controlNames = []
        controlNames.append("Numeric")
        if match:
            for controlName in controlNames:
                matchingClasses.append("stdNum:"+controlName)
            matchingClasses.append("stdNum")
        controlNames = []
        controlNames.append("Framed Color Box")
        if match:
            for controlName in controlNames:
                matchingClasses.append("stdColorNum:"+controlName)
            matchingClasses.append("stdColorNum")
        controlNames = []
        controlNames.append("Scrollbar")
        if match:
            for controlName in controlNames:
                matchingClasses.append("scrollbar:"+controlName)
            matchingClasses.append("scrollbar")
        controlNames = []
        controlNames.append("Listbox")
        controlNames.append("Multicolumn Listbox")
        if match:
            for controlName in controlNames:
                matchingClasses.append("listbox:"+controlName)
            matchingClasses.append("listbox")
    if dcoTypeDesc.get("Type") == "String":
        # Controls from String and Path category: String Control, String Indicator
        match = True
        controlNames = []
        if True:
            controlNames.append("String")
        if match:
            for controlName in controlNames:
                matchingClasses.append("stdString:"+controlName)
            matchingClasses.append("stdString")
    if dcoTypeDesc.get("Type") == "Picture":
        # Controls from Graph category: 2D Picture, Distribution Plot, Min Max Plot, Polar Plot, Radar Plot, Smith Plot
        match = True
        controlNames = []
        if True:
            controlNames.append("2D Picture")
            controlNames.append("Distribution Plot")
            controlNames.append("Min-Max Plot")
            controlNames.append("Polar Plot")
            controlNames.append("Radar Plot")
            controlNames.append("Smith Plot")
        if match:
            for controlName in controlNames:
                matchingClasses.append("stdPict:"+controlName)
            matchingClasses.append("stdPict")
    if dcoTypeDesc.get("Type") == "MeasureData":
        # Controls from I/O category: Digital Data
        match = True
        controlNames = []
        if dcoTypeDesc.get("Flavor") == "Digitaldata":
            controlNames.append("Digital Data")
        else:
            match = False
        if match:
            for controlName in controlNames:
                matchingClasses.append("digitalTable:"+controlName)
            matchingClasses.append("digitalTable")
    if dcoTypeDesc.get("Type") == "UnitUInt16":
        # Controls from Graph DataTypes category: Font Enum
        match = True
        controlNames = []
        if True:
            controlNames.append("Font Enum.ctl")
        if match:
            for controlName in controlNames:
                matchingClasses.append("stdRing:"+controlName)
            matchingClasses.append("stdRing")
    if dcoTypeDesc.get("Type") == "Tag":
        # Controls from I/O category: DAQ Channel, DAQmx Device, DAQmx Terminal, DAQmx Physical Channel, DAQmx Scale, DAQmx Switch
        # These use two TDs, both pointing at the same flat index of Tag TD.
        match = True
        controlNames = []
        if   dcoTypeDesc.get("TagType") == "DAQChannelOld":
            controlNames.append("Traditional DAQ Channel")
        elif dcoTypeDesc.get("TagType") == "DAQmxScaleName":
            controlNames.append("DAQmx Scale Name")
        elif dcoTypeDesc.get("TagType") == "DAQmxDeviceName":
            controlNames.append("DAQmx Device Name")
        elif dcoTypeDesc.get("TagType") == "DAQmxTerminal":
            controlNames.append("DAQmx Terminal")
        elif dcoTypeDesc.get("TagType") == "DAQmxPhysChannel":
            controlNames.append("DAQmx Physical Channel")
        elif dcoTypeDesc.get("TagType") == "DAQmxSwitch":
            controlNames.append("DAQmx Switch")
        else:
            match = False
        tagDataType = dcoTypeDesc.find("./LVVariant/DataType[@Type='Void']")
        if tagDataType is None:
            match = False
        if match:
            for controlName in controlNames:
                matchingClasses.append("stdTag:"+controlName)
            matchingClasses.append("stdTag")
    if dcoTypeDesc.get("Type") == "Refnum" and dcoTypeDesc.get("RefType") == "DotNet":
        # Controls from Containers category: dotNET Container
        # Controls from dotNet and ActiveX category: Web Browser, Media Player
        match = True
        controlNames = []
        dNetTypeName = dcoTypeDesc.get("dNetTypeName")
        if True:
            if dNetTypeName is not None and "System.Windows.Forms.PictureBox" in dNetTypeName:
                controlNames.append("plat-PictureBox.ctl")
            elif dNetTypeName is not None and "System.Windows.Forms.RichTextBox" in dNetTypeName:
                controlNames.append("plat-RichTextBox.ctl")
            else:
                controlNames.append(".NET Container")
        if match:
            for controlName in controlNames:
                matchingClasses.append("stdCont:"+controlName)
            matchingClasses.append("stdCont")
    if dcoTypeDesc.get("Type") == "Refnum" and dcoTypeDesc.get("RefType") == "AutoRef":
        # Controls from Containers category: ActiveX Container
        # Controls from TestStand UI category: Application Manager, Button Control, CheckBox Control,
        #   ComboBox Control, ExecutionView Manager, ExpressionEdit Control, InsertionPalette Control,
        #   Label Control, ListBar Control, ListBox Control, ReportView Control, SequenceFileView Manager,
        #   SequenceView Control, StatusBar Control, VariablesView Control
        match = True
        controlNames = []
        dcoTypeItemList = dcoTypeDesc.findall("./Item[@ClassID]")
        if True:
            if   "d30c1661-cdaf-11d0-8a3e00c04fc9e26e" in [ itm.get("ClassID").lower() for itm in dcoTypeItemList ]: # IWebBrowser2
                controlNames.append("plat-Microsoft Web Browser.ctl")
            elif "eab22ac0-30c1-11cf-a7eb0000c05bae0b" in [ itm.get("ClassID").lower() for itm in dcoTypeItemList ]: # Microsoft Internet Controls
                controlNames.append("plat-Microsoft Web Browser.ctl")
            elif "6bf52a50-394a-11d3-b15300c04f79faa6" in [ itm.get("ClassID").lower() for itm in dcoTypeItemList ]: # WMPLib
                controlNames.append("plat-Windows Media Player.ctl")
            elif "03b81820-510e-42c6-93b8cfa253794662" in [ itm.get("ClassID").lower() for itm in dcoTypeItemList ]: # TestStand User Interface
                if "d0743b7d-50bf-409d-87df49983721dfdc" in [ itm.get("ClassID").lower() for itm in dcoTypeItemList ]:
                    controlNames.append("TestStand UI Application Manager.ctl")
                elif "a6fa998e-98ef-11d2-93b700a02411ebe6" in [ itm.get("ClassID").lower() for itm in dcoTypeItemList ]:
                    controlNames.append("TestStand UI Button Control.ctl")
                elif "661bd29b-11cc-4666-b4b8c9de53e5f1ab" in [ itm.get("ClassID").lower() for itm in dcoTypeItemList ]:
                    controlNames.append("TestStand UI CheckBox Control.ctl")
                elif "be676080-61ac-11d5-8efa0050dac50018" in [ itm.get("ClassID").lower() for itm in dcoTypeItemList ]:
                    controlNames.append("TestStand UI ComboBox Control.ctl")
                elif "0b2d723f-0a05-40fe-a0fc362ef92a1dcb" in [ itm.get("ClassID").lower() for itm in dcoTypeItemList ]:
                    controlNames.append("TestStand UI ExecutionView Manager.ctl")
                elif "fdd24392-1132-424d-bf4b77f0f0801f7a" in [ itm.get("ClassID").lower() for itm in dcoTypeItemList ]:
                    controlNames.append("TestStand UI ExpressionEdit Control.ctl")
                elif "7575abc2-9520-4ef4-9df82c33b6da18bc" in [ itm.get("ClassID").lower() for itm in dcoTypeItemList ]:
                    controlNames.append("TestStand UI InsertionPalette Control.ctl")
                elif "c50fd121-99bf-11d2-93b700a02411ebe6" in [ itm.get("ClassID").lower() for itm in dcoTypeItemList ]:
                    controlNames.append("TestStand UI Label Control.ctl")
                elif "5ca55ac1-a7f1-470c-90943dbeefe0acf9" in [ itm.get("ClassID").lower() for itm in dcoTypeItemList ]:
                    controlNames.append("TestStand UI ListBar Control.ctl")
                elif "a6fa998b-98ef-11d2-93b700a02411ebe6" in [ itm.get("ClassID").lower() for itm in dcoTypeItemList ]:
                    controlNames.append("TestStand UI ListBox Control.ctl")
                elif "f54f4eba-497c-11d5-8eeb0050dac50018" in [ itm.get("ClassID").lower() for itm in dcoTypeItemList ]:
                    controlNames.append("TestStand UI ReportView Control.ctl")
                elif "817d7c9a-8f4b-4bb7-aea6e118ceb0f823" in [ itm.get("ClassID").lower() for itm in dcoTypeItemList ]:
                    controlNames.append("TestStand UI SequenceFileView Manager.ctl")
                elif "34b7e073-5533-4a8a-a6511230c0e6500a" in [ itm.get("ClassID").lower() for itm in dcoTypeItemList ]:
                    controlNames.append("TestStand UI SequenceView Control.ctl")
                elif "9ce1ada4-09a8-4158-b1e2f3489316e12b" in [ itm.get("ClassID").lower() for itm in dcoTypeItemList ]:
                    controlNames.append("TestStand UI StatusBar Control.ctl")
                elif "aabdf204-cd20-4fdf-822e5db98192a4b9" in [ itm.get("ClassID").lower() for itm in dcoTypeItemList ]:
                    controlNames.append("TestStand UI VariablesView Control.ctl")
                else:
                    controlNames.append("TestStand UI Unknown Control.ctl") # Not a real thing
            else:
                controlNames.append("ActiveX Container")
        if match:
            for controlName in controlNames:
                matchingClasses.append("stdCont:"+controlName)
            matchingClasses.append("stdCont")
    if dcoTypeDesc.get("Type") == "Refnum" and dcoTypeDesc.get("RefType") == "LVObjCtl":
        # Controls from 3D Graph category: 3D Picture
        # Controls from Refnum category: Application Refnum, Control Refnum, VI Refnum
        # The difference between these is in CtlFlags
        match = True
        controlNames = []
        CtlFlags = dcoTypeDesc.get("CtlFlags")
        if CtlFlags is not None:
            CtlFlags = int(CtlFlags,0)
        else:
            CtlFlags = 0
        if match:
            if ((CtlFlags & 0x006e) == 0x0068):
                controlNames.append("3D Picture")
                for controlName in controlNames:
                    matchingClasses.append("scenegraphdisplay:"+controlName)
                matchingClasses.append("scenegraphdisplay")
            else:
                if ((CtlFlags & 0x006e) == 0x0006):
                    controlNames.append("Control Refnum")
                elif ((CtlFlags & 0x006e) == 0x0002):
                    controlNames.append("VI Refnum")
                else:
                    controlNames.append("Application Refnum")
                for controlName in controlNames:
                    matchingClasses.append("stdRefNum:"+controlName)
                matchingClasses.append("stdRefNum")
    if dcoTypeDesc.get("Type") == "Refnum":
        # Controls from Variant and Class category: LvObject
        match = True
        controlNames = []
        if dcoTypeDesc.get("RefType") != "UDClassInst":
            match = False
        dcoTypeItemList = dcoTypeDesc.findall("./Item")
        if   "LabVIEW Object" in [ itm.get("Text") for itm in dcoTypeItemList ]:
            controlNames.append("LabVIEW Object")
        else:
            match = False
        if match:
            for controlName in controlNames:
                matchingClasses.append("udClassDDO:"+controlName)
            matchingClasses.append("udClassDDO")
    if dcoTypeDesc.get("Type") == "Refnum":
        # Controls from I/O category: IMAQ Session
        # Controls from Refnum category: Automation Refnum, Bluetooth Refnum, Byte Stream Refnum,
        #   Data Log Refnum, DataSocket Refnum, dotNET Refnum, Event Callback, Irda Network,
        #   Menu Refnum, Occurrence Refnum, TCP Network, UDP Network
        match = True
        controlNames = []
        if   dcoTypeDesc.get("RefType") == "Imaq" and dcoTypeDesc.get("Ident") == "IMAQ":
            controlNames.append("IMAQ Session")
        elif dcoTypeDesc.get("RefType") == "AutoRef":
            controlNames.append("Automation Refnum")
        elif dcoTypeDesc.get("RefType") == "BluetoothCon":
            controlNames.append("Bluetooth Network Connection Refnum")
        elif dcoTypeDesc.get("RefType") == "ByteStream":
            controlNames.append("Byte Stream File Refnum")
        elif dcoTypeDesc.get("RefType") == "DataLog":
            controlNames.append("Data Log File Refnum")
        elif dcoTypeDesc.get("RefType") == "DataSocket":
            controlNames.append("DataSocket Refnum")
        elif dcoTypeDesc.get("RefType") == "DotNet":
            controlNames.append(".NET Refnum")
        elif dcoTypeDesc.get("RefType") == "Callback" and dcoTypeDesc.get("Ident") == "Event Callback":
            controlNames.append("Event Callback Refnum")
        elif dcoTypeDesc.get("RefType") == "IrdaNetConn":
            controlNames.append("IrDA Network Connection Refnum")
        elif dcoTypeDesc.get("RefType") == "Menu":
            controlNames.append("Menu Refnum")
        elif dcoTypeDesc.get("RefType") == "Occurrence":
            controlNames.append("Occurrence Refnum")
        elif dcoTypeDesc.get("RefType") == "TCPNetConn":
            controlNames.append("TCP Network Connection Refnum")
        elif dcoTypeDesc.get("RefType") == "UDPNetConn":
            controlNames.append("UDP Network Connection Refnum")
        else:
            match = False
        if match:
            for controlName in controlNames:
                matchingClasses.append("stdRefNum:"+controlName)
            matchingClasses.append("stdRefNum")
    if dcoTypeDesc.get("Type") == "LVVariant":
        # Controls from Variant and Class category: LVVariant
        match = True
        controlNames = []
        controlNames.append("Variant")
        if match:
            for controlName in controlNames:
                matchingClasses.append("stdLvVariant:"+controlName)
            matchingClasses.append("stdLvVariant")
    if dcoTypeDesc.get("Type") == "Refnum":
        # Controls from Containers category, FP parts: Sub Panel
        #TODO This has NO DCO - how can we support it?
        match = True
        controlNames = []
        if dcoTypeDesc.get("RefType") not in ("LVObjCtl",):
            match = False
        if True:
            controlNames.append("Sub Panel")
        if match:
            for controlName in controlNames:
                matchingClasses.append("grouper:"+controlName)
            matchingClasses.append("grouper")
    # Remove duplicates
    mClasses = list(set(matchingClasses))
    # Place most common items at start of the list
    for fpClass in ("stdPict","stdString","stdNum",):
        if fpClass in mClasses:
            mClasses.insert(0,mClasses.pop(mClasses.index(fpClass)))
    # Place most common items at start
    return mClasses

def DCO_recognize_fpClass_dcoName_from_dcoTypeID(RSRC, fo, po, dcoTypeID):
    """ Recognizes DCO class using only Heap typeID of the DCO as input

    This function may sometimes return fpClass different that the one used, because
    using only one TypeID for identification does not provide unequivocal result.
    """
    DTHP_typeDescSlice = RSRC.find("./DTHP/Section/TypeDescSlice")
    if DTHP_typeDescSlice is not None:
        DTHP_indexShift = DTHP_typeDescSlice.get("IndexShift")
        if DTHP_indexShift is not None:
            DTHP_indexShift = int(DTHP_indexShift, 0)
    if DTHP_indexShift is None:
        return None, None
    typeID = DTHP_indexShift+dcoTypeID-1
    # Get list of flat types for the recognition finction
    VCTP = RSRC.find("./VCTP/Section")
    VCTP_FlatTypeDescList = None
    if VCTP is not None:
        VCTP_FlatTypeDescList = VCTP.findall("TypeDesc")
    # Get DCO TypeDesc
    dcoTypeDesc = getConsolidatedTopType(RSRC, typeID, po)
    matchingClasses = DCO_recognize_fpClassEx_list_from_single_TypeDesc(RSRC, fo, po, VCTP_FlatTypeDescList, dcoTypeDesc)
    if len(matchingClasses) < 1:
        return None, None
    if ':' not in matchingClasses[0]:
        return matchingClasses[0], None
    return matchingClasses[0].split(':',2)

def DCO_recognize_from_typeIDs(RSRC, fo, po, typeID, endTypeID, VCTP_TypeDescList, VCTP_FlatTypeDescList):
    """ Recognizes DCO from its data space, starting at given typeID

    Returns amount of typeID entries used by that DCO, and DCO information dict.
    TypeID values within the DCO information dict are Top Types in dange between typeID and endTypeID, including boundary values.
    """
    VCTP = RSRC.find("./VCTP/Section")
    if VCTP is None or endTypeID < typeID:
        return 0, None
    # Get list of Flat TypeDescs
    flatTypeIDList = []
    for subTypeID in range(typeID, endTypeID+1):
        _, flatSubTypeID = getConsolidatedTopTypeAndID(RSRC, subTypeID, po, VCTP=VCTP)
        assert(flatSubTypeID is not None)
        flatTypeIDList.append(flatSubTypeID)
    tdCount, DCOShiftInfo = DCO_recognize_heap_TDs_from_flat_list(RSRC, fo, po, VCTP_FlatTypeDescList, flatTypeIDList)
    if DCOShiftInfo is None:
        return 0, None
    # Convert TypeID Shifts to Top TypeIDs
    dcoTypeID = typeID + DCOShiftInfo['dcoTypeID']
    partTypeIDs = [ typeID + typeIndex for typeIndex in DCOShiftInfo['partTypeIDs'] ]
    subTypeIDs = [ typeID + typeIndex for typeIndex in DCOShiftInfo['subTypeIDs'] ]
    extraTypeID = (typeID + DCOShiftInfo['extraTypeID']) if DCOShiftInfo['extraTypeID'] is not None else None
    ddoTypeID = typeID + DCOShiftInfo['ddoTypeID']
    DCOTopInfo = { 'fpClass': DCOShiftInfo['fpClass'], 'dcoName': DCOShiftInfo['dcoName'], 'dcoTypeID': dcoTypeID, 'partTypeIDs': partTypeIDs, 'extraTypeID': extraTypeID, 'ddoTypeID': ddoTypeID, 'subTypeIDs': subTypeIDs }
    return tdCount, DCOTopInfo

def DCO_recognize_TDs_after_cluster_from_flat_list(RSRC, fo, po, VCTP_FlatTypeDescList, flatTypeIDList, flatClusterTypeIDList):
    """ Recognizes list of items from a Cluster within given list of FlatTypeIDs

    Returns amount FlatTypeIDs consumed, or None if all entries couldn't be matched.
    The elements may be in different order in sub-TDs than inside the actual Cluster. Example of that behavior
    is "User Font" control, but also Cluster control with elements reordered after creation.
    """
    flatRemainTypeIDList = flatClusterTypeIDList.copy()
    tdShift = 0
    while len(flatRemainTypeIDList) > 0:
        tdSubCount = 0
        for flatTypeID in reversed(flatRemainTypeIDList):
            flatSubTypeIDList = [ flatTypeID ] + flatTypeIDList[tdShift:]
            tdSubCount, _ = DCO_recognize_heap_TDs_from_flat_list(RSRC, fo, po, VCTP_FlatTypeDescList, flatSubTypeIDList)
            if tdSubCount < 2: continue
            # Found one - end the loop
            break
        if tdSubCount < 2: # No match found
            return None
        # The element was matched - remove it from list
        flatRemainTypeIDList.remove(flatTypeID)
        tdShift += tdSubCount - 1
    return tdShift

def DCO_recognize_heap_TDs_from_flat_list(RSRC, fo, po, VCTP_FlatTypeDescList, flatTypeIDList):
    """ Recognizes DCO from its heap data space, using given list of FlatTypeIDs

    Returns amount of FlatTypeID entries used by that DCO, and DCO information dict.
    This is the most important function for re-creating DTHP and later FPHP section.
    """
    if len(flatTypeIDList) < 2:
        return 0, None
    # Get the DCO TypeDecs
    dcoFlatTypeID = flatTypeIDList[0]
    dcoTypeDesc = getConsolidatedFlatType(RSRC, dcoFlatTypeID, po)
    # Get the next TypeDesc
    n1FlatTypeID = flatTypeIDList[1]
    n1TypeDesc = getConsolidatedFlatType(RSRC, n1FlatTypeID, po)
    # Recognize matching classes by DCO TypeDesc
    matchingClasses = DCO_recognize_fpClassEx_list_from_single_TypeDesc(RSRC, fo, po, VCTP_FlatTypeDescList, dcoTypeDesc)

    # Recognize the DCO - start with Controls which use four or more FP TypeDescs, or the amount is dynamic
    dcoClass = [itm for itm in matchingClasses if itm in ("typeDef:RealMatrix.ctl","typeDef:ComplexMatrix.ctl",)]
    if len(dcoClass) > 0:
        # These use six TDs (for 2 dimensions), first and last pointing at the same flat TypeDef TD; second and third are
        # per-dimension NumUInt32 shift TDs; fourth is Array with the dimension elements inside, fifth is the TD from inside of TypeDef.
        match = True
        dcoInnerTypeDesc = dcoTypeDesc.find("./TypeDesc[@Type]")
        if dcoInnerTypeDesc is not None and dcoInnerTypeDesc.get("Type") == "Array":
            nDimensions = len(dcoInnerTypeDesc.findall("./Dimension"))
        else:
            nDimensions = 0
        if nDimensions < 1:
            match = False
        partTypeIDs = []
        for dimID in range(nDimensions):
            if len(flatTypeIDList) > 1+dimID:
                n2FlatTypeID = flatTypeIDList[1+dimID]
                n2TypeDesc = getConsolidatedFlatType(RSRC, n2FlatTypeID, po)
            else:
                n2TypeDesc, n2FlatTypeID = None, None
            if n2TypeDesc is not None and n2TypeDesc.get("Type") == "NumUInt32":
                partTypeIDs.append(1+dimID)
            else:
                match = False
        if len(partTypeIDs) != nDimensions:
            match = False
        dcoSubTypeDesc = dcoInnerTypeDesc.find("./TypeDesc[@TypeID]")
        if len(flatTypeIDList) > 1+nDimensions+0:
            extraFlatTypeID = flatTypeIDList[1+nDimensions+0]
            extraTypeDesc = getConsolidatedFlatType(RSRC, extraFlatTypeID, po)
        else:
            extraTypeDesc, extraFlatTypeID = None, None
        if extraTypeDesc is not None and extraTypeDesc.get("Type") == "Array":
            extraDimensions = len(extraTypeDesc.findall("./Dimension"))
            extraSubTypeDesc = extraTypeDesc.find("./TypeDesc[@TypeID]")
        else:
            extraDimensions = 0
            extraSubTypeDesc = None
        if nDimensions != extraDimensions:
            match = False
        if dcoSubTypeDesc is None or extraSubTypeDesc is None or dcoSubTypeDesc.get("TypeID") != extraSubTypeDesc.get("TypeID"):
            match = False
        if len(flatTypeIDList) > 1+nDimensions+1:
            n4FlatTypeID = flatTypeIDList[1+nDimensions+1]
            n4TypeDesc = getConsolidatedFlatType(RSRC, n4FlatTypeID, po)
        else:
            n4TypeDesc, n4FlatTypeID = None, None
        if n4TypeDesc is None or n4TypeDesc.get("Type") not in ("NumUInt32","NumFloat64","NumComplex128",):
            match = False
        if len(flatTypeIDList) > 1+nDimensions+2:
            n5FlatTypeID = flatTypeIDList[1+nDimensions+2]
            n5TypeDesc = getConsolidatedFlatType(RSRC, n5FlatTypeID, po)
        else:
            n5TypeDesc, n5FlatTypeID = None, None
        if dcoFlatTypeID != n5FlatTypeID:
            match = False
        if match:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': partTypeIDs, 'extraTypeID': 1+nDimensions+0, 'ddoTypeID': 1+nDimensions+2, 'subTypeIDs': [] }
            return 1+nDimensions+3, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("radioClust:Radio Buttons",)]
    if len(dcoClass) > 0 and dcoTypeDesc.get("Type") == n1TypeDesc.get("Type") and dcoFlatTypeID == n1FlatTypeID:
        # These use two Unit TDs, followed by bool TD for each radio button; both Unit TDs are pointing at the same flat index of UnitUInt TD,
        # radio buttons have separate TD for each. Unit TD has as much Enum entries as there are following radio button TDs.
        dcoSubTypeEnumLabels = dcoTypeDesc.findall("./EnumLabel")
        # Following that, we expect bool types from each radio button
        subTypeIDs = []
        subFlatTypeIDs = []
        match = True
        for i, dcoSubTypeEnLabel in enumerate(dcoSubTypeEnumLabels):
            if len(flatTypeIDList) <= 2+i:
                match = False
                break
            subFlatTypeID = flatTypeIDList[2+i]
            subTypeDesc = getConsolidatedFlatType(RSRC, subFlatTypeID, po)
            if subTypeDesc is None or subTypeDesc.get("Type") != "Boolean":
                match = False
                break
            subFlatTypeIDs.append(subFlatTypeID)
            subTypeIDs.append(2+i)
        # The Flat Types inside needs to be unique for each radio button
        if len(subFlatTypeIDs) > len(set(subFlatTypeIDs)):
            match = False # Some types repeat - fail
        if match:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [], 'extraTypeID': None, 'ddoTypeID': 1, 'subTypeIDs': subTypeIDs }
            return 2+len(dcoSubTypeEnumLabels), DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("tabControl:Tab Control",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "UnitUInt32" and dcoFlatTypeID != n1FlatTypeID:
        # These use four TDs, first and last pointing at the same flat TD; second has its own TD, of the same type; third is NumInt32.
        match = True
        if len(flatTypeIDList) > 2:
            n2FlatTypeID = flatTypeIDList[2]
            n2TypeDesc = getConsolidatedFlatType(RSRC, n2FlatTypeID, po)
        else:
            n2TypeDesc, n2FlatTypeID = None, None
        if n2TypeDesc is None or n2TypeDesc.get("Type") not in ("NumInt32",):
            match = False
        if len(flatTypeIDList) > 3:
            n3FlatTypeID = flatTypeIDList[3]
            n3TypeDesc = getConsolidatedFlatType(RSRC, n3FlatTypeID, po)
        else:
            n3TypeDesc, n3FlatTypeID = None, None
        if dcoFlatTypeID != n3FlatTypeID:
            match = False
        if match:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [ 1, 2 ], 'extraTypeID': None, 'ddoTypeID': 3, 'subTypeIDs': [] }
            return 4, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("typeDef:LabVIEW Test - Invocation Info.ctl","typeDef:LabVIEW Test - Test Data.ctl",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "Cluster":
        # These use nine TDs, first and last pointing at the same flat TypeDef TD; next there is a Cluster and after it - its content fields.
        match = True
        # Verify DCO Inner TypeDesc
        dcoInnerTypeDesc = dcoTypeDesc.find("./TypeDesc[@Type]")
        if dcoInnerTypeDesc is not None and dcoInnerTypeDesc.get("Type") == "Cluster":
            dcoInnerTDMapList = dcoInnerTypeDesc.findall("./TypeDesc[@TypeID]")
        else:
            dcoInnerTDMapList = []
        # Create list of fields within Cluster
        dcoFlatInnerTypeIDList = []
        for i, dcoInnerTDMap in enumerate(dcoInnerTDMapList):
            dcoInnTypeDesc, _, dcoFlatInnTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, dcoInnerTDMap, po)
            if dcoInnTypeDesc is None:
                break
            dcoFlatInnerTypeIDList.append(dcoFlatInnTypeID)
        # The type following DCO TypeID should be the same as DCO Inner TypeDesc
        if not TypeDesc_equivalent(RSRC, fo, po, dcoInnerTypeDesc, n1TypeDesc, VCTP_FlatTypeDescList):
            match = False
        niTypeIDShift = 2
        partTypeIDs = []
        if True:
            # Verify TDs between DCO TD and DDO TD - items from inside the Cluster following the Cluster
            matchedTypeIDShift = DCO_recognize_TDs_after_cluster_from_flat_list(RSRC, fo, po, VCTP_FlatTypeDescList, flatTypeIDList[niTypeIDShift:], dcoFlatInnerTypeIDList)
            if matchedTypeIDShift is not None:
                for i in range(matchedTypeIDShift):
                    partTypeIDs.append(niTypeIDShift+i)
            else:
                match = False
        ddoTypeIDShift = niTypeIDShift+len(partTypeIDs)
        if match:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': partTypeIDs, 'extraTypeID': None, 'ddoTypeID': ddoTypeIDShift, 'subTypeIDs': [] }
            return ddoTypeIDShift+1, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("stdGraph:Digital Waveform Graph","stdGraph:Waveform Graph", \
          "stdGraph:Intensity Chart","stdGraph:XY Graph","stdGraph:Express XY Graph","stdGraph:Waveform Chart",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "NumUInt32":
        # These use over fifteen TDs, first and last pointing at the same flat TD of Cluster,Array or NumFloat64 type; inbetween there is
        #   a combination of NumUInt32, Array, Cluster, String, Boolean, with some chunks of the types depending on specific control kind.
        match = True
        prop1TypeIDShift = 1
        # Verify TDs between DCO TD and DDO TD - constant part at start, with optional copy
        # (well, not exact copy - the 2nd one has different amount of Bool properties in a cluster)
        prop1TypeIDs = []
        contentMatches = 0
        for contentDescrNo in range(2):
            niAddTypeIDs = []

            prop2TypeIDShift = prop1TypeIDShift+len(prop1TypeIDs)
            if len(flatTypeIDList) > prop2TypeIDShift:
                n2FlatTypeID = flatTypeIDList[prop2TypeIDShift]
                n2TypeDesc = getConsolidatedFlatType(RSRC, n2FlatTypeID, po)
            else:
                n2TypeDesc, n2FlatTypeID = None, None
            if n2TypeDesc.get("Type") != "NumUInt32":
                break
            niAddTypeIDs.append(prop2TypeIDShift)

            prop3TypeIDShift = prop2TypeIDShift+1
            if len(flatTypeIDList) > prop3TypeIDShift:
                n3FlatTypeID = flatTypeIDList[prop3TypeIDShift]
                n3TypeDesc = getConsolidatedFlatType(RSRC, n3FlatTypeID, po)
            else:
                n3TypeDesc, n3FlatTypeID = None, None
            if n3TypeDesc.get("Type") != "Array":
                break
            niSubTypeDescMap = n3TypeDesc.find("./TypeDesc[@TypeID]")
            if niSubTypeDescMap is not None:
                niSubClustTypeDesc, _, niSubClustTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, niSubTypeDescMap, po)
            else:
                niSubClustTypeDesc, niSubClustTypeID = None, None
            if niSubClustTypeDesc is None or niSubClustTypeDesc.get("Type") != "Cluster":
                break
            n3PartTypeDescMapList = niSubClustTypeDesc.findall("./TypeDesc[@TypeID]")
            if len(n3PartTypeDescMapList) < 3 or len(n3PartTypeDescMapList) > 4:
                break
            checkPassed = 0
            for si, niPartTypeDescMap in enumerate(n3PartTypeDescMapList):
                niSubTypeDesc, _, niFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, niPartTypeDescMap, po)
                if niSubTypeDesc is None:
                    break
                if   si == 0:
                    if niSubTypeDesc.get("Type") == "String":
                        checkPassed += 1
                elif si >= 1:
                    if niSubTypeDesc.get("Type") == "Boolean":
                        checkPassed += 1
            if checkPassed != len(n3PartTypeDescMapList):
                break
            niAddTypeIDs.append(prop3TypeIDShift)
            prop3TypeIDShift += 1
            # Verify TDs between DCO TD and DDO TD - items from inside the Array following the Array
            matchedTypeIDShift = DCO_recognize_TDs_after_cluster_from_flat_list(RSRC, fo, po, VCTP_FlatTypeDescList, flatTypeIDList[prop3TypeIDShift:], [niSubClustTypeID])
            if matchedTypeIDShift is None:
                break
            for i in range(matchedTypeIDShift):
                niAddTypeIDs.append(prop3TypeIDShift+i)
            prop1TypeIDs.extend(niAddTypeIDs)
            contentMatches += 1
        if contentMatches < 1: # At least one match is required
            match = False
        prop4TypeIDShift = prop1TypeIDShift+len(prop1TypeIDs)

        # Verify TDs between DCO TD and DDO TD - cluster of bools
        prop4TypeIDs = []
        contentMatches = 0
        for contentDescrNo in range(1):
            niAddTypeIDs = []

            if len(flatTypeIDList) > prop4TypeIDShift:
                n4FlatTypeID = flatTypeIDList[prop4TypeIDShift]
                n4TypeDesc = getConsolidatedFlatType(RSRC, n4FlatTypeID, po)
            else:
                n4TypeDesc, n4FlatTypeID = None, None
            if n4TypeDesc.get("Type") != "Cluster":
                break
            n4PartTypeDescMapList = n4TypeDesc.findall("./TypeDesc[@TypeID]")
            if len(n4PartTypeDescMapList) < 3 or len(n4PartTypeDescMapList) > 4:
                break
            checkPassed = 0
            flatClusterTypeIDList = []
            for si, niPartTypeDescMap in enumerate(n4PartTypeDescMapList):
                niSubTypeDesc, _, niFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, niPartTypeDescMap, po)
                if niSubTypeDesc is None:
                    break
                if si >= 0: # all are bools here
                    if niSubTypeDesc.get("Type") == "Boolean":
                        checkPassed += 1
                flatClusterTypeIDList.append(niFlatSubTypeID)
            if checkPassed != len(n4PartTypeDescMapList):
                break
            niAddTypeIDs.append(prop4TypeIDShift)
            # Verify TDs between DCO TD and DDO TD - items from inside the Cluster following the Cluster
            matchedTypeIDShift = DCO_recognize_TDs_after_cluster_from_flat_list(RSRC, fo, po, VCTP_FlatTypeDescList, flatTypeIDList[prop4TypeIDShift+1:], flatClusterTypeIDList)
            if matchedTypeIDShift is None:
                break
            for i in range(matchedTypeIDShift):
                niAddTypeIDs.append(prop4TypeIDShift+1+i)
            prop4TypeIDs.extend(niAddTypeIDs)
            contentMatches += 1
        if contentMatches != 1: # Exactly one match is required
            match = False
        prop5TypeIDShift = prop4TypeIDShift+len(prop4TypeIDs)

        # Verify TDs between DCO TD and DDO TD - Array near end
        prop5TypeIDs = []
        if len(flatTypeIDList) > prop5TypeIDShift+1:
            for i in range(1):
                niFlatTypeID = flatTypeIDList[prop5TypeIDShift+i]
                niTypeDesc = getConsolidatedFlatType(RSRC, niFlatTypeID, po)
                if niTypeDesc is None:
                    break
                if i == 0:
                    if niTypeDesc.get("Type") != "Array":
                        break
                prop5TypeIDs.append(prop5TypeIDShift+i)
        if len(prop5TypeIDs) != 1:
            match = False
        prop6TypeIDShift = prop5TypeIDShift+len(prop5TypeIDs)
        # Verify TDs between DCO TD and DDO TD - optional part at end
        prop6TypeIDs = []
        prop4FirstTD = None
        if len(flatTypeIDList) > prop6TypeIDShift+1:
            for i in range(1):
                niFlatTypeID = flatTypeIDList[prop6TypeIDShift+i]
                niTypeDesc = getConsolidatedFlatType(RSRC, niFlatTypeID, po)
                if niTypeDesc is None:
                    break
                if   i == 0: # Exists for: Digital Waveform, Intensity Chart
                    prop4FirstTD = niTypeDesc
                    if niTypeDesc.get("Type") != "String" and niTypeDesc.get("Type") != "NumUInt32":
                        break
                prop6TypeIDs.append(prop6TypeIDShift+i)
        if len(flatTypeIDList) > prop6TypeIDShift+2 and prop4FirstTD is not None and prop4FirstTD.get("Type") == "NumUInt32":
            for i in range(1,2):
                niFlatTypeID = flatTypeIDList[prop6TypeIDShift+i]
                niTypeDesc = getConsolidatedFlatType(RSRC, niFlatTypeID, po)
                if niTypeDesc is None:
                    break
                if   i == 1: # Exists for: Intensity Chart
                    if niTypeDesc.get("Type") != prop4FirstTD.get("Type"):
                        break
                prop6TypeIDs.append(prop6TypeIDShift+i)
        # Optional part - if no match found, assume it's not there
        if len(prop6TypeIDs) not in (1,2,):
            prop6TypeIDs = [] # Continue as if nothing was matched
        ddoTypeIDShift = prop6TypeIDShift+len(prop6TypeIDs)
        # Make list of all part TypeIDs
        partTypeIDs = prop1TypeIDs + prop4TypeIDs + prop5TypeIDs + prop6TypeIDs

        # Verify DDO TD
        if len(flatTypeIDList) > ddoTypeIDShift:
            n21FlatTypeID = flatTypeIDList[ddoTypeIDShift]
            n21TypeDesc = getConsolidatedFlatType(RSRC, n21FlatTypeID, po)
        else:
            n21TypeDesc, n21FlatTypeID = None, None
        if n21TypeDesc is None or n21TypeDesc.get("Type") != dcoTypeDesc.get("Type") or dcoFlatTypeID != n21FlatTypeID:
            match = False

        subTypeIDs = []
        hasHistTD = True
        # For some controls, we have additional Cluster at end; detect it by content
        if hasHistTD:
            if len(flatTypeIDList) > ddoTypeIDShift+1:
                histFlatTypeID = flatTypeIDList[ddoTypeIDShift+1]
                histTypeDesc = getConsolidatedFlatType(RSRC, histFlatTypeID, po)
            else:
                histTypeDesc, histFlatTypeID = None, None
            if histTypeDesc is not None and histTypeDesc.get("Type") == "Cluster":
                histClustTypeMap = histTypeDesc.findall("./TypeDesc[@TypeID]")
            else:
                histClustTypeMap = []

            if len(histClustTypeMap) != 6:
                hasHistTD = False
            histClustTypeDescList = []
            histClustFlatTypeIDList = []
            for hcTypeMap in histClustTypeMap:
                hcTypeDesc, _, hcFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, hcTypeMap, po)
                if hcTypeDesc is None:
                    break
                histClustTypeDescList.append(hcTypeDesc)
                histClustFlatTypeIDList.append(hcFlatSubTypeID)
            if len(histClustTypeDescList) == 6:
                if histClustTypeDescList[0].get("Type") == "Cluster" and histClustFlatTypeIDList[0] == histClustFlatTypeIDList[5]:
                    histCCTypeMap = histClustTypeDescList[0].findall("./TypeDesc[@TypeID]")
                else:
                    histCCTypeMap = []
                if len(histCCTypeMap) != 4:
                    hasHistTD = False

                for hcci, hccTypeMap in enumerate(histCCTypeMap):
                    hccTypeDesc, _, hccFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, hccTypeMap, po)
                    if hccTypeDesc is None:
                        hasHistTD = False
                        break
                    if hcci in (0,1,2,):
                        if hccTypeDesc.get("Type") != "NumInt32":
                            hasHistTD = False
                            break
                    elif hcci == 3:
                        if hccTypeDesc.get("Type") != "Array":
                            hasHistTD = False
                            break
                        #TODO we could verify the array type
                if histClustTypeDescList[1].get("Type") != "NumInt32":
                    hasHistTD = False
                if histClustTypeDescList[2].get("Type") != "NumInt16" or histClustFlatTypeIDList[2] != histClustFlatTypeIDList[3]:
                    hasHistTD = False
                if histClustTypeDescList[4].get("Type") != "NumUInt32":
                    hasHistTD = False
            else:
                hasHistTD = False
        if hasHistTD:
            subTypeIDs.append(ddoTypeIDShift+1)
        if match:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': partTypeIDs, 'extraTypeID': None, 'ddoTypeID': ddoTypeIDShift, 'subTypeIDs': subTypeIDs }
            return ddoTypeIDShift+len(subTypeIDs)+1, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("stdClust:Cluster","stdClust:User Font.ctl", \
          "stdClust:Text Alignment.ctl","stdClust:Rect.ctl","stdClust:Point.ctl",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "Cluster" and dcoFlatTypeID == n1FlatTypeID:
        # These use two Cluster TDs of same flat index, followed by TDs for each item within the cluster, but without DCO TDs.
        # The items from inside cluster can be in different order than "master" types.
        dcoSubTypeDescMap = dcoTypeDesc.findall("./TypeDesc")
        dcoSubFlatTypeIDList = []
        for TDTopMap in dcoSubTypeDescMap:
            TypeDesc, _, FlatTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, TDTopMap, po)
            if TypeDesc is None: continue
            dcoSubFlatTypeIDList.append(FlatTypeID)
        # Following that, we expect types from inside the Cluster; make sure all are matching
        match = True
        tdShift = 2
        matchedTypeIDShift = DCO_recognize_TDs_after_cluster_from_flat_list(RSRC, fo, po, VCTP_FlatTypeDescList, flatTypeIDList[2:], dcoSubFlatTypeIDList)
        subTypeIDs = []
        if matchedTypeIDShift is not None:
            for i in range(matchedTypeIDShift):
                subTypeIDs.append(tdShift+i)
            tdShift += matchedTypeIDShift
        else:
            match = False
        if match:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [], 'extraTypeID': None, 'ddoTypeID': 1, 'subTypeIDs': subTypeIDs }
            return tdShift, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("stdMeasureData:Digital Waveform.ctl","stdMeasureData:Waveform",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "Cluster":
        # These use over ten TDs, first and last pointing at the same flat TD of MeasureData type; inbetween there is
        #   a Cluster, and following types which are dependancies of that Cluster. Some elements within the Cluster depend on specific control kind.
        match = True
        partTypeIDs = []
        niTypeIDShift = 1 + len(partTypeIDs)
        # Verify TDs between DCO TD and DDO TD - the Cluster
        flatClusterTypeIDList = []
        if  True:
            n1SubTypeDescMapList = n1TypeDesc.findall("./TypeDesc[@TypeID]")
            if len(n1SubTypeDescMapList) != 5:
                match = False
            # Verify fields within Cluster
            for si, n1SubTypeDescMap in enumerate(n1SubTypeDescMapList):
                n1SubTypeDesc, _, n1FlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, n1SubTypeDescMap, po)
                if n1SubTypeDesc is None:
                    match = False
                    break
                if   si in (0,):
                    if n1SubTypeDesc.get("Type") != "MeasureData" or n1SubTypeDesc.get("Flavor") != "TimeStamp": # t0
                        match = False
                elif si in (1,):
                    if n1SubTypeDesc.get("Type") != "NumFloat64": # dt
                        match = False
                elif si in (2,):
                    if  dcoTypeDesc.get("Flavor") == "DigitalWaveform":
                        if n1SubTypeDesc.get("Type") != "MeasureData" or n1SubTypeDesc.get("Flavor") != "Digitaldata": # Y
                            match = False
                    elif  dcoTypeDesc.get("Flavor") == "Float64Waveform":
                        if n1SubTypeDesc.get("Type") != "Array": # Y
                            match = False
                        # Get the array item type
                        n1SubArrTDMap = n1SubTypeDesc.find("./TypeDesc[@TypeID]")
                        if n1SubArrTDMap is not None:
                            n1SubSubTypeDesc, _, n1FlatSubSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, n1SubArrTDMap, po)
                        else:
                            n1SubSubTypeDesc, n1FlatSubSubTypeID = None, None
                        if n1SubSubTypeDesc is None or n1SubSubTypeDesc.get("Type") != "NumFloat64":
                            match = False
                        #TODO Array-in-Cluster Array in this case has its content typeID inserted after the Cluster, we need the below hack
                        #TODO Array-in-Cluster to accept the types following the cluster; maybe every array within Cluster behaves like this?
                        if n1FlatSubSubTypeID is not None:
                            flatClusterTypeIDList.append(n1FlatSubSubTypeID)
                    else:
                        match = False
                elif si in (3,):
                    if n1SubTypeDesc.get("Type") != "Cluster": # standard Error Cluster
                        match = False
                    n1ErrorTDMapList = n1SubTypeDesc.findall("./TypeDesc[@TypeID]")
                    for ssi, n1ErrorTDMap in enumerate(n1ErrorTDMapList):
                        n1ErrorTypeDesc, _, n1ErrorFlatTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, n1ErrorTDMap, po)
                        if n1ErrorTypeDesc is None:
                            match = False
                            break
                        if   ssi in (0,):
                            if n1ErrorTypeDesc.get("Type") != "Boolean":
                                match = False
                        elif ssi in (1,):
                            if n1ErrorTypeDesc.get("Type") != "NumInt32":
                                match = False
                        elif ssi in (2,):
                            if n1ErrorTypeDesc.get("Type") != "String":
                                match = False
                elif si in (4,):
                    if n1SubTypeDesc.get("Type") != "LVVariant": # attributes
                        match = False
                if not match:
                    break
                flatClusterTypeIDList.append(n1FlatSubTypeID)
            partTypeIDs.append(niTypeIDShift)
        niTypeIDShift = 1 + len(partTypeIDs)
        # Verify TDs between DCO TD and DDO TD - items from inside the Cluster following the Cluster
        matchedTypeIDShift = DCO_recognize_TDs_after_cluster_from_flat_list(RSRC, fo, po, VCTP_FlatTypeDescList, flatTypeIDList[niTypeIDShift:], flatClusterTypeIDList)
        if matchedTypeIDShift is not None:
            for i in range(matchedTypeIDShift):
                partTypeIDs.append(flatTypeIDList[niTypeIDShift+i])
        else:
            match = False
        niTypeIDShift = 1 + len(partTypeIDs)
        ddoFlatTypeID = flatTypeIDList[niTypeIDShift]
        if dcoFlatTypeID != ddoFlatTypeID:
                match = False
        if match:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': partTypeIDs, 'extraTypeID': None, 'ddoTypeID': niTypeIDShift, 'subTypeIDs': [] }
            return niTypeIDShift+1, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("tableControl:Table Control","tableControl:mergeTable.vi",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "NumUInt32" and dcoFlatTypeID != n1FlatTypeID:
        # Controls from List Table And Tree category: Table Control, Ex Table
        # These use four TDs, first and last pointing at the same flat TD; second and third are NumUInt32.
        match = True
        if len(flatTypeIDList) > 2:
            n2FlatTypeID = flatTypeIDList[2]
            n2TypeDesc = getConsolidatedFlatType(RSRC, n2FlatTypeID, po)
        else:
            n2TypeDesc, n2FlatTypeID = None, None
        if n2TypeDesc is None or n2TypeDesc.get("Type") not in ("NumUInt32",):
            match = False
        if n2FlatTypeID != n1FlatTypeID:
            match = False
        if len(flatTypeIDList) > 3:
            n3FlatTypeID = flatTypeIDList[3]
            n3TypeDesc = getConsolidatedFlatType(RSRC, n3FlatTypeID, po)
        else:
            n3TypeDesc, n3FlatTypeID = None, None
        if dcoFlatTypeID != n3FlatTypeID:
            match = False
        if match:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [ 1, 2 ], 'extraTypeID': None, 'ddoTypeID': 3, 'subTypeIDs': [] }
            return 4, DCOInfo

    # Controls which use three or less FP TypeDefs are left below
    dcoClass = [itm for itm in matchingClasses if itm in ("xControl:3D Line Graph.vi","xControl:3D Parametric Graph.vi",
          "xControl:3D Surface Graph.vi","xControl:2D Error Bar Plot.vi","xControl:2D Feather Plot.vi","xControl:2D Compass",
          "xControl:3D_Bar_Plot_Merge_VI.vi","xControl:3D_Comet_Plot_Merge_VI.vi","xControl:3D_Contour_Plot_Merge_VI.vi",
          "xControl:3D_Mesh_Plot_Merge_VI.vi","xControl:3D_Pie_Plot_Merge_VI.vi","xControl:3D_Quiver_Plot_Merge_VI.vi",
          "xControl:3D_Ribbon_Plot_Merge_VI.vi","xControl:3D_Scatter_Plot_Merge_VI.vi","xControl:3D_Stem_Plot_Merge_VI.vi",
          "xControl:3D_Surface_Plot_Merge_VI.vi","xControl:3D_Waterfall_Plot_Merge_VI.vi","xControl:XY Plot Matrix.vi",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "Array" and dcoFlatTypeID == n1FlatTypeID:
        # These use three TDs; two are pointing at the same flat index of Array TD; third is a TypeDef with Cluster TD for state.
        match = True
        # Get the array item type
        dcoSubTDMap = dcoTypeDesc.find("./TypeDesc[@TypeID]")
        dcoSubTypeDesc, _, dcoFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, dcoSubTDMap, po)
        # Now check the third TD
        if len(flatTypeIDList) > 2:
            n2FlatTypeID = flatTypeIDList[2]
            n2TypeDesc = getConsolidatedFlatType(RSRC, n2FlatTypeID, po)
        else:
            n2TypeDesc, n2FlatTypeID = None, None
        if n2TypeDesc is not None and n2TypeDesc.get("Type") == "TypeDef":
            n2ClustTypeDesc = n2TypeDesc.find("./TypeDesc[@Type]")
        else:
            n2ClustTypeDesc = None
        if n2ClustTypeDesc is not None and n2ClustTypeDesc.get("Type") == "Cluster":
            n2SubTypeDesc = n2ClustTypeDesc.findall("./TypeDesc[@TypeID]")
        else:
            n2SubTypeDesc = []
        # The state Cluster has 3 or more items; first is a copy of DCO sub-TD, second is TypeDef with queue, following are some int properties.
        if len(n2SubTypeDesc) < 3 or len(n2SubTypeDesc) > 9:
            match = False
        expectContent = ""
        for i, stateTypeMap in enumerate(n2SubTypeDesc):
            stateTypeDesc, _, stateFlatTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, stateTypeMap, po)
            if stateTypeDesc is None:
                match = False
                break
            if i == 0:
                if stateTypeDesc.get("Type") == "TypeDef":
                    expectContent = "LineGraph"
                elif stateTypeDesc.get("Type") == dcoSubTypeDesc.get("Type"):
                    expectContent = "Contour"
                else:
                    match = False
                    break
            if   expectContent == "LineGraph":
                if i == 0: # Graph Properties
                    if stateTypeDesc.get("Type") != "TypeDef":
                        match = False
                    grpropTypeDesc = stateTypeDesc.find("./TypeDesc[@Type]")
                    if grpropTypeDesc is not None and grpropTypeDesc.get("Type") == "Cluster":
                        grpropTypeMapList = grpropTypeDesc.findall("./TypeDesc[@TypeID]")
                    else:
                        grpropTypeMapList = []
                    if len(grpropTypeMapList) != 9:
                        match = False
                elif i == 1: # Plot/Axes/Cursor Properties
                    if stateTypeDesc.get("Type") != "TypeDef":
                        match = False
                    pacpropTypeDesc = stateTypeDesc.find("./TypeDesc[@Type]")
                    if pacpropTypeDesc is not None and pacpropTypeDesc.get("Type") == "Cluster":
                        pacpropTypeMapList = pacpropTypeDesc.findall("./TypeDesc[@TypeID]")
                    else:
                        pacpropTypeMapList = []
                    if len(grpropTypeMapList) != 9:
                        match = False
                    for ppi, pacpropTypeMap in enumerate(pacpropTypeMapList):
                        ppeTypeDesc, _, ppeFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, pacpropTypeMap, po)
                        if ppi in (1,2,3,4,5,6,):
                            if stateTypeDesc.get("Type") != "TypeDef":
                                match = False
                            #TODO we could check content of each typedef
                        elif ppi == 7:
                            if stateTypeDesc.get("Type") != "Array":
                                match = False
                            #TODO we could check content of that array
                elif i in (2,3,4,):
                    if stateTypeDesc.get("Type") != "NumInt32":
                        match = False
                else:
                    if stateTypeDesc.get("Type") != "Boolean":
                        match = False
            elif expectContent == "Contour":
                if i == 0:
                    if stateTypeDesc.get("Type") != dcoSubTypeDesc.get("Type") or stateTypeDesc.get("RefType") != dcoSubTypeDesc.get("RefType"):
                        match = False
                elif i == 1:
                    if stateTypeDesc.get("Type") != "TypeDef":
                        match = False
                    stateRefTypeDesc = stateTypeDesc.find("./TypeDesc[@Type]")
                    if stateRefTypeDesc is not None and stateRefTypeDesc.get("Type") == "Refnum" and stateRefTypeDesc.get("RefType") == "Queue":
                        queueTypeMap = stateRefTypeDesc.find("./TypeDesc[@TypeID]")
                    else:
                        queueTypeMap = None
                    if queueTypeMap is not None:
                        queueTypeDesc, _, queueFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, queueTypeMap, po)
                    else:
                        queueTypeDesc, queueFlatSubTypeID = None, None
                    if queueTypeDesc is None or queueTypeDesc.get("Type") != "TypeDef":
                        match = False
                else:
                    if stateTypeDesc.get("Type") != "NumUInt32":
                        match = False
        if match:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [], 'extraTypeID': None, 'ddoTypeID': 1, 'subTypeIDs': [ 2 ] }
            return 3, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("stdKnob:Knob","stdKnob:Dial","stdKnob:Gauge","stdKnob:Meter",)]
    if len(dcoClass) > 0 and dcoTypeDesc.get("Type") == n1TypeDesc.get("Type") and dcoFlatTypeID != n1FlatTypeID:
        # These use three TDs, first and last pointing at the same flat TD; second has its own TD, of the same type.
        if len(flatTypeIDList) > 2:
            n2FlatTypeID = flatTypeIDList[2]
            n2TypeDesc = getConsolidatedFlatType(RSRC, n2FlatTypeID, po)
        else:
            n2TypeDesc, n2FlatTypeID = None, None
        match = True
        if dcoFlatTypeID != n2FlatTypeID:
                match = False
        if match:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [ 1 ], 'extraTypeID': None, 'ddoTypeID': 2, 'subTypeIDs': [] }
            return 3, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("stdSlide:Slide","stdSlide:Bar","stdSlide:Tank","stdSlide:Thermometer",)]
    if len(dcoClass) > 0 and dcoTypeDesc.get("Type") == n1TypeDesc.get("Type") and dcoFlatTypeID != n1FlatTypeID:
        # These use three TDs, first and last pointing at the same flat TD; second has its own TD, of the same type.
        if len(flatTypeIDList) > 2:
            n2FlatTypeID = flatTypeIDList[2]
            n2TypeDesc = getConsolidatedFlatType(RSRC, n2FlatTypeID, po)
        else:
            n2TypeDesc, n2FlatTypeID = None, None
        match = True
        if dcoFlatTypeID != n2FlatTypeID:
                match = False
        if match:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [ 1 ], 'extraTypeID': None, 'ddoTypeID': 2, 'subTypeIDs': [] }
            return 3, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("typeDef:LabVIEW Test - Input Buffer.ctl","typeDef:LabVIEW Test - Sequence Context.ctl",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") in ("String","Refnum",):
        # These use three TDs, first and last pointing at the same flat TypeDef TD; second has its own TD, of String type.
        match = True
        dcoInnerTypeDesc = dcoTypeDesc.find("./TypeDesc[@Type]")
        # The type following DCO TypeID should be the same as DCO Inner TypeDesc
        if not TypeDesc_equivalent(RSRC, fo, po, dcoInnerTypeDesc, n1TypeDesc, VCTP_FlatTypeDescList):
            match = False
        # Check the finishing DDO TypeID
        if len(flatTypeIDList) > 2:
            n2FlatTypeID = flatTypeIDList[2]
            n2TypeDesc = getConsolidatedFlatType(RSRC, n2FlatTypeID, po)
        else:
            n2TypeDesc, n2FlatTypeID = None, None
        if dcoFlatTypeID != n2FlatTypeID:
            match = False
        if match:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [ 1 ], 'extraTypeID': None, 'ddoTypeID': 2, 'subTypeIDs': [] }
            return 3, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("stdRefNum:Shared Variable Control","stdRefNum:DAQmx Task Name",\
          "stdRefNum:DAQmx Channel","stdRefNum:FieldPoint IO Point","stdRefNum:Motion Resource",\
          "stdRefNum:nisyscfg.ctl","stdRefNum:VISA resource name","stdRefNum:IVI Logical Name",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "Tag" and dcoFlatTypeID != n1FlatTypeID:
        # These use three TDs, first and last pointing at the same flat Refnum TD; second has its own TD, of Tag type.
        match = True
        if len(flatTypeIDList) > 2:
            n2FlatTypeID = flatTypeIDList[2]
            n2TypeDesc = getConsolidatedFlatType(RSRC, n2FlatTypeID, po)
        else:
            n2TypeDesc, n2FlatTypeID = None, None
        dcoSubTDMap = dcoTypeDesc.find("./TypeDesc[@TypeID]")
        dcoSubTypeDesc, _, dcoFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, dcoSubTDMap, po)
        if dcoFlatSubTypeID != n1FlatTypeID:
            match = False
        if match:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [ 1 ], 'extraTypeID': None, 'ddoTypeID': 2, 'subTypeIDs': [] }
            return 3, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("absTime:Time Stamp",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "Boolean" and dcoFlatTypeID != n1FlatTypeID:
        # These use three TDs, first and last pointing at the same flat Measuredata TD; second has its own TD, of Boolean type.
        if len(flatTypeIDList) > 2:
            n2FlatTypeID = flatTypeIDList[2]
            n2TypeDesc = getConsolidatedFlatType(RSRC, n2FlatTypeID, po)
        else:
            n2TypeDesc, n2FlatTypeID = None, None
        match = True
        if dcoFlatTypeID != n2FlatTypeID:
                match = False
        if match:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [ 1 ], 'extraTypeID': None, 'ddoTypeID': 2, 'subTypeIDs': [] }
            return 3, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("stdComboBox:Combo Box",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "NumInt32" and dcoFlatTypeID != n1FlatTypeID:
        # These use three TDs, first and last pointing at the same flat String TD; second has its own TD, of NumInt32 type.
        if len(flatTypeIDList) > 2:
            n2FlatTypeID = flatTypeIDList[2]
            n2TypeDesc = getConsolidatedFlatType(RSRC, n2FlatTypeID, po)
        else:
            n2TypeDesc, n2FlatTypeID = None, None
        match = True
        if dcoFlatTypeID != n2FlatTypeID:
                match = False
        if match:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [ 1 ], 'extraTypeID': None, 'ddoTypeID': 2, 'subTypeIDs': [] }
            return 3, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("indArr:Array",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "NumUInt32" and dcoFlatTypeID != n1FlatTypeID:
        # These use three TDs, first and last pointing at the same flat Array TD; second has its own TD, of NumUInt32 type.
        if len(flatTypeIDList) > 2:
            n2FlatTypeID = flatTypeIDList[2]
            n2TypeDesc = getConsolidatedFlatType(RSRC, n2FlatTypeID, po)
        else:
            n2TypeDesc, n2FlatTypeID = None, None
        match = True
        if dcoFlatTypeID != n2FlatTypeID:
                match = False
        if match:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [ 1 ], 'extraTypeID': None, 'ddoTypeID': 2, 'subTypeIDs': [] }
            return 3, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("stdPath:File Path",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "Boolean" and dcoFlatTypeID != n1FlatTypeID:
        # These use three TDs, first and last pointing at the same flat Path TD; second has its own TD, of Boolean type.
        if len(flatTypeIDList) > 2:
            n2FlatTypeID = flatTypeIDList[2]
            n2TypeDesc = getConsolidatedFlatType(RSRC, n2FlatTypeID, po)
        else:
            n2TypeDesc, n2FlatTypeID = None, None
        match = True
        if dcoFlatTypeID != n2FlatTypeID:
                match = False
        if match:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [ 1 ], 'extraTypeID': None, 'ddoTypeID': 2, 'subTypeIDs': [] }
            return 3, DCOInfo

    # Controls which use two or less FP TypeDefs are left below
    dcoClass = [itm for itm in matchingClasses if itm in ("stdBool:Push Button","stdBool:Rocker","stdBool:Toggle Switch", \
          "stdBool:Slide Switch","stdBool:OK Button","stdBool:Cancel Button","stdBool:Stop Button","stdBool:LED",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "Boolean" and dcoFlatTypeID == n1FlatTypeID:
        # These use two TDs, both pointing at the same flat index of Boolean TD.
        if True:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [], 'extraTypeID': None, 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("stdNum:Numeric","stdColorNum:Framed Color Box",
          "scrollbar:Scrollbar","listbox:Listbox","listbox:Multicolumn Listbox",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type").startswith("Num") and dcoFlatTypeID == n1FlatTypeID:
        # These use two TDs, both pointing at the same flat Number TD.
        if True:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [], 'extraTypeID': None, 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("stdString:String",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "String" and dcoFlatTypeID == n1FlatTypeID:
        # These use two TDs, both pointing at the same flat index of String TD.
        if True:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [], 'extraTypeID': None, 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("stdPict:2D Picture","stdPict:Distribution Plot", \
          "stdPict:Min-Max Plot","stdPict:Polar Plot","stdPict:Radar Plot","stdPict:Smith Plot",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "Picture" and dcoFlatTypeID == n1FlatTypeID:
        # These use two TDs, both pointing at the same flat index of Picture TD.
        if True:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [], 'extraTypeID': None, 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("digitalTable:Digital Data",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "MeasureData" and dcoFlatTypeID == n1FlatTypeID:
        # These use two TDs, both pointing at the same flat index of Tag TD.
        if True:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [], 'extraTypeID': None, 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("stdRing:Font Enum.ctl",)]
    if len(dcoClass) > 0 and dcoTypeDesc.get("Type") == n1TypeDesc.get("Type") and dcoFlatTypeID == n1FlatTypeID:
        # These use two Unit TDs; both Unit TDs are pointing at the same flat index of UnitUInt TD.
        if True:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [], 'extraTypeID': None, 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("stdTag:Traditional DAQ Channel","stdTag:DAQmx Scale Name", \
          "stdTag:DAQmx Device Name","stdTag:DAQmx Terminal","stdTag:DAQmx Physical Channel","stdTag:DAQmx Switch",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "Tag" and dcoFlatTypeID == n1FlatTypeID:
        # These use two TDs, both pointing at the same flat index of Tag TD.
        if True:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [], 'extraTypeID': None, 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("stdCont:plat-PictureBox.ctl","stdCont:plat-RichTextBox.ctl","stdCont:.NET Container",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "Refnum" and dcoFlatTypeID == n1FlatTypeID:
        # These use two TDs, both pointing at the same flat index of Refnum TD.
        # Existence of Containers in the VI can be determined by existence of VINS block with multiple entries.
        if True:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [], 'extraTypeID': None, 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("stdCont:ActiveX Container", \
          "stdCont:plat-Microsoft Web Browser.ctl","stdCont:plat-Microsoft Web Browser.ctl", \
          "stdCont:plat-Windows Media Player.ctl","stdCont:TestStand UI Application Manager.ctl", \
          "stdCont:TestStand UI Button Control.ctl","stdCont:TestStand UI CheckBox Control.ctl", \
          "stdCont:TestStand UI ComboBox Control.ctl","stdCont:TestStand UI ExecutionView Manager.ctl", \
          "stdCont:TestStand UI ExpressionEdit Control.ctl","stdCont:TestStand UI InsertionPalette Control.ctl", \
          "stdCont:TestStand UI Label Control.ctl","stdCont:TestStand UI ListBar Control.ctl", \
          "stdCont:TestStand UI ListBox Control.ctl","stdCont:TestStand UI ReportView Control.ctl", \
          "stdCont:TestStand UI SequenceFileView Manager.ctl","stdCont:TestStand UI SequenceView Control.ctl", \
          "stdCont:TestStand UI StatusBar Control.ctl","stdCont:TestStand UI VariablesView Control.ctl", \
          "stdCont:TestStand UI Unknown Control.ctl",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "Refnum" and dcoFlatTypeID == n1FlatTypeID:
        # These use two TDs, both pointing at the same flat index of Refnum TD.
        # Existence of Containers in the VI can be determined by existence of VINS block with multiple entries.
        if True:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [], 'extraTypeID': None, 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("scenegraphdisplay:3D Picture",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "Refnum" and dcoFlatTypeID == n1FlatTypeID:
        # These use two TDs, both pointing at the same flat index of Refnum TD.
        if True:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [], 'extraTypeID': None, 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("stdRefNum:Control Refnum","stdRefNum:VI Refnum","stdRefNum:Application Refnum",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "Refnum" and dcoFlatTypeID == n1FlatTypeID:
        # These use two TDs, both pointing at the same flat index of Refnum TD.
        if True:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [], 'extraTypeID': None, 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("udClassDDO:LabVIEW Object",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "Refnum" and dcoFlatTypeID == n1FlatTypeID:
        # Controls from Variant and Class category: LvObject
        # These use two TDs, both pointing at the same flat index of Refnum TD.
        if True:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [], 'extraTypeID': None, 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("stdRefNum:IMAQ Session","stdRefNum:Automation Refnum", \
          "stdRefNum:Bluetooth Network Connection Refnum","stdRefNum:Byte Stream File Refnum", \
          "stdRefNum:Data Log File Refnum","stdRefNum:DataSocket Refnum","stdRefNum:.NET Refnum", \
          "stdRefNum:Event Callback Refnum","stdRefNum:IrDA Network Connection Refnum", \
          "stdRefNum:Menu Refnum","stdRefNum:Occurrence Refnum","stdRefNum:TCP Network Connection Refnum", \
          "stdRefNum:UDP Network Connection Refnum",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "Refnum" and dcoFlatTypeID == n1FlatTypeID:
        # Controls from I/O category: IMAQ Session
        # Controls from Refnum category: App Refnum, Automation Refnum, Bluetooth Refnum, Byte Stream Refnum,
        #   Ctl Refnum, Data Log Refnum, DataSocket Refnum, dotNET Refnum, Event Callback, Irda Network,
        #   Menu Refnum, Occurrence Refnum, TCP Network, UDP Network, VI Refnum
        # These use two TDs, both pointing at the same flat index of Refnum TD.
        if True:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [], 'extraTypeID': None, 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("stdLvVariant:Variant",)]
    if len(dcoClass) > 0 and n1TypeDesc.get("Type") == "LVVariant" and dcoFlatTypeID == n1FlatTypeID:
        # Controls from Variant and Class category: LVVariant
        # These use two TDs, both pointing at the same flat index of LVVariant TD.
        if True:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [], 'extraTypeID': None, 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    dcoClass = [itm for itm in matchingClasses if itm in ("grouper:Sub Panel",)]
    if len(dcoClass) > 0:
        # Controls from Containers category, FP parts: Sub Panel
        # These use one FP TD, of Refnum type.
        # These controls have FP TypeIDs and BD TypeIDs - this will match the FP part only.
        # We're using only one TD entry here, but we've requested 2 - that's not an issue, since this DCO enforces a lot of following BD heap TDs
        if True:
            dcoProps = dcoClass[0].split(':',2)
            DCOInfo = { 'fpClass': dcoProps[0], 'dcoName': dcoProps[1], 'dcoTypeID': 0, 'partTypeIDs': [], 'extraTypeID': None, 'ddoTypeID': 0, 'subTypeIDs': [] }
            return 1, DCOInfo

    #TODO recognize BD part of Sub Panel (maybe separate function for BD recognition?)
    #TODO recognize splitter - not from TDs, but it should be recognizable.
    # No control recognized
    return 0, None


def DTHP_TypeDesc_matching_ranges(RSRC, fo, po, VCTP_TypeDescList=None, VCTP_FlatTypeDescList=None):
    """ Finds possible ranges of TypeDescs for DTHP
    """
    # DTHP must not include TypeDesc values used by other sections
    heapRanges = TypeDesc_find_unused_ranges(RSRC, fo, po, skipRm=["TM80","DTHP"], \
          VCTP_TypeDescList=VCTP_TypeDescList, VCTP_FlatTypeDescList=VCTP_TypeDescList)
    if True:
        # We need TM80 to convert TMIs into TypeIDs
        TM80_IndexShift = None
        TM80 = RSRC.find("./TM80/Section")
        if TM80 is not None:
            TM80_IndexShift = TM80.get("IndexShift")
            if TM80_IndexShift is not None:
                TM80_IndexShift = int(TM80_IndexShift, 0)
    if True:
        # DTHP range is always above TM80 IndexShift
        # This is not directly enforced in code, but before Heap TypeDescs
        # there are always TypeDescs which store options, and those are
        # filled with DFDS, meaning they have to be included in TM80 range
        heapRanges = intRangesExcludeBelow(heapRanges, TM80_IndexShift)
        if (po.verbose > 2):
            print("{:s}: After TM80 IndexShift exclusion, heap TD ranges: {}"\
                .format(po.xml,heapRanges))
    if True:
        # DTHP IndexShift must be high enough to not include TypeDesc from CONP
        # Since CONP type is created with new VIs it is always before any heap TDs
        # The same does not apply to CPC2 - that type is created when first connector
        # from pane is assigned; so it's sometimes placed before, sometimes after heap TDs
        CONP_TypeID = None
        CONP_TypeDesc = RSRC.find("./CONP/Section/TypeDesc")
        if CONP_TypeDesc is not None:
            CONP_TypeID = CONP_TypeDesc.get("TypeID")
            if CONP_TypeID is not None:
                CONP_TypeID = int(CONP_TypeID, 0)
        heapRanges = intRangesExcludeBelow(heapRanges, CONP_TypeID)
        if (po.verbose > 2):
            print("{:s}: After CONP exclusion, heap TD ranges: {}"\
                .format(po.xml,heapRanges))
    if True:
        # DTHP must not include TypeDesc of type "Function"
        # IndexShift must be high enough or count must be small enough to keep
        # Function TDs outside.
        nonHeapTypes = []
        for TDTopMap in VCTP_TypeDescList:
            TypeDesc, TDTopMap_Index, FlatTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, TDTopMap, po)
            if TypeDesc is None: continue
            if TypeDesc.get("Type") == "Function":
                # Function type can only be part of heap types if its FlatTypeID is used two times
                # in the file, and the other use is not a heap type.
                for otherTDTopMap in VCTP_TypeDescList:
                    otherTypeDesc, otherTDTopMap_Index, otherFlatTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, otherTDTopMap, po)
                    # Let's assume the second use of the same Function type can be in heap types
                    # So only if we are on first use of that flat type, disallow it s use in heap
                    if otherFlatTypeID == FlatTypeID:
                        if otherTDTopMap_Index == TDTopMap_Index:
                            nonHeapTypes.append(TDTopMap_Index)
                        break
            #TODO check if other types should be removed from heap
        for TypeDesc_Index in nonHeapTypes:
            heapRanges = intRangesExcludeOne(heapRanges, TypeDesc_Index)
        if (po.verbose > 2):
            print("{:s}: After Type based exclusion, heap TD ranges: {}"\
                .format(po.xml,heapRanges))
    # DTHP must match the two-per-TD layout (with proper exceptions)
    # Valid ranges contain ref to the same type twice for each DCO, single types are only used after Cluster
    # (and they must match the fields within cluster)
    heapRangesProper = []
    for rng in heapRanges:
        properMin = None
        properMax = None
        typeID = rng.min
        # Recognize one DCO for each move through this loop (proper DCO requires two or more typeID values; so increment varies)
        while typeID < rng.max: # rng.max is a proper value, but can't be start of DCO - at least two types make a DCO
            tdCount, DCOInfo = DCO_recognize_from_typeIDs(RSRC, fo, po, typeID, rng.max, VCTP_TypeDescList, VCTP_FlatTypeDescList)
            if DCOInfo is not None:
                # Got a proper types list for DCO
                if properMin is None:
                    properMin = typeID
                properMax = typeID + tdCount - 1 # Max value in our ranges is the last included index
                typeID += tdCount
            else:
                # No control recognized - store the previous range and search for next valid range
                if (po.verbose > 2):
                    print("{:s}: TypeID {} not viable for heap after checking subsequent types"\
                      .format(po.xml,typeID))
                if properMax is not None:
                    rng = SimpleNamespace(min=properMin,max=properMax)
                    heapRangesProper.append(rng)
                properMin = None
                properMax = None
                typeID += 1
        # Store the last proper range, in case loop ended before it had the chance of being saved
        if properMax is not None:
            rng = SimpleNamespace(min=properMin,max=properMax)
            heapRangesProper.append(rng)
    heapRanges = heapRangesProper
    return heapRanges

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
    VCTP = RSRC.find("./VCTP/Section")
    VCTP_TypeDescList = []
    VCTP_FlatTypeDescList = None
    if VCTP is not None:
        VCTP_TypeDescList = VCTP.findall("TopLevel/TypeDesc")
        VCTP_FlatTypeDescList = VCTP.findall("TypeDesc")
    heapRanges = DTHP_TypeDesc_matching_ranges(RSRC, fo, po, \
          VCTP_TypeDescList=VCTP_TypeDescList, \
          VCTP_FlatTypeDescList=VCTP_FlatTypeDescList)
    dcoDfDataTypesMap = getDCOMappingForIntField(RSRC, 'defaultDataTMI', po)
    dcoExDataTypesMap = getDCOMappingForIntField(RSRC, 'extraDataTMI', po)
    minIndexShift = 0
    maxTdCount = 0
    if (po.verbose > 1):
        print("{:s}: Possible heap TD ranges: {}"\
            .format(po.xml,heapRanges))
    for rng in heapRanges:
        if rng.max - rng.min + 1 <= maxTdCount:
            continue
        minIndexShift = rng.min
        maxTdCount = rng.max - rng.min + 1
    if maxTdCount <= 0 and len(dcoDfDataTypesMap) > 0:
        # if range is empty but we have dcoDfDataTypesMap, then we can create new types for DTHP
        if (po.verbose > 1):
            print("{:s}: No TypeDesc entries found for DTHP; need to re-create the entries"\
                .format(po.xml))
        minIndexShift = getMaxIndexFromList(VCTP_TypeDescList, fo, po) + 1
        maxIndexShift = minIndexShift
        # Flat types in dco*DataTypesMap should be used to re-create VCTP entries needed for DTHP
        VCTP_TopLevel = VCTP.find("TopLevel")
        for dcoIndex, dcoTypeID in reversed(dcoDfDataTypesMap.items()):
            dcoTypeDesc, dcoFlatTypeID = \
                  getTypeDescFromIDUsingLists(VCTP_TypeDescList, VCTP_FlatTypeDescList, dcoTypeID, po)
            dcoExTypeDesc, dcoFlatExTypeID = \
                  getTypeDescFromIDUsingLists(VCTP_TypeDescList, VCTP_FlatTypeDescList, dcoExDataTypesMap[dcoIndex], po)
            if (po.verbose > 1):
                print("{:s}: Re-creating DTHP entries for DCO{} using FlatTypeID {} Type {}"\
                    .format(po.xml,dcoIndex,dcoFlatTypeID,dcoTypeDesc.get("Type")))
            maxIndexShift += DCO_create_VCTP_heap_entries(RSRC, fo, po, dcoIndex, dcoTypeDesc, dcoFlatTypeID, \
                dcoExTypeDesc, dcoFlatExTypeID, VCTP, VCTP_TopLevel, maxIndexShift)
            # We might have added entries to VCTP - update the lists
            VCTP_TypeDescList = VCTP.findall("TopLevel/TypeDesc")
            VCTP_FlatTypeDescList = VCTP.findall("TypeDesc")
        maxTdCount = maxIndexShift - minIndexShift
    elif maxTdCount <= 0:
        if (po.verbose > 1):
            print("{:s}: No TypeDesc entries found for DTHP, and no DCO TDs to re-create them"\
                .format(po.xml))
        pass
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
    #TODO CONP can be re-created from DSInit
    return fo[FUNC_OPTS.changed]

def CPC2_TypeDesc_matching_ranges(RSRC, fo, po, VCTP_TypeDescList=None, VCTP_FlatTypeDescList=None):
    """ Finds possible ranges of TypeDesc for CPC2
    """
    # DTHP must not include TypeDesc values used by other sections
    conpc2Ranges = TypeDesc_find_unused_ranges(RSRC, fo, po, skipRm=["TM80","CPC2"], \
          VCTP_TypeDescList=VCTP_TypeDescList, VCTP_FlatTypeDescList=VCTP_TypeDescList)
    if True:
        # CPC2 TypeDesc type is "Function"
        nonFuncTypes = []
        for TDTopMap in VCTP_TypeDescList:
            TypeDesc, TDTopMap_Index, FlatTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, TDTopMap, po)
            if TypeDesc is None: continue
            if TypeDesc.get("Type") != "Function":
                nonFuncTypes.append(TDTopMap_Index)
        for TypeDesc_Index in nonFuncTypes:
            conpc2Ranges = intRangesExcludeOne(conpc2Ranges, TypeDesc_Index)
        if (po.verbose > 2):
            print("{:s}: After Type based exclusion, CPC2 TD ranges: {}"\
                .format(po.xml,conpc2Ranges))
    return conpc2Ranges

def CPC2_Fix(RSRC, CPC2, ver, fo, po):
    typeDescMap = CPC2.find("./TypeDesc")
    if typeDescMap is None:
        typeDescMap = ET.SubElement(CPC2, "TypeDesc")
        fo[FUNC_OPTS.changed] = True
    CPC2_typeID = typeDescMap.get("TypeID")
    if CPC2_typeID is not None:
        CPC2_typeID = int(CPC2_typeID, 0)
    # We have current value, now compute proper one
    VCTP = RSRC.find("./VCTP/Section")
    VCTP_TypeDescList = []
    VCTP_FlatTypeDescList = None
    if VCTP is not None:
        VCTP_TypeDescList = VCTP.findall("./TopLevel/TypeDesc")
        VCTP_FlatTypeDescList = VCTP.findall("./TypeDesc")
    conpc2Ranges = CPC2_TypeDesc_matching_ranges(RSRC, fo, po, \
          VCTP_TypeDescList=VCTP_TypeDescList, \
          VCTP_FlatTypeDescList=VCTP_FlatTypeDescList)
    if (po.verbose > 1):
        print("{:s}: Possible CPC2 TD ranges: {}"\
            .format(po.xml,conpc2Ranges))
    proper_typeID = None
    # Check if current value is within the vaid range
    if CPC2_typeID is not None:
        for rng in conpc2Ranges:
            if rng.min >= CPC2_typeID and rng.max <= CPC2_typeID:
                proper_typeID = CPC2_typeID
                break
    # If it's not, use the last matching type
    if proper_typeID is None and len(conpc2Ranges) > 0:
        rng = conpc2Ranges[-1]
        proper_typeID = rng.max
    # If no valid TDs in our ranges, re-create the TypeDesc
    if proper_typeID is None:
        # if range is empty but we have connector list, make the new TypeDesc based on that
        if (po.verbose > 1):
            print("{:s}: No TypeDesc entry found for CPC2; need to re-create from connectors list"\
                .format(po.xml))
        CONP_TypeDesc = None
        CONP_TypeDescMap = RSRC.find("./CONP/Section/TypeDesc")
        if CONP_TypeDescMap is not None:
            CONP_TypeID = CONP_TypeDescMap.get("TypeID")
            if CONP_TypeID is not None:
                CONP_TypeID = int(CONP_TypeID, 0)
            if CONP_TypeID is not None:
                CONP_TypeDesc = getConsolidatedTopType(RSRC, CONP_TypeID, po)
        if CONP_TypeDesc is not None:
            CONP_TDMapList = CONP_TypeDesc.findall("./TypeDesc")
        else:
            # At this point, CONP should have been re-created already
            if (po.verbose > 1):
                print("{:s}: CONP TypeDesc not found, creating empty list of connectors"\
                    .format(po.xml))
            CONP_TDMapList = []
        # Create the flat type for CPC2
        TypeDesc_elem = ET.Element("TypeDesc")
        TypeDesc_elem.set("Type","Function")
        TypeDesc_elem.set("FuncFlags","0x0")
        CONP_TypeDesc_Pattern = None
        CONP_TypeDesc_HasThrall = None
        if CONP_TypeDescMap is not None:
            CONP_TypeDesc_Pattern = CONP_TypeDescMap.get("Pattern")
            CONP_TypeDesc_HasThrall = CONP_TypeDescMap.get("HasThrall")
        if CONP_TypeDesc_Pattern is None:
            CONP_TypeDesc_Pattern = "0x8"
        if CONP_TypeDesc_HasThrall is None:
            CONP_TypeDesc_HasThrall = "0"
        TypeDesc_elem.set("Pattern", CONP_TypeDesc_Pattern)
        TypeDesc_elem.set("HasThrall",CONP_TypeDesc_HasThrall)
        TypeDesc_elem.set("Format","inline")
        # flatTypeID and flatPos will usually be the same, but just in case there's
        # a mess in tags within VCTP, let's treat them as separate values
        proper_flatTypeID = len(VCTP_FlatTypeDescList)
        proper_flatPos = list(VCTP).index(VCTP_FlatTypeDescList[-1]) + 1
        VCTP.insert(proper_flatPos,TypeDesc_elem)
        fo[FUNC_OPTS.changed] = True
        for TDFlatMap in CONP_TDMapList:
            FlatTypeID = TDFlatMap.get("TypeID") # For map entries within Function TD
            assert(FlatTypeID is not None) # this should've been re-created with CONP
            FlatTypeID = int(FlatTypeID, 0)
            FlatTDFlags = TDFlatMap.get("Flags") # For map entries within Function TD
            assert(FlatTDFlags is not None) # this should've been re-created with CONP
            FlatTDFlags = int(FlatTDFlags, 0)
            elem = ET.SubElement(TypeDesc_elem, "TypeDesc")
            elem.set("TypeID","{:d}".format(FlatTypeID))
            elem.set("Flags","0x{:04x}".format(FlatTDFlags & ~0x0401)) # checked on one example only
        # Now add a top type which references our new flat type
        VCTP_TopLevel = VCTP.find("./TopLevel")
        proper_typeID = getMaxIndexFromList(VCTP_TypeDescList, fo, po) + 1
        elem = ET.SubElement(VCTP_TopLevel, "TypeDesc")
        elem.set("Index","{:d}".format(proper_typeID))
        elem.set("FlatTypeID","{:d}".format(proper_flatTypeID))
    if CPC2_typeID != proper_typeID:
        if (po.verbose > 0):
            print("{:s}: Changing 'CPC2/TypeDesc' TypeID to {}"\
                .format(po.xml,proper_typeID))
        typeDescMap.set("TypeID","{}".format(proper_typeID))
        fo[FUNC_OPTS.changed] = True
    return fo[FUNC_OPTS.changed]

def BDHb_Fix(RSRC, BDHP, ver, fo, po):
    block_name = "BDHb"

    attribGetOrSetDefault(BDHP, "Index", 0, fo, po)
    sect_format = BDHP.get("Format")
    if sect_format not in ("xml",):
        BDHP.set("Format","xml")
        if len(RSRC.findall("./"+block_name+"/Section")) <= 1:
            snum_str = ""
        else:
            if sect_index >= 0:
                snum_str = str(sect_index)
            else:
                snum_str = 'm' + str(-sect_index)
        fname_base = "{:s}_{:s}{:s}".format(po.filebase, block_name, snum_str)
        BDHP.set("File","{:s}.xml".format(fname_base))
        fo[FUNC_OPTS.changed] = True

    rootObject = elemFindOrCreate(BDHP, "SL__rootObject", fo, po)
    attribGetOrSetDefault(rootObject, "class", "oHExt", fo, po)
    attribGetOrSetDefault(rootObject, "uid", 1, fo, po)

    root = elemFindOrCreate(rootObject, "root", fo, po)
    attribGetOrSetDefault(root, "class", "diag", fo, po)
    attribGetOrSetDefault(root, "uid", 1, fo, po)

    pBounds = elemFindOrCreate(rootObject, "pBounds", fo, po)
    elemTextGetOrSetDefault(pBounds, [46,0,681,1093], fo, po)
    dBounds = elemFindOrCreate(rootObject, "dBounds", fo, po)
    elemTextGetOrSetDefault(dBounds, [0,0,0,0], fo, po)

    origin = elemFindOrCreate(rootObject, "origin", fo, po)
    elemTextGetOrSetDefault(origin, [327,105], fo, po)

    instrStyle = elemFindOrCreate(rootObject, "instrStyle", fo, po)
    elemTextGetOrSetDefault(instrStyle, 31, fo, po)

    # Now content of the 'root' element

    root_zPlaneList, root_nodeList_termList, root_signalList = elemCheckOrCreate_bdroot_content( \
          root, fo, po, aeObjFlags=16384, hasPlanes=True, hasNodes=True, hasSignals=True, \
          aeBgColor=0x00FFFFFF, aeFirstNodeIdx=1, \
          aeBounds=[0,0,0,0], aeShortCount=1, aeClumpNum=0x020003)

    return fo[FUNC_OPTS.changed]


def icl8_genDefaultIcon(title, po):
    """ Generates default icon image for VI file
    """
    imageHex = \
    "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff" +\
    "ff000000000000000000000000000000000000000000000000000000000000ff" +\
    "ff000000000000000000000000000000000000000000000000000000000000ff" +\
    "ff0000ffffffffffffffffffffffffffffffffffffff000000000000000000ff" +\
    "ff0000fffafafafafafafafafafafafaf8fa2cfa2cff000000000000000000ff" +\
    "ff0000fffafffffffffffffffffffffff8fa2cfa2cff000000000000000000ff" +\
    "ff0000fffaffd1c5d1ffffffd1c5d1fff8fc2bfc2cff000000000000000000ff" +\
    "ff0000fffaffc5ffc5ffffffc5ffc5fff82c2c2c2cff000000000000000000ff" +\
    "ff0000fffad1c5ffc5d1ffd1c5ffc5d1f82bfc2b2cff000000000000000000ff" +\
    "ff0000fffac5d1ffd1c5ffc5d1ffd1c5f8fc08fc2cff000000000000000000ff" +\
    "ff0000fffac5ffffffc5ffc5ffffffc5f8fc08fc2cff000000000000000000ff" +\
    "ff0000fffaffffffffd1c5d1fffffffff82bfc2b2cff000000000000000000ff" +\
    "ff0000fffafffffffffffffffffffffff82c2c2c2cff000000000000000000ff" +\
    "ff0000fff8f8f8f8f8f8f8f8f8f8f8f8f82c2c8383ff000000000000000000ff" +\
    "ff0000ff2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c830583830000000000000000ff" +\
    "ff0000ff2cfc2c2c2c2c2cfc2c2c2c2c232323830505058383000000000000ff" +\
    "ff0000fffcd5fc2c2c2cfc23fc2c23232c2c2c830505ff0505838300000000ff" +\
    "ff0000ff2cd42c2c2c2c232c2c232c2c2c2c2c8305ffffff05050583232300ff" +\
    "ff0000ffffd5ffffff23ffff23ffffffffffff830505ff0505838300000000ff" +\
    "ff00000000d4000000230000230000d5d4d4d5830505058383000000000000ff" +\
    "ff0000000000d500000023230000d400000000830583830000000000000000ff" +\
    "ff000000000000d4d400000000d50000000000838300000000000000000000ff" +\
    "ff0000000000000000d5d4d5d4000000000000000000000000000000000000ff" +\
    "ff000000000000000000000000000000000000000000000000000000000000ff"*8 +\
    "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    from PIL import ImageFont, ImageDraw
    image = Image.new("P", (32, 32))
    if True:
        from LVmisc import LABVIEW_COLOR_PALETTE_256
        img_palette = [ 0 ] * (3*256)
        lv_color_palette = LABVIEW_COLOR_PALETTE_256
        for i, rgb in enumerate(lv_color_palette):
            img_palette[3*i+0] = (rgb >> 16) & 0xFF
            img_palette[3*i+1] = (rgb >>  8) & 0xFF
            img_palette[3*i+2] = (rgb >>  0) & 0xFF
        image.putpalette(img_palette, rawmode='RGB')
    img_data = bytes.fromhex(imageHex)
    image.putdata(img_data)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load(os.path.join(sys.path[0], 'assets', 'tom-thumb.pil'))
    short_title = title
    if len(short_title) > 7:
        short_title = re.sub('[^A-Za-z0-9{}=-]', '', short_title)[:7]
    draw.text((2,24), short_title, font=font, fill=(0xff))
    return image

def icon_changePalette(RSRC, src_image, bpp, fo, po):
    from LVmisc import LABVIEW_COLOR_PALETTE_256, LABVIEW_COLOR_PALETTE_16, LABVIEW_COLOR_PALETTE_2
    img_palette = [ 0 ] * (3*(2**bpp))
    if bpp == 8:
        lv_color_palette = LABVIEW_COLOR_PALETTE_256
    elif bpp == 4:
        lv_color_palette = LABVIEW_COLOR_PALETTE_16
    else:
        lv_color_palette = LABVIEW_COLOR_PALETTE_2
    for i, rgb in enumerate(lv_color_palette):
        img_palette[3*i+0] = (rgb >> 16) & 0xFF
        img_palette[3*i+1] = (rgb >>  8) & 0xFF
        img_palette[3*i+2] = (rgb >>  0) & 0xFF
    palimage = Image.new('P', (2, 2))
    palimage.putpalette(img_palette, rawmode='RGB')
    rgb_image = src_image.convert('RGB')
    dst_image = rgb_image.quantize(colors=len(lv_color_palette), palette=palimage)
    return dst_image

def icon_readImage(RSRC, icon_elem, fo, po):
    """ Reads icon image from section
    """
    icon_Format = icon_elem.get("Format")
    icon_File = icon_elem.get("File")
    xml_path = os.path.dirname(po.xml)
    icon_fname = None
    if icon_File is not None:
        if len(xml_path) > 0:
            icon_fname = xml_path + '/' + icon_File
        else:
            icon_fname = icon_File
    image = None
    fileOk = (icon_fname is not None) and os.access(icon_fname, os.R_OK)
    if icon_Format == "png" and fileOk:
        # As long as the file loads, we're good
        try:
            image = Image.open(icon_fname)
            image.getdata() # to make sure the file gets loaded; everything is lazy nowadays
        except:
            fileOk = False
            image = None
    return image, icon_fname, fileOk

def icl8_Fix(RSRC, icl8, ver, fo, po):
    icl8_Format = icl8.get("Format")
    icl8_File = icl8.get("File")
    image, icl8_fname, fileOk = icon_readImage(RSRC, icl8, fo, po)
    if image is not None and fileOk:
        # If we were abe to read the image, section is OK
        return fo[FUNC_OPTS.changed]
    if icl8_Format == "bin" and fileOk:
        # Just accept that; no real need to verify BIN file
        return fo[FUNC_OPTS.changed]
    # So the section is bad; we will re-create the icon
    icl8_Format = "png"
    icl8_baseName = os.path.splitext(os.path.basename(po.xml))[0]
    icl8_File = icl8_baseName+"_icl8.png"
    if True:
        xml_path = os.path.dirname(po.xml)
        if len(xml_path) > 0:
            icl8_fname = xml_path + '/' + icl8_File
        else:
            icl8_fname = icl8_File
    if image is None:
        icl4 = RSRC.find("./icl4/Section")
        if icl4 is not None:
            image, icl4_fname, fileOk = icon_readImage(RSRC, icl4, fo, po)
        if image is not None:
            image = icon_changePalette(RSRC, image, 8, fo, po)
    if image is None:
        ICON = RSRC.find("./ICON/Section")
        if ICON is not None:
            image, ICON_fname, fileOk = icon_readImage(RSRC, ICON, fo, po)
        if image is not None:
            image = icon_changePalette(RSRC, image, 8, fo, po)
    if image is None:
        image = icl8_genDefaultIcon(icl8_baseName, po)
    image.save(icl8_fname, format="PNG")
    icl8.set("Format", icl8_Format)
    icl8.set("File", icl8_File)
    fo[FUNC_OPTS.changed] = True
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

CPC2_SectionDef = [
 ["CPC2",	9,0,0,	CPC2_Fix], # does not exist in in LV7.1, found for LV9.0 - LV14.0
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

icl8_SectionDef = [
 ["icl8",	5,0,0,	icl8_Fix], # existed at least from LV6.0
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

def getOrMakeSection(section_def, RSRC, ver, po, allowCreate=True):
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
    if (not allowCreate) and (sec_d[0] not in po.force_recover_section):
        if (po.verbose > 0):
            print("{:s}: No sections found for block <{}>, not creating"\
              .format(po.xml,sec_d[0]))
        return None
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
    for xpath in ("./SL__rootObject/root/ddoList/SL__arrayElement", \
          ".//SL__arrayElement/ddo/ddoList/SL__arrayElement", \
          "./SL__rootObject/root/conPane/cons/SL__arrayElement/ConnectionDCO",):
        not_unique_elems.extend(FPHP.findall(xpath))
    for xpath in ("./SL__rootObject/root/zPlaneList/SL__arrayElement", \
          "./SL__rootObject/root/nodeList/SL__arrayElement/termList/SL__arrayElement/dco",):
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
    # Refilling of ddoList - it should have entries for all DDOs
    # There is one root ddoList, and controls which are containers for other controls also have their nested lists
    # For the root, we will still use findall() to support the case where there is no such path
    allDDOsWithLists = []
    allDDOsWithLists.extend( FPHP.findall("./SL__rootObject/root/ddoList/..") )
    allDDOsWithLists.extend( FPHP.findall(".//SL__arrayElement/ddo/ddoList/..") )
    for ddo in allDDOsWithLists:
        zPlaneList_elems = ddo.findall("./paneHierarchy/zPlaneList/SL__arrayElement[@class][@uid]")
        ddoList = ddo.find("./ddoList")
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
    zPlaneList_elems = FPHP.findall("./SL__rootObject/root/paneHierarchy/zPlaneList/SL__arrayElement[@class='fPDCO'][@uid]")
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

    CPC2 = getOrMakeSection(CPC2_SectionDef, RSRC, ver, po)
    fixSection(CPC2_SectionDef, RSRC, CPC2, ver, po)

    DTHP = getOrMakeSection(DTHP_SectionDef, RSRC, ver, po)
    fixSection(DTHP_SectionDef, RSRC, DTHP, ver, po)

    FPHP = getOrMakeSection(FPHP_SectionDef, RSRC, ver, po)
    fixSection(FPHP_SectionDef, RSRC, FPHP, ver, po)

    BDHP = getOrMakeSection(BDHP_SectionDef, RSRC, ver, po, allowCreate=False)
    if BDHP is not None:
        fixSection(BDHP_SectionDef, RSRC, BDHP, ver, po)

    LIvi = getOrMakeSection(LIvi_SectionDef, RSRC, ver, po)
    fixSection(LIvi_SectionDef, RSRC, LIvi, ver, po)

    LIfp = getOrMakeSection(LIfp_SectionDef, RSRC, ver, po)
    fixSection(LIfp_SectionDef, RSRC, LIfp, ver, po)

    LIbd = getOrMakeSection(LIbd_SectionDef, RSRC, ver, po, allowCreate=False)
    if LIbd is not None:
        fixSection(LIbd_SectionDef, RSRC, LIbd, ver, po)

    DSTM = getOrMakeSection(DSTM_SectionDef, RSRC, ver, po)
    fixSection(DSTM_SectionDef, RSRC, DSTM, ver, po)

    DFDS = getOrMakeSection(DFDS_SectionDef, RSRC, ver, po)
    fixSection(DFDS_SectionDef, RSRC, DFDS, ver, po)

    BDPW = getOrMakeSection(BDPW_SectionDef, RSRC, ver, po)
    fixSection(BDPW_SectionDef, RSRC, BDPW, ver, po)

    icl8 = getOrMakeSection(icl8_SectionDef, RSRC, ver, po)
    fixSection(icl8_SectionDef, RSRC, icl8, ver, po)

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

    parser.add_argument('--force-recover-section', action='append', type=str,
            help="name a section to force re-create even if this may produce damaged file")

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

    if po.force_recover_section is None:
        po.force_recover_section = []

    if po.drop_section is None:
        po.drop_section = []

    if po.fix:

        if (po.verbose > 0):
            print("{}: Starting XML file parse for RSRC fix".format(po.xml))
        tree = ET.parse(po.xml, parser=ET.XMLParser(target=ET.CommentedTreeBuilder()))
        root = tree.getroot()
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

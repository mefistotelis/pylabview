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

def representsList(s):
    """ Checks if given string represents a comma separated list in brackets.
    """
    try: 
        list_str = s.trim()
    except AttributeError:
        return False
    if list_str[0] != '(' or list_str[-1] != ')':
        return False
    list_str = list_str[1:-1].split(',')
    # We only need lists of integers
    for i in range(len(list_str)): 
        list_str[i] = int(list_str[i].trim(), 0)
    return True

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
    DSI_candidates = DFDS.findall('./RepeatedBlock/I32/..')
    for DSInit in DSI_candidates:
        if len(DSInit.findall('./I32')) == 51:
            return DSInit
    # No matching type in DFDS
    return None

def getDSInitEntry(RSRC, entryId, po):
    """ Returns DSInit entry value.
    """
    DSInit = getDSInitRecord(RSRC, po)
    if DSInit is None:
        return None
    entry_elem = DSInit.find("./I32["+str(int(entryId+1))+"]")
    if entry_elem is None:
        return None
    return int(entry_elem.text,0)

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

def elemCheckOrCreate_zPlaneList_arrayElement(parent, fo, po, aeClass="fPDCO", \
          aeTypeID=1, aeObjFlags=None, aeDdoClass="stdBool", aeConNum=None, \
          aeTermListLength=None, aeDdoObjFlags=None, \
          aeBounds=None, aeDdoTypeID=None, aeMinButSize=None):

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

    if aeConNum is not None:
        conNum = elemFindOrCreate(arrayElement, "conNum", fo, po)
        elemTextGetOrSetDefault(conNum, aeConNum, fo, po)

    if aeTermListLength is not None:
        termListLength = elemFindOrCreate(arrayElement, "termListLength", fo, po)
        elemTextGetOrSetDefault(termListLength, aeTermListLength, fo, po)

    # Now content of 'arrayElement/ddo'

    if aeDdoObjFlags is not None:
        ddo_objFlags = elemFindOrCreate(ddo, "objFlags", fo, po, pos=0)
        elemTextGetOrSetDefault(ddo_objFlags, aeDdoObjFlags, fo, po)

    if aeBounds is not None:
        ddo_bounds = elemFindOrCreate(ddo, "bounds", fo, po)
        elemTextGetOrSetDefault(ddo_bounds, aeBounds, fo, po)

    partsList = elemFindOrCreate(ddo, "partsList", fo, po)
    attribGetOrSetDefault(partsList, "elements", 0, fo, po)

    ddo_TypeDesc = elemFindOrCreate(ddo, "typeDesc", fo, po)
    elemTextGetOrSetDefault(ddo_TypeDesc, "TypeID({})".format(aeDdoTypeID), fo, po)

    ddo_MouseWheelSupport = elemFindOrCreate(ddo, "MouseWheelSupport", fo, po)
    elemTextGetOrSetDefault(ddo_MouseWheelSupport, 0, fo, po)

    if aeMinButSize is not None:
        ddo_MinButSize = elemFindOrCreate(ddo, "MinButSize", fo, po)
        elemTextGetOrSetDefault(ddo_MinButSize, aeMinButSize, fo, po)

    return arrayElement, partsList

def recountHeapElements(RSRC, Heap, ver, fo, po):
    """ Updates 'elements' attributes in the Heap tree
    """
    elems = Heap.findall(".//*[@elements]")
    # The 'cons' tag does not store amount of elements inside
    cons_elem = Heap.find(".//conPane/cons")
    if cons_elem is not None:
        count = None
        if cons_elem in elems: elems.remove(cons_elem)
        # Get the value from connectors
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
            count = getDSInitEntry(RSRC, DSINIT.NConnectorPorts, po)
            if count is not None:
                if count >= 1 and count <= 28:
                    if (po.verbose > 1):
                        print("{:s}: Getting connector ports count for \"conPane/cons\" from DSInit Record".format(po.xml))
                else:
                        count = None
        count_str = None
        if count is not None:
            # Terminal patterns nly allow specific amounts of connectors
            if count > 12 and count < 16: count = 16
            if count > 16 and count < 20: count = 20
            if count > 20 and count < 28: count = 28
            if count >= 1 and count <= 28:
                count_str = str(count)
        if (count_str is None):
            count_str = str(8) # A default value if no real one found
        if (count_str is not None) and (cons_elem.get("elements") != count_str):
            cons_elem.set("elements", count_str)
    # For the rest = count the elements
    for elem in elems:
        count = len(elem.findall("SL__arrayElement"))
        count_str = str(count)
        if elem.get("elements") != count_str:
            elem.set("elements", count_str)
            fo[FUNC_OPTS.changed] = True
    return fo[FUNC_OPTS.changed]

def checkOrCreateParts_Pane(RSRC, partsList, parentObjFlags, fo, po):
    """ Checks content of the 'root/paneHierarchy/partsList' element
    """
    # NAME_LABEL properties taken from empty VI file created in LV14
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1511754, aeMasterPart=PARTID.CONTENT_AREA, aeHowGrow=5,
      aeBounds=[0,0,15,27], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 1028, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\"Pane\"", fo, po)
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


def checkOrCreateParts_Boolean(RSRC, partsList, parentObjFlags, fo, po):
    """ Checks content of partsList element of Boolean type
    """
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1507655, aeMasterPart=PARTID.BOOLEAN_BUTTON, aeHowGrow=4096,
      aeBounds=[0,0,15,41], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 17412, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\"Boolean\"", fo, po)
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

    root_objFlags = elemFindOrCreate(root, "objFlags", fo, po, pos=0)
    elemTextGetOrSetDefault(root_objFlags, 65536, fo, po)

    root_bounds = elemFindOrCreate(root, "bounds", fo, po)
    elemTextGetOrSetDefault(root_bounds, [0,0,0,0], fo, po)

    root_MouseWheelSupport = elemFindOrCreate(root, "MouseWheelSupport", fo, po)
    elemTextGetOrSetDefault(root_MouseWheelSupport, 0, fo, po)

    root_ddoList = elemFindOrCreate(root, "ddoList", fo, po)
    attribGetOrSetDefault(root_ddoList, "elements", 0, fo, po)

    root_paneHierarchy = elemFindOrCreate(root, "paneHierarchy", fo, po)
    attribGetOrSetDefault(root_paneHierarchy, "class", "pane", fo, po)
    attribGetOrSetDefault(root_paneHierarchy, "uid", 1, fo, po)

    root_savedSize = elemFindOrCreate(root, "savedSize", fo, po)
    elemTextGetOrSetDefault(root_savedSize, [0,0,0,0], fo, po)

    root_conPane = elemFindOrCreate(root, "conPane", fo, po)
    attribGetOrSetDefault(root_conPane, "class", "conPane", fo, po)
    attribGetOrSetDefault(root_conPane, "uid", 1, fo, po)

    root_keyMappingList = elemFindOrCreate(root, "keyMappingList", fo, po)
    attribGetOrSetDefault(root_keyMappingList, "class", "keyMapList", fo, po)
    attribGetOrSetDefault(root_keyMappingList, "uid", 1, fo, po)
    attribGetOrSetDefault(root_keyMappingList, "ScopeInfo", 0, fo, po)

    # Now content of the 'root/conPane' element

    root_conPane_conId = elemFindOrCreate(root_conPane, "conId", fo, po)
    elemTextGetOrSetDefault(root_conPane_conId, 4815, fo, po)

    root_conPane_cons = elemFindOrCreate(root_conPane, "cons", fo, po)
    attribGetOrSetDefault(root_conPane_cons, "elements", 0, fo, po)

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
    checkOrCreateParts_Pane(RSRC, paneHierarchy_partsList, paneHierarchy_objFlags_val, fo, po)

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

    # recover DCOs from TDs
    heapTypeMap = {htId+1:getConsolidatedTopType(RSRC, indexShift+htId, po) for htId in range(tdCount)}

    usedTypeID = 0
    for typeID, TypeDesc in heapTypeMap.items():
        if usedTypeID >= typeID: continue
        if TypeDesc.get("Type") == "Boolean":
            ddoTypeID = typeID + 1
            if ddoTypeID not in heapTypeMap or heapTypeMap[ddoTypeID] != TypeDesc:
                eprint("{:s}: Warning: Heap TypeDesc {} '{}' is followed by different type"\
                  .format(po.xml,typeID,TypeDesc.get("Type")))
                ddoTypeID = None
            print("{:s}: Associating TypeDesc {} with DCO of class '{}'"\
              .format(po.xml,typeID,"stdBool"))
            ddoObjFlags_val = 1
            dco, dco_partsList = elemCheckOrCreate_zPlaneList_arrayElement(paneHierarchy_zPlaneList, fo, po, aeClass="fPDCO", \
              aeTypeID=typeID, aeObjFlags=1, aeDdoClass="stdBool", aeConNum=-1, aeTermListLength=1, aeDdoObjFlags=ddoObjFlags_val,
              aeBounds=[185,581,223,622], aeDdoTypeID=ddoTypeID, aeMinButSize=[17,17])
            checkOrCreateParts_Boolean(RSRC, dco_partsList, ddoObjFlags_val, fo, po)
        else:
            #TODO add more types
            eprint("{:s}: Warning: Heap TypeDesc {} is not supported"\
              .format(po.xml,typeID))
        if ddoTypeID is not None:
            usedTypeID = ddoTypeID
        else:
            usedTypeID = typeID

    #TODO re-compute sizes and positions so parts do not overlap and fit the window

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
    minIndexShift = 1 # Min possible value; we will increase it shortly
    maxTdCount = 4095 # Max acceptable value; we will decrease it shortly
    VCTP_TypeDescCount = None
    VCTP = RSRC.find("./VCTP/Section")
    if VCTP is not None:
        VCTP_TypeDescList = VCTP.findall("TopLevel/TypeDesc")
        VCTP_FlatTypeDescList = VCTP.findall("TypeDesc")
    if True: # find proper IndexShift value
        # DTHP IndexShift is always above TM80 IndexShift
        # This is not directly enforced in code, but before Heap TypeDescs
        # there are always TypeDescs which store options, and those are
        # filled with DFDS, meaning they have to be included in TM80 range
        TM80 = RSRC.find("./TM80/Section")
        if TM80 is not None:
            TM80_IndexShift = TM80.get("IndexShift")
            if TM80_IndexShift is not None:
                TM80_IndexShift = int(TM80_IndexShift, 0)
            if TM80_IndexShift is not None:
                minIndexShift = max(minIndexShift, TM80_IndexShift+1)
        # DTHP IndexShift must be high enough to not include TypeDesc from CONP
        CONP_TypeDesc = RSRC.find("./CONP/Section/TypeDesc")
        if CONP_TypeDesc is not None:
            CONP_TypeID = CONP_TypeDesc.get("TypeID")
            if CONP_TypeID is not None:
                CONP_TypeID = int(CONP_TypeID, 0)
            if CONP_TypeID is not None:
                minIndexShift = max(minIndexShift, CONP_TypeID+1)
        # DTHP IndexShift must be high enough to not include TypeDesc from CPC2
        CPC2_TypeDesc = RSRC.find("./CPC2/Section/TypeDesc")
        if CPC2_TypeDesc is not None:
            CPC2_TypeID = CPC2_TypeDesc.get("TypeID")
            if CPC2_TypeID is not None:
                CPC2_TypeID = int(CPC2_TypeID, 0)
            if CPC2_TypeID is not None:
                minIndexShift = max(minIndexShift, CPC2_TypeID+1)
        # DTHP IndexShift must be high enough to not include TypeDesc of type "Function"
        LastFunction_TypeID = None
        for TypeDesc in reversed(VCTP_TypeDescList):
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
                LastFunction_TypeID = TypeDesc_Index
                break
        if LastFunction_TypeID is not None:
            minIndexShift = max(minIndexShift, LastFunction_TypeID+1)
        # DTHP IndexShift is within range of existing VCTP TypeDesc entries
        if VCTP_TypeDescList is not None:
            minIndexShift = min(minIndexShift, len(VCTP_TypeDescList))
    if True: # find proper Count value
        # Preserve VCTP size expressed by original value, if it's there.
        if tdCount is not None:
            maxTdCount = tdCount + (indexShift - minIndexShift)
        # DTHP Count is within range of existing VCTP TypeDesc entries
        if VCTP_TypeDescList is not None:
            # If we have VCTP - just replace the value, VCTP knows best
            maxTdCount = len(VCTP_TypeDescList) - minIndexShift + 1
    if indexShift is None or indexShift < minIndexShift:
        print("{:s}: Changing 'DTHP/TypeDescSlice' IndexShift to {}"\
            .format(po.xml,minIndexShift))
        indexShift = minIndexShift
        typeDescSlice.set("IndexShift","{}".format(indexShift))
        fo[FUNC_OPTS.changed] = True
    if tdCount is None or tdCount > maxTdCount:
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
    # Now make more detailed refilling of ddoList - it should have entries for all DDOs
    zPlaneList_elems = FPHP.findall("./SL__rootObject/root/paneHierarchy/zPlaneList/SL__arrayElement[@class='fPDCO'][@uid]")
    ddoList = FPHP.find("./SL__rootObject/root/ddoList")
    for ddo_elem in zPlaneList_elems:
        uidStr = ddo_elem.get("uid")
        if representsInt(uidStr):
            uid = int(uidStr,0)
        ddoref = ddoList.find("./SL__arrayElement[@uid='{}']".format(uid))
        if ddoref is None:
            ddoref = ET.SubElement(ddoList, "SL__arrayElement")
            ddoref.set("uid",str(uid))

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

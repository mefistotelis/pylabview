# -*- coding: utf-8 -*-

""" LabView RSRC file format heap parsers.

    Heap formats are used for Front Panel and Block Diagram strorage in a RSRC file.
"""

# Copyright (C) 2019 Mefistotelis <mefistotelis@gmail.com>
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.


import enum
import re
import struct

from hashlib import md5
from io import BytesIO
from types import SimpleNamespace
from ctypes import *

import LVdatatype
import LVdatafill
import LVmisc
from LVmisc import eprint
import LVxml as ET

class HEAP_FORMAT(enum.Enum):
    """ Heap storage formats
    """
    Unknown = 0
    VersionT = 1
    XMLVer = 2
    BinVerA = 3
    BinVerB = 4
    BinVerC = 5


class NODE_SCOPE(enum.IntEnum):
    """ Heap node scope
    """
    TagOpen = 0 # Opening of a tag
    TagLeaf = 1 # Short tag, opening and closing as single entry
    TagClose = 2 # Closing of a tag


class ENUM_TAGS(enum.Enum):
    @classmethod
    def has_value(cls, value):
        #return tagId in set(itm.value for itm in cls) # slower
        return value in cls._value2member_map_

    @classmethod
    def has_name(cls, name):
        return name in cls.__members__


class SL_SYSTEM_TAGS(ENUM_TAGS):
    SL__object = -3
    SL__array = -4
    SL__reference = -5
    SL__arrayElement = -6
    SL__rootObject = -7

class SL_SYSTEM_ATTRIB_TAGS(ENUM_TAGS):
    SL__class = -2
    SL__uid = -3
    SL__stockObj = -4
    SL__elements = -5
    SL__index = -6
    SL__stockSource = -7


class OBJ_FIELD_TAGS(ENUM_TAGS):
    OF__activeDiag = 1
    OF__activeMarker = 2
    OF__activePlot = 3
    OF__activeThumb = 4
    OF__activeXScale = 5
    OF__activeYScale = 6
    OF__alarmName = 7
    OF__bary = 8
    OF__bgColor = 9
    OF__bindings = 10
    OF__blinkList = 11
    OF__borderColor = 12
    OF__botOrRight = 13
    OF__bounds = 14
    OF__buf = 15
    OF__callOffset = 16
    OF__callType = 17
    OF__callee = 18
    OF__caller = 19
    OF__callerGlyphBounds = 20
    OF__caseSelDCO = 21
    OF__cboxDsOffset = 22
    OF__cboxTdOffset = 23
    OF__cbrIcon = 24
    OF__cinPath = 25
    OF__className = 26
    OF__clumpNum = 27
    OF__cnst = 28
    OF__code = 29
    OF__color = 30
    OF__colorDSO = 31
    OF__colorTDO = 32
    OF__cols = 33
    OF__commentMode = 34
    OF__companionDiag = 35
    OF__conId = 36
    OF__conNum = 37
    OF__conPane = 38
    OF__confState = 39
    OF__configNode = 40
    OF__connectorTM = 41
    OF__cons = 42
    OF__contRect = 43
    OF__ctlDataObj = 44
    OF__dBounds = 45
    OF__dIdx = 46
    OF__dataNodeList = 47
    OF__dco = 48
    OF__dcoAgg = 49
    OF__dcoFiller = 50
    OF__dcoList = 51
    OF__ddo = 52
    OF__ddoIndex = 53
    OF__ddoList = 54
    OF__ddoListList = 55
    OF__defaultDiag = 56
    OF__delDCO = 57
    OF__depth = 58
    OF__description = 59
    OF__diagDefined = 60
    OF__diagFiller1 = 61
    OF__diagFiller2 = 62
    OF__diagramList = 63
    OF__docBounds = 64
    OF__dsOffset = 65
    OF__dsw = 66
    OF__dynBounds = 67
    OF__dynLink = 68
    OF__eOracleIdx = 69
    OF__ePtrOff = 70
    OF__eSizeOff = 71
    OF__eltDCO = 72
    OF__embedToken = 73
    OF__errCode = 74
    OF__errIn = 75
    OF__errOfst = 76
    OF__errOut = 77
    OF__eventObj_unused = 78
    OF__fName = 79
    OF__fgColor = 80
    OF__filler = 81
    OF__filterNodeList = 82
    OF__firstNodeIdx = 83
    OF__focusRow = 84
    OF__format = 85
    OF__formula = 86
    OF__frontRow = 87
    OF__funcTD = 88
    OF__graphCursor = 89
    OF__graphType = 90
    OF__growAreaBounds = 91
    OF__growObj = 92
    OF__growTermsList = 93
    OF__growViewObj = 94
    OF__hFlags = 95
    OF__hGrowNodeList = 96
    OF__hSEnd = 97
    OF__hSStart = 98
    OF__headerImage = 99
    OF__hierarchyColor = 100
    OF__histDSOffset = 101
    OF__histTD = 102
    OF__histTDOffset = 103
    OF__hoodBounds = 104
    OF__hotPoint = 105
    OF__howGrow = 106
    OF__i = 107
    OF__iconBounds = 108
    OF__id = 109
    OF__image = 110
    OF__inArrDCO = 111
    OF__inVILib = 112
    OF__index = 113
    OF__indexPosCol = 114
    OF__indexPosRow = 115
    OF__indexing = 116
    OF__innerLpTunDCO = 117
    OF__innerR = 118
    OF__innerSeq = 119
    OF__inplace = 120
    OF__instance = 121
    OF__instanceSelector = 122
    OF__instrStyle = 123
    OF__intermediateList = 124
    OF__invokeFlags = 125
    OF__keyMappingList = 126
    OF__label = 127
    OF__lastSignalKind = 128
    OF__legendLbl = 129
    OF__lenDCO = 130
    OF__lengthDCOList = 131
    OF__level = 132
    OF__libPath = 133
    OF__listFlags = 134
    OF__listboxFlags = 135
    OF__loopEndDCO = 136
    OF__loopIndexDCO = 137
    OF__loopTimingDCO = 138
    OF__lpTunDCO = 139
    OF__lsrDCOList = 140
    OF__mJasterWizard = 141
    OF__mask = 142
    OF__master_unused = 143
    OF__masterPart = 144
    OF__mate = 145
    OF__maxPaneSize = 146
    OF__maxPanelSize = 147
    OF__mclFlags = 148
    OF__menuInstanceUsed = 149
    OF__methCode = 150
    OF__methName = 151
    OF__minPaneSize = 152
    OF__minPanelSize = 153
    OF__nChunks = 154
    OF__nConnections = 155
    OF__nDims = 156
    OF__nInputs = 157
    OF__nLabels = 158
    OF__nMajDivs = 159
    OF__nRC = 160
    OF__nVisItems = 161
    OF__nmxFiller = 162
    OF__nodeInfo = 163
    OF__nodeList = 164
    OF__nodeName = 165
    OF__numFrozenCols = 166
    OF__numFrozenRows = 167
    OF__numRows = 168
    OF__numSubVIs = 169
    OF__oMId = 170
    OF__oRC = 171
    OF__objFlags = 172
    OF__omidDSOffset = 173
    OF__omidTDOffset = 174
    OF__omidTypeDesc = 175
    OF__orderList = 176
    OF__origin = 177
    OF__otherSide = 178
    OF__outerR = 179
    OF__outputDCO = 180
    OF__outputNode = 181
    OF__ownerSignal = 182
    OF__pBounds = 183
    OF__pMap = 184
    OF__pMapOfst = 185
    OF__pageList = 186
    OF__paneFlags = 187
    OF__paneHierarchy = 188
    OF__paramIdx = 189
    OF__paramTableOffset = 190
    OF__parmIndex = 191
    OF__partID = 192
    OF__partOrder = 193
    OF__partsList = 194
    OF__pattern = 195
    OF__pctTransparent = 196
    OF__permDCOList = 197
    OF__permutation = 198
    OF__pixmap = 199
    OF__pos = 200
    OF__preferredInstIndex = 201
    OF__primIndex = 202
    OF__primResID = 203
    OF__priv = 204
    OF__privDataList = 205
    OF__propList = 206
    OF__refList = 207
    OF__resetJumpLabel = 208
    OF__revisionInfoCreator = 209
    OF__revisionInfoTlkitID = 210
    OF__revisionInfoTlkitVersion = 211
    OF__ringDsOffset = 212
    OF__ringTdOffset = 213
    OF__root = 214
    OF__rowHeight = 215
    OF__rsrDCO = 216
    OF__rsrcID = 217
    OF__rtPopupData = 218
    OF__rtPopupString = 219
    OF__rtPopupVersion = 220
    OF__rtdsoff = 221
    OF__savedState = 222
    OF__screenRes = 223
    OF__scriptName = 224
    OF__sdllName = 225
    OF__selLabData = 226
    OF__selString = 227
    OF__selectionColor = 228
    OF__seqLocDCOList = 229
    OF__sequenceList = 230
    OF__shortCount = 231
    OF__signalIndex = 232
    OF__signalList = 233
    OF__simDiagFlags = 234
    OF__simparam = 235
    OF__simtype = 236
    OF__simulationDiag = 237
    OF__sizeRect = 238
    OF__slaveList_unused = 239
    OF__slocFiller = 240
    OF__snFiller = 241
    OF__splitterFlags = 242
    OF__srDCOList = 243
    OF__srcDCO = 244
    OF__stamp = 245
    OF__state = 246
    OF__stateTD = 247
    OF__streamData = 248
    OF__strings = 249
    OF__structColor = 250
    OF__subPanelFlags = 251
    OF__subVIGlyphBounds = 252
    OF__symmetry = 253
    OF__tInset = 254
    OF__tabWidth = 255
    OF__table = 256
    OF__tableFlags = 257
    OF__tagDevice = 258
    OF__tagDisplayFilter = 259
    OF__tagSubTypeClass = 260
    OF__tagType = 261
    OF__tagTypeClass = 262
    OF__tblOffset = 263
    OF__tdOffset = 264
    OF__termBMPs = 265
    OF__termBounds = 266
    OF__termHotPoint = 267
    OF__termList = 268
    OF__textDivider = 269
    OF__textRec = 270
    OF__threadInfo = 271
    OF__timeDataNodeDMux = 272
    OF__timeDataNodeMux = 273
    OF__timeLoop = 274
    OF__timeOutDCO = 275
    OF__tool = 276
    OF__topOrLeft = 277
    OF__treeFlags = 278
    OF__tsH = 279
    OF__tunnelList = 280
    OF__type = 281
    OF__typeCode = 282
    OF__typeDesc = 283
    OF__userDiagram = 284
    OF__vTblPtr = 285
    OF__varTypeDesc = 286
    OF__vblName = 287
    OF__version = 288
    OF__viPath = 289
    OF__viState = 290
    OF__visClust = 291
    OF__width = 292
    OF__winFlags = 293
    OF__wireGlyphID = 294
    OF__wireID = 295
    OF__wireTable = 296
    OF__wizData = 297
    OF__wizDataH = 298
    OF__wizDataID = 299
    OF__wizID = 300
    OF__wizVersion = 301
    OF__xflags = 302
    OF__zPlaneList = 303
    OF__zPlaneListList = 304
    OF__zoom = 305
    OF__srcDCO1 = 306
    OF__srcDCO2 = 307
    OF__srcDCO3 = 308
    OF__srcDCO4 = 309
    OF__cRectAbove = 310
    OF__cRectBelow = 311
    OF__variantIndex = 312
    OF__termListLength = 313
    OF__refListLength = 314
    OF__hGrowNodeListLength = 315
    OF__dataTypeDesc = 316
    OF__hair = 317
    OF__displayName = 318
    OF__selLabFlags = 319
    OF__lastSelRow = 320
    OF__lastSelCol = 321
    OF__scrollPosV = 322
    OF__scrollPosH = 323
    OF__totalBounds = 324
    OF__srcRect = 325
    OF__labelPosRow = 326
    OF__labelPosCol = 327
    OF__simparamOut = 328
    OF__innerMate = 329
    OF__outerMate = 330
    OF__flatSeq = 331
    OF__timeSeq = 332
    OF__slaveMods = 333
    OF__slaveOwner = 334
    OF__simConfigNode = 335
    OF__simOutputNode = 336
    OF__glyphs = 337
    OF__pUseStoredSize = 338
    OF__pUseStoredPos = 339
    OF__pRuntimeType = 340
    OF__pRuntimeTop = 341
    OF__pRuntimeLeft = 342
    OF__pRuntimeWidth = 343
    OF__pRuntimeHeight = 344
    OF__pRuntimeMonitor = 345
    OF__libVersion = 346
    OF__ratio = 347
    OF__annexDDOFlag = 348
    OF__xCtlState = 349
    OF__wizList = 350
    OF__lockedObjectList = 351
    OF__lockedSignalList = 352
    OF__masterStateEnum = 353
    OF___Quit_StateEnum = 354
    OF__stopCodeEnum = 355
    OF__stateLoop = 356
    OF__stateCase = 357
    OF__stateCaseOutputTunnel = 358
    OF__stateList = 359
    OF__isSubVICall = 360
    OF__name = 361
    OF__transitionEnum = 362
    OF__transitionCase = 363
    OF__transCaseOutputTunnel = 364
    OF__transitionList = 365
    OF__stateBounds = 366
    OF__terminal = 367
    OF__stateConst = 368
    OF__exitAngle = 369
    OF__entranceAngle = 370
    OF__stiffness = 371
    OF__labelPos = 372
    OF__pinCorner = 373
    OF__currentlyScripting = 374
    OF__textNodeLabel = 375
    OF__heapFlags = 376
    OF__refreshFilter = 377
    OF__plugInData = 378
    OF__xTunDDO = 379
    OF__gridFlags = 380
    OF__headerFiles = 381
    OF__sceneView = 382
    OF__lastAutoScale = 383
    OF__autoScaleDelay = 384
    OF__reserveCB = 385
    OF__unreserveCB = 386
    OF__abortCB = 387
    OF__paramInfo = 388
    OF__extFuncFlags = 389
    OF__tMI = 390
    OF__lineNumbers = 391
    OF__fPath = 392
    OF__mDate = 393
    OF__errHandle = 394
    OF__xTunnelDir = 395
    OF__sCFlag = 396
    OF__sCStNGuid = 397
    OF__sCDiagSubType = 398
    OF__sCDiagFlag = 399
    OF__isLoopCaseTransition = 400
    OF__selectorXNode = 401
    OF__iFeedbackLoop = 402
    OF__cellPosRow = 403
    OF__cellPosCol = 404
    OF__font = 405
    OF__mode = 406
    OF__height = 407
    OF__glyphIndex = 408
    OF__flags = 409
    OF__attributeList = 410
    OF__qtWidget = 411
    OF__fLoopCondTerm = 412
    OF__isInterface = 413
    OF__loopLimitDCO = 414
    OF__loopTestDCO = 415
    OF__overrideType = 416
    OF__maxWordLength = 417
    OF__override = 418
    OF__overflow = 419
    OF__quantize = 420
    OF__tunOrdList = 421
    OF__multiSegPipeFlange1Size = 422
    OF__multiSegPipeFlange2Size = 423
    OF__multiSegPipeFlange1Depth = 424
    OF__multiSegPipeFlange2Depth = 425
    OF__multiSegPipeWidth = 426
    OF__staticState = 427
    OF__funcName = 428
    OF__mFilePath = 429
    OF__tagDLLPath = 430
    OF__recursiveFunc = 430
    OF__tagDLLName = 431
    OF__poser = 432
    OF__dataValRefDCO = 433
    OF__write = 434
    OF__showTimestamp = 435
    OF__name4 = 436
    OF__privDataDSO = 437
    OF__privDataTMI = 438
    OF__disabledList = 439
    OF__tunnelLink = 451
    OF__activeBus = 452
    OF__terminal_ID = 453
    OF__implementingNode = 454
    OF__fboxlineList = 455
    OF__compressedWireTable = 456
    OF__sharedCloneAllocationFlags = 457
    OF__initOrderIndex = 458
    OF__ringSparseValues = 459
    OF__ringDisabledIndicies = 460
    OF__scrollbarMin = 461
    OF__scrollbarMax = 462
    OF__scrollbarInc = 463
    OF__scrollbarVis = 464
    OF__browseOptions = 465
    OF__decomposeArraySplitNodeSplitDimension = 466
    OF__rowHeaders = 467
    OF__columnHeaders = 468
    OF__activeCell = 469
    OF__scaleDMin = 470
    OF__scaleDMax = 471
    OF__scaleDStart = 472
    OF__scaleDIncr = 473
    OF__scaleDMinInc = 474
    OF__scaleDMultiplier = 475
    OF__scaleDOffset = 476
    OF__scaleRRef = 477
    OF__scaleRngf = 478
    OF__scaleCenter = 479
    OF__scaleRadius = 480
    OF__scaleRMin = 481
    OF__scaleRMax = 482
    OF__scaleFunIdx = 483
    OF__scaleLoColor = 484
    OF__scaleHiColor = 485
    OF__scaleColorData = 486
    OF__minDataSel = 487
    OF__maxDataSel = 488
    OF__pivotDataSel = 489
    OF__absTime_min = 490
    OF__absTime_max = 491
    OF__absTime_inc = 492
    OF__baseListboxItemStrings = 493
    OF__baseListboxDoubleClickedRow = 494
    OF__baseListboxClickedColumnHeader = 495
    OF__baseListboxDragRow = 496
    OF__listboxClickedCell = 497
    OF__listboxDisabledItems = 498
    OF__listboxGlyphColumns = 499
    OF__treeNodeArray = 500
    OF__treeDragIntoRow = 501
    OF__arrayIndices = 502
    OF__arraySelectionStart = 503
    OF__arraySelectionEnd = 504
    OF__comboBoxIndex = 505
    OF__comboBoxValues = 506
    OF__tabArrayFirstTab = 507
    OF__tabArrayFg = 508
    OF__tabArrayBg = 509
    OF__tabArrayTabInfoArray = 510
    OF__tabControlPageSelValue = 511
    OF__tabControlPageInfoArray = 512
    OF__StdNumMin = 513
    OF__StdNumMax = 514
    OF__StdNumInc = 515
    OF__CBRExecAlias = 516
    OF__CBRExecResolved = 517
    OF__CBRRefPathAlias = 518
    OF__CBRRefPath = 519
    OF__CBRCfgMode = 520
    OF__commentSelInfoArray = 521
    OF__commentSelLabData = 522
    OF__GVNGrowTerms = 523
    OF__GVNMaxGrowTerms = 524
    OF__GVMinGVWidth = 525
    OF__GVHoodTermWidth = 526
    OF__GVGrowTermsInfo = 527
    OF__PlugInDLLName = 528
    OF__PlugInLoadProcName = 529
    OF__PropItemName = 530
    OF__PropItemCode = 531
    OF__ActiveXItemDataSize = 532
    OF__ActiveXItemObjMgrFlags = 533
    OF__ActiveXItemOrigVarType = 534
    OF__ActiveXItemOrigIndex = 535
    OF__DotNetItemDataSize = 536
    OF__DotNetItemObjMgrFlags = 537
    OF__DotNetItemDotNetFlags = 538
    OF__DotNetItemType = 539
    OF__SharedVariableCustomRule = 540
    OF__GraphMPlot = 541
    OF__GraphActivePlot = 542
    OF__GraphActiveCursor = 543
    OF__GraphCursors = 544
    OF__GraphFlags = 545
    OF__GraphTreeData = 546
    OF__GraphPlotImages = 547
    OF__GraphAnnotations = 548
    OF__GraphActivePort = 549
    OF__GraphCursorButtons = 550
    OF__GraphCursorLegendData = 551
    OF__GraphPlotLegendData = 552
    OF__GraphMinPlotNum = 553
    OF__GraphBusOrg = 554
    OF__GraphScalePalette = 555
    OF__GraphScaleData = 556
    OF__IntensityGraphCT = 557
    OF__IntensityGraphBMP = 558
    OF__IntensityGraphBounds = 559
    OF__SimDiagFeedThroughData = 560
    OF__SimDiagSimNodeMapData = 561
    OF__SimDiagCompNodeMapData = 562
    OF__SimDiagSignalMapData = 563
    OF__SimDiagAdditionalData = 564
    OF__SelectDefaultCase = 565
    OF__SelectNRightType = 566
    OF__SelectRangeArray32 = 567
    OF__SelectRangeArray64 = 568
    OF__SelectStringArray = 569
    OF__EventNodeEvents = 570
    OF__DefaultData = 571
    OF__ParForWorkers = 572
    OF__ParForIndexDistribution = 573
    OF__StateData = 574
    OF__MinButSize = 575
    OF__possibleMSNDCOTypes = 576
    OF__feedbackNodeDelay = 577
    OF__englishName = 578
    OF__SharedVariableDynamicResID = 579
    OF__ParForNumStaticWorkers = 580
    OF__OMRCFlags = 581
    OF__SimDiagSimParamData = 582
    OF__SelectSelLabFlags = 583
    OF__SelectSelLabData = 584
    OF__CommentSelLabFlags = 585
    OF__CommentSelLabData = 586
    OF__UDClassItemDataSize = 587
    OF__UDClassItemPropName = 588
    OF__ConstValue = 589
    OF__EventNodeOccurrence = 590
    OF__EventSelLabFlags = 591
    OF__EventSelLabData = 592
    OF__ChunkSize = 593
    OF__DebuggingEnabled = 594
    OF__SlaveFBInputNode = 595
    OF__HiddenFBNode = 596
    OF__InnerChunkSize = 597
    OF__savedSize = 598
    OF__nodeFlags2 = 599
    OF__OutputInstanceNumberFromP = 600
    OF__CBRSaveStyle = 601
    OF__JoinCBRTimeout = 602
    OF__OffScreenSceneView = 603
    OF__OffScreenGLContext = 604
    OF__scaleRMin32 = 605
    OF__scaleRMax32 = 606
    OF__TunnelType = 607
    OF__DefaultTunnelType = 608
    OF__FpgaImplementation = 609
    OF__IsConditional = 610
    OF__ConditionDCOList = 611
    OF__LpTunConditionDCO = 612
    OF__MSNFlags = 613
    OF__arrayOfStringsIsCellArray = 614
    OF__MouseWheelSupport = 615
    OF__GraphMPlot2013 = 616
    OF__GraphBusOrg2013 = 617
    OF__attachedObject = 618
    OF__attachment = 619
    OF__ScaleAutoscalePadding = 620
    OF__ThralledTunnelUID = 621
    OF__GraphCursors2014 = 622
    OF__GraphAnnotations2014 = 623
    OF__kSLHDefaultValueMatchesCtlVI = 624
    OF__kSLHFieldDefaultValueMatchesCtlVI = 625
    OF__FpgaEnableBoundsMux = 626


class SL_CLASS_TAGS(ENUM_TAGS):
    SL__fontRun = 0
    SL__textHair = 1
    SL__prNodeList = 3
    SL__prFrameList = 4
    SL__prVIPartList = 5
    SL__generic = 6
    SL__list = 7
    SL__dataObj = 8
    SL__cosm = 9
    SL__label = 10
    SL__multiCosm = 11
    SL__bigMultiCosm = 12
    SL__multiLabel = 13
    SL__bigMultiLabel = 14
    SL__dCO = 17
    SL__fPDCO = 18
    SL__bDConstDCO = 19
    SL__bDDCO = 20
    SL__term = 21
    SL__fPTerm = 22
    SL__signal = 23
    SL__wire = 24
    SL__hSignal = 25
    SL__hNode = 26
    SL__diag = 27
    SL__node = 28
    SL__sRN = 29
    SL__sNode = 30
    SL__growableNode = 31
    SL__forLoop = 32
    SL__whileLoop = 33
    SL__lpTun = 34
    SL__innerLpTun = 35
    SL__lCnt = 36
    SL__lTst = 37
    SL__lMax = 38
    SL__lSR = 39
    SL__rSR = 40
    SL__sequence = 41
    SL__seqTun = 42
    SL__sLoc = 43
    SL__select = 44
    SL__selTun = 45
    SL__caseSel = 46
    SL__prim = 47
    SL__parm = 48
    SL__iUse = 49
    SL__gRef = 50
    SL__iUseDCO = 51
    SL__mux = 52
    SL__mxDCO = 53
    SL__demux = 54
    SL__dmxDCO = 55
    SL__codeVI = 56
    SL__codeVIArg = 57
    SL__aBuild = 58
    SL__aBuildDCO = 59
    SL__cABuild = 60
    SL__cABuildDCO = 61
    SL__concat = 62
    SL__concatDCO = 63
    SL__decimate = 64
    SL__decimateDCO = 65
    SL__interLeave = 66
    SL__interLeaveDCO = 67
    SL__aIndx = 68
    SL__aIDCO = 69
    SL__subset = 72
    SL__subsetDCO = 73
    SL__fBox = 74
    SL__fBoxDCO = 75
    SL__supC = 76
    SL__dDO = 77
    SL__bDFixed = 78
    SL__stdBool = 79
    SL__stdNum = 80
    SL__stdString = 81
    SL__indArr = 82
    SL__stdClust = 83
    SL__stdVar = 84
    SL__stdRefNum = 85
    SL__stdColorNum = 86
    SL__stdRing = 87
    SL__stdSlide = 88
    SL__stdKnob = 89
    SL__stdPath = 91
    SL__stdTable = 92
    SL__stdHandle = 93
    SL__stdGraph = 94
    SL__stdPict = 95
    SL__stdPixMap = 96
    SL__userItem = 97
    SL__nmxDCO = 98
    SL__nMux = 99
    SL__typeDef = 100
    SL__stdRamp = 101
    SL__uCast = 102
    SL__gRefDCO = 103
    SL__annex = 104
    SL__stdListbox = 105
    SL__extFunc = 106
    SL__extFuncArg = 107
    SL__cpdArith = 108
    SL__cpdArithDCO = 109
    SL__crossList = 124
    SL__oHExt = 126
    SL__conPane = 127
    SL__loop = 128
    SL__multiDiagSNode = 129
    SL__instrTypeRec = 130
    SL__typeDesc = 131
    SL__editSelectionBkUp = 132
    SL__bHExt = 133
    SL__transTable = 134
    SL__textSelectionBkUp = 135
    SL__objInfoTable = 136
    SL__recipeBkUp = 137
    SL__recipe = 138
    SL__dataBkUp = 139
    SL__propNode = 140
    SL__propItem = 141
    SL__hGrowCItem = 142
    SL__scale = 143
    SL__scanfArg = 144
    SL__printfArg = 145
    SL__scanf = 146
    SL__printf = 147
    SL__stdTag = 148
    SL__selLabel = 149
    SL__wizardData = 166
    SL__hGrowNode = 168
    SL__invokeNode = 169
    SL__invokeItem = 170
    SL__oleVariant = 171
    SL__grouper = 172
    SL__iUseCore = 173
    SL__callByRefNode = 174
    SL__stdCont = 175
    SL__cEData = 176
    SL__subVIFromSelBkUp = 177
    SL__selListBkUp = 178
    SL__sNDCO = 179
    SL__scriptNode = 180
    SL__stdComboBox = 181
    SL__ctlRefConst = 182
    SL__ctlRefDCO = 183
    SL__stdMeasureData = 184
    SL__aReplace = 185
    SL__aRepDCO = 186
    SL__aInsert = 187
    SL__aInsDCO = 188
    SL__aDelete = 189
    SL__aDelDCO = 190
    SL__textNode = 191
    SL__exprNode = 192
    SL__cLStrObj = 193
    SL__stdLvVariant = 194
    SL__tabControl = 195
    SL__placeholderNode = 196
    SL__polyIUse = 197
    SL__polyIUseDCO = 198
    SL__page = 199
    SL__tabArray = 200
    SL__part = 201
    SL__flatSequence = 202
    SL__flatSeqTun = 203
    SL__growViewObj = 204
    SL__commentNode = 205
    SL__commentTun = 206
    SL__stdSubPanel = 207
    SL__mergeSignal = 208
    SL__mergeSignalDCO = 209
    SL__grid = 210
    SL__splitSignal = 211
    SL__splitSignalDCO = 212
    SL__eventStruct = 213
    SL__eventDataNode = 214
    SL__eventDynDCO = 215
    SL__eventTimeOut = 216
    SL__dropFeedback = 217
    SL__masterWiz = 218
    SL__subWizard = 219
    SL__stateDiagWiz = 220
    SL__state = 221
    SL__transition = 222
    SL__absTime = 223
    SL__numLabel = 224
    SL__tableControl = 225
    SL__digitalTable = 226
    SL__externalNode = 227
    SL__externalTun = 228
    SL__polySelector = 229
    SL__listbox = 230
    SL__treeControl = 231
    SL__externalSignal = 232
    SL__baseTableControl = 233
    SL__baseListbox = 234
    SL__eventRegNode = 235
    SL__eventRegItem = 236
    SL__constructorNode = 237
    SL__plugInDDO = 238
    SL__radioClust = 239
    SL__externalStructNode = 240
    SL__stubDDO = 241
    SL__graphSplitBar = 242
    SL__eventRItem = 243
    SL__eventRegCallback = 244
    SL__eventRegCBItem = 245
    SL__externalDiagram = 246
    SL__subVIFromCodeGenBkUp = 247
    SL__oldStatVIRef = 248
    SL__lTiming = 249
    SL__timeDataNode = 250
    SL__timeLoop = 251
    SL__timeLoopExtNode = 252
    SL__simDiag = 253
    SL__simNode = 254
    SL__compDiag = 255
    SL__simTun = 256
    SL__keyMapList = 257
    SL__xControl = 258
    SL__statVIRef = 259
    SL__dynIUse = 260
    SL__xNode = 261
    SL__xTunnel = 262
    SL__xStructure = 263
    SL__xDiagram = 264
    SL__xSignal = 265
    SL__dynPolyIUse = 266
    SL__dynLink = 267
    SL__udClassDDO = 268
    SL__simDCO = 269
    SL__baseRefNum = 270
    SL__privDataHelper = 271
    SL__propItemInfo = 272
    SL__axItemInfo = 273
    SL__dnetItemInfo = 274
    SL__udClassPropItemPrivInfo = 275
    SL__aInit = 276
    SL__aInitDCO = 277
    SL__aReshape = 278
    SL__aReshapeDCO = 279
    SL__sharedGrowArrayNode = 280
    SL__growArrayNode = 281
    SL__sharedGrowArrayDCO = 282
    SL__growArrayDCO = 283
    SL__pane = 284
    SL__splitter = 285
    SL__dynIUseCore = 286
    SL__timeFlatSequenceFrame = 287
    SL__xDataNode = 288
    SL__sequenceFrame = 289
    SL__timeSequence = 290
    SL__timeFlatSequence = 291
    SL__callParentDynIUse = 292
    SL__matedLpTun = 293
    SL__matedSeqTun = 294
    SL__matedLSR = 295
    SL__matedRSR = 296
    SL__scrollbar = 297
    SL__mathScriptNode = 298
    SL__mathScriptNodeDCO = 299
    SL__sdfDiag = 300
    SL__sdfNode = 301
    SL__sdfcompDiag = 302
    SL__sdfTun = 303
    SL__sdfDCO = 304
    SL__scenegraphdisplay = 305
    SL__htmlControl = 306
    SL__codeWizard = 307
    SL__cBoxDPIdx = 308
    SL__cBoxDCODPIdx = 309
    SL__abstractDiagram = 310
    SL__mathDiagram = 311
    SL__basicObj = 312
    SL__regionNode = 313
    SL__stateNode = 314
    SL__junctionNode = 315
    SL__regionTun = 316
    SL__multiSegmentPipe = 317
    SL__lDCO = 318
    SL__rDCO = 319
    SL__forkNode = 320
    SL__joinNode = 321
    SL__scDiag = 322
    SL__indArrInterface = 323
    SL__leftFeedback = 324
    SL__rightFeedback = 325
    SL__initFeedback = 326
    SL__qtCont = 327
    SL__sharedVariable = 328
    SL__sharedVariableDCO = 329
    SL__hiddenFBNode = 330
    SL__overridableParm = 331
    SL__ternaryDDO = 332
    SL__decomposeRecomposeStructure = 333
    SL__decomposeRecomposeTunnel = 334
    SL__decomposeArrayNode = 335
    SL__decomposeClusterNode = 336
    SL__decomposeVariantNode = 337
    SL__decomposeMatchNode = 338
    SL__decomposeDataValRefNode = 339
    SL__dataValRefPoserInterface = 340
    SL__decomposeDCO = 341
    SL__decomposeClusterDCO = 342
    SL__poserInterface = 343
    SL__arrayPoserInterface = 344
    SL__clusterPoserInterface = 345
    SL__variantPoserInterface = 346
    SL__matchPoserInterface = 347
    SL__mathScriptCallByRefNode = 349
    SL__FBoxLine = 351
    SL__sceneGraphDisplayPart = 352
    SL__fxpUnbundle = 353
    SL__fxpUnbundleDCO = 354
    SL__decomposeArrayNodeDCO = 355
    SL__decomposeArraySplitNode = 356
    SL__arraySplitPoserInterface = 357
    SL__decomposeArraySPlitNodeDCO = 358
    SL__genIUse = 359
    SL__parForWorkers = 361
    SL__sharedVariableDynamicOpen = 362
    SL__sharedVariableDynamicRead = 363
    SL__sharedVariableDynamicWrite = 364
    SL__sharedVariableDynamicDCO = 365
    SL__conditionalFeedbackDCO = 366
    SL__chunkSize = 367
    SL__slaveFBInputNode = 368
    SL__innerChunkSize = 369
    SL__mergeErrors = 370
    SL__mergeErrorsDCO = 371
    SL__dexChannelCreateNode = 372
    SL__dexChannelShutdownNode = 373
    SL__lpTunConditionDCO = 374
    SL__attachment = 375
    SL__ConpaneConnection = 500
    SL__ComplexScalar = 550
    SL__Time128 = 551
    SL__Image = 600
    SL__KeyMappingBinding = 700
    SL__ExtFuncParam = 740
    SL__ExtFuncAdded = 750
    SL__SubCosm = 800
    SL__EmbedObject = 900
    SL__SubLabel = 901
    SL__SceneView = 902
    SL__SceneColor = 903
    SL__SceneEyePoint = 904
    SL__TableAttribute = 905
    SL__BrowseOptions = 906
    SL__StorageRowCol = 907
    SL__ColorPair = 908
    SL__TreeNode = 909
    SL__RelativeRowCol = 910
    SL__TabInfoItem = 911
    SL__PageInfoItem = 912
    SL__TreeElt = 913
    SL__ExpressionInfo = 914
    SL__SelectorInfoElement = 915
    SL__GrowTermInfo = 916
    SL__MappedPoint = 917
    SL__PlotData = 918
    SL__CursorData = 919
    SL__PlotImages = 920
    SL__CursorButtonsRec = 921
    SL__PlotLegendData = 922
    SL__DigitlaBusOrgClust = 923
    SL__ScaleLegendData = 924
    SL__ScaleData = 925
    SL__ObjNodeMapEntry = 927
    SL__ObjMapEntry = 928
    SL__EventSpec = 929
    SL__SelectorRange = 930


class SL_MULTI_DIM_CLASS_TAGS(ENUM_TAGS):
    SL__multiDimArray = 0


class OBJ_FONT_RUN_TAGS(ENUM_TAGS):
    """Tags within SL__fontRun class.

    Strings as the same as in OBJ_TEXT_HAIR_TAGS, but support is a bit different.
    """
    OF__textRecObject = 0
    OF__flags = 1
    OF__mode = 2
    OF__text = 3
    OF__view = 4
    OF__bgColor = 5
    OF__fr = 6
    OF__curfr = 7
    OF__fontofst = 8
    OF__fontid = 9
    OF__fontcolor = 10


class OBJ_TEXT_HAIR_TAGS(ENUM_TAGS):
    OF__textRecObject = 0
    OF__flags = 1
    OF__mode = 2
    OF__text = 3
    OF__view = 4
    OF__bgColor = 5
    OF__fr = 6
    OF__curfr = 7
    OF__fontofst = 8
    OF__fontid = 9
    OF__fontcolor = 10


class OBJ_COMPLEX_SCALAR_TAGS(ENUM_TAGS):
    OF__real = 0
    OF__imaginary = 1


class OBJ_TIME128_TAGS(ENUM_TAGS):
    OF__Seconds = 0
    OF__FractionalSeconds = 1


class OBJ_IMAGE_TAGS(ENUM_TAGS):
    OF__ImageResID = 0
    OF__ImageInternalsResID = 1
    OF__ImageData1 = 2
    OF__ImageData2 = 3
    OF__ImageData3 = 4


class OBJ_SUBCOSM_TAGS(ENUM_TAGS):
    OF__Bounds = 0
    OF__FGColor = 1
    OF__BGColor = 2
    OF__Image = 3


class OBJ_EMBED_OBJECT_TAGS(ENUM_TAGS):
    OF__Type = 0
    OF__Flags = 1


class OBJ_SCENE_GRAPH_TAGS(ENUM_TAGS):
    OF__ModelView = 0
    OF__Projection = 1
    OF__BackgroundColor = 2
    OF__CameraController = 3
    OF__AutoProjection = 4
    OF__Zoom = 5
    OF__EyePoint = 6


class OBJ_SCENE_COLOR_TAGS(ENUM_TAGS):
    OF__red = 0
    OF__green = 1
    OF__blue = 2
    OF__alpha = 3


class OBJ_SCENE_EYE_POINT_TAGS(ENUM_TAGS):
    OF__eyePoint_X = 0
    OF__eyePoint_Y = 1
    OF__eyePoint_Z = 2


class OBJ_ATTRIBUTE_LIST_ITEM_TAGS(ENUM_TAGS):
    OF__cellPosRow = 403
    OF__cellPosCol = 404
    OF__font = 405
    OF__mode = 406
    OF__fgColor = 80
    OF__bgColor = 9
    OF__width = 292
    OF__height = 407
    OF__flags = 409
    OF__glyphIndex = 408


class OBJ_BROWSE_OPTIONS_TAGS(ENUM_TAGS):
    OF__pattern = 0
    OF__matchPattern = 1
    OF__mode = 2
    OF__startPath = 3
    OF__patternLabel = 4
    OF__buttonLabel = 5


class OBJ_ROW_COL_TAGS(ENUM_TAGS):
    OF__row = 0
    OF__col = 1


class OBJ_COLOR_PAIR_TAGS(ENUM_TAGS):
    OF__value = 0
    OF__color = 1


class OBJ_TREE_NODE_TAGS(ENUM_TAGS):
    OF__nodeFlags = 0
    OF__tag = 1
    OF__indentLevel = 2


class OBJ_TAB_INFO_ITEM_TAGS(ENUM_TAGS):
    OF__itemFlags = 0
    OF__textWidth = 1
    OF__caption = 2
    OF__fg = 3
    OF__bg = 4


class OBJ_PAGE_INFO_ITEM_TAGS(ENUM_TAGS):
    OF__itemFlags = 0
    OF__caption = 1
    OF__fg = 2
    OF__bg = 3


class OBJ_MAPPED_POINT_TAGS(ENUM_TAGS):
    OF__y = 0
    OF__x = 1


class OBJ_PLOT_DATA_TAGS(ENUM_TAGS):
    OF__color = 0
    OF__flags = 1
    OF__interp = 2
    OF__lineStyle = 3
    OF__pointStyle = 4
    OF__fillStyle = 5
    OF__width = 6
    OF__plotFlags = 7
    OF__plotName = 8
    OF__cnt = 9
    OF__mapped = 10
    OF__pointColor = 11
    OF__fillColor = 12
    OF__xScale = 13
    OF__yScale = 14
    OF__mBits = 15
    OF__gtoIndex = 16
    OF__unused = 17
    OF__fxpWordLength = 18
    OF__fxpIntegerLength = 19
    OF__fxpIsSigned = 20
    OF__fxpFracDigits = 21
    OF__fxpStyle = 22


class OBJ_CURSOR_DATA_TAGS(ENUM_TAGS):
    OF__flags = 0
    OF__plot = 1
    OF__glyph = 2
    OF__lineStyle = 3
    OF__lineWidth = 4
    OF__color = 5
    OF__name = 6
    OF__x = 7
    OF__y = 8
    OF__z = 9
    OF__index = 10
    OF__loc = 11
    OF__font = 12
    OF__mode = 13
    OF__txSize = 14
    OF__txOffset = 15
    OF__active = 16
    OF__port = 17
    OF__xScale = 18
    OF__yScale = 19
    OF__watchPlots = 20
    OF__txOffsetX = 21
    OF__txOffsetY = 22
    OF__loc32 = 23
    OF__txOffset32 = 24


class OBJ_PLOT_IMAGES_TAGS(ENUM_TAGS):
    OF__plotPicBg = 0
    OF__plotPicMg = 1
    OF__plotPicFg = 2


class OBJ_CURS_BUTTONS_REC_TAGS(ENUM_TAGS):
    OF__left = 0
    OF__right = 1
    OF__up = 2
    OF__down = 3


class OBJ_PLOT_LEGEND_DATA_TAGS(ENUM_TAGS):
    OF__name = 0
    OF__menu = 1
    OF__visBool = 2


class OBJ_DIGITAL_BUS_ORG_CLUST_TAGS(ENUM_TAGS):
    OF__arrayHandle = 0
    OF__isBus = 1
    OF__pData = 2


class OBJ_SCALE_LEGEND_DATA_TAGS(ENUM_TAGS):
    OF__name = 0
    OF__autoScaleLock = 1
    OF__autoScale = 2
    OF__formatButton = 3


class OBJ_SCALE_DATA_TAGS(ENUM_TAGS):
    OF__partID = 0
    OF__partOrder = 1
    OF__flags = 2
    OF__gridMaxColor = 3
    OF__gridMinColor = 4
    OF__gridMaxLineStyle = 5
    OF__gridMinLineStyle = 6
    OF__scaleRect = 7
    OF__port = 8
    OF__scaleFlavor = 9


class OBJ_KEY_MAPPING_TAGS(ENUM_TAGS):
    OF__VKey = 0
    OF__CharCode = 1
    OF__Mods = 2
    OF__Obj = 3
    OF__Action = 4


class OBJ_MULTI_DIM_TAGS(ENUM_TAGS):
    OF__multiDimArraySizes = 0
    OF__multiDimArrayElems = 1


class OBJ_GROW_TERM_INFO_TAGS(ENUM_TAGS):
    OF__flags = 0
    OF__termOfst = 1


class OBJ_CONNECTION_TAGS(ENUM_TAGS):
    OF__ConnectionDCO = 0
    OF__ConNum = 1
    OF__Flags = 2
    OF__TermRect = 3


class OBJ_SELECTOR_RANGE_TAGS(ENUM_TAGS):
    OF__start = 0
    OF__end = 1
    OF__startRangeType = 2
    OF__endRangeType = 3
    OF__diagramIdx = 4


class OBJ_EVENT_SPEC_TAGS(ENUM_TAGS):
    OF__diagramIdx = 0
    OF__source = 1
    OF__regFlags = 2
    OF__eSource = 3
    OF__type = 4
    OF__eFlags = 5
    OF__ddoUID = 6
    OF__menuTag = 7
    OF__dynIndex = 8


class OBJ_BASE_TABLE_CONTROL_FLAGS(enum.IntEnum):
    """ Flags for baseTableControl
    """
    BTCUnused0		= 0
    EditableHeaders	= 1
    MoveableHeaders	= 2
    MultilineInput	= 3
    NoHorizontalLines = 4
    NoVerticalLines	= 5
    GlyphsInAllCells = 6
    NoEmptyGlyphSpace = 7
    BTCUnused8		= 8
    AutosizeRows	= 9
    SmoothScrolling	= 10
    TwoDimScrollbars = 11
    BTCUnused12		= 12
    HasDefaultHeight = 13
    HasDefaultWidth	= 14
    BTCBit15		= 15


class OBJ_BASE_LISTBOX_FLAGS(enum.IntEnum):
    """ Flags for baseListbox
    """
    NoZeroSelection	= 0
    Multiselect		= 1
    ToggleItem		= 2
    Dragging		= 3
    KbCaseSensitive	= 4
    KbCaseInsensitive = 5
    DisableTracking	= 6
    IsMulticolumn	= 7
    SingleCellSelect = 8
    UseIndent		= 9
    Use16PixelIcon	= 10
    GlyphClickEqDouble = 11
    ShowGlyphs		= 12
    IsArray			= 13
    Unused14		= 14
    UseResourceIcons = 15


class PHONY_ENUM:
    pass

class UNRECOGNIZED_TAG(PHONY_ENUM):
    def __init__(self, tagId):
        self.value = int(tagId)
        self.name = 'OF__Tag{:04X}'.format(tagId)


class UNRECOGNIZED_CLASS(PHONY_ENUM):
    def __init__(self, classId):
        self.value = int(classId)
        self.name = 'Class{:04X}'.format(classId)


class HeapNode(object):
    """ Class for all objects stored in either FP or BD heap

    Used directly for nodes with no data inside, and used as base class for nodes
    which do store some data.
    """
    def __init__(self, vi, po, parentNode, tagEn, scopeInfo):
        """ Creates new Heap Node object.
        """
        self.vi = vi
        self.po = po
        self.attribs = {}
        self.content = None
        self.format = "inline"
        self.parent = parentNode
        self.tagEn = tagEn
        self.scopeInfo = scopeInfo
        self.childs = []
        self.raw_data = None
        # Whether RAW data has been updated and RSRC parsing is required to update properties
        self.raw_data_updated = False
        # Whether any properties have been updated and preparation of new RAW data is required
        self.parsed_data_updated = False

    def getScopeInfo(self):
        if self.scopeInfo not in set(item.value for item in NODE_SCOPE):
            return self.scopeInfo
        return NODE_SCOPE(self.scopeInfo)

    def parseRSRCContent(self):
        pass

    def parseRSRCData(self, bldata, hasAttrList, sizeSpec):
        attribs = {}
        if hasAttrList != 0:
            count = LVmisc.readVariableSizeFieldU124(bldata)

            if (self.po.verbose > 2):
                print("{:s}: Heap Container start tag='{}' scopeInfo={:d} sizeSpec={:d} attrCount={:d}"\
                  .format(self.vi.src_fname, self.tagEn.name, self.scopeInfo, sizeSpec, count))
            attribs = {}
            for i in range(count):
                atId = LVmisc.readVariableSizeFieldS124(bldata)
                atIntVal = LVmisc.readVariableSizeFieldS24(bldata)
                atVal = attributeValueIntToIntOrEn(atId, atIntVal, self)
                attribs[atId] = atVal
        else:
            if (self.po.verbose > 2):
                print("{:s}: Heap Container tag='{}' scopeInfo={:d} sizeSpec={:d} noAttr"\
                  .format(self.vi.src_fname, self.tagEn.name, self.scopeInfo, sizeSpec))

        # Read size of data, unless sizeSpec identifies the size completely
        contentSize = 0;
        if sizeSpec == 0 or sizeSpec == 7: # bool data
            contentSize = 0
        elif sizeSpec <= 4:
            contentSize = sizeSpec
        elif sizeSpec == 6:
            contentSize = LVmisc.readVariableSizeFieldU124(bldata)
        else:
            contentSize = 0
            eprint("{:s}: Warning: Unexpected value of SizeSpec={:d} on heap"\
              .format(self.vi.src_fname, sizeSpec))

        content = None
        if contentSize > 0:
            content = bldata.read(contentSize)
        elif sizeSpec == 0:
            content = False
        elif sizeSpec == 7:
            content = True

        self.attribs = attribs
        self.content = content

        try:
            self.parseRSRCContent()
        except Exception as e:
            self.format = "hex"
            eprint("{:s}: Warning: Heap Container tag='{}' parse exception: {}."\
                .format(self.vi.src_fname,self.tagEn.name,str(e)))
            HeapNode.parseRSRCContent(self)

    def getData(self):
        bldata = BytesIO(self.raw_data)
        return bldata

    def setData(self, data_buf, incomplete=False):
        self.raw_data = data_buf
        self.size = len(self.raw_data)
        if not incomplete:
            self.raw_data_updated = True

    def updateContent(self):
        pass

    def updateData(self, avoid_recompute=False):

        if avoid_recompute and self.raw_data_updated:
            return # If we have strong raw data, and new one will be weak, then leave the strong buffer

        if self.format == "inline":
            self.updateContent()

        data_buf = b''

        hasAttrList = 1 if len(self.attribs) > 0 else 0

        if hasAttrList != 0:
            data_buf += LVmisc.prepareVariableSizeFieldU124(len(self.attribs))
            for atId, atVal in self.attribs.items():
                if isinstance(atVal, enum.Enum) or isinstance(atVal, PHONY_ENUM):
                    atVal = atVal.value
                data_buf += LVmisc.prepareVariableSizeFieldS124(atId)
                data_buf += LVmisc.prepareVariableSizeFieldS24(atVal)

        if self.content is None:
            sizeSpec = 0
        elif isinstance(self.content, bool):
            if self.content == True:
                sizeSpec = 7
            else:
                sizeSpec = 0
        elif isinstance(self.content, (bytes, bytearray,)):
            if len(self.content) <= 4:
                sizeSpec = len(self.content)
            else:
                sizeSpec = 6
        else:
            eprint("{:s}: Warning: Unexpected type of tag content on heap"\
              .format(self.vi.src_fname))

        if sizeSpec == 6:
            data_buf += LVmisc.prepareVariableSizeFieldU124(len(self.content))

        if sizeSpec in [1,2,3,4,6]:
            data_buf += self.content

        if (self.po.verbose > 2):
            print("{:s}: Heap Container tag='{}' scopeInfo={:d} sizeSpec={:d} attrCount={:d}"\
              .format(self.vi.src_fname, self.tagEn.name, self.scopeInfo, sizeSpec, len(self.attribs)))

        if (self.tagEn.value + 31) < 1023:
            rawTagId = self.tagEn.value + 31
        else:
            rawTagId = 1023

        data_head = bytearray(2)
        data_head[0] = ((sizeSpec & 7) << 5) | ((hasAttrList & 1) << 4) | ((self.scopeInfo & 3) << 2) | ((rawTagId >> 8) & 3)
        data_head[1] = (rawTagId & 0xFF)
        if rawTagId == 1023:
            data_head += int(self.tagEn.value).to_bytes(4, byteorder='big', signed=True)

        self.setData(data_head+data_buf, incomplete=avoid_recompute)

    def prepareContentXML(self, fname_base):
        tagText = None
        if self.content is not None:
            if isinstance(self.content, (bytes, bytearray)):
                tagText = self.content.hex().upper()
            elif self.content is not False:
                tagText = str(self.content)
        return tagText

    def exportXML(self, elem, scopeInfo, fname_base):
        if self.format != "inline":
            elem.set("Format", self.format)
        for atId, atVal in self.attribs.items():
            propName = attributeIdToName(atId)
            elem.set(propName, attributeValueIntOrEnToStr(atId, atVal, self.parent))

        tagText = self.prepareContentXML(fname_base)
        ET.safe_store_element_text(elem, tagText)

        if scopeInfo == NODE_SCOPE.TagClose:
            # Our automativc algorithm sometimes gives TagLeaf instead of TagOpen; this code
            # makes sure such anomalies are stored in XML and re-created while reading XML
            # The code is executed when closing the tag - all properties of the Element are
            # already set at this point.
            scopeInfoAuto = autoScopeInfoFromET(elem)
            scopeInfoForce = NODE_SCOPE.TagOpen
            if scopeInfoAuto != scopeInfoForce:
                if (self.po.verbose > 1):
                    print("{}: Tag '{}' automatic scopeInfo={:d} bad, forcing {:d}"\
                      .format(self.vi.src_fname, elem.tag, scopeInfoAuto.value, scopeInfoForce.value))
                elem.set("ScopeInfo", "{:d}".format(scopeInfoForce.value))
        pass

    def initContentWithXML(self, tagText):
        if tagText == "":
            content  = None
        elif tagText in ["True", "False"]:
            content  = (tagText == "True")
        else:
            content  = bytes.fromhex(tagText)
        self.content = content

    def initWithXML(self, elem):
        attribs = {}
        for name, value in elem.attrib.items():
            if name in ("ScopeInfo",): # Attribs to ignore at this point
                continue
            if name == "Format":
                if value in ("inline","hex",):
                    self.format = value
                continue
            atId = attributeNameToId(name)
            if atId is None:
                raise AttributeError("Unrecognized attrib name in heap XML, '{}'".format(name))
            atVal = attributeValueStrToIntOrEn(atId, value)
            if atVal is None:
                raise AttributeError("Unrecognized attrib value in heap XML for name '{}'".format(name))
            attribs[atId] = atVal
        self.attribs = attribs

        if elem.text is not None:
            tagText = elem.text.strip()
        else:
            tagText = ""

        if self.format == "inline":
            self.initContentWithXML(tagText)
        elif self.format == "hex":
            HeapNode.initContentWithXML(self, tagText)
        else:
            raise AttributeError("Unsupported value of Format attrib in heap XML")
        pass

    def initWithXMLLate(self):
        """ Late part of Heap Node loading from XML file

        Can access some basic data from other blocks and sections.
        Useful only if properties needs an update after other blocks are accessible.
        """
        pass

    def findChild(self, tagEn, index=0):
        for node in self.childs:
            if node.tagEn != tagEn:
                continue
            if index > 0:
                index -= 1
            else:
                return node
        return None


class HeapNodeStdInt(HeapNode):
    """ Class for Heap Nodes which store standard size integer value
    """
    def __init__(self, *args, btlen=-1, signed=True):
        super().__init__(*args)
        self.btlen = btlen
        self.signed = signed
        self.value = 0

    def parseRSRCContent(self):
        if not isinstance(self.content, (bytes, bytearray,)):
            raise AttributeError("Tag '{}' of Class '{}' has no byte-like content"\
              .format(self.tagEn.name, parentTopClassEn(self.parent).name))
        bldata = BytesIO(self.content)
        if self.btlen < 0:
            btlen = len(self.content)
        else:
            btlen = self.btlen
        self.value = int.from_bytes(bldata.read(btlen), byteorder='big', signed=self.signed)

    def updateContent(self):
        if self.btlen < 0:
            btlen = 1
            for cklen in range(7,0,-1):
                if self.value < -(2**(cklen*8-1)) or self.value > (2**(cklen*8-1))-1:
                    btlen = cklen+1
                    break
        else:
            btlen = self.btlen
        self.content = int(self.value).to_bytes(btlen, byteorder='big', signed=self.signed)

    def prepareContentXML(self, fname_base):
        return "{:d}".format(self.value)

    def initContentWithXML(self, tagText):
        tagParse = re.match("^([0-9A-Fx-]+)$", tagText)
        if tagParse is None:
            raise AttributeError("Tag '{}' of Class '{}' has content with bad Integer value"\
              .format(self.tagEn.name, parentTopClassEn(self.parent).name))
        self.value = int(tagParse[1], 0)
        self.updateContent()


class HeapNodeTypeId(HeapNodeStdInt):
    """ Class for Heap Nodes which store integer representing Heap TypeID
    """
    def __init__(self, *args):
        super().__init__(*args, btlen=-1, signed=True)

    def prepareContentXML(self, fname_base):
        return "TypeID({:d})".format(self.value)

    def initContentWithXML(self, tagText):
        tagParse = re.match("^TypeID\(([0-9A-Fx-]+)\)$", tagText)
        if tagParse is None:
            raise AttributeError("Tag '{}' of Class '{}' has content with bad TypeID value"\
              .format(self.tagEn.name, parentTopClassEn(self.parent).name))
        self.value = int(tagParse[1], 0)
        self.updateContent()


class HeapNodeRect(HeapNode):
    """ Class for Heap Nodes which store rectangle data - four coords
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.left = 0
        self.top = 0
        self.right = 0
        self.bottom = 0

    def parseRSRCContent(self):
        bldata = BytesIO(self.content)
        self.left = int.from_bytes(bldata.read(2), byteorder='big', signed=True)
        self.top = int.from_bytes(bldata.read(2), byteorder='big', signed=True)
        self.right = int.from_bytes(bldata.read(2), byteorder='big', signed=True)
        self.bottom = int.from_bytes(bldata.read(2), byteorder='big', signed=True)

    def updateContent(self):
        content = b''
        content += int(self.left).to_bytes(2, byteorder='big', signed=True)
        content += int(self.top).to_bytes(2, byteorder='big', signed=True)
        content += int(self.right).to_bytes(2, byteorder='big', signed=True)
        content += int(self.bottom).to_bytes(2, byteorder='big', signed=True)
        self.content = content

    def prepareContentXML(self, fname_base):
        return "({:d}, {:d}, {:d}, {:d})".format(self.left, self.top, self.right, self.bottom)

    def initContentWithXML(self, tagText):
        tagParse = re.match("^\([ ]*([0-9A-Fx-]+),[ ]*([0-9A-Fx-]+),[ ]*([0-9A-Fx-]+),[ ]*([0-9A-Fx-]+)[ ]*\)$", tagText)
        if tagParse is None:
            raise AttributeError("Tag '{}' of Class '{}' has content which does not match Rect definition"\
              .format(self.tagEn.name, parentTopClassEn(self.parent).name))
        self.left = int(tagParse[1], 0)
        self.top = int(tagParse[2], 0)
        self.right = int(tagParse[3], 0)
        self.bottom = int(tagParse[4], 0)
        self.updateContent()


class HeapNodePoint(HeapNode):
    """ Class for Heap Nodes which store point data - two coords
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.x = 0
        self.y = 0

    def parseRSRCContent(self):
        bldata = BytesIO(self.content)
        self.x = int.from_bytes(bldata.read(2), byteorder='big', signed=True)
        self.y = int.from_bytes(bldata.read(2), byteorder='big', signed=True)

    def updateContent(self):
        content = b''
        content += int(self.x).to_bytes(2, byteorder='big', signed=True)
        content += int(self.y).to_bytes(2, byteorder='big', signed=True)
        self.content = content

    def prepareContentXML(self, fname_base):
        return "({:d}, {:d})".format(self.y, self.x)

    def initContentWithXML(self, tagText):
        tagParse = re.match("^\([ ]*([0-9A-Fx-]+),[ ]*([0-9A-Fx-]+)[ ]*\)$", tagText)
        if tagParse is None:
            raise AttributeError("Tag '{}' of Class '{}' has content which does not match Point definition"\
              .format(self.tagEn.name, parentTopClassEn(self.parent).name))
        self.y = int(tagParse[1], 0)
        self.x = int(tagParse[2], 0)
        self.updateContent()


class HeapNodeString(HeapNode):
    """ Class for Heap Nodes which store string data
    """
    def __init__(self, *args):
        super().__init__(*args)

    def prepareContentXML(self, fname_base):

        if self.content is None or isinstance(self.content, bool):
            return "[NULL]"
        valText = self.content.decode(self.vi.textEncoding)
        return "\"{:s}\"".format(valText)

    def initContentWithXML(self, tagText):
        tagParse = re.match("^\"(.*)\"$", tagText, re.MULTILINE|re.DOTALL)
        if tagParse is not None:
            # The text may have been in cdata tag, there is no way to know; so unescape anyway
            valText = ET.unescape_cdata_control_chars(tagParse[1])
            self.content = valText.encode(self.vi.textEncoding)
        elif tagText == "[NULL]":
            self.content = False
        else:
            raise AttributeError("Tag '{}' of Class '{}' has content with bad String value '{}'"\
              .format(self.tagEn.name, parentTopClassEn(self.parent).name, tagText))
        pass


class HeapNodePStrList(HeapNode):
    """ Class for Heap Nodes which store list of strings with one-byte lengths
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.values = []

    def parseRSRCContent(self):
        if not isinstance(self.content, (bytes, bytearray,)):
            raise AttributeError("Tag '{}' of Class '{}' has no byte-like content"\
              .format(self.tagEn.name, parentTopClassEn(self.parent).name))
        bldata = BytesIO(self.content)
        values = []
        while (True):
            btcount = bldata.read(1)
            if len(btcount) < 1: break
            count = int.from_bytes(btcount, byteorder='big', signed=False)
            val = bldata.read(count)
            values.append(val)
            if len(val) < count:
                raise AttributeError("Tag '{}' of Class '{}' has truncated strings list in content"\
                  .format(self.tagEn.name, parentTopClassEn(self.parent).name))
        self.values = values

    def updateContent(self):
        content = b''
        for val in self.values:
            content += int(len(val)).to_bytes(1, byteorder='big', signed=False)
            content += val
        self.content = content

    def prepareContentXML(self, fname_base):
        strval = "({:d})".format(len(self.values))
        for val in self.values:
            valText = val.decode(self.vi.textEncoding)
            valText = ET.escape_cdata_custom_chars(valText, ( ord("\""), ) )
            strval += "\"{:s}\"".format(valText)
        return strval

    def initContentWithXML(self, tagText):
        count = None
        tagParse = re.match(r"^[(]([0-9A-Fx]+)[)](\".*\")$", tagText, re.MULTILINE|re.DOTALL)
        if tagParse is not None:
            count = int(tagParse[1], 0)
        if count is None:
            raise AttributeError("Tag '{}' of Class '{}' has content with no string list length"\
              .format(self.tagEn.name, parentTopClassEn(self.parent).name))
        values = []
        tagParse = re.match(r"^[(][0-9A-Fx]+[)]" + (r"\"([^\"]*)\"" * count) + r"$", tagText, re.MULTILINE|re.DOTALL)
        if tagParse is None:
            raise AttributeError("Tag '{}' of Class '{}' has content with too few strings"\
              .format(self.tagEn.name, parentTopClassEn(self.parent).name))
        for valText in tagParse.groups():
            # The text may have been in cdata tag, there is no way to know; so unescape anyway
            valText = ET.unescape_cdata_control_chars(valText)
            valText = ET.unescape_cdata_custom_chars(valText, ( ord("\""), ) )
            val = valText.encode(self.vi.textEncoding)
            values.append(val)
        self.values = values
        self.updateContent()


class HeapNodeBool(HeapNode):
    """ Class for Heap Nodes which store boolean value
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.value = False

    def parseRSRCContent(self):
        self.value = bool(self.content)

    def updateContent(self):
        self.content = self.value

    def prepareContentXML(self, fname_base):
        return str(self.value)

    def initContentWithXML(self, tagText):
        tagParse = re.match("^(True|False)$", tagText)
        if tagParse is None:
            raise AttributeError("Tag '{}' of Class '{}' has content with bad boolean value"\
              .format(self.tagEn.name, parentTopClassEn(self.parent).name))
        self.value = (tagParse[1] == "True")
        self.updateContent()


class HeapNodeTDDataFill(HeapNode):
    """ Value within heap which represents DataFill for given TD

    This node gets data before TD is available, so stores it in raw or string form.
    Then, when it becomes possible to parse that data, it is converted to value of proper type.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.td = None
        self.value = None
        self.raw_str = None

    def setTD(self, td):
        if (self.po.verbose > 2):
            print("{:s}: Tag '{}' of Class {:s} setting TD {}"\
              .format(self.vi.src_fname, self.tagEn.name, type(self).__name__, td))
        self.td = td

    def findAndStoreTD(self):
        if self.parent is not None:
            typeDescNode = self.parent.findChild(OBJ_FIELD_TAGS.OF__typeDesc)
        else:
            typeDescNode = None
        if typeDescNode is not None:
            heapTypeId = typeDescNode.value
        else:
            heapTypeId = 0
        td = self.vi.getHeapTD(heapTypeId)
        self.setTD(td)

    @staticmethod
    def shrinkRepeatedBits(btval):
        if len(btval) < 2:
            return btval
        i = 0
        if btval[0] == 0x0:
            while i < len(btval)-1:
                if btval[i] == 0x0 and btval[i+1] & 0x80 == 0x0:
                    i += 1
                    continue
                break
        elif btval[0] == 0xff:
            while i < len(btval)-1:
                if btval[i] == 0xff and btval[i+1] & 0x80 == 0x80:
                    i += 1
                    continue
                break
        return btval[i:]

    @staticmethod
    def parseRSRCContentDirect(bldata, tdType):
        val = None
        from LVdatatype import TD_FULL_TYPE
        # Signed integer values are sign-extended automatically and no further processing is needed
        if tdType in (TD_FULL_TYPE.NumInt8,):
            val = int.from_bytes(bldata.read(1), byteorder='big', signed=True)
        elif tdType in (TD_FULL_TYPE.NumInt16,):
            val = int.from_bytes(bldata.read(2), byteorder='big', signed=True)
        elif tdType in (TD_FULL_TYPE.NumInt32,):
            val = int.from_bytes(bldata.read(4), byteorder='big', signed=True)
        elif tdType in (TD_FULL_TYPE.NumInt64,):
            val = int.from_bytes(bldata.read(8), byteorder='big', signed=True)
        # Unsigned integers need to be sign-extended as well, so pretend they're signed at first
        elif tdType in (TD_FULL_TYPE.NumUInt8,TD_FULL_TYPE.UnitUInt8,):
            val = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        elif tdType in (TD_FULL_TYPE.NumUInt16,TD_FULL_TYPE.UnitUInt16,):
            tmpbt = int.from_bytes(bldata.read(2), byteorder='big', signed=True).to_bytes(2, byteorder='big', signed=True)
            val = int.from_bytes(tmpbt, byteorder='big', signed=False)
        elif tdType in (TD_FULL_TYPE.NumUInt32,TD_FULL_TYPE.UnitUInt32,):
            tmpbt = int.from_bytes(bldata.read(4), byteorder='big', signed=True).to_bytes(4, byteorder='big', signed=True)
            val = int.from_bytes(tmpbt, byteorder='big', signed=False)
        elif tdType in (TD_FULL_TYPE.NumUInt64,):
            tmpbt = int.from_bytes(bldata.read(8), byteorder='big', signed=True).to_bytes(8, byteorder='big', signed=True)
            val = int.from_bytes(tmpbt, byteorder='big', signed=False)
        # Float values have special reaing routines
        elif tdType in (TD_FULL_TYPE.NumFloat32,TD_FULL_TYPE.UnitFloat32,):
            val = struct.unpack('>f', bldata.read(4))[0]
        elif tdType in (TD_FULL_TYPE.NumFloat64,TD_FULL_TYPE.UnitFloat64,):
            val = struct.unpack('>d', bldata.read(8))[0]
        elif tdType in (TD_FULL_TYPE.NumFloatExt,TD_FULL_TYPE.UnitFloatExt,):
            val = LVmisc.readQuadFloat(bldata)
        return val

    @staticmethod
    def prepareRSRCContentDirect(val, tdType):
        content = None
        from LVdatatype import TD_FULL_TYPE
        # Signed integer values
        if tdType in (TD_FULL_TYPE.NumInt8,):
            tmpbt = int(val).to_bytes(1, byteorder='big', signed=True)
            content = HeapNodeTDDataFill.shrinkRepeatedBits(tmpbt)
        elif tdType in (TD_FULL_TYPE.NumInt16,):
            tmpbt = int(val).to_bytes(2, byteorder='big', signed=True)
            content = HeapNodeTDDataFill.shrinkRepeatedBits(tmpbt)
        elif tdType in (TD_FULL_TYPE.NumInt32,):
            tmpbt = int(val).to_bytes(4, byteorder='big', signed=True)
            content = HeapNodeTDDataFill.shrinkRepeatedBits(tmpbt)
        elif tdType in (TD_FULL_TYPE.NumInt64,):
            tmpbt = int(val).to_bytes(8, byteorder='big', signed=True)
            content = HeapNodeTDDataFill.shrinkRepeatedBits(tmpbt)
        # Unsigned integer values
        elif tdType in (TD_FULL_TYPE.NumUInt8,TD_FULL_TYPE.UnitUInt8,):
            tmpbt = int(val).to_bytes(1, byteorder='big', signed=False)
            content = HeapNodeTDDataFill.shrinkRepeatedBits(tmpbt)
        elif tdType in (TD_FULL_TYPE.NumUInt16,TD_FULL_TYPE.UnitUInt16,):
            tmpbt = int(val).to_bytes(2, byteorder='big', signed=False)
            content = HeapNodeTDDataFill.shrinkRepeatedBits(tmpbt)
        elif tdType in (TD_FULL_TYPE.NumUInt32,TD_FULL_TYPE.UnitUInt32,):
            tmpbt = int(val).to_bytes(4, byteorder='big', signed=False)
            content = HeapNodeTDDataFill.shrinkRepeatedBits(tmpbt)
        elif tdType in (TD_FULL_TYPE.NumUInt64,):
            tmpbt = int(val).to_bytes(8, byteorder='big', signed=False)
            content = HeapNodeTDDataFill.shrinkRepeatedBits(tmpbt)
        # Float values
        elif tdType in (TD_FULL_TYPE.NumFloat32,TD_FULL_TYPE.UnitFloat32,):
            tmpbt = struct.pack('>f', val)
            content = tmpbt
        elif tdType in (TD_FULL_TYPE.NumFloat64,TD_FULL_TYPE.UnitFloat64,):
            tmpbt = struct.pack('>d', val)
            content = tmpbt
        elif tdType in (TD_FULL_TYPE.NumFloatExt,TD_FULL_TYPE.UnitFloatExt,):
            tmpbt = LVmisc.prepareQuadFloat(val)
            content = tmpbt
        return content

    def parseRSRCContentTree(self):
        ret = False
        tdType = self.td.fullType()
        from LVdatatype import TD_FULL_TYPE
        if tdType in (TD_FULL_TYPE.NumComplex64,TD_FULL_TYPE.UnitComplex64,\
              TD_FULL_TYPE.NumComplex128,TD_FULL_TYPE.UnitComplex128,\
              TD_FULL_TYPE.NumComplexExt,TD_FULL_TYPE.UnitComplexExt,):
            # Real and imaginary part will be filled within children
            ret = True
        return ret

    def prepareRSRCContentTree(self):
        ret = False
        tdType = self.td.fullType()
        from LVdatatype import TD_FULL_TYPE
        if tdType in (TD_FULL_TYPE.NumComplex64,TD_FULL_TYPE.UnitComplex64,\
              TD_FULL_TYPE.NumComplex128,TD_FULL_TYPE.UnitComplex128,\
              TD_FULL_TYPE.NumComplexExt,TD_FULL_TYPE.UnitComplexExt,):
            # Real and imaginary part will be prepared within children
            ret = True
        return ret

    def parseRSRCContent(self):
        if self.scopeInfo == NODE_SCOPE.TagClose:
            return
        if self.td is None:
            self.findAndStoreTD()
        # Do nothing if we don't have TD set
        if self.td is None:
            self.value = None
            self.format = "hex"
            return
        ret = False
        tdType = self.td.fullType()
        # We have two types of content, depending on TD type: text value directly in current tag, or in children
        if isinstance(self.content, (bytes, bytearray,)):
            bldata = BytesIO(self.content)
            val = self.parseRSRCContentDirect(bldata, tdType)
            if val is not None:
                self.value = val
                ret = True
        if not ret:
            ret = self.parseRSRCContentTree()
        if not ret:
            raise AttributeError("Tag '{}' of Class '{}' could not parse its TypeDesc type={} dependent content"\
              .format(self.tagEn.name, parentTopClassEn(self.parent).name,tdType))
        self.format = "inline"

    def updateContent(self):
        if self.td is None:
            return
        ret = False
        tdType = self.td.fullType()
        content = self.prepareRSRCContentDirect(self.value, tdType)
        if content is not None:
            self.content = content
            ret = True
        if not ret:
            ret = self.prepareRSRCContentTree()
        if not ret:
            raise AttributeError("Tag '{}' of Class '{}' could not generate TypeDesc type={} dependent content"\
              .format(self.tagEn.name, parentTopClassEn(self.parent).name,tdType))

    def prepareContentXML(self, fname_base):
        if self.format == "hex" or self.scopeInfo == NODE_SCOPE.TagClose:
            return HeapNode.prepareContentXML(self, fname_base)

        text = ""
        ret = False
        tdType = self.td.fullType()
        from LVdatatype import TD_FULL_TYPE
        tmpText = LVdatatype.numericToStringUnequivocal(self.value, tdType)
        if tmpText is not None:
            text = tmpText
            ret = True
        if not ret:
            if tdType in (TD_FULL_TYPE.NumComplex64,TD_FULL_TYPE.UnitComplex64,\
              TD_FULL_TYPE.NumComplex128,TD_FULL_TYPE.UnitComplex128,\
              TD_FULL_TYPE.NumComplexExt,TD_FULL_TYPE.UnitComplexExt,):
                ret = True # real content is stored in children
        if not ret:
            raise AttributeError("Tag '{}' of Class '{}' could not generate TypeDesc type={} XML text"\
              .format(self.tagEn.name, parentTopClassEn(self.parent).name,tdType))

        return text

    def initContentWithXML(self, tagText):
        self.raw_str = tagText
        # Further initialization will be done in late function below

    def initWithXMLLate(self):
        if self.scopeInfo == NODE_SCOPE.TagClose:
            return
        if self.format == "hex":
            # in this case, the content was filled already
            return
        self.findAndStoreTD()
        if self.td is None:
            # if we have no TD, we can't do anything with the string
            raise AttributeError("Tag '{}' of Class '{}' has non-hex content, but cannot get related TypeDesc"\
              .format(self.tagEn.name, parentTopClassEn(self.parent).name))
        text = self.raw_str
        self.raw_str = None
        ret = False
        val = None
        tdType = self.td.fullType()
        from LVdatatype import TD_FULL_TYPE
        val = LVdatatype.stringUnequivocalToNumeric(text, tdType)
        if val is not None:
            ret = True
        elif tdType in (TD_FULL_TYPE.NumComplex64,TD_FULL_TYPE.UnitComplex64,\
              TD_FULL_TYPE.NumComplex128,TD_FULL_TYPE.UnitComplex128,\
              TD_FULL_TYPE.NumComplexExt,TD_FULL_TYPE.UnitComplexExt,):
            ret = True # real content is stored in children
        if ret:
            self.value = val
        else:
            raise AttributeError("Tag '{}' of Class '{}' could not parse TypeDesc type={} XML text"\
              .format(self.tagEn.name, parentTopClassEn(self.parent).name,tdType))
        self.updateContent()


class HeapNodeTDDataFillLeaf(HeapNode):
    """ Leaf of a value within heap which represents DataFill for given TD

    This node gets content before TD is available, so stores it in raw or string form.
    Then, when parent node receives the TD reference, the content is converted to value of proper type.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.value = None
        self.raw_str = None

    @staticmethod
    def parseRSRCContentDirect(bldata, tdType):
        val = None
        from LVdatatype import TD_FULL_TYPE
        if tdType in (TD_FULL_TYPE.NumComplex64,TD_FULL_TYPE.UnitComplex64,\
              TD_FULL_TYPE.NumComplex128,TD_FULL_TYPE.UnitComplex128,\
              TD_FULL_TYPE.NumComplexExt,TD_FULL_TYPE.UnitComplexExt,):
            if tdType in (TD_FULL_TYPE.NumComplex64,TD_FULL_TYPE.UnitComplex64,):
                val = HeapNodeTDDataFill.parseRSRCContentDirect(bldata, TD_FULL_TYPE.NumFloat32)
            elif tdType in (TD_FULL_TYPE.NumComplex128,TD_FULL_TYPE.UnitComplex128,):
                val = HeapNodeTDDataFill.parseRSRCContentDirect(bldata, TD_FULL_TYPE.NumFloat64)
            elif tdType in (TD_FULL_TYPE.NumComplexExt,TD_FULL_TYPE.UnitComplexExt,):
                val = HeapNodeTDDataFill.parseRSRCContentDirect(bldata, TD_FULL_TYPE.NumFloatExt)
        return val

    def parseRSRCContent(self):
        if self.scopeInfo == NODE_SCOPE.TagClose:
            return
        # Do nothing if we don't have TD set
        if self.parent.td is None or self.format == "hex":
            self.value = None
            self.format = "hex"
            return
        ret = False
        if isinstance(self.content, (bytes, bytearray,)):
            bldata = BytesIO(self.content)
            val = self.parseRSRCContentDirect(bldata, self.parent.td.fullType())
            if val is not None:
                self.value = val
                ret = True
        if not ret:
            raise AttributeError("Tag '{}' of Class '{}' could not parse its TypeDesc dependent content"\
              .format(self.tagEn.name, parentTopClassEn(self.parent).name))
        self.format = "inline"

    def updateContent(self):
        if self.parent.td is None:
            return
        ret = False
        tdType = self.parent.td.fullType()
        from LVdatatype import TD_FULL_TYPE
        content = None
        try:
            if tdType in (TD_FULL_TYPE.NumComplex64,TD_FULL_TYPE.UnitComplex64,):
                content = HeapNodeTDDataFill.prepareRSRCContentDirect(self.value, TD_FULL_TYPE.NumFloat32)
            elif tdType in (TD_FULL_TYPE.NumComplex128,TD_FULL_TYPE.UnitComplex128,):
                content = HeapNodeTDDataFill.prepareRSRCContentDirect(self.value, TD_FULL_TYPE.NumFloat64)
            elif tdType in (TD_FULL_TYPE.NumComplexExt,TD_FULL_TYPE.UnitComplexExt,):
                content = HeapNodeTDDataFill.prepareRSRCContentDirect(self.value, TD_FULL_TYPE.NumFloatExt)
            if content is not None:
                self.content = content
                ret = True
            if not ret:
                raise AttributeError("Failed to generate TypeDesc type={} dependent content"\
                  .format(tdType))
        except Exception as e:
            raise AttributeError("Tag '{}' of Class '{}' failed to update binary content: {}"\
              .format(self.tagEn.name, parentTopClassEn(self.parent).name, str(e)))


    def prepareContentXML(self, fname_base):
        if self.format == "hex" or self.scopeInfo == NODE_SCOPE.TagClose:
            return HeapNode.prepareContentXML(self, fname_base)

        text = ""
        ret = False
        tdType = self.parent.td.fullType()
        from LVdatatype import TD_FULL_TYPE
        if tdType in (TD_FULL_TYPE.NumComplex64,TD_FULL_TYPE.UnitComplex64,):
            tmpText = LVdatatype.numericToStringUnequivocal(self.value, TD_FULL_TYPE.NumFloat32)
            if tmpText is not None:
                text = tmpText
                ret = True
        elif tdType in (TD_FULL_TYPE.NumComplex128,TD_FULL_TYPE.UnitComplex128,):
            tmpText = LVdatatype.numericToStringUnequivocal(self.value, TD_FULL_TYPE.NumFloat64)
            if tmpText is not None:
                text = tmpText
                ret = True
        elif tdType in (TD_FULL_TYPE.NumComplexExt,TD_FULL_TYPE.UnitComplexExt,):
            tmpText = LVdatatype.numericToStringUnequivocal(self.value, TD_FULL_TYPE.NumFloatExt)
            if tmpText is not None:
                text = tmpText
                ret = True
        if not ret:
            raise AttributeError("Tag '{}' of Class '{}' could not generate TypeDesc type={} XML text"\
              .format(self.tagEn.name, parentTopClassEn(self.parent).name,tdType))

        return text

    def initContentWithXML(self, tagText):
        self.raw_str = tagText
        # Further initialization will be done in late function below

    def initWithXMLLate(self):
        if self.scopeInfo == NODE_SCOPE.TagClose:
            return
        if self.format == "hex":
            # in this case, the content was filled already
            return
        if self.parent.td is None:
            # if we have no TD, we can't do anything with the string
            raise AttributeError("Tag '{}' of Class '{}' has non-hex content, but cannot get related TypeDesc"\
              .format(self.tagEn.name, parentTopClassEn(self.parent).name))
        text = self.raw_str
        self.raw_str = None
        val = None
        try:
            tdType = self.parent.td.fullType()
            from LVdatatype import TD_FULL_TYPE
            if tdType in (TD_FULL_TYPE.NumComplex64,TD_FULL_TYPE.UnitComplex64,):
                val = LVdatatype.stringUnequivocalToNumeric(text, TD_FULL_TYPE.NumFloat32)
            elif tdType in (TD_FULL_TYPE.NumComplex128,TD_FULL_TYPE.UnitComplex128,):
                val = LVdatatype.stringUnequivocalToNumeric(text, TD_FULL_TYPE.NumFloat64)
            elif tdType in (TD_FULL_TYPE.NumComplexExt,TD_FULL_TYPE.UnitComplexExt,):
                val = LVdatatype.stringUnequivocalToNumeric(text, TD_FULL_TYPE.NumFloatExt)
            else:
                raise RuntimeError("Class {} used for unexpected type {}"\
                  .format(type(self).__name__, tdType))
            if val is not None:
                self.value = val
            else:
                raise AttributeError("Class {} got content with with bad value"\
                  .format(type(self).__name__))
        except Exception as e:
            raise AttributeError("Tag '{}' of Class '{}' failed to init from XML: {}"\
              .format(self.tagEn.name, parentTopClassEn(self.parent).name, str(e)))
        self.updateContent()


CLASS_EN_TO_TAG_LIST_MAPPING = {
    SL_CLASS_TAGS.SL__fontRun: OBJ_FONT_RUN_TAGS,
    SL_CLASS_TAGS.SL__textHair: OBJ_TEXT_HAIR_TAGS,
    SL_CLASS_TAGS.SL__Image: OBJ_IMAGE_TAGS,
    SL_CLASS_TAGS.SL__SubCosm: OBJ_SUBCOSM_TAGS,
    SL_CLASS_TAGS.SL__EmbedObject: OBJ_EMBED_OBJECT_TAGS,
    SL_CLASS_TAGS.SL__SceneView: OBJ_SCENE_GRAPH_TAGS,
    SL_CLASS_TAGS.SL__SceneColor: OBJ_SCENE_COLOR_TAGS,
    SL_CLASS_TAGS.SL__SceneEyePoint: OBJ_SCENE_EYE_POINT_TAGS,
    SL_CLASS_TAGS.SL__ComplexScalar: OBJ_COMPLEX_SCALAR_TAGS,
    SL_CLASS_TAGS.SL__TableAttribute: OBJ_ATTRIBUTE_LIST_ITEM_TAGS,
    SL_CLASS_TAGS.SL__Time128: OBJ_TIME128_TAGS,
    SL_CLASS_TAGS.SL__BrowseOptions: OBJ_BROWSE_OPTIONS_TAGS,
    SL_CLASS_TAGS.SL__StorageRowCol: OBJ_ROW_COL_TAGS,
    SL_CLASS_TAGS.SL__ColorPair: OBJ_COLOR_PAIR_TAGS,
    SL_CLASS_TAGS.SL__TreeNode: OBJ_TREE_NODE_TAGS,
    SL_CLASS_TAGS.SL__RelativeRowCol: OBJ_ROW_COL_TAGS,
    SL_CLASS_TAGS.SL__TabInfoItem: OBJ_TAB_INFO_ITEM_TAGS,
    SL_CLASS_TAGS.SL__PageInfoItem: OBJ_PAGE_INFO_ITEM_TAGS,
    SL_CLASS_TAGS.SL__MappedPoint: OBJ_MAPPED_POINT_TAGS,
    SL_CLASS_TAGS.SL__PlotData: OBJ_PLOT_DATA_TAGS,
    SL_CLASS_TAGS.SL__CursorData: OBJ_CURSOR_DATA_TAGS,
    SL_CLASS_TAGS.SL__PlotImages: OBJ_PLOT_IMAGES_TAGS,
    SL_CLASS_TAGS.SL__CursorButtonsRec: OBJ_CURS_BUTTONS_REC_TAGS,
    SL_CLASS_TAGS.SL__PlotLegendData: OBJ_PLOT_LEGEND_DATA_TAGS,
    SL_CLASS_TAGS.SL__DigitlaBusOrgClust: OBJ_DIGITAL_BUS_ORG_CLUST_TAGS,
    SL_CLASS_TAGS.SL__ScaleLegendData: OBJ_SCALE_LEGEND_DATA_TAGS,
    SL_CLASS_TAGS.SL__KeyMappingBinding: OBJ_KEY_MAPPING_TAGS,
    SL_CLASS_TAGS.SL__ScaleData: OBJ_SCALE_DATA_TAGS,
    SL_CLASS_TAGS.SL__ConpaneConnection: OBJ_CONNECTION_TAGS,
    SL_CLASS_TAGS.SL__GrowTermInfo: OBJ_GROW_TERM_INFO_TAGS,
    SL_CLASS_TAGS.SL__EventSpec: OBJ_EVENT_SPEC_TAGS,
    SL_CLASS_TAGS.SL__SelectorRange: OBJ_SELECTOR_RANGE_TAGS,
    SL_MULTI_DIM_CLASS_TAGS.SL__multiDimArray: OBJ_MULTI_DIM_TAGS,
}

NODE_RECT_TAGS_LIST = (
    OBJ_FIELD_TAGS.OF__bounds,
    OBJ_FIELD_TAGS.OF__contRect,
    OBJ_FIELD_TAGS.OF__dBounds,
    OBJ_FIELD_TAGS.OF__pBounds,
    OBJ_FIELD_TAGS.OF__hoodBounds,
    OBJ_FIELD_TAGS.OF__iconBounds,
    OBJ_FIELD_TAGS.OF__growAreaBounds,
    OBJ_FIELD_TAGS.OF__docBounds,
    OBJ_FIELD_TAGS.OF__dynBounds,
    OBJ_FIELD_TAGS.OF__savedSize,
    OBJ_FIELD_TAGS.OF__termBounds,
    OBJ_TEXT_HAIR_TAGS.OF__view,
    OBJ_SCALE_DATA_TAGS.OF__scaleRect,
    OBJ_SUBCOSM_TAGS.OF__Bounds,
)

NODE_POINT_TAGS_LIST = (
    OBJ_FIELD_TAGS.OF__origin,
    OBJ_FIELD_TAGS.OF__minPaneSize,
    OBJ_FIELD_TAGS.OF__minPanelSize,
    OBJ_FIELD_TAGS.OF__termHotPoint,
    OBJ_FIELD_TAGS.OF__MinButSize,
    OBJ_FIELD_TAGS.OF__nRC,
    OBJ_FIELD_TAGS.OF__oRC,
    OBJ_GROW_TERM_INFO_TAGS.OF__termOfst,
)

NODE_STDINT_AUTOLEN_TAGS_LIST = (
    OBJ_FIELD_TAGS.OF__activeMarker,
    OBJ_FIELD_TAGS.OF__partID,
    OBJ_FIELD_TAGS.OF__partOrder,
    OBJ_FIELD_TAGS.OF__objFlags,
    OBJ_FIELD_TAGS.OF__howGrow,
    OBJ_FIELD_TAGS.OF__masterPart,
    OBJ_FIELD_TAGS.OF__conId,
    OBJ_FIELD_TAGS.OF__dIdx,
    OBJ_FIELD_TAGS.OF__dcoFiller,
    OBJ_FIELD_TAGS.OF__dsw,
    OBJ_FIELD_TAGS.OF__rsrcID,
    OBJ_FIELD_TAGS.OF__conNum,
    OBJ_FIELD_TAGS.OF__firstNodeIdx,
    OBJ_FIELD_TAGS.OF__graphType,
    OBJ_FIELD_TAGS.OF__GraphActivePlot,
    OBJ_FIELD_TAGS.OF__GraphActivePort,
    OBJ_FIELD_TAGS.OF__GraphActiveCursor,
    OBJ_FIELD_TAGS.OF__GraphMinPlotNum,
    OBJ_FIELD_TAGS.OF__GVNGrowTerms,
    OBJ_FIELD_TAGS.OF__GVNMaxGrowTerms,
    OBJ_FIELD_TAGS.OF__GVMinGVWidth,
    OBJ_FIELD_TAGS.OF__GVHoodTermWidth,
    OBJ_FIELD_TAGS.OF__MouseWheelSupport,
    OBJ_FIELD_TAGS.OF__SelectNRightType,
    OBJ_FIELD_TAGS.OF__refListLength,
    OBJ_FIELD_TAGS.OF__hGrowNodeListLength,
    OBJ_FIELD_TAGS.OF__i,
    OBJ_FIELD_TAGS.OF__index,
    OBJ_FIELD_TAGS.OF__inplace,
    OBJ_FIELD_TAGS.OF__typeCode,
    OBJ_FIELD_TAGS.OF__gridFlags,
    OBJ_FIELD_TAGS.OF__state,
    OBJ_FIELD_TAGS.OF__treeFlags,
    OBJ_FIELD_TAGS.OF__labelPosRow,
    OBJ_FIELD_TAGS.OF__labelPosCol,
    OBJ_FIELD_TAGS.OF__listboxFlags,
    OBJ_FIELD_TAGS.OF__lastSignalKind,
    OBJ_FIELD_TAGS.OF__methCode,
    OBJ_FIELD_TAGS.OF__numFrozenCols,
    OBJ_FIELD_TAGS.OF__numFrozenRows,
    OBJ_FIELD_TAGS.OF__baseListboxDoubleClickedRow,
    OBJ_FIELD_TAGS.OF__baseListboxClickedColumnHeader,
    OBJ_FIELD_TAGS.OF__nMajDivs,
    OBJ_FIELD_TAGS.OF__paramIdx,
    OBJ_FIELD_TAGS.OF__maxWordLength,
    OBJ_FIELD_TAGS.OF__override,
    OBJ_FIELD_TAGS.OF__overflow,
    OBJ_FIELD_TAGS.OF__quantize,
    OBJ_FIELD_TAGS.OF__shortCount,
    OBJ_FIELD_TAGS.OF__clumpNum,
    OBJ_FIELD_TAGS.OF__termBMPs,
    OBJ_FIELD_TAGS.OF__termListLength,
    OBJ_FIELD_TAGS.OF__annexDDOFlag,
    OBJ_FIELD_TAGS.OF__paneFlags,
    OBJ_FIELD_TAGS.OF__parmIndex,
    OBJ_FIELD_TAGS.OF__primIndex,
    OBJ_FIELD_TAGS.OF__primResID,
    OBJ_FIELD_TAGS.OF__paramTableOffset,
    OBJ_FIELD_TAGS.OF__cellPosRow,
    OBJ_FIELD_TAGS.OF__cellPosCol,
    OBJ_FIELD_TAGS.OF__selLabFlags,
    OBJ_FIELD_TAGS.OF__selLabData,
    OBJ_FIELD_TAGS.OF__tableFlags,
    OBJ_FIELD_TAGS.OF__comboBoxIndex,
    OBJ_FIELD_TAGS.OF__tagType,
    OBJ_FIELD_TAGS.OF__FpgaImplementation,
    OBJ_FIELD_TAGS.OF__PropItemCode,
    OBJ_FIELD_TAGS.OF__variantIndex,
    OBJ_FIELD_TAGS.OF__scaleRMin32,
    OBJ_FIELD_TAGS.OF__scaleRMax32,
    OBJ_FIELD_TAGS.OF__instrStyle,
    OBJ_FIELD_TAGS.OF__nVisItems,
    OBJ_FIELD_TAGS.OF__pRuntimeType,
    OBJ_FONT_RUN_TAGS.OF__fontid,
    OBJ_TEXT_HAIR_TAGS.OF__flags,
    OBJ_TEXT_HAIR_TAGS.OF__mode,
    OBJ_TIME128_TAGS.OF__Seconds,
    OBJ_TIME128_TAGS.OF__FractionalSeconds,
    OBJ_IMAGE_TAGS.OF__ImageResID,
    OBJ_IMAGE_TAGS.OF__ImageInternalsResID,
    OBJ_ATTRIBUTE_LIST_ITEM_TAGS.OF__cellPosRow,
    OBJ_ATTRIBUTE_LIST_ITEM_TAGS.OF__cellPosCol,
    OBJ_ATTRIBUTE_LIST_ITEM_TAGS.OF__font,
    OBJ_ATTRIBUTE_LIST_ITEM_TAGS.OF__mode,
    OBJ_ATTRIBUTE_LIST_ITEM_TAGS.OF__width,
    OBJ_ATTRIBUTE_LIST_ITEM_TAGS.OF__height,
    OBJ_ATTRIBUTE_LIST_ITEM_TAGS.OF__flags,
    OBJ_ATTRIBUTE_LIST_ITEM_TAGS.OF__glyphIndex,
    OBJ_EMBED_OBJECT_TAGS.OF__Type,
    OBJ_EMBED_OBJECT_TAGS.OF__Flags,
    OBJ_PLOT_DATA_TAGS.OF__flags,
    OBJ_PLOT_DATA_TAGS.OF__interp,
    OBJ_PLOT_DATA_TAGS.OF__width,
    OBJ_PLOT_DATA_TAGS.OF__plotFlags,
    OBJ_PLOT_DATA_TAGS.OF__lineStyle,
    OBJ_PLOT_DATA_TAGS.OF__pointStyle,
    OBJ_PLOT_DATA_TAGS.OF__fillStyle,
    OBJ_PLOT_DATA_TAGS.OF__xScale,
    OBJ_PLOT_DATA_TAGS.OF__yScale,
    OBJ_PLOT_DATA_TAGS.OF__cnt,
    OBJ_PLOT_DATA_TAGS.OF__mBits,
    OBJ_PLOT_DATA_TAGS.OF__gtoIndex,
    OBJ_PLOT_DATA_TAGS.OF__unused,
    OBJ_PLOT_DATA_TAGS.OF__fxpWordLength,
    OBJ_PLOT_DATA_TAGS.OF__fxpIntegerLength,
    OBJ_PLOT_DATA_TAGS.OF__fxpFracDigits,
    OBJ_PLOT_DATA_TAGS.OF__fxpStyle,
    OBJ_SCALE_DATA_TAGS.OF__gridMaxLineStyle,
    OBJ_SCALE_DATA_TAGS.OF__gridMinLineStyle,
    OBJ_SCALE_DATA_TAGS.OF__port,
    OBJ_SCALE_DATA_TAGS.OF__scaleFlavor,
    OBJ_BROWSE_OPTIONS_TAGS.OF__mode,
    OBJ_TREE_NODE_TAGS.OF__nodeFlags,
    OBJ_TREE_NODE_TAGS.OF__indentLevel,
    OBJ_KEY_MAPPING_TAGS.OF__VKey,
    OBJ_KEY_MAPPING_TAGS.OF__CharCode,
    OBJ_KEY_MAPPING_TAGS.OF__Mods,
    OBJ_KEY_MAPPING_TAGS.OF__Action,
    OBJ_ROW_COL_TAGS.OF__row,
    OBJ_ROW_COL_TAGS.OF__col,
    OBJ_SCALE_DATA_TAGS.OF__partID,
    OBJ_SCALE_DATA_TAGS.OF__partOrder,
    OBJ_SCALE_DATA_TAGS.OF__flags,
    OBJ_SELECTOR_RANGE_TAGS.OF__start,
    OBJ_SELECTOR_RANGE_TAGS.OF__end,
    OBJ_SELECTOR_RANGE_TAGS.OF__startRangeType,
    OBJ_SELECTOR_RANGE_TAGS.OF__endRangeType,
    OBJ_SELECTOR_RANGE_TAGS.OF__diagramIdx,
    OBJ_EVENT_SPEC_TAGS.OF__diagramIdx,
    OBJ_EVENT_SPEC_TAGS.OF__source,
    OBJ_EVENT_SPEC_TAGS.OF__regFlags,
    OBJ_EVENT_SPEC_TAGS.OF__eSource,
    OBJ_EVENT_SPEC_TAGS.OF__type,
    OBJ_EVENT_SPEC_TAGS.OF__eFlags,
    OBJ_EVENT_SPEC_TAGS.OF__ddoUID,
    OBJ_EVENT_SPEC_TAGS.OF__dynIndex,
)

NODE_STRING_TAGS_LIST = (
    OBJ_TEXT_HAIR_TAGS.OF__text,
    OBJ_FIELD_TAGS.OF__format,
    OBJ_FIELD_TAGS.OF__methName,
    OBJ_FIELD_TAGS.OF__nodeName,
    OBJ_FIELD_TAGS.OF__tagDLLName,
    OBJ_FIELD_TAGS.OF__DefaultData,
    OBJ_FIELD_TAGS.OF__PropItemName,
    OBJ_PLOT_DATA_TAGS.OF__plotName,
    OBJ_PLOT_LEGEND_DATA_TAGS.OF__name,
    OBJ_SCALE_LEGEND_DATA_TAGS.OF__name,
    OBJ_TREE_NODE_TAGS.OF__tag,
)

NODE_TYPEID_TAGS_LIST = (
    OBJ_FIELD_TAGS.OF__typeDesc,
    OBJ_FIELD_TAGS.OF__histTD,
    OBJ_FIELD_TAGS.OF__connectorTM,
    OBJ_FIELD_TAGS.OF__omidTypeDesc,
    OBJ_FIELD_TAGS.OF__dataTypeDesc,
)

NODE_BOOL_TAGS_LIST = (
    OBJ_FIELD_TAGS.OF__FpgaEnableBoundsMux,
    OBJ_CURS_BUTTONS_REC_TAGS.OF__left,
    OBJ_CURS_BUTTONS_REC_TAGS.OF__right,
    OBJ_CURS_BUTTONS_REC_TAGS.OF__up,
    OBJ_CURS_BUTTONS_REC_TAGS.OF__down,
    OBJ_PLOT_LEGEND_DATA_TAGS.OF__menu,
    OBJ_SCALE_LEGEND_DATA_TAGS.OF__autoScaleLock,
    OBJ_SCALE_LEGEND_DATA_TAGS.OF__autoScale,
    OBJ_SCALE_LEGEND_DATA_TAGS.OF__formatButton,
    OBJ_PLOT_DATA_TAGS.OF__fxpIsSigned,
    OBJ_DIGITAL_BUS_ORG_CLUST_TAGS.OF__isBus,
)

NODE_STRING_ARRAY_TAGS_LIST = (
    OBJ_FIELD_TAGS.OF__strings,
    OBJ_FIELD_TAGS.OF__rowHeaders,
    OBJ_FIELD_TAGS.OF__columnHeaders,
)

NODE_STDINT_AUTOLEN_ARRAY_TAGS_LIST = (
    OBJ_FIELD_TAGS.OF__arrayIndices,
    OBJ_FIELD_TAGS.OF__arraySelectionStart,
    OBJ_FIELD_TAGS.OF__arraySelectionEnd,
    OBJ_DIGITAL_BUS_ORG_CLUST_TAGS.OF__arrayHandle,
)

NODE_DATAFILL_TAGS_LIST = (
    OBJ_FIELD_TAGS.OF__StdNumMin,
    OBJ_FIELD_TAGS.OF__StdNumMax,
    OBJ_FIELD_TAGS.OF__StdNumInc,
)

NODE_DTFILLEAF_TAGS_LIST = (
    OBJ_COMPLEX_SCALAR_TAGS.OF__real,
    OBJ_COMPLEX_SCALAR_TAGS.OF__imaginary,
)


def getFrontPanelHeapIdent(hfmt):
    """ Gives 4-byte heap identifier from HEAP_FORMAT member
    """
    heap_ident = {
        HEAP_FORMAT.VersionT: b'FPHT',
        HEAP_FORMAT.XMLVer: b'FPHX',
        HEAP_FORMAT.BinVerA: b'FPHB',
        HEAP_FORMAT.BinVerB: b'FPHb',
        HEAP_FORMAT.BinVerC: b'FPHc',
    }.get(hfmt, b'')
    return heap_ident


def recognizePanelHeapFmtFromIdent(heap_ident):
    """ Gives FILE_FMT_TYPE member from given 4-byte file identifier
    """
    heap_id = bytes(heap_ident)
    for hfmt in HEAP_FORMAT:
        curr_heap_id = getFrontPanelHeapIdent(hfmt)
        if len(curr_heap_id) > 0 and (curr_heap_id == heap_id):
            return hfmt
    return HEAP_FORMAT.Unknown

def parentNodeTagMatches(parentNode, tagList, levels=1, start=0):
    """ Checks whether parent nodes have tags matching any item in list
    """
    for i in range(start):
        if parentNode is None:
            break
        parentNode = parentNode.parent
    for i in range(levels):
        if parentNode is None:
            break
        if parentNode.tagEn in tagList:
            return True
        parentNode = parentNode.parent
    return False

def parentTopClassEn(obj, levels=128, start=0):
    """ Return classId of top object with class

    From a list of object and its parents, this function will return class id
    of the one nearest to top which has a 'class' attribute.
    """
    for i in range(start):
        if obj is None:
            break
        obj = obj.parent
    for i in range(levels):
        if obj is None:
            break
        if SL_SYSTEM_ATTRIB_TAGS.SL__class.value in obj.attribs:
            return obj.attribs[SL_SYSTEM_ATTRIB_TAGS.SL__class.value]
        obj = obj.parent
    return SL_CLASS_TAGS.SL__oHExt

def tagIdToEnum(tagId, parentNode):
    # System level tags are always active; other tags depend
    # on an upper level tag which has 'class' set.
    tagEn = None
    if SL_SYSTEM_TAGS.has_value(tagId):
        tagEn = SL_SYSTEM_TAGS(tagId)

    if tagEn is None:
        classEn = parentTopClassEn(parentNode)
        if classEn in CLASS_EN_TO_TAG_LIST_MAPPING:
            TAG_LIST = CLASS_EN_TO_TAG_LIST_MAPPING[classEn]
            if TAG_LIST.has_value(tagId):
                tagEn = TAG_LIST(tagId)

    if tagEn is None:
        if OBJ_FIELD_TAGS.has_value(tagId):
            tagEn = OBJ_FIELD_TAGS(tagId)

    if tagEn is None:
        tagEn = UNRECOGNIZED_TAG(tagId)

    return tagEn

def tagEnToName(tagEn, parentNode):
    # For most enums, we need to remove 4 starting bytes to get the name
    if isinstance(tagEn, SL_SYSTEM_TAGS):
        tagName = tagEn.name
    else:
        tagName = tagEn.name[4:]
    return tagName

def tagNameToEnum(tagName, parentNode):
    tagEn = None

    if SL_SYSTEM_TAGS.has_name(tagName):
        tagEn = SL_SYSTEM_TAGS[tagName]

    if tagEn is None:
        classEn = parentTopClassEn(parentNode)
        if classEn in CLASS_EN_TO_TAG_LIST_MAPPING:
            TAG_LIST = CLASS_EN_TO_TAG_LIST_MAPPING[classEn]
            if TAG_LIST.has_name("OF__"+tagName):
                tagEn = TAG_LIST["OF__"+tagName]

    if tagEn is None:
        if OBJ_FIELD_TAGS.has_name("OF__"+tagName):
            tagEn = OBJ_FIELD_TAGS["OF__"+tagName]

    if tagEn is None:
        tagParse = re.match("^Tag([0-9A-F]{4,8})$", tagName)
        if tagParse is not None:
            tagEn = UNRECOGNIZED_TAG(int(tagParse[1], 16))

    return tagEn

def attributeIdToName(attrId):
    if SL_SYSTEM_ATTRIB_TAGS.has_value(attrId):
        attrName = SL_SYSTEM_ATTRIB_TAGS(attrId).name[4:]
    else:
        attrName = 'Prop{:04X}'.format(attrId)
    return attrName

def attributeNameToId(attrName):
    if SL_SYSTEM_ATTRIB_TAGS.has_name("SL__"+attrName):
        attrId = SL_SYSTEM_ATTRIB_TAGS["SL__"+attrName].value
    else:
        nameParse = re.match("^Prop([0-9A-F]{4,8})$", attrName)
        if nameParse is not None:
            attrId = int(nameParse[1], 16)
        else:
            attrId = None
    return attrId

def classIdToEnum(classId, obj):
    classEn = None
    if parentNodeTagMatches(obj, (
      OBJ_FIELD_TAGS.OF__baseListboxItemStrings,
      )):
        if SL_MULTI_DIM_CLASS_TAGS.has_value(classId):
            classEn = SL_MULTI_DIM_CLASS_TAGS(classId)
    if classEn is None:
        if SL_CLASS_TAGS.has_value(classId):
            classEn = SL_CLASS_TAGS(classId)
    if classEn is None:
        classEn = UNRECOGNIZED_CLASS(classId)
    return classEn

def classEnToName(classEn):
    if isinstance(classEn, SL_CLASS_TAGS):
        className = classEn.name[4:]
    else:
        className = classEn.name
    return className

def classNameToEnum(className):
    classEn = None
    if SL_CLASS_TAGS.has_name("SL__"+className):
        classEn = SL_CLASS_TAGS["SL__"+className]
    elif SL_MULTI_DIM_CLASS_TAGS.has_name(className):
        classEn = SL_MULTI_DIM_CLASS_TAGS[className]
    else:
        classParse = re.match("^Class([0-9A-F]{4,8})$", className)
        if classParse is not None:
            classId = int(classParse[1], 16)
            classEn = UNRECOGNIZED_CLASS(classId)
    return classEn

def attributeValueIntToIntOrEn(attrId, attrIntVal, obj):
    if attrId == SL_SYSTEM_ATTRIB_TAGS.SL__class.value:
        attrVal = classIdToEnum(attrIntVal, obj)
    else:
        attrVal = attrIntVal
    return attrVal

def attributeValueIntOrEnToStr(attrId, attrVal, parentNode):
    if attrId == SL_SYSTEM_ATTRIB_TAGS.SL__class.value:
        attrStr = classEnToName(attrVal)
    else:
        attrStr = '{:d}'.format(attrVal)
    return attrStr

def attributeValueStrToIntOrEn(attrId, attrStr):
    if attrId == SL_SYSTEM_ATTRIB_TAGS.SL__class.value:
        attrVal = classNameToEnum(attrStr)
    else:
        attrVal = int(attrStr, 0)
    return attrVal

def autoScopeInfoFromET(elem):
    # If scopeInfo is forced by XML tag, use the one from XML
    scopeStr = elem.get("ScopeInfo")
    if scopeStr is not None:
        scopeInfo = int(scopeStr, 0)
        return NODE_SCOPE(scopeInfo)
    if len(elem) == 0 and elem.get("elements") is None:
        return NODE_SCOPE.TagLeaf
    return NODE_SCOPE.TagOpen

def createObjectNode(vi, po, parentNode, tagEn, scopeInfo):
    """ create new Heap Node

    Acts as a factory which selects object class based on tagEn.
    """
    # Tags which have always the same type
    if tagEn in NODE_RECT_TAGS_LIST:
        obj = HeapNodeRect(vi, po, parentNode, tagEn, scopeInfo)
    elif tagEn in NODE_POINT_TAGS_LIST:
        obj = HeapNodePoint(vi, po, parentNode, tagEn, scopeInfo)
    elif tagEn in NODE_STDINT_AUTOLEN_TAGS_LIST:
        obj = HeapNodeStdInt(vi, po, parentNode, tagEn, scopeInfo, btlen=-1, signed=True)
    elif tagEn in NODE_STRING_TAGS_LIST:
        obj = HeapNodeString(vi, po, parentNode, tagEn, scopeInfo)
    elif tagEn in NODE_TYPEID_TAGS_LIST:
        obj = HeapNodeTypeId(vi, po, parentNode, tagEn, scopeInfo)
    elif tagEn in NODE_BOOL_TAGS_LIST:
        obj = HeapNodeBool(vi, po, parentNode, tagEn, scopeInfo)
    elif tagEn in NODE_DATAFILL_TAGS_LIST:
        obj = HeapNodeTDDataFill(vi, po, parentNode, tagEn, scopeInfo)
    # Tags within array
    elif tagEn == SL_SYSTEM_TAGS.SL__arrayElement and \
      parentNodeTagMatches(parentNode, NODE_STRING_ARRAY_TAGS_LIST):
        obj = HeapNodeString(vi, po, parentNode, tagEn, scopeInfo)
    elif tagEn == SL_SYSTEM_TAGS.SL__arrayElement and \
      parentNodeTagMatches(parentNode, NODE_STDINT_AUTOLEN_ARRAY_TAGS_LIST):
        obj = HeapNodeStdInt(vi, po, parentNode, tagEn, scopeInfo, btlen=-1, signed=True)
    elif tagEn == SL_SYSTEM_TAGS.SL__arrayElement and \
      parentNodeTagMatches(parentNode, (OBJ_FIELD_TAGS.OF__baseListboxItemStrings,), start=1):
        if parentNodeTagMatches(parentNode, (OBJ_MULTI_DIM_TAGS.OF__multiDimArrayElems,), start=0):
            obj = HeapNodeString(vi, po, parentNode, tagEn, scopeInfo)
        elif parentNodeTagMatches(parentNode, (OBJ_MULTI_DIM_TAGS.OF__multiDimArraySizes,), start=0):
            obj = HeapNodeStdInt(vi, po, parentNode, tagEn, scopeInfo, btlen=-1, signed=True)
    # Special combinations, where tag type depends on parents
    elif tagEn == OBJ_FIELD_TAGS.OF__buf and \
      parentTopClassEn(parentNode) in (SL_CLASS_TAGS.SL__multiLabel,):
        obj = HeapNodePStrList(vi, po, parentNode, tagEn, scopeInfo)
    elif tagEn == OBJ_FIELD_TAGS.OF__activePlot and \
      parentNodeTagMatches(parentNode, (OBJ_FIELD_TAGS.OF__ddo,)):
        obj = HeapNodeStdInt(vi, po, parentNode, tagEn, scopeInfo, btlen=-1, signed=True)
    elif tagEn in NODE_DTFILLEAF_TAGS_LIST and \
      parentNodeTagMatches(parentNode, NODE_DATAFILL_TAGS_LIST):
        obj = HeapNodeTDDataFillLeaf(vi, po, parentNode, tagEn, scopeInfo)
    else:
        obj = HeapNode(vi, po, parentNode, tagEn, scopeInfo)
    return obj

def addObjectNodeToTree(section, parentIdx, objectIdx):
    """ put object node into tree struct
    """
    obj = section.objects[objectIdx]
    # Add node to parent
    if parentIdx > 0:
        parent = section.objects[parentIdx]
        parent.childs.append(objectIdx)
    else:
        parent = None
    obj.parent = parent

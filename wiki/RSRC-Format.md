### Table of Content

* [General structure](#General-structure) 
* [RSRC Header](#RSRC-Header) 
* [Block Info List Header](#Block-Info-List-Header) 
* [Blocks Info](#Blocks-Info) 
* [Block Header](#Block-Header) 
* [Block Section Info](#Block-Section-Info) 
* [Block Section Data](#Block-Section-Data) 
* [Other sources](#Other-sources) 

### General structure

The RSRC file contains two identical RSRC headers. Data for sections of each block follow the first RSRC header. Second RSRC header is followed by Blocks Info and then an array of Block Headers. Following these is an array of Block Section Info. The file ends with some section names stored as Pascal string (there is often only one name).

```
+-----------------------------+
|        RSRC header 1        |
|+---------------------------+|
||      Section 1 Data       ||
|+---------------------------+|
||           ....            ||
|+---------------------------+|
||      Section M Data       ||
|+---------------------------+|
+-----------------------------+
+-----------------------------+
|        RSRC header 2        |
|+---------------------------+|
||  Block Info List Header   ||
|+---------------------------+|
||        Blocks Info        ||
||+-------------------------+||
|||     Block 1 Header      |||
||+-------------------------+||
|||          ....           |||
||+-------------------------+||
|||     Block N Header      |||
||+-------------------------+||
|+---------------------------+|
||      Section 1 Info       ||
|+---------------------------+|
||           ....            ||
|+---------------------------+|
||      Section M Info       ||
|+---------------------------+|
|+---------------------------+|
||       Section Names       ||
|+---------------------------+|
+-----------------------------+
```

Reading the file starts with finding second RSRC header (pointed to by size in 1st RSRC Header). Then reading Block Info and Block Headers. The Block Headers contain offset to list of Section Infos for each block, and the count of sections within each block. Then Section Info structures can then be parsed, and these contain offsets, within the first RSRC, to the Block Section Data. There, the real data is stored.

It is not fully known why there is the division to sections. Each section of a block seem to contain alternative data for that block. The idea seem to be that a loading program selects the section which matches its environment, and ignores other sections in specific block.


### RSRC Header

offset1: 0
offset2: _RSRC Data Offset_

```
 Length | Type    | Value
--------+---------+-------
      6 | string  | "RSRC\r\n" Magic ID
      2 | uint16  | Format version
      4 | string  | "LVIN" File type (ie. LabVIEW Instrument)
      4 | string  | "LBVW" Creator (always LabVIEW)
      4 | uint32  | RSRC Info Offset
      4 | uint32  | RSRC Info Size
      4 | uint32  | RSRC Data Offset
      4 | uint32  | RSRC Data Size
```
For more information, see `RSRCHeader` class declaration within _pylabview_ source.

### Block Info List Header

offset: _RSRC Info Offset_ + _RSRC Header Size_

```
 Length | Type    | Value
--------+---------+-------
      4 |         | ?
      4 |         | ?
      4 | uint32  | size of `RSRCHeader`
      4 | uint32  | Block Info Offset
      4 | uint32  | Block Info Size
```

For more information, see `BlockInfoListHeader` class declaration within _pylabview_ source.

### Blocks Info

offset: _RSRC Info Offset_ + _Block Info Offset_

```
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | Block Count (+1)
        |         | Block data
```

For more information, see `BlockInfoHeader` class declaration within _pylabview_ source.

### Block Header

``` 
 Length | Type    | Value
--------+---------+-------
      4 | string  | Name
      4 | uint32  | Count (+1)
      4 | uint32  | Info Offset
```

For more information, see `BlockHeader` class declaration within _pylabview_ source.

### Block Section Info

offset: _Info Offset_ + _Block Offset_

```
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | Section Index
      4 | uint32  | Section Name Offset
      4 | uint32  | ?
      4 | uint32  | Section Data Offset
      4 | int32   | ?
```

For more information, see ` BlockSectionStart` class declaration within _pylabview_ source.

### Block Section Data

offset: _Offset_ + _Data Offset_

Max size is _Data Size_. Otherwise you can get the size by comparing the offsets. Repeat 
_Count_ of these:

```
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | Size
   Size | data    | Contents of the block (might be compressed (zlib))
```

### Other sources

Findings in this document are based on work of @jcreigh and @tomsoftware. 
See [VI Explorer Source](http://www.hmilch.net/hmilch.php/labview_source.php) and [Jessica's Wiki](https://github.com/jcreigh/pylabview/wiki) for more.

### Table of Content

* [General structure](#General-structure) 
* [RSRC Header](#RSRC-Header) 
* [Blocks Info](#Blocks-Info) 
* [Block Header](#Block-Header) 
* [Block Section Info](#Block-Section-Info) 
* [Block Section Data](#Block-Section-Data) 
* [Other sources](#Other-sources) 

### General structure

The RSRC file contains two identical RSRC headers. Data for sections of each block follow the first RSRC header. Second RSRC header is followed by Blocks Info and then an array of Block Headers. Following these is an array of Block Section Info. The file ends with its filename stored as Pascal string.

```
+---------------------+
|    RSRC header 1    |
|+-------------------+|
||  Section 1 Data   ||
|+-------------------+|
||       ....        ||
|+-------------------+|
||  Section M Data   ||
|+-------------------+|
+---------------------+
+---------------------+
|    RSRC header 2    |
|+-------------------+|
||    Blocks Info    ||
|+-------------------+|
||  Block 1 Header   ||
|+-------------------+|
||       ....        ||
|+-------------------+|
||  Block N Header   ||
|+-------------------+|
||  Section 1 Info   ||
|+-------------------+|
||       ....        ||
|+-------------------+|
||  Section M Info   ||
|+-------------------+|
|+-------------------+|
||     File Name     ||
|+-------------------+|
+---------------------+
```

Reading the file starts with finding second RSRC header (pointed to by size in 1st RSRC Header). Then reading Block Info and Block Headers. The Block Headers contain offset to list of Section Infos for each block, and the count of sections within each block. Then Section Info structures can then be parsed, and these contain offsets, within the first RSRC, to the Block Section Data. There, the real data is stored.

It is not fully known why there is the division to sections. Each section of a block seem to contain alternative data for that block. The idea seem to be that a loading program selects the section which matches its environment, and ignores other sections in specific block.


### RSRC Header

offset: 0

```
 Length | Type    | Value
--------+---------+-------
      6 | string  | "RSRC\r\n"
      2 |         | ?
      4 | string  | "LVIN" (LabVIEW Instrument?)
      4 | string  | "LBVW" (LabVIEW?)
      4 | uint32  | RSRC Offset
      4 | uint32  | RSRC Size
      4 | uint32  | Data Offset
      4 | uint32  | Data Size
      4 |         | ?
      4 |         | ?
      4 |         | ?
      4 | uint32  | Block Offset
      4 | uint32  | Block Size
```

### Blocks Info

offset: _Block Offset_ + _RSRC Offset_

```
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | Block Count (+1)
        |         | Block data
```

### Block Header

``` 
 Length | Type    | Value
--------+---------+-------
      4 | string  | Name
      4 | uint32  | Count (+1)  (I think?)
      4 | uint32  | Info Offset
```

### Block Section Info

offset: _Info Offset_ + _Block Offset_

```
 Length | Type    | Value
--------+---------+-------
      4 | int32?  | ?
      4 | int32?  | ?
      4 | int32?  | ?
      4 | uint32  | Offset
      4 | int32   | ?
```

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

### Table of Content

* [File Header](#File-Header) 
* [Blocks Info](#Blocks-Info) 
* [Block Header](#Block-Header) 
* [Block Info](#Block-Info) 
* [Block Data](#Block-Data) 
* [Other sources](#Other-sources) 

### File Header

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

### Block Info

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

### Block Data

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

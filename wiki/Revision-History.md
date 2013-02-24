* [HBUF](#HBUF) - Revision History ?
* [HBIN](#HBIN) - Revision History ?

<a name="wiki-HBUF" />
### HBUF
```plain
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | ?
      4 | uint32  | Count
```

Count of the following:
```plain
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | Revision Number
      4 | uint32  | Time (unknown format)
      4 | uint32  | ?
      4 | uint32  | ?
      4 | uint32  | ?
```

***

<a name="wiki-HBIN" />
### HBUF

Multiple of the following:
```plain
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | Name Length
      * | string  | Name
```

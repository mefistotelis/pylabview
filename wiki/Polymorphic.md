* [LIvi](#LIvi) - Linked VIs?

<a name="wiki-LIvi" />
### LIvi
```plain
 Length | Type    | Value
--------+---------+-------
      2 | uint16  | 00 01 ?
      4 | string  | LVIN
      1 | uint8   | Name Length
      * | string  | Name
      6 |         | 00 00 00 00 00 00 ?
      1 | uint8   | Count
      1 | uint8   | 00 ?
```

Count of the following:
```plain
 Length | Type    | Value
--------+---------+-------
      1 | uint8   | 02
      4 | string  | VIVI
      4 | uint32  | 00 00 00 01 ?
      1 | uint8   | Name Length
      * | string  | Name
     1? | uint8   | 00 ? Sometimes is missing
      4 | string  | PTH0
      4 | uint32  | ?
      2 | uint16  | ?
      2 | uint16  | ?
      1 | uint8   | 00 ?
     1? | uint8   | 00 ? Is here if previous 00 is there
      1 | uint8   | Name Length
      * | string  | Name
      4 | uint32  | 00 00 00 00 ?
      2 | uint16  | 1 if subVI is nonexecutable, 2 if okay
      4 | uint34  | 00 00 00 01 ?
      2 | uint16  | 00 01 ?
     24 |         | All 00s
```

At the end:
```plain
 Length | Type    | Value
--------+---------+-------
      1 | uint8   | 03 ?
```

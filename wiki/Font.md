### FTAB - Font Table

```plain
 Length | Type    | Value
--------+---------+---------
      2 |         | ? 00 01
      2 |         | ? 00 02
      2 |         | ? 00 03
      2 | uint16  | Font count
```

Font count of the following:
```plain
 Length | Type    | Value
--------+---------+---------
      4 | uint32  | id?
      2 |         | Size
      1 |         | ? 04
      1 | uint8   | Style (see below)
      4 |         | ?
      2 |         | ?
      2 |         | ?
```

Font count of the following:
```plain
 Length | Type    | Value
--------+---------+-------
      1 | uint8   | Font name length
      * | string  | Font name
```

<a id="wiki-Style" />
### Style
```plain
 Mask | Value
------+---------------
 0x01 | Strikethrough
 0x02 | Italic
 0x04 | Underline
 0x08 | Outline
```

### FTAB - Font Table

The font table appears to have has a minimum of 4 entries. 
First 3 are the same. 4th is an instance of Application Font

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
      2 | uint16  | Bold if == 1000?
      2 |         | Real Size?
      2 |         | ? Seems to increase when bold
      2 |         | ? Seems to increase when bold
```

Font count of the following:
```plain
 Length | Type    | Value
--------+---------+-------
      1 | uint8   | Font name length
      * | string  | Font name
```

A few special fonts:
```plain
 Name | Value
------+------------------
    0 | Application Font
    1 | System Font
    2 | Dialog Font

Bold and Size are 0x8000 when not set
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
 0x16 | Shadow
```

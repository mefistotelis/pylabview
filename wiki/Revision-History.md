* [HBUF](#HBUF) - Revision History ?
* [HBIN](#HBIN) - Revision History ?
* [HIST](#HIST) - Revision History

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

***

<a name="wiki-HIST" />
### HIST

```plain
 Length | Type    | Value
--------+---------+-------
      6 |         | 
      2 | uint16  | Flags
      4 | uint32  | Revision number
     28 |         |
```

Flags:
```plain
 Mask   | Meaning
--------+---------
 0x0001 | Add entry whenever saved
 0x0002 | Prompt for comment when closed
 0x0004 | Prompt for comment when saved
 0x0100 | Custom settings
 0x0200 | Record generated comments
 0x0400 | Default settings (overrides above flags)
```

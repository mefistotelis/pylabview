Some have example data included.

All guesses at the acronyms are that. Guesses.

## Contents

* [BDHb, BDHc](#BDH_) - Block Diagram
* [BDPW](#BDPW) - Block Diagram Password
* [BDSE](#BDSE) - Block Diagram ?
* [BNID](#BNID)
* [CCSG](#CCSG)
* [CONP](#CONP)
* [CPC4](#CPC2)
* [CPMp](#CPMp)
* [DFDS](#DFDS)
* [DLDR](#DLDR)
* [DTHP](#DTHP)
* [FPHb](#FPHb) - Front Panel ?
* [FPSE](#FPSE) - Front Panel ?
* [FPTD](#FPTD) - Front Panel ?
* [FTAB](#FTAB) - Font Table
* [GCPR](#GCPR)
* [HBUF](#HBUF) - Revision History ?
* [HBIN](#HBIN) - Revision History ?
* [HIST](#HIST) - History ?
* [HLPP](#HLPP) - Help Path
* [HLPT](#HLPT) - Help Tag
* [icl8](#icl8) - 8-bit Icon
* [ICON](#ICON) - 1-bit Icon
* [LIbd](#LIbd)
* [LIds](#LIds)
* [LIfp](#LIfp)
* [LIBN](#LIBN)
* [LIvi](#LIvi)
* [LVSR](#LVSR) - Version ?
* [MUID](#MUID)
* [NUID](#NUID)
* [OBSG](#OBSG)
* [PRT](#PRT)   - Print Settings
* [RTSG](#RTSG)
* [SCSR](#SCSR)
* [STRG](#STRG) - String Description
* [SUID](#SUID)
* [TM80](#TM80)
* [VCTP](#VCTP)
* [VICD](#VICD)
* [VITS](#VITS)
* [vers](#vers) - Version

***

<a name="wiki-BDH_" />

### BDHb, BDHc

<b>B</b>lock <b>D</b>iagram <b>H</b>eap
Compressed

```plain
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | String length
      * | string  | Content
```

***

### BDPW

<b>B</b>lock <b>D</b>iagram <b>P</b>ass<b>w</b>ord

```plain
 Length | Type    | Value
--------+---------+-------
     16 | string  | Password md5
     16 | string  | Hash 1
     16 | string  | Hash 2
```

***

### BDSE

4 bytes

```plain
00 00 00 07
```

***

<a name="wiki-BNID" />
### BNID

12 bytes

```plain
00 00 00 02  00 00 00 00  00 00 00 00
```

***

### CCSG

16 bytes

***

### CONP

2 bytes

```plain
00 01
```

***

### CPC2

2 bytes  
Not in Controls

```plain
00 01 - Normal VI
00 08 - Polymorphic VI
```

***

### CPMp

***

### DFDS

***

### DLDR

28 bytes?  
Not in Polymorphic VIs or Controls

```plain
00 00 00 01  00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00
```

***

### DTHP

2 bytes

```plain
00 00
```

***

### FPHb

***

### FPSE

4 bytes

```plain
00 00 00 10
```

***

### FPTD

2 bytes  
Not in Polymorphic VIs or Controls

```plain
00 09
```

***

### FTAB

<b>F</b>ont <b>Tab</b>le 

***

### GCPR

13 bytes?

```plain
00 00 00 00  00 00 00 00  00 00 00 00  00
```

***

### HIST

<b>Hist</b>ory 
See [[Revision History]]

***

### icl8

<b>ic</b>on ? <b>8</b> (bit) 
See [[Icon]]

***

### ICON

<b>ICON</b> 
See [[Icon]]

***

### LIbd

***

### LIds

***

### LIfp

Might be "full path"
Contains name of a file

***

### LIBN

```plain
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | Count?
      1 | uint8   | String length
      * | string  | Content
```

***

### LIvi

Only in polymorphic VIs. Lists VIs included.

***

### LVSR

See [[Version Bits]]

```plain
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | Version
      2 | int16   | ?
      2 | uint16  | flags

Flags:
 Protected: 0x2000
```

***

### MUID
4 bytes

```plain
00 00 00 2b
```

***

### NUID
16 bytes

***

### OBSG
16 bytes

```plain
00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00
```

***

### PRT
See [[Print]]

### RTSG
16 bytes

```plain
00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00
```

***

### SCSR

***

### SUID
12 bytes

```plain
00 00 00 02  00 00 00 00  00 00 00 00
```

***

### TM80

***

### VCTP

***

### VICD

***

### VITS

***

### vers

<b>vers</b>ion  
12 bytes  
See [[Version Bits]]

```plain
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | Version
      1 | uint8   | String length
      * | string  | Text
      1 | uint8   | String length
      * | string  | Info
```

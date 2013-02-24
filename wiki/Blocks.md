Some have example data included.

All guesses at the acronyms are that. Guesses.
## Contents
* [BDHb, BDHc](#BDH_) - Block Diagram ?
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
<b>B</b>lock <b>D</b>ata ?  
Compressed

```plain
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | String length
      * | string  | Content
```

***

<a name="wiki-BDPW" />
### BDPW
<b>B</b>lock <b>D</b>ata <b>P</b>ass<b>w</b>ord
```plain
 Length | Type    | Value
--------+---------+-------
     16 | string  | Password md5
     16 | string  | Hash 1
     16 | string  | Hash 2
```

***

<a name="wiki-BDSE" />
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

<a name="wiki-CCSG" />
### CCSG
16 bytes

***

<a name="wiki-CONP" />
### CONP
2 bytes

```plain
00 01
```

***

<a name="wiki-CPC2" />
### CPC2
2 bytes  
Not in Controls

```plain
00 01 - Normal VI
00 08 - Polymorphic VI
```

***

<a name="wiki-CPMp" />
### CPMp

***

<a name="wiki-DFDS" />
### DFDS

***

<a name="wiki-DLDR" />
### DLDR
28 bytes?  
Not in Polymorphic VIs or Controls

```plain
00 00 00 01  00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00
```

***

<a name="wiki-DTHP" />
### DTHP
2 bytes

```plain
00 00
```

***

<a name="wiki-FPHb" />
### FPHb

***

<a name="wiki-FPSE" />
### FPSE
4 bytes

```plain
00 00 00 10
```

***

<a name="wiki-FPTD" />
### FPTD
2 bytes  
Not in Polymorphic VIs or Controls
```plain
00 09
```

***

<a name="wiki-FTAB" />
### FTAB
<b>F</b>ont <b>Tab</b>le

***

<a name="wiki-GCPR" />
### GCPR
13 bytes?
```plain
00 00 00 00  00 00 00 00  00 00 00 00  00
```

***

<a name="wiki-HIST" />
### HIST
<b>Hist</b>ory

***

<a name="wiki-icl8" />
### icl8
<b>ic</b>on ? <b>8</b> (bit)
See [[Icon]]

***

<a name="wiki-ICON" />
### ICON
<b>ICON</b>  
See [[Icon]]

***

<a name="wiki-LIbd" />
### LIbd

***

<a name="wiki-LIds" />
### LIds

***

<a name="wiki-LIfp" />
### LIfp
Might be "full path"  
Contains name of a file

***

<a name="wiki-LIBN" />
### LIBN
```plain
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | Count?
      1 | uint8   | String length
      * | string  | Content
```

***

<a name="wiki-LIvi" />
### LIvi
Only in polymorphic VIs. Lists VIs included.

***

<a name="wiki-LVSR" />
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

<a name="wiki-MUID" />
### MUID
4 bytes

```plain
00 00 00 2b
```

***

<a name="wiki-NUID" />
### NUID
16 bytes

***

<a name="wiki-OBSG" />
### OBSG
16 bytes

```plain
00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00
```

***

<a name="wiki-RTSG" />
### RTSG
16 bytes

```plain
00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00
```

***

<a name="wiki-SCSR" />
### SCSR

***

<a name="wiki-SUID" />
### SUID
12 bytes

```plain
00 00 00 02  00 00 00 00  00 00 00 00
```

***

<a name="wiki-TM80" />
### TM80

***

<a name="wiki-VCTP" />
### VCTP

***

<a name="wiki-VICD" />
### VICD

***

<a name="wiki-VITS" />
### VITS

***

<a name="wiki-vers" />
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

Some have example data included.

All guesses at the acronyms are that. Guesses.

## Contents

* [BDHP, BDHb, BDHc](#BDH_) - Block Diagram Heap
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
* [FPHP, FPHb, FPHc](#FPH_) - Front Panel Heap
* [FPSE](#FPSE) - Front Panel SE
* [FPTD](#FPTD) - Front Panel TD
* [FTAB](#FTAB) - Font Table
* [GCPR](#GCPR)
* [HBUF](#HBUF) - Revision History ?
* [HBIN](#HBIN) - Revision History ?
* [HIST](#HIST) - History ?
* [HLPP](#HLPP) - Help Path
* [HLPT](#HLPT) - Help Tag
* [icl8, icl4](#icl_) - 8-bit/4-bit Icon
* [ICON](#ICON) - 1-bit Icon
* [LIbd](#LIbd)
* [LIds](#LIds)
* [LIfp](#LIfp)
* [LIBN](#LIBN) - Library Names
* [LIvi](#LIvi)
* [LVSR](#LVSR) - LabVIEW Save Record
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

### BDH_

<b>B</b>lock <b>D</b>iagram <b>H</b>eap  
Compressed

Depending on LV version, the full name is one of: BDHP, BDHb, BDHc.

```
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | Content length
      * | binary  | Content
```

See [[Block Diagram Heap Format]] for content explanation.

***

### BDPW

<b>B</b>lock <b>D</b>iagram <b>P</b>ass<b>w</b>ord  

```
 Length | Type    | Value
--------+---------+-------
     16 | string  | Password md5
     16 | string  | Hash 1
     16 | string  | Hash 2
```

***

### BDSE

4 bytes

```
00 00 00 07
```

***

### BNID

12 bytes

```
00 00 00 02  00 00 00 00  00 00 00 00
```

***

### CCSG

16 bytes

***

### CONP

2 bytes

```
00 01
```

***

### CPC2

2 bytes  
Not in Controls

```
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

```
00 00 00 01  00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00
```

***

### DTHP

2 bytes

```
00 00
```

***

### FPH_

<b>F</b>ront <b>P</b>anel <b>H</b>eap  
Compressed

Stores the actual Front Panel data
Depending on LV version, the full name is one of: FPHP, FPHb, FPHc.

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

```
00 09
```

***

### FTAB

<b>F</b>ont <b>Tab</b>le 

See [[Font Table Format]] for content explanation.

***

### GCPR

13 bytes?

```
00 00 00 00  00 00 00 00  00 00 00 00  00
```

***

### HIST

<b>Hist</b>ory 
See [[Revision History]]

***

### icl_

<b>ic</b>on <b>l</b>arge <b>4/8</b> (bit) 
See [[Icon Format]]

***

### ICON

<b>ICON</b> 1bpp image 
See [[Icon Format]]

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

<b>Lib</b>rary <b>N</b>ames  

```
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | Count
      1 | uint8   | String length
      * | string  | Content
```

***

### LIvi

Only in polymorphic VIs. Lists VIs included.

***

### LVSR

LabVIEW Save Record  
See [[Version Bits]]

```
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

```
00 00 00 2b
```

***

### NUID
16 bytes

***

### OBSG
16 bytes

```
00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00
```

***

### PRT

<b>PR</b>in<b>t</b> Settings  

See [[Print Settings]] for details.

### RTSG
16 bytes

```
00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00
```

***

### SCSR

***

### SUID
12 bytes

```
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

See [[Version Bits]] for details.

```plain
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | Version Bits
      1 | uint8   | String length
      2 | uint16  | Language
      1 | uint8   | Text length
      * | string  | Text
      1 | uint8   | Info length
      * | string  | Info
```

#### Language

```plain
 Value  | Language
--------+---------
      0 | English
      1 | French
      3 | German
     14 | Japanese
     23 | Korean
     33 | Chinese
```

While these codes seem to originate from
[old Macintosh codes in script.h](https://github.com/phracker/MacOSX-SDKs/blob/master/MacOSX10.6.sdk/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/CarbonCore.framework/Versions/A/Headers/Script.h)
only the above values have been seen.
Non-zero Language code has been seen in versions 8.0.0f5 through 19.0.0f5.

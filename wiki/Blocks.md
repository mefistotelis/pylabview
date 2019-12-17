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
* [icl8](#icl8) - 8-bit Icon
* [icl4](#icl4) - 4-bit Icon
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

### icl8

<b>ic</b>on ? <b>8</b> (bit) 
See [[Icon]]

***

### ICON

<b>ICON</b> 1bpp image 
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
      * | string  | Text
      1 | uint8   | String length
      * | string  | Info
```

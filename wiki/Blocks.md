Blocks which only appear with compiled data have a <sup>c</sup>, blocks with <sup>?</sup> are unknown.

Some have example data included.

All guesses at the acronyms are that. Guesses.
## Contents
* [BDHb, BDHc](#BDH_)
* [BDPW](#BDPW) - Block Data Password
* [BDSE](#BDSE)
* [BNID<sup>c</sup><sup>?</sup>](#BNID)
* [CCSG<sup>c</sup><sup>?</sup>](#CCSG)
* [CONP<sup>?</sup>](#CONP)
* [CPC2<sup>?</sup>](#CPC2)
* [CPMp<sup>c</sup><sup>?</sup>](#CPMp)
* [DFDS<sup>c</sup><sup>?</sup>](#DFDS)
* [DLDR<sup>c</sup><sup>?</sup>](#DLDR)
* [DTHP<sup>?</sup>](#DTHP)
* [FPHb<sup>?</sup>](#FPHb)
* [FPSE<sup>?</sup>](#FPSE)
* [FPTD<sup>c</sup><sup>?</sup>](#FPTD)
* [FTAB](#FTAB) - Font Table
* [GCPR<sup>c</sup><sup>?</sup>](#GCPR)
* [HIST](#HIST) - History
* [ICON<sup>?</sup>](#ICON)
* [LIbd<sup>?</sup>](#LIbd)
* [LIds<sup>c</sup><sup>?</sup>](#LIds)
* [LIfp<sup>?</sup>](#LIfp)
* [icl8](#icl8) - Icon ?
* [LIBN](#LIBN)
* [LVSR](#LVSR) - Version ?
* [MUID<sup>?</sup>](#MUID)
* [NUID<sup>c</sup><sup>?</sup>](#NUID)
* [OBSG<sup>c</sup><sup>?</sup>](#OBSG)
* [RTSG<sup>?</sup>](#RTSG)
* [SCSR<sup>c</sup><sup>?</sup>](#SCSR)
* [SUID<sup>c</sup><sup>?</sup>](#SUID)
* [TM80<sup>c</sup><sup>?</sup>](#TM80)
* [VCTP<sup>?</sup>](#VCTP)
* [VICD<sup>c</sup><sup>?</sup>](#VICD)
* [VITS<sup>?</sup>](#VITS)
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
### BNID<sup>c</sup><sup>?</sup>
12 bytes

```plain
00 00 00 02  00 00 00 00  00 00 00 00
```

***

<a name="wiki-CCSG" />
### CCSG<sup>c</sup><sup>?</sup>
16 bytes

***

<a name="wiki-CONP" />
### CONP<sup>?</sup>
2 bytes

```plain
00 01
```

***

<a name="wiki-CPC2" />
### CPC2<sup>?</sup>
2 bytes

```plain
00 01
```

***

<a name="wiki-CPMp" />
### CPMp<sup>c</sup><sup>?</sup>

***

<a name="wiki-DFDS" />
### DFDS<sup>c</sup><sup>?</sup>

***

<a name="wiki-DLDR" />
### DLDR<sup>c</sup><sup>?</sup>
28 bytes?

```plain
00 00 00 01  00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00
```

***

<a name="wiki-DTHP" />
### DTHP<sup>?</sup>
2 bytes

```plain
00 00
```

***

<a name="wiki-FPHb" />
### FPHb<sup>?</sup>

***

<a name="wiki-FPSE" />
### FPSE<sup>?</sup>
4 bytes

```plain
00 00 00 10
```

***

<a name="wiki-FPTD" />
### FPTD<sup>c</sup><sup>?</sup>
2 bytes
```plain
00 09
```

***

<a name="wiki-FTAB" />
### FTAB
<b>F</b>ont <b>Tab</b>le

***

<a name="wiki-GCPR" />
### GCPR<sup>c</sup><sup>?</sup>
13 bytes?

***

<a name="wiki-HIST" />
### HIST
<b>Hist</b>ory

***

<a name="wiki-ICON" />
### ICON<sup>?</sup>

***

<a name="wiki-LIbd" />
### LIbd<sup>?</sup>
<b>L</b>abVIEW <b>I</b>nstrument ?

***

<a name="wiki-LIds" />
### LIds<sup>c</sup><sup>?</sup>
<b>L</b>abVIEW <b>I</b>nstrument ?

***

<a name="wiki-LIfp" />
### LIfp<sup>?</sup>
<b>L</b>abVIEW <b>I</b>nstrument ?

***

<a name="wiki-icl8" />
### icl8
<b>ic</b>on ?  
See [[Icon]]

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
### MUID<sup>?</sup>
4 bytes

```plain
00 00 00 2b
```

***

<a name="wiki-NUID" />
### NUID<sup>c</sup><sup>?</sup>
16 bytes

***

<a name="wiki-OBSG" />
### OBSG<sup>c</sup><sup>?</sup>
16 bytes

```plain
00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00
```

***

<a name="wiki-RTSG" />
### RTSG<sup>?</sup>
16 bytes

```plain
00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00
```

***

<a name="wiki-SCSR" />
### SCSR<sup>c</sup><sup>?</sup>

***

<a name="wiki-SUID" />
### SUID<sup>c</sup><sup>?</sup>
12 bytes

```plain
00 00 00 02  00 00 00 00  00 00 00 00
```

***

<a name="wiki-TM80" />
### TM80<sup>c</sup><sup>?</sup>

***

<a name="wiki-VCTP" />
### VCTP<sup>?</sup>

***

<a name="wiki-VICD" />
### VICD<sup>c</sup><sup>?</sup>

***

<a name="wiki-VITS" />
### VITS<sup>?</sup>

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

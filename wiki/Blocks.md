## Contents
* [BDHb, BDHc](#BDH_)
* [BDPW](#BDPW)
* [FTAB](#FTAB)
* [icl8](#icl8)
* [LIBN](#LIBN)
* [LVSR](#LVSR)
* [vers](#vers)

***

<a name="BDH_" />
### BDHb, BDHc
This block is compressed
```plain
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | String length
      * | string  | Content
```

***

<a name="BDPW" />
### BDPW
```plain
 Length | Type    | Value
--------+---------+-------
     16 | string  | Password md5
     16 | string  | Hash 1
     16 | string  | Hash 2
```

***

<a name="FTAB" />
### FTAB
<b>F</b>ont <b>Tab</b>le, I believe.

***

<a name="icl8" />
### icl8
See [[Icon]]

***

<a name="LIBN" />
### LIBN
```plain
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | Count?
      1 | uint8   | String length
      * | string  | Content
```

***

<a name="LVSR" />
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

<a name="vers" />
### vers
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

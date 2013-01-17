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

### BDPW
```plain
 Length | Type    | Value
--------+---------+-------
     16 | string  | Password md5
     16 | string  | Hash 1
     16 | string  | Hash 2
```

### LIBN
```plain
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | Count?
      1 | uint8   | String length
      * | string  | Content
```

### BDHb, BDHc
This block is compressed
```plain
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | String length
      * | string  | Content
```

### icl8
See [[Icon]]
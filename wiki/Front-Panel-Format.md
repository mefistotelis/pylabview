
### Header
```plain
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | Data length
```

### Elements
```plain
 Length | Type    | Value
--------+---------+-------
      1 | uint8   | Field type
```

### Field: 10 - Section
```plain
 Length | Type    | Value
--------+---------+-------
      1 | uint8   | Type/ID/???
      1 | uint8   | Metadata count?
```

### Field: 11 - Section
```plain
 Length | Type    | Value
--------+---------+-------
      1 | uint8   | Type/ID/???
      1 | uint8   | Metadata count?
```


### Metadata: fe, fd, fb
```plain
 Length | Type    | Value
--------+---------+-------
      1 | uint8   | fe, fd, fb (unknown)
      2 | ?       | Unknown
```

### Field: 08 - uint8?
```plain
 Length | Type    | Value
--------+---------+-------
      1 | uint8   | 08
      1 | uint8   | Data
```

### Field: 09 - int8?
```plain
  Length | Type    | Value
--------+---------+-------
      1 | uint8   | 09
      1 | uint8   | Data
```

### Field: 24 - 1 byte?
```plain
 Length | Type    | Value
--------+---------+-------
      1 | uint8   | 64
      1 | uint8   | Type/ID/???
      2 | ?       | Unknown
```

### Field: 44 - 2 bytes?
```plain
 Length | Type    | Value
--------+---------+-------
      1 | uint8   | 44
      1 | uint8   | Type/ID/???
      2 | ?       | Unknown
```

### Field: 64 - 3 bytes?
```plain
 Length | Type    | Value
--------+---------+-------
      1 | uint8   | 64
      1 | uint8   | Type/ID/???
      3 | ?       | Unknown
```

### Field: 84 - 4 bytes?
```plain
 Length | Type    | Value
--------+---------+-------
      1 | uint8   | 84
      1 | uint8   | Type/ID/???
      4 | ?       | Unknown
```

### Field: c4 - Array
```plain
 Length | Type    | Value
--------+---------+-------
      1 | uint8   | c4
      1 | uint8   | Element type?
      1 | uint8   | Array length
      ? | ?       | Array data
```

### Field: 25 - Unknown
```plain
 Length | Type    | Value
--------+---------+-------
      1 | uint8   | 25
```

### Field: 2d - Unknown
```plain
 Length | Type    | Value
--------+---------+-------
      1 | uint8   | 2d
      6 | ?       | Unknown
```


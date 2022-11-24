Version is stored as a 32-bit number
```plain
 Offset | Length | Value
--------|--------+-------
     28 |      4 | Major (tens)
     24 |      4 | Major (ones)
     20 |      4 | Minor
     16 |      4 | Bugfix
     13 |      3 | Stage
      8 |      5 | Flags (5 bits?)
      4 |      4 | Build (tens)
      0 |      4 | Build (ones)
```

### Stage
```plain
 1: Development
 2: Alpha
 3: Beta
 4: Release
```
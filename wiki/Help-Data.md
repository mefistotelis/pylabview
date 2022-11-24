* [HLPP](#HLPP) - Help Path
* [HLPT](#HLPT) - Help Tag
* [STRG](#STRG) - String (description)

<a name="wiki-HLPP" />
### HLPP
```plain
 Length | Type    | Value
--------+---------+-------
      4 | string  | PTH0 - Path 0?
      4 | uint32  | ?
      2 | uint16  | ?
      2 | uint16  | Count
```

Count of the following:
```plain
 Length | Type    | Value
--------+---------+-------
      1 | uint32  | String Length
      * | uint32  | String
```

***

<a name="wiki-HLPT" />
### HLPT

```plain
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | Tag Length
      * | string  | Tag
```

***

<a name="wiki-STRG" />
### STRG

```plain
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | String Length
      * | string  | String
```

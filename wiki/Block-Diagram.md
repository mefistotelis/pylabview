* [BDHb, BDHc](#BDH_) - Block Diagram ?
* [BDPW](#BDPW) - Block Diagram Password
* [BDSE](#BDSE) - Block Diagram ?

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

<a name="wiki-BDPW" />
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

<a name="wiki-BDSE" />
### BDSE

<b>B</b>lock <b>D</b>iagram  

```plain
 Length | Type    | Value
--------+---------+-------
      4 | uint32  | 
```

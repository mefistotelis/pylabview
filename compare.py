#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" LabView RSRC files compare.

Experimental tool.
"""

import readRSRC
from colorama import Fore
import sys

fn1 = "examples/AB2.vi"
fn2 = "examples/AB4Courier.vi"
if len(sys.argv) > 1:
    fn1 = sys.argv[1]
    fn2 = sys.argv[2]

vi1 = readRSRC.VI(fn1)
vi2 = readRSRC.VI(fn2)

for i in range(0, len(vi1.blocks_arr)):
    name = vi1.blocks_arr[i].name
    data1 = vi1.get(name).raw_data[0]
    data2 = vi2.get(name).raw_data[0]
    if name == "BDHb":
        open("dumps/BDHb1.dmp", "wb").write(data1)
        open("dumps/BDHb2.dmp", "wb").write(data2)
    if data1 != data2:
        print(name)
        for i in range(0, len(data1)):
            if i % 48 == 0:
                print()
                y = 0
            p = ("0" + hex(ord(data1[i]))[2:])[-2:]
            if i % 4 == 0 and y != 0:
                p += " "
            y += 1
            if i >= len(data2) or data1[i] != data2[i]:
                print(Fore.BLUE + p + Fore.RESET, end=' ')
            else:
                print(p, end=' ')
        print()
        for i in range(0, len(data2)):
            if i % 48 == 0:
                print()
                y = 0
            p = ("0" + hex(ord(data2[i]))[2:])[-2:]
            if i % 4 == 0 and y != 0:
                p += " "
            y += 1
            if i >= len(data1) or data1[i] != data2[i]:
                print(Fore.BLUE + p + Fore.RESET, end=' ')
            else:
                print(p, end=' ')
        print()
        print()

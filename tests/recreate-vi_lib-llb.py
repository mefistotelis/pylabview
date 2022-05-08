#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" Test for pyLabview project.
    UNFINISHED - this is just a WIP on translating shell scripts into python tests.
"""

# Copyright (C) 2021 Mefistotelis <mefistotelis@gmail.com>
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

import unittest
import os
import pathlib
import subprocess
import sys

class ScriptTest(unittest.TestCase):
    def test_script(self):
        rsrc_inp_fn = os.path.join("examples", "blank_project1_extr_from_exe_lv14f1.llb")
        rsrc_path, rsrc_filename = os.path.split(rsrc_inp_fn)
        rsrc_path = pathlib.Path(rsrc_path)
        rsrc_basename, rsrc_fileext = os.path.splitext(rsrc_filename)
        xml_fn = f"{rsrc_basename}.xml"
        rsrc_out_fn = f"{rsrc_basename}{rsrc_fileext}"
        #single_vi_path = ${rsrc_path#*/}  # remove first folder
        if len(rsrc_path.parts) > 1:
            single_vi_path = os.sep.join(["test_out", *rsrc_path.parts[1:]])
        else:
            single_vi_path = "test_out"
        os.mkdir(single_vi_path)
        command = [os.path.join("pylabview", "readRSRC.py"), "-vv", "-x", "--keep-names", "-i", rsrc_inp_fn, "-m", os.sep.join([single_vi_path, xml_fn])]
        print(str(command))
        with subprocess.Popen([sys.executable or 'python', *command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True) as process:
            prout, prerr = process.communicate()
        prout = prout.decode("utf-8")
        prerr = prerr.decode("utf-8")
        # TODO check return code, output streams, and presence of expected xml file
        #self.assertEqual(prout, '8')


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(ScriptTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

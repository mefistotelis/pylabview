# pylabview

Tools for extracting, changing, and re-creating LabView RSRC files, like VIs or CTLs.

# Motivation

LabView environment is unneccessarily closed. Its mechanisms prevent the developers
from dodifying projects outside of the GUI, which makes scalability painful.

If you want to modify something in 1000 of files, and you're not really into
clicking through all that, this might be the tool for you.

Besides batch processing of LabView files, this tool should be also helpful
for fixing the ones which LabView refuses to read.

# Tools

Running the tools without parameters will give you details on supported commands
in each of them.

To get specifics about command line arguments of each tool, run them with `--help`
option. Some tools also have additional remarks in their headers - try viewing them.

# File format

To learn abot file format, check out wiki of this project.

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

# Verification

If you want to verify whrther your specific file will be handled correctly by the tool, try:
- extracting it to XML
- re-creating it from the XML
- checking whether oroginal and re-created file are binary identical, or load with all features in LabView

Note that many LLB files created by the tool will not be binary identical to the originals; this is because some items in these files are not ordered, and the order depends on specific timing between threads while the file was saved.

A few example files are included in the project.

# File format

To learn abot file format, check out wiki of this project.

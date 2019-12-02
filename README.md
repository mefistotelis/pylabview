# pylabview

Tools for extracting, changing, and re-creating LabVIEV RSRC files, like VIs or CTLs.

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

# Reversing EXE back to buildable project

While it is possible to reverse the EXE built with LabVIEW to its source, there are no tools to automate such conversion at the moment. When VI files are being build, some elements are removed from them:
- Block Diagram is removed and repaced by 'compiled' version, optimized to run on a specific version of labVIEW Runtime Environment (LVRT)
- If the VI Front Panel is unused, it is also removed.

The missing elements can be re-created, but currently there is no tool to do so. We don't even have a tool which would fully read all elements of the VI file - and that is required to try and re-construct missing parts.

Still, even without the full VI reversed so source form, it is possible to extract the EXE back to a project, which then can be re-built with the same version of LabView which was originally used. It is then possible to start replacing single VIs with a newly created ones, while retaining useability of the whole project.

In order to reverse an EXE back to LabView project:

1. Extract EXE, decrypt ZIP inside

2. Create a folder, create new LabView project there

3. create sub-folder within project folder, ie. "app" or "lv" or however you want to call the labview app part; copy the files extracted from ZIP there

4. Copy any config and data files (and folders) distributed with original binary to the project folder

5. Copy options from BinryName.ini into your BinaryName.lvproj (created in step 2)

6. Open the project in LabView

7. Add each folder from your labview app part to the project; use "My Computer" -> "Add" -> "Folder (Auto-populating)"

8. Make new build target; use "Build Specifications" -> "New" -> "Application"

9. Set proper "Name: and "Target filename" in build target "Information" tab

10. Find the starting form of the original app and add it as "Startup VIs" in build target "Source files" tab

11. You shouldn't have to put anything in "Always included" list in build target "Source files" tab; but if you want - you can now

12. Disable all the "Remove ..." and "Disconnect ..." options in build target "Additional Exclusions" tab

13. Fix any "Missing items" in the project, by placing files in correct places or modifying *.lvlib files which point to locations of additional files (VIs with both Front Panel and Block Diagram removed will require manual fixing of the paths inside, as LabVIEW will refuse to load them, and therefore to re-save them with different paths)

14. Build the project

# Text Code Pages

The RSRC files use various code pages, depending on OS on which the file was created.
On reading RSRC file, you can provide the code page as a parameter.

Example code pages you could use:

| TextEncoding | Related Operating System |
| ------------ | ------------------------ |
| mac_cyrillic | MacOS Bulgarian, Byelorussian, Macedonian, Russian, Serbian |
| mac_greek    | MacOS Greek |
| mac_iceland  | MacOS Icelandic |
| mac_latin2   | MacOS Central and Eastern Europe |
| mac_roman    | MacOS Western Europe (and US) |
| mac_turkish  | MacOS Turkish |
| cp1250       | Windows Central and Eastern Europe |
| cp1251       | Windows Bulgarian, Byelorussian, Macedonian, Russian, Serbian |
| cp1252       | Windows Western Europe (and US) |
| cp1253       | Windows Greek |
| cp1254       | Windows Turkish |
| cp1255       | Windows Hebrew |
| cp1256       | Windows Arabic |
| cp1257       | Windows Baltic languages |
| cp1258       | Windows Vietnamese |
| shift_jis    | Windows Japanese |
| gbk          | Windows Chinese (simplified) |
| cp949        | Windows Korean Hangul |
| cp950        | Windows Chinese (traditional) |
| utf-8        | Universal encoding, used by everyone except NI for decades |

# File format

To learn abot file format, check out wiki of this project.

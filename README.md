# pylabview

Tools for extracting, changing, and re-creating LabVIEV RSRC files, like VIs or CTLs.

# Motivation

LabView environment is unneccessarily closed. Its mechanisms prevent the developers
from modifying projects outside of the GUI, which makes scalability painful.

If you want to modify something in 1000 of files, and you're not really into
clicking through all that, this might be the tool for you.

Besides batch processing of LabView files, this tool should be also helpful
for fixing the ones which LabView refuses to read.

# Tools

Running the tools without parameters will give you details on supported commands
in each of them.

To get specifics about command line arguments of each tool, run them with `--help`
option. Some tools also have additional remarks in their headers - try viewing them.

The first tool to use is `readRSRC.py` and extract the RSRC file into a form
which is easier to understand and modify.

# Supported versions

The tools were tested on all standard VIs from LabVIEW 2014 and LabVIEW 6.0.
These standard VIs included a variety of versions, ie LV14 contains some VIs
created in previous versions down to LabVIEW 8.6.

But the actual development was made with LabVIEW 2014 in mind. Other versions may get
less resources converted to XML, or may require some tweaks to work.

# Verification

If you want to verify whrther your specific file will be handled correctly by the tool, try:
- extracting it to XML
- re-creating it from the XML
- checking whether oroginal and re-created file are binary identical, or load with all features in LabVIEW

Note that some files created by the tool will not be binary identical to the
originals. This includes many LLB files, and some VIs from LV6.0 and older.
The differenes in LLB can happen because string names in these files are not ordered,
and the order depends on specific timing between threads while the file was saved
(this tool always uses the same ordering of all items).
The differenes in old VI files are due to unpredicatable values used for padding
between actual data (this tool uses zeros for padding).

A few example files are included in the project.

# Use cases

The general intended use of the tools is as follows:
- extract RSRC file to XML form
- look at the resulting XML, perform modifications
- re-create RSRC file from the XML

Several specific things you can do with these tools are listed below.
One caveat worth noticing is that these tasks are not fully automated. To use
these functions, you must know what you're doing, and modify the scripts where
apropriate.

### Look at the data inside VI file

If you don't have a LabVIEW license, and want to look inside some VIs, these
tools can help. You can convert your VIs to XML format, and then look at the XML.

It is possible to write a viewer, which displays the XML data in graphical
form, like they look in LabVIEW. Such viewer does not exist at the moment.

### Look at the compiled code inside VI file

If you want to look at assembly bytecode, the tool will create a BIN file with
that code during VI extraction. It will even prepare a MAP file, with some known
symbols within the code. Base address of the extracted code is always 0x0.
Relocations and imports are stored in an array called 'Patches', and for most
versions of LV, the tool will store these within XML file.

### Batch process VIs

You can extract, modify and re-create VIs. So as long as you can write a script
which does proper modification to XMLs, you can automatically apply a change
to thousands of VI files, without the need of clicking through LabVIEW GUI.

### Reverse a compiled VI project

You can look into internals of a compiled VI project. You can also, to some
extent, convert the EXE cack to source form. Though at the moment, the tools
will not allow you to automatically recover Block Diagram which is lost during
VIs compilation process. There is a script which recovers Front Panel from
a VI which had it removed.

It is possible to write a tool which recovers these items completely, though.

### Fix damaged VI files

The extractor can be modified to ignore errors and read damaged VI file. Then
it can re-create the VI from XML, and it will use proper format required by
LabVIEW. So it can be used to fix a VI file, though there is no premade
parameter which will do it for you.

### Backport VI files

You can modify version numbers in XML files, and the tools will re-create
VIs using structures from the updated version markings. There is no automated
version changer though - if the switch requires some blocks to be renamed,
or some data added - you will have to do it manually.

# Reversing EXE back to buildable project

While it is possible to reverse the EXE built with LabVIEW to its source, there
are no tools to automate such conversion at the moment. When VI files are being
build, some elements are removed from them:
- Block Diagram is removed, leaving only compiled version. The compiled version
 is kind of OBJ file, which can only run on a specific CPU, and specific
 version of LabVIEW Runtime Environment (LVRT).
- If GUI of the VI file is never shown, the unused VI Front Panel is also removed.

The missing elements can be re-created, and doing so with use of the XML format
is much easier than doing that directly with binary form of the VI files.
A script which reads the XML and re-constructs missing parts is in the project,
though it currently reconstructs only Front Panel. The reconstructing script
is not as thoroughly tested as the XML extractor, so may require some tweaks to
work with a specific project.

Even without the VIs fully reversed so source form, it is possible to extract
the EXE back to a project, which then can be re-built with the same version of
LabView which was originally used. It is then possible to start replacing
single VIs with a newly created ones, while retaining useability of the whole
project.

In order to reverse an executable back to LabView project:

### 1. Extract RSRC file from the executable

Use any tool you see fit. In case of Windows `PE` executable, you may use
`wrestool`, or if you prefer GUIs, [Resource Hacker](https://en.wikipedia.org/wiki/Resource_Hacker).
You may also just find `RSRC` in file content and copy the data starting from
that position, using `dd`. Any method should work, as long as you receive the
file with `RSRC` header.

### 2. Decrypt the ZIP from within RSRC file

The `RSRC` file will contain weakly encrypted ZIP. Extract it with the tools from this repo.

### 3. Get proper LabVIEW version

Look inside VI files from the ZIP to figure out which version of LabVIEW was used to create them. You can look at the versions by extraction one of the vIs to XML form. Use the exact same version for further steps.

### 4. Make new LabView project

Create a folder. Open LabVIEW. Create new LabView project in the new folder.

### 5. Copy VIs to the project folder

Create sub-folder within the project folder, ie. `app` or `lv` or however you want to call the labview app part; copy the files extracted from ZIP there.

### 6. Copy non-VI dependencies

Copy any config and data files (and folders) distributed with original binary (either within the ZIP, or just placed in the same folder where the EXE you've extracted) to the project folder.

### 7. Copy LV Runtime Engine settings

Copy options from BinryName.ini into your BinaryName.lvproj (created in step 4).

### 8. Open the project in LabView

Just run LabVIEW and open your project. Noe that LabVIEW still considers your project to be empty.

### 9. Add VIs to the LV project

Add each folder from your labview app part to the project. Use "My Computer" -> "Add" -> "Folder (Auto-populating)".

### 10. Create build target in the LV project

To make the new build target, use "Build Specifications" -> "New" -> "Application".

### 11. Set build target settings

Set proper "Name: and "Target filename" in build target "Information" tab.

### 12. Set build target Startup VI

Look at the starting form from original app. Find the starting panel in your VIs, and add it as "Startup VIs" in build target "Source files" tab.

You shouldn't have to put anything in "Always included" list in build target "Source files" tab. Each VI stores its dependencies, so LV should be able to figure out which files to include in your build. But if you want - you can add some files there now.

### 13. Disable removing things from VIs

Disable all the "Remove ..." and "Disconnect ..." options in build target "Additional Exclusions" tab.

### 14. Fix "Missing items"

LabVIEW will likely inform you of "Missing items" in the project. You can fix these by placing files in correct places or modifying file paths within the files which reference them. Usually, LabVIEW will ask you dozens of questions in regard to which file you want to use; but after that, most "Missing items" will be fixed. Probably not all though - VIs with both Front Panel and Block Diagram removed will require manual fixing of the paths inside, as LabVIEW will refuse to load them, and therefore will not re-save them with different paths.

### 15. Build the project

If you encounter further errors, fix them. If you've solved the "Missing items", everything else is simple and you shouldn't have much problems.

Now you have a LabVIEW project which allows you to re-build the EXE.

You may look into converting to XML all the VIs which are missing Front Panel,
and recovering these Front Panels.

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

Note that changing text code pages of VI files will not influence extraction
of ZIP files which were stored inside RSRC sections, and the code pages of
file names within the ZIP. Use proper `unzip` switches to change these.

# File format

To learn about file format, check out wiki of this project.

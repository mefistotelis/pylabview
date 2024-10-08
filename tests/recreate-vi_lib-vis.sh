#!/bin/bash
# Test extraction and re-creation of VI files
# You need a group of vi/ctl/vit/mnu files to execute this test on.
# To verify changes in pylabview code, directory 'vi.lib'
# from LV installation can be used.
set -x
#set -e

# Files from LV2 have no ordering of sections, so when the file from there is extracted an re-created,
# it is usually different. For those old files, we'd have to compare extracted sections. So skipping here.
if [ $# -eq 0 ]; then
    echo "No custom folders supplied - using default list"
    SRC_VI_DIRS="../lv060 ./lv060 ../lv071 ./lv071 ../lv100 ./lv100 ../lv140 ./lv140"
else
    echo "Custom folders set from parameter list"
    SRC_VI_DIRS="$@"
fi
STORE_EXTRACTED_FILES=true

mkdir -p ../test_out
pushd ../test_out

echo | tee log-vi_lib-vi-1extr.txt
echo | tee log-vi_lib-vi-2creat.txt
echo | tee log-vi_lib-vi-3cmp.txt


# LLB files generated by the tool are NOT the same as original on binary level. That's because names section generation has time dependencies.
# Find supported files, other than LLBs. We have a separate script for the LLBs.
find ${SRC_VI_DIRS} -type f -iname '*.vi' -o -iname '*.ctl' -o -iname '*.vit' -o -iname '*.mnu' -o -iname '*.ctt' -o -iname '*.uir' -o -iname '*.lsb' -o -iname '*.rsc' | tee log-vi_lib-vi-0list.txt

# Remove files which generate irrelevant differences due to different order inside
sed -i -n '/lv071\/user[.]lib\/\(dir\)[.]mnu/!p' log-vi_lib-vi-0list.txt
sed -i -n '/lv100\/menus\/[^\/]\+\/[^\/]\+\/\(dir\)[.]mnu/!p' log-vi_lib-vi-0list.txt
sed -i -n '/lv100\/menus\/Controls\/[^\/]\+\/\(3dio\|io\)[.]mnu/!p' log-vi_lib-vi-0list.txt
sed -i -n '/lv100\/menus\/default\/[^\/]\+\/\(instr\|picture\)[.]mnu/!p' log-vi_lib-vi-0list.txt
sed -i -n '/lv100\/menus\/default\/\(root\)[.]mnu/!p' log-vi_lib-vi-0list.txt

while IFS= read -r rsrc_fn; do
    rsrc_out_fn=$(basename "${rsrc_fn}")
    rsrc_dir=$(dirname "${rsrc_fn}")
    rsrc_base_fn=${rsrc_out_fn%.*}
    xml_fn="${rsrc_base_fn}.xml"
    if $STORE_EXTRACTED_FILES; then
        rsrc_out_dir=${rsrc_dir#"./"}
        rsrc_out_dir="./extract/"${rsrc_out_dir#"../"}
        mkdir -p "${rsrc_out_dir}"
    else
        rsrc_out_dir="."
    fi

    (export PYTHONPATH=".."; ../pylabview/readRSRC.py -vv -x -i "${rsrc_fn}" -m "${rsrc_out_dir}/${xml_fn}") 2>&1 | tee -a log-vi_lib-vi-1extr.txt
    #mv "${rsrc_fn}" "${rsrc_fn}.orig"

    # Now some fixups for XML parser not meeting standards; will be fixed in Python 3.9
    if [[ "${rsrc_fn}" == *'/Equi-Ripple BandPass (CDB).vi' ]] || \
       [[ "${rsrc_fn}" == *'/Equi-Ripple BandPass (DBL).vi' ]] || \
       [[ "${rsrc_fn}" == *'/Equi-Ripple BandStop (CDB).vi' ]] || \
       [[ "${rsrc_fn}" == *'/Equi-Ripple BandStop (DBL).vi' ]] || \
       [[ "${rsrc_fn}" == *'/Equi-Ripple HighPass (CDB).vi' ]] || \
       [[ "${rsrc_fn}" == *'/Equi-Ripple HighPass (DBL).vi' ]] || \
       [[ "${rsrc_fn}" == *'/Equi-Ripple LowPass (CDB).vi' ]] || \
       [[ "${rsrc_fn}" == *'/Equi-Ripple LowPass (DBL).vi' ]] || \
       [[ "${rsrc_fn}" == *'/Equi-Ripple BandPass PtByPt.vi' ]] || \
       [[ "${rsrc_fn}" == *'/Equi-Ripple BandStop PtByPt.vi' ]] || \
       [[ "${rsrc_fn}" == *'/Equi-Ripple HighPass PtByPt.vi' ]] || \
       [[ "${rsrc_fn}" == *'/Equi-Ripple LowPass PtByPt.vi' ]] || \
       [[ "${rsrc_fn}" == *'/Parks-McClellan.vi' ]] || \
       [[ "${rsrc_fn}" == *'/ma_sml_Compensation Filter Design.vi' ]] || \
       [[ "${rsrc_fn}" == *'/ma_Equi-RippleFIRCoeff.vi' ]] || \
       [[ "${rsrc_fn}" == *'/ma_Design FIR Coeff.vi' ]] || \
       [[ "${rsrc_fn}" == *'/ma_sml_Last Stage FIR Filter Design.vi' ]] || \
       false; then
        (echo "FIX ${rsrc_out_fn} - it contains CR which ElementTree converts to LF") 2>&1 | tee -a log-vi_lib-vi-1extr.txt
        sed -i 's/"\(Weighted\)&#10;\(Ripple\)"/"\1\&#13;\2"/' "${rsrc_out_dir}/${xml_fn}"
    elif [[ "${rsrc_fn}" == *'/Serial Port Reset.vi' ]] || \
       false; then
        (echo "FIX ${rsrc_out_fn} - it contains CR which ElementTree converts to LF") 2>&1 | tee -a log-vi_lib-vi-1extr.txt
        sed -i 's/"\(.* HShk[.]\)&#10;\([\(][A-Z]\+[\)]\)"/"\1\&#13;\2"/' "${rsrc_out_dir}/${xml_fn}"
    fi

    (export PYTHONPATH=".."; ../pylabview/readRSRC.py -vv -c -m "${rsrc_out_dir}/${xml_fn}" -i "${rsrc_out_fn}") 2>&1 | tee -a log-vi_lib-vi-2creat.txt

    # Get version of LabVIEW from the XML file
    rsrc_lvver=$(grep -A30 '^[ \t]*<vers>$' "${rsrc_out_dir}/${xml_fn}" | grep -B30 '^[ \t]*</vers>$' | sed -n 's/^[ \t]*<Version[ \t]\+.*Major="\([0-9]\+\)".*Minor="\([0-9]\+\)".*$/\1.\2/p' | head -n 1)
    if [[ "${rsrc_lvver}" == '6.'* ]] || \
       [[ "${rsrc_lvver}" == '7.'* ]] || \
       false; then
        # Old LV versions have random values at padding; ignore differences where non-zero value was replaced by zero
        (cmp -l "${rsrc_fn}" "${rsrc_out_fn}") 2>&1 | grep -v '^[ ]*[0-9]\+[ ]\+[0-7]\+[ ]\+0$' | head -n 64 | tee -a log-vi_lib-vi-3cmp.txt
    elif [[ "${rsrc_fn}" == *'/FFT Power Spectrum.vi' ]] || \
       false; then
        # For some specific files, ignore EOLN conversion inconsistencies
        (cmp -l "${rsrc_fn}" "${rsrc_out_fn}") 2>&1 | grep -v '^[ ]*[0-9]\+[ ]\+15[ ]\+12$' | head -n 64 | tee -a log-vi_lib-vi-3cmp.txt
    else
        (cmp -l "${rsrc_fn}" "${rsrc_out_fn}") 2>&1 | head -n 64 | tee -a log-vi_lib-vi-3cmp.txt
    fi
    rsrc_base_pattern="${rsrc_base_fn}"
    rsrc_base_pattern="${rsrc_base_pattern//[/\\[}"
    rsrc_base_pattern="${rsrc_base_pattern//]/\\]}"
    rm "${rsrc_out_fn}"
    if ! $STORE_EXTRACTED_FILES; then
        find "${rsrc_out_dir}/" -maxdepth 1 -type f -name "${rsrc_base_pattern}*" -exec rm {} +
    fi
done < log-vi_lib-vi-0list.txt

popd

sed -n 's/^.*\(Warning: .*\)$/\1/p' ../test_out/log-vi_lib-vi-1extr.txt | sort | uniq -c | sort > ../test_out/log-vi_lib-vi-1extr-warns.txt

if grep -q '^\(cmp:\|[ ]*[0-9]\+ \)' ../test_out/log-vi_lib-vi-1extr.txt; then
    echo Some comparisons FAILED!
else
    echo All tests ended with SUCCESS
fi

exit 0

# A fresh Magic process prevents extresist retaining the earlier hierarchical
# extraction root. This stage extracts only the explicitly flattened cell.
cd $::env(TG_RUN_DIR)
load adc_tgate_flat
select top cell
expand
extract all
extresist threshold 0
extresist minres 0
extresist mindelay 0
extresist all
ext2spice lvs
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist on
ext2spice -o adc_tgate_flat.rc.spice
quit -noprompt

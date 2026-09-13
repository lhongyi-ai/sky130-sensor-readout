# UNROUTED assembly geometry check only. Does not verify chip connectivity.
cd /repo/v2/physical/core_integration_20260913
crashbackups stop
drc off
gds read reusable_macros_UNROUTED.gds
load REUSABLE_MACROS_UNROUTED_20260913
select top cell
expand
drc on
drc check
drc catchup
puts "ASSEMBLY_UNROUTED_DRC_COUNT [drc count total]"
puts "ASSEMBLY_UNROUTED_DRC_DETAILS [drc listall why]"
quit -noprompt

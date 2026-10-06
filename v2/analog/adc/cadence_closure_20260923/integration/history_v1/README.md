# Historical v1 AMS preparation

This retained version assembled the actual reset1 ADC, native phases and original RTL for two-frame/12-frame tests. It is superseded by the current integration package and is not an accepted numerical configuration.

Its baseline global reltol request was 1e−6. The installed conservative preset tightens the effective value further, so copying an earlier effective log value into the global request inadvertently added another factor of ten. This preparation failure remains part of the history. Build strict variants in separate directories and verify actual effective V/I/relative tolerances from the log rather than assuming the request is the realized value.

Native connectivity, reset port, original RTL, finite reference network, input source resistance and original full-domain threshold remain required. A prepared file, repeated output code or incomplete common prefix does not qualify the ADC. See [current integration](../../README.md) and the top-level RESULTS report for subsequent actual outcomes.

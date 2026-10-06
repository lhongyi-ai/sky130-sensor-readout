# First internal-body probe

In the actual first-acquisition probe, external CONV−VDD crossed zero within a 201.302 fs accepted step. The ordinary phase-output PFET int_b voltage decreased by 449.092 µV while its local gate remained smooth. External source and bulk were correctly tied to VDD.

This localizes a source/drain-direction/body-network hypothesis. It does not identify a PDK defect, prove a physical discontinuity or qualify the ADC. The log timestamp is rounded and does not expose the failed Newton iteration. Subsequent actual reversed/dbnode/sbnode and terminal-current controls are documented separately in `body_network_probe_review/`.

The complete ADC precision threshold remains 9.765625 µV over the predefined domain. Source literals and current model hashes are provenance, not resolved simulator selector values. Evidence: `first_body_probe_review.json` and the adjacent figure.

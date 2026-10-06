# Prepared internal-body observability probe

The frozen first-phase actual ADC input was copied without changing its model, 741-device circuit, RTL, stimulus, reference, reset, stop time, solver or tolerances. The only EDA changes are four save lines requesting dbnode/sbnode, vds/reversed and four terminal currents while retaining int_b/local gate.

Run only in a new result directory and preserve all inputs, logs, exit states and raw PSF. A successful 4.1 µs diagnostic simulation is expected to fail the inherited complete two-frame protocol check; that status must not be relabeled PASS. Missing saves must remain missing, without synthetic replacement nodes.

```sh
python3 verify_inputs.py
bash run.sh 120
python3 inspect_saved_outputs.py
```

The package is an observability experiment. Actual completed results are in `../body_network_probe_review/`. Temporal mode/body association needs controlled precision and complete ADC follow-up before any supported repair is accepted.

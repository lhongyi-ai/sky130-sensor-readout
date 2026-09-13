# Learning Checkpoint for This Stage

Start with these five questions to understand the new project; no Cadence operation is needed first.

1. **What do the PGA and ADC each do?** The PGA amplifies a small signal into a suitable range; the ADC converts it into an integer within a finite time. As gain increases, the allowed input amplitude must decrease accordingly.
2. **Why does 12-bit not mean 12-bit effective accuracy?** 12-bit specifies only 4096 output codes. Noise, distortion, and settling error reduce the information that can actually be resolved, so SNDR/ENOB is measured separately.
3. **Why make 12 comparisons?** SAR tries the most significant bit first and then narrows the range by successive binary decisions. Acquisition takes 4 cycles and decisions take 12 cycles, giving 10 µs per frame at a 1.6 MHz clock.
4. **What can calibration fix?** Linear calibration corrects fixed offset and scale errors; it cannot remove random noise, mismatch nonlinearity, or unstable sampling. Observing drift with one fixed set of coefficients shows how robust calibration is.
5. **Why does a passing model still not mean a passing chip?** We currently assign the model numerical gain, noise, and other parameters; the next step is to prove that real transistors, layout, and parasitics can deliver those values.

Choose one passing and one failing result from the experiment report and explain in your own words: what the input was, what was measured, why it passed/failed, and what evidence is still missing.

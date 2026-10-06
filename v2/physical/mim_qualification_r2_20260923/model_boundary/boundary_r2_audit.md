# Fixed-reference external-lead audit

Actual GDS readback confirmed the same 84 core rectangles, including 81 via3 cuts, in both samples. PLUS=(4.8,0.4) µm stays fixed; only the external 0.5 µm-wide M4 lead changes from 10 to 30 µm, with FAR at 14.8/34.8 µm.

Both passed nine project MIM checks and LVS, retained one functional model and completed Spectre DC with zero errors/warnings. FAR→PLUS resistance is 0.94/2.82 Ω. The 1.88 Ω difference equals the current technology's 0.047 Ω/□×20/0.5 arithmetic, not an independently measured sheet resistance.

Core access resistances remain 0.150199 Ω on PLUS and 0.043084 Ω on MINUS. Only external-lead R and its distributed C change. A capacitance attached to PLUS can still belong to the changing lead; node attachment alone does not establish ownership.

QRC's explicit via term approximately 3.41/81=0.042099 Ω coexists with model contact R approximately 0.067679 Ω at nominal27°C. No original physical reference plane justifies deleting either term. DC opens the capacitor, so this test did not measure functionality, loss or edge fields. Exact coordinates, hashes and the retained JSON-format comparison failure are in `boundary_r2_audit.json`.

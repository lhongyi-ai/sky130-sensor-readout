# Minimal runtime experiment configurations

These three project-authored drafts use documented interfaces and contain no school material parameters: a minimal layer setup, no-block command and plate-capacitance-block command. Use absolute paths in an otherwise validated process_technology setup, preserving actual technology directory, PVS inputs and functional-instance output.

```text
-technology_layer_setup_file /path/to/project/layer_setup_minimal
-technology_command_file /path/to/project/runtime_no_block.cmd
```

Run the block variant independently, with only the command-file selection changed. These drafts were not executed by the documentation subtask; actual later results are in the parent r1 record.

CAPM must not be mapped to ordinary metal4 to invent height/thickness/coupling. Installed documentation describes unmapped conductor/contact layers as zero-resistance connectivity with ignored capacitance. That can preserve connectivity for a small diagnostic but leaves CAPM coupling and thin-electrode resistance unqualified. It may also bypass contact resistance, requiring explicit checks.

Do not delete CAPM, delete the functional device, point to a nonexistent layer or suppress warnings. This limited mapping is unsuitable for a complete core whose other conductors and devices are omitted.

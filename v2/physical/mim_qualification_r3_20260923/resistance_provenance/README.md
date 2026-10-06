# Absolute resistance/reference-temperature provenance

The installed M3/M4/via3 device models explicitly use tnom=30°C. Their examined sheet/via parameter file matches the frozen public file, with0.047 Ω/□ and3.41 Ω. The whole model file differs through a documented naming compatibility edit; whole-file identity is not claimed.

QRC exports effective temp_reference25°C, the same numeric base values, and originally no TC1/TC2. Installed documentation allows a default25°C reference, so the export cannot distinguish a deliberate physical reference from an omitted value filled by the tool. Original ICT/generation provenance was not obtained.

Rebinding the public temperature law correctly demonstrates normalized response, but leaves approximately1.7438%/1.2234% same-temperature base differences. Neither a numerical match nor a community unmerged Synopsys ITF proves current-school build/measurement provenance or permits modifying base resistance.

Public model history changed tref to tnom while retaining30, not25→30. Exact fixed-source links, hashes, bounded school metadata and differences remain in `public_temperature_history.json` and adjacent records. Preserve r2 as a restricted experimental configuration until an applicable version/corner/reference/conversion contract is obtained.

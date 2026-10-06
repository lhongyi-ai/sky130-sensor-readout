# Actual 4µm two-device access controls

Status: SCOPED_ACCESS_GEOMETRY_AND_LVS_VERIFIED. Three new school cells were created and independently audited from actual GDS, DRC/LVS and extracted-device records. No PEX/electrical-performance qualification is claimed.

Each normal/open/short sample passed279 ordinary geometric checks and nine project MIM checks with zero violations. Normal LVS matched two4×4µm devices, three ports/nets. Removing BITB's external via4 produced MISMATCH with four nets and an internal second-bottom node. Shorting bottoms produced MISMATCH with two ports/nets and merged BITA/BITB labels.

All samples retain both devices, correct dimensions, zero black boxes and zero unperformed comparison cells. Electrical defects need not violate geometry; DRC=0 on a wrong connection is not validation. Exact primary-cell identity was checked rather than inferred from summary filenames.

The normal extracted ports are TOP–BITA and TOP–BITB. This verifies a scoped access geometry/connectivity contract only. CAPM absolute coupling, internal/external RC boundaries, full array and formal ADC PEX remain incomplete. Actual independent evidence is in the adjacent review records; original prepared inputs and failures are preserved.

# Static charge / source-drain mode boundary, v1

This isolates a static model derivative question from transient integration. It is not a repair or ADC pass. The exact school native PFET W=32 µm,L=150 nm,m=1 and original source/drain junction areas/perimeters are retained. Gate is fixed at the observed reversal mean0.91642555277800053V, source/externalbulk1.8V. Only externalD−S is swept. NoPDK, body-network, capacitance selector, gmin, cmin or initial-condition changes.

Each profile performs four namedDC analyses: ±20mV wide(up/down), ±1mV fine(up/down). Baseline steps100µV/1µV; strict50µV/0.5µV plus tenfold tighterreltol/vabstol/iabstol. InstalledDChelp supportsstart/stop/lin; positive stepcounts give opposite directions without guessing negative-step semantics. Actualpoints must match manifest. `force=none,useprevic=no` avoids carrying an initialcondition betweenanalyses; `swpuseprevic=yes` uses each preceding converged sweep point, preserving direction as a meaningful diagnostic.

Serial root scheduler in the existingconfigured schoolenvironment:

```bash
bash run_case.sh baseline 120
bash run_case.sh strict 120
```

Every run creates an independentdirectory retaining all rawDC/info outputs and trueexitcode. No transient/LTE claim can follow fromDC. No expensivefullADC is dispatched bythisrunner.

Read actualoutput schema first. InstalledBSIM4help explicitly lists totalqg/qd/qs/qb, separatejunctionqjd/qjs, intrinsicqgi/qdi/qsi/qbi, totalCmatrix and intrinsicderivativescgdbo/cddbo/cbdbo. All are saved bydocumented names. Missing or rejectedfields must be reported; never replacedbyzero. int_b/dbnode/sbnode are the three internalnodes already verified onschoolSpectre21; unverifiedint_g/int_d/int_s aliases are intentionally absent. DocumentedOP bias outputs vgs/vgd/vds/vbs/vdb/vgb supplementexternalbias observations.

Foranalysis, preserve rawcharge signs and reversed enum. Do not multiplybyPFETtype or automaticallyswapqdi/qsi. Comparebranch-resolved signed differences ofintrinsicqgi/qdi/qbi with thehelp's -cgdbo/+cddbo/-cbdbo only as diagnostic pairs. A derivativealongresolved externalD includeschainresponse ofinternalBP/DB/SB andotherinternalnodes, whereasintrinsicC isapartialderivative; disagreement isnotautomaticallyerror. Totalcharges andjunctioncharges have differentdefinitions; do notaddthem orclaimchargeconservationwithoutcheckingtheiractualscope.

Use trueobserved D−SB axis andbothdirections. Forone-sidedextrapolation, comparewindows1–5,2–10,5–20µV fromzero and1/0.5µV grids. Center/scale fits; reportfitcondition,residual,window/stepdependence,nearzeromode andexactzero. Do not inferaphysical discontinuityfromonefinitewindowintercept or usecross-zerocentraldifferencestohideabranchjump.

`limited_model_metadata.py` reads onlyselected literaloptions across theinstalledTTmodelbins andfilehashes before/after. It doesnot exportmodeltext, assumehelpdefaults, or identifytheseasresolvedeffectiveinstanceoptions. `element info what=inst` and`outputParameter info what=output` arealready-supported schoolnetlistentries and may showresolvedinstance/effectivedimensions. No`what=models`wholePDKdumpisrequested.

CompleteADC andnumericalacceptance remainfalse. SmoothDCcharges would notexclude ahistory-dependent orintegrationproblem; nonsmoothsavedvalueswouldstillneedmapping,internalbias,precisionandindependentmodel reviewbefore anybugclaim.

"""Fast structural checks. Passing these is not electrical qualification."""
import json
import re
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
PINS='INP INN Q QB SAMPLE SAMPLEB ACQ CONV EVAL B11 B10 B9 B8 B7 B6 B5 B4 B3 B2 B1 B0 RP RN VCM VDD VSS'.split()


class ADCContracts(unittest.TestCase):
    def test_wrapper_interfaces_remain_identical(self):
        for path in HERE.glob('adc_analog12*.spice'):
            declaration=next(s for s in path.read_text().splitlines() if s.lower().startswith('.subckt'))
            self.assertEqual(declaration.split()[2:],PINS,path.name)

    def test_binary_weights_and_dummy_count(self):
        text=(HERE/'adc_blocks.spice').read_text().split('.subckt adc_cdac12',1)[1]
        weights={int(b):int(n) for b,n in re.findall(r'^XC(\d+) .* COUNT=(\d+)$',text,re.M)}
        self.assertEqual(weights,{b:2**b for b in range(12)})
        self.assertIn('XD TOP DUMMY adc_mim_bank COUNT=1',text)
        self.assertEqual(sum(weights.values())+1,4096)

    def test_statistical_multiplier_not_omitted(self):
        text=(HERE/'adc_blocks.spice').read_text()
        self.assertRegex(text,r'sky130_fd_pr__cap_mim_m3_1 W=3 L=3 m=\{COUNT\} mult=\{COUNT\}')

    def test_bottom_dummy_matches_offset_binary_threshold(self):
        # P bit1=RP and bit0=RN; N complementary. P dummy=RN, N=RP.
        for code in [0,1,1024,2048,3072,4095]:
            p_minus_n=sum((1 if (code>>b)&1 else -1)*.4*2**b for b in range(12))-.4
            self.assertAlmostEqual(p_minus_n/4096,.8*code/4096-.4,places=14)
        text=(HERE/'adc_analog12_bottom_preamp_lvtref.spice').read_text()
        self.assertIn('XDP DP VSS ACQ CONV RP RN INP',text)
        self.assertIn('XDN DN VDD ACQ CONV RP RN INN',text)
        self.assertIn('XPRE TN TP PREP PREN',text)

    def test_mixed_expression_pair_regression(self):
        text=(HERE/'adc_blocks.spice').read_text()
        # Both sides must use expressions, not one expression and one literal:
        # the installed corner-model resolution differed in that mixed case.
        self.assertIn('W={8.4*(1+ADC_PAIR_WIDTH_SKEW)}',text)
        self.assertIn('W={8.4*(1-ADC_PAIR_WIDTH_SKEW)}',text)

    def test_analog_implementations_have_no_ideal_controlled_sources(self):
        for path in HERE.glob('*.spice'):
            for line in path.read_text().splitlines():
                line=line.strip()
                if line and not line.startswith(('*','.','+')):
                    self.assertTrue(line.upper().startswith('X'),f'{path.name}: {line}')

    def test_summary_cannot_promote_blocks_to_adc(self):
        summary=json.loads((HERE/'summary.json').read_text())
        self.assertFalse(summary['full_adc_qualification_pass'])
        self.assertFalse(summary['cadence_used'])
        self.assertFalse(summary['tapeout_or_silicon_measurement'])


if __name__=='__main__':unittest.main(verbosity=2)

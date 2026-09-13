"""Nominal M0 geometry only; public-model equations, never fitted to RC data.

Reference provenance, approximation and numerical budgets: passive_criteria.md.
These checks qualify migration smoke tests, not OTA or frontend performance.
"""
import math

C_MIM = 34.6223e-15  # Frozen CDF geometry value, rounded; AC independently checks it.
C_RES_END = ((.35 + 2*2.08)*.35*1.06e-4*1e-12 +
             2*(.35 + 2*2.08 + .35)*5.04e-11*1e-6)/2


def resistance(v):
    v = abs(v)
    d = min(v-1.7, .3)
    scale = (1-.0071*(27-30))/math.sqrt(.35)
    return (589.99*(1+scale*(-.0202*d+.155*d*d+.0461*d*d*d)) +
            .35*1112.41*(1-.00846*v+.00197*v*v+.000033*v*v*v))


def reference_delay():
    # Ideal step, nonlinear resistor: t63=C*integral_0^1 R(0.1*exp(-s)) ds.
    # Output-end resistor parasitic is in parallel with MIM. Input-end parasitic
    # is driven by the ideal source and does not add to the output load.
    n = 1024
    values = [resistance(.1*math.exp(-k/n)) for k in range(n+1)]
    integral = (values[0]+values[-1]+4*sum(values[1:-1:2])+2*sum(values[2:-1:2]))/(3*n)
    return (C_MIM+C_RES_END)*integral


def paired(a, b):
    if len(a) != len(b) or any(x != y for (x, _), (y, _) in zip(a, b)):
        raise ValueError('Passive waveform axes differ')


def analyze_passive(out, job):
    from analyze import curve, crossing, ratio
    if job['corner'] != 'tt' or job['temp'] != 27:
        raise ValueError('Passive reference is restricted to TT / 27 C / tnom=27')
    ident = job['id']
    m = dict(status='FAIL', criteria={}, acceptance_revision='M0_MODEL_REVIEW_V1',
             scope='Default passive geometries, TT 27 C only; no OTA/PVT qualification')
    c = m['criteria']
    if ident == 'res_dc':
        v, i = curve(out, 'TEST'), curve(out, 'VTEST_p'); paired(v, i)
        if len(v) != 101: raise ValueError('Expected 101 DC samples')
        c['dc_axis_and_voltage_match'] = all(abs(t-k*.001) <= 1e-12 and abs(z.real-t) <= 1e-7 and z.imag == 0
                                             for k, (t, z) in enumerate(v))
        errors = [abs(-a.real-b.real/resistance(b.real)) for (_, a), (_, b) in zip(i, v)]
        budgets = [1e-12 + 1e-4*abs(b.real/resistance(b.real)) for _, b in v]
        c['positive_current'] = all(a.real < 0 for (_, a), (_, b) in zip(i, v) if b.real > 0)
        c['current_matches_public_model'] = all(e <= b for e, b in zip(errors, budgets))
        c['current_is_real'] = all(z.imag == 0 for _, z in i)
        resistances = [b.real/-a.real for (_, a), (_, b) in zip(i, v) if b.real >= .01 and a.real != 0]
        m.update(mean_resistance_ohm=sum(resistances)/len(resistances) if resistances else None,
                 max_current_error_A=max(errors), cdf_resistance_ohm=979.33)
    elif ident == 'mim_ac':
        v, i = curve(out, 'TEST'), curve(out, 'VTEST_p'); paired(v, i)
        if len(v) != 1081: raise ValueError('Expected 1081 AC samples')
        c['ac_grid_and_stimulus_match'] = all(abs(math.log10(f)-k/120) < 1e-9 and abs(z-1) <= 1e-7
                                             for k, (f, z) in enumerate(v))
        adm = ratio([(f, -z) for f, z in i], v)
        caps = [y.imag/(2*math.pi*f) for f, y in adm if 1e3 <= f <= 1e6]
        if not caps or any(abs(y) == 0 for _, y in adm): raise ValueError('Missing capacitor response')
        cap = sum(caps)/len(caps)
        esr = [(1/y).real for f, y in adm if 1e6 <= f <= 1e9]
        c['positive_capacitance'] = cap > 0
        c['within_5pct_of_CDF'] = abs(cap/C_MIM-1) <= .05
        c['capacitance_flat_in_measurement_band'] = (max(caps)-min(caps))/C_MIM <= 1e-4
        # Bound needed by the simplified RC reference; not an ADC ESR spec.
        c['series_resistance_bounded_for_RC_reference'] = min(esr) >= -1e-9 and max(esr) <= 1
        m.update(capacitance_F=cap, cdf_capacitance_F=C_MIM,
                 difference_percent=100*(cap/C_MIM-1), max_series_resistance_ohm=max(esr))
    elif ident == 'rc_step':
        vin, vo = curve(out, 'VIN'), curve(out, 'VOUT'); paired(vin, vo)
        def pulse(t):
            if t <= 1e-9: return 0.
            if t < 1.001e-9: return .1*(t-1e-9)/1e-12
            if t <= 6.001e-9: return .1
            if t < 6.002e-9: return .1*(6.002e-9-t)/1e-12
            return 0.
        c['time_coverage_and_step_size'] = (vin[0][0] == 0 and abs(vin[-1][0]-1e-8) < 1e-18 and
                                          max(b[0]-a[0] for a, b in zip(vin, vin[1:])) <= .50001e-12)
        c['real_waveforms'] = all(z.imag == 0 for rows in (vin, vo) for _, z in rows)
        c['input_pulse_matches'] = all(abs(z.real-pulse(t)) <= 1e-7 for t, z in vin)
        c['output_in_range'] = all(-1e-7 <= z.real <= .1000001 for _, z in vo)
        delays = []
        for start, stop, up, level in [(0, 4e-9, True, .1*(1-math.exp(-1))),
                                      (5e-9, 9e-9, False, .1*math.exp(-1))]:
            t0 = crossing(vin, .05, start, stop, up)
            delays.append(crossing(vo, level, t0, stop, up)-t0)
        ref = reference_delay()
        c['both_delays_within_0p5pct_of_model'] = all(abs(d/ref-1) <= .005 for d in delays)
        # Integral KCL over the complete trace independently checks the shape.
        # Approximation excludes <=1 ohm MIM ESR; 250 uV includes its effect,
        # trapezoidal integration, 1 ps finite edges and simulator tolerances.
        q, errors = 0., [0.]
        for k in range(1, len(vo)):
            dt = vo[k][0]-vo[k-1][0]
            va = vin[k-1][1].real-vo[k-1][1].real
            vb = vin[k][1].real-vo[k][1].real
            q += dt*(va/resistance(va)+vb/resistance(vb))/2
            errors.append(abs(vo[k][1].real-vo[0][1].real-q/(C_MIM+C_RES_END)))
        c['charge_balance_within_250uV'] = max(errors) <= 250e-6
        c['settles_high_and_low'] = all(abs(z.real-pulse(t)) <= 1e-6 for t, z in vo if 2e-9 <= t <= 5e-9 or 7e-9 <= t <= 1e-8)
        m.update(rise_delay_s=delays[0], fall_delay_s=delays[1], model_delay_s=ref,
                 resistor_output_parasitic_F=C_RES_END, max_charge_balance_error_V=max(errors),
                 old_CDF_delay_s=979.33*C_MIM)
    else:
        raise ValueError('Unknown passive job: '+ident)
    m['status'] = 'PASS' if c and all(c.values()) else 'FAIL'
    return m

#!/usr/bin/env python3
"""Synthetic algebra checks only; never a Cadence/frontend qualification."""
from pathlib import Path
import json
import numpy as np


def winding(values):
    # The supplied contour must already be closed and positively oriented.
    return float(np.angle(values[1:] / values[:-1]).sum() / (2 * np.pi))


def main():
    rng = np.random.default_rng(20260923)
    n, m = 11, 4
    b = rng.normal(size=(n, m))
    r = np.diag([0.1, 0.3, 0.7, 1.3])
    selector = np.block([[np.zeros((n, m))], [np.eye(m)]])
    current_pick = selector.T
    max_det_error = max_inverse_error = max_basis_error = 0.0
    # Full physical MNA has bilateral/nonreciprocal node coupling, not an
    # assumed unilateral block diagram. This checks the determinant lemma.
    for omega in np.geomspace(1e-3, 1e3, 71):
        k = rng.normal(size=(n, n)) + 1j * omega * np.eye(n)
        closed = np.block([[k, b], [b.T, np.zeros((m, m))]])
        reference = closed - selector @ r @ current_pick
        yc = current_pick @ np.linalg.solve(closed, selector)
        yr = current_pick @ np.linalg.solve(reference, selector)
        ratio = np.linalg.det(reference) / np.linalg.det(closed)
        f = np.linalg.det(np.eye(m) - r @ yc)
        max_det_error = max(max_det_error, abs(ratio-f)/max(abs(ratio), 1e-30))
        inverse = (np.eye(m)-r@yc) @ (np.eye(m)+r@yr)
        max_inverse_error = max(max_inverse_error, np.linalg.norm(inverse-np.eye(m)))
        s = np.eye(m)
        s[:2, :2] = [[0.5, 1.0], [-0.5, 1.0]]
        t = np.linalg.inv(s)
        ym = s.T @ yc @ s
        rm = t @ r @ t.T
        fm = np.linalg.det(np.eye(m)-rm@ym)
        max_basis_error = max(max_basis_error, abs(f-fm)/max(abs(f), 1e-30))
    assert max_det_error < 1e-9
    assert max_inverse_error < 1e-9
    assert max_basis_error < 1e-9

    # Source direction: with passive G||C across a voltage source,
    # I(source) = -(G+sC)*V. Omitting this minus sign predicts a false RHP pole.
    g, c, resistance = 0.2, 0.4, 0.7
    reference_pole = -(1+resistance*g)/(resistance*c)
    assert reference_pole < 0
    sign_example = {
        "source_admittance": "-(G+s*C)",
        "reference_over_closed": "1+R*(G+s*C)",
        "closed_over_reference": "1/(1+R*(G+s*C))",
        "reference_pole_rad_per_s": reference_pole,
        "closed_has_no_finite_dynamic_mode_because_ideal_voltage_clamps_C": True,
        "high_frequency_ratio_is_not_necessarily_one": True,
    }

    # RHP-positive contour: imaginary axis down, right semicircle up.
    radius = 1e4
    axis = 1j*np.linspace(radius, -radius, 200001)
    arc = radius*np.exp(1j*np.linspace(-np.pi/2, np.pi/2, 20001))
    contour = np.r_[axis, arc[1:]]
    d_stable_from_unstable_ref = (contour+2)/(contour-1)
    d_unstable_from_stable_ref = (contour-2)/(contour+1)
    w1, w2 = winding(d_stable_from_unstable_ref), winding(d_unstable_from_stable_ref)
    assert abs(w1+1) < 1e-9 and abs(w2-1) < 1e-9

    # A shared unobservable unstable state cancels from the ratio exactly.
    # F=1 does NOT establish absolute stability; reference state count is needed.
    hidden = {"shared_characteristic_factor": "s-3", "ratio": 1,
              "winding": 0, "closed_RHP_count": 1, "reference_RHP_count": 1}
    report = {
        "status": "SYNTHETIC_ALGEBRA_CHECKS_PASS",
        "actual_frontend_or_Cadence_run": False,
        "global_stability_signoff": False,
        "random_MNA_frequency_cases": 71,
        "max_relative_determinant_identity_error": max_det_error,
        "max_inverse_identity_norm": max_inverse_error,
        "max_modal_basis_relative_error": max_basis_error,
        "passive_sign_and_high_frequency_example": sign_example,
        "counterclockwise_RHP_winding_examples": {
            "stable_closed_unstable_reference": w1,
            "unstable_closed_stable_reference": w2,
        },
        "hidden_unstable_mode_counterexample": hidden,
    }
    out = Path(__file__).with_name("synthetic_method_checks.json")
    out.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

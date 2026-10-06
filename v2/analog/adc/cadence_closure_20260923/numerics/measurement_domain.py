#!/usr/bin/env python3
"""Derive the normal testbench finish from frozen source, not waveform results.

Any changed sequence requires a new reviewed contract. Integer picoseconds avoid
rounding or selecting a domain from whatever happened to finish successfully.
"""
import hashlib
from pathlib import Path
import re

SEQUENCE_SHA256="6fddc959ba418bbd23584e8b6dce3137f378ca0be34f60315f5fb51869864505"


def schedule(frames):
    if frames not in (2,12):raise ValueError("Only planned 2/12-frame profiles reviewed")
    t=0;steps=[]
    def falling():
        nonlocal t
        t=(t//625000+1)*625000
    def rising():
        nonlocal t
        t=((t-312500)//625000+1)*625000+312500
    def drive(n=1):
        nonlocal t
        for _ in range(n):
            falling();t+=10000;rising();t+=10000
    def record(name):steps.append({"event":name,"time_ps":t})
    for _ in range(3):falling()
    t+=10000;record("initial_reset_release")
    drive(3);record("first_accept_drive_returns")
    drive(16*frames);record("all_requested_frames_complete_drive_returns")
    drive();record("valid_cleared_check")
    drive();record("third_or_thirteenth_abort_frame_accept_drive_returns")
    drive(4);falling();t+=100000;record("abort_reset_assert")
    t+=100000;record("reset_Q0_QB1_check")
    falling();falling();t+=10000;record("abort_reset_release")
    drive(2);record("normal_pass_and_finish")
    return {"frames":frames,"start_ps":0,"finish_ps":t,"finish_s":t*1e-12,"watchdog_ps":(frames*10000+19000)*1000,"events":steps}


def contract(design):
    design=Path(design)
    sequence=(design/"p2_sequence.sv").read_bytes()
    digest=hashlib.sha256(sequence).hexdigest()
    if digest!=SEQUENCE_SHA256:raise ValueError("Unreviewed testbench sequence; derive new domain contract")
    profile=(design/"profile.vh").read_text()
    m=re.fullmatch(r"\s*`define P2_FRAMES (\d+)\s*",profile)
    if not m:raise ValueError("Unreviewed frame profile")
    return {"basis":"Frozen deterministic stimulus clock and task delays; independent of solver output or errors", "sequence_sha256":digest,"profile_sha256":hashlib.sha256(profile.encode()).hexdigest(),**schedule(int(m[1])),"rules":["Both runs must complete normally at exactly this scheduled $finish time and pass independent integration checks.","Include initial reset, all requested frames, independent abort conversion and post-reset checks, and every switching edge in the entire closed interval.","All accepted points inside the interval plus its exact endpoints are compared without time alignment.","Saved waves must bracket both endpoints; no extrapolation or shortened successful prefix.","All stored data, including simulator lookahead after $finish, remain audited and separately reported.","A watchdog or failure-path $finish cannot redefine the measurement end."]}

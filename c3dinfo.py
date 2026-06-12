#!/usr/bin/env python3
"""Print a summary of a C3D file.

Usage:
    python3 c3dinfo.py FILE.c3d [FILE2.c3d ...]
"""
import sys
import numpy as np
import ezc3d


def summarize(path: str) -> None:
    c = ezc3d.c3d(path)

    pts = c["data"]["points"]       # (4, markers, frames)
    ana = c["data"]["analogs"]      # (1, channels, analog_frames)

    pt_rate   = float(c["parameters"]["POINT"]["RATE"]["value"][0])
    n_markers = pts.shape[1]
    n_frames  = pts.shape[2]
    duration  = n_frames / pt_rate if pt_rate else float("nan")
    units     = c["parameters"]["POINT"].get("UNITS", {}).get("value", ["?"])[0]

    an_rate     = float(c["parameters"]["ANALOG"]["RATE"]["value"][0]) if c["parameters"]["ANALOG"]["RATE"]["value"] else 0.0
    n_an_ch     = ana.shape[1]
    n_an_frames = ana.shape[2]

    pt_labels = c["parameters"]["POINT"]["LABELS"]["value"]
    an_labels = c["parameters"]["ANALOG"]["LABELS"]["value"]

    # NaN/invalid marker stats
    valid_mask = np.isfinite(pts[0])          # (markers, frames)
    valid_pct  = valid_mask.mean(axis=1) * 100

    print(f"File       : {path}")
    print(f"Duration   : {duration:.3f} s  ({n_frames} frames @ {pt_rate:.0f} Hz)")
    print(f"Markers    : {n_markers}  [{', '.join(pt_labels)}]")
    print(f"Units      : {units}")
    if n_an_ch:
        print(f"Analog     : {n_an_ch} channels @ {an_rate:.0f} Hz  ({n_an_frames} frames)")
        print(f"  channels : [{', '.join(an_labels)}]")
    else:
        print("Analog     : none")

    # Per-marker validity
    print("Marker fill:")
    col = 0
    for lbl, pct in zip(pt_labels, valid_pct):
        entry = f"  {lbl}: {pct:5.1f}%"
        print(entry, end="")
        col += 1
        if col % 4 == 0:
            print()
    if col % 4:
        print()


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    for i, path in enumerate(sys.argv[1:]):
        if i:
            print()
        summarize(path)


if __name__ == "__main__":
    main()

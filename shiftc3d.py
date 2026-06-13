#!/usr/bin/env python3
"""Truncate frames from two C3D files.

Usage:
    python3 shiftc3d.py PRE.c3d POST.c3d N

N may be a non-integer and is rounded to the nearest whole video frame. Analog
data is always kept as an exact integer multiple of the point frame count (a
C3D format requirement), so analog precision is limited to one video frame
regardless of the analog sample rate.

Writes:
    PRE_pretruncated.c3d   — PRE.c3d with the first N frames removed
    POST_posttruncated.c3d — POST.c3d with the last N frames removed
"""
import sys
from pathlib import Path

import ezc3d
import numpy as np


def truncate_c3d(src_path: str, n: float, from_start: bool) -> str:
    c = ezc3d.c3d(src_path)

    pts = c["data"]["points"]         # (4, markers, frames)
    ana = c["data"]["analogs"]        # (1, channels, analog_frames)
    rot = c["data"].get("rotations")  # (4, 4, segments, frames) or None

    n_frames = pts.shape[2] if pts.shape[2] else (rot.shape[3] if rot is not None else 0)

    if n <= 0:
        raise ValueError(f"n must be a positive number, got {n}")

    n_pt = int(round(n))
    if n_pt < 1:
        raise ValueError(f"n={n} rounds to zero frames; minimum is 0.5")
    if n_pt >= n_frames:
        raise ValueError(f"{src_path} has only {n_frames} frames; cannot remove {n_pt}")

    # Analog must be an exact integer multiple of point frames (C3D format
    # requirement, enforced by ezc3d on write).
    ratio = int(round(ana.shape[2] / n_frames)) if n_frames and ana.shape[2] else 0
    n_an = n_pt * ratio

    pt_rate = float(c["parameters"]["POINT"]["RATE"]["value"][0])
    ms = n_pt / pt_rate * 1000

    if from_start:
        c["data"]["points"] = np.asfortranarray(pts[:, :, n_pt:])
        if rot is not None and rot.shape[3] > 0:
            c["data"]["rotations"] = np.asfortranarray(rot[:, :, :, n_pt:])
        if n_an > 0:
            c["data"]["analogs"] = np.asfortranarray(ana[:, :, n_an:])
        suffix = "_pretruncated"
    else:
        c["data"]["points"] = np.asfortranarray(pts[:, :, :-n_pt])
        if rot is not None and rot.shape[3] > 0:
            c["data"]["rotations"] = np.asfortranarray(rot[:, :, :, :-n_pt])
        if n_an > 0:
            c["data"]["analogs"] = np.asfortranarray(ana[:, :, :-n_an])
        suffix = "_posttruncated"

    del c["data"]["meta_points"]

    p = Path(src_path)
    out = p.with_name(p.stem + suffix + ".c3d")
    c.write(str(out))
    return str(out), n_pt, n_an, ms


def main():
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    pre_src, post_src, n_str = sys.argv[1], sys.argv[2], sys.argv[3]

    try:
        n = float(n_str)
    except ValueError:
        print(f"error: N must be a number, got '{n_str}'", file=sys.stderr)
        sys.exit(1)

    out_pre, n_pt, n_an, ms = truncate_c3d(pre_src, n, from_start=True)
    print(f"wrote {out_pre}  ({n_pt} frames / {n_an} analog samples = {ms:.2f} ms)")

    out_post, n_pt, n_an, ms = truncate_c3d(post_src, n, from_start=False)
    print(f"wrote {out_post}  ({n_pt} frames / {n_an} analog samples = {ms:.2f} ms)")


if __name__ == "__main__":
    main()

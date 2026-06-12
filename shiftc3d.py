#!/usr/bin/env python3
"""Truncate frames from two C3D files.

Usage:
    python3 shiftc3d.py PRE.c3d POST.c3d N

Writes:
    PRE_pretruncated.c3d   — PRE.c3d with the first N frames removed
    POST_posttruncated.c3d — POST.c3d with the last N frames removed
"""
import sys
from pathlib import Path

import ezc3d
import numpy as np


def truncate_c3d(src_path: str, n: int, from_start: bool) -> str:
    c = ezc3d.c3d(src_path)

    pts = c["data"]["points"]      # (4, markers, frames)
    ana = c["data"]["analogs"]     # (1, channels, analog_frames)
    rot = c["data"].get("rotations")  # (4, 4, segments, frames) or None

    n_frames = pts.shape[2] if pts.shape[2] else (rot.shape[3] if rot is not None else 0)
    if n <= 0:
        raise ValueError(f"n must be a positive integer, got {n}")
    if n >= n_frames:
        raise ValueError(
            f"{src_path} has only {n_frames} frames; cannot remove {n}"
        )

    ratio = int(round(ana.shape[2] / n_frames)) if n_frames and ana.shape[2] else 1
    an = n * ratio

    if from_start:
        c["data"]["points"] = np.asfortranarray(pts[:, :, n:])
        c["data"]["analogs"] = np.asfortranarray(ana[:, :, an:])
        if rot is not None:
            c["data"]["rotations"] = np.asfortranarray(rot[:, :, :, n:])
        suffix = "_pretruncated"
    else:
        c["data"]["points"] = np.asfortranarray(pts[:, :, :-n])
        c["data"]["analogs"] = np.asfortranarray(ana[:, :, :-an])
        if rot is not None:
            c["data"]["rotations"] = np.asfortranarray(rot[:, :, :, :-n])
        suffix = "_posttruncated"

    # Let ezc3d rebuild meta_points (residuals etc.) for the new frame count.
    del c["data"]["meta_points"]

    p = Path(src_path)
    out = p.with_name(p.stem + suffix + ".c3d")
    c.write(str(out))
    return str(out)


def main():
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    pre_src, post_src, n_str = sys.argv[1], sys.argv[2], sys.argv[3]

    try:
        n = int(n_str)
    except ValueError:
        print(f"error: N must be an integer, got '{n_str}'", file=sys.stderr)
        sys.exit(1)

    out_pre = truncate_c3d(pre_src, n, from_start=True)
    print(f"wrote {out_pre}")

    out_post = truncate_c3d(post_src, n, from_start=False)
    print(f"wrote {out_post}")


if __name__ == "__main__":
    main()

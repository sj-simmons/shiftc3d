#!/usr/bin/env python3
"""Animate the 3D markers of a C3D file with matplotlib.

Usage:
    python3 view_c3d.py FILE.c3d [--save out.mp4] [--fps N] [--no-labels]
"""
import argparse

import ezc3d
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation


def load_points(path):
    c = ezc3d.c3d(path)
    pts = c["data"]["points"][:3]  # (3, n_markers, n_frames), drop homogeneous row
    labels = c["parameters"]["POINT"]["LABELS"]["value"]
    rate = float(c["parameters"]["POINT"]["RATE"]["value"][0])
    units = c["parameters"]["POINT"].get("UNITS", {}).get("value", ["?"])[0]
    return pts, labels, rate, units


def main():
    ap = argparse.ArgumentParser(description="View a C3D file's markers in 3D.")
    ap.add_argument("file", help="path to a .c3d file")
    ap.add_argument("--save", metavar="OUT", help="save animation instead of showing (e.g. out.mp4)")
    ap.add_argument("--fps", type=float, default=None, help="playback fps (default: file's capture rate)")
    ap.add_argument("--no-labels", action="store_true", help="hide marker name labels")
    args = ap.parse_args()

    pts, labels, rate, units = load_points(args.file)
    n_markers, n_frames = pts.shape[1], pts.shape[2]
    fps = args.fps or rate

    # Ignore NaN/zero-filled invalid samples when computing bounds.
    finite = np.isfinite(pts)
    lo = np.nanmin(np.where(finite, pts, np.nan), axis=(1, 2))
    hi = np.nanmax(np.where(finite, pts, np.nan), axis=(1, 2))
    center = (lo + hi) / 2
    span = float(np.nanmax(hi - lo)) or 1.0

    fig = plt.figure(figsize=(8, 7))
    ax = fig.add_subplot(111, projection="3d")
    scat = ax.scatter([], [], [], s=30, c="tab:blue", depthshade=True)
    txts = [] if args.no_labels else [ax.text(0, 0, 0, lbl, size=7) for lbl in labels]

    for axis, c in zip("xyz", center):
        getattr(ax, f"set_{axis}lim")(c - span / 2, c + span / 2)
    ax.set_xlabel(f"X ({units})")
    ax.set_ylabel(f"Y ({units})")
    ax.set_zlabel(f"Z ({units})")
    try:
        ax.set_box_aspect((1, 1, 1))
    except Exception:
        pass

    def update(f):
        frame = pts[:, :, f]
        scat._offsets3d = (frame[0], frame[1], frame[2])
        if txts:
            for t, m in zip(txts, range(n_markers)):
                t.set_position((frame[0, m], frame[1, m]))
                t.set_3d_properties(frame[2, m], zdir="z")
        ax.set_title(f"{args.file}   frame {f + 1}/{n_frames}")
        return [scat, *txts]

    anim = FuncAnimation(fig, update, frames=n_frames, interval=1000 / fps, blit=False)

    if args.save:
        anim.save(args.save, fps=fps)
        print(f"saved {args.save}")
    else:
        plt.show()


if __name__ == "__main__":
    main()

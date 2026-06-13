#!/usr/bin/env python3
"""Animate the 3D markers of a C3D file with matplotlib.

Usage:
    python3 view_c3d.py FILE.c3d [FILE2.c3d] [--save out.mp4] [--fps N] [--no-labels]

If two files with the same number of frames are given they are shown side-by-side.
"""
import argparse
import sys

import ezc3d
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_points(path):
    c = ezc3d.c3d(path)
    rate = float(c["parameters"]["POINT"]["RATE"]["value"][0])
    units = c["parameters"]["POINT"].get("UNITS", {}).get("value", ["?"])[0]
    pts = c["data"]["points"][:3]       # (3, n_markers, n_frames)
    labels = c["parameters"]["POINT"]["LABELS"]["value"]

    if pts.shape[1] == 0 and "rotations" in c["data"]:
        rot = c["data"]["rotations"]    # (4, 4, n_segs, n_frames)
        pts = rot[0:3, 3, :, :]
        raw = c["parameters"]["ROTATION"]["LABELS"]["value"]
        labels = [l.removesuffix("_4X4") for l in raw]
        rate = float(c["parameters"]["ROTATION"]["RATE"]["value"][0])

    return pts, labels, rate, units


def load_force_plates(path):
    c = ezc3d.c3d(path)
    fp = c["parameters"]["FORCE_PLATFORM"]
    n_plates = int(fp["USED"]["value"][0])
    corners = np.array(fp["CORNERS"]["value"])   # (3, 4, n_plates)
    channels = np.array(fp["CHANNEL"]["value"])  # (6, n_plates) 1-based

    ana = c["data"]["analogs"][0]
    an_rate = float(c["parameters"]["ANALOG"]["RATE"]["value"][0])
    pt_rate = float(c["parameters"]["POINT"]["RATE"]["value"][0])
    ratio = max(1, int(round(an_rate / pt_rate)))

    n_frames = ana.shape[1] // ratio
    ana_ds = ana[:, :n_frames * ratio].reshape(ana.shape[0], n_frames, ratio).mean(axis=2)

    plates = []
    for p in range(n_plates):
        ch = channels[:, p].astype(int) - 1
        fx, fy, fz, mx, my, mz = [ana_ds[i] for i in ch]
        threshold = 10.0
        active = np.abs(fz) > threshold
        cop_x = np.where(active, -my / np.where(active, fz, 1), 0.0)
        cop_y = np.where(active, mx  / np.where(active, fz, 1), 0.0)
        cop = np.stack([cop_x, cop_y, np.zeros(n_frames)])
        plates.append({
            "corners": corners[:, :, p],
            "cop":     cop,
            "force":   np.stack([fx, fy, fz]),
            "active":  active,
        })

    return plates, pt_rate, n_frames


def is_fp_file(path):
    c = ezc3d.c3d(path)
    n_fp = int(c["parameters"].get("FORCE_PLATFORM", {}).get("USED", {}).get("value", [0])[0])
    return n_fp > 0 and c["data"]["points"].shape[1] == 0


# ---------------------------------------------------------------------------
# Axis setup — each returns an update(frame_index) callable
# ---------------------------------------------------------------------------

def setup_points_ax(ax, pts, labels, filename, no_labels):
    n_markers, n_frames = pts.shape[1], pts.shape[2]
    finite = np.isfinite(pts)
    lo = np.nanmin(np.where(finite, pts, np.nan), axis=(1, 2))
    hi = np.nanmax(np.where(finite, pts, np.nan), axis=(1, 2))
    center = (lo + hi) / 2
    span = float(np.nanmax(hi - lo)) or 1.0

    scat = ax.scatter([], [], [], s=30, c="tab:blue", depthshade=True)
    txts = [] if no_labels else [ax.text(0, 0, 0, lbl, size=7) for lbl in labels]

    for axis, c in zip("xyz", center):
        getattr(ax, f"set_{axis}lim")(c - span / 2, c + span / 2)
    try:
        ax.set_box_aspect((1, 1, 1))
    except Exception:
        pass
    ax.set_title(filename)

    def update(f):
        frame = pts[:, :, f]
        scat._offsets3d = (frame[0], frame[1], frame[2])
        if txts:
            for t, m in zip(txts, range(n_markers)):
                t.set_position((frame[0, m], frame[1, m]))
                t.set_3d_properties(frame[2, m], zdir="z")
        ax.set_title(f"{filename}   frame {f + 1}/{n_frames}")
        return [scat, *txts]

    return update, n_frames


def setup_fp_ax(ax, plates, filename):
    n_frames = plates[0]["cop"].shape[1]
    colors = ["tab:blue", "tab:orange"]

    for p, plate in enumerate(plates):
        verts = [tuple(plate["corners"][:, i]) for i in range(4)]
        ax.add_collection3d(Poly3DCollection([verts], alpha=0.25,
                                             facecolor=colors[p], edgecolor="k"))

    max_f = max(np.linalg.norm(pl["force"], axis=0).max() for pl in plates) or 1.0
    scale = 0.3 / max_f

    quivers = [ax.quiver(0, 0, -10, 0, 0, 0, color=colors[p], linewidth=2)
               for p in range(len(plates))]

    all_corners = np.hstack([pl["corners"] for pl in plates])
    lo, hi = all_corners.min(axis=1), all_corners.max(axis=1)
    pad = 0.2
    ax.set_xlim(lo[0] - pad, hi[0] + pad)
    ax.set_ylim(lo[1] - pad, hi[1] + pad)
    ax.set_zlim(-0.05, 0.4)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_zlabel("Z (m)")
    try:
        ax.set_box_aspect((1, 1, 0.5))
    except Exception:
        pass

    def update(f):
        for p, plate in enumerate(plates):
            quivers[p].remove()
            if plate["active"][f]:
                cx, cy, cz = plate["cop"][:, f]
                fx, fy, fz = plate["force"][:, f] * scale
                quivers[p] = ax.quiver(cx, cy, cz, fx, fy, fz,
                                       color=colors[p], linewidth=2)
            else:
                quivers[p] = ax.quiver(0, 0, -10, 0, 0, 0,
                                       color=colors[p], linewidth=2)
        ax.set_title(f"{filename}   frame {f + 1}/{n_frames}")
        return quivers

    return update, n_frames


def prepare_ax(ax, path, no_labels):
    """Load file, configure ax, return (update_fn, n_frames, rate)."""
    if is_fp_file(path):
        plates, rate, n_frames = load_force_plates(path)
        update, _ = setup_fp_ax(ax, plates, path)
    else:
        pts, labels, rate, units = load_points(path)
        ax.set_xlabel(f"X ({units})")
        ax.set_ylabel(f"Y ({units})")
        ax.set_zlabel(f"Z ({units})")
        update, n_frames = setup_points_ax(ax, pts, labels, path, no_labels)
    return update, n_frames, rate


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Animate C3D marker or force-plate data in 3D.")
    ap.add_argument("files", nargs="+", metavar="FILE",
                    help="one or two .c3d files")
    ap.add_argument("--save", metavar="OUT",
                    help="save animation instead of showing (e.g. out.mp4)")
    ap.add_argument("--fps", type=float, default=None,
                    help="playback fps (default: min(capture rate, 30) for display, capture rate for --save)")
    ap.add_argument("--no-labels", action="store_true",
                    help="hide marker name labels")
    args = ap.parse_args()

    if len(args.files) > 2:
        ap.error("at most two files may be specified")

    dual = len(args.files) == 2

    if dual:
        fig = plt.figure(figsize=(16, 7))
        ax1 = fig.add_subplot(121, projection="3d")
        ax2 = fig.add_subplot(122, projection="3d")
        update1, n_frames1, rate1 = prepare_ax(ax1, args.files[0], args.no_labels)
        update2, n_frames2, rate2 = prepare_ax(ax2, args.files[1], args.no_labels)
        if n_frames1 != n_frames2:
            sys.exit(f"error: frame counts differ "
                     f"({args.files[0]}: {n_frames1}, {args.files[1]}: {n_frames2})")
        n_frames = n_frames1
        fps = args.fps or rate1

        def update(f):
            a = update1(f) or []
            b = update2(f) or []
            return a + b
    else:
        fig = plt.figure(figsize=(8, 7))
        ax = fig.add_subplot(111, projection="3d")
        update, n_frames, rate = prepare_ax(ax, args.files[0], args.no_labels)
        fps = args.fps or rate

    if args.save:
        interval = 1000 / fps
    else:
        # matplotlib 3D rendering takes ~50-200 ms per frame, so intervals
        # shorter than ~33 ms (30 fps) have no effect. Cap the default so
        # --fps meaningfully controls speed when the user overrides it.
        display_fps = args.fps or min(fps, 30)
        interval = 1000 / display_fps

    anim = FuncAnimation(fig, update, frames=n_frames,
                         interval=interval, blit=False)

    if args.save:
        anim.save(args.save, fps=fps)
        print(f"saved {args.save}")
    else:
        plt.show()


if __name__ == "__main__":
    main()

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
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def load_points(path):
    c = ezc3d.c3d(path)
    rate = float(c["parameters"]["POINT"]["RATE"]["value"][0])
    units = c["parameters"]["POINT"].get("UNITS", {}).get("value", ["?"])[0]

    pts = c["data"]["points"][:3]  # (3, n_markers, n_frames)
    labels = c["parameters"]["POINT"]["LABELS"]["value"]

    if pts.shape[1] == 0 and "rotations" in c["data"]:
        # No markers — use segment translation vectors from 4x4 rotation matrices.
        rot = c["data"]["rotations"]       # (4, 4, n_segs, n_frames)
        pts = rot[0:3, 3, :, :]            # (3, n_segs, n_frames)
        raw = c["parameters"]["ROTATION"]["LABELS"]["value"]
        labels = [l.removesuffix("_4X4") for l in raw]
        rate = float(c["parameters"]["ROTATION"]["RATE"]["value"][0])

    return pts, labels, rate, units


def load_force_plates(path):
    """Return per-plate COP and force vectors downsampled to point rate."""
    c = ezc3d.c3d(path)
    fp = c["parameters"]["FORCE_PLATFORM"]
    n_plates = int(fp["USED"]["value"][0])
    corners = np.array(fp["CORNERS"]["value"])   # (3, 4, n_plates) in m
    channels = np.array(fp["CHANNEL"]["value"])  # (6, n_plates) 1-based

    ana = c["data"]["analogs"][0]                # (n_ch, n_analog_frames)
    an_rate = float(c["parameters"]["ANALOG"]["RATE"]["value"][0])
    pt_rate = float(c["parameters"]["POINT"]["RATE"]["value"][0])
    ratio = max(1, int(round(an_rate / pt_rate)))

    # Downsample by averaging to point rate.
    n_frames = ana.shape[1] // ratio
    ana_ds = ana[:, :n_frames * ratio].reshape(ana.shape[0], n_frames, ratio).mean(axis=2)

    plates = []
    for p in range(n_plates):
        ch = channels[:, p].astype(int) - 1     # 0-based: [Fx,Fy,Fz,Mx,My,Mz]
        fx, fy, fz, mx, my, mz = [ana_ds[i] for i in ch]

        # Centre of pressure in lab frame (TYPE-2 formula; ORIGIN assumed zero).
        threshold = 10.0  # N — ignore near-zero Fz
        active = np.abs(fz) > threshold
        cop_x = np.where(active, -my / np.where(active, fz, 1), 0.0)
        cop_y = np.where(active, mx  / np.where(active, fz, 1), 0.0)
        cop = np.stack([cop_x, cop_y, np.zeros(n_frames)])  # (3, n_frames)

        plates.append({
            "corners": corners[:, :, p],         # (3, 4)
            "cop":     cop,                       # (3, n_frames)
            "force":   np.stack([fx, fy, fz]),    # (3, n_frames)
            "active":  active,
        })

    return plates, pt_rate, n_frames


def run_fp(args):
    plates, rate, n_frames = load_force_plates(args.file)
    fps = args.fps or rate

    fig = plt.figure(figsize=(8, 7))
    ax = fig.add_subplot(111, projection="3d")

    colors = ["tab:blue", "tab:orange"]

    # Draw static plate outlines.
    for p, plate in enumerate(plates):
        verts = [tuple(plate["corners"][:, i]) for i in range(4)]
        poly = Poly3DCollection([verts], alpha=0.25, facecolor=colors[p], edgecolor="k")
        ax.add_collection3d(poly)

    # Compute a fixed scale: 0.3 m per max-force magnitude across all plates/frames.
    max_f = max(np.linalg.norm(pl["force"], axis=0).max() for pl in plates) or 1.0
    scale = 0.3 / max_f

    # One quiver artist per plate; initialise off-screen.
    quivers = []
    for p in range(len(plates)):
        q = ax.quiver(0, 0, -10, 0, 0, 0, color=colors[p], linewidth=2)
        quivers.append(q)

    # Axis limits from plate corners plus headroom for arrows.
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
        for p, (plate, q) in enumerate(zip(plates, quivers)):
            q.remove()
            if plate["active"][f]:
                cx, cy, cz = plate["cop"][:, f]
                fx, fy, fz = plate["force"][:, f] * scale
                quivers[p] = ax.quiver(cx, cy, cz, fx, fy, fz,
                                       color=colors[p], linewidth=2)
            else:
                quivers[p] = ax.quiver(0, 0, -10, 0, 0, 0,
                                       color=colors[p], linewidth=2)
        ax.set_title(f"{args.file}   frame {f + 1}/{n_frames}")
        return quivers

    anim = FuncAnimation(fig, update, frames=n_frames, interval=1000 / fps, blit=False)

    if args.save:
        anim.save(args.save, fps=fps)
        print(f"saved {args.save}")
    else:
        plt.show()


def run_points(args):
    pts, labels, rate, units = load_points(args.file)
    n_markers, n_frames = pts.shape[1], pts.shape[2]
    fps = args.fps or rate

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


def is_fp_file(path):
    c = ezc3d.c3d(path)
    n_fp = int(c["parameters"].get("FORCE_PLATFORM", {}).get("USED", {}).get("value", [0])[0])
    n_markers = c["data"]["points"].shape[1]
    return n_fp > 0 and n_markers == 0


def main():
    ap = argparse.ArgumentParser(description="View a C3D file's markers or force plates in 3D.")
    ap.add_argument("file", help="path to a .c3d file")
    ap.add_argument("--save", metavar="OUT", help="save animation instead of showing (e.g. out.mp4)")
    ap.add_argument("--fps", type=float, default=None, help="playback fps (default: file's capture rate)")
    ap.add_argument("--no-labels", action="store_true", help="hide marker name labels")
    args = ap.parse_args()

    if is_fp_file(args.file):
        run_fp(args)
    else:
        run_points(args)


if __name__ == "__main__":
    main()

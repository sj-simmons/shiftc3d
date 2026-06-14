#!/usr/bin/env python3
"""Truncate frames from two C3D files to align them temporally.

Usage:
    python3 shiftc3d.py PRE.c3d POST.c3d [N]

If N is given, that many frames are removed (rounded to the nearest whole
frame). If N is omitted, the offset is detected automatically by
cross-correlating a representative signal from each file.

N may be a non-integer. Analog data is always kept as an exact integer multiple
of the point frame count (a C3D format requirement enforced by ezc3d), so
effective precision is limited to one video frame regardless of analog rate.

Writes:
    PRE_pretruncated.c3d   — PRE.c3d with the first N frames removed
    POST_posttruncated.c3d — POST.c3d with the last N frames removed
"""
import sys
from pathlib import Path

import ezc3d
import numpy as np


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------

def truncate_c3d(src_path: str, n: float, from_start: bool):
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


# ---------------------------------------------------------------------------
# Auto-detection via cross-correlation
# ---------------------------------------------------------------------------

def extract_signal(path):
    """Return (signal, pt_rate, description) for cross-correlation.

    FP files  → total absolute vertical force, downsampled to point rate.
    Other files → Z-translation of the first non-world body segment.
    """
    c = ezc3d.c3d(path)
    pt_rate = float(c["parameters"]["POINT"]["RATE"]["value"][0])

    n_fp = int(c["parameters"].get("FORCE_PLATFORM", {}).get("USED", {}).get("value", [0])[0])
    if n_fp > 0 and c["data"]["analogs"].shape[1] > 0:
        ana = c["data"]["analogs"][0]
        an_rate = float(c["parameters"]["ANALOG"]["RATE"]["value"][0])
        ratio = max(1, int(round(an_rate / pt_rate)))
        labels = c["parameters"]["ANALOG"]["LABELS"]["value"]
        fz_idx = [i for i, l in enumerate(labels) if "fz" in l.lower()]
        if fz_idx:
            fz = np.abs(ana[fz_idx]).sum(axis=0)
            n = fz.shape[0] // ratio
            sig = fz[: n * ratio].reshape(n, ratio).mean(axis=1)
            return sig, pt_rate, f"total |Fz| ({len(fz_idx)} plates, downsampled to {pt_rate:.0f} Hz)"

    rot = c["data"].get("rotations")
    if rot is not None and rot.shape[3] > 0:
        from scipy.signal import butter, filtfilt
        labels = c["parameters"].get("ROTATION", {}).get("LABELS", {}).get("value", [])
        nyq = pt_rate / 2.0
        b, a = butter(4, min(10.0 / nyq, 0.99), btype="low")
        foot_idx = [i for i, l in enumerate(labels) if "foot" in l.lower()]
        if foot_idx:
            foot_z = rot[2, 3, foot_idx, :]              # (n_feet, n_frames)
            ranges = foot_z.max(axis=1) - foot_z.min(axis=1)
            active = foot_idx[int(np.argmax(ranges))]    # foot with most vertical travel
            sig = filtfilt(b, a, rot[2, 3, active, :])
            name = labels[active].removesuffix("_4X4")
            return sig, pt_rate, f"Z-position of {name} (most variable foot)"
        # Fallback: pelvis Z if no foot segments are labelled
        pelvis_idx = next(
            (i for i, l in enumerate(labels)
             if "pelvis" in l.lower() and "shift" not in l.lower()), 1)
        sig = filtfilt(b, a, rot[2, 3, pelvis_idx, :])
        name = labels[pelvis_idx].removesuffix("_4X4") if labels else "pelvis"
        return sig, pt_rate, f"Z-position of {name}"

    pts = c["data"]["points"]
    if pts.shape[1] > 0:
        label = c["parameters"]["POINT"]["LABELS"]["value"][0]
        return pts[2, 0, :], pt_rate, f"Z of marker {label}"

    raise ValueError(f"No suitable signal found in {path} for cross-correlation")


def auto_detect_n(pre_path, post_path):
    """Cross-correlate signals from PRE and POST to find the frame offset.

    Returns (n_frames, pt_rate, confidence_pct) where n_frames is the number
    of frames to pass to truncate_c3d (always positive).  A negative raw lag
    means PRE and POST may be swapped.
    """
    try:
        from scipy.signal import correlate, correlation_lags
    except ImportError:
        sys.exit("error: scipy is required for auto-detection — pip install scipy")

    sig_pre, rate_pre, desc_pre = extract_signal(pre_path)
    sig_post, rate_post, desc_post = extract_signal(post_path)

    if rate_pre != rate_post:
        sys.exit(f"error: point rates differ ({rate_pre} vs {rate_post} Hz)")

    print(f"auto-detecting offset:")
    print(f"  PRE  signal: {desc_pre} ({len(sig_pre)} frames)")
    print(f"  POST signal: {desc_post} ({len(sig_post)} frames)")

    s1 = sig_pre - sig_pre.mean()
    s2 = sig_post - sig_post.mean()

    corr = correlate(s1, s2, mode="full")
    lags = correlation_lags(len(s1), len(s2), mode="full")
    peak_idx = int(np.argmax(np.abs(corr)))
    lag = int(lags[peak_idx])

    norm = np.sqrt(np.sum(s1 ** 2) * np.sum(s2 ** 2))
    confidence = abs(corr[peak_idx]) / norm * 100 if norm > 0 else 0.0

    return lag, rate_pre, confidence


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) not in (3, 4):
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    pre_src, post_src = sys.argv[1], sys.argv[2]

    if len(sys.argv) == 4:
        try:
            n = float(sys.argv[3])
        except ValueError:
            print(f"error: N must be a number, got '{sys.argv[3]}'", file=sys.stderr)
            sys.exit(1)
    else:
        lag, rate, confidence = auto_detect_n(pre_src, post_src)
        if lag == 0:
            print(f"detected:  0 frames (confidence {confidence:.1f}%) — sequences are already aligned")
            return
        n = float(abs(lag))
        direction = "PRE start / POST end" if lag >= 0 else "POST start / PRE end (files may be swapped)"
        print(f"detected:  {n:.0f} frames = {n / rate * 1000:.2f} ms  "
              f"(confidence {confidence:.1f}%, direction: {direction})")
        if lag < 0:
            print("warning: negative lag — consider swapping PRE and POST arguments",
                  file=sys.stderr)

    out_pre, n_pt, n_an, ms = truncate_c3d(pre_src, n, from_start=True)
    print(f"wrote {out_pre}  ({n_pt} frames / {n_an} analog samples = {ms:.2f} ms)")

    out_post, n_pt, n_an, ms = truncate_c3d(post_src, n, from_start=False)
    print(f"wrote {out_post}  ({n_pt} frames / {n_an} analog samples = {ms:.2f} ms)")


if __name__ == "__main__":
    main()

# shiftc3d

Python tools for inspecting, viewing, and truncating [C3D](https://www.c3d.org/) motion-capture files.

## Requirements

- Python 3.8+
- [ezc3d](https://github.com/pyomeca/ezc3d)
- matplotlib
- numpy
- scipy (required only for `shiftc3d.py` auto-detection)

```
pip install ezc3d matplotlib numpy scipy
```

## Tools

### `c3dinfo.py` — print file summary

```
python3 c3dinfo.py FILE.c3d [FILE2.c3d ...]
```

Prints for each file:

- Duration (seconds and frame count at capture rate)
- Marker count and names
- Units
- Analog channel count, rate, and channel names
- Per-marker fill percentage (fraction of frames with valid, non-NaN data)

### `view_c3d.py` — animate markers or force plates in 3D

```
python3 view_c3d.py FILE.c3d [FILE2.c3d] [--fps N] [--save out.mp4] [--no-labels]
```

Opens an interactive matplotlib 3D window. Pass two files with the same number
of frames to show them side-by-side in a single synchronized animation.

The file type is detected automatically:

- **Marker data** — animates marker positions as a 3D scatter with labels.
- **Segment rotation data** — animates segment origin positions extracted from
  the 4×4 transformation matrices.
- **Force plate data** (files where markers are absent and force platforms are
  present) — draws plate outlines and animates the ground reaction force vector
  at the centre of pressure for each plate.

| Option | Description |
|---|---|
| `--fps N` | Playback speed (default: file's capture rate) |
| `--save FILE` | Render to video instead of showing (requires ffmpeg) |
| `--no-labels` | Hide marker/segment name labels |

### `shiftc3d.py` — truncate frames from two files to align them

```
python3 shiftc3d.py PRE.c3d POST.c3d [N]
```

Writes two new files:

- `PRE_pretruncated.c3d` — `PRE.c3d` with the first N frames removed
- `POST_posttruncated.c3d` — `POST.c3d` with the last N frames removed

Both point data and analog data are truncated proportionally to their respective
sample rates. N may be a non-integer; it is rounded to the nearest whole video
frame (a C3D format constraint).

**Auto-detection (omit N):** if N is not supplied, the offset is estimated
automatically by cross-correlating a representative signal extracted from each
file. The signal used depends on the file type:

| File type | Signal used |
|---|---|
| Force plate (FP) | Total absolute vertical force \|Fz\| across all plates, downsampled to point rate |
| Segment rotation | Z-position of the most vertically active foot segment |

The output reports the detected frame count, equivalent time, and a confidence
score (0–100%). Scores above ~80% are generally trustworthy; below that,
inspect the result and consider supplying N manually.

Auto-detection requires `scipy` (`pip install scipy`).

**Notes on precision:** The C3D format requires the analog sample count to be
an exact integer multiple of the point frame count, so effective alignment
precision is limited to one video frame (e.g. 8.33 ms at 120 Hz) regardless
of the analog sample rate.

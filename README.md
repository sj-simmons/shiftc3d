# shiftc3d

Python tools for inspecting, viewing, and truncating [C3D](https://www.c3d.org/) motion-capture files.

## Requirements

- Python 3.8+
- [ezc3d](https://github.com/pyomeca/ezc3d)
- matplotlib
- numpy

```
pip install ezc3d matplotlib numpy
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

### `shiftc3d.py` — truncate frames from two files

```
python3 shiftc3d.py PRE.c3d POST.c3d N
```

Writes two new files:

- `PRE_pretruncated.c3d` — `PRE.c3d` with the first N frames removed
- `POST_posttruncated.c3d` — `POST.c3d` with the last N frames removed

Both point data and analog data are truncated proportionally to their respective
sample rates.

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

### `view_c3d.py` — animate markers in 3D

```
python3 view_c3d.py FILE.c3d [--fps N] [--save out.mp4] [--no-labels]
```

Opens an interactive matplotlib 3D window that animates the marker trajectories.
Drag to rotate, scroll to zoom.

| Option | Description |
|---|---|
| `--fps N` | Playback speed (default: file's capture rate) |
| `--save FILE` | Render to video instead of showing (requires ffmpeg) |
| `--no-labels` | Hide marker name labels |

### `shiftc3d.py` — truncate frames from two files

```
python3 shiftc3d.py PRE.c3d POST.c3d N
```

Writes two new files:

- `PRE_pretruncated.c3d` — `PRE.c3d` with the first N frames removed
- `POST_posttruncated.c3d` — `POST.c3d` with the last N frames removed

Both point data and analog data are truncated proportionally to their respective
sample rates.

"""Plot every monthly precipitation GeoTIFF as a map with one shared color scale.

Two passes: first finds the global min/max over all valid pixels, then each
month is plotted with the same vmin/vmax so maps are directly comparable.
"""
import argparse
import glob
import os

INDIR = r"C:\Users\pvssy\Documents\Sylesh\dev\cauvery_catchment\data\processed\monthly_precip_clipped"
OUTDIR = r"C:\Users\pvssy\Documents\Sylesh\dev\cauvery_catchment\data\plots\monthly_maps"


def _fix_proj_env():
    """Point PROJ at rasterio's bundled database, not PostgreSQL's stale one."""
    try:
        import rasterio
        import os as _os

        bundled = _os.path.join(_os.path.dirname(rasterio.__file__), "proj_data")
        if _os.path.isdir(bundled):
            _os.environ["PROJ_LIB"] = bundled
            _os.environ["PROJ_DATA"] = bundled
    except Exception:
        pass


def list_inputs(indir=INDIR):
    """List monthly .tif files sorted by month.

    Args:
        indir: Directory with monthly precipitation .tif files.

    Returns:
        Sorted list of .tif paths.
    """
    srcs = sorted(glob.glob(os.path.join(indir, "*.tif")))
    if not srcs:
        raise FileNotFoundError(f"No .tif files in {indir}")
    return srcs


def global_scale(srcs):
    """Find global min/max over valid pixels of all files.

    Args:
        srcs: List of .tif paths.

    Returns:
        Tuple (vmin, vmax) shared across all maps.
    """
    _fix_proj_env()
    import numpy as np
    import rasterio

    vmin, vmax = float("inf"), float("-inf")
    for p in srcs:
        with rasterio.open(p) as src:
            a = src.read(1)
            nd = src.nodata
            valid = a[a != nd] if nd is not None else a.ravel()
            if valid.size:
                vmin = min(vmin, float(valid.min()))
                vmax = max(vmax, float(valid.max()))
    return vmin, vmax


def plot_one(src_path, dst_path, vmin, vmax, cmap="Blues"):
    """Plot a single monthly GeoTIFF as a map with the shared scale.

    Args:
        src_path: Input .tif path.
        dst_path: Output .png path.
        vmin: Shared color-scale minimum.
        vmax: Shared color-scale maximum.
        cmap: Matplotlib colormap name.

    Returns:
        Output path.
    """
    _fix_proj_env()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import rasterio

    with rasterio.open(src_path) as src:
        a = src.read(1).astype(float)
        if src.nodata is not None:
            a[a == src.nodata] = np.nan
        west, south, east, north = src.bounds
    month = os.path.splitext(os.path.basename(src_path))[0].rsplit("_", 1)[-1]

    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(a, extent=(west, east, south, north), origin="upper",
                   vmin=vmin, vmax=vmax, cmap=cmap)
    ax.set_title(f"Monthly precipitation {month} (mm)")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("mm")
    fig.tight_layout()
    fig.savefig(dst_path, dpi=150)
    plt.close(fig)
    return dst_path


def plot_all(indir=INDIR, outdir=OUTDIR, cmap="Blues"):
    """Plot all monthly .tif files with one constant color scale.

    Args:
        indir: Directory with monthly precipitation .tif files.
        outdir: Directory for output .png maps (created if needed).
        cmap: Matplotlib colormap name.

    Returns:
        List of written .png paths.
    """
    os.makedirs(outdir, exist_ok=True)
    srcs = list_inputs(indir)
    vmin, vmax = global_scale(srcs)
    print(f"shared scale: vmin={vmin:.2f} vmax={vmax:.2f} mm over {len(srcs)} files")
    written = []
    for i, src_path in enumerate(srcs, 1):
        month = os.path.splitext(os.path.basename(src_path))[0].rsplit("_", 1)[-1]
        dst_path = os.path.join(outdir, f"era5_tp_{month}.png")
        plot_one(src_path, dst_path, vmin, vmax, cmap)
        written.append(dst_path)
        if i % 12 == 0 or i == len(srcs):
            print(f"plotted {i}/{len(srcs)}")
    print(f"done: {len(written)} maps in {outdir}")
    return written


def main(argv=None):
    """CLI entry point for monthly map plotting.

    Args:
        argv: Optional arg list for testing; defaults to sys.argv.
    """
    ap = argparse.ArgumentParser(description="Plot monthly precip TIFFs as maps, constant scale.")
    ap.add_argument("--indir", default=INDIR)
    ap.add_argument("--outdir", default=OUTDIR)
    ap.add_argument("--cmap", default="Blues")
    args = ap.parse_args(argv)
    return plot_all(args.indir, args.outdir, args.cmap)


if __name__ == "__main__":
    main()

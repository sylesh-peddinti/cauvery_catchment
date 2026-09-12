"""Extract catchment-mean monthly precipitation and plot year comparison.

Reads every clipped monthly GeoTIFF, averages valid pixels per month, saves
the time series to CSV, and plots one line per year (x = Jan-Dec) so years
can be compared directly.
"""
import argparse
import glob
import os

INDIR = r"C:\Users\pvssy\Documents\Sylesh\dev\cauvery_catchment\data\processed\monthly_precip_clipped"
OUTDIR = r"C:\Users\pvssy\Documents\Sylesh\dev\cauvery_catchment\data\plots"


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


def monthly_means(indir=INDIR):
    """Compute catchment spatial mean for each monthly GeoTIFF.

    Args:
        indir: Directory with clipped monthly .tif files.

    Returns:
        List of (year, month, mean_mm, valid_pixels) sorted by time.
    """
    _fix_proj_env()
    import rasterio

    rows = []
    for p in sorted(glob.glob(os.path.join(indir, "*.tif"))):
        ym = os.path.splitext(os.path.basename(p))[0].rsplit("_", 1)[-1]
        year, month = map(int, ym.split("-"))
        with rasterio.open(p) as src:
            a = src.read(1).astype(float)
            if src.nodata is not None:
                a = a[a != src.nodata]
            rows.append((year, month, float(a.mean()), int(a.size)))
    return rows


def save_csv(rows, path):
    """Save monthly mean series to CSV.

    Args:
        rows: Output of monthly_means().
        path: Destination .csv path.
    """
    import csv

    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "month", "mean_mm", "valid_pixels"])
        w.writerows([(y, m, f"{v:.3f}", n) for y, m, v, n in rows])
    return path


def plot_comparison(rows, path):
    """Plot one line per year of monthly catchment means (x = Jan-Dec).

    Args:
        rows: Output of monthly_means().
        path: Destination .png path.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    years = sorted({r[0] for r in rows})
    fig, ax = plt.subplots(figsize=(9, 5))
    for y in years:
        pts = [(m, v) for yy, m, v, _ in rows if yy == y]
        pts.sort()
        ax.plot([m for m, _ in pts], [v for _, v in pts], marker="o", label=str(y))
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    ax.set_xlabel("Month")
    ax.set_ylabel("Catchment mean precipitation (mm)")
    ax.set_title("Monthly catchment precipitation by year")
    ax.legend(title="Year")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def main(argv=None):
    """CLI entry point: extract means, save CSV, plot year comparison.

    Args:
        argv: Optional arg list for testing; defaults to sys.argv.
    """
    ap = argparse.ArgumentParser(description="Year-on-year monthly catchment precip comparison.")
    ap.add_argument("--indir", default=INDIR)
    ap.add_argument("--outdir", default=OUTDIR)
    args = ap.parse_args(argv)
    os.makedirs(args.outdir, exist_ok=True)
    rows = monthly_means(args.indir)
    csv_path = save_csv(rows, os.path.join(args.outdir, "catchment_monthly_means.csv"))
    png_path = plot_comparison(rows, os.path.join(args.outdir, "year_comparison.png"))
    print(f"months: {len(rows)}, years: {sorted({r[0] for r in rows})}")
    print(f"csv: {csv_path}")
    print(f"plot: {png_path}")
    return rows


if __name__ == "__main__":
    main()

"""Plot per-year cumulative catchment precipitation for year comparison.

Each year's line restarts at zero in January and accumulates that year's
monthly means through December, so wet/dry years separate visually.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

INDIR = r"C:\Users\pvssy\Documents\Sylesh\dev\cauvery_catchment\data\processed\monthly_precip_clipped"
OUTDIR = r"C:\Users\pvssy\Documents\Sylesh\dev\cauvery_catchment\data\plots"
CSV_IN = os.path.join(OUTDIR, "catchment_monthly_means.csv")


def load_monthly(csv_path=CSV_IN, indir=INDIR):
    """Load (year, month, mean_mm) rows from CSV, recomputing if missing.

    Args:
        csv_path: Path to catchment_monthly_means.csv.
        indir: Clipped .tif dir used to recompute when CSV is absent.

    Returns:
        List of (year, month, mean_mm) sorted by time.
    """
    if os.path.isfile(csv_path):
        with open(csv_path) as f:
            return [(int(r["year"]), int(r["month"]), float(r["mean_mm"]))
                    for r in csv.DictReader(f)]
    from plot_yearly_comparison import monthly_means

    return [(y, m, v) for y, m, v, _ in monthly_means(indir)]


def yearly_cumulative(rows):
    """Accumulate monthly means within each calendar year.

    Args:
        rows: List of (year, month, mean_mm) sorted by time.

    Returns:
        Dict year -> list of (month, cum_mm) in month order.
    """
    per_year = {}
    for y, m, v in rows:
        if y not in per_year:
            per_year[y] = []
            total = 0.0
        else:
            total = per_year[y][-1][1]
        per_year[y].append((m, total + v))
    return per_year


def save_csv(per_year, path):
    """Save per-year cumulative series to CSV.

    Args:
        per_year: Output of yearly_cumulative().
        path: Destination .csv path.
    """
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "month", "cumulative_mm"])
        for y in sorted(per_year):
            for m, v in per_year[y]:
                w.writerow([y, m, f"{v:.3f}"])
    return path


def plot_yearly_cumulative(per_year, path):
    """Plot one cumulative line per year (x = Jan-Dec).

    Args:
        per_year: Output of yearly_cumulative().
        path: Destination .png path.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 5))
    for y in sorted(per_year):
        pts = per_year[y]
        ax.plot([m for m, _ in pts], [v for _, v in pts], marker="o", label=str(y))
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    ax.set_xlabel("Month")
    ax.set_ylabel("Cumulative precipitation within year (mm)")
    ax.set_title("Yearly cumulative catchment precipitation")
    ax.legend(title="Year")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def main(argv=None):
    """CLI entry point: per-year cumulative series, save CSV, plot lines.

    Args:
        argv: Optional arg list for testing; defaults to sys.argv.
    """
    ap = argparse.ArgumentParser(description="Per-year cumulative catchment precip comparison.")
    ap.add_argument("--indir", default=INDIR)
    ap.add_argument("--outdir", default=OUTDIR)
    args = ap.parse_args(argv)
    os.makedirs(args.outdir, exist_ok=True)
    rows = load_monthly(os.path.join(args.outdir, "catchment_monthly_means.csv"), args.indir)
    per_year = yearly_cumulative(rows)
    csv_path = save_csv(per_year, os.path.join(args.outdir, "catchment_yearly_cumulative.csv"))
    png_path = plot_yearly_cumulative(per_year, os.path.join(args.outdir, "yearly_cumulative.png"))
    for y in sorted(per_year):
        print(f"{y}: {len(per_year[y])} months, year total {per_year[y][-1][1]:.1f} mm")
    print(f"csv: {csv_path}")
    print(f"plot: {png_path}")
    return per_year


if __name__ == "__main__":
    main()

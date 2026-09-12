"""Plot cumulative catchment precipitation over 2021-2026 as a line chart.

Reads the monthly-mean CSV (or recomputes it), builds the running total,
saves it to CSV, and plots cumulative mm against time.
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


def cumulative(rows):
    """Build running totals from monthly means.

    Args:
        rows: List of (year, month, mean_mm) sorted by time.

    Returns:
        List of (label, cum_mm) with label 'YYYY-MM'.
    """
    out, total = [], 0.0
    for y, m, v in rows:
        total += v
        out.append((f"{y:04d}-{m:02d}", total))
    return out


def save_csv(cum_rows, path):
    """Save cumulative series to CSV.

    Args:
        cum_rows: Output of cumulative().
        path: Destination .csv path.
    """
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["month", "cumulative_mm"])
        w.writerows([(m, f"{v:.3f}") for m, v in cum_rows])
    return path


def plot_cumulative(cum_rows, path):
    """Plot cumulative precipitation line against time.

    Args:
        cum_rows: Output of cumulative().
        path: Destination .png path.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot([m for m, _ in cum_rows], [v for _, v in cum_rows], marker="o", markersize=3)
    ax.set_xlabel("Month")
    ax.set_ylabel("Cumulative precipitation (mm)")
    ax.set_title("Cumulative catchment precipitation 2021-2026")
    tick = max(1, len(cum_rows) // 12)
    ax.set_xticks(range(0, len(cum_rows), tick))
    ax.set_xticklabels([cum_rows[i][0] for i in range(0, len(cum_rows), tick)], rotation=45)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def main(argv=None):
    """CLI entry point: build cumulative series, save CSV, plot line.

    Args:
        argv: Optional arg list for testing; defaults to sys.argv.
    """
    ap = argparse.ArgumentParser(description="Cumulative catchment precip line plot.")
    ap.add_argument("--indir", default=INDIR)
    ap.add_argument("--outdir", default=OUTDIR)
    args = ap.parse_args(argv)
    os.makedirs(args.outdir, exist_ok=True)
    rows = load_monthly(os.path.join(args.outdir, "catchment_monthly_means.csv"), args.indir)
    cum_rows = cumulative(rows)
    csv_path = save_csv(cum_rows, os.path.join(args.outdir, "catchment_cumulative.csv"))
    png_path = plot_cumulative(cum_rows, os.path.join(args.outdir, "cumulative.png"))
    print(f"months: {len(cum_rows)}, total: {cum_rows[-1][1]:.1f} mm")
    print(f"csv: {csv_path}")
    print(f"plot: {png_path}")
    return cum_rows


if __name__ == "__main__":
    main()

# Cauvery Catchment — ERA5 Precipitation Processing

Process ERA5 total precipitation (GRIB1, param 128.228) for the Cauvery catchment: GRIB → monthly GeoTIFFs → clipped/cropped catchment rasters → CSVs and plots.

No ecCodes / cfgrib required for the core pipeline — GRIB1 is parsed and simple-unpacked manually with `numpy`.

## Layout

```
src/processing_ecmwf_dwnld/
  reader.py                # inspect GRIB headers, extract one month, optional xarray decode
  save_cum_sum.py          # stream GRIB → monthly cumulative-sum GeoTIFFs (mm)
  clip_to_extent.py        # mask+crop monthly TIFFs to catchment KML polygon
  clip_to_bbox.py          # crop monthly TIFFs to catchment bounding-box rectangle
  plot_yearly_comparison.py# catchment means per month → CSV + year-on-year line plot
  plot_cumulative.py       # running cumulative 2021–2026 → CSV + line plot
  plot_yearly_cumulative.py# per-year cumulative (Jan reset) → CSV + line plot
  plot_monthly.py          # per-month maps with one shared colour scale
```

## Requirements

* Python >= 3.14 (see `.python-version`)
* `xarray` (declared in `pyproject.toml`)
* Also imported at runtime (not yet declared): `numpy`, `rasterio`, `shapely`, `matplotlib`, `tifffile`

```powershell
uv sync
# or
pip install xarray numpy rasterio shapely matplotlib tifffile
```

## Data (local-only, gitignored)

Default Windows paths (override with CLI flags):

| Role | Default |
|---|---|
| Input GRIB | `C:\Users\pvssy\Documents\Sylesh\dev\cauvery_catchment\data\ecmwf_era5_2021_2026.grib` |
| Catchment KML | `...\data\catchment.kml` |
| Monthly TIFFs | `...\data\monthly_precip_tiff` / `processed\monthly_precip_tiff` |
| Clipped | `...\data\processed\monthly_precip_clipped` |
| BBox | `...\data\processed\monthly_precip_bbox` |
| Plots/CSVs | `...\data\plots` |

Source GRIB: GRIB1, hourly accumulation, 201×201 grid, 60E–110E / 50N–0N, 0.25° resolution, ~2020-12-31–2026-09-05.

`*.grib`, `*.tif`, `*.png`, `data/`, `plots/` are gitignored — outputs stay local.

## Usage

Run from repo root, e.g.:

```powershell
# 1. Inspect GRIB (messages, size, grid, time span)
python src/processing_ecmwf_dwnld/reader.py --file <input.grib>

# Optional: extract one month to a smaller GRIB
python src/processing_ecmwf_dwnld/reader.py --file <input.grib> --extract 2021-01 --out jan2021.grib

# Optional: try full xarray/cfgrib decode
python src/processing_ecmwf_dwnld/reader.py --file <input.grib> --decode

# 2. Accumulate hourly → monthly GeoTIFFs (mm)
python src/processing_ecmwf_dwnld/save_cum_sum.py --input <input.grib> --outdir <monthly_tiff_dir> --start 2021-01 --end 2026-10

# 3a. Mask+crop to catchment polygon (outside = nodata -9999)
python src/processing_ecmwf_dwnld/clip_to_extent.py --kml catchment.kml --indir <monthly_tiff_dir> --outdir <clipped_dir>

# 3b. Or crop to bounding-box rectangle (keeps all pixels)
python src/processing_ecmwf_dwnld/clip_to_bbox.py --kml catchment.kml --indir <monthly_tiff_dir> --outdir <bbox_dir>

# 4. Means + plots (all read the clipped dir by default)
python src/processing_ecmwf_dwnld/plot_yearly_comparison.py --indir <clipped_dir> --outdir <plots_dir>
python src/processing_ecmwf_dwnld/plot_cumulative.py --indir <clipped_dir> --outdir <plots_dir>
python src/processing_ecmwf_dwnld/plot_yearly_cumulative.py --indir <clipped_dir> --outdir <plots_dir>
python src/processing_ecmwf_dwnld/plot_monthly.py --indir <clipped_dir> --outdir <plots_dir/monthly_maps>
```

Outputs:

* `catchment_monthly_means.csv` — `year,month,mean_mm,valid_pixels`
* `catchment_cumulative.csv` — `month,cumulative_mm` (running total)
* `catchment_yearly_cumulative.csv` — `year,month,cumulative_mm` (Jan reset)
* `year_comparison.png`, `cumulative.png`, `yearly_cumulative.png`, `monthly_maps/era5_tp_YYYY-MM.png`

## Notes

* `clip_to_extent.py` nulls edge pixels outside the polygon; `clip_to_bbox.py` preserves them — pick based on whether you need exact catchment means or spatial context.
* `plot_monthly.py` uses a two-pass global min/max so all monthly maps share one colour scale and are directly comparable.
* `rasterio` needs its bundled PROJ DB — scripts set `PROJ_LIB/PROJ_DATA` automatically via `_fix_proj_env()`; `save_cum_sum.py` falls back to `tifffile` with manual GeoTIFF tags if rasterio fails.

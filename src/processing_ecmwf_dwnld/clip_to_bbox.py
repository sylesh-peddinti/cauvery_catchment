"""Crop monthly precipitation GeoTIFFs to the catchment bounding box.

Unlike clip_to_extent.py (which masks to the polygon and nulls edge pixels),
this keeps every pixel intact: it takes the extreme left/right/top/bottom of
the KML shape and cuts a rectangle snapped outward to whole pixels.
"""
import argparse
import glob
import os
import xml.etree.ElementTree as ET

KML = r"C:\Users\pvssy\Documents\Sylesh\dev\cauvery_catchment\data\catchment.kml"
INDIR = r"C:\Users\pvssy\Documents\Sylesh\dev\cauvery_catchment\data\processed\monthly_precip_tiff"
OUTDIR = r"C:\Users\pvssy\Documents\Sylesh\dev\cauvery_catchment\data\processed\monthly_precip_bbox"


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


def read_kml_bounds(kml_path=KML):
    """Get the extreme (minx, miny, maxx, maxy) of all KML Placemark polygons.

    Args:
        kml_path: Path to the .kml file.

    Returns:
        Tuple (minx, miny, maxx, maxy) in lon/lat degrees (WGS84).
    """
    tree = ET.parse(kml_path)
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    minx, miny, maxx, maxy = float("inf"), float("inf"), float("-inf"), float("-inf")
    found = 0
    for pm in tree.getroot().findall(".//k:Placemark", ns):
        for coords in pm.findall(".//k:coordinates", ns):
            for p in coords.text.strip().split():
                lon, lat = float(p.split(",")[0]), float(p.split(",")[1])
                minx, miny = min(minx, lon), min(miny, lat)
                maxx, maxy = max(maxx, lon), max(maxy, lat)
                found += 1
    if not found:
        raise ValueError(f"No coordinates found in {kml_path}")
    return minx, miny, maxx, maxy


def crop_one(src_path, bounds, dst_path):
    """Crop a single GeoTIFF to bounds, snapped outward to whole pixels.

    Args:
        src_path: Input .tif path.
        bounds: Tuple (minx, miny, maxx, maxy) in the raster's CRS.
        dst_path: Output .tif path.

    Returns:
        Output path.
    """
    _fix_proj_env()
    import math
    import rasterio
    from rasterio.windows import Window

    with rasterio.open(src_path) as src:
        west, south, east, north = src.bounds
        resx, resy = src.res
        col0 = math.floor((bounds[0] - west) / resx)
        col1 = math.ceil((bounds[2] - west) / resx)
        row0 = math.floor((north - bounds[3]) / resy)
        row1 = math.ceil((north - bounds[1]) / resy)
        window = Window(col0, row0, col1 - col0, row1 - row0)
        window = window.crop(src.height, src.width)
        out = src.read(window=window)
        transform = src.window_transform(window)
        profile = src.profile.copy()
        profile.update(height=window.height, width=window.width,
                       transform=transform, compress="LZW")
        tags = src.tags()
    with rasterio.open(dst_path, "w", **profile) as dst:
        dst.write(out)
        if tags:
            dst.update_tags(**tags)
    return dst_path


def crop_all(kml_path=KML, indir=INDIR, outdir=OUTDIR):
    """Crop every monthly .tif in indir to the KML bounding box.

    Args:
        kml_path: Path to the catchment .kml file.
        indir: Directory with monthly precipitation .tif files.
        outdir: Directory for cropped outputs (created if needed).

    Returns:
        List of written .tif paths.
    """
    os.makedirs(outdir, exist_ok=True)
    bounds = read_kml_bounds(kml_path)
    print(f"bbox: left={bounds[0]:.4f} bottom={bounds[1]:.4f} "
          f"right={bounds[2]:.4f} top={bounds[3]:.4f}")
    srcs = sorted(glob.glob(os.path.join(indir, "*.tif")))
    if not srcs:
        raise FileNotFoundError(f"No .tif files in {indir}")
    written = []
    for i, src_path in enumerate(srcs, 1):
        dst_path = os.path.join(outdir, os.path.basename(src_path))
        crop_one(src_path, bounds, dst_path)
        written.append(dst_path)
        if i % 12 == 0 or i == len(srcs):
            print(f"cropped {i}/{len(srcs)} -> {dst_path}")
    print(f"done: {len(written)} files in {outdir}")
    return written


def main(argv=None):
    """CLI entry point for bounding-box cropping.

    Args:
        argv: Optional arg list for testing; defaults to sys.argv.
    """
    ap = argparse.ArgumentParser(description="Crop monthly precip TIFFs to catchment bbox.")
    ap.add_argument("--kml", default=KML)
    ap.add_argument("--indir", default=INDIR)
    ap.add_argument("--outdir", default=OUTDIR)
    args = ap.parse_args(argv)
    return crop_all(args.kml, args.indir, args.outdir)


if __name__ == "__main__":
    main()

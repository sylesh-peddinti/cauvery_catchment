"""Clip monthly precipitation GeoTIFFs to the catchment KML extent.

Reads the catchment polygon straight from KML XML (no GDAL vector driver
needed), then masks + crops every monthly .tif with rasterio. Cells outside
the catchment are set to nodata.
"""
import argparse
import glob
import os
import xml.etree.ElementTree as ET

KML = r"C:\Users\pvssy\Documents\Sylesh\dev\cauvery_catchment\data\catchment.kml"
INDIR = r"C:\Users\pvssy\Documents\Sylesh\dev\cauvery_catchment\data\processed\monthly_precip_tiff"
OUTDIR = r"C:\Users\pvssy\Documents\Sylesh\dev\cauvery_catchment\data\processed\monthly_precip_clipped"
NODATA = -9999.0


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


def read_kml_polygons(kml_path=KML):
    """Parse KML Placemark polygons into shapely geometries (lon/lat, WGS84).

    Args:
        kml_path: Path to the .kml file.

    Returns:
        List of shapely Polygon objects (with holes where defined).
    """
    from shapely.geometry import Polygon

    tree = ET.parse(kml_path)
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    polys = []
    for pm in tree.getroot().findall(".//k:Placemark", ns):
        for poly in pm.findall(".//k:Polygon", ns):
            outer = poly.find("k:outerBoundaryIs/k:LinearRing/k:coordinates", ns)
            if outer is None:
                continue
            shell = [(float(p.split(",")[0]), float(p.split(",")[1]))
                     for p in outer.text.strip().split()]
            holes = []
            for inner in poly.findall("k:innerBoundaryIs/k:LinearRing/k:coordinates", ns):
                holes.append([(float(p.split(",")[0]), float(p.split(",")[1]))
                              for p in inner.text.strip().split()])
            polys.append(Polygon(shell, holes))
    if not polys:
        raise ValueError(f"No polygons found in {kml_path}")
    return polys


def clip_one(src_path, shapes, dst_path, nodata=NODATA):
    """Mask + crop a single GeoTIFF to the catchment shapes.

    Args:
        src_path: Input .tif path.
        shapes: GeoJSON-like mapping sequence of catchment polygons.
        dst_path: Output .tif path.
        nodata: Fill value for cells outside the catchment.

    Returns:
        Output path.
    """
    _fix_proj_env()
    import rasterio
    from rasterio.mask import mask

    with rasterio.open(src_path) as src:
        out, transform = mask(src, shapes, crop=True, nodata=nodata, filled=True)
        profile = src.profile.copy()
        profile.update(height=out.shape[1], width=out.shape[2],
                       transform=transform, nodata=nodata, compress="LZW")
        tags = src.tags()
    with rasterio.open(dst_path, "w", **profile) as dst:
        dst.write(out)
        if tags:
            dst.update_tags(**tags)
    return dst_path


def clip_all(kml_path=KML, indir=INDIR, outdir=OUTDIR, nodata=NODATA):
    """Clip every monthly .tif in indir to the KML catchment extent.

    Args:
        kml_path: Path to the catchment .kml file.
        indir: Directory with monthly precipitation .tif files.
        outdir: Directory for clipped outputs (created if needed).
        nodata: Fill value outside the catchment.

    Returns:
        List of written .tif paths.
    """
    from shapely.geometry import mapping

    os.makedirs(outdir, exist_ok=True)
    shapes = [mapping(p) for p in read_kml_polygons(kml_path)]
    print(f"catchment: {len(shapes)} polygon(s)")
    srcs = sorted(glob.glob(os.path.join(indir, "*.tif")))
    if not srcs:
        raise FileNotFoundError(f"No .tif files in {indir}")
    written = []
    for i, src_path in enumerate(srcs, 1):
        dst_path = os.path.join(outdir, os.path.basename(src_path))
        clip_one(src_path, shapes, dst_path, nodata)
        written.append(dst_path)
        if i % 12 == 0 or i == len(srcs):
            print(f"clipped {i}/{len(srcs)} -> {dst_path}")
    print(f"done: {len(written)} files in {outdir}")
    return written


def main(argv=None):
    """CLI entry point for catchment clipping.

    Args:
        argv: Optional arg list for testing; defaults to sys.argv.
    """
    ap = argparse.ArgumentParser(description="Clip monthly precip TIFFs to catchment KML.")
    ap.add_argument("--kml", default=KML)
    ap.add_argument("--indir", default=INDIR)
    ap.add_argument("--outdir", default=OUTDIR)
    ap.add_argument("--nodata", type=float, default=NODATA)
    args = ap.parse_args(argv)
    return clip_all(args.kml, args.indir, args.outdir, args.nodata)


if __name__ == "__main__":
    main()

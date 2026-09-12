"""Accumulate hourly ERA5 total precipitation into monthly sums, saved as GeoTIFF.

Reads the local GRIB1 file message-by-message (streaming, no ecCodes needed),
decodes simple-packed values with numpy, groups by valid month from 2021 to
2026, and writes one GeoTIFF per month.
"""
import argparse
import os
import time
from datetime import datetime, timedelta

import numpy as np

INPUT = r"C:\Users\pvssy\Documents\Sylesh\dev\cauvery_catchment\data\ecmwf_era5_2021_2026.grib"
OUTDIR = r"C:\Users\pvssy\Documents\Sylesh\dev\cauvery_catchment\data\monthly_precip_tiff"

NI, NJ = 201, 201
LON1, LAT1 = 60.0, 50.0
RES = 0.25


def grib1_signed_int(raw):
    """Convert 2-byte GRIB1 sign-magnitude integer to Python int."""
    v = int.from_bytes(raw, "big")
    return -(v & 0x7FFF) if v & 0x8000 else v


def ibm370_float(raw):
    """Convert 4-byte IBM 370 hex float to Python float."""
    if raw == b"\x00\x00\x00\x00":
        return 0.0
    sign = -1.0 if raw[0] & 0x80 else 1.0
    exponent = (raw[0] & 0x7F) - 64
    mantissa = int.from_bytes(raw[1:4], "big") / 16777216.0
    return sign * mantissa * (16.0 ** exponent)


def parse_pds_valid(msg):
    """Extract valid datetime from a GRIB1 message buffer.

    Valid time = PDS base date plus P2 hours (hourly accumulation).

    Args:
        msg: Full message bytes (at least through the PDS).

    Returns:
        Datetime of field validity.
    """
    pds_len = int.from_bytes(msg[8:11], "big")
    pds = msg[8:8 + pds_len]
    year = (pds[24] - 1) * 100 + pds[12]
    base = datetime(year, pds[13], pds[14], pds[15], pds[16])
    return base + timedelta(hours=pds[19])  # P2


def decode_values(msg):
    """Decode GRIB1 simple-packed data section to a (NJ, NI) float64 array in metres.

    Args:
        msg: Full message bytes.

    Returns:
        2D numpy array with row 0 at the northernmost latitude.
    """
    pds_len = int.from_bytes(msg[8:11], "big")
    gds_len = int.from_bytes(msg[8 + pds_len:8 + pds_len + 3], "big")
    bo = 8 + pds_len + gds_len
    blen = int.from_bytes(msg[bo:bo + 3], "big")
    exp = grib1_signed_int(msg[bo + 4:bo + 6])
    ref = ibm370_float(msg[bo + 6:bo + 10])
    raw = msg[bo + 11 + 1:bo + blen]  # 1 filler octet, then packed uint16
    packed = np.frombuffer(raw, dtype=">u2").astype(np.float64)
    return (ref + packed * (2.0 ** exp)).reshape(NJ, NI)


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


def month_label(key):
    """Convert year*12+month key to 'YYYY-MM' string.

    Args:
        key: Integer key as year*12 + month (month 1-12).

    Returns:
        Label like '2021-12'.
    """
    return f"{(key - 1) // 12:04d}-{(key - 1) % 12 + 1:02d}"


def save_geotiff(path, data_mm):
    """Save a 2D monthly-sum array (mm) as a georeferenced GeoTIFF.

    Tries rasterio first; falls back to tifffile with GeoTIFF tags if the
    PROJ database is broken (e.g. PostgreSQL's PROJ_LIB shadowing rasterio).

    Args:
        path: Output .tif path.
        data_mm: 2D float array, row 0 = north (50N), col 0 = west (60E).
    """
    _fix_proj_env()
    try:
        from rasterio.transform import from_origin
        import rasterio

        transform = from_origin(LON1 - RES / 2, LAT1 + RES / 2, RES, RES)
        with rasterio.open(
            path, "w", driver="GTiff", height=NJ, width=NI, count=1,
            dtype="float32", crs="EPSG:4326", transform=transform, compress="LZW",
        ) as dst:
            dst.write(data_mm.astype(np.float32), 1)
            dst.update_tags(units="mm", variable="monthly total precipitation sum")
        return
    except Exception as e:
        print(f"rasterio failed ({e}); using tifffile fallback")
    import tifffile

    scale = (RES, RES, 0.0)
    tiepoint = (0.0, 0.0, 0.0, LON1 - RES / 2, LAT1 + RES / 2, 0.0)
    gkd = (1, 1, 0, 6, 1024, 0, 1, 2, 2048, 0, 1, 4326, 2049, 34737, 7, 0, 2050, 0, 1, 1)
    geo_ascii = b"WGS 84\x00"
    extratags = [
        (33550, "d", 3, scale, False),
        (33922, "d", 6, tiepoint, False),
        (34735, "H", len(gkd), tuple(gkd), False),
        (34737, "s", len(geo_ascii), geo_ascii, False),
    ]
    tifffile.imwrite(path, data_mm.astype(np.float32), extratags=extratags, compression="deflate")


def monthly_cumsum(path=INPUT, outdir=OUTDIR, start="2021-01", end="2026-10", to_mm=True):
    """Stream the GRIB file and write one monthly cumulative-sum GeoTIFF.

    Args:
        path: Input .grib path.
        outdir: Directory for monthly .tif files.
        start: First month inclusive as 'YYYY-MM'.
        end: Month exclusive as 'YYYY-MM'.
        to_mm: Multiply metre values by 1000 before saving.

    Returns:
        List of written .tif paths.
    """
    os.makedirs(outdir, exist_ok=True)
    sy, sm = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    first_month = sy * 12 + sm
    last_month = ey * 12 + em

    written = []
    acc = None
    cur_key = None
    n = 0
    t0 = time.time()
    with open(path, "rb") as f:
        while True:
            pos = f.tell()
            hdr = f.read(8)
            if not hdr:
                break
            if hdr[0:4] != b"GRIB":
                raise ValueError(f"Bad GRIB magic at byte {pos}")
            size = int.from_bytes(hdr[4:7], "big")  # GRIB edition 1
            f.seek(pos)
            msg = f.read(size)
            vt = parse_pds_valid(msg)
            key = vt.year * 12 + vt.month
            if key < first_month or key >= last_month:
                n += 1
                continue
            vals = decode_values(msg)
            if cur_key is None:
                cur_key = key
                acc = np.zeros((NJ, NI), dtype=np.float64)
            if key != cur_key:
                ym = month_label(cur_key)
                out = os.path.join(outdir, f"era5_tp_monthly_{ym}.tif")
                save_geotiff(out, acc * 1000.0 if to_mm else acc)
                written.append(out)
                print(f"saved {ym}: {out} ({time.time()-t0:.0f}s)")
                cur_key = key
                acc = np.zeros((NJ, NI), dtype=np.float64)
            acc += vals
            n += 1
    if acc is not None and cur_key is not None:
        ym = month_label(cur_key)
        out = os.path.join(outdir, f"era5_tp_monthly_{ym}.tif")
        save_geotiff(out, acc * 1000.0 if to_mm else acc)
        written.append(out)
        print(f"saved {ym}: {out}")
    print(f"done: {n} messages, {len(written)} months, {time.time()-t0:.0f}s")
    return written


def main(argv=None):
    """CLI entry point for monthly accumulation.

    Args:
        argv: Optional arg list for testing; defaults to sys.argv.
    """
    ap = argparse.ArgumentParser(description="Monthly cumulative precip from ERA5 GRIB to GeoTIFF.")
    ap.add_argument("--input", default=INPUT)
    ap.add_argument("--outdir", default=OUTDIR)
    ap.add_argument("--start", default="2021-01")
    ap.add_argument("--end", default="2026-10")
    args = ap.parse_args(argv)
    return monthly_cumsum(args.input, args.outdir, args.start, args.end)


if __name__ == "__main__":
    main()

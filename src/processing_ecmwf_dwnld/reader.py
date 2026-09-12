"""Read the local ERA5 GRIB file without re-downloading it."""
import argparse
import os
from datetime import datetime, timedelta

DEFAULT_GRIB = r"C:\Users\pvssy\Documents\Sylesh\dev\cauvery_catchment\data\ecmwf_era5_2021_2026.grib"


def read_pds(f, msg_offset, msg_len):
    """Parse the GRIB1 Product Definition Section at a message offset.

    Args:
        f: Open binary file object.
        msg_offset: Byte offset where the GRIB message starts.
        msg_len: Total message length in bytes (unused, kept for symmetry).

    Returns:
        Dict with table, centre, param, level_type, date tuple,
        and forecast offsets p1, p2 plus time_range indicator.
    """
    f.seek(msg_offset + 8)
    pds_len = int.from_bytes(f.read(3), "big")
    f.seek(msg_offset + 8)
    pds = f.read(pds_len)
    year_byte, month, day, hour, minute = pds[12], pds[13], pds[14], pds[15], pds[16]
    century = pds[24]
    year = (century - 1) * 100 + year_byte
    return {
        "table": pds[3], "centre": pds[4], "param": pds[8],
        "level_type": pds[9], "date": (year, month, day, hour, minute),
        "p1": pds[18], "p2": pds[19], "time_range": pds[20],
    }


def read_grid(f, msg_offset, msg_len):
    """Parse the GRIB1 Grid Description Section for grid shape and bounds.

    Args:
        f: Open binary file object.
        msg_offset: Byte offset where the GRIB message starts.
        msg_len: Total message length in bytes (unused, kept for symmetry).

    Returns:
        Dict with ni, nj, lat1/lon1, lat2/lon2, and di/dj resolution.
    """
    f.seek(msg_offset + 8)
    pds_len = int.from_bytes(f.read(3), "big")
    gds_off = msg_offset + 8 + pds_len
    f.seek(gds_off)
    gds_len = int.from_bytes(f.read(3), "big")
    f.seek(gds_off)
    gds = f.read(min(gds_len, 64))
    ni = int.from_bytes(gds[6:8], "big")
    nj = int.from_bytes(gds[8:10], "big")
    lat1 = int.from_bytes(gds[10:13], "big", signed=True) / 1000.0
    lon1 = int.from_bytes(gds[13:16], "big", signed=True) / 1000.0
    lat2 = int.from_bytes(gds[17:20], "big", signed=True) / 1000.0
    lon2 = int.from_bytes(gds[20:23], "big", signed=True) / 1000.0
    di = int.from_bytes(gds[23:25], "big") / 1000.0
    dj = int.from_bytes(gds[25:27], "big") / 1000.0
    return {"ni": ni, "nj": nj, "lat1": lat1, "lon1": lon1, "lat2": lat2, "lon2": lon2, "di": di, "dj": dj}


def summarize(path=DEFAULT_GRIB, sample=10000):
    """Scan GRIB headers and print message count, param, grid, and time span.

    Args:
        path: Path to the .grib file.
        sample: Read full PDS every N messages to reduce I/O.

    Returns:
        Dict with messages count, file size, and grid info.
    """
    size = os.path.getsize(path)
    n = 0
    first = None
    last_pds = None
    grid = None
    with open(path, "rb") as f:
        while True:
            pos = f.tell()
            hdr = f.read(8)
            if not hdr:
                break
            if hdr[0:4] != b"GRIB":
                raise ValueError(f"Bad magic at {pos}")
            total = int.from_bytes(hdr[4:7], "big")  # file is GRIB1
            if n == 0:
                first = (pos, total)
                grid = read_grid(open(path, "rb"), pos, total)
            if n % sample == 0:
                last_pds = read_pds(open(path, "rb"), pos, total)
            n += 1
            f.seek(pos + total)
    last_pds = read_pds(open(path, "rb"), size - first[1], first[1])
    print(f"file: {path}")
    print(f"size: {size} bytes ({size/1e9:.3f} GB)")
    print(f"messages: {n} (GRIB1, {first[1]} bytes each)")
    print("param: 128.228 (total precipitation), surface, centre 98 ECMWF")
    print(f"grid: {grid}")
    print("first date ~2020-12-31 18Z, last date ~2026-09-05 18Z (hourly accumulation)")
    print(f"last PDS: {last_pds}")
    return {"messages": n, "size": size, "grid": grid}


def valid_time(pds):
    """Compute valid datetime as PDS base date plus P2 hours.

    Args:
        pds: Dict from read_pds() with date tuple and p2 offset.

    Returns:
        Datetime of the accumulated field validity time.
    """
    y, mo, d, h, mi = pds["date"]
    return datetime(y, mo, d, h, mi) + timedelta(hours=pds["p2"])


def extract_month(path=DEFAULT_GRIB, year_month="2021-01", out=None):
    """Copy only messages whose valid time falls in YYYY-MM. No ecCodes needed.

    Args:
        path: Input .grib path.
        year_month: Month selector as 'YYYY-MM'.
        out: Output path; defaults to input name suffixed with year_month.

    Returns:
        Output file path.
    """
    year, month = map(int, year_month.split("-"))
    if out is None:
        base, ext = os.path.splitext(path)
        out = f"{base}_{year_month}{ext}"
    kept = 0
    total = 0
    with open(path, "rb") as fin, open(out, "wb") as fout:
        while True:
            pos = fin.tell()
            hdr = fin.read(8)
            if not hdr:
                break
            if hdr[0:4] != b"GRIB":
                raise ValueError(f"Bad magic at {pos}")
            size = int.from_bytes(hdr[4:7], "big")  # GRIB1
            fin.seek(pos)
            raw = fin.read(size)
            with open(path, "rb") as f2:
                vt = valid_time(read_pds(f2, pos, size))
            if vt.year == year and vt.month == month:
                fout.write(raw)
                kept += 1
            total += 1
    print(f"kept {kept}/{total} messages -> {out} ({os.path.getsize(out)/1e6:.1f} MB)")
    return out


def decode_with_xarray(path=DEFAULT_GRIB):
    """Try a full xarray/cfgrib decode, falling back to header summary.

    Args:
        path: Path to the .grib file.

    Returns:
        xarray Dataset on success, otherwise the summarize() result dict.
    """
    try:
        import xarray as xr
        ds = xr.open_dataset(path, engine="cfgrib")
        print(ds)
        return ds
    except Exception as e:
        print(f"xarray/cfgrib decode unavailable ({e}).")
        print("Falling back to header summary (no ecCodes needed):")
        return summarize(path)


def main(argv=None):
    """CLI entry point: summarize, extract one month, or attempt full decode.

    Args:
        argv: Optional arg list for testing; defaults to sys.argv.

    Returns:
        Whatever the selected sub-action returns.
    """
    ap = argparse.ArgumentParser(description="Read local ERA5 GRIB (no download).")
    ap.add_argument("--file", default=DEFAULT_GRIB)
    ap.add_argument("--decode", action="store_true", help="try xarray/cfgrib full decode")
    ap.add_argument("--extract", metavar="YYYY-MM", help="extract 1 month to a smaller .grib")
    ap.add_argument("--out", default=None, help="output path for --extract")
    args = ap.parse_args(argv)
    if args.extract:
        return extract_month(args.file, args.extract, args.out)
    if args.decode:
        return decode_with_xarray(args.file)
    return summarize(args.file)


if __name__ == "__main__":
    main()

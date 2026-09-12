/* ------------------------------------------------------------------
 * Cauvery catchment — ERA5 monthly precipitation cross-check
 * Paste into the Earth Engine Code Editor: https://code.earthengine.google.com
 *
 * Reference (local pipeline under test):
 *   CDS: reanalysis-era5-single-levels, total_precipitation, hourly,
 *        area [50, 60, 0, 110], GRIB
 *   Local result:  2024-07 catchment mean ~6200 mm (suspect)
 *   Climatology:   July basin mean ~204 mm (IMD 1989-2019)
 *
 * This recomputes the same quantity from GEE's official
 * ECMWF/ERA5/HOURLY ingest: sum of hourly `total_precipitation`
 * (metres of water per hour) x 1000 over each month, averaged over
 * the catchment. No de-accumulation needed (ERA5 hourly tp is
 * already per-hour accumulations ending at validity time).
 * ------------------------------------------------------------------ */

// ---- 1. Catchment ---------------------------------------------------
// Bounding box of catchment.kml: lon 75.489-79.879, lat 10.124-13.557.
// For the exact polygon, upload catchment.kml as a Table asset and use:
//   var catchment = ee.FeatureCollection('users/USERNAME/catchment');
var catchment = ee.Geometry.Rectangle([75.489, 10.124, 79.879, 13.557]);
Map.centerObject(catchment, 7);

// ---- 2. ERA5 hourly total precipitation (m per hour) ------------------
var era5 = ee.ImageCollection('ECMWF/ERA5/HOURLY')
    .select('total_precipitation');

var START = ee.Date('2021-01-01');
var END = ee.Date('2026-10-01');  // exclusive -> last full month 2026-09
var SCALE = 27830;  // ~0.25 deg in metres

// ---- 3. Monthly sums + catchment stats, all server-side --------------
var nMonths = END.difference(START, 'month').toInt();
var feats = ee.List.sequence(0, nMonths.subtract(1)).map(function(i) {
  var s = START.advance(ee.Number(i), 'month');
  var e = s.advance(1, 'month');
  var monthlyMm = era5.filterDate(s, e).sum().multiply(1000).rename('tp_mm');
  var stats = monthlyMm.reduceRegion({
    reducer: ee.Reducer.mean().combine({
      reducer2: ee.Reducer.minMax(),
      sharedInputs: true
    }),
    geometry: catchment,
    scale: SCALE,
    maxPixels: 1e9
  });
  return ee.Feature(null, {
    month: s.format('YYYY-MM'),
    mean_mm: stats.get('tp_mm_mean'),
    min_mm: stats.get('tp_mm_min'),
    max_mm: stats.get('tp_mm_max')
  });
});
var fc = ee.FeatureCollection(feats);
print('Monthly catchment stats (ERA5 via GEE)', fc);

// ---- 4. Test months: 2024-01 and 2024-07 ------------------------------
var test = fc.filter(ee.Filter.inList('month', ['2024-01', '2024-07']));
print('Test months (GEE mm) vs local (1636 / 6206 mm):', test);

// ---- 5. July 2024 map -------------------------------------------------
var julyImg = era5
    .filterDate('2024-07-01', '2024-08-01')
    .sum().multiply(1000).rename('tp_mm')
    .clip(catchment);
Map.addLayer(julyImg,
  {min: 0, max: 600, palette: ['white', 'lightblue', 'blue', 'darkblue']},
  '2024-07 monthly tp (mm)');

// ---- 6. Time-series chart ----------------------------------------------
print(ui.Chart.feature.byFeature(fc, 'month', 'mean_mm')
  .setChartType('LineChart')
  .setOptions({
    title: 'Cauvery catchment mean monthly precipitation (ERA5, GEE)',
    hAxis: {title: 'Month'},
    vAxis: {title: 'mm'},
    pointSize: 3,
    lineWidth: 2
  }));

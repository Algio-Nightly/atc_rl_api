
/**
 * Coordinate Utility for RL ATC Visualizer
 * Center: Coimbatore International Airport [11.030288, 77.039218]
 * Units: Kilometers
 */

export const DEFAULT_CENTER = { lat: 11.030288, lon: 77.039218 };
const KM_PER_DEGREE_LAT = 111.32;

/**
 * Converts metric x, y (kilometers from center) to geographic [lat, lon].
 * @param {number} x - Easting in kilometers.
 * @param {number} y - Northing in kilometers.
 * @param {{lat: number, lon: number}} center - The [0,0] reference.
 * @returns {[number, number]} - [latitude, longitude].
 */
export function xyToLatLon(x, y, center = DEFAULT_CENTER) {
  const lat = center.lat + (y / KM_PER_DEGREE_LAT);
  const lon = center.lon + (x / (KM_PER_DEGREE_LAT * Math.cos(center.lat * Math.PI / 180)));
  return [lat, lon];
}

/**
 * Converts geographic latitude, longitude to metric x, y (kilometers from center).
 * @param {number} lat - Latitude.
 * @param {number} lon - Longitude.
 * @param {{lat: number, lon: number}} center - The [0,0] reference.
 * @returns {{x: number, y: number}} - {x, y} offsets in kilometers.
 */
export function latLonToXY(lat, lon, center = DEFAULT_CENTER) {
  const y = (lat - center.lat) * KM_PER_DEGREE_LAT;
  const x = (lon - center.lon) * (KM_PER_DEGREE_LAT * Math.cos(center.lat * Math.PI / 180));
  return { x, y };
}

export const MAP_CENTER = [DEFAULT_CENTER.lat, DEFAULT_CENTER.lon];

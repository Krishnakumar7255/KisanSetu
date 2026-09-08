// Geolocation utility and Haversine distance calculator for KisanQueue

/**
 * Calculates great-circle distance between two geographic coordinates using the Haversine formula.
 * @param {number} lat1 Latitude of point 1 in degrees
 * @param {number} lon1 Longitude of point 1 in degrees
 * @param {number} lat2 Latitude of point 2 in degrees
 * @param {number} lon2 Longitude of point 2 in degrees
 * @returns {number|null} Distance in kilometers rounded to 1 decimal place
 */
export function calculateHaversineDistance(lat1, lon1, lat2, lon2) {
  if (lat1 == null || lon1 == null || lat2 == null || lon2 == null) return null;
  const numLat1 = Number(lat1);
  const numLon1 = Number(lon1);
  const numLat2 = Number(lat2);
  const numLon2 = Number(lon2);

  if (isNaN(numLat1) || isNaN(numLon1) || isNaN(numLat2) || isNaN(numLon2)) return null;

  const R = 6371; // Earth radius in kilometers
  const dLat = ((numLat2 - numLat1) * Math.PI) / 180;
  const dLon = ((numLon2 - numLon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((numLat1 * Math.PI) / 180) *
      Math.cos((numLat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  const distance = R * c;
  return Math.round(distance * 10) / 10;
}

/**
 * Requests user location using HTML5 Geolocation API.
 * @returns {Promise<{latitude: number, longitude: number}>}
 */
export function getUserCoordinates() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Geolocation is not supported by your browser.'));
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
        });
      },
      (error) => {
        let msg = 'Unable to retrieve location.';
        switch (error.code) {
          case error.PERMISSION_DENIED:
            msg = 'Location access was denied. Please allow location permissions in your browser.';
            break;
          case error.POSITION_UNAVAILABLE:
            msg = 'Location information is currently unavailable.';
            break;
          case error.TIMEOUT:
            msg = 'Request to get location timed out.';
            break;
          default:
            msg = error.message || msg;
        }
        reject(new Error(msg));
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 60000,
      }
    );
  });
}

/**
 * Finds the nearest centre to a user's coordinates.
 * Supports latitude/longitude or lat/lng field names.
 */
export function findNearestCentre(centres, position) {
  if (!Array.isArray(centres) || !position) return null;
  const userLat = Number(position.latitude ?? position.lat);
  const userLon = Number(position.longitude ?? position.lon ?? position.lng);
  if (!Number.isFinite(userLat) || !Number.isFinite(userLon)) return null;

  let nearest = null;
  let minDistance = Infinity;
  for (const centre of centres) {
    const lat = Number(centre.latitude ?? centre.lat);
    const lon = Number(centre.longitude ?? centre.lon ?? centre.lng);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
    const distance = calculateHaversineDistance(userLat, userLon, lat, lon);
    if (distance != null && distance < minDistance) {
      minDistance = distance;
      nearest = centre;
    }
  }
  return nearest;
}

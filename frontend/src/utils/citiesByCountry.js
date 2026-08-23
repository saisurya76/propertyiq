// Major cities per supported country, for the City dropdown on the main
// report form. Country stays a disabled, context-driven field (set by
// which site the user is on); city is the one field within that country
// the user actually picks themselves, so it needs a real, enabled list.
export const CITIES_BY_COUNTRY = {
  "India": [
    "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai", "Kolkata", "Pune",
    "Ahmedabad", "Jaipur", "Surat", "Lucknow", "Kanpur", "Nagpur", "Indore",
    "Thane", "Bhopal", "Visakhapatnam", "Patna", "Vadodara", "Ghaziabad",
    "Other",
  ],
  "Thailand": [
    "Bangkok", "Chiang Mai", "Pattaya", "Phuket", "Nonthaburi",
    "Nakhon Ratchasima", "Hat Yai", "Udon Thani", "Khon Kaen", "Surat Thani",
    "Other",
  ],
  "Philippines": [
    "Manila", "Quezon City", "Davao City", "Cebu City", "Zamboanga City",
    "Taguig", "Pasig", "Cagayan de Oro", "Makati", "Bacolod",
    "Other",
  ],
  "Vietnam": [
    "Ho Chi Minh City", "Hanoi", "Da Nang", "Hai Phong", "Can Tho",
    "Bien Hoa", "Hue", "Nha Trang", "Vung Tau", "Buon Ma Thuot",
    "Other",
  ],
  "Indonesia": [
    "Jakarta", "Surabaya", "Bandung", "Medan", "Bekasi", "Semarang",
    "Palembang", "Makassar", "Depok", "Tangerang",
    "Other",
  ],
};

// Returns [value, label] pairs. Includes a leading placeholder with an
// EXPLICIT empty value when no city is selected yet — a real, caught
// mistake otherwise: visiting /th seeds city as "" (no default city
// forced on any country, deliberately, since guessing one would be
// arbitrary), and a plain list of real city names has no "" option for
// a controlled <select> to match, so it would silently fall back to
// showing the first real city while formData.city stays "" underneath
// — the same class of bug already caught twice before with mismatched
// dropdown values (the "sq meter" and country-list cases). Giving the
// placeholder an explicit value="" makes React's controlled select
// match it correctly by value, not by accidental list position.
export function getCitiesForCountry(country, currentCity) {
  const cities = CITIES_BY_COUNTRY[country] || ["Other"];
  const options = cities.map((c) => [c, c]);
  if (!currentCity) {
    return [["", "Select a city..."], ...options];
  }
  if (!cities.includes(currentCity)) {
    return [[currentCity, currentCity], ...options];
  }
  return options;
}

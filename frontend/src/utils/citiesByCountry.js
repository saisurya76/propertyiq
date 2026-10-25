// Major cities per supported country, for the City dropdown on the main
// report form. Country stays a disabled, context-driven field (set by
// which site the user is on); city is the one field within that country
// the user actually picks themselves, so it needs a real, enabled list.
// Which Indian state each listed city is in. The report form has no state
// field, so picking a city sets the state too; otherwise a Goa property would
// be sent as "Telangana", the India default.
export const INDIA_CITY_STATE = {
  "Mumbai": "Maharashtra", "Navi Mumbai": "Maharashtra", "Thane": "Maharashtra", "Pune": "Maharashtra",
  "Nagpur": "Maharashtra", "Nashik": "Maharashtra",
  "Delhi": "Delhi", "Noida": "Uttar Pradesh", "Ghaziabad": "Uttar Pradesh", "Lucknow": "Uttar Pradesh",
  "Kanpur": "Uttar Pradesh", "Varanasi": "Uttar Pradesh", "Agra": "Uttar Pradesh",
  "Gurgaon": "Haryana", "Faridabad": "Haryana",
  "Bangalore": "Karnataka", "Mysuru": "Karnataka", "Mangalore": "Karnataka",
  "Hyderabad": "Telangana",
  "Chennai": "Tamil Nadu", "Coimbatore": "Tamil Nadu", "Madurai": "Tamil Nadu",
  "Kolkata": "West Bengal",
  "Ahmedabad": "Gujarat", "Surat": "Gujarat", "Vadodara": "Gujarat", "Rajkot": "Gujarat",
  "Jaipur": "Rajasthan", "Jodhpur": "Rajasthan", "Udaipur": "Rajasthan",
  "Indore": "Madhya Pradesh", "Bhopal": "Madhya Pradesh",
  "Visakhapatnam": "Andhra Pradesh", "Vijayawada": "Andhra Pradesh",
  "Patna": "Bihar",
  "Kochi": "Kerala", "Thiruvananthapuram": "Kerala",
  "Panaji": "Goa", "Margao": "Goa", "Mapusa": "Goa", "Vasco da Gama": "Goa",
  "Chandigarh": "Chandigarh", "Ludhiana": "Punjab", "Amritsar": "Punjab",
  "Bhubaneswar": "Odisha", "Ranchi": "Jharkhand", "Raipur": "Chhattisgarh",
  "Dehradun": "Uttarakhand", "Guwahati": "Assam",
};

export const CITIES_BY_COUNTRY = {
  "India": [
    "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai", "Kolkata", "Pune",
    "Ahmedabad", "Jaipur", "Surat", "Lucknow", "Kanpur", "Nagpur", "Indore",
    "Thane", "Navi Mumbai", "Bhopal", "Visakhapatnam", "Vijayawada", "Patna",
    "Vadodara", "Ghaziabad", "Noida", "Gurgaon", "Faridabad", "Chandigarh",
    "Coimbatore", "Madurai", "Kochi", "Thiruvananthapuram", "Mysuru", "Mangalore",
    "Panaji", "Margao", "Mapusa", "Vasco da Gama",
    "Nashik", "Rajkot", "Jodhpur", "Udaipur", "Varanasi", "Agra", "Ludhiana",
    "Amritsar", "Bhubaneswar", "Ranchi", "Raipur", "Dehradun", "Guwahati",
    "Other",
  ],
  "Thailand": [
    "Bangkok", "Chiang Mai", "Pattaya", "Phuket", "Nonthaburi",
    "Nakhon Ratchasima", "Hat Yai", "Udon Thani", "Khon Kaen", "Surat Thani",
    "Hua Hin", "Koh Samui", "Krabi", "Rayong", "Chonburi", "Chiang Rai",
    "Other",
  ],
  "Philippines": [
    "Manila", "Quezon City", "Davao City", "Cebu City", "Zamboanga City",
    "Taguig", "Pasig", "Cagayan de Oro", "Makati", "Bacolod",
    "Mandaluyong", "Parañaque", "Las Piñas", "Caloocan", "Antipolo", "Iloilo City",
    "Baguio", "Angeles", "Lapu-Lapu", "Tagaytay",
    "Other",
  ],
  "Vietnam": [
    "Ho Chi Minh City", "Hanoi", "Da Nang", "Hai Phong", "Can Tho",
    "Bien Hoa", "Hue", "Nha Trang", "Vung Tau", "Buon Ma Thuot",
    "Hoi An", "Da Lat", "Quy Nhon", "Thu Duc", "Binh Duong", "Phu Quoc",
    "Other",
  ],
  "Indonesia": [
    "Jakarta", "Surabaya", "Bandung", "Medan", "Bekasi", "Semarang",
    "Palembang", "Makassar", "Depok", "Tangerang",
    "Denpasar", "Yogyakarta", "Malang", "Bogor", "Batam", "Balikpapan",
    "Manado", "Pekanbaru",
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

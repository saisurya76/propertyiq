// The concept of an officially government-published property valuation
// (used as a tax/registration-fee base, typically below true market
// price) is genuinely real in multiple countries, not India-specific —
// just called different things. Rather than hiding this field for
// non-India properties, or leaving it mislabeled with India-only
// terminology regardless of the property's actual country, this gives
// each supported country its own accurate name for the real concept
// that exists there.
//
// India: the "circle rate" / "ready reckoner rate" / "guidance value" —
// a government-published minimum valuation used for stamp duty and
// registration.
//
// Thailand: the government-appraised value set by the Treasury
// Department and Land Department, adjusted periodically, used as the
// base for transfer fees, stamp duty, specific business tax, and the
// annual Land and Building Tax — genuinely the same underlying concept
// as India's circle rate, just a different name and administering body.
const GOVERNMENT_VALUE_LABELS = {
  india: {
    label: "Government Guidance Value",
    shortLabel: "Government Guidance",
    helpText: "The circle rate / ready reckoner rate — India's government-published minimum property valuation, used for stamp duty and registration.",
  },
  thailand: {
    label: "Government Appraised Value",
    shortLabel: "Government Appraised Value",
    helpText: "Thailand's official Treasury/Land Department appraised value — used as the base for transfer fees, stamp duty, and the annual Land and Building Tax.",
  },
};

const DEFAULT_LABEL = {
  label: "Government Guidance Value",
  shortLabel: "Government Guidance",
  helpText: "The official government-published property valuation used for local tax/registration purposes, where one exists.",
};

export function getGovernmentValueLabel(country) {
  const key = (country || "").trim().toLowerCase();
  return GOVERNMENT_VALUE_LABELS[key] || DEFAULT_LABEL;
}

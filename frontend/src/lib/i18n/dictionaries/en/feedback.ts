/** API error codes (types/api.ts) and form-validation messages. */
export const errors = {
  unauthenticated: "Your session has ended. Please sign in again.",
  forbidden: "You don't have permission to do that.",
  not_found: "We couldn't find what you asked for.",
  validation: "Some of the information isn't valid. Please check and try again.",
  invalid_credentials: "Incorrect ID/username or password.",
  national_id_taken: "An account with this National ID already exists.",
  phone_taken: "An account with this mobile number already exists.",
  username_taken: "This username is already taken.",
  service_unavailable: "This service isn't accepting requests right now.",
  invalid_transition: "That status change isn't allowed from the current status.",
  request_closed: "This request is closed and can't be changed.",
  network: "A network error occurred. Please try again.",
  unknown: "Something went wrong. Please try again.",
} as const;

export const validation = {
  required: "This field is required",
  fullName: "Enter your full name (at least 2 characters)",
  nationalId: {
    format: "National ID must be exactly 10 digits",
    checksum: "This National ID isn't valid — check the digits",
  },
  phone: "Enter an 11-digit mobile number starting with 09",
  postalCode: "Postal code must be exactly 10 digits",
  address: "Enter your address (at least 5 characters)",
  password: {
    min: "Use at least 8 characters",
    mix: "Use at least one letter and one digit",
    mismatch: "Passwords don't match",
  },
  accept: "Please confirm to continue",
  username: "3–20 characters: lowercase letters, digits or underscore, starting with a letter",
  description: {
    min: "Describe your request in at least 10 characters",
    max: "Keep it under 1000 characters",
  },
  number: {
    invalid: "Enter a valid number",
    min: "Must be at least {min}",
    max: "Must be at most {max}",
  },
  text: { max: "Keep it under {max} characters" },
  select: "Choose an option",
  names: "Enter the name in both languages",
  departments: "Choose at least one department",
  note: { required: "Add a note explaining this decision to the applicant" },
} as const;

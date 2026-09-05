export const API_BASE_URL = "http://127.0.0.1:8000";

const ES_SERVIDOR_LOCAL = typeof window !== "undefined" &&
  ["localhost", "127.0.0.1"].includes(window.location.hostname) &&
  window.location.port === "5600";

export const API_REQUEST_BASE_URL = ES_SERVIDOR_LOCAL
  ? window.location.origin
  : API_BASE_URL;

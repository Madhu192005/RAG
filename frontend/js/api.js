/**
 * WasteWise AI – api.js (Step 3 Enhanced)
 * -----------------------------------------
 * Robust, unified fetch() client wrapper for the FastAPI backend.
 * Features:
 *   • Automatic JSON serialization & deserialization.
 *   • Central Bearer JWT token header injection from localStorage.
 *   • Robust error extraction (handles both string and FastAPI 422 list details).
 *   • Dedicated helper methods for all Step 3 endpoints.
 * Requires: config.js must be loaded prior to this script.
 */

const WW_API = (() => {
  const TOKEN_KEY = "ww_access_token";

  function getBaseUrl() {
    return (typeof WW_CONFIG !== "undefined" && WW_CONFIG.BACKEND_URL) 
      ? WW_CONFIG.BACKEND_URL 
      : "http://localhost:8000";
  }

  function getToken() {
    return localStorage.getItem(TOKEN_KEY) || null;
  }

  function setToken(token) {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  }

  function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
  }

  /**
   * Internal request dispatcher
   */
  async function request(method, path, body = null, isFormData = false) {
    const url = getBaseUrl() + path;
    const headers = { Accept: "application/json" };

    // Inject Bearer token if user is authenticated
    const token = getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    if (body && !isFormData) {
      headers["Content-Type"] = "application/json";
    }

    const opts = { method, headers };
    if (body) {
      opts.body = isFormData ? body : JSON.stringify(body);
    }

    let response;
    try {
      response = await fetch(url, opts);
    } catch (networkError) {
      throw new Error(`Network failure connecting to ${url}: ${networkError.message}`);
    }

    if (!response.ok) {
      let errorMsg = `HTTP ${response.status} ${response.statusText}`;
      try {
        const errorJson = await response.json();
        if (typeof errorJson.detail === "string") {
          errorMsg = errorJson.detail;
        } else if (Array.isArray(errorJson.detail)) {
          // Format FastAPI Pydantic validation errors nicely
          errorMsg = errorJson.detail.map(d => `${d.loc ? d.loc.join('.') : 'field'}: ${d.msg}`).join("; ");
        } else if (errorJson.message) {
          errorMsg = errorJson.message;
        }
      } catch {
        // Fallback to text status
      }
      const err = new Error(errorMsg);
      err.status = response.status;
      throw err;
    }

    // 204 No Content
    if (response.status === 204) return null;

    return response.json();
  }

  return {
    // Core HTTP primitives
    get:      (path)             => request("GET",    path),
    post:     (path, body)       => request("POST",   path, body),
    put:      (path, body)       => request("PUT",    path, body),
    delete:   (path)             => request("DELETE", path),
    postForm: (path, formData)   => request("POST",   path, formData, true),

    // Token management
    getToken,
    setToken,
    clearToken,

    // Step 1 Health check
    health: () => request("GET", (typeof WW_CONFIG !== "undefined" ? WW_CONFIG.ENDPOINTS.HEALTH : "/health")),

    // Authentication
    register: (userData) => request("POST", WW_CONFIG.ENDPOINTS.AUTH_REGISTER, userData),
    login: async (credentials) => {
      const data = await request("POST", WW_CONFIG.ENDPOINTS.AUTH_LOGIN, credentials);
      if (data && data.access_token) {
        setToken(data.access_token);
      }
      return data;
    },
    getMe: () => request("GET", WW_CONFIG.ENDPOINTS.AUTH_ME),

    // User Profile
    getProfile: () => request("GET", WW_CONFIG.ENDPOINTS.USERS_PROFILE),
    updateProfile: (profileData) => request("PUT", WW_CONFIG.ENDPOINTS.USERS_PROFILE, profileData),

    // Waste Management
    getWasteCategories: () => request("GET", WW_CONFIG.ENDPOINTS.WASTE_CATEGORIES),
    submitWasteReport: (reportData) => request("POST", WW_CONFIG.ENDPOINTS.WASTE_REPORTS, reportData),
    getWasteReports: (params = "") => request("GET", `${WW_CONFIG.ENDPOINTS.WASTE_REPORTS}${params ? '?' + params : ''}`),
    getWasteReportById: (id) => request("GET", `${WW_CONFIG.ENDPOINTS.WASTE_REPORTS}/${id}`),

    // AI Assistant
    chatAssistant: (message, sessionId = null) => 
      request("POST", WW_CONFIG.ENDPOINTS.ASSISTANT_CHAT, { message, session_id: sessionId }),

    // Centers
    getCenters: (params = "") => request("GET", `${WW_CONFIG.ENDPOINTS.CENTERS}${params ? '?' + params : ''}`),
    getCenterById: (id) => request("GET", `${WW_CONFIG.ENDPOINTS.CENTERS}/${id}`),

    // Collection
    submitCollectionRequest: (reqData) => request("POST", WW_CONFIG.ENDPOINTS.COLLECTION_REQUESTS, reqData),
    getCollectionRequests: (params = "") => request("GET", `${WW_CONFIG.ENDPOINTS.COLLECTION_REQUESTS}${params ? '?' + params : ''}`),

    // Analytics
    getAnalyticsSummary: () => request("GET", WW_CONFIG.ENDPOINTS.ANALYTICS_SUMMARY),
    getAnalyticsMonthly: () => request("GET", WW_CONFIG.ENDPOINTS.ANALYTICS_MONTHLY),
    getAnalyticsCategories: () => request("GET", WW_CONFIG.ENDPOINTS.ANALYTICS_CATEGORIES),
  };
})();

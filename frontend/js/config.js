/**
 * WasteWise AI – config.js (Step 3 Enhanced)
 * -------------------------------------------
 * Centralized API endpoint routing and client constants.
 * Modify BACKEND_URL here to target any host (local dev, staging, production).
 */

const WW_CONFIG = {
  BACKEND_URL: "http://localhost:8000",

  // REST API Endpoints (all prefixed with BACKEND_URL)
  ENDPOINTS: {
    // System
    ROOT:                 "/",
    HEALTH:               "/health",

    // Authentication
    AUTH_REGISTER:        "/api/auth/register",
    AUTH_LOGIN:           "/api/auth/login",
    AUTH_ME:              "/api/auth/me",

    // User Profile
    USERS_PROFILE:        "/api/users/profile",

    // Waste Management & Streams
    WASTE_CATEGORIES:     "/api/waste/categories",
    WASTE_REPORTS:        "/api/waste/reports",

    // AI Recycling Assistant
    ASSISTANT_CHAT:       "/api/assistant/chat",
    CHAT:                 "/api/assistant/chat",  // Backward compatibility alias

    // Recycling Center Directory
    CENTERS:              "/api/centers",

    // Collection Logistics
    COLLECTION_REQUESTS:  "/api/collection/requests",
    COLLECTION:           "/api/collection/requests",  // Backward compatibility alias

    // Analytics & ESG
    ANALYTICS_SUMMARY:    "/api/analytics/summary",
    ANALYTICS_MONTHLY:    "/api/analytics/monthly",
    ANALYTICS_CATEGORIES: "/api/analytics/categories",
    ANALYTICS:            "/api/analytics/summary",    // Backward compatibility alias
  },

  // App Metadata
  APP_NAME: "WasteWise AI",
  VERSION:  "0.3.0",
};

// Freeze configuration against accidental modification
Object.freeze(WW_CONFIG);
Object.freeze(WW_CONFIG.ENDPOINTS);

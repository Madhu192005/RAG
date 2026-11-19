/**
 * WasteWise AI – validation.js
 * -----------------------------
 * Reusable form-validation helpers.
 *
 * Usage:
 *   WW_VALIDATE.required(value, "Name")          → "" | "Name is required"
 *   WW_VALIDATE.email(value)                     → "" | "Invalid email"
 *   WW_VALIDATE.minLength(value, 10, "Address")  → "" | "Address must be …"
 *   WW_VALIDATE.form(formEl)                     → true | false (also shows inline errors)
 */

const WW_VALIDATE = (() => {

  function required(value, label = "Field") {
    return String(value).trim() === "" ? `${label} is required.` : "";
  }

  function email(value) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) ? "" : "Enter a valid email address.";
  }

  function minLength(value, min, label = "Field") {
    return String(value).trim().length < min
      ? `${label} must be at least ${min} characters.`
      : "";
  }

  function phone(value) {
    return /^[0-9\s\+\-\(\)]{7,15}$/.test(value.trim()) ? "" : "Enter a valid phone number.";
  }

  /**
   * Validate every <input>, <select>, <textarea> that has data-validate="*".
   * Supported validators (comma-separated in data-validate):
   *   required, email, phone, minlength=N
   *
   * Shows / clears .field-error span next to each field.
   * Returns true if all fields pass.
   */
  function form(formEl) {
    if (!formEl) return false;
    let valid = true;

    formEl.querySelectorAll("[data-validate]").forEach(field => {
      const rules  = field.dataset.validate.split(",").map(r => r.trim());
      const label  = field.dataset.label || field.name || "Field";
      const value  = field.value;
      let   errMsg = "";

      for (const rule of rules) {
        if (rule === "required")          errMsg = required(value, label);
        else if (rule === "email")        errMsg = email(value);
        else if (rule === "phone")        errMsg = phone(value);
        else if (rule.startsWith("minlength=")) {
          const n = parseInt(rule.split("=")[1], 10);
          errMsg = minLength(value, n, label);
        }
        if (errMsg) break;
      }

      // Show / clear inline error
      let errEl = field.parentElement.querySelector(".field-error");
      if (!errEl) {
        errEl = document.createElement("span");
        errEl.className = "field-error";
        field.parentElement.appendChild(errEl);
      }
      errEl.textContent = errMsg;
      field.classList.toggle("invalid", !!errMsg);
      if (errMsg) valid = false;
    });

    return valid;
  }

  return { required, email, minLength, phone, form };
})();

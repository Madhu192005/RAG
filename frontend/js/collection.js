"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("collectionForm");
  const list = document.getElementById("requestsList");
  const success = document.getElementById("formSuccessAlert");
  const submit = document.getElementById("submitPickupBtn");
  const date = document.getElementById("pickupDate");
  const classification = document.getElementById("classificationId");
  const centerSelect = document.getElementById("recyclingCenterId");
  const category = document.getElementById("wasteCategory");
  const params = new URLSearchParams(window.location.search);
  let pickupCoordinates = null;
  date.min = new Date().toISOString().slice(0, 10);
  date.value = date.min;
  if (params.get("classification_id")) classification.value = params.get("classification_id");
  if (!WW_API.getToken()) {
    document.getElementById("requestListNotice").textContent = "Sign in to create and track private collection requests.";
  }

  document.getElementById("pickupLocationButton").addEventListener("click", () => {
    const status = document.getElementById("pickupLocationStatus");
    if (!navigator.geolocation) { status.textContent = "Location is unavailable in this browser. Enter your address manually."; return; }
    status.textContent = "Requesting location permission…";
    navigator.geolocation.getCurrentPosition(position => {
      pickupCoordinates = { latitude: position.coords.latitude, longitude: position.coords.longitude };
      status.textContent = "Coordinates captured for this request only.";
    }, error => {
      pickupCoordinates = null;
      status.textContent = error.code === error.PERMISSION_DENIED
        ? "Location permission denied. Enter your pickup address manually."
        : "Could not get location. Enter your pickup address manually.";
    }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 });
  });

  category.addEventListener("change", loadMatchingCenters);
  loadMatchingCenters();
  refreshRequests();

  async function loadMatchingCenters() {
    const selected = category.value;
    centerSelect.replaceChildren(new Option("No center selected", ""));
    try {
      let rows = [];
      if (classification.value) {
        const recommendation = await WW_API.get(`/api/recycling-centers/recommendations/${encodeURIComponent(classification.value)}`);
        rows = recommendation.matching_centers || [];
      } else if (selected) {
        rows = await WW_API.get(`/api/recycling-centers?category=${encodeURIComponent(selected)}&limit=100`);
      }
      rows.forEach(center => centerSelect.add(new Option(`${center.center_name || center.name} · ${center.city}`, center.id)));
      const centerId = params.get("center_id");
      if (centerId && !classification.value && !rows.some(center => String(center.id) === centerId)) {
        const center = await WW_API.get(`/api/recycling-centers/${encodeURIComponent(centerId)}`);
        centerSelect.add(new Option(`${center.name} · ${center.city}`, center.id));
      }
      if (centerId) centerSelect.value = centerId;
    } catch (_) { /* The optional destination list stays empty when no verified data is available. */ }
  }

  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!WW_API.getToken()) return showError("Sign in before submitting a collection request.");
    if (!WW_VALIDATE.form(form)) return;
    if (!category.value && !classification.value) return showError("Choose a waste stream or enter a confirmed classification ID.");
    submit.disabled = true; submit.textContent = "Submitting request…";
    const body = {
      full_name: document.getElementById("requesterName").value.trim(),
      email: document.getElementById("requesterEmail").value.trim(),
      phone: document.getElementById("requesterPhone").value.trim(),
      category: category.value || undefined,
      waste_classification_id: classification.value ? Number(classification.value) : undefined,
      recycling_center_id: centerSelect.value ? Number(centerSelect.value) : undefined,
      quantity: document.getElementById("quantity").value ? Number(document.getElementById("quantity").value) : undefined,
      quantity_unit: "kg", weight_tier: document.getElementById("weightTier").value,
      pickup_address: document.getElementById("pickupAddress").value.trim(),
      pickup_latitude: pickupCoordinates ? pickupCoordinates.latitude : undefined,
      pickup_longitude: pickupCoordinates ? pickupCoordinates.longitude : undefined,
      requested_date: date.value, time_slot: document.getElementById("timeSlot").value,
      special_instructions: document.getElementById("specialNotes").value.trim() || undefined
    };
    try {
      const result = await WW_API.post("/api/collections/requests", body);
      document.getElementById("successMessage").textContent = `Request #${result.id} was submitted. Current status: ${result.status}.`;
      success.style.display = "flex"; form.reset(); date.value = date.min; pickupCoordinates = null;
      document.getElementById("pickupLocationStatus").textContent = "Location is not stored unless you choose this.";
      await refreshRequests();
    } catch (error) { showError(error.message); }
    finally { submit.disabled = false; submit.textContent = "🚛 Submit Collection Request"; }
  });

  async function refreshRequests() {
    if (!WW_API.getToken()) { render([]); return; }
    try { render(await WW_API.get("/api/collections/requests?limit=100")); }
    catch (error) {
      render([]);
      document.getElementById("requestListNotice").textContent = error.status === 401
        ? "Sign in to see your requests." : `Requests could not be loaded: ${error.message}`;
    }
  }

  function render(rows) {
    document.getElementById("requestCount").textContent = `${rows.length} request${rows.length === 1 ? "" : "s"}`;
    list.replaceChildren();
    if (!rows.length) {
      const empty = document.createElement("p"); empty.className = "text-muted";
      empty.textContent = "No collection requests are available in this account."; list.appendChild(empty); return;
    }
    rows.forEach(request => {
      const card = document.createElement("article"); card.className = "collection-request-card";
      const header = document.createElement("div"); header.className = "flex-between";
      const title = document.createElement("strong"); title.textContent = `${request.category} · #${request.id}`;
      const badge = document.createElement("span"); badge.className = "badge badge-blue"; badge.textContent = request.status.replaceAll("_", " ");
      header.append(title, badge); card.appendChild(header);
      const info = document.createElement("p"); info.className = "text-muted";
      info.textContent = `Pickup: ${request.pickup_address} · ${request.requested_date || request.preferred_date} · ${request.time_slot || "time not specified"}`;
      card.appendChild(info);
      if (["pending", "approved"].includes(request.status)) {
        const cancel = document.createElement("button"); cancel.type = "button"; cancel.className = "btn btn-outline btn-sm"; cancel.textContent = "Cancel request";
        cancel.addEventListener("click", async () => {
          cancel.disabled = true;
          try { await WW_API.patch(`/api/collections/requests/${request.id}/cancel`, {}); await refreshRequests(); }
          catch (error) { showError(error.message); cancel.disabled = false; }
        }); card.appendChild(cancel);
      }
      list.appendChild(card);
    });
  }

  function showError(text) {
    const node = document.getElementById("requestListNotice"); node.textContent = text; node.classList.add("text-danger");
  }
});

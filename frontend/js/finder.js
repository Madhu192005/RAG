"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const search = document.getElementById("searchInput"), type = document.getElementById("categoryFilter");
  const radius = document.getElementById("radiusFilter"), container = document.getElementById("centersContainer");
  const centerType = document.getElementById("centerTypeFilter");
  const empty = document.getElementById("emptyState"), status = document.getElementById("finderStatus");
  const mapNode = document.getElementById("centerMap");
  let coordinates = null, map = null, tileLayer = null;
  const params = new URLSearchParams(window.location.search);
  const classificationId = params.get("classification_id");

  document.getElementById("currentLocationBtn").addEventListener("click", () => {
    if (!navigator.geolocation) return setStatus("Location is unavailable in this browser. Search by city or postal code instead.", true);
    setStatus("Your browser will ask for permission. Coordinates are used only for this search.");
    navigator.geolocation.getCurrentPosition(position => {
      coordinates = { latitude: position.coords.latitude, longitude: position.coords.longitude };
      search.value = "";
      runSearch();
    }, error => {
      coordinates = null;
      setStatus(error.code === error.PERMISSION_DENIED
        ? "Location permission was denied. Enter a city or postal code to search manually."
        : "Current location is unavailable. Enter a city or postal code to search manually.", true);
    }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 });
  });
  document.getElementById("searchBtn").addEventListener("click", runSearch);
  search.addEventListener("keydown", event => { if (event.key === "Enter") runSearch(); });
  search.addEventListener("input", () => { if (search.value.trim()) coordinates = null; });
  document.getElementById("resetFiltersBtn").addEventListener("click", reset);
  document.getElementById("clearSearchBtn").addEventListener("click", reset);

  if (classificationId) loadClassificationRecommendations();

  async function runSearch() {
    const wasteType = type.value;
    if (!wasteType) return setStatus("Select a waste stream or specific material to find centers that explicitly accept it.", true);
    const button = document.getElementById("searchBtn"); button.disabled = true; button.textContent = "Searching…";
    setStatus("Searching verified center records…");
    try {
      let response;
      if (coordinates) {
        const query = new URLSearchParams({ ...coordinates, radius_km: radius.value, waste_type: wasteType });
        if (centerType.value.trim()) query.set("center_type", centerType.value.trim());
        response = await WW_API.get(`/api/recycling-centers/nearby?${query}`);
        render(response.matching_centers || [], coordinates);
        setStatus(response.message || `${response.matching_centers.length} matching verified center(s) found within ${radius.value} km.`);
      } else {
        const query = new URLSearchParams({ limit: "100" });
        if (search.value.trim()) query.set("location", search.value.trim());
        if (centerType.value.trim()) query.set("center_type", centerType.value.trim());
        if (["Dry waste", "Wet waste", "Sanitary waste", "Special-care waste"].includes(wasteType)) query.set("category", wasteType);
        else query.set("waste_type", wasteType);
        response = await WW_API.get(`/api/recycling-centers?${query}`);
        render(response, null);
        setStatus(response.length ? `${response.length} verified database match(es). Distances require coordinates for both locations.`
                                  : "No verified centers explicitly accepting this waste type were found.", !response.length);
      }
    } catch (error) {
      render([], null); setStatus(error.message, true);
    } finally { button.disabled = false; button.textContent = "Search centers"; }
  }

  async function loadClassificationRecommendations() {
    setStatus("Checking the confirmed classification against explicit center acceptance…");
    try {
      const query = new URLSearchParams();
      if (coordinates) { query.set("latitude", coordinates.latitude); query.set("longitude", coordinates.longitude); query.set("radius_km", radius.value); }
      const location = search.value.trim(); if (location) query.set("location", location);
      const suffix = query.size ? `?${query}` : "";
      const response = await WW_API.get(`/api/recycling-centers/recommendations/${encodeURIComponent(classificationId)}${suffix}`);
      render(response.matching_centers || [], coordinates);
      setStatus(response.message || `${response.matching_centers.length} center(s) explicitly accept ${response.waste_type}.`);
      if (response.waste_type) {
        const option = [...type.options].find(item => item.value === response.waste_type || item.textContent === response.waste_type);
        if (option) type.value = option.value;
      }
    } catch (error) { render([], null); setStatus(error.message, true); }
  }

  function render(centers, origin) {
    container.replaceChildren(); empty.style.display = centers.length ? "none" : "block";
    container.style.display = centers.length ? "grid" : "none";
    document.getElementById("resultsCountBadge").textContent = `${centers.length} center${centers.length === 1 ? "" : "s"}`;
    centers.forEach(center => container.appendChild(centerCard(center)));
    renderMap(centers, origin);
  }

  function centerCard(center) {
    const card = document.createElement("article"); card.className = "center-card";
    const header = document.createElement("div"); header.className = "center-card-header";
    const titleBlock = document.createElement("div");
    const title = document.createElement("div"); title.className = "center-name"; title.textContent = center.center_name || center.name;
    const distance = document.createElement("div"); distance.className = "center-distance";
    distance.textContent = center.distance_km == null ? "Distance unavailable" : `${center.distance_km.toFixed(2)} km away`;
    titleBlock.append(title, distance);
    const verified = document.createElement("span"); verified.className = "badge badge-green"; verified.textContent = center.verification_status || "verified";
    header.append(titleBlock, verified); card.appendChild(header);
    const body = document.createElement("div"); body.className = "center-body";
    addDetail(body, "Address", [center.address, center.city, center.state, center.postal_code, center.country].filter(Boolean).join(", "));
    addDetail(body, "Hours", center.operating_hours || "Hours not listed");
    addDetail(body, "Accepted material classes", (center.accepted_waste_types || []).join(", ") || "No material classes recorded");
    addDetail(body, "Accepted streams", (center.accepted_categories || []).join(", ") || "No streams recorded");
    if (center.match_reason) addDetail(body, "Match", center.match_reason);
    if (center.phone) addDetail(body, "Phone", center.phone);
    if (center.email) addDetail(body, "Email", center.email);
    card.appendChild(body);
    const footer = document.createElement("div"); footer.className = "center-card-footer";
    const addressQuery = center.latitude != null && center.longitude != null
      ? `${center.latitude},${center.longitude}` : [center.address, center.city, center.postal_code].filter(Boolean).join(", ");
    if (addressQuery) {
      const directions = document.createElement("a");
      directions.href = `https://www.openstreetmap.org/search?query=${encodeURIComponent(addressQuery)}`;
      directions.target = "_blank"; directions.rel = "noopener noreferrer"; directions.className = "btn btn-primary btn-sm";
      directions.textContent = "Directions"; footer.appendChild(directions);
    }
    if (center.phone) { const phone = document.createElement("a"); phone.href = `tel:${encodeURIComponent(center.phone)}`; phone.className = "btn btn-secondary btn-sm"; phone.textContent = "Call"; footer.appendChild(phone); }
    if (classificationId) {
      const request = document.createElement("a");
      request.href = `collection.html?classification_id=${encodeURIComponent(classificationId)}&center_id=${encodeURIComponent(center.id)}`;
      request.className = "btn btn-secondary btn-sm"; request.textContent = "Request collection"; footer.appendChild(request);
    }
    card.appendChild(footer); return card;
  }

  function addDetail(parent, label, value) {
    if (!value) return;
    const row = document.createElement("div"); row.className = "center-detail-item";
    const text = document.createElement("span"); text.textContent = `${label}: ${value}`; row.appendChild(text); parent.appendChild(row);
  }

  function renderMap(centers, origin) {
    const located = centers.filter(center => Number.isFinite(center.latitude) && Number.isFinite(center.longitude));
    if (!located.length && !origin) { mapNode.style.display = "none"; return; }
    if (!window.L) { mapNode.style.display = "none"; return; }
    mapNode.style.display = "block";
    const initial = origin || [located[0].latitude, located[0].longitude];
    if (!map) {
      map = L.map(mapNode).setView(Array.isArray(initial) ? initial : [initial.latitude, initial.longitude], 11);
      tileLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
      }).addTo(map);
    }
    map.eachLayer(layer => { if (layer !== tileLayer) map.removeLayer(layer); });
    const markers = [];
    if (origin) markers.push(L.marker([origin.latitude, origin.longitude]).addTo(map).bindPopup("Search location"));
    located.forEach(center => {
      const popup = document.createElement("div");
      const name = document.createElement("strong"); name.textContent = center.center_name || center.name; popup.appendChild(name);
      const address = document.createElement("div"); address.textContent = [center.address, center.city, center.postal_code].filter(Boolean).join(", "); popup.appendChild(address);
      const accepted = document.createElement("div"); accepted.textContent = `Accepted: ${(center.accepted_waste_types || []).join(", ") || (center.accepted_categories || []).join(", ")}`; popup.appendChild(accepted);
      markers.push(L.marker([center.latitude, center.longitude]).addTo(map).bindPopup(popup));
    });
    if (markers.length) map.fitBounds(L.featureGroup(markers).getBounds().pad(0.2));
    setTimeout(() => map.invalidateSize(), 0);
  }

  function reset() {
    search.value = ""; type.value = ""; centerType.value = ""; coordinates = null; radius.value = "10";
    render([], null); setStatus("Select a waste type and location. Current location is requested only after a button press.");
  }
  function setStatus(text, isError = false) { status.textContent = text; status.classList.toggle("text-danger", isError); }
});

"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const el = (id) => document.getElementById(id);
  const drop = el("dropArea"), input = el("fileInput"), preview = el("previewContainer");
  const image = el("previewImage"), run = el("classifyBtn"), message = el("classificationMessage");
  const output = el("resultContent"), empty = el("emptyStateBox");
  let file = null, predictionId = null, objectUrl = null;

  el("browseFileBtn").addEventListener("click", () => input.click());
  drop.addEventListener("click", (event) => { if (event.target.id !== "browseFileBtn") input.click(); });
  ["dragenter", "dragover"].forEach(type => drop.addEventListener(type, event => {
    event.preventDefault(); drop.classList.add("drag-over");
  }));
  ["dragleave", "drop"].forEach(type => drop.addEventListener(type, event => {
    event.preventDefault(); drop.classList.remove("drag-over");
  }));
  drop.addEventListener("drop", event => { if (event.dataTransfer.files[0]) choose(event.dataTransfer.files[0]); });
  input.addEventListener("change", event => { if (event.target.files[0]) choose(event.target.files[0]); });

  function choose(selected) {
    if (!/^image\/(jpeg|png|webp)$/.test(selected.type)) return showError("Choose a JPEG, PNG, or WebP image.");
    if (selected.size > 10 * 1024 * 1024) return showError("Image exceeds the 10 MB upload limit.");
    file = selected;
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = URL.createObjectURL(file); image.src = objectUrl;
    drop.style.display = "none"; preview.style.display = "block";
    el("fileMeta").style.display = "block"; el("fileNameDisplay").textContent = file.name;
    el("fileSizeDisplay").textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB`;
    run.disabled = false; hideMessage();
  }

  el("removeImgBtn").addEventListener("click", () => {
    file = null; predictionId = null; input.value = ""; image.removeAttribute("src");
    preview.style.display = "none"; drop.style.display = "block"; el("fileMeta").style.display = "none";
    run.disabled = true; output.style.display = "none"; empty.style.display = "block";
    el("correctionFeedback").style.display = "none"; hideMessage();
    if (objectUrl) URL.revokeObjectURL(objectUrl); objectUrl = null;
  });

  run.addEventListener("click", async () => {
    if (!file) return;
    run.disabled = true; run.textContent = "Uploading and classifying…"; hideMessage();
    const data = new FormData(); data.append("file", file);
    const location = el("classificationLocation").value.trim(); if (location) data.append("location", location);
    try {
      const result = await WW_API.postForm("/api/classification/predict", data);
      render(result);
    } catch (error) { showError(error.message); }
    finally { run.disabled = false; run.textContent = "🔍 Run Classification Analysis"; }
  });

  el("submitCorrectionBtn").addEventListener("click", async () => {
    const selected = el("correctionSelect").value;
    if (!selected || !predictionId) return showError("Run a classification first, then choose the item class to confirm.");
    const button = el("submitCorrectionBtn"); button.disabled = true; button.textContent = "Saving…";
    try {
      const result = await WW_API.post("/api/classification/confirm", { prediction_id: predictionId, confirmed_class: selected });
      el("categoryDescription").textContent = `Confirmed as ${result.confirmed_class} · ${result.waste_category}.`;
      if (result.guidance) renderGuidance(result.guidance);
      showCenterLink(selected !== "Other / Unknown");
      showCollectionLink(selected !== "Other / Unknown");
      showCollectionLink(selected !== "Other / Unknown");
      el("correctionFeedback").textContent = result.guidance ? "Confirmation saved; cited guidance is shown above." : "Confirmation saved. Verified guidance is currently unavailable.";
      el("correctionFeedback").style.display = "block";
    } catch (error) { showError(error.message); }
    finally { button.disabled = false; button.textContent = "Confirm item"; }
  });

  function render(result) {
    predictionId = result.classification_id || null; empty.style.display = "none"; output.style.display = "block";
    el("statusBadge").textContent = result.status === "uncertain" ? "Needs confirmation" : "Classified";
    el("resultCategoryTitle").textContent = result.predicted_class || "Unable to identify item";
    const score = Number(result.confidence_score || 0); const pct = Math.round(score * 100);
    el("confidencePct").textContent = `${pct}%`;
    el("confidenceFill").style.width = `${pct}%`;
    el("confidenceLabel").textContent = `${result.confidence_label || "Model score"} · model score, not guaranteed accuracy`;
    el("categoryDescription").textContent = result.status === "uncertain"
      ? result.message : `Waste-management category: ${result.waste_category}.`;
    const list = el("topPredictions"); list.replaceChildren();
    (result.top_predictions || []).forEach(item => {
      const li = document.createElement("li"); li.textContent = `${item.class_name}: ${(Number(item.score) * 100).toFixed(1)}%`; list.appendChild(li);
    });
    el("correctionSelect").value = "";
    el("submitCorrectionBtn").textContent = result.requires_confirmation ? "Confirm item" : "Correct item";
    if (result.guidance) renderGuidance(result.guidance); else el("guidancePanel").style.display = "none";
    showCenterLink(result.status === "success" && !result.requires_confirmation && result.predicted_class !== "Other / Unknown");
    showCollectionLink(result.status === "success" && !result.requires_confirmation && result.predicted_class !== "Other / Unknown");
    showCollectionLink(result.status === "success" && !result.requires_confirmation && result.predicted_class !== "Other / Unknown");
    if (result.guidance_error) showError(result.guidance_error);
    else if (result.status === "uncertain") showError(result.message);
    else hideMessage();
  }

  function renderGuidance(guidance) {
    el("guidancePanel").style.display = "block"; el("guidanceAnswer").textContent = guidance.answer || "";
    const list = el("guidanceSources"); list.replaceChildren();
    (guidance.sources || []).forEach(source => {
      const li = document.createElement("li");
      const title = document.createElement("strong"); title.textContent = `${source.citation_id}: ${source.title}`;
      li.appendChild(title);
      if (source.url && /^https?:\/\//i.test(source.url)) {
        const link = document.createElement("a"); link.href = source.url; link.target = "_blank"; link.rel = "noopener noreferrer";
        link.textContent = " Source"; li.appendChild(link);
      }
      const excerpt = document.createElement("p"); excerpt.textContent = source.snippet; li.appendChild(excerpt); list.appendChild(li);
    });
  }

  function showCenterLink(visible) {
    const link = el("findCentersLink");
    if (!visible || !predictionId) { link.style.display = "none"; return; }
    link.href = `finder.html?classification_id=${encodeURIComponent(predictionId)}`;
    link.style.display = "inline-flex";
  }

  function showCollectionLink(visible) {
    const link = el("requestCollectionLink");
    if (!visible || !predictionId) { link.style.display = "none"; return; }
    link.href = `collection.html?classification_id=${encodeURIComponent(predictionId)}`;
    link.style.display = "inline-flex";
  }

  function showCollectionLink(visible) {
    const link = el("requestCollectionLink");
    if (!visible || !predictionId) { link.style.display = "none"; return; }
    link.href = `collection.html?classification_id=${encodeURIComponent(predictionId)}`;
    link.style.display = "inline-flex";
  }

  function showError(text) { message.textContent = text; message.style.display = "block"; }
  function hideMessage() { message.textContent = ""; message.style.display = "none"; }
});

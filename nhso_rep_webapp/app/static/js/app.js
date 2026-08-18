(function () {
  "use strict";

  const elements = {
    form: document.getElementById("downloadForm"),
    startDate: document.getElementById("startDate"),
    endDate: document.getElementById("endDate"),
    destination: document.getElementById("destination"),
    overwrite: document.getElementById("overwrite"),
    insecure: document.getElementById("insecure"),
    hcode: document.getElementById("hcode"),
    datePreset: document.getElementById("datePreset"),
    previewButton: document.getElementById("previewButton"),
    downloadButton: document.getElementById("downloadButton"),
    loginButton: document.getElementById("loginButton"),
    clearButton: document.getElementById("clearButton"),
    authIndicator: document.getElementById("authIndicator"),
    authLabel: document.getElementById("authLabel"),
    authHcode: document.getElementById("authHcode"),
    runState: document.getElementById("runState"),
    formAlert: document.getElementById("formAlert"),
    emptyState: document.getElementById("emptyState"),
    resultTableWrap: document.getElementById("resultTableWrap"),
    resultTableBody: document.getElementById("resultTableBody"),
    matchedCount: document.getElementById("matchedCount"),
    downloadedCount: document.getElementById("downloadedCount"),
    existsCount: document.getElementById("existsCount"),
    failedCount: document.getElementById("failedCount"),
    jobProgress: document.getElementById("jobProgress"),
    jobProgressLabel: document.getElementById("jobProgressLabel"),
    jobProgressPercent: document.getElementById("jobProgressPercent"),
    jobProgressBar: document.getElementById("jobProgressBar"),
    jobLogPanel: document.getElementById("jobLogPanel"),
    jobLogList: document.getElementById("jobLogList")
  };
  let applicationSettings = window.REP_APP || {};
  let availablePresets = [];

  function isoDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function setDefaultDates() {
    const today = new Date();
    const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
    elements.startDate.value = isoDate(firstDay);
    elements.endDate.value = isoDate(today);
  }

  function applyPreset(presetId) {
    if (presetId === "custom") return;
    const preset = availablePresets.find((item) => item.id === presetId);
    if (!preset) return;
    elements.startDate.value = preset.start_date;
    elements.endDate.value = preset.end_date;
  }

  async function loadConfiguration() {
    try {
      const [settingsResponse, presetsResponse] = await Promise.all([
        fetch("/api/settings"),
        fetch("/api/settings/presets")
      ]);
      if (!settingsResponse.ok || !presetsResponse.ok) return;
      applicationSettings = await settingsResponse.json();
      const presetData = await presetsResponse.json();
      availablePresets = presetData.presets || [];
      availablePresets.forEach((preset) => {
        const option = document.createElement("option");
        option.value = preset.id;
        option.textContent = preset.label;
        elements.datePreset.appendChild(option);
      });
      elements.destination.value = applicationSettings.default_destination;
      elements.insecure.checked = applicationSettings.default_insecure;
      if (applicationSettings.last_start_date && applicationSettings.last_end_date) {
        elements.startDate.value = applicationSettings.last_start_date;
        elements.endDate.value = applicationSettings.last_end_date;
        elements.datePreset.value = "custom";
      } else if (availablePresets.length) {
        elements.datePreset.value = "current_month";
        applyPreset("current_month");
      }
      refreshAuthStatus();
    } catch (_error) {
      return;
    }
  }

  function setBusy(isBusy, label) {
    elements.previewButton.disabled = isBusy;
    elements.downloadButton.disabled = isBusy;
    elements.loginButton.disabled = isBusy;
    elements.runState.className = `run-state ${isBusy ? "is-running" : "is-idle"}`;
    elements.runState.querySelector("span").textContent = label || "พร้อมทำงาน";
  }

  function setRunResult(ok, label) {
    elements.runState.className = `run-state ${ok ? "is-success" : "is-error"}`;
    elements.runState.querySelector("span").textContent = label;
  }

  function showError(message) {
    elements.formAlert.textContent = message;
    elements.formAlert.hidden = false;
    setRunResult(false, "ดำเนินการไม่สำเร็จ");
  }

  function clearError() {
    elements.formAlert.hidden = true;
    elements.formAlert.textContent = "";
  }

  function errorMessage(data, fallback) {
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail) && data.detail.length) return data.detail[0].msg;
    return fallback;
  }

  function payload() {
    const hcode = elements.hcode.value.trim();
    return {
      start_date: elements.startDate.value,
      end_date: elements.endDate.value,
      destination: elements.destination.value.trim(),
      overwrite: elements.overwrite.checked,
      insecure: elements.insecure.checked,
      hcode: hcode || null,
      page_size: Number(applicationSettings.default_page_size || 3000)
    };
  }

  function resultLabel(result) {
    const labels = {
      matched: "พร้อมดาวน์โหลด",
      downloaded: "ดาวน์โหลดแล้ว",
      exists: "มีอยู่แล้ว"
    };
    return labels[result] || result || "ไม่ทราบผล";
  }

  function renderStats(stats) {
    elements.matchedCount.textContent = stats.matched || 0;
    elements.downloadedCount.textContent = stats.downloaded || 0;
    elements.existsCount.textContent = stats.exists || 0;
    elements.failedCount.textContent = stats.failed || 0;
  }

  function renderResult(data) {
    const stats = data.stats || {};
    renderStats(stats);
    elements.resultTableBody.replaceChildren();

    const files = Array.isArray(data.files) ? data.files : [];
    elements.emptyState.hidden = files.length > 0;
    elements.resultTableWrap.hidden = files.length === 0;

    files.forEach((file, index) => {
      const row = document.createElement("tr");
      const result = file.result || "";
      const badgeClass = result === "downloaded" || result === "matched"
        ? "is-success"
        : result === "exists" ? "" : "is-error";

      [String(index + 1), file.source_name || "-", file.output_name || "-"].forEach((value) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.appendChild(cell);
      });

      const resultCell = document.createElement("td");
      const badge = document.createElement("span");
      badge.className = `result-badge ${badgeClass}`;
      badge.textContent = resultLabel(result);
      resultCell.appendChild(badge);
      row.appendChild(resultCell);
      elements.resultTableBody.appendChild(row);
    });
  }

  function clearResults() {
    renderResult({ stats: {}, files: [] });
    clearError();
    setRunResult(true, "พร้อมทำงาน");
    elements.jobProgress.hidden = true;
    elements.jobLogPanel.hidden = true;
    elements.jobLogList.replaceChildren();
  }

  function sleep(milliseconds) {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
  }

  function renderJobProgress(job) {
    const stats = job.progress || {};
    renderStats(stats);
    elements.jobProgress.hidden = false;
    const processed = (stats.downloaded || 0) + (stats.exists || 0) + (stats.failed || 0);
    const matched = stats.matched || 0;
    const percent = matched > 0 ? Math.min(100, Math.round((processed / matched) * 100)) : 0;
    const searching = job.status === "queued" || (job.status === "running" && matched === 0);
    elements.jobProgressLabel.textContent = job.status === "queued"
      ? "อยู่ในคิว"
      : searching ? "กำลังค้นหารายการ REP" : "กำลังดาวน์โหลดไฟล์";
    elements.jobProgressPercent.textContent = searching ? "..." : `${percent}%`;
    elements.jobProgressBar.style.width = searching ? "100%" : `${percent}%`;
    elements.jobProgressBar.classList.toggle("progress-bar-animated", searching || job.status === "running");
    elements.jobProgressBar.parentElement.setAttribute("aria-valuenow", String(percent));
  }

  async function refreshJobLogs(jobId) {
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/logs`);
    if (!response.ok) return;
    const data = await response.json();
    const logs = Array.isArray(data.logs) ? data.logs : [];
    elements.jobLogPanel.hidden = logs.length === 0;
    elements.jobLogList.replaceChildren();
    logs.slice(-100).forEach((entry) => {
      const item = document.createElement("li");
      item.className = `is-${entry.level || "info"}`;
      item.textContent = entry.message || "";
      elements.jobLogList.appendChild(item);
    });
  }

  async function pollJob(jobId) {
    while (true) {
      const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
      const job = await response.json();
      if (!response.ok) throw new Error(errorMessage(job, "ไม่พบสถานะงานดาวน์โหลด"));
      renderJobProgress(job);
      await refreshJobLogs(jobId);

      if (job.status === "completed" || job.status === "completed_with_errors") {
        renderResult(job.result || { stats: job.progress, files: [] });
        elements.jobProgressBar.style.width = "100%";
        elements.jobProgressPercent.textContent = "100%";
        setRunResult(job.status === "completed", job.status === "completed" ? "ดาวน์โหลดเสร็จแล้ว" : "เสร็จพร้อมข้อผิดพลาด");
        return;
      }
      if (job.status === "failed") {
        throw new Error(job.error?.message || "งานดาวน์โหลดไม่สำเร็จ");
      }
      await sleep(1000);
    }
  }

  async function requestDownload(endpoint, isPreview) {
    clearError();
    if (!elements.form.reportValidity()) return;
    if (elements.overwrite.checked && !isPreview) {
      const confirmed = window.confirm("ยืนยันการเขียนทับไฟล์ REP ที่มีอยู่แล้ว");
      if (!confirmed) return;
    }

    setBusy(true, isPreview ? "กำลังตรวจสอบรายการ" : "กำลังดาวน์โหลด");
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload())
      });
      const data = await response.json();
      if (!response.ok) throw new Error(errorMessage(data, "ไม่สามารถดำเนินการได้"));
      if (isPreview) {
        renderResult(data);
        const failed = data.stats?.failed || 0;
        setRunResult(failed === 0, "ตรวจสอบรายการแล้ว");
      } else {
        await pollJob(data.job_id);
      }
    } catch (error) {
      showError(error.message || "ไม่สามารถเชื่อมต่อระบบได้");
    } finally {
      elements.previewButton.disabled = false;
      elements.downloadButton.disabled = false;
      elements.loginButton.disabled = false;
    }
  }

  async function refreshAuthStatus() {
    elements.authIndicator.className = "status-dot is-checking";
    elements.authLabel.textContent = "กำลังตรวจสอบ SSO";
    const query = elements.insecure.checked ? "?insecure=true" : "";
    try {
      const response = await fetch(`/api/auth/status${query}`);
      const data = await response.json();
      if (!response.ok) throw new Error("auth status failed");
      const ready = data.status === "ready";
      elements.authIndicator.className = `status-dot ${ready ? "is-ready" : "is-error"}`;
      elements.authLabel.textContent = ready
        ? "SSO พร้อมใช้งาน"
        : data.status === "session_expired" ? "SSO หมดอายุ" : "ต้องเข้าสู่ระบบ";
      elements.authHcode.textContent = `รหัสหน่วยบริการ ${data.hcode || "-"}`;
    } catch (_error) {
      elements.authIndicator.className = "status-dot is-error";
      elements.authLabel.textContent = "ตรวจสอบ SSO ไม่สำเร็จ";
    }
  }

  async function loginSso() {
    clearError();
    setBusy(true, "รอการเข้าสู่ระบบ NHSO");
    try {
      const response = await fetch("/api/auth/login", { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(errorMessage(data, "เข้าสู่ระบบไม่สำเร็จ"));
      await refreshAuthStatus();
      setRunResult(true, "เข้าสู่ระบบแล้ว");
    } catch (error) {
      showError(error.message || "เข้าสู่ระบบไม่สำเร็จ");
    } finally {
      elements.previewButton.disabled = false;
      elements.downloadButton.disabled = false;
      elements.loginButton.disabled = false;
    }
  }

  elements.form.addEventListener("submit", (event) => {
    event.preventDefault();
    requestDownload("/api/downloads/preview", true);
  });
  elements.downloadButton.addEventListener("click", () => requestDownload("/api/downloads", false));
  elements.loginButton.addEventListener("click", loginSso);
  elements.clearButton.addEventListener("click", clearResults);
  elements.insecure.addEventListener("change", refreshAuthStatus);
  elements.datePreset.addEventListener("change", () => applyPreset(elements.datePreset.value));
  elements.startDate.addEventListener("change", () => { elements.datePreset.value = "custom"; });
  elements.endDate.addEventListener("change", () => { elements.datePreset.value = "custom"; });

  setDefaultDates();
  clearResults();
  loadConfiguration();
  refreshAuthStatus();
  if (window.lucide) window.lucide.createIcons();
})();

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
    failedCount: document.getElementById("failedCount")
  };

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
      hcode: hcode || null
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

  function renderResult(data) {
    const stats = data.stats || {};
    elements.matchedCount.textContent = stats.matched || 0;
    elements.downloadedCount.textContent = stats.downloaded || 0;
    elements.existsCount.textContent = stats.exists || 0;
    elements.failedCount.textContent = stats.failed || 0;
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
      renderResult(data);
      const failed = data.stats?.failed || 0;
      setRunResult(failed === 0, isPreview ? "ตรวจสอบรายการแล้ว" : "ดาวน์โหลดเสร็จแล้ว");
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

  setDefaultDates();
  clearResults();
  refreshAuthStatus();
  if (window.lucide) window.lucide.createIcons();
})();

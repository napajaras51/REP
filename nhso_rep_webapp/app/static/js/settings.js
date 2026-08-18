(function () {
  "use strict";

  const form = document.getElementById("settingsForm");
  const destination = document.getElementById("defaultDestination");
  const pageSize = document.getElementById("defaultPageSize");
  const insecure = document.getElementById("defaultInsecure");
  const alert = document.getElementById("settingsAlert");

  function showMessage(message, isError) {
    alert.textContent = message;
    alert.hidden = false;
    alert.classList.toggle("is-success", !isError);
  }

  async function loadSettings() {
    try {
      const response = await fetch("/api/settings");
      const data = await response.json();
      if (!response.ok) throw new Error("โหลดการตั้งค่าไม่สำเร็จ");
      destination.value = data.default_destination;
      pageSize.value = data.default_page_size;
      insecure.checked = data.default_insecure;
    } catch (error) {
      showMessage(error.message, true);
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    alert.hidden = true;
    try {
      const response = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          default_destination: destination.value.trim(),
          default_page_size: Number(pageSize.value),
          default_insecure: insecure.checked,
          last_start_date: null,
          last_end_date: null
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error?.message || data.detail || "บันทึกไม่สำเร็จ");
      showMessage("บันทึกการตั้งค่าแล้ว", false);
    } catch (error) {
      showMessage(error.message, true);
    }
  });

  loadSettings();
  if (window.lucide) window.lucide.createIcons();
})();

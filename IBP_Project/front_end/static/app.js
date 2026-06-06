document.addEventListener("DOMContentLoaded", () => {
  let selectedFile = null;
  let uploadedFileId = null;
  let uploadedFileName = null;
  let currentPolling = null;
  let currentJobId = null;
  let isCancelling = false;

  const fileInput = document.getElementById("fileInput");
  const btnUpload = document.getElementById("btnUpload");
  const btnCancel = document.getElementById("btnCancel");
  const datasetType = document.getElementById("datasetType");
  const datasetYear = document.getElementById("datasetYear");
  const progressBar = document.getElementById("progressBar");
  const progressText = document.getElementById("progressText");
  const previewArea = document.getElementById("previewArea");
  const fileBadge = document.getElementById("fileBadge");
  const statusMessage = document.getElementById("statusMessage");
  const alertArea = document.getElementById("alertArea");
  const dropZone = document.getElementById("dropZone");
  const previewCard = document.getElementById("previewCard");

  if (
    !fileInput || !btnUpload || !btnCancel || !datasetType || !datasetYear ||
    !progressBar || !progressText || !previewArea || !fileBadge ||
    !statusMessage || !alertArea || !dropZone
  ) {
    return;
  }

  function showAlert(message, type = "danger") {
    alertArea.innerHTML = `
      <div class="alert alert-${type} py-2" role="alert">
        ${message}
      </div>
    `;
  }

  function clearAlert() {
    alertArea.innerHTML = "";
  }

  function updateProgress(percent) {
    const safePercent = Math.max(0, Math.min(100, Number(percent) || 0));
    progressBar.style.width = `${safePercent}%`;
    progressBar.setAttribute("aria-valuenow", safePercent);
    progressText.innerText = `${safePercent}%`;
  }

  function setPreviewEmpty(isEmpty) {
    if (!previewCard) return;
    previewCard.classList.toggle("preview-empty", !!isEmpty);
  }

  function resetPreview() {
    previewArea.innerHTML = `
      <div class="text-secondary">
        Choose a file to automatically load and preview the first 20 rows.
      </div>
    `;
    setPreviewEmpty(true);
  }

  function resetAll() {
    selectedFile = null;
    uploadedFileId = null;
    uploadedFileName = null;
    currentJobId = null;
    isCancelling = false;

    fileInput.value = "";
    btnUpload.disabled = true;
    btnCancel.disabled = true;

    updateProgress(0);
    statusMessage.innerText = "";
    clearAlert();
    fileBadge.innerText = "No file";
    resetPreview();

    if (currentPolling) {
      clearInterval(currentPolling);
      currentPolling = null;
    }
  }

  async function uploadFileOnly(file) {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Upload failed.");
    }

    return data;
  }

  async function loadPreview(fileId) {
    const res = await fetch(`/api/preview?file_id=${fileId}&rows=20`);
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Could not load preview.");
    }

    if (!data.columns || !data.rows) {
      previewArea.innerHTML = `<div class="text-danger">Could not load preview.</div>`;
      setPreviewEmpty(true);
      return;
    }

    let html = `
      <div class="small text-secondary mb-2">
        Showing first <strong>${data.rows.length}</strong> row(s)
      </div>
      <div class="table-responsive">
        <table class="table table-sm table-bordered mb-0">
          <thead>
            <tr>
    `;

    data.columns.forEach((col) => {
      html += `<th>${col}</th>`;
    });

    html += `
            </tr>
          </thead>
          <tbody>
    `;

    data.rows.forEach((row) => {
      html += "<tr>";
      data.columns.forEach((col) => {
        const value = row[col] ?? "";
        html += `<td>${value}</td>`;
      });
      html += "</tr>";
    });

    html += `
          </tbody>
        </table>
      </div>
    `;

    previewArea.innerHTML = html;
    setPreviewEmpty(false);
  }

  async function prepareFileForPreview(file) {
    clearAlert();
    statusMessage.innerText = "Uploading file for preview...";
    btnUpload.disabled = true;
    btnCancel.disabled = false;
    updateProgress(5);

    const uploadData = await uploadFileOnly(file);

    uploadedFileId = uploadData.file_id;
    uploadedFileName = uploadData.original_name || file.name;
    fileBadge.innerText = uploadedFileName;

    updateProgress(10);
    statusMessage.innerText = "Loading preview...";

    await loadPreview(uploadedFileId);

    updateProgress(0);
    statusMessage.innerText = "Preview loaded. Click Upload to run the pipeline.";
    btnUpload.disabled = false;
    btnCancel.disabled = false;
  }

  async function runPipeline(fileId, datasetTypeValue, datasetYearValue) {
    const formData = new FormData();
    formData.append("file_id", fileId);
    formData.append("dataset_type", datasetTypeValue);
    formData.append("dataset_year", datasetYearValue);

    const res = await fetch("/api/run", {
      method: "POST",
      body: formData
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Could not start pipeline.");
    }

    statusMessage.innerText = data.message || "Pipeline started.";
    return data;
  }

  async function cancelPipeline() {
    if (!currentJobId) {
      resetAll();
      return;
    }

    try {
      isCancelling = true;
      statusMessage.innerText = "Cancel requested. Rolling back changes...";
      btnCancel.disabled = true;

      const res = await fetch(`/api/cancel/${currentJobId}`, {
        method: "POST"
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Could not cancel job.");
      }

      statusMessage.innerText = data.message || "Cancel requested.";
    } catch (err) {
      showAlert(err.message || "Cancel failed.");
      btnCancel.disabled = false;
      isCancelling = false;
    }
  }

  function pollJobStatus(jobId) {
    if (currentPolling) {
      clearInterval(currentPolling);
      currentPolling = null;
    }

    currentPolling = setInterval(async () => {
      try {
        const res = await fetch(`/api/status/${jobId}`);
        const data = await res.json();

        if (!res.ok) {
          throw new Error(data.detail || "Could not read job status.");
        }

        updateProgress(data.progress || 0);
        statusMessage.innerText = data.message || "Checking job status...";

        if (data.status === "completed") {
          clearInterval(currentPolling);
          currentPolling = null;
          currentJobId = null;
          isCancelling = false;

          updateProgress(100);
          statusMessage.innerText = "Upload completed and pipeline finished successfully.";

          setTimeout(() => {
            window.location.href = "/";
          }, 1500);
          return;
        }

        if (data.status === "warning") {
          clearInterval(currentPolling);
          currentPolling = null;
          currentJobId = null;
          isCancelling = false;

          updateProgress(data.progress || 100);
          statusMessage.innerText =
            (data.message || "Completed with warning.") +
            (data.powerbi_refresh_msg ? ` ${data.powerbi_refresh_msg}` : "");

          btnUpload.disabled = false;
          btnCancel.disabled = false;
          return;
        }

        if (data.status === "cancelled") {
          clearInterval(currentPolling);
          currentPolling = null;
          currentJobId = null;
          isCancelling = false;

          updateProgress(0);
          statusMessage.innerText = data.message || "Upload cancelled and rolled back.";

          setTimeout(() => {
            window.location.href = "/upload";
          }, 1200);

          return;
        }

        if (data.status === "failed") {
          clearInterval(currentPolling);
          currentPolling = null;
          currentJobId = null;
          isCancelling = false;

          updateProgress(0);
          statusMessage.innerText = data.message || "Upload failed.";
          showAlert(data.message || "Upload failed.");

          setTimeout(() => {
            window.location.href = "/upload";
          }, 1500);

          return;
        }
      } catch (err) {
        clearInterval(currentPolling);
        currentPolling = null;
        currentJobId = null;
        isCancelling = false;

        updateProgress(0);
        statusMessage.innerText = "Could not read pipeline status.";
        showAlert(err.message || "Status polling failed.");
        btnUpload.disabled = false;
        btnCancel.disabled = false;
      }
    }, 1000);
  }

  async function startPipeline() {
    if (!selectedFile || !uploadedFileId) {
      showAlert("Please choose a file first.");
      return;
    }

    clearAlert();
    btnUpload.disabled = true;
    btnCancel.disabled = false;
    isCancelling = false;
    updateProgress(0);
    statusMessage.innerText = "Starting pipeline...";

    try {
      const runData = await runPipeline(
        uploadedFileId,
        datasetType.value,
        datasetYear.value
      );

      if (!runData.job_id) {
        throw new Error("No job ID returned from pipeline.");
      }

      currentJobId = runData.job_id;
      pollJobStatus(currentJobId);
    } catch (err) {
      showAlert(err.message || "Could not start pipeline.");
      statusMessage.innerText = "";
      btnUpload.disabled = false;
      btnCancel.disabled = false;
      updateProgress(0);
    }
  }

  async function handleSelectedFile(file) {
    selectedFile = file || null;

    if (!selectedFile) {
      resetAll();
      return;
    }

    fileBadge.innerText = selectedFile.name;
    clearAlert();

    previewArea.innerHTML = `
      <div class="text-secondary">
        Preparing preview for <strong>${selectedFile.name}</strong>...
      </div>
    `;
    setPreviewEmpty(false);

    try {
      await prepareFileForPreview(selectedFile);
    } catch (err) {
      showAlert(err.message || "Could not prepare preview.");
      statusMessage.innerText = "";
      btnUpload.disabled = true;
      btnCancel.disabled = false;
      updateProgress(0);
      uploadedFileId = null;
    }
  }

  fileInput.addEventListener("change", async (e) => {
    const file = e.target.files[0] || null;
    await handleSelectedFile(file);
  });

  btnUpload.addEventListener("click", async () => {
    await startPipeline();
  });

  btnCancel.addEventListener("click", async () => {
    if (currentJobId && !isCancelling) {
      await cancelPipeline();
    } else if (!currentJobId) {
      resetAll();
    }
  });

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });

  dropZone.addEventListener("drop", async (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");

    const file = e.dataTransfer.files[0] || null;
    if (file) {
      await handleSelectedFile(file);
    }
  });

  resetPreview();
});
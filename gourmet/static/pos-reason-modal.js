(function () {
  "use strict";

  function csrfFromCookie() {
    var match = document.cookie.match(/(^| )csrftoken=([^;]+)/);
    return match ? match[2] : "";
  }

  function refreshBoard() {
    if (window.htmx) {
      window.htmx.ajax("GET", window.location.pathname, {
        target: "#to-serve-board",
        select: "#to-serve-board",
      });
    }
  }

  var modal = null;
  var textarea = null;
  var currentUrl = "";

  function closeModal() {
    if (modal) modal.style.display = "none";
  }

  function openModal(url) {
    currentUrl = url;
    if (textarea) textarea.value = "";
    if (modal) modal.style.display = "flex";
  }

  function confirmCancel() {
    var reason = textarea ? textarea.value.trim() : "";
    if (!reason) {
      alert("Debes indicar un motivo");
      return;
    }
    var formData = new FormData();
    formData.append("reason", reason);
    fetch(currentUrl, {
      method: "POST",
      body: formData,
      headers: { "X-CSRFToken": csrfFromCookie() },
      credentials: "same-origin",
    })
      .then(function () {
        closeModal();
        refreshBoard();
      })
      .catch(function () {
        alert("No se pudo cancelar el item");
      });
  }

  function cancelPending(url) {
    if (!window.confirm("¿Cancelar este item pendiente?")) return;
    fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfFromCookie(),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({}),
      credentials: "same-origin",
    })
      .then(function () {
        refreshBoard();
      })
      .catch(function () {
        alert("No se pudo cancelar el item");
      });
  }

  document.addEventListener("click", function (event) {
    var readyBtn = event.target.closest(".js-cancel-ready");
    if (readyBtn) {
      openModal(readyBtn.dataset.url);
      return;
    }
    var pendingBtn = event.target.closest(".js-cancel-pending");
    if (pendingBtn) {
      cancelPending(pendingBtn.dataset.url);
      return;
    }
    if (event.target.closest(".js-reason-close")) {
      closeModal();
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    modal = document.getElementById("reason-modal");
    textarea = document.getElementById("reason-text");
    var confirmBtn = document.getElementById("reason-confirm");
    if (confirmBtn) confirmBtn.addEventListener("click", confirmCancel);
  });
})();

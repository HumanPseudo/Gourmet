(function () {
  "use strict";

  function money(value) {
    return new Intl.NumberFormat("es-CO", {
      style: "currency",
      currency: "COP",
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(value || 0);
  }

  function replaceRegion(html) {
    var wrapper = document.createElement("div");
    wrapper.innerHTML = html;
    var ids = ["cart-summary", "order-status-box"];
    for (var i = 0; i < ids.length; i++) {
      var fresh = wrapper.querySelector("#" + ids[i]);
      if (!fresh) continue;
      var old = document.getElementById(ids[i]);
      if (old) {
        old.replaceWith(fresh);
        if (window.htmx) window.htmx.process(fresh);
        if (window.Alpine && window.Alpine.initTree) {
          window.Alpine.initTree(fresh);
        }
      }
      return true;
    }
    return false;
  }

  function initProductModal(root) {
    if (!root || root.dataset.initialized === "1") return;
    root.dataset.initialized = "1";

    var config = {};
    try {
      var configElement = document.getElementById(root.dataset.configId);
      if (configElement) config = JSON.parse(configElement.textContent);
    } catch (error) {
      config = {};
    }

    var groups = config.groups || [];
    var conditions = config.conditions || [];
    var basePrice = parseFloat(config.base_price || "0");
    var submitUrl = config.submit_url || config.add_url;
    var itemId = config.item_id || "";

    var selected = {};

    groups.forEach(function (group) {
      selected[group.id] = [];
    });

    var priceMap = {};
    root.querySelectorAll(".option-input").forEach(function (input) {
      priceMap[input.dataset.valueId] = parseFloat(input.dataset.price || "0");
    });

    var quantityInput = root.querySelector(".product-qty");
    var unitPriceElement = root.querySelector(".product-unit-price");
    var totalElement = root.querySelector(".product-total-price");
    var submitButton = root.querySelector(".product-submit");

    function groupVisible(groupId, depth) {
      depth = depth || 0;
      if (depth > 10) return false;

      var condition = conditions.find(function (item) {
        return item.group === groupId;
      });

      if (!condition) return true;
      if (!groupVisible(condition.parent, depth + 1)) return false;

      var parentSelected = selected[condition.parent] || [];
      return condition.values.some(function (valueId) {
        return parentSelected.includes(valueId);
      });
    }

    function readSelected() {
      groups.forEach(function (group) {
        selected[group.id] = [];
      });
      root
        .querySelectorAll(".option-input:checked:not(:disabled)")
        .forEach(function (input) {
          var groupId = input.dataset.groupId;
          if (!selected[groupId]) selected[groupId] = [];
          selected[groupId].push(input.dataset.valueId);
        });
    }

    function refreshVisibility() {
      readSelected();
      groups.forEach(function (group) {
        var visible = groupVisible(group.id);
        var container = root.querySelector('[data-group-container="' + group.id + '"]');
        if (container) container.style.display = visible ? "" : "none";
        root
          .querySelectorAll('.option-input[data-group-id="' + group.id + '"]')
          .forEach(function (input) {
            input.disabled = !visible;
            if (!visible && input.checked) input.checked = false;
          });
        if (!visible) selected[group.id] = [];
      });
    }

    function canSubmit() {
      if (config.orderable === false || !submitUrl) return false;
      var quantity = parseInt(quantityInput.value || "1", 10);
      if (isNaN(quantity) || quantity < 1) return false;

      return groups.every(function (group) {
        if (!groupVisible(group.id) || !group.required) return true;
        return (selected[group.id] || []).length >= group.min;
      });
    }

    function recalculate() {
      readSelected();
      var delta = 0;

      Object.keys(selected).forEach(function (groupId) {
        selected[groupId].forEach(function (valueId) {
          delta += priceMap[valueId] || 0;
        });
      });

      var quantity = parseInt(quantityInput.value || "1", 10);
      if (isNaN(quantity) || quantity < 1) quantity = 1;

      var unitPrice = basePrice + delta;

      if (unitPriceElement) unitPriceElement.textContent = money(unitPrice);
      if (totalElement) totalElement.textContent = money(unitPrice * quantity);
      if (submitButton) submitButton.disabled = !canSubmit();
    }

    function closeModal() {
      document.removeEventListener("keydown", onKeydown);
      root.remove();
    }

    function onKeydown(event) {
      if (event.key === "Escape") closeModal();
    }

    root.addEventListener("change", function (event) {
      if (!event.target.classList.contains("option-input")) return;

      var groupId = event.target.dataset.groupId;
      var group = groups.find(function (item) {
        return item.id === groupId;
      });

      if (
        event.target.type === "checkbox" &&
        event.target.checked &&
        group &&
        group.multiple
      ) {
        var checkedCount = root.querySelectorAll(
          '.option-input:checked:not(:disabled)[data-group-id="' + groupId + '"]',
        ).length;
        if (checkedCount > group.max) event.target.checked = false;
      }

      refreshVisibility();
      recalculate();
    });

    if (quantityInput) quantityInput.addEventListener("input", recalculate);

    root.querySelectorAll(".product-modal-close").forEach(function (button) {
      button.addEventListener("click", closeModal);
    });

    var backdrop = root.querySelector(".product-modal-backdrop");
    if (backdrop) {
      backdrop.addEventListener("click", function (event) {
        if (event.target === backdrop) closeModal();
      });
    }

    if (submitButton) {
      submitButton.addEventListener("click", function (event) {
        event.preventDefault();
        if (submitButton.disabled) return;

        var formData = new FormData();
        formData.append("product_id", config.product_id);
        formData.append("quantity", quantityInput.value || "1");
        if (itemId) formData.append("item_id", itemId);
        Object.keys(selected).forEach(function (groupId) {
          selected[groupId].forEach(function (valueId) {
            formData.append("option_values", valueId);
          });
        });

        var csrfInput = root.querySelector("input[name=csrfmiddlewaretoken]");
        var headers = {};
        if (csrfInput) headers["X-CSRFToken"] = csrfInput.value;

        fetch(submitUrl, {
          method: "POST",
          headers: headers,
          body: formData,
          credentials: "same-origin",
        })
          .then(function (response) {
            if (!response.ok) throw new Error("Respuesta " + response.status);
            return response.text();
          })
          .then(function (html) {
            replaceRegion(html);
            closeModal();
          })
          .catch(function () {
            alert("No se pudo completar la operación.");
          });
      });
    }

    document.addEventListener("keydown", onKeydown);
    refreshVisibility();
    recalculate();
  }

  document.addEventListener("htmx:afterSwap", function (event) {
    var target = event.detail && event.detail.target;
    if (!target || target.id !== "product-modal-container") return;

    var modalRoot = target.querySelector(".product-modal-root");
    if (modalRoot) initProductModal(modalRoot);
  });
})();

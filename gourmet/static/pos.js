/* POS build 2026-11-14 · modales imperativos (cierran siempre) */
console.info("[pos] build 2026-11-14-modal-fix");

const FLOOR_TABLE_BOX = 56;
const FLOOR_STATUS_COLOR = {
  available: "#2ea043",
  occupied: "#f85149",
  reserved: "#2f81f7",
  cleaning: "#6e7681",
  out_of_service: "#6e7681",
};
const EMPTY_BILL = {
  table_id: "",
  table_code: "",
  orders: [],
  total: "0",
  paid: "0",
  remaining: "0",
};

/* ── Controlador global de modales (independiente de Alpine) ── */
function posOpenModal(id) {
  const m = document.getElementById(id);
  if (!m) return;
  m.hidden = false;
  document.body.style.overflow = "hidden";
}
function posCloseModal(id) {
  const m = document.getElementById(id);
  if (!m) return;
  m.hidden = true;
  if (!document.querySelector(".p-modal:not([hidden])")) {
    document.body.style.overflow = "";
  }
}
function posCloseAllModals() {
  document.querySelectorAll(".p-modal").forEach((m) => (m.hidden = true));
  document.body.style.overflow = "";
}
window.posOpenModal = posOpenModal;
window.posCloseModal = posCloseModal;
window.posCloseAllModals = posCloseAllModals;

document.addEventListener("click", (e) => {
  const opener = e.target.closest("[data-modal-open]");
  if (opener) {
    posOpenModal(opener.getAttribute("data-modal-open"));
    return;
  }
  const closer = e.target.closest("[data-modal-close]");
  if (closer) {
    const m = closer.closest(".p-modal");
    if (m) posCloseModal(m.id);
    else posCloseAllModals();
    return;
  }
  if (e.target.classList && e.target.classList.contains("p-modal")) {
    posCloseModal(e.target.id);
  }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") posCloseAllModals();
});

document.addEventListener("alpine:init", () => {
  Alpine.data("posApp", () => ({
    categories: [],
    products: [],
    activeCat: "",
    search: "",
    cart: [],
    tableId: "",
    orderId: null,
    tableBill: { ...EMPTY_BILL },
    billLoading: false,
    billNotice: "",
    billError: "",
    moveOrderId: null,
    payOrderId: null,
    customerName: "",
    payMethod: "cash",
    payAmount: 0,
    payError: "",
    totalPaid: 0,
    createOrderError: "",
    closed: false,
    tipAmount: 0,
    outOfStock: [],
    lowStock: [],
    loadError: "",
    floorLayout: null,
    floorItems: [],
    floorUnplaced: [],
    noTableOrders: [],
    optState: null,
    serveItems: [],
    serveError: "",
    methods: [
      { value: "cash", label: "\u{1F4B5} Efectivo", color: "#2ea043" },
      { value: "card", label: "\u{1F4B3} Tarjeta", color: "#2f81f7" },
      { value: "transfer", label: "\u{1F3E6} Transf.", color: "#a371f7" },
    ],
    taxLabels: {
      INC_8: "INC 8%",
      IVA_19: "IVA 19%",
      IVA_5: "IVA 5%",
      EXENTO: "Exento",
    },
    taxRates: { INC_8: 0.08, IVA_19: 0.19, IVA_5: 0.05, EXENTO: 0.0 },
    get csrf() {
      return document.querySelector("meta[name=csrf-token]")?.content || "";
    },
    async init() {
      try {
        const meta = document.querySelector("meta[name=out-of-stock]");
        if (meta) this.outOfStock = JSON.parse(meta.content);
        const ls = document.querySelector("meta[name=low-stock]");
        if (ls) this.lowStock = JSON.parse(ls.content);
        const [cats, prods] = await Promise.all([
          fetch("/api/menu/categories").then((r) => {
            if (!r.ok) throw new Error("categories: " + r.status);
            return r.json();
          }),
          fetch("/api/menu/products").then((r) => {
            if (!r.ok) throw new Error("products: " + r.status);
            return r.json();
          }),
        ]);
        this.categories = cats.items || cats || [];
        this.products = (prods.items || prods || []).filter((p) => p.is_available);
        await this.refreshFloor();
        await this.restoreState();
      } catch (e) {
        this.loadError = "Error al cargar datos: " + e.message;
      }
      setInterval(() => this.refreshFloor(), 30000);
      setInterval(() => {
        if (this.tableId && !this.optState) this.loadTableBill(true);
      }, 12000);
    },
    persistState() {
      try {
        sessionStorage.setItem("pos_table_id", this.tableId || "");
        sessionStorage.setItem("pos_order_id", this.orderId || "");
      } catch (_) {}
    },
    async restoreState() {
      let savedOrder = "";
      let savedTable = "";
      try {
        savedOrder = sessionStorage.getItem("pos_order_id") || "";
        savedTable = sessionStorage.getItem("pos_table_id") || "";
      } catch (_) {}
      if (!savedTable) return;
      const all = this.floorItems.concat(this.floorUnplaced);
      if (!all.some((t) => t.table_id === savedTable)) return;
      this.tableId = savedTable;
      await this.loadTableBill();
      if (savedOrder && this.billOrders.some((o) => o.id === savedOrder)) {
        this.orderId = savedOrder;
      }
      this.persistState();
    },
    get billOrders() {
      return this.tableBill.orders || [];
    },
    get billTotal() {
      return parseFloat(this.tableBill.total || 0);
    },
    get billPaid() {
      return parseFloat(this.tableBill.paid || 0);
    },
    get billRemaining() {
      return parseFloat(this.tableBill.remaining || 0);
    },
    get billPaidPct() {
      const t = this.billTotal;
      return t > 0 ? Math.min(100, (this.billPaid / t) * 100) : 0;
    },
    get billSettled() {
      return this.billTotal > 0 && this.billRemaining <= 0.005;
    },
    get targetOrder() {
      return (
        this.billOrders.find((o) => o.id === this.orderId) ||
        this.billOrders[this.billOrders.length - 1] ||
        null
      );
    },
    get moveTargets() {
      return this.floorItems
        .concat(this.floorUnplaced)
        .filter((t) => t.table_id !== this.tableId)
        .sort((a, b) => a.code.localeCompare(b.code));
    },
    orderRemaining(o) {
      return parseFloat(o.remaining || 0);
    },
    orderPaid(o) {
      return parseFloat(o.paid || 0);
    },
    orderTotal(o) {
      return parseFloat(o.total || 0);
    },
    orderPaidPct(o) {
      const t = this.orderTotal(o);
      return t > 0 ? Math.min(100, (this.orderPaid(o) / t) * 100) : 0;
    },
    orderSettled(o) {
      return this.orderTotal(o) > 0 && this.orderRemaining(o) <= 0.005;
    },
    setTarget(orderId) {
      this.orderId = orderId;
      this.persistState();
    },
    async loadTableBill(silent) {
      if (!this.tableId) {
        this.tableBill = { ...EMPTY_BILL };
        this.orderId = null;
        return;
      }
      if (!silent) this.billLoading = true;
      try {
        const r = await fetch("/pos/table-bill/" + this.tableId + "/");
        if (!r.ok) throw new Error("HTTP " + r.status);
        const data = await r.json();
        this.tableBill = data;
        if (this.orderId && !data.orders.some((o) => o.id === this.orderId)) {
          this.orderId = null;
        }
        this.totalPaid = parseFloat(data.paid || 0);
        this.closed = data.orders.length === 0;
        this.billError = "";
      } catch (e) {
        if (!silent) this.billError = "No se pudo cargar la cuenta: " + e.message;
      } finally {
        this.billLoading = false;
      }
    },
    statusLabel(s) {
      return (
        {
          pending: "Recibido",
          preparing: "Preparando",
          ready: "Listo",
          served: "Entregado",
          cancelled: "Cancelado",
        }[s] || s
      );
    },
    statusColor(s) {
      return (
        {
          pending: "#6e7681",
          preparing: "#d29922",
          ready: "#2ea043",
          served: "#2f81f7",
          cancelled: "#f85149",
        }[s] || "#6e7681"
      );
    },
    sourceLabel(s) {
      return s === "qr" ? "QR" : "POS";
    },
    sourceColor(s) {
      return s === "qr" ? "#2f81f7" : "#2ea043";
    },
    async openServe() {
      window.posOpenModal("serve-modal");
      await this.refreshServe();
    },
    closeServe() {
      window.posCloseModal("serve-modal");
    },
    async refreshServe() {
      this.serveError = "";
      try {
        const r = await fetch("/pos/serve-list/");
        if (!r.ok) throw new Error("HTTP " + r.status);
        const data = await r.json();
        this.serveItems = data.items || [];
      } catch (e) {
        this.serveError = "Error al cargar: " + e.message;
      }
    },
    async serveItem(si) {
      const res = await fetch(
        "/pos/orders/" + si.order_id + "/items/" + si.id + "/status/",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": this.csrf,
          },
          body: JSON.stringify({ status: "served" }),
        },
      );
      if (!res.ok) {
        alert("No se pudo entregar el item.");
        return;
      }
      await this.refreshServe();
      await this.loadTableBill(true);
      await this.refreshFloor();
    },
    async cancelServeItem(si) {
      const payload = { status: "cancelled" };
      if (si.status === "ready") {
        const reason = prompt("Motivo de cancelación (obligatorio):");
        if (!reason || !reason.trim()) return;
        payload.reason = reason.trim();
      } else if (!confirm("¿Cancelar este item pendiente?")) {
        return;
      }
      const res = await fetch(
        "/pos/orders/" + si.order_id + "/items/" + si.id + "/status/",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": this.csrf,
          },
          body: JSON.stringify(payload),
        },
      );
      if (!res.ok) {
        alert("No se pudo cancelar el item.");
        return;
      }
      await this.refreshServe();
      await this.loadTableBill(true);
    },
    get currentTableCode() {
      const all = this.floorItems.concat(this.floorUnplaced);
      const t = all.find((x) => x.table_id === this.tableId);
      return t ? t.code : "Ninguna";
    },
    floorItemStyle(t) {
      const radius = t.shape === "round" ? "50%" : "10px";
      const rotation = t.rotation || 0;
      return (
        "position:absolute;left:" +
        t.pos_x +
        "px;top:" +
        t.pos_y +
        "px;" +
        "width:" +
        FLOOR_TABLE_BOX +
        "px;height:" +
        FLOOR_TABLE_BOX +
        "px;" +
        "display:flex;flex-direction:column;align-items:center;" +
        "justify-content:center;cursor:pointer;border-radius:" +
        radius +
        ";" +
        "transform:rotate(" +
        rotation +
        "deg);color:#fff;font-weight:700;" +
        "font-size:12px;user-select:none;transition:transform .15s ease;" +
        "box-shadow:0 2px 8px rgba(0,0,0,.35);background:" +
        (FLOOR_STATUS_COLOR[t.status] || "#6e7681") +
        ";" +
        (t.table_id === this.tableId
          ? "outline:3px solid #e6edf3;outline-offset:2px;"
          : "")
      );
    },
    floorButtonStyle(t) {
      const bg =
        t.table_id === this.tableId
          ? "#e6edf3"
          : FLOOR_STATUS_COLOR[t.status] || "#6e7681";
      const fg = t.table_id === this.tableId ? "#0d1117" : "#fff";
      return (
        "padding:10px 14px;border:none;border-radius:10px;color:" +
        fg +
        ";" +
        "font-weight:700;font-size:13px;cursor:pointer;background:" +
        bg +
        ";"
      );
    },
    floorBoardStyle() {
      if (!this.floorLayout) return "";
      return (
        "position:relative;width:" +
        this.floorLayout.width +
        "px;height:" +
        this.floorLayout.height +
        "px;background:#0d1117;" +
        "border:1px solid #2a323b;border-radius:12px;max-width:100%;overflow:auto;"
      );
    },
    async refreshFloor() {
      try {
        const r = await fetch("/pos/floor-status/");
        if (!r.ok) return;
        const data = await r.json();
        this.floorLayout = data.layout;
        this.floorItems = data.items || [];
        this.floorUnplaced = data.unplaced || [];
        this.noTableOrders = data.no_table_orders || [];
      } catch (_) {}
    },
    async selectNoTableOrder(o) {
      const res = await fetch("/pos/order-json/" + o.order_id + "/");
      if (!res.ok) return;
      const data = await res.json();
      this.tableId = data.table_id || "";
      this.orderId = o.order_id;
      await this.loadTableBill();
      this.persistState();
      window.posCloseModal("floor-modal");
    },
    async selectTable(t) {
      if (
        this.cart.length &&
        !confirm(
          "Tienes " +
            this.cart.length +
            " producto(s) sin enviar.\n" +
            "Cambiar de mesa los descartará. ¿Continuar?",
        )
      ) {
        return;
      }
      this.cart = [];
      this.billNotice = "";
      this.tableId = t.table_id;
      this.orderId = null;
      await this.loadTableBill();
      this.persistState();
      window.posCloseModal("floor-modal");
    },
    openMove(orderId) {
      this.moveOrderId = orderId;
      window.posOpenModal("move-modal");
    },
    closeMove() {
      this.moveOrderId = null;
      window.posCloseModal("move-modal");
    },
    async confirmMove(targetTableId) {
      if (!this.moveOrderId) return;
      const res = await fetch("/pos/set-table/" + this.moveOrderId + "/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": this.csrf,
        },
        body: JSON.stringify({ table_id: targetTableId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.error || "No se pudo mover la orden.");
        return;
      }
      this.closeMove();
      this.billNotice = "Orden reasignada a la mesa destino.";
      await this.loadTableBill();
      await this.refreshFloor();
    },
    async removeOrderItem(orderId, itemId) {
      if (!confirm("¿Quitar este item de la orden?")) return;
      const res = await fetch("/pos/remove-item/" + orderId + "/" + itemId + "/", {
        method: "POST",
        headers: { "X-CSRFToken": this.csrf },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.error || "No se pudo quitar el item.");
        return;
      }
      await this.loadTableBill();
      await this.refreshFloor();
    },
    async refreshOrder() {
      await this.loadTableBill();
    },
    _applyOrder(data) {
      if (data.table_id) this.tableId = data.table_id;
      if (data.id) this.orderId = data.id;
      this.customerName = data.customer_name || this.customerName;
      this.persistState();
    },
    get stockClass() {
      return (id) => (this.outOfStock.includes(id) ? "out-of-stock" : "");
    },
    get filteredProducts() {
      let p = this.products;
      if (this.search) {
        const q = this.search.toLowerCase();
        p = p.filter((x) => x.name.toLowerCase().includes(q));
      }
      if (this.activeCat) p = p.filter((x) => x.category_id === this.activeCat);
      return p;
    },
    _lineTotal(item) {
      return item.price * item.qty;
    },
    _formatPeso(n) {
      const parts = Number(n || 0)
        .toFixed(2)
        .split(".");
      parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
      return "$ " + parts.join(",");
    },
    itemUnitPrice(i) {
      return parseFloat(i.price || 0);
    },
    itemLineTotal(i) {
      return parseFloat(i.price || 0) * (i.quantity || 0);
    },
    get subtotal() {
      return this.cart.reduce((s, i) => s + this._lineTotal(i), 0);
    },
    get taxBreakdown() {
      const map = {};
      for (const item of this.cart) {
        const label = this.taxLabels[item.tax_type] || item.tax_type;
        const rate = this.taxRates[item.tax_type] || 0;
        map[label] = (map[label] || 0) + this._lineTotal(item) * rate;
      }
      return map;
    },
    get total() {
      let t = this.subtotal;
      for (const item of this.cart) {
        t += this._lineTotal(item) * (this.taxRates[item.tax_type] || 0);
      }
      return t;
    },
    get remaining() {
      return this.cart.length > 0 ? this.total : this.billRemaining;
    },
    _pushCartLine(p, qty, unitPrice, optionIds, selectedOptions, label) {
      const key = p.id + ":" + (optionIds || []).join(",");
      const existing = this.cart.find((i) => i.line_key === key);
      if (existing) {
        existing.qty = Math.min(99, existing.qty + qty);
        return;
      }
      this.cart.push({
        line_key: key,
        id: p.id,
        name: label ? p.name + " (" + label + ")" : p.name,
        price: unitPrice != null ? unitPrice : parseFloat(p.price),
        unit_price: unitPrice,
        option_value_ids: optionIds || [],
        selected_options: selectedOptions || [],
        tax_type: p.tax_type,
        qty: qty,
      });
    },
    addItem(p) {
      if (p.has_options) {
        this.openOptionModal(p);
        return;
      }
      this._pushCartLine(p, 1, null, [], [], "");
    },
    changeQty(idx, delta) {
      const item = this.cart[idx];
      if (!item) return;
      item.qty = Math.max(1, item.qty + delta);
    },
    removeItem(idx) {
      this.cart.splice(idx, 1);
    },
    async openOptionModal(p) {
      this.closeOptionModal();
      let cfg;
      try {
        const r = await fetch("/pos/product-options/" + p.id + "/");
        if (!r.ok) throw new Error("HTTP " + r.status);
        cfg = await r.json();
      } catch (e) {
        alert("No se pudieron cargar las opciones: " + e.message);
        return;
      }
      const st = {
        product: p,
        groups: cfg.groups || [],
        conditions: cfg.conditions || [],
        selected: {},
        qty: 1,
        el: null,
        keydown: null,
      };
      st.groups.forEach((g) => {
        st.selected[g.id] = [];
      });
      this.optState = st;
      this.buildOptionModal(st);
    },
    optGroupVisible(st, groupId, depth) {
      depth = depth || 0;
      if (depth > 10) return false;
      const cond = st.conditions.find((c) => c.group === groupId);
      if (!cond) return true;
      if (!this.optGroupVisible(st, cond.parent, depth + 1)) return false;
      const parentSelected = st.selected[cond.parent] || [];
      return cond.values.some((vid) => parentSelected.includes(vid));
    },
    optToggle(st, groupId, valueId) {
      const group = st.groups.find((g) => g.id === groupId);
      if (!group) return;
      const arr = st.selected[groupId] || [];
      const idx = arr.indexOf(valueId);
      if (group.multiple) {
        if (idx >= 0) arr.splice(idx, 1);
        else if (arr.length < group.max) arr.push(valueId);
      } else {
        st.selected[groupId] = idx >= 0 ? [] : [valueId];
      }
      st.groups.forEach((g) => {
        if (!this.optGroupVisible(st, g.id)) st.selected[g.id] = [];
      });
    },
    optUnitPriceOf(st) {
      let delta = 0;
      for (const g of st.groups) {
        for (const vid of st.selected[g.id] || []) {
          const v = (g.values || []).find((x) => x.id === vid);
          if (v) delta += parseFloat(v.price_delta || 0);
        }
      }
      return parseFloat(st.product.price) + delta;
    },
    optCanSubmitOf(st) {
      for (const g of st.groups) {
        if (!this.optGroupVisible(st, g.id)) continue;
        const count = (st.selected[g.id] || []).length;
        if (g.required && count < g.min) return false;
        if (count > g.max) return false;
      }
      return st.qty >= 1;
    },
    syncOptionModal(st) {
      const el = st.el;
      if (!el) return;
      for (const g of st.groups) {
        const gc = el.querySelector('[data-gid="' + g.id + '"]');
        if (!gc) continue;
        const visible = this.optGroupVisible(st, g.id);
        gc.style.display = visible ? "" : "none";
        gc.querySelectorAll("input").forEach((input) => {
          input.disabled = !visible;
          input.checked = (st.selected[g.id] || []).includes(input.dataset.vid);
        });
      }
      const unit = el.querySelector("[data-role=opt-unit]");
      const total = el.querySelector("[data-role=opt-total]");
      const hint = el.querySelector("[data-role=opt-hint]");
      const confirmBtn = el.querySelector("[data-role=opt-confirm]");
      const qtyInput = el.querySelector("[data-role=opt-qty]");
      if (qtyInput && document.activeElement !== qtyInput) qtyInput.value = st.qty;
      const unitPrice = this.optUnitPriceOf(st);
      if (unit) unit.textContent = this._formatPeso(unitPrice);
      if (total) total.textContent = this._formatPeso(unitPrice * st.qty);
      const ok = this.optCanSubmitOf(st);
      if (confirmBtn) confirmBtn.disabled = !ok;
      if (hint) hint.style.display = ok ? "none" : "";
    },
    confirmOptions(st) {
      if (!this.optCanSubmitOf(st)) return;
      const selected = [];
      for (const g of st.groups) {
        if (!this.optGroupVisible(st, g.id)) continue;
        for (const vid of st.selected[g.id] || []) {
          const v = (g.values || []).find((x) => x.id === vid);
          if (v)
            selected.push({
              group_id: g.id,
              group_name: g.name,
              value_id: v.id,
              value_name: v.name,
              price_delta: v.price_delta,
            });
        }
      }
      const delta = selected.reduce((s, o) => s + (parseFloat(o.price_delta) || 0), 0);
      const unit = parseFloat(st.product.price) + delta;
      const label = selected.map((o) => o.value_name).join(", ");
      const ids = selected.map((o) => o.value_id).sort();
      this._pushCartLine(st.product, st.qty, unit, ids, selected, label);
    },
    buildOptionModal(st) {
      const wrap = document.createElement("div");
      wrap.id = "pos-option-modal";
      wrap.className = "p-modal";
      wrap.style.cssText =
        "position:fixed;inset:0;background:rgba(1,4,9,.72);z-index:2000;" +
        "display:flex;align-items:center;justify-content:center;padding:16px;";
      const box = document.createElement("div");
      box.style.cssText =
        "background:#161b22;border:1px solid #2a323b;border-radius:14px;" +
        "width:100%;max-width:600px;max-height:88vh;display:flex;" +
        "flex-direction:column;overflow:hidden;color:#e6edf3;" +
        "box-shadow:0 24px 60px rgba(0,0,0,.6);";
      const header = document.createElement("div");
      header.style.cssText =
        "padding:14px 18px;border-bottom:1px solid #2a323b;display:flex;" +
        "justify-content:space-between;align-items:center;background:#1b2127;";
      const h3 = document.createElement("h3");
      h3.style.cssText = "margin:0;font-size:16px;font-weight:700;";
      h3.textContent = st.product.name;
      const closeBtn = document.createElement("button");
      closeBtn.type = "button";
      closeBtn.textContent = "\u2715";
      closeBtn.style.cssText =
        "background:none;border:none;font-size:20px;cursor:pointer;color:#8b949e;";
      closeBtn.addEventListener("click", () => this.closeOptionModal());
      header.appendChild(h3);
      header.appendChild(closeBtn);
      const body = document.createElement("div");
      body.className = "gscroll";
      body.style.cssText = "padding:18px;overflow-y:auto;flex:1;";
      for (const g of st.groups) {
        const gc = document.createElement("div");
        gc.dataset.gid = g.id;
        gc.style.cssText = "margin-bottom:16px;";
        const title = document.createElement("div");
        title.style.cssText =
          "font-weight:700;margin-bottom:8px;font-size:13px;letter-spacing:.02em;";
        title.textContent =
          g.name +
          (g.required ? " *" : "") +
          (g.multiple ? " (máx " + g.max + ")" : "");
        gc.appendChild(title);
        for (const v of g.values) {
          const label = document.createElement("label");
          label.style.cssText =
            "display:flex;align-items:center;gap:10px;border:1px solid #2a323b;" +
            "border-radius:10px;padding:9px 12px;cursor:pointer;margin-bottom:6px;" +
            "background:#0d1117;font-size:13px;";
          const input = document.createElement("input");
          input.type = g.multiple ? "checkbox" : "radio";
          input.name = "opt_" + g.id;
          input.dataset.gid = g.id;
          input.dataset.vid = v.id;
          input.style.accentColor = "#2ea043";
          input.addEventListener("change", () => {
            this.optToggle(st, g.id, v.id);
            this.syncOptionModal(st);
          });
          const span = document.createElement("span");
          span.textContent =
            v.name +
            (parseFloat(v.price_delta) > 0
              ? "  (+" + this._formatPeso(parseFloat(v.price_delta)) + ")"
              : "");
          label.appendChild(input);
          label.appendChild(span);
          gc.appendChild(label);
        }
        body.appendChild(gc);
      }
      const footer = document.createElement("div");
      footer.style.cssText =
        "padding:14px 18px;border-top:1px solid #2a323b;background:#1b2127;" +
        "display:flex;justify-content:space-between;align-items:center;" +
        "gap:12px;flex-wrap:wrap;";
      footer.innerHTML =
        "<div style='display:flex;align-items:center;gap:8px;'>" +
        "<label style='font-weight:600;font-size:13px;'>Cant.</label>" +
        "<input type='number' min='1' max='99' value='1' " +
        "style='width:64px;padding:7px;border:1px solid #2a323b;" +
        "border-radius:8px;background:#0d1117;color:#e6edf3;' " +
        "data-role='opt-qty'></div>" +
        "<div style='text-align:right;'>" +
        "<div style='font-size:12px;color:#8b949e;'>Unitario: " +
        "<span data-role='opt-unit'></span></div>" +
        "<div style='font-size:18px;font-weight:800;color:#3fb950;'>" +
        "<span data-role='opt-total'></span></div></div>" +
        "<span data-role='opt-hint' style='display:none;color:#f85149;" +
        "font-size:12px;font-weight:600;'>Faltan opciones obligatorias (*)</span>" +
        "<div style='display:flex;gap:8px;'>" +
        "<button type='button' data-role='opt-cancel' style='background:#30363d;" +
        "color:#e6edf3;border:none;padding:10px 16px;border-radius:9px;" +
        "font-weight:700;cursor:pointer;'>Cancelar</button>" +
        "<button type='button' data-role='opt-confirm' style='background:#2ea043;" +
        "color:#fff;border:none;padding:10px 18px;border-radius:9px;" +
        "font-weight:700;cursor:pointer;'>Agregar</button></div>";
      box.appendChild(header);
      box.appendChild(body);
      box.appendChild(footer);
      wrap.appendChild(box);
      document.body.appendChild(wrap);
      st.el = wrap;
      wrap.addEventListener("click", (e) => {
        if (e.target === wrap) this.closeOptionModal();
      });
      st.keydown = (e) => {
        if (e.key === "Escape") this.closeOptionModal();
      };
      document.addEventListener("keydown", st.keydown);
      footer
        .querySelector("[data-role=opt-cancel]")
        .addEventListener("click", () => this.closeOptionModal());
      footer.querySelector("[data-role=opt-confirm]").addEventListener("click", () => {
        this.confirmOptions(st);
        this.closeOptionModal();
      });
      const qtyInput = footer.querySelector("[data-role=opt-qty]");
      qtyInput.addEventListener("input", () => {
        const q = parseInt(qtyInput.value || "1", 10);
        st.qty = isNaN(q) || q < 1 ? 1 : Math.min(99, q);
        this.syncOptionModal(st);
      });
      this.syncOptionModal(st);
    },
    closeOptionModal() {
      const st = this.optState;
      if (!st) return;
      if (st.keydown) document.removeEventListener("keydown", st.keydown);
      if (st.el) st.el.remove();
      this.optState = null;
    },
    _posItemsPayload() {
      return this.cart.map((i) => ({
        product_id: i.id,
        quantity: i.qty,
        option_value_ids: i.option_value_ids || [],
      }));
    },
    async createOrder() {
      this.createOrderError = "";
      this.billNotice = "";
      if (this.cart.length === 0) return;
      const res = await fetch("/pos/create/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": this.csrf,
        },
        body: JSON.stringify({
          table_id: this.tableId || null,
          customer_name: this.customerName,
          items: this._posItemsPayload(),
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        this.createOrderError = err.error || "Error del servidor";
        return;
      }
      const data = await res.json();
      this.cart = [];
      this.orderId = data.id;
      if (data.table_id) this.tableId = data.table_id;
      await this.loadTableBill();
      await this.refreshFloor();
      this.persistState();
      this.billNotice = "Orden #" + String(data.id).slice(0, 8) + " enviada a cocina.";
    },
    async addItems() {
      this.createOrderError = "";
      this.billNotice = "";
      if (this.cart.length === 0) return;
      const target = this.targetOrder;
      if (!target) {
        await this.createOrder();
        return;
      }
      const res = await fetch("/pos/add-items/" + target.id + "/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": this.csrf,
        },
        body: JSON.stringify({ items: this._posItemsPayload() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        this.createOrderError = err.error || "No se pudieron agregar los items.";
        return;
      }
      const data = await res.json();
      this.cart = [];
      this.orderId = data.id;
      await this.loadTableBill();
      await this.refreshFloor();
      this.billNotice = "Items agregados a la orden #" + target.short + ".";
    },
    openPay(orderId) {
      this.payOrderId = orderId || null;
      this.payError = "";
      this.payAmount = 0;
      this.tipAmount = 0;
      window.posOpenModal("pay-modal");
    },
    closePay() {
      this.payOrderId = null;
      this.payError = "";
      window.posCloseModal("pay-modal");
    },
    get payScopeLabel() {
      if (!this.payOrderId) return "Todas las cuentas de la mesa";
      const o = this.billOrders.find((x) => x.id === this.payOrderId);
      return o ? "Orden #" + o.short : "Orden";
    },
    get payScopeRemaining() {
      if (!this.payOrderId) return this.billRemaining;
      const o = this.billOrders.find((x) => x.id === this.payOrderId);
      return o ? this.orderRemaining(o) : 0;
    },
    async _payOne(orderId, amount, tip) {
      const res = await fetch("/pos/pay/" + orderId + "/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": this.csrf,
        },
        body: JSON.stringify({
          method: this.payMethod,
          amount: amount,
          tip: tip || 0,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Error al registrar el pago");
      }
      return res.json();
    },
    async payRemaining() {
      this.payError = "";
      const custom = parseFloat(this.payAmount);
      const tip = parseFloat(this.tipAmount || 0);
      try {
        if (this.payOrderId) {
          const due = this.payScopeRemaining;
          const amount = custom > 0 ? Math.min(custom, due) : due;
          if (amount <= 0) throw new Error("Esta orden ya está saldada.");
          await this._payOne(this.payOrderId, amount, tip);
        } else {
          let left = custom > 0 ? custom : this.billRemaining;
          if (left <= 0) throw new Error("La cuenta ya está saldada.");
          let tipLeft = tip;
          for (const o of this.billOrders) {
            const due = this.orderRemaining(o);
            if (due <= 0.005 || left <= 0.005) continue;
            const amount = Math.min(due, left);
            await this._payOne(o.id, amount, tipLeft);
            tipLeft = 0;
            left -= amount;
          }
        }
      } catch (e) {
        this.payError = e.message;
        return;
      }
      this.payAmount = 0;
      this.tipAmount = 0;
      this.closePay();
      await this.loadTableBill();
      await this.refreshFloor();
      this.billNotice = this.billSettled
        ? "Cuenta saldada por completo."
        : "Pago registrado. Queda saldo pendiente.";
    },
    async closeOrder(orderId) {
      const o = this.billOrders.find((x) => x.id === orderId);
      if (!o) return;
      if (!o.can_close) {
        alert("No se puede cerrar: hay items sin servir o cancelar.");
        return;
      }
      if (this.orderRemaining(o) > 0.005) {
        if (!confirm("La orden tiene saldo pendiente. ¿Cerrar de todos modos?")) return;
      } else if (!confirm("¿Cerrar la orden #" + o.short + "?")) {
        return;
      }
      const res = await fetch("/pos/close/" + orderId + "/", {
        method: "POST",
        headers: { "X-CSRFToken": this.csrf },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.error || "No se pudo cerrar la orden.");
        return;
      }
      await this.loadTableBill();
      await this.refreshFloor();
      this.billNotice = "Orden #" + o.short + " cerrada.";
    },
    async resetAll() {
      this.closeOptionModal();
      window.posCloseAllModals();
      this.cart = [];
      this.orderId = null;
      this.tableBill = { ...EMPTY_BILL };
      this.payMethod = "cash";
      this.tableId = "";
      this.payAmount = 0;
      this.payError = "";
      this.totalPaid = 0;
      this.customerName = "";
      this.createOrderError = "";
      this.closed = false;
      this.tipAmount = 0;
      this.billNotice = "";
      this.billError = "";
      try {
        sessionStorage.removeItem("pos_table_id");
        sessionStorage.removeItem("pos_order_id");
      } catch (_) {}
      await this.refreshFloor();
    },
  }));
});

const FLOOR_TABLE_BOX = 56;
const FLOOR_STATUS_COLOR = {
  available: "#28a745",
  occupied: "#dc3545",
  reserved: "#007bff",
  cleaning: "#6c757d",
  out_of_service: "#6c757d",
};

document.addEventListener("alpine:init", () => {
  Alpine.data("posApp", () => ({
    categories: [],
    products: [],
    activeCat: "",
    search: "",
    cart: [],
    orderItems: [],
    tableId: "",
    orderId: null,
    customerName: "",
    orderDiscount: 0,
    payMethod: "cash",
    payAmount: 0,
    payError: "",
    totalPaid: 0,
    orderSubtotal: 0,
    orderTotal: 0,
    createOrderError: "",
    closeError: "",
    closed: false,
    tipAmount: 0,
    showPay: false,
    outOfStock: [],
    lowStock: [],
    loadError: "",
    showFloor: false,
    floorLayout: null,
    floorItems: [],
    floorUnplaced: [],
    noTableOrders: [],
    optState: null,
    methods: [
      { value: "cash", label: "\u{1F4B5} Efectivo", color: "#28a745" },
      { value: "card", label: "\u{1F4B3} Tarjeta", color: "#007bff" },
      { value: "transfer", label: "\u{1F3E6} Transf.", color: "#6f42c1" },
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
      } catch (e) {
        this.loadError = "Error al cargar datos: " + e.message;
      }
      setInterval(() => this.refreshFloor(), 30000);
    },

    get currentTableCode() {
      const all = this.floorItems.concat(this.floorUnplaced);
      const t = all.find((t) => t.table_id === this.tableId);
      return t ? t.code : "Ninguna";
    },

    floorItemStyle(t) {
      const radius = t.shape === "round" ? "50%" : "8px";
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
        "px;display:flex;flex-direction:column;" +
        "align-items:center;justify-content:center;cursor:pointer;border-radius:" +
        radius +
        ";" +
        "transform:rotate(" +
        rotation +
        "deg);color:#fff;font-weight:700;font-size:12px;" +
        "user-select:none;box-shadow:0 1px 3px rgba(0,0,0,.3);" +
        "background:" +
        (FLOOR_STATUS_COLOR[t.status] || "#6c757d") +
        ";" +
        (t.table_id === this.tableId
          ? "outline:3px solid #333;outline-offset:2px;"
          : "")
      );
    },
    floorButtonStyle(t) {
      const bg =
        t.table_id === this.tableId
          ? "#333"
          : FLOOR_STATUS_COLOR[t.status] || "#6c757d";
      return (
        "padding:10px 14px;border:none;border-radius:8px;color:#fff;font-weight:700;font-size:13px;cursor:pointer;background:" +
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
        "px;" +
        "background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;max-width:100%;overflow:auto;"
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
      if (o.order_id === this.orderId) {
        this.showFloor = false;
        return;
      }
      if (
        (this.cart.length || this.orderId) &&
        !confirm("¿Cambiar a esta orden? Perderás la selección actual.")
      )
        return;
      await this.loadOrder(o.order_id);
      this.showFloor = false;
    },

    async selectTable(t) {
      if (t.status === "occupied" && t.order_id) {
        if (t.order_id === this.orderId) {
          this.showFloor = false;
          return;
        }
        if (
          (this.cart.length || this.orderId) &&
          !confirm("¿Cambiar a la orden de esta mesa? Perderás la selección actual.")
        )
          return;
        await this.loadOrder(t.order_id);
        this.showFloor = false;
        return;
      }
      if (this.orderId) {
        const res = await fetch("/pos/set-table/" + this.orderId + "/", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": this.csrf },
          body: JSON.stringify({ table_id: t.table_id }),
        });
        if (!res.ok) {
          const err = await res.json();
          alert(err.error || "Error");
          return;
        }
        await this.refreshOrder();
        await this.refreshFloor();
      } else {
        this.tableId = t.table_id;
      }
      this.showFloor = false;
    },

    async loadOrder(orderId) {
      this.orderId = orderId;
      this.cart = [];
      await this.refreshOrder();
    },

    async refreshOrder() {
      if (!this.orderId) return;
      const res = await fetch("/pos/order-json/" + this.orderId + "/");
      if (!r_ok(res)) return;
      this._applyOrder(await res.json());

      function r_ok(r) {
        return r.ok;
      }
    },

    _optionsSuffix(opts) {
      if (!opts || !opts.length) return "";
      return " (" + opts.map((o) => o.value_name).join(", ") + ")";
    },

    _applyOrder(data) {
      this.tableId = data.table_id || "";
      this.customerName = data.customer_name || "";
      this.orderItems = data.items.map((i) => ({
        id: i.id,
        name: i.name + this._optionsSuffix(i.selected_options),
        price: parseFloat(i.price),
        qty: i.quantity,
        status: i.status,
      }));
      this.orderSubtotal = parseFloat(data.subtotal || 0);
      this.orderTotal = parseFloat(data.total || 0);
      this.totalPaid = parseFloat(data.total_paid || 0);
      this.closed = data.status !== "open";
    },

    async removeOrderItem(itemId) {
      if (!confirm("¿Quitar este item de la orden?")) return;
      const res = await fetch("/pos/remove-item/" + this.orderId + "/" + itemId + "/", {
        method: "POST",
        headers: { "X-CSRFToken": this.csrf },
      });
      if (!res.ok) return;
      this._applyOrder(await res.json());
      await this.refreshFloor();
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
      const parts = Number(n).toFixed(2).split(".");
      parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
      return "$ " + parts.join(",");
    },

    get subtotal() {
      return this.cart.reduce((s, i) => s + this._lineTotal(i), 0);
    },
    get taxBreakdown() {
      const map = {};
      for (const item of this.cart) {
        const label = this.taxLabels[item.tax_type] || item.tax_type;
        const rate = this.taxRates[item.tax_type] || 0;
        const tax = this._lineTotal(item) * rate;
        map[label] = (map[label] || 0) + tax;
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
      const t = this.cart.length > 0 ? this.total : this.orderTotal;
      return Math.max(0, t - this.totalPaid);
    },

    // ── Carrito con líneas por opciones ──────────────────────────
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

    // ── Modal de opciones: estado en objeto plano (fuera de Alpine) ──
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
      wrap.style.cssText =
        "position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:2000;display:flex;align-items:center;justify-content:center;padding:16px;";

      const box = document.createElement("div");
      box.style.cssText =
        "background:#fff;border-radius:10px;width:100%;max-width:600px;max-height:88vh;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 10px 30px rgba(0,0,0,.25);";

      const header = document.createElement("div");
      header.style.cssText =
        "padding:12px 16px;border-bottom:1px solid #dee2e6;display:flex;justify-content:space-between;align-items:center;background:#f8f9fa;";
      const h3 = document.createElement("h3");
      h3.style.cssText = "margin:0;font-size:16px;font-weight:700;";
      h3.textContent = st.product.name;
      const closeBtn = document.createElement("button");
      closeBtn.type = "button";
      closeBtn.textContent = "\u2715";
      closeBtn.style.cssText =
        "background:none;border:none;font-size:20px;cursor:pointer;color:#666;";
      closeBtn.addEventListener("click", () => this.closeOptionModal());
      header.appendChild(h3);
      header.appendChild(closeBtn);

      const body = document.createElement("div");
      body.style.cssText = "padding:16px;overflow-y:auto;flex:1;";
      for (const g of st.groups) {
        const gc = document.createElement("div");
        gc.dataset.gid = g.id;
        gc.style.cssText = "margin-bottom:14px;";
        const title = document.createElement("div");
        title.style.cssText = "font-weight:700;margin-bottom:6px;";
        title.textContent =
          g.name +
          (g.required ? " *" : "") +
          (g.multiple ? " (máx " + g.max + ")" : "");
        gc.appendChild(title);
        for (const v of g.values) {
          const label = document.createElement("label");
          label.style.cssText =
            "display:flex;align-items:center;gap:8px;border:1px solid #e5e7eb;border-radius:6px;padding:6px 10px;cursor:pointer;margin-bottom:6px;";
          const input = document.createElement("input");
          input.type = g.multiple ? "checkbox" : "radio";
          input.name = "opt_" + g.id;
          input.dataset.gid = g.id;
          input.dataset.vid = v.id;
          input.addEventListener("change", () => {
            this.optToggle(st, g.id, v.id);
            this.syncOptionModal(st);
          });
          const span = document.createElement("span");
          span.textContent =
            v.name +
            (parseFloat(v.price_delta) > 0
              ? " (+" + this._formatPeso(parseFloat(v.price_delta)) + ")"
              : "");
          label.appendChild(input);
          label.appendChild(span);
          gc.appendChild(label);
        }
        body.appendChild(gc);
      }

      const footer = document.createElement("div");
      footer.style.cssText =
        "padding:12px 16px;border-top:1px solid #dee2e6;background:#f8f9fa;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;";
      footer.innerHTML =
        "<div style='display:flex;align-items:center;gap:8px;'>" +
        "<label style='font-weight:600;'>Cant.</label>" +
        "<input type='number' min='1' max='99' value='1' style='width:64px;padding:6px;border:1px solid #ced4da;border-radius:6px;' data-role='opt-qty'>" +
        "</div>" +
        "<div style='text-align:right;'>" +
        "<div style='font-size:12px;color:#666;'>Unitario: <span data-role='opt-unit'></span></div>" +
        "<div style='font-size:17px;font-weight:800;color:#28a745;'><span data-role='opt-total'></span></div>" +
        "</div>" +
        "<span data-role='opt-hint' style='display:none;color:#dc3545;font-size:12px;font-weight:600;'>Faltan opciones obligatorias (*)</span>" +
        "<div style='display:flex;gap:8px;'>" +
        "<button type='button' data-role='opt-cancel' style='background:#6c757d;color:#fff;border:none;padding:9px 14px;border-radius:6px;font-weight:700;cursor:pointer;'>Cancelar</button>" +
        "<button type='button' data-role='opt-confirm' style='background:#28a745;color:#fff;border:none;padding:9px 16px;border-radius:6px;font-weight:700;cursor:pointer;'>Agregar</button>" +
        "</div>";

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

    // ── Creación / agregado de items ─────────────────────────────
    _posItemsPayload() {
      return this.cart.map((i) => ({
        product_id: i.id,
        quantity: i.qty,
        option_value_ids: i.option_value_ids || [],
      }));
    },

    async createOrder() {
      this.createOrderError = "";
      if (this.cart.length === 0) return;
      const res = await fetch("/pos/create/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": this.csrf },
        body: JSON.stringify({
          table_id: this.tableId || null,
          customer_name: this.customerName,
          discount_amount: this.orderDiscount,
          items: this._posItemsPayload(),
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        this.createOrderError = err.error || "Error del servidor";
        return;
      }
      const data = await res.json();
      this.orderId = data.id;
      this.cart = [];
      this._applyOrder(data);
      await this.refreshFloor();
    },

    async addItems() {
      if (this.cart.length === 0) return;
      const res = await fetch("/pos/add-items/" + this.orderId + "/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": this.csrf },
        body: JSON.stringify({ items: this._posItemsPayload() }),
      });
      if (!res.ok) return;
      this.cart = [];
      this._applyOrder(await res.json());
    },

    async payRemaining() {
      this.payError = "";
      const amount =
        parseFloat(this.payAmount) > 0 ? parseFloat(this.payAmount) : this.remaining;
      const res = await fetch("/pos/pay/" + this.orderId + "/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": this.csrf },
        body: JSON.stringify({
          method: this.payMethod,
          amount: amount,
          tip: parseFloat(this.tipAmount || 0),
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        this.payError = err.error || "Error";
        return;
      }
      const data = await res.json();
      this.totalPaid += parseFloat(data.amount);
      this.payAmount = 0;
      this.tipAmount = 0;
      this.payError = "";
      if (this.remaining <= 0.005) {
        await this._closeAfterPay();
      }
    },

    async _closeAfterPay() {
      const res = await fetch("/pos/close/" + this.orderId + "/", {
        method: "POST",
        headers: { "X-CSRFToken": this.csrf },
      });
      if (res.ok) {
        this.closed = true;
        await this.refreshFloor();
      }
    },

    async resetAll() {
      this.closeOptionModal();
      this.cart = [];
      this.orderItems = [];
      this.orderId = null;
      this.payMethod = "cash";
      this.tableId = "";
      this.payAmount = 0;
      this.payError = "";
      this.totalPaid = 0;
      this.orderSubtotal = 0;
      this.orderTotal = 0;
      this.customerName = "";
      this.orderDiscount = 0;
      this.createOrderError = "";
      this.closeError = "";
      this.closed = false;
      this.tipAmount = 0;
      this.showPay = false;
      await this.refreshFloor();
    },
  }));
});

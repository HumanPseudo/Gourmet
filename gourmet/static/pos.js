const FLOOR_TABLE_BOX = 56;
const FLOOR_STATUS_COLOR = {
  available: '#28a745',
  occupied: '#dc3545',
  reserved: '#007bff',
  cleaning: '#6c757d',
  out_of_service: '#6c757d',
};

document.addEventListener('alpine:init', () => {
  Alpine.data('posApp', () => ({
    categories: [], products: [], activeCat: '', search: '',
    cart: [], orderItems: [], tableId: '', orderId: null, customerName: '', orderDiscount: 0,
    payMethod: 'cash', payAmount: 0, payError: '',
    totalPaid: 0, orderSubtotal: 0, orderTotal: 0,
    createOrderError: '', closeError: '', closed: false, tipAmount: 0, showPay: false,
    outOfStock: [], lowStock: [],
    loadError: '',
    showFloor: false, floorLayout: null, floorItems: [], floorUnplaced: [], noTableOrders: [],
    methods: [
      { value: 'cash', label: '\u{1F4B5} Efectivo', color: '#28a745' },
      { value: 'card', label: '\u{1F4B3} Tarjeta', color: '#007bff' },
      { value: 'transfer', label: '\u{1F3E6} Transf.', color: '#6f42c1' },
    ],
    taxLabels: { INC_8: 'INC 8%', IVA_19: 'IVA 19%', IVA_5: 'IVA 5%', EXENTO: 'Exento' },
    taxRates: { INC_8: 0.08, IVA_19: 0.19, IVA_5: 0.05, EXENTO: 0.0 },

    get csrf() { return document.querySelector('meta[name=csrf-token]')?.content || ''; },

    async init() {
      try {
        const meta = document.querySelector('meta[name=out-of-stock]');
        if (meta) this.outOfStock = JSON.parse(meta.content);
        const ls = document.querySelector('meta[name=low-stock]');
        if (ls) this.lowStock = JSON.parse(ls.content);
        const [cats, prods] = await Promise.all([
          fetch('/api/menu/categories').then(r => { if (!r.ok) throw new Error('categories: ' + r.status); return r.json(); }),
          fetch('/api/menu/products').then(r => { if (!r.ok) throw new Error('products: ' + r.status); return r.json(); }),
        ]);
        this.categories = cats.items || cats || [];
        this.products = (prods.items || prods || []).filter(p => p.is_available);
        await this.refreshFloor();
      } catch (e) {
        this.loadError = 'Error al cargar datos: ' + e.message;
      }
      setInterval(() => this.refreshFloor(), 30000);
    },

    get currentTableCode() {
      const all = this.floorItems.concat(this.floorUnplaced);
      const t = all.find(t => t.table_id === this.tableId);
      return t ? t.code : 'Ninguna';
    },

    floorItemStyle(t) {
      const radius = t.shape === 'round' ? '50%' : '8px';
      const rotation = t.rotation || 0;
      return 'position:absolute;left:' + t.pos_x + 'px;top:' + t.pos_y + 'px;'
        + 'width:' + FLOOR_TABLE_BOX + 'px;height:' + FLOOR_TABLE_BOX + 'px;display:flex;flex-direction:column;'
        + 'align-items:center;justify-content:center;cursor:pointer;border-radius:' + radius + ';'
        + 'transform:rotate(' + rotation + 'deg);color:#fff;font-weight:700;font-size:12px;'
        + 'user-select:none;box-shadow:0 1px 3px rgba(0,0,0,.3);'
        + 'background:' + (FLOOR_STATUS_COLOR[t.status] || '#6c757d') + ';'
        + (t.table_id === this.tableId ? 'outline:3px solid #333;outline-offset:2px;' : '');
    },

    floorButtonStyle(t) {
      const bg = t.table_id === this.tableId ? '#333' : (FLOOR_STATUS_COLOR[t.status] || '#6c757d');
      return 'padding:10px 14px;border:none;border-radius:8px;color:#fff;font-weight:700;font-size:13px;cursor:pointer;background:' + bg + ';';
    },

    floorBoardStyle() {
      if (!this.floorLayout) return '';
      return 'position:relative;width:' + this.floorLayout.width + 'px;height:' + this.floorLayout.height + 'px;'
        + 'background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;max-width:100%;overflow:auto;';
    },

    async refreshFloor() {
      try {
        const r = await fetch('/pos/floor-status/');
        if (!r.ok) return;
        const data = await r.json();
        this.floorLayout = data.layout;
        this.floorItems = data.items || [];
        this.floorUnplaced = data.unplaced || [];
        this.noTableOrders = data.no_table_orders || [];
      } catch (_) {}
    },

    async selectNoTableOrder(o) {
      if (o.order_id === this.orderId) { this.showFloor = false; return; }
      if ((this.cart.length || this.orderId) && !confirm('¿Cambiar a esta orden? Perderás la selección actual.')) return;
      await this.loadOrder(o.order_id);
      this.showFloor = false;
    },

    async selectTable(t) {
      if (t.status === 'occupied' && t.order_id) {
        if (t.order_id === this.orderId) { this.showFloor = false; return; }
        if ((this.cart.length || this.orderId) && !confirm('¿Cambiar a la orden de esta mesa? Perderás la selección actual.')) return;
        await this.loadOrder(t.order_id);
        this.showFloor = false;
        return;
      }
      if (this.orderId) {
        const res = await fetch('/pos/set-table/' + this.orderId + '/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrf },
          body: JSON.stringify({ table_id: t.table_id }),
        });
        if (!res.ok) { const err = await res.json(); alert(err.error || 'Error'); return; }
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
      const res = await fetch('/pos/order-json/' + this.orderId + '/');
      if (!res.ok) return;
      this._applyOrder(await res.json());
    },

    _applyOrder(data) {
      this.tableId = data.table_id || '';
      this.customerName = data.customer_name || '';
      this.orderItems = data.items.map(i => ({ id: i.id, name: i.name, price: parseFloat(i.price), qty: i.quantity, status: i.status }));
      this.orderSubtotal = parseFloat(data.subtotal || 0);
      this.orderTotal = parseFloat(data.total || 0);
      this.totalPaid = parseFloat(data.total_paid || 0);
      this.closed = data.status !== 'open';
    },

    async removeOrderItem(itemId) {
      if (!confirm('¿Quitar este item de la orden?')) return;
      const res = await fetch('/pos/remove-item/' + this.orderId + '/' + itemId + '/', {
        method: 'POST', headers: { 'X-CSRFToken': this.csrf },
      });
      if (!res.ok) return;
      this._applyOrder(await res.json());
      await this.refreshFloor();
    },

    get stockClass() {
      return (id) => this.outOfStock.includes(id) ? 'out-of-stock' : '';
    },

    get filteredProducts() {
      let p = this.products;
      if (this.search) {
        const q = this.search.toLowerCase();
        p = p.filter(x => x.name.toLowerCase().includes(q));
      }
      if (this.activeCat) p = p.filter(x => x.category_id === this.activeCat);
      return p;
    },

    _lineTotal(item) { return item.price * item.qty; },

    _formatPeso(n) {
      const parts = Number(n).toFixed(2).split('.');
      parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
      return '$ ' + parts.join(',');
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

    addItem(p) {
      const existing = this.cart.find(i => i.id === p.id);
      if (existing) { existing.qty++; return; }
      this.cart.push({ id: p.id, name: p.name, price: parseFloat(p.price), tax_type: p.tax_type, qty: 1 });
    },

    changeQty(idx, delta) {
      const item = this.cart[idx];
      if (!item) return;
      item.qty = Math.max(1, item.qty + delta);
    },

    removeItem(idx) { this.cart.splice(idx, 1); },

    async createOrder() {
      this.createOrderError = '';
      if (this.cart.length === 0) return;
      const res = await fetch('/pos/create/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrf },
        body: JSON.stringify({
          table_id: this.tableId || null,
          customer_name: this.customerName,
          discount_amount: this.orderDiscount,
          items: this.cart.map(i => ({ product_id: i.id, quantity: i.qty })),
        }),
      });
      if (!res.ok) { const err = await res.json(); this.createOrderError = err.error || 'Error del servidor'; return; }
      const data = await res.json();
      this.orderId = data.id;
      this.cart = [];
      this._applyOrder(data);
      await this.refreshFloor();
    },

    async addItems() {
      if (this.cart.length === 0) return;
      const res = await fetch('/pos/add-items/' + this.orderId + '/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrf },
        body: JSON.stringify({
          items: this.cart.map(i => ({ product_id: i.id, quantity: i.qty })),
        }),
      });
      if (!res.ok) return;
      this.cart = [];
      this._applyOrder(await res.json());
    },

    async payRemaining() {
      this.payError = '';
      const amount = parseFloat(this.payAmount) > 0 ? parseFloat(this.payAmount) : this.remaining;
      const res = await fetch('/pos/pay/' + this.orderId + '/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrf },
        body: JSON.stringify({ method: this.payMethod, amount: amount, tip: parseFloat(this.tipAmount || 0) }),
      });
      if (!res.ok) { const err = await res.json(); this.payError = err.error || 'Error'; return; }
      const data = await res.json();
      this.totalPaid += parseFloat(data.amount);
      this.payAmount = 0; this.tipAmount = 0; this.payError = '';
      if (this.remaining <= 0.005) {
        await this._closeAfterPay();
      }
    },

    async _closeAfterPay() {
      const res = await fetch('/pos/close/' + this.orderId + '/', {
        method: 'POST', headers: { 'X-CSRFToken': this.csrf },
      });
      if (res.ok) {
        this.closed = true;
        await this.refreshFloor();
      }
    },

    async resetAll() {
      this.cart = []; this.orderItems = []; this.orderId = null; this.payMethod = 'cash';
      this.tableId = '';
      this.payAmount = 0; this.payError = ''; this.totalPaid = 0;
      this.orderSubtotal = 0; this.orderTotal = 0; this.customerName = ''; this.orderDiscount = 0;
      this.createOrderError = ''; this.closeError = ''; this.closed = false; this.tipAmount = 0; this.showPay = false;
      await this.refreshFloor();
    },

  }));
});

document.addEventListener('DOMContentLoaded', function() {
    var splitBtn = document.getElementById('splitBtn');
    if (splitBtn) {
        splitBtn.addEventListener('click', function() {
            var ids = Array.from(document.querySelectorAll('.split-item:checked')).map(function(cb) { return cb.value; });
            if (!ids.length) { alert('Selecciona items para separar'); return; }
            if (!confirm('Separar ' + ids.length + ' item(s) a una nueva orden?')) return;
            fetch(splitBtn.dataset.url, {
                method: 'POST',
                headers: {'Content-Type':'application/json','X-CSRFToken':document.querySelector('meta[name=csrf-token]').content},
                body: JSON.stringify({item_ids: ids}),
            }).then(function(r) { return r.json(); }).then(function(d) {
                if (d.error) { alert(d.error); return; }
                window.location.reload();
            });
        });
    }
    var closeForm = document.getElementById('closeForm');
    if (closeForm) {
        closeForm.addEventListener('submit', function(e) {
            if (!confirm('Cerrar la orden?')) { e.preventDefault(); }
        });
    }
});

// ── Bill Splitting (Alpine.js components) ────────────────────────

function splitPanel(orderId) {
    return {
        orderId: orderId,
        mode: 'by_items',
        loading: false,
        error: '',
        createdSplits: [],

        // By percentage
        pctSplits: [
            { label: 'Persona 1', percentage: 50 },
            { label: 'Persona 2', percentage: 50 },
        ],

        // Equal
        eqCount: 2,
        eqLabels: ['Persona 1', 'Persona 2'],

        get pctTotal() {
            return this.pctSplits.reduce(function(sum, p) { return sum + (parseFloat(p.percentage) || 0); }, 0);
        },

        _getApiToken: function() {
            var meta = document.querySelector('meta[name=api-token]');
            return meta ? meta.content : '';
        },

        createSplit: function() {
            var self = this;
            self.loading = true;
            self.error = '';

            var body;
            if (self.mode === 'by_items') {
                var panel = document.querySelector('.split-person');
                if (!panel) { self.error = 'No hay items'; self.loading = false; return; }
                var items = [];
                panel.querySelectorAll('.split-item-row').forEach(function(row) {
                    var cb = row.querySelector('input[type=checkbox]');
                    var qty = row.querySelector('input[type=number]');
                    if (cb && cb.checked && qty && parseInt(qty.value) > 0) {
                        items.push({ order_item_id: cb.value, quantity: parseInt(qty.value) });
                    }
                });
                if (items.length === 0) {
                    self.error = 'Selecciona al menos un item';
                    self.loading = false;
                    return;
                }
                var nameInput = panel.querySelector('input[type=text]');
                body = {
                    method: 'by_items',
                    splits: [{ label: nameInput ? nameInput.value || 'Sin nombre' : 'Sin nombre', items: items }],
                };
            } else if (self.mode === 'by_percentage') {
                body = {
                    method: 'by_percentage',
                    splits: self.pctSplits.map(function(p) {
                        return { label: p.label, percentage: parseFloat(p.percentage) };
                    }),
                };
            } else {
                body = {
                    method: 'equal',
                    n_splits: self.eqCount,
                    labels: self.eqLabels.filter(function(l) { return l.trim(); }),
                };
            }

            fetch('/api/orders/' + self.orderId + '/splits', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + self._getApiToken(),
                },
                body: JSON.stringify(body),
            }).then(function(r) {
                if (!r.ok) return r.json().then(function(d) { throw new Error(d.detail || 'Error'); });
                return r.json();
            }).then(function(splits) {
                self.createdSplits = splits;
                self.loading = false;
            }).catch(function(e) {
                self.error = e.message;
                self.loading = false;
            });
        },

        paySplit: function(split) {
            var self = this;
            var method = prompt('Método de pago (cash/card/transfer):', 'cash');
            if (!method) return;

            fetch('/api/orders/' + self.orderId + '/splits/' + split.id + '/pay', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + self._getApiToken(),
                },
                body: JSON.stringify({ method: method, reference: '', tip: '0.00' }),
            }).then(function(r) {
                if (!r.ok) return r.json().then(function(d) { throw new Error(d.detail || 'Error'); });
                return r.json();
            }).then(function() {
                split.paid = true;
            }).catch(function(e) {
                self.error = e.message;
            });
        },

        deleteSplit: function(split) {
            var self = this;
            if (!confirm('Eliminar división de ' + split.label + '?')) return;

            fetch('/api/orders/' + self.orderId + '/splits/' + split.id, {
                method: 'DELETE',
                headers: {
                    'Authorization': 'Bearer ' + self._getApiToken(),
                },
            }).then(function(r) {
                if (!r.ok) return r.json().then(function(d) { throw new Error(d.detail || 'Error'); });
                self.createdSplits = self.createdSplits.filter(function(s) { return s.id !== split.id; });
            }).catch(function(e) {
                self.error = e.message;
            });
        },
    };
}

function splitPerson(name) {
    return {
        name: name,
        checked: {},
        qty: {},
    };
}

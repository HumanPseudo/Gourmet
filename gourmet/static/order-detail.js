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

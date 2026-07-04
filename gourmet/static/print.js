document.addEventListener('DOMContentLoaded', function() {
    window.print();
    document.querySelectorAll('.print-btn').forEach(function(btn) {
        btn.addEventListener('click', function() { window.print(); });
    });
});

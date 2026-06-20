/**
 * Contract Admin - Main JavaScript
 * Version: 0.0.1
 */

document.addEventListener('DOMContentLoaded', function () {

    // ---- Confirm dialogs for delete buttons -------------------------------
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
        el.addEventListener('click', function (e) {
            var message = el.getAttribute('data-confirm') || '确定要执行此操作吗？';
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });

    // ---- Auto-dismiss flash messages after 5 seconds ----------------------
    document.querySelectorAll('.flash').forEach(function (flash) {
        setTimeout(function () {
            flash.style.transition = 'opacity 0.5s';
            flash.style.opacity = '0';
            setTimeout(function () {
                if (flash.parentNode) {
                    flash.remove();
                }
            }, 500);
        }, 5000);
    });

    // ---- File input: show selected filename -------------------------------
    var fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(function (input) {
        input.addEventListener('change', function () {
            var label = input.parentNode.querySelector('.file-name');
            if (label) {
                label.textContent = input.files[0]
                    ? input.files[0].name
                    : '未选择文件';
            }
        });
    });

});

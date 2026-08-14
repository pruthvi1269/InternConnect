document.addEventListener("DOMContentLoaded", function () {
    const alerts = document.querySelectorAll(".alert");

    alerts.forEach(function (alert) {
        setTimeout(function () {
            alert.style.transition = "opacity 0.5s";
            alert.style.opacity = "0";
        }, 4000);
    });

    const forms = document.querySelectorAll("form");

    forms.forEach(function (form) {
        form.addEventListener("submit", function () {
            const button = form.querySelector("button[type='submit'], button:not(.btn-close)");
            if (button && !button.classList.contains("btn-close")) {
                button.disabled = true;
                if (button.innerText.includes("Apply")) {
                    button.innerText = "Submitting...";
                }
            }
        });
    });
});

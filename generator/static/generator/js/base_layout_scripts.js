document.addEventListener('DOMContentLoaded', function () {
    const navbar = document.getElementById('main-navbar');
    if (navbar) {
        const setBodyPadding = () => {
            const navbarHeight = navbar.offsetHeight;
            document.body.style.paddingTop = navbarHeight + 'px';
        }
        setBodyPadding();
        // Opcional: new ResizeObserver(setBodyPadding).observe(navbar);
    }

    // Inicializa tooltips do Bootstrap para os links da navbar
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('.navbar-nav .nav-link[title], .navbar-nav .btn[title]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl, {
            placement: 'bottom', // Tooltips aparecerão abaixo dos ícones
            trigger: 'hover' // Mostrar no hover
        });
    });
});


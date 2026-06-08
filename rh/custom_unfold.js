document.addEventListener("DOMContentLoaded", function() {
    const cambiarPlaceholderSelect = () => {
        // 1. Busca elementos select nativos o divs que Unfold genera con ese texto
        document.querySelectorAll('*').forEach(el => {
            // Si el elemento contiene exactamente "Select value"
            if (el.textContent && el.textContent.trim() === "Select value") {
                el.textContent = "Seleccionar";
            }
            // A veces el texto viene en los atributos placeholder de los buscadores internos de Unfold
            if (el.getAttribute('placeholder') === "Select value") {
                el.setAttribute('placeholder', "Seleccionar...");
            }
        });
    };

    // Ejecutar inmediatamente al cargar la página
    setTimeout(cambiarPlaceholderSelect, 100);

    // Ejecutar dinámicamente cada vez que Unfold abra o dibuje un combo en la pantalla
    const observer = new MutationObserver(() => {
        cambiarPlaceholderSelect();
    });
    
    observer.observe(document.body, { childList: true, subtree: true });
});
document.addEventListener('DOMContentLoaded', function () {
    const realSelect = document.getElementById('search-area');
    const customDropdownBtn = document.getElementById('custom-area-filter-btn');
    if (!realSelect || !customDropdownBtn) {
        // console.warn("Elementos do dropdown de área não encontrados. Funcionalidade de multi-select de área pode não funcionar.");
        return;
    }
    const dropdownMenu = customDropdownBtn.nextElementSibling;
    if (!dropdownMenu) {
        // console.warn("Menu dropdown para multi-select de área não encontrado.");
        return;
    }

    const customDropdownBtnText = customDropdownBtn.querySelector('.btn-text');
    const areaCheckboxContainers = dropdownMenu.querySelectorAll('.dropdown-item-text');

    function updateDropdownButtonText() {
        if (!customDropdownBtnText) return;
        const selectedOptions = Array.from(realSelect.options).filter(option => option.selected);
        if (selectedOptions.length === 0) {
            customDropdownBtnText.textContent = 'Selecione área(s)';
        } else if (selectedOptions.length === 1) {
            customDropdownBtnText.textContent = selectedOptions[0].text;
        } else {
            customDropdownBtnText.textContent = selectedOptions.length + ' áreas selecionadas';
        }
    }

    areaCheckboxContainers.forEach(function(container) {
        const checkbox = container.querySelector('.area-checkbox');
        if (!checkbox) return;

        checkbox.addEventListener('change', function() {
            const value = this.value;
            const correspondingOption = realSelect.querySelector('option[value="' + value + '"]');
            if (correspondingOption) {
                correspondingOption.selected = this.checked;
            }
            updateDropdownButtonText();
        });

        // Permite clicar no texto do item para marcar/desmarcar o checkbox
        container.addEventListener('click', function(e) {
            if (e.target !== checkbox) { // Evita disparar duas vezes se clicar diretamente no checkbox
                checkbox.checked = !checkbox.checked;
                // Dispara o evento 'change' manualmente para que o listener acima seja acionado
                const event = new Event('change', { bubbles: true });
                checkbox.dispatchEvent(event);
            }
        });
    });

    // Inicializa o texto do botão do dropdown
    updateDropdownButtonText();

    // Lógica do botão de impressão
    const printButton = document.getElementById('printQuestionsBtn');
    if (printButton) {
        printButton.addEventListener('click', function() {
            window.print();
        });
    }
});
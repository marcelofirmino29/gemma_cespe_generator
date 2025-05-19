/*!
 * Color mode toggler for Bootstrap's docs (https://getbootstrap.com/)
 * Copyright 2011-2024 The Bootstrap Authors
 * Licensed under the Creative Commons Attribution 3.0 Unported License.
 * Modified to use data-bs-theme directly and integrate with localStorage
 */

(() => {
  'use strict'

  const getStoredTheme = () => localStorage.getItem('color-theme')
  const setStoredTheme = theme => localStorage.setItem('color-theme', theme)

  const getPreferredTheme = () => {
    const storedTheme = getStoredTheme()
    if (storedTheme) {
      return storedTheme
    }
    // ALTERADO: Agora usa 'light' como padrão se o sistema não preferir escuro e não houver tema salvo.
    // Isso é mais adequado se o seu tema principal (Brite) é claro.
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }

  const setTheme = theme => {
    if (theme === 'auto') {
        // ALTERADO: 'auto' agora reflete corretamente a preferência do sistema, ou 'light' como padrão.
        const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        document.documentElement.setAttribute('data-bs-theme', systemTheme);
    } else {
      document.documentElement.setAttribute('data-bs-theme', theme)
    }
  }

  // Aplica o tema imediatamente ao carregar o script
  setTheme(getPreferredTheme())

  const showActiveTheme = (theme, focus = false) => {
    const themeSwitcher = document.querySelector('#bd-theme')

    if (!themeSwitcher) {
      return
    }

    const themeSwitcherText = document.querySelector('#bd-theme-text')
    const activeThemeIcon = document.querySelector('.theme-icon-active use') // Ícone no botão
    // Certifique-se que btnToActive não será nulo se o tema for 'auto' e o sistema for light/dark
    let effectiveTheme = theme;
    if (theme === 'auto') {
        effectiveTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    const btnToActive = document.querySelector(`[data-bs-theme-value="${effectiveTheme}"]`) // Usa o tema efetivo para encontrar o botão
    
    // Adicionada verificação para btnToActive antes de prosseguir
    if (!btnToActive) {
        // Pode ser que o tema 'auto' resultou em um valor que não tem um botão correspondente direto
        // ou o botão para o tema efetivo não foi encontrado.
        // Tenta encontrar o botão 'auto' se o tema original era 'auto'.
        const autoButton = document.querySelector(`[data-bs-theme-value="auto"]`);
        if (theme === 'auto' && autoButton) {
            // Se o tema é 'auto', destaca o botão 'auto' e atualiza o ícone principal para o tema do sistema
            const systemThemeIcon = document.querySelector(`[data-bs-theme-value="${effectiveTheme}"] svg use`).getAttribute('href');
            document.querySelectorAll('[data-bs-theme-value]').forEach(element => {
                element.classList.remove('active');
                element.setAttribute('aria-pressed', 'false');
                element.querySelector('svg.bi.ms-auto.d-none').classList.add('d-none');
            });
            autoButton.classList.add('active');
            autoButton.setAttribute('aria-pressed', 'true');
            autoButton.querySelector('svg.bi.ms-auto.d-none').classList.remove('d-none');
            activeThemeIcon.setAttribute('href', systemThemeIcon); // Ícone do sistema no botão principal
            const themeSwitcherLabel = `${themeSwitcherText.textContent} (${autoButton.dataset.bsThemeValue} - ${effectiveTheme})`
            themeSwitcher.setAttribute('aria-label', themeSwitcherLabel)

        } else if (btnToActive) { // Se btnToActive foi encontrado (não era 'auto' ou 'auto' resolveu para um botão existente)
             const svgOfActiveBtn = btnToActive.querySelector('svg use').getAttribute('href') // Ícone no item do dropdown
             document.querySelectorAll('[data-bs-theme-value]').forEach(element => {
                element.classList.remove('active')
                element.setAttribute('aria-pressed', 'false')
                element.querySelector('svg.bi.ms-auto.d-none').classList.add('d-none'); // Esconde checkmark
             })
             btnToActive.classList.add('active')
             btnToActive.setAttribute('aria-pressed', 'true')
             btnToActive.querySelector('svg.bi.ms-auto.d-none').classList.remove('d-none'); // Mostra checkmark
             activeThemeIcon.setAttribute('href', svgOfActiveBtn) // Atualiza ícone do botão
             const themeSwitcherLabel = `${themeSwitcherText.textContent} (${btnToActive.dataset.bsThemeValue})`
             themeSwitcher.setAttribute('aria-label', themeSwitcherLabel)
        } else {
            console.warn(`Botão para o tema '${effectiveTheme}' não encontrado no seletor de tema.`);
            return;
        }


    } else { // btnToActive foi encontrado diretamente
        const svgOfActiveBtn = btnToActive.querySelector('svg use').getAttribute('href') 
        document.querySelectorAll('[data-bs-theme-value]').forEach(element => {
            element.classList.remove('active')
            element.setAttribute('aria-pressed', 'false')
            element.querySelector('svg.bi.ms-auto.d-none').classList.add('d-none'); 
        })
        btnToActive.classList.add('active')
        btnToActive.setAttribute('aria-pressed', 'true')
        btnToActive.querySelector('svg.bi.ms-auto.d-none').classList.remove('d-none'); 
        activeThemeIcon.setAttribute('href', svgOfActiveBtn) 
        const themeSwitcherLabel = `${themeSwitcherText.textContent} (${btnToActive.dataset.bsThemeValue})`
        themeSwitcher.setAttribute('aria-label', themeSwitcherLabel)
    }


    if (focus) {
      themeSwitcher.focus()
    }
  }

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    const storedTheme = getStoredTheme()
    if (storedTheme === 'auto') { // Só atualiza se 'auto' estiver explicitamente salvo
      setTheme('auto') // Reavalia e aplica o tema 'auto' baseado na nova preferência do sistema
      showActiveTheme('auto') // Atualiza a UI para refletir o estado 'auto'
    }
  })

  window.addEventListener('DOMContentLoaded', () => {
    showActiveTheme(getPreferredTheme())

    document.querySelectorAll('[data-bs-theme-value]')
      .forEach(toggle => {
        toggle.addEventListener('click', () => {
          const theme = toggle.getAttribute('data-bs-theme-value')
          setStoredTheme(theme)
          setTheme(theme)
          showActiveTheme(theme, true)
        })
      })
  })
})()
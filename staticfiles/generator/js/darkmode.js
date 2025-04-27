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
    // Define 'dark' como padrão se não houver preferência do sistema detectável ou salva
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'dark'
    // return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light' // Para padrão light
  }

  const setTheme = theme => {
    if (theme === 'auto') {
        // Define dark como padrão 'auto' se o sistema não tiver preferência clara
        const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'dark';
        document.documentElement.setAttribute('data-bs-theme', systemTheme);
        // document.documentElement.setAttribute('data-bs-theme', (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')) // Para auto real
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
    const btnToActive = document.querySelector(`[data-bs-theme-value="${theme}"]`)
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

    if (focus) {
      themeSwitcher.focus()
    }
  }

  // Ouve mudanças na preferência do sistema (se o tema atual for 'auto')
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    const storedTheme = getStoredTheme()
    if (storedTheme !== 'light' && storedTheme !== 'dark') { // Só atualiza se for 'auto'
      setTheme(getPreferredTheme())
    }
  })

  // Garante que a UI do seletor seja atualizada ao carregar a página
  window.addEventListener('DOMContentLoaded', () => {
    showActiveTheme(getPreferredTheme())

    // Adiciona listeners aos botões do dropdown
    document.querySelectorAll('[data-bs-theme-value]')
      .forEach(toggle => {
        toggle.addEventListener('click', () => {
          const theme = toggle.getAttribute('data-bs-theme-value')
          setStoredTheme(theme) // Salva a escolha
          setTheme(theme)      // Aplica o tema
          showActiveTheme(theme, true) // Atualiza a UI do botão/dropdown
        })
      })
  })
})()

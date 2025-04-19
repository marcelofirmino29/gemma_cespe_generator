// static/generator/js/darkmode.js
/*!
 * Color mode toggler for Bootstrap's docs (https://getbootstrap.com/)
 * Copyright 2011-2024 The Bootstrap Authors
 * Licensed under the Creative Commons Attribution 3.0 Unported License.
 */
(() => {
    'use strict'
    const getStoredTheme = () => localStorage.getItem('theme')
    const setStoredTheme = theme => localStorage.setItem('theme', theme)

    const getPreferredTheme = () => {
      const storedTheme = getStoredTheme()
      if (storedTheme) {
        return storedTheme
      }
      // Define 'light' como padrão inicial ou se 'auto' não for preferido
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
      // return 'auto' // Use esta linha em vez da anterior se preferir 'auto' como padrão absoluto
    }

    const setTheme = theme => {
      let themeToSet = theme
      if (theme === 'auto') {
        themeToSet = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
      }
      document.documentElement.setAttribute('data-bs-theme', themeToSet)
    }

    // Aplica o tema salvo ou preferido imediatamente ao carregar o JS
    setTheme(getPreferredTheme())

    const showActiveTheme = (theme, focus = false) => {
      const themeSwitcher = document.querySelector('#bd-theme')
      if (!themeSwitcher) { return }

      const themeSwitcherText = document.querySelector('#bd-theme-text') // Para o label em telas pequenas
      const activeThemeIcon = document.querySelector('.theme-icon-active use')
      const btnToActivate = document.querySelector(`[data-bs-theme-value="${theme}"]`)

      if (!btnToActivate) return; // Sai se o botão do tema ativo não for encontrado

      const svgOfActiveBtn = btnToActivate.querySelector('svg.theme-icon use')?.getAttribute('href')

      // Remove 'active' e 'aria-pressed' de todos os itens do dropdown
      document.querySelectorAll('[data-bs-theme-value]').forEach(element => {
        element.classList.remove('active')
        element.setAttribute('aria-pressed', 'false')
        // Esconde o ícone de "check" em todos
        const checkIcon = element.querySelector('svg.bi.ms-auto.d-none')
        if(checkIcon) checkIcon.classList.add('d-none')
      })

      // Ativa o botão correto no dropdown
      btnToActivate.classList.add('active')
      btnToActivate.setAttribute('aria-pressed', 'true')
      const checkIconActive = btnToActivate.querySelector('svg.bi.ms-auto.d-none')
      if(checkIconActive) checkIconActive.classList.remove('d-none') // Mostra o "check"

      // Atualiza o ícone e o texto do botão principal do dropdown
      if(activeThemeIcon && svgOfActiveBtn){
           activeThemeIcon.setAttribute('href', svgOfActiveBtn)
      }
      const themeSwitcherLabel = `Theme (${btnToActivate.dataset.bsThemeValue})`
      themeSwitcher.setAttribute('aria-label', themeSwitcherLabel)

      // Atualiza o texto para telas pequenas (opcional)
      if(themeSwitcherText) {
        themeSwitcherText.textContent = btnToActivate.textContent.trim(); // Pega o texto do botão ativo
      }


      if (focus) { themeSwitcher.focus() }
    }

    // Listener para mudança de preferência do sistema operacional
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      const storedTheme = getStoredTheme()
      if (storedTheme !== 'light' && storedTheme !== 'dark') { // Só atualiza se o usuário deixou em 'auto'
        const preferred = getPreferredTheme();
        setTheme(preferred)
        showActiveTheme(preferred) // Atualiza o botão para refletir a mudança do OS
      }
    })

    // Configura estado inicial e listeners dos botões ao carregar a página
    window.addEventListener('DOMContentLoaded', () => {
      // Mostra qual tema está ativo no dropdown ao carregar
      showActiveTheme(getStoredTheme() || 'auto') // Mostra o salvo ou 'auto' como default visual

      // Adiciona listeners de clique aos botões do dropdown
      document.querySelectorAll('[data-bs-theme-value]')
        .forEach(toggle => {
          toggle.addEventListener('click', () => {
            const theme = toggle.getAttribute('data-bs-theme-value')
            setStoredTheme(theme) // Salva a escolha no localStorage ('light', 'dark' ou 'auto')
            setTheme(theme) // Aplica o tema (resolve 'auto' para light/dark no atributo html)
            showActiveTheme(theme, true) // Atualiza o dropdown para refletir a escolha
          })
        })
    })
  })()
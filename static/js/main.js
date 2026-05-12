/* ════════════════════════════════════════════
   LiftAGILE · main.js
   Handles:
     - Dark mode toggle (persisted via localStorage)
     - Collapsible sidebar (persisted via localStorage)
     - Bar chart entrance animation
     - Flash message auto-dismiss
════════════════════════════════════════════ */

// Set theme toggle icons before the first paint.
// main.js is at the end of <body> so the DOM is already available here,
// meaning this runs before any frame is rendered — no flash, no CSS cascade delay.
(function () {
  var t    = localStorage.getItem('liftlab-theme') || 'light';
  var sun  = document.getElementById('themeIconDark');   // sun icon → shown in dark mode
  var moon = document.getElementById('themeIconLight');  // moon icon → shown in light mode
  if (sun && moon) {
    sun.style.display  = t === 'dark' ? 'block' : 'none';
    moon.style.display = t === 'dark' ? 'none'  : 'block';
  }
})();

// Remove the preloading class after the first paint so CSS transitions
// are suppressed during initial theme/sidebar application but work normally
// for all subsequent user interactions.
requestAnimationFrame(() => requestAnimationFrame(() => {
  document.documentElement.classList.remove('preloading');
}));

document.addEventListener('DOMContentLoaded', () => {
   // ── 1. RANK ACCENT THEME ─────────────────────
  (function applyRankTheme() {
    const tier = document.body.dataset.userTier || 'unranked';

    const themes = {
      unranked: { accent: '#534AB7', hover: '#3C3489', light: '#EEEDFE', dark: '#3C3489' },
      bronze:   { accent: '#CD7F32', hover: '#9A5A20', light: 'rgba(205,127,50,0.13)', dark: '#8A4F1D' },
      silver:   { accent: '#A8A9AD', hover: '#7E8085', light: 'rgba(168,169,173,0.14)', dark: '#66686D' },
      gold:     { accent: '#EF9F27', hover: '#C77D12', light: 'rgba(239,159,39,0.14)', dark: '#A9650C' },
      platinum: { accent: '#4DD0C4', hover: '#2AA99E', light: 'rgba(77,208,196,0.14)', dark: '#1C8078' },
      diamond:  { accent: '#8AB4F8', hover: '#5C8FE0', light: 'rgba(138,180,248,0.16)', dark: '#3F6EB8' },
      emerald:  { accent: '#22C55E', hover: '#16A34A', light: 'rgba(34,197,94,0.14)', dark: '#15803D' },
      champion: { accent: '#F59E0B', hover: '#D97706', light: 'rgba(245,158,11,0.15)', dark: '#B45309' }
    };

    const selected = themes[tier] || themes.unranked;
    const root = document.documentElement;

    root.style.setProperty('--accent', selected.accent);
    root.style.setProperty('--accent-hover', selected.hover);
    root.style.setProperty('--accent-light', selected.light);
    root.style.setProperty('--accent-dark', selected.dark);
  })();
  // ── 2. DARK MODE ─────────────────────────────
  const THEME_KEY = 'liftlab-theme';

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.style.background  = theme === 'dark' ? '#0F0F0E' : '';
    document.documentElement.style.colorScheme = theme === 'dark' ? 'dark'    : 'light';
    const iconLight = document.getElementById('themeIconLight');
    const iconDark  = document.getElementById('themeIconDark');
    if (iconLight && iconDark) {
      iconLight.style.display = theme === 'dark' ? 'none'  : 'block';
      iconDark.style.display  = theme === 'dark' ? 'block' : 'none';
    }
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    const next    = current === 'dark' ? 'light' : 'dark';
    localStorage.setItem(THEME_KEY, next);
    applyTheme(next);
  }

  // Apply saved theme immediately (before paint to avoid flash)
  const savedTheme = localStorage.getItem(THEME_KEY) || 'light';
  applyTheme(savedTheme);

  // Wire up toggle button
  const themeBtn = document.getElementById('themeToggleBtn');
  if (themeBtn) themeBtn.addEventListener('click', toggleTheme);

  // Expose globally so inline onclick handlers also work
  window.toggleTheme = toggleTheme;


  // ── 2. COLLAPSIBLE SIDEBAR ───────────────────
  const SIDEBAR_KEY = 'liftlab-sidebar';
  const sidebar     = document.querySelector('.sidebar');
  const collapseBtn = document.getElementById('sidebarCollapseBtn');

  function applySidebar(collapsed) {
    if (!sidebar) return;
    if (collapsed) {
      sidebar.classList.add('collapsed');
      document.documentElement.setAttribute('data-sidebar', 'collapsed');
    } else {
      sidebar.classList.remove('collapsed');
      document.documentElement.removeAttribute('data-sidebar');
    }
  }

  function toggleSidebar() {
    const isCollapsed = sidebar.classList.contains('collapsed');
    const next = !isCollapsed;
    localStorage.setItem(SIDEBAR_KEY, next ? 'collapsed' : 'open');
    applySidebar(next);
  }

  // Apply saved state
  const savedSidebar = localStorage.getItem(SIDEBAR_KEY);
  applySidebar(savedSidebar === 'collapsed');

  // Wire up button
  if (collapseBtn) collapseBtn.addEventListener('click', toggleSidebar);
  window.toggleSidebar = toggleSidebar;


  // ── 3. BAR CHART ANIMATION ───────────────────
  document.querySelectorAll('.bar-fill').forEach(bar => {
    const target = bar.style.height;
    bar.style.height = '0';
    requestAnimationFrame(() => {
      bar.style.transition = 'height 0.5s cubic-bezier(0.4,0,0.2,1)';
      bar.style.height = target;
    });
  });


 // ── 4. FLASH MESSAGE AUTO-DISMISS ────────────
  document.querySelectorAll('.flash').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity 0.4s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 400);
    }, 3500);
  });

  // ── 5. PASSWORD TOGGLE ───────────────────────
  document.querySelectorAll('.toggle-password').forEach(button => {
    button.addEventListener('click', () => {
      const input = button.previousElementSibling;
      const icon = button.querySelector('i');

      if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
      } else {
        input.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
      }
    });
  });

});

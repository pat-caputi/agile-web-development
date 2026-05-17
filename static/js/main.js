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

  // ── 1. DARK MODE ─────────────────────────────
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

  // Inline script already set data-theme; just sync the icons/label
  applyTheme(document.documentElement.getAttribute('data-theme') || 'light');

  // Live OS tracking — only fires when user has no active session override
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
    if (!localStorage.getItem(THEME_KEY)) applyTheme(e.matches ? 'dark' : 'light');
  });

  const themeBtn = document.getElementById('themeToggleBtn');
  if (themeBtn) themeBtn.addEventListener('click', toggleTheme);
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

  // ── 6. CARD ENTRANCE ANIMATION (vanilla JS — works before jQuery loads) ──
  document.querySelectorAll('.fd-card, .plan-card, .pp-plan-card').forEach((el, i) => {
    setTimeout(() => el.classList.add('card-visible'), i * 40);
  });

});

// ── jQuery: flash message auto-dismiss & Bootstrap alert wiring ──────────────
$(function () {
  // Auto-dismiss Bootstrap alerts after 4 seconds
  setTimeout(function () {
    $('.flash-msg').fadeTo(400, 0, function () {
      $(this).slideUp(200, function () { $(this).remove(); });
    });
  }, 4000);

  // Wire Bootstrap dismiss button for any manually-rendered alerts
  $(document).on('click', '.flash-msg .btn-close', function () {
    $(this).closest('.flash-msg').fadeTo(300, 0, function () {
      $(this).slideUp(150, function () { $(this).remove(); });
    });
  });

  // Card entrance animation handled by vanilla JS above (section 6)
});

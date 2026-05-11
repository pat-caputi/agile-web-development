/* ════════════════════════════════════════════
   LiftAGILE · main.js
   Handles:
     - Dark mode toggle (persisted via localStorage)
     - Collapsible sidebar (persisted via localStorage)
     - Bar chart entrance animation
     - Flash message auto-dismiss
════════════════════════════════════════════ */

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
    // Swap the icon in the toggle button
    const iconLight = document.getElementById('themeIconLight');
    const iconDark  = document.getElementById('themeIconDark');
    if (iconLight && iconDark) {
      iconLight.style.display = theme === 'dark' ? 'none'  : 'block';
      iconDark.style.display  = theme === 'dark' ? 'block' : 'none';
    }
    const label = document.getElementById('themeToggleLabel');
    if (label) label.textContent = theme === 'dark' ? 'Light mode' : 'Dark mode';
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

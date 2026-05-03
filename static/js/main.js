document.addEventListener('DOMContentLoaded', () => {
  // Highlight active nav link based on current filename
  const page = location.pathname.split('/').pop() || 'dashboard.html';
  document.querySelectorAll('.nav-link').forEach(link => {
    const href = link.getAttribute('href').split('/').pop();
    if (href === page) link.classList.add('active');
    else link.classList.remove('active');
  });

  // Animate bar chart bars on load
  document.querySelectorAll('.bar-fill').forEach(bar => {
    const target = bar.style.height;
    bar.style.height = '0';
    requestAnimationFrame(() => {
      bar.style.transition = 'height 0.5s cubic-bezier(0.4,0,0.2,1)';
      bar.style.height = target;
    });
  });

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

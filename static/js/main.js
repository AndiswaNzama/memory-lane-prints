// ---- Mobile nav toggle ----
document.getElementById('navToggle')?.addEventListener('click', () => {
  document.getElementById('navLinks')?.classList.toggle('open');
});

// ---- Navbar shadow on scroll ----
const navbar = document.querySelector('.navbar');
if (navbar) {
  window.addEventListener('scroll', () => {
    navbar.classList.toggle('scrolled', window.scrollY > 20);
  }, { passive: true });
}

// ---- Auto-dismiss flash messages ----
document.querySelectorAll('.flash').forEach(el => {
  setTimeout(() => {
    el.style.transition = 'opacity .4s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 400);
  }, 5000);
});

// ---- Scroll reveal (Intersection Observer) ----
const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (!entry.isIntersecting) return;
    const el = entry.target;
    const delay = parseInt(el.dataset.delay || '0', 10);
    setTimeout(() => el.classList.add('revealed'), delay);
    revealObserver.unobserve(el);
  });
}, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

document.querySelectorAll('[data-animate]').forEach(el => revealObserver.observe(el));

// ---- Staggered children inside [data-stagger] groups ----
document.querySelectorAll('[data-stagger]').forEach(group => {
  const type  = group.dataset.stagger || '';
  const step  = parseInt(group.dataset.step  || '80', 10);
  Array.from(group.children).forEach((child, i) => {
    child.setAttribute('data-animate', type);
    child.setAttribute('data-delay', i * step);
    revealObserver.observe(child);
  });
});

// ---- Duplicate marquee content for seamless loop ----
document.querySelectorAll('.marquee-track').forEach(track => {
  track.innerHTML += track.innerHTML;
});

// ---- Lucide icon refresh after dynamic DOM changes ----
if (typeof lucide !== 'undefined') lucide.createIcons();

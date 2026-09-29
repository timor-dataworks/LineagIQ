/**
 * LineagIQ Product & Architecture Website Scripts
 */

document.addEventListener('DOMContentLoaded', () => {
  initLightbox();
  initArchTabs();
  initCopyButtons();
  initNavScroll();
  initMobileNav();
  initFaqAccordion();
});

// FAQ Accordion (closes other items when one is opened for clean focus)
function initFaqAccordion() {
  const faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach(item => {
    item.addEventListener('toggle', () => {
      if (item.open) {
        faqItems.forEach(otherItem => {
          if (otherItem !== item && otherItem.open) {
            otherItem.open = false;
          }
        });
      }
    });
  });
}

// Mobile Hamburger Navigation Drawer
function initMobileNav() {
  const toggleBtn = document.getElementById('nav-toggle');
  const navLinks = document.getElementById('nav-links');

  if (!toggleBtn || !navLinks) return;

  toggleBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleBtn.classList.toggle('open');
    navLinks.classList.toggle('open');
  });

  // Close mobile drawer when clicking any nav link
  const links = navLinks.querySelectorAll('.nav-link');
  links.forEach(link => {
    link.addEventListener('click', () => {
      toggleBtn.classList.remove('open');
      navLinks.classList.remove('open');
    });
  });

  // Close drawer if user clicks outside
  document.addEventListener('click', (e) => {
    if (!toggleBtn.contains(e.target) && !navLinks.contains(e.target) && navLinks.classList.contains('open')) {
      toggleBtn.classList.remove('open');
      navLinks.classList.remove('open');
    }
  });

  // Close on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && navLinks.classList.contains('open')) {
      toggleBtn.classList.remove('open');
      navLinks.classList.remove('open');
    }
  });
}

// Lightbox Modal for Full-Resolution Product Screenshots
function initLightbox() {
  const modal = document.getElementById('lightbox-modal');
  const modalImg = document.getElementById('lightbox-img');
  const modalCaption = document.getElementById('lightbox-caption');
  const closeBtn = document.getElementById('lightbox-close');

  if (!modal || !modalImg || !closeBtn) return;

  const cards = document.querySelectorAll('.screenshot-card, .showcase-inner');
  cards.forEach(card => {
    card.addEventListener('click', () => {
      const img = card.querySelector('img');
      if (!img) return;

      modalImg.src = img.src;
      modalCaption.textContent = img.alt || card.dataset.caption || 'LineagIQ Product Screenshot';
      modal.classList.add('active');
      document.body.style.overflow = 'hidden';
    });
  });

  const closeModal = () => {
    modal.classList.remove('active');
    document.body.style.overflow = '';
  };

  closeBtn.addEventListener('click', closeModal);
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('active')) {
      closeModal();
    }
  });
}

// Architecture Deep Dive Tab Navigation
function initArchTabs() {
  const tabBtns = document.querySelectorAll('.arch-tab-btn');
  const tabPanels = document.querySelectorAll('.arch-tab-panel');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.dataset.tab;

      tabBtns.forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-selected', 'false');
      });
      tabPanels.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');
      const targetPanel = document.getElementById(targetId);
      if (targetPanel) {
        targetPanel.classList.add('active');
      }
    });
  });
}

// Copy Code Snippets
function initCopyButtons() {
  const copyBtns = document.querySelectorAll('.copy-btn');

  copyBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.dataset.code;
      const codeEl = document.getElementById(targetId);
      if (!codeEl) return;

      navigator.clipboard.writeText(codeEl.textContent).then(() => {
        const originalText = btn.textContent;
        btn.textContent = 'Copied!';
        btn.style.color = '#10b981';
        btn.style.borderColor = '#10b981';

        setTimeout(() => {
          btn.textContent = originalText;
          btn.style.color = '';
          btn.style.borderColor = '';
        }, 2000);
      });
    });
  });
}

// Active navigation highlight on scroll
function initNavScroll() {
  const sections = document.querySelectorAll('section[id]');
  const navLinks = document.querySelectorAll('.nav-link');

  const onScroll = () => {
    let current = '';
    const scrollY = window.pageYOffset;
    const windowHeight = window.innerHeight;
    const bodyHeight = document.documentElement.scrollHeight;

    // If near the bottom of the page, highlight the last section (quickstart)
    if (scrollY + windowHeight >= bodyHeight - 120) {
      const lastSection = sections[sections.length - 1];
      if (lastSection) {
        current = lastSection.getAttribute('id');
      }
    } else {
      sections.forEach(section => {
        const sectionHeight = section.offsetHeight;
        const sectionTop = section.offsetTop - 120;
        if (scrollY >= sectionTop && scrollY < sectionTop + sectionHeight) {
          current = section.getAttribute('id');
        }
      });
    }

    if (!current && sections.length > 0) {
      current = sections[0].getAttribute('id');
    }

    navLinks.forEach(link => {
      if (link.getAttribute('href') === `#${current}`) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    });
  };

  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
}

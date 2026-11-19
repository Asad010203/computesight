/* Blog: reading progress + table-of-contents highlighting */
(() => {
  'use strict';
  const bar = document.querySelector('.progress');
  const article = document.querySelector('.prose');
  if (bar && article) {
    const update = () => {
      const r = article.getBoundingClientRect();
      const total = r.height - innerHeight;
      const p = total > 0 ? Math.min(1, Math.max(0, -r.top / total)) : 1;
      bar.style.transform = `scaleX(${p})`;
    };
    addEventListener('scroll', update, { passive: true });
    addEventListener('resize', update);
    update();
  }

  const links = [...document.querySelectorAll('.toc a')];
  if (!links.length) return;
  const byId = new Map(links.map((a) => [a.hash.slice(1), a]));
  const io = new IntersectionObserver((entries) => {
    entries.forEach((en) => {
      if (!en.isIntersecting) return;
      links.forEach((a) => a.classList.remove('active'));
      const a = byId.get(en.target.id);
      if (a) a.classList.add('active');
    });
  }, { rootMargin: '-20% 0px -70% 0px' });
  byId.forEach((_, id) => { const h = document.getElementById(id); if (h) io.observe(h); });
})();

/* Blog index: filter articles by topic */
(() => {
  'use strict';
  const buttons = [...document.querySelectorAll('.filter')];
  const cards = [...document.querySelectorAll('#postGrid .post-card')];
  if (!buttons.length) return;
  buttons.forEach((b) => b.addEventListener('click', () => {
    const f = b.dataset.filter;
    buttons.forEach((x) => { x.classList.toggle('active', x === b); x.setAttribute('aria-pressed', x === b); });
    cards.forEach((c, i) => {
      const show = f === 'all' || c.dataset.cat === f;
      c.hidden = !show;
      // only feature the first article on the unfiltered view
      c.classList.toggle('featured', f === 'all' && i === 0);
    });
  }));
})();

/* Junjie Chen — site interactions. Vanilla, no dependencies, no network.
 *
 * Everything here is an enhancement. The pre-paint script in <head> already
 * swapped `no-js` for `js` on <html>, and the stylesheet only hides `.reveal`
 * content under `.js` — so if this file fails to load, the page is still
 * complete and readable, just static. */
(function () {
  'use strict';

  var root = document.documentElement;
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* Announce that THIS file is running. The stylesheet hides .reveal content
     only under .reveal-on, so a failed or blocked main.js leaves the page
     complete rather than blank. Must happen before anything that can throw. */
  root.classList.add('reveal-on');

  /* ---- Theme toggle (persisted) ---- */
  var toggle = document.getElementById('theme-toggle');

  function describeToggle() {
    if (!toggle) return;
    var goingTo = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    toggle.setAttribute('aria-label', 'Switch to ' + goingTo + ' theme');
    toggle.setAttribute('title', 'Switch to ' + goingTo + ' theme');
  }

  if (toggle) {
    describeToggle();
    toggle.addEventListener('click', function () {
      var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('theme', next); } catch (e) {}
      describeToggle();
    });
  }

  /* ---- Mobile nav ---- */
  var burger = document.getElementById('nav-burger');
  var links = document.getElementById('nav-links');

  function setNav(open) {
    if (!links) return;
    links.classList.toggle('is-open', open);
    /* Hold the page still while the overlay is up. */
    document.body.style.overflow = open ? 'hidden' : '';
    if (burger) {
      burger.setAttribute('aria-expanded', open ? 'true' : 'false');
      burger.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    }
  }

  function closeNav() { setNav(false); }

  if (burger && links) {
    burger.addEventListener('click', function (e) {
      e.stopPropagation();
      setNav(!links.classList.contains('is-open'));
    });
    links.addEventListener('click', function (e) {
      if (e.target.closest('a')) closeNav();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeNav();
    });
    /* Tapping the scrim — anything outside the panel — dismisses it. */
    document.addEventListener('click', function (e) {
      if (!links.classList.contains('is-open')) return;
      if (!links.contains(e.target) && !burger.contains(e.target)) closeNav();
    });
  }

  /* ---- Footer year (the build bakes one in; this keeps it honest) ---- */
  var year = document.getElementById('year');
  if (year) year.textContent = String(new Date().getFullYear());

  /* ---- Reveal on scroll ---- */
  var reveals = document.querySelectorAll('.reveal');
  if (reduceMotion || !('IntersectionObserver' in window)) {
    Array.prototype.forEach.call(reveals, function (el) { el.classList.add('is-in'); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-in');
          io.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
    Array.prototype.forEach.call(reveals, function (el) { io.observe(el); });
  }

  /* ---- Scrollspy.
   * Nav hrefs are page-qualified ("index.html#about"), so match on the hash
   * only when the target section actually exists on this page. */
  var navAnchors = Array.prototype.slice.call(document.querySelectorAll('.nav__links a'));
  var spied = [];
  navAnchors.forEach(function (a) {
    var hash = (a.getAttribute('href') || '').split('#')[1];
    var section = hash ? document.getElementById(hash) : null;
    if (section) spied.push({ anchor: a, section: section });
  });

  if (spied.length && 'IntersectionObserver' in window) {
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        spied.forEach(function (pair) {
          var on = pair.section === entry.target;
          pair.anchor.classList.toggle('is-active', on);
          if (on) pair.anchor.setAttribute('aria-current', 'page');
          else pair.anchor.removeAttribute('aria-current');
        });
      });
    }, { rootMargin: '-45% 0px -50% 0px', threshold: 0 });
    spied.forEach(function (pair) { spy.observe(pair.section); });
  }

  /* ---- Reading progress (post pages only) ---- */
  var progress = document.getElementById('progress');
  var article = document.querySelector('.post');
  if (progress && article) {
    var tick = function () {
      var start = article.offsetTop;
      var span = article.offsetHeight - window.innerHeight;
      var seen = span > 0 ? (window.scrollY - start) / span : 1;
      progress.style.width = Math.max(0, Math.min(1, seen)) * 100 + '%';
    };
    window.addEventListener('scroll', tick, { passive: true });
    window.addEventListener('resize', tick);
    tick();
  }

  /* ---- Copy buttons on code blocks.
   * Injected rather than authored, so a no-JS reader never sees a dead button. */
  Array.prototype.forEach.call(document.querySelectorAll('.codeblock'), function (block) {
    var bar = block.querySelector('.codeblock__bar');
    var code = block.querySelector('pre');
    if (!bar || !code || !navigator.clipboard) return;

    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'codeblock__copy';
    button.textContent = 'copy';
    button.addEventListener('click', function () {
      navigator.clipboard.writeText(code.textContent.replace(/\s+$/, '')).then(function () {
        button.textContent = 'copied';
        setTimeout(function () { button.textContent = 'copy'; }, 1600);
      }, function () {
        button.textContent = 'failed';
        setTimeout(function () { button.textContent = 'copy'; }, 1600);
      });
    });
    bar.appendChild(button);
  });

  /* ---- Tag filtering: the writing index and the publications list.
   * The publication chips ship `hidden`, so a reader without this script
   * never sees a button that does nothing; the writing chips are generated
   * visible by build.py and simply stay inert. */
  function wireFilter(filterId, listId, emptyId) {
    var filter = document.getElementById(filterId);
    var list = document.getElementById(listId);
    if (!filter || !list) return;
    var items = Array.prototype.slice.call(list.querySelectorAll('[data-tags]'));
    var empty = document.getElementById(emptyId);
    filter.hidden = false;

    filter.addEventListener('click', function (e) {
      var chip = e.target.closest('.chip');
      if (!chip) return;
      var wanted = chip.getAttribute('data-tag');

      Array.prototype.forEach.call(filter.querySelectorAll('.chip'), function (c) {
        var on = c === chip;
        c.classList.toggle('is-on', on);
        c.setAttribute('aria-pressed', on ? 'true' : 'false');
      });

      var shown = 0;
      items.forEach(function (item) {
        var tags = (item.getAttribute('data-tags') || '').split('|');
        var show = wanted === '*' || tags.indexOf(wanted) !== -1;
        item.hidden = !show;
        if (show) shown++;
      });
      if (empty) empty.hidden = shown !== 0;
    });
  }
  wireFilter('tag-filter', 'postlist', 'postlist-empty');
  wireFilter('pub-filter', 'pub-list', 'pub-empty');
})();

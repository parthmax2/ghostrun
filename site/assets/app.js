(function () {
  "use strict";

  /* ---------------------------------------------------------------------
     Site root, resolved from this script's own URL so search-index links
     work under any deploy path (GitHub Pages' /ghostrun/ subpath, Vercel's
     root domain, or a plain local file:// open).
     --------------------------------------------------------------------- */
  var SITE_BASE = (function () {
    var el = document.currentScript;
    if (!el) return "";
    return el.src.replace(/assets\/app\.js(\?.*)?$/, "");
  })();

  /* ---------------------------------------------------------------------
     Theme toggle: localStorage -> system preference -> dark default.
     --------------------------------------------------------------------- */
  var root = document.documentElement;
  var THEME_KEY = "ghostrun-theme";

  function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    var btn = document.getElementById("theme-toggle");
    if (btn) btn.setAttribute("aria-label", "Switch to " + (theme === "dark" ? "light" : "dark") + " mode");
  }

  function initTheme() {
    var stored = localStorage.getItem(THEME_KEY);
    var theme = stored || (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
    applyTheme(theme);
  }

  function toggleTheme() {
    var current = root.getAttribute("data-theme") === "light" ? "light" : "dark";
    var next = current === "light" ? "dark" : "light";
    localStorage.setItem(THEME_KEY, next);
    applyTheme(next);
  }

  initTheme();

  document.addEventListener("DOMContentLoaded", function () {
    var themeBtn = document.getElementById("theme-toggle");
    if (themeBtn) themeBtn.addEventListener("click", toggleTheme);

    /* -------------------------------------------------------------------
       Mobile sidebar drawer
       ------------------------------------------------------------------- */
    var navToggle = document.getElementById("nav-toggle");
    var sidebar = document.querySelector(".sidebar");
    var scrim = document.querySelector(".scrim");

    function closeDrawer() {
      if (sidebar) sidebar.classList.remove("open");
      if (scrim) scrim.classList.remove("open");
    }
    function openDrawer() {
      if (sidebar) sidebar.classList.add("open");
      if (scrim) scrim.classList.add("open");
    }
    if (navToggle) {
      navToggle.addEventListener("click", function () {
        if (sidebar && sidebar.classList.contains("open")) closeDrawer();
        else openDrawer();
      });
    }
    if (scrim) scrim.addEventListener("click", closeDrawer);

    /* -------------------------------------------------------------------
       Copy-to-clipboard on every code block
       ------------------------------------------------------------------- */
    document.querySelectorAll(".article pre").forEach(function (pre) {
      var btn = document.createElement("button");
      btn.className = "copy-btn";
      btn.type = "button";
      btn.textContent = "Copy";
      btn.addEventListener("click", function () {
        var code = pre.querySelector("code");
        var text = code ? code.textContent : pre.textContent;
        navigator.clipboard.writeText(text).then(function () {
          btn.textContent = "Copied";
          btn.classList.add("copied");
          setTimeout(function () {
            btn.textContent = "Copy";
            btn.classList.remove("copied");
          }, 1500);
        });
      });
      pre.appendChild(btn);
    });

    /* -------------------------------------------------------------------
       Auto-built "on this page" TOC from the article's h2/h3, with a
       scrollspy highlighting whichever section is currently in view.
       ------------------------------------------------------------------- */
    var tocList = document.getElementById("toc-list");
    var article = document.querySelector(".article");
    if (tocList && article) {
      var headings = article.querySelectorAll("h2, h3");
      var links = [];
      headings.forEach(function (h) {
        if (!h.id) {
          h.id = h.textContent
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/(^-|-$)/g, "");
        }
        var li = document.createElement("li");
        var a = document.createElement("a");
        a.href = "#" + h.id;
        a.textContent = h.textContent;
        if (h.tagName === "H3") a.classList.add("toc-h3");
        li.appendChild(a);
        tocList.appendChild(li);
        links.push({ id: h.id, el: a });
      });

      if (links.length && "IntersectionObserver" in window) {
        var observer = new IntersectionObserver(
          function (entries) {
            entries.forEach(function (entry) {
              var match = links.find(function (l) {
                return l.id === entry.target.id;
              });
              if (!match) return;
              if (entry.isIntersecting) {
                links.forEach(function (l) {
                  l.el.classList.remove("active");
                });
                match.el.classList.add("active");
              }
            });
          },
          { rootMargin: "-20% 0px -70% 0px" }
        );
        headings.forEach(function (h) {
          observer.observe(h);
        });
      }
    } else {
      var tocBox = document.querySelector(".toc");
      if (tocBox) tocBox.style.display = "none";
    }

    /* -------------------------------------------------------------------
       Client-side search over window.GHOSTRUN_SEARCH_INDEX
       ------------------------------------------------------------------- */
    var input = document.getElementById("search-input");
    var results = document.getElementById("search-results");
    if (input && results && window.GHOSTRUN_SEARCH_INDEX) {
      var index = window.GHOSTRUN_SEARCH_INDEX;
      var activeIndex = -1;

      function render(matches, query) {
        results.innerHTML = "";
        if (!matches.length) {
          var empty = document.createElement("div");
          empty.className = "search-empty";
          empty.textContent = 'No results for "' + query + '"';
          results.appendChild(empty);
          results.classList.add("open");
          return;
        }
        matches.slice(0, 8).forEach(function (m, i) {
          var a = document.createElement("a");
          a.href = SITE_BASE + m.url;
          a.className = "search-result";
          if (i === 0) a.classList.add("active");
          a.innerHTML =
            '<span class="result-title">' +
            m.title +
            ' <span class="result-crumb">' +
            m.section +
            "</span></span>" +
            '<span class="result-excerpt">' +
            m.excerpt +
            "</span>";
          results.appendChild(a);
        });
        results.classList.add("open");
        activeIndex = 0;
      }

      function search(query) {
        var q = query.trim().toLowerCase();
        if (!q) {
          results.classList.remove("open");
          return;
        }
        var matches = index.filter(function (entry) {
          return (
            entry.title.toLowerCase().indexOf(q) !== -1 ||
            entry.excerpt.toLowerCase().indexOf(q) !== -1 ||
            (entry.keywords || "").toLowerCase().indexOf(q) !== -1
          );
        });
        render(matches, query);
      }

      input.addEventListener("input", function () {
        search(input.value);
      });
      input.addEventListener("focus", function () {
        if (input.value.trim()) search(input.value);
      });
      document.addEventListener("click", function (e) {
        if (!results.contains(e.target) && e.target !== input) {
          results.classList.remove("open");
        }
      });
      input.addEventListener("keydown", function (e) {
        var items = Array.prototype.slice.call(results.querySelectorAll(".search-result"));
        if (!items.length) return;
        if (e.key === "ArrowDown") {
          e.preventDefault();
          activeIndex = Math.min(activeIndex + 1, items.length - 1);
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          activeIndex = Math.max(activeIndex - 1, 0);
        } else if (e.key === "Enter") {
          if (items[activeIndex]) window.location.href = items[activeIndex].getAttribute("href");
          return;
        } else {
          return;
        }
        items.forEach(function (it, i) {
          it.classList.toggle("active", i === activeIndex);
        });
      });
    }
  });
})();

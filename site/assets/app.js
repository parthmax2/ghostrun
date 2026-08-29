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
     Theme: Permanent pure sleek dark mode.
     --------------------------------------------------------------------- */
  var root = document.documentElement;
  root.setAttribute("data-theme", "dark");

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
        if (!navigator.clipboard || !navigator.clipboard.writeText) {
          btn.textContent = "Unavailable";
          setTimeout(function () {
            btn.textContent = "Copy";
          }, 1500);
          return;
        }
        navigator.clipboard.writeText(text)
          .then(function () {
            btn.textContent = "Copied";
            btn.classList.add("copied");
            setTimeout(function () {
              btn.textContent = "Copy";
              btn.classList.remove("copied");
            }, 1500);
          })
          .catch(function () {
            btn.textContent = "Failed";
            setTimeout(function () {
              btn.textContent = "Copy";
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
          var title = document.createElement("span");
          title.className = "result-title";
          title.appendChild(document.createTextNode(m.title + " "));

          var crumb = document.createElement("span");
          crumb.className = "result-crumb";
          crumb.textContent = m.section;
          title.appendChild(crumb);

          var excerpt = document.createElement("span");
          excerpt.className = "result-excerpt";
          excerpt.textContent = m.excerpt;

          a.appendChild(title);
          a.appendChild(excerpt);
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

    /* ---------------------------------------------------------------------
       Autonomous Roaming Mascot Companion (Patrols, Climbs, Jumps & Tips)
       --------------------------------------------------------------------- */
    (function initRoamingMascot() {
      // Don't duplicate if already exists
      if (document.getElementById("ghostrun-roaming-pet")) return;

      var petContainer = document.createElement("div");
      petContainer.id = "ghostrun-roaming-pet";
      petContainer.style.cssText = [
        "position: fixed;",
        "bottom: 24px;",
        "right: 40px;",
        "z-index: 9999;",
        "display: flex;",
        "flex-direction: column;",
        "align-items: center;",
        "cursor: grab;",
        "user-select: none;",
        "touch-action: none;",
        "transition: transform 0.2s cubic-bezier(0.2, 0.8, 0.2, 1), bottom 0.5s ease, right 0.5s ease;"
      ].join(" ");

      // Speech / Tip Bubble
      var bubble = document.createElement("div");
      bubble.id = "roaming-pet-bubble";
      bubble.style.cssText = [
        "background: rgba(16, 18, 26, 0.95);",
        "border: 1px solid rgba(255, 51, 75, 0.4);",
        "color: #ffffff;",
        "font-family: var(--font-mono, monospace);",
        "font-size: 11px;",
        "padding: 6px 12px;",
        "border-radius: 8px;",
        "margin-bottom: 8px;",
        "box-shadow: 0 8px 24px rgba(0,0,0,0.6);",
        "white-space: nowrap;",
        "opacity: 0;",
        "transform: translateY(6px);",
        "transition: opacity 0.3s, transform 0.3s;",
        "pointer-events: none;"
      ].join(" ");
      bubble.textContent = "pytest for AI apps!";

      // Sprite Element
      var petSprite = document.createElement("div");
      petSprite.style.cssText = [
        "width: 72px;",
        "height: 78px;",
        "background: url('" + SITE_BASE + "assets/spritesheet.png') 0px 0px no-repeat;",
        "background-size: 576px 702px;",
        "image-rendering: pixelated;",
        "filter: drop-shadow(0 0 16px rgba(255, 51, 75, 0.55));",
        "transition: transform 0.15s ease;"
      ].join(" ");
      petSprite.title = "Drag me around or click to interact!";

      petContainer.appendChild(bubble);
      petContainer.appendChild(petSprite);
      document.body.appendChild(petContainer);

      // Spritesheet row mappings:
      // 0: idle (8 frames)
      // 1: run (8 frames)
      // 3: wave (8 frames)
      // 4: jump (8 frames)
      // 5: salute / fail (8 frames)
      // 7: thinking (8 frames)
      // 8: celebration (8 frames)
      var frame = 0;
      var currentRow = 0;
      var isFacingLeft = false;
      var posX = window.innerWidth - 120;
      var posY = 24;

      function updateSpriteFrame() {
        frame = (frame + 1) % 8;
        petSprite.style.backgroundPosition = "-" + (frame * 72) + "px -" + (currentRow * 78) + "px";
        petSprite.style.transform = isFacingLeft ? "scaleX(-1)" : "scaleX(1)";
      }
      var animTimer = setInterval(updateSpriteFrame, 110);

      // Bubble tips library
      var quotes = [
        "pytest for AI apps!",
        "Replay LLM tests in 0.04s ($0 cost)!",
        "Run `ghostrun init` to start!",
        "Self-improving prompts with `ghostrun craft` ⚡",
        "100% deterministic regression testing!",
        "Watching your code patrol...",
        "Zero API flakiness on CI/CD!",
        "All tests passing! 🚀"
      ];

      function speak(text, duration) {
        bubble.textContent = text || quotes[Math.floor(Math.random() * quotes.length)];
        bubble.style.opacity = "1";
        bubble.style.transform = "translateY(0px)";
        setTimeout(function() {
          bubble.style.opacity = "0";
          bubble.style.transform = "translateY(6px)";
        }, duration || 3500);
      }

      // Autonomous Patrol AI Engine
      var actions = ["idle", "walk", "jump", "think", "wave", "celebrate"];
      function runAutonomousAI() {
        var choice = actions[Math.floor(Math.random() * actions.length)];
        var vw = window.innerWidth;

        if (choice === "walk") {
          // Walk to a new random X position
          var targetX = Math.floor(Math.random() * (vw - 160)) + 40;
          isFacingLeft = targetX < posX;
          currentRow = 1; // Running animation
          
          var distance = Math.abs(targetX - posX);
          var duration = Math.max(1200, distance * 5);

          petContainer.style.transition = "left " + (duration/1000) + "s linear, bottom 0.4s ease";
          petContainer.style.left = targetX + "px";
          petContainer.style.right = "auto";
          posX = targetX;

          setTimeout(function() {
            currentRow = 0; // Return to idle
            if (Math.random() > 0.6) speak();
          }, duration);

        } else if (choice === "jump") {
          currentRow = 4; // Jump animation
          petContainer.style.transform = "translateY(-40px)";
          setTimeout(function() {
            petContainer.style.transform = "translateY(0px)";
            setTimeout(function() { currentRow = 0; }, 300);
          }, 350);

        } else if (choice === "think") {
          currentRow = 7;
          speak("Analyzing prompt latency...", 2500);
          setTimeout(function() { currentRow = 0; }, 3000);

        } else if (choice === "wave") {
          currentRow = 3;
          speak("Hey developer! Ready to test?", 2500);
          setTimeout(function() { currentRow = 0; }, 2600);

        } else if (choice === "celebrate") {
          currentRow = 8;
          speak("100% Tests Passed! 🎉", 2500);
          setTimeout(function() { currentRow = 0; }, 2800);

        } else {
          currentRow = 0; // Idle
        }
      }

      // Run an action every 5-9 seconds
      var aiInterval = setInterval(function() {
        if (!isDragging) {
          runAutonomousAI();
        }
      }, 6500);

      // Drag and Drop Mascot Interactivity
      var isDragging = false;
      var startMouseX = 0, startMouseY = 0;
      var elemStartX = 0, elemStartY = 0;

      petContainer.addEventListener("pointerdown", function(e) {
        isDragging = true;
        petContainer.style.cursor = "grabbing";
        petContainer.style.transition = "none";
        currentRow = 4; // Jumping / hanging in air

        startMouseX = e.clientX;
        startMouseY = e.clientY;

        var rect = petContainer.getBoundingClientRect();
        elemStartX = rect.left;
        elemStartY = window.innerHeight - rect.bottom;

        petContainer.setPointerCapture(e.pointerId);
      });

      petContainer.addEventListener("pointermove", function(e) {
        if (!isDragging) return;
        var dx = e.clientX - startMouseX;
        var dy = startMouseY - e.clientY;

        var newX = Math.max(10, Math.min(window.innerWidth - 90, elemStartX + dx));
        var newY = Math.max(10, Math.min(window.innerHeight - 100, elemStartY + dy));

        petContainer.style.left = newX + "px";
        petContainer.style.right = "auto";
        petContainer.style.bottom = newY + "px";
        posX = newX;
        posY = newY;
      });

      petContainer.addEventListener("pointerup", function(e) {
        if (!isDragging) return;
        isDragging = false;
        petContainer.style.cursor = "grab";
        petContainer.style.transition = "left 0.4s ease, bottom 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275)";
        
        // Gravity Drop back to bottom
        petContainer.style.bottom = "24px";
        posY = 24;
        currentRow = 8; // Celebrate landing!
        speak("Weeee! That was fun!", 2000);

        setTimeout(function() {
          currentRow = 0;
        }, 1200);
      });

      // Quick Click Action
      petContainer.addEventListener("click", function(e) {
        if (Math.abs(e.clientX - startMouseX) < 5 && Math.abs(e.clientY - startMouseY) < 5) {
          var quickStates = [3, 4, 7, 8];
          currentRow = quickStates[Math.floor(Math.random() * quickStates.length)];
          speak();
          setTimeout(function() { currentRow = 0; }, 2000);
        }
      });

      // React to User Scrolling
      window.addEventListener("scroll", function() {
        if (Math.random() > 0.85 && currentRow === 0) {
          currentRow = 3; // Wave
          setTimeout(function() { currentRow = 0; }, 1500);
        }
      });
    })();
  });
})();

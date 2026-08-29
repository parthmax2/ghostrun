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
       Living Mascot Companion Engine (DOM-Aware, Props, Reactions & Easter Eggs)
       --------------------------------------------------------------------- */
    (function initLivingMascotEngine() {
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
        "transition: transform 0.2s cubic-bezier(0.2, 0.8, 0.2, 1), left 0.6s ease, top 0.6s ease, bottom 0.6s ease;"
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
        "box-shadow: 0 8px 24px rgba(0,0,0,0.7);",
        "white-space: nowrap;",
        "opacity: 0;",
        "transform: translateY(6px);",
        "transition: opacity 0.3s, transform 0.3s;",
        "pointer-events: none;",
        "z-index: 30;"
      ].join(" ");
      bubble.textContent = "pytest for AI apps!";

      // Sprite Wrapper (holds sprite + dynamic props)
      var spriteWrap = document.createElement("div");
      spriteWrap.style.cssText = "position: relative; width: 72px; height: 78px;";

      // Sprite Element
      var petSprite = document.createElement("div");
      petSprite.style.cssText = [
        "width: 72px;",
        "height: 78px;",
        "background: url('" + SITE_BASE + "assets/spritesheet.png') 0px 0px no-repeat;",
        "background-size: 576px 702px;",
        "image-rendering: pixelated;",
        "transition: transform 0.15s ease;"
      ].join(" ");
      petSprite.title = "I am your GhostRun tactical pet! Click, drag, or watch me patrol!";

      // Dynamic Prop Slot
      var propSlot = document.createElement("div");
      propSlot.id = "mascot-prop-slot";

      spriteWrap.appendChild(petSprite);
      spriteWrap.appendChild(propSlot);
      petContainer.appendChild(bubble);
      petContainer.appendChild(spriteWrap);
      document.body.appendChild(petContainer);

      var frame = 0;
      var currentRow = 0;
      var isFacingLeft = false;
      var posX = window.innerWidth - 120;
      var posY = 24;
      var isPerched = false;
      var isDragging = false;
      var clickCount = 0;
      var clickTimer = null;

      function updateSpriteFrame() {
        frame = (frame + 1) % 8;
        petSprite.style.backgroundPosition = "-" + (frame * 72) + "px -" + (currentRow * 78) + "px";
        petSprite.style.transform = isFacingLeft ? "scaleX(-1)" : "scaleX(1)";
      }
      setInterval(updateSpriteFrame, 110);

      // Prop Manager
      function setProp(propName) {
        propSlot.innerHTML = "";
        if (!propName) return;
        var p = document.createElement("div");
        p.className = "mascot-prop-" + propName;
        propSlot.appendChild(p);
      }

      // Speech library
      var quotes = [
        "Replay LLM tests in 0.04s ($0 cost)!",
        "pytest for AI Apps 🚀",
        "Run `ghostrun init` to scaffold in 1 command!",
        "Self-improving prompts with `ghostrun craft` ⚡",
        "100% deterministic regression testing!",
        "Zero API flakiness on CI/CD!",
        "Patrolling codeblocks for flaky outputs..."
      ];

      function speak(text, duration) {
        bubble.textContent = text || quotes[Math.floor(Math.random() * quotes.length)];
        bubble.style.opacity = "1";
        bubble.style.transform = "translateY(0px)";
        setTimeout(function() {
          bubble.style.opacity = "0";
          bubble.style.transform = "translateY(6px)";
        }, duration || 3200);
      }

      // Particle Confetti Generator
      function spawnConfetti(originX, originY) {
        var colors = ["#ff334b", "#ffffff", "#00e676", "#ff9933"];
        for (var i = 0; i < 24; i++) {
          var dot = document.createElement("div");
          dot.className = "mascot-confetti";
          dot.style.left = (originX || posX + 36) + "px";
          dot.style.top = (originY || (window.innerHeight - posY - 36)) + "px";
          dot.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
          var dx = (Math.random() - 0.5) * 160 + "px";
          var dy = (Math.random() - 0.8) * 160 + "px";
          dot.style.setProperty("--dx", dx);
          dot.style.setProperty("--dy", dy);
          document.body.appendChild(dot);
          setTimeout((function(el) { return function() { el.remove(); }; })(dot), 1200);
        }
      }

      // 1. Autonomous Behavior Engine (Patrols, Perches & Props)
      var behaviorTree = ["walk_floor", "perch_codeblock", "laptop_hack", "coffee_break", "radar_scan", "wave", "celebrate"];

      function runAutonomousAI() {
        if (isDragging) return;
        var action = behaviorTree[Math.floor(Math.random() * behaviorTree.length)];

        if (action === "perch_codeblock") {
          // Find visible code blocks or cards to perch on
          var elements = Array.prototype.slice.call(document.querySelectorAll(".step-card, pre, .home-card, .video-frame"));
          var visibleElements = elements.filter(function(el) {
            var rect = el.getBoundingClientRect();
            return rect.top >= 80 && rect.bottom <= window.innerHeight - 80;
          });

          if (visibleElements.length > 0) {
            var targetEl = visibleElements[Math.floor(Math.random() * visibleElements.length)];
            var rect = targetEl.getBoundingClientRect();
            
            isPerched = true;
            currentRow = 4; // Jump up
            petContainer.style.transition = "all 0.8s cubic-bezier(0.16, 1, 0.3, 1)";
            petContainer.style.left = (rect.right - 90) + "px";
            petContainer.style.bottom = "auto";
            petContainer.style.top = Math.max(70, rect.top - 68) + "px";

            setTimeout(function() {
              currentRow = 7; // Thinking / inspecting
              setProp("laptop");
              speak("Inspecting code assertions...", 3000);

              setTimeout(function() {
                setProp(null);
                // Hop down
                currentRow = 4;
                petContainer.style.top = "auto";
                petContainer.style.bottom = "24px";
                isPerched = false;
                setTimeout(function() { currentRow = 0; }, 600);
              }, 5000);
            }, 800);
            return;
          }
        }

        if (action === "laptop_hack") {
          currentRow = 7; // Thinking
          setProp("laptop");
          speak("Running prompt craft optimizer...", 3500);
          setTimeout(function() {
            setProp(null);
            currentRow = 0;
          }, 4000);

        } else if (action === "coffee_break") {
          currentRow = 0; // Idle
          setProp("coffee");
          speak("Replay cache hit: 0.04s. Coffee time ☕", 3000);
          setTimeout(function() {
            setProp(null);
          }, 4500);

        } else if (action === "radar_scan") {
          currentRow = 7;
          setProp("radar");
          speak("Scanning for LLM regressions...", 3000);
          setTimeout(function() {
            setProp(null);
            currentRow = 8; // Celebrate clean scan
            speak("Zero regressions found! 🎯", 2000);
            setTimeout(function() { currentRow = 0; }, 2000);
          }, 3500);

        } else if (action === "walk_floor") {
          if (isPerched) return;
          var vw = window.innerWidth;
          var targetX = Math.floor(Math.random() * (vw - 160)) + 40;
          isFacingLeft = targetX < posX;
          currentRow = 1; // Running animation
          
          var distance = Math.abs(targetX - posX);
          var duration = Math.max(1200, distance * 5);

          petContainer.style.transition = "left " + (duration/1000) + "s linear, bottom 0.4s ease";
          petContainer.style.left = targetX + "px";
          petContainer.style.right = "auto";
          petContainer.style.bottom = "24px";
          posX = targetX;

          setTimeout(function() {
            currentRow = 0;
            if (Math.random() > 0.5) speak();
          }, duration);

        } else if (action === "wave") {
          currentRow = 3;
          speak("Tactical AI testing ready!", 2500);
          setTimeout(function() { currentRow = 0; }, 2500);

        } else if (action === "celebrate") {
          currentRow = 8;
          spawnConfetti();
          speak("100% Deterministic Pass! 🎉", 2500);
          setTimeout(function() { currentRow = 0; }, 2500);
        }
      }

      setInterval(runAutonomousAI, 7000);

      // 2. Developer Action Reaction Hooks
      // React when developer copies code
      document.addEventListener("copy", function() {
        currentRow = 8; // Celebrate
        setProp("laptop");
        spawnConfetti();
        speak("Code copied! Cached in 0.04s ($0 cost) ⚡", 3500);
        setTimeout(function() {
          setProp(null);
          currentRow = 0;
        }, 3500);
      });

      // React when developer searches
      var searchInput = document.getElementById("search-input");
      if (searchInput) {
        searchInput.addEventListener("focus", function() {
          currentRow = 3; // Wave
          speak("Looking for docs? Let's find it!", 2500);
          setTimeout(function() { currentRow = 0; }, 2500);
        });
      }

      // 3. Drag and Drop Physics
      var startMouseX = 0, startMouseY = 0;
      var elemStartX = 0, elemStartY = 0;

      petContainer.addEventListener("pointerdown", function(e) {
        isDragging = true;
        setProp(null);
        petContainer.style.cursor = "grabbing";
        petContainer.style.transition = "none";
        currentRow = 4; // Airborne jump
        isPerched = false;

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
        petContainer.style.top = "auto";
        posX = newX;
        posY = newY;
      });

      petContainer.addEventListener("pointerup", function(e) {
        if (!isDragging) return;
        isDragging = false;
        petContainer.style.cursor = "grab";
        petContainer.style.transition = "left 0.4s ease, bottom 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275)";
        
        petContainer.style.bottom = "24px";
        posY = 24;
        currentRow = 8; // Celebrate landing
        spawnConfetti();
        speak("Tactical landing executed!", 2000);

        setTimeout(function() { currentRow = 0; }, 1500);
      });

      // 4. Easter Eggs (Triple Click Party Mode + Konami Code)
      petContainer.addEventListener("click", function(e) {
        clickCount++;
        clearTimeout(clickTimer);
        clickTimer = setTimeout(function() {
          if (clickCount >= 3) {
            // Secret Rave Mode
            currentRow = 8;
            spawnConfetti();
            speak("SECRET UNLOCKED: GHOSTRUN RAVE MODE! 🪩⚡", 4000);
            document.body.style.filter = "invert(0.1) hue-rotate(45deg)";
            setTimeout(function() {
              document.body.style.filter = "none";
              currentRow = 0;
            }, 3000);
          } else if (clickCount === 1) {
            var quick = [3, 4, 7, 8];
            currentRow = quick[Math.floor(Math.random() * quick.length)];
            speak();
            setTimeout(function() { currentRow = 0; }, 2000);
          }
          clickCount = 0;
        }, 350);
      });

      // Konami Code Listener: ↑ ↑ ↓ ↓ ← → ← → B A
      var konami = [38, 38, 40, 40, 37, 39, 37, 39, 66, 65];
      var konamiIndex = 0;
      document.addEventListener("keydown", function(e) {
        if (e.keyCode === konami[konamiIndex]) {
          konamiIndex++;
          if (konamiIndex === konami.length) {
            konamiIndex = 0;
            spawnConfetti(window.innerWidth / 2, window.innerHeight / 2);
            speak("SQUAD CLONES DEPLOYED! 👻👻👻", 5000);
            currentRow = 8;
            // Spawn 2 clone buddies
            for (var c = 0; c < 2; c++) {
              var clone = petContainer.cloneNode(true);
              clone.style.left = (posX + (c === 0 ? -90 : 90)) + "px";
              document.body.appendChild(clone);
              (function(cl) {
                setTimeout(function() { cl.remove(); }, 6000);
              })(clone);
            }
          }
        } else {
          konamiIndex = 0;
        }
      });
    })();
  });
})();

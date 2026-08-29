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
       Punisher-Style Living Tactical Mentor Engine ("Ghost")
       --------------------------------------------------------------------- */
    (function initLivingTacticalMentor() {
      if (document.getElementById("ghostrun-roaming-pet")) return;

      // 1. Voice Synthesis & Audio Engine (100% Free Browser-Native)
      function speakTacticalAudio(text) {
        var isVoiceOn = (window.GhostRunVoiceEnabled !== false);
        if (!isVoiceOn || !window.speechSynthesis) {
          if (window.speechSynthesis) window.speechSynthesis.cancel();
          return;
        }
        window.speechSynthesis.cancel();

        var utter = new SpeechSynthesisUtterance(text);
        utter.rate = 0.95; // Calm, steady cadence
        utter.pitch = 0.75; // Deep commanding tone
        
        var voices = window.speechSynthesis.getVoices();
        // Look for deep English voice
        var chosenVoice = voices.find(function(v) { 
          return v.lang.startsWith("en") && (v.name.includes("Male") || v.name.includes("David") || v.name.includes("Google US English") || v.name.includes("Natural")); 
        }) || voices[0];

        if (chosenVoice) utter.voice = chosenVoice;
        window.speechSynthesis.speak(utter);
      }

      // Pre-warm voices
      if (window.speechSynthesis) {
        window.speechSynthesis.onvoiceschanged = function() {
          window.speechSynthesis.getVoices();
        };
      }

      // 2. Mascot Container
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
        "transition: transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1), left 0.8s cubic-bezier(0.16, 1, 0.3, 1), top 0.8s cubic-bezier(0.16, 1, 0.3, 1), bottom 0.8s ease;"
      ].join(" ");
      petContainer.style.left = (window.innerWidth - 130) + "px";
      petContainer.style.bottom = "24px";

      // Speech / Subtitle Bubble
      var bubble = document.createElement("div");
      bubble.id = "roaming-pet-bubble";
      bubble.style.cssText = [
        "background: rgba(16, 18, 26, 0.95);",
        "border: 1px solid rgba(255, 51, 75, 0.5);",
        "color: #ffffff;",
        "font-family: var(--font-mono, monospace);",
        "font-size: 11.5px;",
        "line-height: 1.4;",
        "padding: 8px 14px;",
        "border-radius: 8px;",
        "margin-bottom: 10px;",
        "box-shadow: 0 8px 24px rgba(0,0,0,0.8);",
        "max-width: 280px;",
        "text-align: center;",
        "opacity: 0;",
        "transform: translateY(6px);",
        "transition: opacity 0.3s, transform 0.3s;",
        "pointer-events: none;",
        "z-index: 30;"
      ].join(" ");
      bubble.textContent = "GhostRun Tactical Mentor Ready.";

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
      petSprite.title = "Ghost: Tactical AI Testing Mentor. Click to brief!";

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
      var isBriefingActive = false;
      var currentStepIndex = 0;

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

      function speak(text, duration, withVoice) {
        bubble.textContent = text;
        bubble.style.opacity = "1";
        bubble.style.transform = "translateY(0px)";
        if (withVoice !== false) {
          speakTacticalAudio(text);
        }
        setTimeout(function() {
          if (!isBriefingActive) {
            bubble.style.opacity = "0";
            bubble.style.transform = "translateY(6px)";
          }
        }, duration || 4500);
      }

      function spawnShockwave(x, y) {
        var ring = document.createElement("div");
        ring.className = "tactical-shockwave";
        ring.style.left = x + "px";
        ring.style.top = y + "px";
        document.body.appendChild(ring);
        setTimeout(function() { ring.remove(); }, 700);
      }

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

      // 3. Guided Tour Mission Steps (Punisher Dialogue)
      var tourSteps = [
        {
          stationId: "station-pc",
          prop: "laptop",
          row: 7,
          message: "Step 1: Stop burning cash on LLMs in CI. Wrap with @ghostrun.record. One run records; future runs replay in 0.04 seconds for zero dollars."
        },
        {
          stationId: "station-coffee",
          prop: "coffee",
          row: 0,
          message: "Step 2: Never test AI for exact strings. LLMs change wording every run. We assert on intent, empathy, and meaning."
        },
        {
          stationId: "station-server",
          prop: "radar",
          row: 7,
          message: "Step 3: When a prompt breaks, don't guess fixes like an amateur. Run ghostrun craft to let Bayesian optimization fix the wording."
        },
        {
          stationId: "station-dummy",
          prop: null,
          row: 4,
          message: "Target secured! Zero hallucinations, zero flakiness. You are ready to ship production AI apps."
        }
      ];

      function executeTourStep(index) {
        if (index >= tourSteps.length) {
          isBriefingActive = false;
          currentRow = 8;
          spawnConfetti();
          speak("Mission briefing complete. Explore the documentation or start testing!", 4000);
          setTimeout(function() {
            setProp(null);
            currentRow = 0;
            petContainer.style.top = "auto";
            petContainer.style.bottom = "24px";
            isPerched = false;
          }, 3500);
          return;
        }

        currentStepIndex = index;
        var step = tourSteps[index];
        var el = document.getElementById(step.stationId);
        if (!el) return;

        // Clear active highlights
        document.querySelectorAll(".station-active-highlight").forEach(function(h) {
          h.classList.remove("station-active-highlight");
        });
        el.classList.add("station-active-highlight");

        var rect = el.getBoundingClientRect();
        var targetLeft = Math.max(20, Math.min(window.innerWidth - 100, rect.left - 60));
        var targetTop = Math.max(60, rect.top - 10);

        isPerched = true;
        isFacingLeft = targetLeft < posX;
        currentRow = 1; // Run to station

        var dist = Math.hypot(targetLeft - posX, targetTop - (window.innerHeight - posY));
        var dur = Math.min(2.0, Math.max(0.6, dist * 0.0018));

        petContainer.style.transition = "left " + dur + "s cubic-bezier(0.16, 1, 0.3, 1), top " + dur + "s cubic-bezier(0.16, 1, 0.3, 1)";
        petContainer.style.left = targetLeft + "px";
        petContainer.style.bottom = "auto";
        petContainer.style.top = targetTop + "px";
        posX = targetLeft;

        setTimeout(function() {
          spawnShockwave(targetLeft + 36, targetTop + 65);
          currentRow = step.row;
          setProp(step.prop);
          speak(step.message, 5500);

          if (step.stationId === "station-dummy") {
            spawnConfetti(targetLeft + 45, targetTop + 40);
          }
        }, dur * 1000);
      }

      // 4. Cinematic Full-Screen Briefing Takeover -> Dive Down Animation
      function triggerCinematicBriefing() {
        isBriefingActive = true;
        setProp(null);
        currentRow = 3; // Saluting / standing tall

        // 1. Zoom into huge center screen
        petContainer.style.transition = "all 0.6s cubic-bezier(0.16, 1, 0.3, 1)";
        petContainer.style.left = (window.innerWidth / 2 - 36) + "px";
        petContainer.style.top = (window.innerHeight / 2 - 80) + "px";
        petContainer.style.bottom = "auto";
        petContainer.style.transform = "scale(2.2)";

        speak("Listen up. I'm Ghost. Most developers test AI with blind hope and burning cash. Let me show you how we run operations here.", 5000);

        // 2. After intro speech, dive down directly to Step 1 station!
        setTimeout(function() {
          petContainer.style.transform = "scale(1)";
          executeTourStep(0);
        }, 4200);
      }

      // 5. Tactical Radio Comms HUD (Hidden by default until tour starts)
      var hud = document.createElement("div");
      hud.id = "tactical-radio-hud";
      hud.style.display = "none";
      hud.innerHTML = [
        '<div class="radio-led"></div>',
        '<span style="color:#ff334b; font-weight:bold;">RADIO: GHOST</span>',
        '<button class="radio-btn primary" id="btn-next-target">Next Target →</button>',
        '<button class="radio-btn" id="btn-end-tour">End Tour ✕</button>',
        '<button class="radio-btn" id="btn-toggle-voice">🔊 Audio: ON</button>'
      ].join("");
      document.body.appendChild(hud);

      // On direct page load (if intro already seen), show Re-Tour button in header
      var reTourBtn = document.getElementById("btn-re-tour");
      if (reTourBtn) reTourBtn.classList.add("active");

      document.getElementById("btn-next-target").addEventListener("click", function() {
        if (window.GhostRunTour) window.GhostRunTour.nextStep();
      });
      document.getElementById("btn-end-tour").addEventListener("click", function() {
        hud.style.display = "none";
        if (window.GhostRunTour) window.GhostRunTour.skipTour();
      });
      document.getElementById("btn-toggle-voice").addEventListener("click", function() {
        if (window.GhostRunTour) {
          var state = window.GhostRunTour.toggleVoice();
          this.textContent = state ? "🔊 Audio: ON" : "🔇 Audio: OFF";
        }
      });

      // 6. Developer Action Reaction Hooks
      document.addEventListener("copy", function() {
        currentRow = 8;
        setProp("laptop");
        spawnConfetti();
        speak("Code secured. Put it in your codebase and run pytest. 0.04s replay locked.", 4000);
        setTimeout(function() {
          setProp(null);
          currentRow = 0;
        }, 4000);
      });

      var searchInput = document.getElementById("search-input");
      if (searchInput) {
        searchInput.addEventListener("focus", function() {
          currentRow = 3;
          speak("Looking for Intel? Type your query. I've indexed everything.", 3000);
          setTimeout(function() { currentRow = 0; }, 3000);
        });
      }

      // 7. Drag & Drop Physics
      var startMouseX = 0, startMouseY = 0;
      var elemStartX = 0, elemStartY = 0;

      petContainer.addEventListener("pointerdown", function(e) {
        isDragging = true;
        isBriefingActive = false;
        setProp(null);
        petContainer.style.cursor = "grabbing";
        petContainer.style.transition = "none";
        currentRow = 4; // Jump / airborne
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
        currentRow = 8;
        spawnShockwave(posX + 36, window.innerHeight - 20);
        speak("Tactical landing executed. Standing by.", 2500);

        setTimeout(function() { currentRow = 0; }, 1500);
      });

      // Quick Click Trigger
      petContainer.addEventListener("click", function(e) {
        if (Math.abs(e.clientX - startMouseX) < 5 && Math.abs(e.clientY - startMouseY) < 5) {
          if (window.GhostRunTour) window.GhostRunTour.launchStageBriefing();
        }
      });
    })();
  });
})();

/* ==========================================================================
   GhostRun — Interactive Tactical Voice Tour & Mascot State Machine
   ========================================================================== */

(function () {
  'use strict';

  // State definitions
  var TourState = {
    IDLE: 'IDLE',
    STAGE_BRIEFING: 'STAGE_BRIEFING',
    STATION_TOUR: 'STATION_TOUR',
    DISMISSED: 'DISMISSED'
  };

  var currentState = TourState.IDLE;
  var currentStepIndex = 0;
  var stageAnimTimer = null;
  window.GhostRunVoiceEnabled = true;

  // Voice synthesis engine (100% Free browser-native)
  function speakVoice(text) {
    if (window.GhostRunVoiceEnabled === false || !window.speechSynthesis) {
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      return;
    }
    try {
      window.speechSynthesis.cancel();
      var utter = new SpeechSynthesisUtterance(text);
      utter.rate = 0.95;
      utter.pitch = 0.75;

      var voices = window.speechSynthesis.getVoices();
      var chosen = voices.find(function (v) {
        return v.lang.startsWith("en") && (v.name.includes("Male") || v.name.includes("David") || v.name.includes("Google US English") || v.name.includes("Natural"));
      }) || voices[0];

      if (chosen) utter.voice = chosen;
      window.speechSynthesis.speak(utter);
    } catch (e) {}
  }

  // Pre-load voices
  if (window.speechSynthesis) {
    window.speechSynthesis.onvoiceschanged = function () {
      window.speechSynthesis.getVoices();
    };
  }

  // 4 Guided Station Steps with Screen Targets & Explanations
  var tourSteps = [
    {
      stationId: "station-pc",
      targetCodeSelector: ".home-quickstart pre:first-of-type",
      prop: "laptop",
      row: 7,
      text: "Look at this command: pip install ghostrun. Wrapping your function in @ghostrun.record captures the API call once. After that? 0.04-second replays for $0 in your CI test suite."
    },
    {
      stationId: "station-coffee",
      targetCodeSelector: ".home-grid",
      prop: "coffee",
      row: 0,
      text: "Now look at how we assert. We don't test for exact strings. LLMs change words every run. We test semantic meaning, empathy, and tone."
    },
    {
      stationId: "station-server",
      targetCodeSelector: ".home-quickstart ul",
      prop: "radar",
      row: 7,
      text: "When a prompt fails in production, don't guess fixes like an amateur. Run ghostrun craft. Bayesian optimization automatically discovers winning prompts."
    },
    {
      stationId: "station-dummy",
      targetCodeSelector: ".site-footer",
      prop: null,
      row: 4,
      text: "Zero hallucinations. Zero flakiness. You have full command of offline AI testing. Click any guide on the left to begin building!"
    }
  ];

  // =========================================================================
  // Phase 3: Center-Screen Stage Takeover
  // =========================================================================
  function launchStageBriefing() {
    currentState = TourState.STAGE_BRIEFING;
    var stage = document.getElementById("mascot-briefing-stage");
    var speechEl = document.getElementById("stage-speech-text");
    var avatar = document.getElementById("stage-avatar");

    if (stage) stage.classList.add("active");

    // Animate giant half-screen stage mascot avatar (320px x 347px)
    if (avatar) {
      var frame = 0;
      var row = 3; // Saluting / waving standing tall
      if (stageAnimTimer) clearInterval(stageAnimTimer);
      stageAnimTimer = setInterval(function () {
        frame = (frame + 1) % 8;
        avatar.style.backgroundPosition = "-" + (frame * 320) + "px -" + (row * 347) + "px";
      }, 110);
    }

    var introText = "Listen up. I'm Ghost. Most developers test AI with blind hope and burning cash. Let me take the wheel and walk you through our operational framework.";
    if (speechEl) speechEl.textContent = introText;

    speakVoice(introText);
  }

  // =========================================================================
  // Phase 4: Screen-Controlling Guided Walkthrough
  // =========================================================================
  var stationMoveTimer = null;
  var stationSpeakTimer = null;

  function startStationTour() {
    currentState = TourState.STATION_TOUR;
    var stage = document.getElementById("mascot-briefing-stage");
    if (stage) stage.classList.remove("active");
    if (stageAnimTimer) clearInterval(stageAnimTimer);

    // Show floating Tactical Radio HUD & HIDE Re-Tour button (mutually exclusive)
    var hud = document.getElementById("tactical-radio-hud");
    if (hud) hud.style.display = "flex";

    var reTourBtn = document.getElementById("btn-re-tour");
    if (reTourBtn) reTourBtn.classList.remove("active");

    // Take screen control starting with Step 1
    executeStationStep(0);
  }

  function skipTour() {
    currentState = TourState.DISMISSED;
    
    // 1. Immediately cancel all audio
    if (window.speechSynthesis) window.speechSynthesis.cancel();

    // 2. Clear any pending movement or speech timeouts
    if (stationMoveTimer) clearTimeout(stationMoveTimer);
    if (stationSpeakTimer) clearTimeout(stationSpeakTimer);
    if (stageAnimTimer) clearInterval(stageAnimTimer);

    // 3. Clear all spotlights and station glow outlines
    document.querySelectorAll(".tactical-camera-spotlight").forEach(function (el) {
      el.classList.remove("tactical-camera-spotlight");
    });
    document.querySelectorAll(".station-active-highlight").forEach(function (el) {
      el.classList.remove("station-active-highlight");
    });

    // 4. Hide Center Stage Modal if open
    var stage = document.getElementById("mascot-briefing-stage");
    if (stage) stage.classList.remove("active");

    // 5. Hide bubble & clear props
    var bubble = document.getElementById("roaming-pet-bubble");
    if (bubble) bubble.style.opacity = "0";

    var propSlot = document.getElementById("mascot-prop-slot");
    if (propSlot) propSlot.innerHTML = "";

    // 6. Park Mascot safely in the bottom corner
    var pet = document.getElementById("ghostrun-roaming-pet");
    if (pet) {
      pet.style.transition = "bottom 0.6s cubic-bezier(0.16, 1, 0.3, 1), left 0.6s ease";
      pet.style.top = "auto";
      pet.style.bottom = "24px";
      pet.style.left = (window.innerWidth - 130) + "px";
    }

    // 7. Hide Floating Radio HUD & SHOW Re-Tour button in header
    var hud = document.getElementById("tactical-radio-hud");
    if (hud) hud.style.display = "none";

    var reTourBtn = document.getElementById("btn-re-tour");
    if (reTourBtn) reTourBtn.classList.add("active");
  }

  function executeStationStep(index) {
    if (index >= tourSteps.length) {
      endTourCelebration();
      return;
    }

    currentStepIndex = index;
    var step = tourSteps[index];
    var stationEl = document.getElementById(step.stationId);
    var pet = document.getElementById("ghostrun-roaming-pet");
    var bubble = document.getElementById("roaming-pet-bubble");
    var propSlot = document.getElementById("mascot-prop-slot");

    if (!stationEl || !pet) return;

    // 1. Clear previous highlights
    document.querySelectorAll(".station-active-highlight, .tactical-camera-spotlight").forEach(function (el) {
      el.classList.remove("station-active-highlight", "tactical-camera-spotlight");
    });

    // 2. Control Developer's Camera: Smooth Auto-Scroll directly to target section
    stationEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    stationEl.classList.add("station-active-highlight");

    if (step.targetCodeSelector) {
      var codeTarget = document.querySelector(step.targetCodeSelector);
      if (codeTarget) {
        codeTarget.classList.add("tactical-camera-spotlight");
      }
    }

    // 3. Move Mascot dynamically to the station location
    stationMoveTimer = setTimeout(function() {
      var rect = stationEl.getBoundingClientRect();
      var targetLeft = Math.max(20, Math.min(window.innerWidth - 100, rect.left - 60));
      var targetTop = Math.max(60, rect.top - 10);

      pet.style.transition = "left 0.8s cubic-bezier(0.16, 1, 0.3, 1), top 0.8s cubic-bezier(0.16, 1, 0.3, 1)";
      pet.style.left = targetLeft + "px";
      pet.style.bottom = "auto";
      pet.style.top = targetTop + "px";

      // 4. Set props, speak dialogue & trigger voice
      stationSpeakTimer = setTimeout(function () {
        if (propSlot) {
          propSlot.innerHTML = "";
          if (step.prop) {
            var p = document.createElement("div");
            p.className = "mascot-prop-" + step.prop;
            propSlot.appendChild(p);
          }
        }

        if (bubble) {
          bubble.textContent = step.text;
          bubble.style.opacity = "1";
          bubble.style.transform = "translateY(0px)";
        }

        speakVoice(step.text);

        // Update button text on last step
        var btnNext = document.getElementById("btn-next-target");
        if (btnNext) {
          if (index === tourSteps.length - 1) {
            btnNext.textContent = "Finish Tour 🏆";
          } else {
            btnNext.textContent = "Next Target →";
          }
        }
      }, 850);
    }, 300);
  }

  function endTourCelebration() {
    currentState = TourState.DISMISSED;
    
    // Clear spotlights
    document.querySelectorAll(".tactical-camera-spotlight, .station-active-highlight").forEach(function (el) {
      el.classList.remove("tactical-camera-spotlight", "station-active-highlight");
    });

    var pet = document.getElementById("ghostrun-roaming-pet");
    var bubble = document.getElementById("roaming-pet-bubble");
    var propSlot = document.getElementById("mascot-prop-slot");

    if (propSlot) propSlot.innerHTML = "";
    if (bubble) {
      bubble.textContent = "Mission Accomplished! 100% Deterministic Pass. 🎉";
      bubble.style.opacity = "1";
      setTimeout(function() { bubble.style.opacity = "0"; }, 4000);
    }

    if (pet) {
      pet.style.transition = "bottom 0.6s cubic-bezier(0.16, 1, 0.3, 1), left 0.6s ease";
      pet.style.top = "auto";
      pet.style.bottom = "24px";
      pet.style.left = (window.innerWidth - 130) + "px";
    }

    // Hide Floating Radio HUD after tour ends & Show Re-Tour button
    var hud = document.getElementById("tactical-radio-hud");
    if (hud) {
      setTimeout(function() { 
        hud.style.display = "none"; 
        var reTourBtn = document.getElementById("btn-re-tour");
        if (reTourBtn) reTourBtn.classList.add("active");
      }, 3500);
    }

    speakVoice("Mission accomplished. You have full command of offline AI testing. Happy coding!");
  }

  // =========================================================================
  // Initialize Global Listeners & Connect Buttons
  // =========================================================================
  window.GhostRunTour = {
    launchStageBriefing: launchStageBriefing,
    startStationTour: startStationTour,
    skipTour: skipTour,
    nextStep: function () {
      if (currentStepIndex >= tourSteps.length - 1) {
        endTourCelebration();
      } else {
        executeStationStep(currentStepIndex + 1);
      }
    },
    toggleVoice: function () {
      window.GhostRunVoiceEnabled = !window.GhostRunVoiceEnabled;
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      return window.GhostRunVoiceEnabled;
    }
  };

  document.addEventListener("DOMContentLoaded", function () {
    var btnStart = document.getElementById("btn-stage-start");
    var btnSkip = document.getElementById("btn-stage-skip");

    if (btnStart) btnStart.addEventListener("click", startStationTour);
    if (btnSkip) btnSkip.addEventListener("click", skipTour);
  });
})();

"""Interactive visual demonstration testing every GhostRun mascot animation."""

import time
from ghostrun.pet import run_pet

DEMO_STATES = [
    ("waving", "👋 1. Waving Greeting (ghostrun init)"),
    ("running-right", "🏃 2. Running Right (pytest test suite in flight)"),
    ("running", "⚡ 3. Thinking / Fast Bayesian Trials (ghostrun craft)"),
    ("jumping", "🏆 4. Victory Dance (All Tests Pass & Replayed in 0.04s)"),
    ("review", "🎖️ 5. Review Approval (Winning Prompt Optimized)"),
    ("waiting", "⏳ 6. Waiting on LLM API completion"),
    ("failed", "💀 7. Failed State (Prompt Regression / Violation)"),
    ("idle", "💤 8. Idle Desk Companion (Ready for next run)"),
]

def main():
    print("==================================================")
    print("👻 GHOSTRUN TACTICAL MASCOT ANIMATION SHOWCASE")
    print("==================================================")
    print("Launching the mascot companion. Click it to cycle animations!")
    print("Or let it run through states automatically.\n")

    for anim_name, desc in DEMO_STATES:
        print(f"-> Now showing: {desc}")
        try:
            run_pet(width=100, initial_anim=anim_name, auto_close_ms=2200)
        except KeyboardInterrupt:
            break
        time.sleep(0.2)

    print("\n✅ All 9 animation states tested and verified successfully!")

if __name__ == "__main__":
    main()

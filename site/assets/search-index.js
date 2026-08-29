window.GHOSTRUN_SEARCH_INDEX = [
  {
    title: "ghostrun",
    section: "Home",
    url: "index.html",
    excerpt: "CI-native LLM evals for real applications: record API calls once, replay in CI, and catch semantic regressions.",
    keywords: "home overview pitch llm evals ci regression testing pytest"
  },
  {
    title: "Getting started",
    section: "Guide",
    url: "guide/getting-started.html",
    excerpt: "Install ghostrun, pull an Ollama model, and scaffold a working first test with ghostrun init.",
    keywords: "install pip ollama init quickstart pytest ghostrun run"
  },
  {
    title: "Prompt crafting & optimization",
    section: "Guide",
    url: "guide/craft.html",
    excerpt: "Automatically synthesize prompt instructions and discover winning few-shot demonstrations with Bayesian optimization.",
    keywords: "craft prompt optimization bayesian search signature optuna few-shot synthesis prompt engineering"
  },
  {
    title: "LLM regression testing",
    section: "Guide",
    url: "guide/llm-regression-testing.html",
    excerpt: "Catch LLM behavior regressions in CI by recording real app calls, replaying them deterministically, and asserting on meaning.",
    keywords: "llm regression testing prompt regression testing deterministic llm tests ci semantic regression"
  },
  {
    title: "Pytest LLM evals",
    section: "Guide",
    url: "guide/pytest-llm-evals.html",
    excerpt: "Write LLM evals as normal pytest tests around the real application code path your users hit.",
    keywords: "pytest llm evals llm testing pytest llm evals python semantic assertions"
  },
  {
    title: "Test OpenAI apps offline",
    section: "Guide",
    url: "guide/test-openai-apps-offline.html",
    excerpt: "Record real OpenAI and Anthropic API calls once, then replay them offline and deterministically in pytest.",
    keywords: "test openai app pytest mock openai calls pytest record replay openai api calls offline llm tests"
  },
  {
    title: "Recording and replay",
    section: "Guide",
    url: "guide/recording.html",
    excerpt: "HTTP transport-layer interception, auto/record/replay modes, judge-verdict caching, providers, secret redaction, parallel runs.",
    keywords: "cache mode ghostrun_mode httpx interceptor provider redaction xdist parallel secrets"
  },
  {
    title: "Semantic assertions",
    section: "Guide",
    url: "guide/assertions.html",
    excerpt: "contains_intent, tone_is, matches, and deterministic assertions. Judge reliability, majority-vote verdicts, tool-call checks.",
    keywords: "expect contains_intent tone_is matches judge votes disagreement_rate tool calls"
  },
  {
    title: "Prompt regression tracking",
    section: "Guide",
    url: "guide/regression-tracking.html",
    excerpt: "Snapshot runs and diff them: ghostrun diff, output drift, PR-comment and JUnit CI formats.",
    keywords: "snapshot diff regression fix stable output drift junit github-comment CI"
  },
  {
    title: "Configuration",
    section: "Guide",
    url: "guide/configuration.html",
    excerpt: ".ghostrun.yaml, environment variables, pytest flags, ghostrun doctor, privacy.",
    keywords: "config yaml env GHOSTRUN_MODE GHOSTRUN_JUDGE doctor flags privacy"
  },
  {
    title: "API reference",
    section: "Guide",
    url: "guide/api-reference.html",
    excerpt: "Every public function, class, exception, and config field in ghostrun.__all__.",
    keywords: "record recording expect expect_tool_calls Config get_config configure exceptions CacheMiss"
  },
  {
    title: "Why not just ask an LLM to write this?",
    section: "Guide",
    url: "guide/why-not-diy.html",
    excerpt: "The concrete bugs found building this: thread-safety races, torn cache writes, secret-redaction false positives.",
    keywords: "diy bugs concurrency thread safety redaction console encoding"
  },
  {
    title: "Comparison with other tools",
    section: "Research",
    url: "research/comparison.html",
    excerpt: "Researched comparison against DeepEval, Promptfoo, Ragas, vcr-langchain, Langfuse, Braintrust, LangSmith, Giskard, and others.",
    keywords: "deepeval promptfoo ragas vcr-langchain langfuse braintrust langsmith giskard comparison"
  },
  {
    title: "Judge-voting benchmark",
    section: "Research",
    url: "research/judge-voting-benchmark.html",
    excerpt: "Does majority-vote caching actually fix LLM-judge unreliability? A small, honest benchmark against a real judge.",
    keywords: "flip rate majority vote benchmark reliability coin flip judge disagreement"
  }
];

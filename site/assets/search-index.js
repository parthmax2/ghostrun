window.GHOSTRUN_SEARCH_INDEX = [
  {
    title: "ghostrun",
    section: "Home",
    url: "index.html",
    excerpt: "pytest for LLMs — deterministic record/replay and semantic assertions, local-first and privacy-first.",
    keywords: "home overview pitch"
  },
  {
    title: "Getting started",
    section: "Guide",
    url: "guide/getting-started.html",
    excerpt: "Install ghostrun, pull an Ollama model, and scaffold a working first test with ghostrun init.",
    keywords: "install pip ollama init quickstart pytest"
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

# Submission checklist (hackathon deadline: Oct 23, 11:59 PM PDT = Oct 24, 07:59 Dublin time)

1. [ ] Run for real once: engine + `scripts/run_decider.sh` + Bedrock credentials → `python -m jride_agent --demo`
2. [ ] `python bench/bench.py --decider 127.0.0.1:8099 --llm --price-in … --price-out …` → real `bench/results.md`
3. [ ] If the CLI says the checkpoint has fewer slots than 7, merge categories in `jride_agent/policy.py` and update the README/article table
4. [ ] New **public** GitHub repo (fresh history): push this folder, add the topics `strands-decider-2b`, `policy`
5. [ ] Record the demo (< 3 min, public) following `DEMO_SCRIPT.md`
6. [ ] Publish the article on AWS Builder Center from `ARTICLE.md` (fill every ⟦FILL⟧), add tags `#strands-decider-2b` and `#policy`
7. [ ] On the hackathon page: Join, then Create post with the repo, article and video links; confirm both tags

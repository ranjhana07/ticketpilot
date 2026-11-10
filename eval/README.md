# Evaluation inputs

`kb_queries.json` is the labelled query set for retrieval. Each entry has a natural language `query`, written the way a customer would phrase it rather than copying the article wording, and a `relevant` list with the id of every help center article that answers it. 65 queries cover all 32 articles in `knowledge_base/`.

A query counts as a hit at k when at least one relevant article is in the first k distinct articles returned. Reciprocal rank uses the position of the first relevant article. Retrieval works on chunks, the evaluation collapses chunks of the same article before scoring.

The queries were written once, after the articles, and were not adjusted after seeing retrieval results. Because the same person wrote the articles and the queries, vocabulary overlap is probably higher than with real customers, so the numbers are best read as a comparison between retrieval modes and less as an absolute quality estimate.

Run `ticketpilot eval retrieval` to reproduce, the output goes to `results/retrieval.json` and `results/retrieval.csv`.

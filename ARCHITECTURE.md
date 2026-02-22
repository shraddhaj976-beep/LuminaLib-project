
Why this DB schema for user preferences:

We store explicit preferences in user_preferences (user_id, tag, weight) and implicit behavior in user_interactions (borrow/review events with optional sentiment). This keeps reads fast for the recommender (just weights) while preserving a full behavioral trail for future models.

How async LLM generation works:

Ingestion endpoint stores the file and inserts a DB row. It enqueues a Celery task generate_summary(book_id). The Celery worker downloads the file, extracts text (PDF via pdfminer), calls the LLM to generate summary + tags, and writes them back to the DB. Review submission enqueues process_review_sentiment(book_id, user_id, text) which runs sentiment analysis and updates user preferences asynchronously. Aggregated review analysis uses a prompt template (AGGREGATE_PROMPT) passed to the LLM.

Recommendation strategy:

Build TF-IDF vectors from (tags + summary) per book and compute cosine similarity to a user preference vector (constructed from weighted tags in user_preferences). Exclude already-borrowed books and return top-N results. 

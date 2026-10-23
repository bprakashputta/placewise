-- 003: only the CURRENT resume version of each person is searchable.
-- Older versions' chunks are kept for history, but retrieval (Block 5) must use this view, so an
-- outdated resume can never appear in search results or citations.
CREATE VIEW current_chunks AS
SELECT c.*
FROM chunks c
JOIN resume_files rf ON rf.id = c.resume_file_id AND rf.is_current;

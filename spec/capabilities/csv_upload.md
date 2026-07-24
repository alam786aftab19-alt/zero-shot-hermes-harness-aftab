# Capability: CSV Upload

## What It Does

Accepts one or more CSV files from the user, validates them (size, encoding, delimiter), infers column names and types, and stores the file on disk. Returns a file ID and a lightweight schema summary for downstream nodes.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| multipart files | `List[UploadFile]` | HTTP POST `/upload` | yes |
| session token | `str` | Header / cookie | no (optional) |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| file_id | `str` (UUID) | HTTP response + stored in `uploaded_file` table |
| column_schema | `dict` (name→dtype) | In-memory, passed to `generate_sql` node |
| stored_path | `str` | `uploaded_file.stored_path` |

## External Calls

| System | Operation | On Failure |
|---------|-----------|------------|
| filesystem | write to `data/uploads/` | Abort upload, return 500 with generic error; do not expose path |

## Business Rules

- Only `.csv` MIME types accepted; reject others with 400.
- Max file size: 50 MB per file; reject with 413.
- If CSV is empty or has no header rows, return 400.
- Store file with a UUID filename; never trust user-provided filename for path.
- Keep original filename in metadata for UI only.

## Success Criteria

- [ ] Uploaded file is readable via pandas within 2 s for a 10 MB CSV.
- [ ] Inferred schema matches at least 95 % of columns on a test dataset (sample types).
- [ ] Duplicate upload of same content yields a new `file_id` (no dedup).

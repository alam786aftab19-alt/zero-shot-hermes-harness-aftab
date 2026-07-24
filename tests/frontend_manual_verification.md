# Frontend Manual Verification Steps

This document provides step-by-step manual testing instructions for the Phase 1 frontend UI. Ensure the FastAPI backend with Phase 1 endpoints (`/chat`) is running.

## Prerequisites

- Backend server running on `http://localhost:8001` (`uv run python -m src`)
- Phase 1 API implemented: POST `/chat` accepts multipart/form-data with `question` and `files` (CSV) and returns JSON with `question`, `reasoning`, `sql`, `chart_config` (Plotly), `result` (columns, rows, row_count), `confidence`, `cache_hit`, `warnings`.
- Sample CSV file ready (e.g., `crime_data.csv`) under 10MB.

## UI Elements Check

1. Open `http://localhost:8001/app/` in a browser.
2. Verify page title: **UP Police Data Analyst** (visible in header).
3. Verify header contains a button labeled **"Coming soon"** (disabled) for MsSQL connection.
4. Verify presence of:
   - **Data Upload** section with "Upload CSV" button.
   - **Ask a Question** section with a text input (placeholder: "e.g., Show total incidents by district as a bar chart...") and an "Ask" button.
5. Initially, results section is hidden.

## File Upload Functionality

6. Click **Upload CSV** button → file picker should open.
7. Select one or more CSV files (ensure each ≤10MB).
   - ✅ Files appear as tags below the button: each shows filename and size (MB) with a remove button (×).
   - ✅ Total file count reflected by number of tags.
8. Try selecting a file with extension `.txt` or larger than 10MB.
   - ✅ An error message appears in red: "File X exceeds 10MB limit." or "File X is not a CSV file."
   - The invalid file is not added to the list.
9. Click the remove (×) on a file tag → file disappears from list.
10. With no files selected, try clicking **Ask** → error: "Please upload at least one CSV file."

## Chat Submission

11. Select a valid CSV file.
12. Enter a question like: "Show total incidents by district as a bar chart."
13. Click **Ask**.
    - ✅ Ask button becomes disabled, status "Thinking..." appears.
    - After ~seconds, results section appears.
14. Verify results:
    - **Your question** is displayed at the top ( echoed ).
    - **Reasoning** section shows a paragraph explaining the reasoning.
    - **Generated SQL** section shows a code block with syntax highlighting (keywords in bold blue, strings in green, comments in gray). A **Copy** button is visible top-right.
    - **Visualization** section renders a Plotly chart matching the agent's intent (e.g., bar chart). Chart is responsive; try resizing the window.
    - **Results** section shows a scrollable table with the data (first 100 rows if applicable). If row count >100, note appears: "Showing first 100 of X rows."
    - **Meta tags** below:
        - "Cached" badge (green) if appropriate.
        - "Confidence: high/medium/low" badge (green/orange/red).
    - **Warnings** section (yellow) if any warnings are present.
    - The **Copy** button in SQL section: click → clipboard receives raw SQL; button briefly changes to "Copied!" then reverts.
15. Check that network request:
    - In DevTools → Network, a POST to `/chat` with `multipart/form-data` including the file(s) and question.
    - Response JSON matches expected schema.

## Error Handling

16. With no files selected, click Ask → see error: "Please upload at least one CSV file."
17. With an empty question, click Ask → see error: "Please enter a question."
18. Simulate server error (e.g., temporarily stop backend) and submit → see a red error banner with a descriptive message.
19. Timeout: if request takes >70s (simulate by using a huge file or slow server), frontend shows "Request timed out after 70 seconds. Please try again."

## Responsive Design

20. Resize browser to mobile width (<600px).
    - Chat input and button become full-width stacked.
    - Header elements adjust (MsSQL button aligns to right).
    - Chart container height reduces (300px).
    - File tags stack vertically; table scrolls horizontally.
    - Overall layout remains usable.

## Accessibility

21. Tab through interactive elements: buttons, inputs, file tags. All should be focusable and show focus ring.
22. Screen reader should announce status changes (ARIA live region for status "Thinking..." and results appearance).
23. All inputs have associated labels (visible or via `aria-label`).

## Notes

- The **MsSQL connection** button is a stub; it is disabled and labeled "Coming soon". It should not perform any action.
- File uploads are sent only with the chat request; there is no separate `/upload` API call from the UI.
- Plotly charts are rendered using the `chart_config` returned by the server.
- The SQL code block uses basic regex-based syntax highlighting.
- The UI uses a light theme with police blue (#1a365d) accents.

## Checklist

- [ ] All UI elements present and labeled correctly.
- [ ] File selection, validation, removal work.
- [ ] Chat submission works; results display correctly.
- [ ] Plotly renders; table shows correct rows and columns.
- [ ] Copy SQL works.
- [ ] Errors appear when required fields missing or upload invalid.
- [ ] Responsive layout functional.
- [ ] Accessibility basics satisfied.

If all items pass, the Phase 1 frontend-ui slice meets specification.

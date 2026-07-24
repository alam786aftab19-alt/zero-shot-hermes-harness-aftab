# UI

The frontend is a single-page application served at `/app/`. It follows a zero-build approach: plain HTML, CSS, and JavaScript (no bundler). Chart.js is used for visualizations. The UI is visually clean and professional, matching police department branding (blue/neutrals). All interactions are asynchronous with clear loading indicators.

## Layout

```
+-----------------------------------------------------------+
| Header: "UP Police Data Analyst"                         |
+-----------------------------------------------------------+
| [Upload CSV]  (button; opens file picker, multiple)      |
| Selected files: file1.csv, file2.csv [x] [x]             |
+-----------------------------------------------------------+
| Question: [___________________________________________] |
|           [Ask] (button)                                 |
+-----------------------------------------------------------+
| Status: "Thinking..." (spinner) — appears below button   |
+-----------------------------------------------------------+
| Results (hidden until response):                        |
|                                                          |
| - SQL Query (in <pre><code>; syntax highlight)          |
| - Reasoning (markdown-ish)                               |
| - Chart (Canvas with Chart.js)                           |
| - Data Table (scrollable, first 100 rows)               |
| - Cache indicator: "Result from cache" (tag)            |
| - Confidence: "Confidence: high" (tag)                  |
| - Warnings (if any) in yellow banner                    |
+-----------------------------------------------------------+
```

## Components

### File Upload Control

- Button: "Upload CSV"
- Input: `<input type="file" accept=".csv" multiple>` hidden; button triggers click.
- After selection, display each filename with a remove (×) button. Files are stored in a `FormData` object to send with the chat request.
- Max file size: 10MB each; client-side validation before sending.
- UI shows file count and total rows (after upload, server returns row counts; display optionally).

### Chat Input

- Single-line text input field expanding to multi-line if needed.
- Send button (disabled while request in flight).
- Press `Enter` to send ( Shift+Enter for newline optional — we'll keep single-line for simplicity).

### Results Area

1. **SQL Section:**
   - Heading: "Generated SQL"
   - Code block with basic syntax highlighting (regex-based: keywords in bold blue, strings in green).
   - Copy button to copy to clipboard.

2. **Reasoning Section:**
   - Heading: "Reasoning"
   - Paragraph text (Markdown rendering optional; plain text with line breaks preserved is fine).
   - Shows how the agent interpreted the question and chose tables.

3. **Chart Section:**
   - Heading: "Visualization"
   - Canvas element for Chart.js.
   - Chart type is selected by agent; UI just renders.
   - Responsive; maintain aspect ratio.

4. **Data Table Section:**
   - Heading: "Results (first 100 rows)"
   - Scrollable `<table>` with sticky header.
   - Columns from result set; rows populated with data.
   - If row_count > 100, show note: "Showing first 100 of X rows."

5. **Meta Tags:**
   - Cache hit: small badge with "Cached" (green) if `chart.cache_hit` true.
   - Confidence: badge with "high"/"medium"/"low" in corresponding colors (green/orange/red).
   - Warnings: if `warnings` array non-empty, show yellow banner with bullet list.

### Loading States

- When request starts: disable input and button; show spinner next to "Ask" or replace button with "Thinking...".
- Timeout after 70 seconds (longer than server timeout); show error "Request timed out. Try again."
- On error: display error message in red banner, keep question intact.

### Error Handling

- Network errors: "Failed to communicate with server."
- Server error (5xx): show `response.error.message`.
- If files fail to upload: show toast with server's error.

## Styling

- Font: System sans-serif (Segoe UI, Roboto, Helvetica).
- Colors: Primary blue (#1a365d; UP Police blue), secondary gray (#f0f0f0), accent green (#2f855a) for success, red (#c53030) for errors.
- Responsive: full-width on mobile, centered max-width 1200px on desktop.
- Buttons: rounded corners, hover effects.

## Accessibility

- All inputs have labels.
- Keyboard navigable.
- ARIA live regions for status updates.

## Polish

- Smooth transitions for showing/hiding sections.
- Fade-in charts.
- Copy-to-clipboard feedback (tooltip "Copied!").

## Assets

- `index.html`: structure with IDs for dynamic updates.
- `styles.css`: all styles.
- `app.js`: DOM manipulation, fetch API handling, Chart.js rendering.

No external dependencies beyond Chart.js (loaded from CDN) to keep zero-build.

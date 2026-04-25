# Test Plan — PR #3: MASTER-PFE frontend port + Markdown lesson / Quiz activity rendering

## What changed (user-visible)
- `apps/frontend` replaced with the MASTER-PFE layout (three-pane: FileTree | Viewer | Chat)
- BlockNote editor removed — lessons now render as styled Markdown (`react-markdown` + `remark-gfm` + `rehype-highlight`)
- New `ChapterQuiz` component renders activities (JSON `{questions[{prompt, options, correct_index, explanation}]}`)
- New `LessonMarkdownViewer` component renders `lessons.content_markdown` as HTML
- Supabase Realtime wired to `syllabuses / chapters / lessons / activities`; rows appear in the FileTree live as the agent writes them
- Schema aligned to MPFE: `syllabuses` (not `syllabi`), lesson body in `content_markdown`, quiz payload uses `correct_index` (int), not `correct_choice_ids` (string[])

## Testing approach
Drive the MPFE supervisor agent against the live Supabase while the Next.js frontend is open in the browser. Use `e2e_run.py` (interactive harness) to run the agent — it auto-answers the `ask_user` interrupts so the run proceeds without needing the chat UI to do it. The frontend's Supabase Realtime subscription proves the FileTree updates live as the agent streams rows. Then click a lesson and an activity to verify the viewer panes.

### Known gap (documented, non-blocking for this test)
The MASTER-PFE ChatPane handles `frontend_tool_call` interrupts only — it does NOT yet render MPFE's native `interrupt({"question", "tool_call_id"})` payload. So the chat pane will look idle while the agent is running. This will be addressed in a follow-up PR; testing the PR's main claims (realtime sync, Markdown, quiz) does not need the chat UI.

---

## Primary flow — single end-to-end run

### Setup (already done before recording starts)
- Frontend: `npm run dev` on `localhost:3000`  (Supabase anon key + `LANGGRAPH_URL=http://localhost:2024` in `.env.local`)
- Agent: `langgraph dev` on `localhost:2024`
- `.env_mpfe_test` sourced into the agent process so Supabase / Serper / Xai / NVIDIA keys resolve

### Recorded test steps

#### Test 1 — Tree populates live as agent streams rows
1. Open `http://localhost:3000` in the browser.  
   **Precondition**: FileTree shows "Waiting for the agent to start a syllabus…", viewer shows "Select a lesson or activity from the file tree."
2. In a shell, run `python e2e_run.py --prompt "Build a 2-chapter syllabus for Intro to HTML, audience: absolute beginners; include 1 quiz per chapter." --thread <thread-uuid>` where `<thread-uuid>` is pulled from the URL query `?threadId=<id>` after clicking "+ New" in the UI.
3. Watch the FileTree pane.  
   **Expected (specific)**:
   - Within ~10 s of `create_syllabus` commit: the tree header flips from "Waiting…" to **"Intro to HTML"** (or the exact title the agent generated).
   - Within ~20 s of `create_chapters` commit: **2 chapter rows** appear, labelled `#1 <chapter-title>` and `#2 <chapter-title>`.
   - As each lesson/activity is committed by the writer/critic loop: leaf rows appear under the parent chapter in increasing `position` order. Lessons have a blue `FileText` icon; activities have an amber `ClipboardCheck` icon.
   - The per-chapter count badge increments by 1 each time a leaf is added.
   **Pass criteria**: ≥ 2 chapters + ≥ 2 lessons + ≥ 1 activity appear **without any page reload**. If the tree stays empty until I hit refresh, the test **fails**.

#### Test 2 — Lesson renders as Markdown with code highlighting
4. Click the first lesson leaf (e.g. "Lesson 1: What is HTML?").  
   **Expected (specific)**:
   - Viewer pane header shows the uppercase label "LESSON" + the exact lesson title.
   - Body renders the `content_markdown` value from Supabase as HTML: `#`-prefix lines become `<h1>/<h2>/<h3>`, `- `/`* ` become bullet lists, ```` ```lang ```` fenced blocks render as syntax-highlighted code (dark github theme).
   - No raw `**bold**` stars, no raw `#` characters visible, no "jumping JSON" from BlockNote.
   **Pass criteria**: I can see at least one `<h2>` heading + one syntax-highlighted `<code>` block (or one `<ul>` list) in the viewer. If raw Markdown text is visible instead, the test **fails**.

#### Test 3 — Activity renders as a quiz and grades `correct_index`
5. Click an activity leaf (amber icon, e.g. "Activity 1: HTML Basics Check").  
   **Expected (specific)**:
   - Viewer pane header shows "Activity · Quiz" + the activity title + `N questions` subtitle.
   - Each question: prompt + 4 (±1) option buttons labelled `A. / B. / C. / D.`. Submit button is disabled until every question is answered.
   - Difficulty badge appears when the payload includes `difficulty`.
6. Intentionally pick the WRONG option for question 1 and the RIGHT option for question 2 (using the `correct_index` from Supabase, looked up out-of-band).
7. Click **Submit**.  
   **Expected (specific)**:
   - Score banner shows "1/N" (or "0/2" if only 2 questions, etc. — exactly equal to the count of right answers I picked).
   - Question 1 shows a red **Incorrect** badge, its correct option is highlighted emerald, my wrong pick is highlighted rose. Explanation for Q1 is shown below.
   - Question 2 shows a green **Correct** badge. Explanation for Q2 is shown below.
   - Submit button becomes a "Retry" button.
   **Pass criteria**: Score matches my deliberate input exactly (1/N), visual coloring distinguishes correct vs wrong vs my-wrong-pick. If the score is wrong by even 1, the test **fails** — that means `correct_index` mapping is off.

---

## What I will NOT test (out of scope for this PR)
- ChatPane askUser interrupt rendering (known gap, follow-up PR)
- Thread-creation flow via "+ New" button (requires agent-id metadata plumbing that MPFE doesn't need for Test 1)
- Deleting syllabi / chapters / lessons from the UI (no writer in MPFE)
- Desktop sidebar resizing, mobile layout (visual only, no semantic change)

## Artifacts I will produce
- Screen recording covering Tests 1–3 with `record_annotate` milestones at (a) tree first row, (b) Markdown render, (c) quiz submit result
- A `test-report.md` with inline screenshots of each pass/fail moment
- PR comment on #3 linking the recording + report

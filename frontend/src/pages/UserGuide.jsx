import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './UserGuide.css';

export default function UserGuide() {
  const { user } = useAuth();
  return <main className="user-guide">
    <header><p>AI Examiner · Quick start</p><h1>User guide</h1>
      <p>Upload answer sheets, evaluate, review the marks, then export verified results.</p>
      <button className="guide-print" onClick={() => window.print()}>Print / save as PDF</button>
    </header>
    <section><h2>1. Sign in and check your access</h2>
      <p>Use the sign-in method provided by your institution. Administrators manage courses, accounts and assignments. Uploaders prepare and evaluate assigned courses; reviewers inspect, revise and verify assigned results. If a course or action is missing, contact your administrator.</p>
    </section>
    <section><h2>2. Prepare and upload PDFs</h2>
      <p>Use one folder per course, for example <strong>MB3204</strong>, containing <strong>model_answer.pdf</strong> (or <strong>answer_key.pdf</strong>), optionally <strong>question_paper.pdf</strong>, and student files such as <strong>student_201.pdf</strong>. Each student filename becomes its identifier. Include clear question numbers, marks and optional-question rules in the source documents.</p>
      <p>In <Link to="/evaluate/batch">Evaluate → Batch</Link>, enter a distinct examination/session ID, exam type and maximum marks. Select the folder and choose <strong>Upload and check existing results</strong>. Keep the page open until upload finishes; preparation then runs in the background. After an interrupted upload, select the same unchanged folder to resume. Alphanumeric course codes and letter suffixes are supported; discovered courses are registered without changing existing assignments.</p>
    </section>
    <section><h2>Correct skipped folders</h2><p>Recent folder preparation lists skipped courses and their issues; valid courses can continue. Choose <strong>Upload corrected folders separately</strong>, include only the corrected course folders, and keep the original examination ID and student filenames. Marking allocations come from the answer key first. If incomplete, evaluation reads the course question paper, then uses an administrator-entered fallback scheme. Administrators configure a default paper and allocations in Courses &amp; accounts → Fallback marking schemes, separately for each course and End Sem/MST. Enter allocations in the form or preview an Excel import before saving. Unresolved sheets appear in Review results → Needs review without a score; correct the scheme and retry them. Running sheets must finish or be cancelled before replacing inputs.</p></section>
    <section><h2>3. Evaluate one sheet or a batch</h2>
      <p><strong>One sheet:</strong> select only that student's checkbox and choose <strong>Evaluate / use existing</strong>. A folder may contain just one student and its answer key. This workspace method saves progress and supports recovery.</p>
      {user?.role === 'admin' && <p><strong>Standalone form:</strong> open <Link to="/evaluate/single">Evaluate → Single (one sheet)</Link>, upload or enter the model answer, select a teacher and student, add the student PDF and maximum marks, then evaluate. Keep this page open; this older direct form does not use the durable workspace queue. Prefer the workspace for long papers.</p>}
      <p><strong>Batch:</strong> select several rows, or use the button to evaluate eligible sheets across all filtered pages. “Select all visible” selects the current page only. Existing compatible results are reused; <strong>Re-evaluate selected</strong> creates a fresh grading attempt while retaining history and reusable extraction.</p>
    </section>
    <section><h2>4. Follow progress and resolve problems</h2>
      <p>To stop one sheet, click <strong>Stop</strong> beside its progress or table row. To stop several, select their checkboxes and click <strong>Stop selected</strong>. <strong>Select running / queued on this page</strong> selects active work on the current page. Queued sheets cancel immediately; running sheets show <strong>Stopping</strong> until the current request returns. Existing saved results remain available.</p>
      <p>Queued sheets wait for capacity. Reading-page and grading stages show current work. Temporary failures retry automatically; “Failed — retry required” needs attention. “Source needs review” means check readability, the answer key or marking rules before retrying. A failed attempt is not a zero mark. Internet or database interruptions preserve the queue and completed OCR pages. The worker reconnects automatically while the backend is running; if it stays offline after connectivity returns, ask the administrator to check the backend process. Cancel selected work before changing or deleting it; an in-flight request may take time to stop.</p>
    </section>
    <section><h2>5. Review, verify and export</h2>
      <p>Open <Link to="/results">Review results</Link>, filter the examination/course, and inspect feedback and question marks. History lets authorized reviewers compare attempts, select an earlier successful result or revise marks with a reason. Verify only after checking against the source. Manual changes clear verification. Download a course or combined workbook; exports include only verified active results. Earlier saved evaluations are available to administrators on the same Review results page.</p>
    </section>
    <section><h2>6. Delete data carefully · administrators</h2>
      <p>Select sheets and use <strong>Delete selected data</strong>: clear cache only, marks/history only, both, or the entire sheet record. Read the scope and type <strong>DELETE</strong> to confirm. Active jobs must stop first. <strong>Original uploaded PDFs remain stored.</strong> Cache clearing keeps marks unless you choose to delete them too; it forces fresh extraction on the next evaluation.</p>
    </section>
    <section><h2>7. Compare against teacher marks</h2>
      <p>Open <Link to="/teacher-comparison">Teacher comparison</Link>, select a course, and download the totals or question template. Teachers should mark the original papers without seeing AI scores. Fill teacher_marks, keep identifiers unchanged, and upload the Excel or CSV file. Review excluded rows before saving the comparison.</p>
      <p>Use calibration papers to investigate OCR, rubric and grading disagreements. Keep held-out test papers separate. Average difference and bias are normalized to percentage points, so exams with different maximum marks can be compared. Paper totals and question rows are reported separately. Manual grades are excluded from AI accuracy metrics.</p>
      <p>After an approved rubric or model change, re-evaluate papers and choose Compare latest AI results. Each saved comparison preserves its original AI scores and teacher labels. Uploading teacher marks does not train the model or change student grades automatically. Review coverage as well as average differences before calling a change an improvement.</p>
      <p>Change from baseline compares only the same teacher targets with valid AI scores in both runs. It reports improved, worsened and unchanged rows, and highlights lost coverage or reused predictions. This comparison remains available after saving and is included in the comparison workbook.</p>
    </section>
    <footer>Check AI marks before verification. For support, share the examination, course, student identifier, time and displayed error with your administrator.</footer>
  </main>;
}

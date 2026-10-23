import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Workspace, { stageLabel } from './Workspace';
import api from '../services/api';

jest.mock('../services/api', () => ({
  __esModule: true, default: { get: jest.fn(), post: jest.fn() }, uploadBatchFolder: jest.fn(),
}));

jest.mock('../context/AuthContext', () => ({ useAuth: () => ({ user: { role: 'admin' } }) }));

const rows = [
  { _id: 'one', exam_id: 'exam-1', course_code: 'FS3401', roll_number: '101', max_marks: 100,
    active: { marks: 0, percentage: 0 }, active_attempt: 'attempt-1',
    attempts: [{ _id: 'attempt-1', status: 'completed', marks: 0, created_at: '2026-10-14T00:00:00Z' }],
    job: { state: 'completed', stage: 'completed' } },
  { _id: 'two', exam_id: 'exam-1', course_code: 'FS3401', roll_number: '102', max_marks: 100,
    active: null, attempts: [], job: { state: 'error', stage: 'error', error: 'Timed out' } },
];

beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockResolvedValue({ data: { sheets: rows, courses: [], worker_online: true } });
  api.post.mockResolvedValue({ data: {} });
});

const activeRows = [
  { ...rows[0], job: { state: 'processing', stage: 'grading' } },
  { ...rows[1], job: { state: 'queued', stage: 'queued' } },
  { ...rows[0], _id: 'done', roll_number: '103' },
];

test('stops a single running sheet and shows the pending stop state', async () => {
  api.get.mockResolvedValue({ data: { sheets: activeRows, courses: [], worker_online: true } });
  render(<Workspace />);
  await screen.findByText('101');
  api.get.mockResolvedValue({ data: { sheets: activeRows.map(s => s._id === 'one' ? { ...s, job: { ...s.job, cancel_requested: true } } : s), courses: [], worker_online: true } });
  fireEvent.click(screen.getAllByRole('button', { name: 'Stop 101' })[0]);
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/workspace/cancel', { sheet_ids: ['one'] }));
  await screen.findByText(/Stop requested for 1 sheet\./);
  await waitFor(() => screen.getAllByRole('button', { name: 'Stopping 101' }).forEach(button => expect(button).toBeDisabled()));
  expect(screen.queryByRole('button', { name: 'Stop 103' })).not.toBeInTheDocument();
});

test('bulk stop sends only selected active sheets and leaves completed results alone', async () => {
  api.get.mockResolvedValue({ data: { sheets: activeRows, courses: [], worker_online: true } });
  render(<Workspace />);
  await screen.findByText('101');
  expect(screen.getByRole('button', { name: 'Stop selected (0)' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Select running / queued on this page' }));
  expect(screen.getByRole('checkbox', { name: 'Select 103' })).not.toBeChecked();
  fireEvent.click(screen.getByRole('checkbox', { name: 'Select 103' }));
  fireEvent.click(screen.getByRole('button', { name: 'Stop selected (2)' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/workspace/cancel', { sheet_ids: ['one', 'two'] }));
  await screen.findByText(/Stop requested for 2 sheets\./);
});

test('failed stop requests display the error and allow retrying', async () => {
  api.get.mockResolvedValue({ data: { sheets: activeRows, courses: [], worker_online: true } });
  api.post.mockRejectedValueOnce({ response: { data: { error: 'Unable to stop work' } } });
  render(<Workspace />);
  await screen.findByText('102');
  fireEvent.click(screen.getByRole('button', { name: 'Stop 102' }));
  await screen.findByText('Unable to stop work');
  expect(screen.getByRole('button', { name: 'Stop 102' })).not.toBeDisabled();
  expect(screen.queryByText(/Stop requested for/)).not.toBeInTheDocument();
});

test('batch restores progress without duplicating result management', async () => {
  render(<Workspace />);
  await screen.findByText('101');
  expect(screen.queryByText('0/100 (0%)')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'View details' })).not.toBeInTheDocument();
  expect(screen.queryByRole('region', { name: 'Delete selected data' })).not.toBeInTheDocument();
  expect(screen.getByText('Timed out')).toBeInTheDocument();

});

test('already evaluated tab offers re-evaluation preserving the sheet identity', async () => {
  render(<Workspace />);
  await screen.findByText('101');
  fireEvent.click(screen.getByRole('button', { name: 'Already evaluated' }));
  expect(screen.queryByText('102')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('checkbox', { name: 'Select 101' }));
  fireEvent.click(screen.getByRole('button', { name: 'Re-evaluate selected' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/workspace/evaluate', { sheet_ids: ['one'], force: true }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Re-evaluate selected' })).not.toBeDisabled());
});

test('deletion requires explicit confirmation and carries only selected IDs', async () => {
  const prompt = jest.spyOn(window, 'prompt').mockReturnValue(null);
  render(<Workspace resultsOnly />);
  await screen.findByText('101');
  fireEvent.click(screen.getByRole('checkbox', { name: 'Select 101' }));
  fireEvent.click(screen.getByRole('button', { name: 'Delete (1)…' }));
  expect(api.post).not.toHaveBeenCalled();
  prompt.mockReturnValue('DELETE');
  fireEvent.click(screen.getByRole('button', { name: 'Delete (1)…' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/workspace/manage', {
    sheet_ids: ['one'], scope: 'cache', confirmation: 'DELETE',
  }));
  await screen.findByText('Selected data deleted. Source uploads are retained.');
  prompt.mockRestore();
});

test('explains OCR page progress without inventing completion percentages', () => {
  expect(stageLabel('extracting_student_page_2_of_5')).toBe('Reading the student answer sheet — page 2 of 5');
  expect(stageLabel('grading')).toBe('AI is marking the answer sheet');
  expect(stageLabel('building_marking_scheme')).toBe('Building the marking scheme');
  expect(stageLabel('mapping_student_answers')).toBe('Matching student answers to questions');
  expect(stageLabel('marking_questions')).toBe('Marking individual questions');
  expect(stageLabel('waiting_for_course_marking_scheme')).toBe('Waiting for the shared course marking scheme');
  expect(stageLabel('validating_course_marking_scheme')).toBe('Validating course marks before reading student sheets');
});

test('grading progress counts questions rather than displaying pages', async () => {
  api.get.mockResolvedValue({ data: { sheets: [{ ...rows[1], job: { state: 'processing', stage: 'marking_questions',
    progress: { completed: 2, total: 6, unit: 'questions' } } }], courses: [], worker_online: true } });
  render(<Workspace />);
  await screen.findByText('102');
  expect(screen.getByText('2 / 6 questions completed')).toBeInTheDocument();
  expect(screen.getByRole('progressbar', { name: 'Progress for 102' })).toHaveAttribute('value', '2');
});

test('administrator can save a parallel limit with a maximum of five', async () => {
  render(<Workspace />);
  await screen.findByText('101');
  const select = screen.getByRole('combobox', { name: 'Parallel evaluations' });
  expect(select.options).toHaveLength(5);
  fireEvent.change(select, { target: { value: '5' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save parallel limit' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/access/settings', { parallelism: 5 }));
  await screen.findByText('Parallel evaluation limit saved. Running work will finish; new work uses the updated limit.');
});

test('missing upload fields show specific red validation messages', async () => {
  render(<Workspace />);
  await screen.findByText('101');
  fireEvent.click(screen.getByRole('button', { name: 'Upload and check existing results' }));
  expect(screen.getByText('Enter an examination / session ID.')).toBeInTheDocument();
  expect(screen.getByText('Select a course folder containing the PDFs.')).toBeInTheDocument();
  expect(screen.getByLabelText(/Examination \/ session ID/)).toHaveAttribute('aria-invalid', 'true');
  expect(api.post).not.toHaveBeenCalled();
});

test('failed sheets show zero success, activity and retry guidance', async () => {
  api.get.mockResolvedValue({ data: { sheets: [rows[1]], courses: [], worker_online: true, capabilities: { admin_all_courses: true } } });
  render(<Workspace />);
  await screen.findByText('102');
  expect(screen.getByText(/1 sheets failed. Nothing is running/)).toBeInTheDocument();
  expect(screen.getByRole('progressbar', { name: /Evaluation completion/ })).toHaveAttribute('value', '0');
  expect(screen.getByRole('region', { name: 'Activity log' })).toHaveTextContent('Timed out');
  expect(screen.queryByText('No courses assigned yet. Contact your administrator.')).not.toBeInTheDocument();
});
test('running OCR shows measured page progress and saved events', async () => {
  api.get.mockResolvedValue({ data: { sheets: [{ ...rows[1], job: { state: 'processing', stage: 'extracting_student_page_2_of_8', progress: { completed: 1, total: 8 }, events: [{ stage: 'queued', at: '2026-10-17T08:00:00Z' }] } }], courses: [], worker_online: true, capabilities: { admin_all_courses: true } } });
  render(<Workspace />);
  await screen.findByText('102');
  expect(screen.getByRole('progressbar', { name: 'Progress for 102' })).toHaveAttribute('value', '1');
  expect(screen.getByRole('progressbar', { name: 'Progress for 102' })).toHaveAttribute('max', '8');
  expect(screen.getByRole('region', { name: 'Activity log' })).toHaveTextContent('Waiting for evaluation');
});


test('review results contains saved marks and verification without processing controls', async () => {
  render(<Workspace resultsOnly />);
  await screen.findByText('101');
  expect(screen.queryByText('102')).not.toBeInTheDocument();
  expect(screen.queryByRole('region', { name: 'Live progress' })).not.toBeInTheDocument();
  expect(screen.queryByRole('region', { name: 'Activity log' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Evaluate / use existing' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Mark selected verified' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Download combined workbook' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Verified results' }));
  expect(screen.queryByText('101')).not.toBeInTheDocument();
  expect(screen.getByText(/No saved results match/)).toBeInTheDocument();
});


test('delete controls explain each scope and block running work', async () => {
  api.get.mockResolvedValue({ data: { sheets: [{ ...rows[0], job: { state: 'processing', stage: 'grading' } }], courses: [], worker_online: true } });
  render(<Workspace resultsOnly />);
  await screen.findByText('101');
  fireEvent.click(screen.getByRole('checkbox', { name: 'Select 101' }));
  expect(screen.getByRole('button', { name: 'Delete (1)…' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Data to delete'), { target: { value: 'records' } });
  expect(screen.getByText(/Delete all marks, verification and attempt history/)).toBeInTheDocument();
  expect(screen.getByText(/Cancel selected evaluations and wait/)).toBeInTheDocument();
  expect(api.post).not.toHaveBeenCalled();
});

test('pagination sends server filters and loads details on demand', async () => {
  api.get.mockImplementation(url => Promise.resolve({ data: url.startsWith('/workspace/sheets/one') ? { sheet: rows[0] } : url === '/access' ? { courses: [] } : { sheets: [rows[0]], total: 120, counts: { review: 120 }, worker_online: true, examinations: ['exam-1'], course_codes: ['FS3401'] } }));
  render(<Workspace resultsOnly />);
  await screen.findByText('101');
  fireEvent.click(screen.getByRole('button', { name: 'View details' }));
  await screen.findByRole('dialog', { name: 'Result details' });
  expect(api.get).toHaveBeenCalledWith('/workspace/sheets/one', { params: { offset: 0 } });
  fireEvent.click(screen.getByRole('button', { name: 'Close details' }));
  fireEvent.click(screen.getByRole('button', { name: 'Next page' }));
  await waitFor(() => expect(api.get).toHaveBeenCalledWith('/workspace/sheets', expect.objectContaining({ params: expect.objectContaining({ page: 2, page_size: 50 }) })));
});


test('skipped courses expose issues and a corrected-folder upload with original exam settings', async () => {
  api.get.mockResolvedValue({ data: { sheets: rows, courses: [], worker_online: true,
    preparations: [{ _id: 'prep', exam_id: 'original-exam', exam_type: 'mst', max_marks: 50,
      state: 'completed', issues: ['CS101A: missing model_answer.pdf'] }] } });
  render(<Workspace />);
  await screen.findByText('CS101A: missing model_answer.pdf');
  fireEvent.click(screen.getAllByRole('button', { name: 'Upload corrected folders separately' })[0]);
  expect(screen.getByLabelText(/Examination \/ session ID/)).toHaveValue('original-exam');
  expect(screen.getByLabelText(/Maximum marks/)).toHaveValue(50);
  expect(screen.getByRole('button', { name: 'Upload corrected folders' })).toBeInTheDocument();
  expect(screen.getByText(/Choose only the corrected course folders/)).toBeInTheDocument();
});


test('paused sheets show explicit retry guidance and cannot be stopped', async () => {
  api.get.mockResolvedValue({ data: { sheets: [{ ...rows[1], job: { state: 'paused', stage: 'paused', error: 'Retry budget reached' } }], courses: [], worker_online: true } });
  render(<Workspace />);
  await screen.findByText('102');
  expect(screen.getAllByText('Paused — retry required').length).toBeGreaterThan(0);
  expect(screen.getByText(/Some sheets reached their retry budget/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Stop 102' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Failed — retry' }));
  expect(screen.getByText('102')).toBeInTheDocument();
});

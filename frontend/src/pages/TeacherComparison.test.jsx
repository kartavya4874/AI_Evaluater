import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import TeacherComparison from './TeacherComparison';
import api from '../services/api';
jest.mock('../services/api', () => ({ __esModule: true, default: { get: jest.fn(), post: jest.fn() } }));
const metrics = { uploaded: 1, compared: 1, excluded: 0, mae_pct: 4, bias_pct: 4, within_tolerance_pct: 0 };
const report = { _id: 'report', name: 'Pilot', state: 'draft', course_code: 'FS3401', split: 'calibration', independent: true, tolerance: 3, created_at: '2026-10-22T00:00:00Z', totals: metrics, questions: { ...metrics, uploaded: 0, compared: 0, mae_pct: null, bias_pct: null, within_tolerance_pct: null }, rows: [{ row: 2, roll_number: '001', teacher_marks: 72, max_marks: 100, ai_marks: 76, difference: 4, difference_pct: 4, status: 'matched' }] };
beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockResolvedValue({ data: { courses: ['FS3401'], reports: [] } });
  api.post.mockResolvedValue({ data: { report } });
});
test('upload previews independent marks before explicitly saving', async () => {
  render(<TeacherComparison />);
  await screen.findByRole('option', { name: 'FS3401' });
  fireEvent.change(screen.getByLabelText('Course'), { target: { value: 'FS3401' } });
  fireEvent.change(screen.getByLabelText('Comparison name'), { target: { value: 'Pilot' } });
  fireEvent.click(screen.getByLabelText('Teacher marked independently, before seeing AI scores'));
  fireEvent.change(screen.getByLabelText('Teacher marks file'), { target: { files: [new File(['teacher_marks,max_marks\n72,100'], 'marks.csv', { type: 'text/csv' })] } });
  fireEvent.click(screen.getByRole('button', { name: 'Preview comparison' }));
  expect(await screen.findByText('Pilot — Preview')).toBeInTheDocument();
  expect(api.post.mock.calls[0][1].get('independent')).toBe('true');
  expect(api.post).toHaveBeenCalledTimes(1);
  expect(screen.getByText('72/100')).toBeInTheDocument();
  expect(screen.getByText('Compared — outside tolerance')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Save comparison' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/workspace/teacher-comparisons/report/save', {}));
  expect(await screen.findByText(/saved separately from evaluation records/)).toBeInTheDocument();
});
test('opening a saved report and comparing latest preserves prior metrics for comparison', async () => {
  const change = { paired: 1, previous_compared: 1, current_compared: 1, newly_comparable: 0, no_longer_comparable: 0, before_mae_pct: 4, after_mae_pct: 4, mae_change_pct: 0, improved: 0, worsened: 0, unchanged: 1, same_prediction: 1 };
  api.post.mockResolvedValue({ data: { report: { ...report, change: { baseline_id: 'report', baseline_name: 'Pilot', baseline_created_at: report.created_at, totals: change, questions: { ...change, paired: 0 } } } } });
  api.get.mockImplementation(url => Promise.resolve({ data: url.endsWith('/report') ? { report: { ...report, state: 'saved' } } : { courses: ['FS3401'], reports: [{ ...report, state: 'saved' }] } }));
  render(<TeacherComparison />);
  fireEvent.click(await screen.findByRole('button', { name: 'Pilot' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Compare latest AI results' }));
  expect(await screen.findByRole('region', { name: 'Change from baseline' })).toHaveTextContent('4.00 → 4.00');
  expect(screen.getByText(/1 paired rows use the same saved prediction/)).toBeInTheDocument();
  expect(api.post).toHaveBeenCalledWith('/workspace/teacher-comparisons/report/compare-latest', {});
});

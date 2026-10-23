import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ResultsOverview from './ResultsOverview';
import api from '../services/api';
jest.mock('../services/api', () => ({ __esModule: true, default: { get: jest.fn(), post: jest.fn() }, updateManualEvaluation: jest.fn() }));
jest.mock('../context/AuthContext', () => ({ useAuth: () => ({ user: { role: 'admin' } }) }));
const old = { id: 'old', source: 'legacy', roll_number: '101', course_code: 'FS3401', max_marks: 100, result: { marks: 76, verification_revision: 'revision-1' } };
const fresh = { id: 'new', source: 'workspace', roll_number: '102', course_code: 'FS3401', max_marks: 100, result: { _id: 'attempt-1', marks: 85 } };
const data = { items: [old, fresh], total: 2, pending: 2, verified: 0, course_codes: ['FS3401'], examinations: [] };
beforeEach(() => { jest.clearAllMocks(); api.get.mockResolvedValue({ data }); api.post.mockResolvedValue({ data: {} }); });
const show = () => render(<MemoryRouter><ResultsOverview /></MemoryRouter>);

test('needs review sheets without marks open their reason and cannot be verified', async () => {
  const result = { status: 'needs_review', needs_review: true, marks: null, feedback: 'Missing allocations' };
  api.get.mockImplementation(url => Promise.resolve({ data: url.includes('/sheets/')
    ? { sheet: { active: null, job: { state: 'needs_review', error: 'Missing allocations' }, attempts: [] } }
    : { ...data, items: [{ ...fresh, result }], total: 1, pending: 0, needs_review: 1 } }));
  show();
  await screen.findByText('Missing allocations');
  expect(screen.getByRole('checkbox', { name: 'Select 102 workspace' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'View details' }));
  expect(await screen.findByRole('dialog')).toHaveTextContent('Missing allocations');
  expect(screen.queryByRole('button', { name: 'Mark this result verified' })).not.toBeInTheDocument();
});
test('one list and summary combines both stores without duplicate management sections', async () => {
  show();
  expect(await screen.findByText('76/100')).toBeInTheDocument();
  expect(screen.getByText('85/100')).toBeInTheDocument();
  expect(screen.getAllByRole('table')).toHaveLength(1);
  expect(within(screen.getByRole('region', { name: 'Results summary' })).getAllByText('2')).toHaveLength(2);
  expect(screen.queryByText('Previous batch results')).not.toBeInTheDocument();
  expect(screen.queryByText('Delete selected data')).not.toBeInTheDocument();
});
test('only previous records still contribute to the main total', async () => {
  api.get.mockResolvedValue({ data: { ...data, items: [old], total: 10, pending: 8, verified: 2 } });
  show();
  expect(await screen.findByText('76/100')).toBeInTheDocument();
  expect(within(screen.getByRole('region', { name: 'Results summary' })).getByText('10')).toBeInTheDocument();
});
test('mixed verification uses source-specific revision and attempt identities', async () => {
  show();
  await screen.findByText('76/100');
  fireEvent.click(screen.getByRole('button', { name: 'Select unverified on this page' }));
  fireEvent.click(screen.getByRole('button', { name: 'Mark selected verified (2)' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/workspace/verify', { source: 'legacy', items: [{ id: 'old', revision: 'revision-1' }] }));
  expect(api.post).toHaveBeenCalledWith('/workspace/verify', { source: 'workspace', items: [{ id: 'new', attempt_id: 'attempt-1' }] });
  expect(await screen.findByText('Selected results verified.')).toBeInTheDocument();
});
test('details retrieve full saved feedback and dismiss outside', async () => {
  api.get.mockImplementation(url => Promise.resolve({ data: url.includes('/legacy/') ? { result: { ...old.result, feedback: 'Complete saved feedback' } } : data }));
  show();
  await screen.findByText('76/100');
  fireEvent.click(screen.getAllByRole('button', { name: 'View details' })[0]);
  expect(await screen.findByText('Complete saved feedback')).toBeInTheDocument();
  fireEvent.click(screen.getByTestId('result-details-backdrop'));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});
test('course filters query the combined endpoint', async () => {
  show(); await screen.findByText('76/100');
  fireEvent.change(screen.getByLabelText('Course'), { target: { value: 'FS3401' } });
  await waitFor(() => expect(api.get).toHaveBeenCalledWith('/workspace/results', { params: { page: 1, page_size: 50, view: 'all', course_code: 'FS3401', exam_id: undefined } }));
});
test('storage failure does not report zero results', async () => {
  api.get.mockRejectedValue(new Error('Storage unavailable')); show();
  expect(await screen.findByRole('alert')).toHaveTextContent('Storage unavailable');
  expect(screen.queryByText('No saved results match these filters.')).not.toBeInTheDocument();
});

test('search and source filters run on the server and clear selection', async () => {
  show(); await screen.findByText('76/100');
  fireEvent.click(screen.getByRole('button', { name: 'Select unverified on this page' }));
  fireEvent.change(screen.getByLabelText('Search results'), { target: { value: '101' } });
  fireEvent.click(screen.getByRole('button', { name: 'Search' }));
  await waitFor(() => expect(api.get).toHaveBeenCalledWith('/workspace/results', { params: expect.objectContaining({ page: 1, q: '101' }) }));
  expect(screen.getByRole('button', { name: 'Mark selected verified (0)' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Record type'), { target: { value: 'legacy' } });
  await waitFor(() => expect(api.get).toHaveBeenCalledWith('/workspace/results', { params: expect.objectContaining({ source: 'legacy', q: '101' }) }));
  fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
  await waitFor(() => expect(screen.getByLabelText('Search results')).toHaveValue(''));
});


test('partial verification refreshes rows and retains the failure message', async () => {
  api.post.mockResolvedValueOnce({ data: {} }).mockRejectedValueOnce(new Error('Saved result changed'));
  show(); await screen.findByText('76/100');
  fireEvent.click(screen.getByRole('button', { name: 'Select unverified on this page' }));
  fireEvent.click(screen.getByRole('button', { name: 'Mark selected verified (2)' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Saved result changed');
  await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2));
  expect(screen.getByRole('button', { name: 'Mark selected verified (0)' })).toBeDisabled();
});

test('a removed active result gives feedback instead of a silent details click', async () => {
  api.get.mockImplementation(url => Promise.resolve({ data: url.includes('/sheets/') ? { sheet: { active: null } } : data }));
  show(); await screen.findByText('85/100');
  fireEvent.click(screen.getAllByRole('button', { name: 'View details' })[1]);
  expect(await screen.findByRole('alert')).toHaveTextContent('no longer active');
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

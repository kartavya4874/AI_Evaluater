import { act, render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ManageResults from './ManageResults';
import api, { deleteEvaluation } from '../services/api';

jest.mock('../services/api', () => ({ __esModule: true, default: { get: jest.fn(), post: jest.fn() }, deleteEvaluation: jest.fn() }));
const items = [
  { id: 'same', source: 'workspace', roll_number: '101', status: 'ready', marks: null },
  { id: 'same', source: 'legacy', roll_number: '102', status: 'completed', marks: 76, max_marks: 100 },
];
beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockResolvedValue({ data: { items, total: 2, counts: { workspace: 1, legacy: 1 }, course_codes: [] } });
  api.post.mockResolvedValue({ data: { success: true } });
  deleteEvaluation.mockResolvedValue({ success: true });
});
test('all inventory includes saved evaluations and sheets without marks', async () => {
  render(<MemoryRouter><ManageResults /></MemoryRouter>);
  expect(await screen.findByText('76/100')).toBeInTheDocument();
  expect(screen.getByText('No saved marks', { selector: 'td' })).toBeInTheDocument();
  expect(api.get).toHaveBeenCalledWith('/workspace/inventory', { params: { page: 1, page_size: 50, source: 'all', course_code: undefined } });
});
test('mixed selection deletes from the correct stores only after confirmation', async () => {
  const prompt = jest.spyOn(window, 'prompt').mockReturnValue(null);
  render(<MemoryRouter><ManageResults /></MemoryRouter>);
  fireEvent.click(await screen.findByRole('button', { name: 'Select all on this page' }));
  fireEvent.click(screen.getByRole('button', { name: 'Apply to selected (2)…' }));
  expect(api.post).not.toHaveBeenCalled();
  expect(deleteEvaluation).not.toHaveBeenCalled();
  prompt.mockReturnValue('DELETE');
  fireEvent.click(screen.getByRole('button', { name: 'Apply to selected (2)…' }));
  await waitFor(() => expect(deleteEvaluation).toHaveBeenCalledWith('same'));
  expect(api.post).toHaveBeenCalledWith('/workspace/manage', { sheet_ids: ['same'], scope: 'records', confirmation: 'DELETE' });
  expect(await screen.findByText('Management action completed for 2 selected record(s).')).toBeInTheDocument();
  prompt.mockRestore();
});
test('cache-only selection cannot silently delete a saved evaluation', async () => {
  render(<MemoryRouter><ManageResults /></MemoryRouter>);
  fireEvent.click(await screen.findByRole('checkbox', { name: 'Select 102 legacy' }));
  fireEvent.change(screen.getByLabelText('Action'), { target: { value: 'cache' } });
  expect(screen.getByRole('button', { name: 'Apply to selected (1)…' })).toBeDisabled();
});

test('stopping selected active workspace sheets retains mixed selection and enables Apply when idle', async () => {
  const activeItems = [{ ...items[0], status: 'processing' }, items[1]];
  api.get.mockResolvedValue({ data: { items: activeItems, total: 2, counts: { workspace: 1, legacy: 1 } } });
  render(<MemoryRouter><ManageResults /></MemoryRouter>);
  fireEvent.click(await screen.findByRole('button', { name: 'Select all on this page' }));
  expect(screen.getByRole('button', { name: 'Apply to selected (2)…' })).toBeDisabled();
  api.get.mockResolvedValue({ data: { items, total: 2, counts: { workspace: 1, legacy: 1 } } });
  fireEvent.click(screen.getByRole('button', { name: 'Stop selected active sheets (1)' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Apply to selected (2)…' })).toBeEnabled());
  expect(api.post).toHaveBeenCalledWith('/workspace/cancel', { sheet_ids: ['same'] });
  expect(deleteEvaluation).not.toHaveBeenCalled();
  expect(screen.getByRole('checkbox', { name: 'Select 101 workspace' })).toBeChecked();
  expect(screen.getByRole('checkbox', { name: 'Select 102 legacy' })).toBeChecked();
});

test('active selection refreshes automatically and remains selected after work stops', async () => {
  jest.useFakeTimers();
  try {
    api.get.mockResolvedValue({ data: { items: [{ ...items[0], status: 'processing' }], total: 1, counts: { workspace: 1, legacy: 0 } } });
    render(<MemoryRouter><ManageResults /></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button', { name: 'Select all on this page' }));
    expect(screen.getByRole('button', { name: 'Apply to selected (1)…' })).toBeDisabled();
    api.get.mockResolvedValue({ data: { items: [items[0]], total: 1, counts: { workspace: 1, legacy: 0 } } });
    await act(async () => { jest.advanceTimersByTime(3000); });
    expect(screen.getByRole('button', { name: 'Apply to selected (1)…' })).toBeEnabled();
  } finally { jest.useRealTimers(); }
});

test('failed stop requests keep deletion blocked and display the error', async () => {
  api.get.mockResolvedValue({ data: { items: [{ ...items[0], status: 'queued' }], total: 1, counts: { workspace: 1, legacy: 0 } } });
  api.post.mockRejectedValueOnce(new Error('Stop failed'));
  render(<MemoryRouter><ManageResults /></MemoryRouter>);
  fireEvent.click(await screen.findByRole('button', { name: 'Select all on this page' }));
  fireEvent.click(screen.getByRole('button', { name: 'Stop selected active sheets (1)' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Stop failed');
  expect(screen.getByRole('button', { name: 'Apply to selected (1)…' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Stop selected active sheets (1)' })).toBeEnabled();
});

test('management search and status filters query all pages and clear stale selections', async () => {
  render(<MemoryRouter><ManageResults /></MemoryRouter>);
  fireEvent.click(await screen.findByRole('button', { name: 'Select all on this page' }));
  fireEvent.change(screen.getByLabelText('Search answer sheets'), { target: { value: '102' } });
  fireEvent.click(screen.getByRole('button', { name: 'Search' }));
  await waitFor(() => expect(api.get).toHaveBeenCalledWith('/workspace/inventory', { params: expect.objectContaining({ page: 1, q: '102' }) }));
  expect(screen.getByRole('button', { name: 'Apply to selected (0)…' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'no_marks' } });
  await waitFor(() => expect(api.get).toHaveBeenCalledWith('/workspace/inventory', { params: expect.objectContaining({ q: '102', status: 'no_marks' }) }));
});


test('failed sheets without marks open their processing error and can be dismissed', async () => {
  api.get.mockImplementation(url => Promise.resolve({ data: url.includes('/sheets/')
    ? { sheet: { max_marks: 100, active: null, job: { state: 'error', error: 'Unreadable page' }, attempts: [] } }
    : { items, total: 2, counts: { workspace: 1, legacy: 1 }, course_codes: [] } }));
  render(<MemoryRouter><ManageResults /></MemoryRouter>);
  fireEvent.click(await screen.findByRole('button', { name: 'View details' }));
  expect(await screen.findByRole('dialog')).toHaveTextContent('Unreadable page');
  expect(screen.getByRole('link', { name: 'Open evaluation workspace' })).toHaveAttribute('href', '/evaluate/batch');
  fireEvent.click(screen.getByTestId('result-details-backdrop'));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

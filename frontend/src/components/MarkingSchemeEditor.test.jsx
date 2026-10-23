import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import MarkingSchemeEditor from './MarkingSchemeEditor';
import api from '../services/api';
jest.mock('../services/api', () => ({ __esModule: true, default: { get: jest.fn(), post: jest.fn() } }));

beforeEach(() => { jest.clearAllMocks(); api.get.mockResolvedValue({ data: { scheme: {} } }); api.post.mockResolvedValue({ data: { success: true } }); });

test('admin enters a scheme and switching exam type clears it before loading', async () => {
  render(<MarkingSchemeEditor />);
  fireEvent.change(screen.getByLabelText('Marking course code'), { target: { value: 'FS3401' } });
  fireEvent.click(screen.getByRole('button', { name: 'Load course scheme' }));
  await screen.findByLabelText('Scheme maximum marks');
  fireEvent.change(screen.getByLabelText('Scheme maximum marks'), { target: { value: '10' } });
  fireEvent.change(screen.getByLabelText('Question ID 1'), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText('Marks 1'), { target: { value: '10' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save marking scheme' }));
  await screen.findByText('Marking scheme saved. Retry affected sheets from Batch evaluation.');
  expect(api.post).toHaveBeenCalledWith('/access/marking-scheme', expect.objectContaining({ course_code: 'FS3401', exam_type: 'end_sem', max_marks: 10 }));
  fireEvent.change(screen.getByLabelText('Marking examination type'), { target: { value: 'mst' } });
  expect(screen.queryByRole('button', { name: 'Save marking scheme' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Load course scheme' }));
  await waitFor(() => expect(api.get).toHaveBeenLastCalledWith('/access/marking-scheme', { params: { course_code: 'FS3401', exam_type: 'mst' } }));
  expect(await screen.findByLabelText('Scheme maximum marks')).toHaveValue(null);
});

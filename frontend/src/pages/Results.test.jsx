import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import Results from './Results';
import { getEvaluation } from '../services/api';

jest.mock('../services/api', () => ({ getEvaluation: jest.fn() }));

const show = () => render(<MemoryRouter initialEntries={['/results/saved-id']}><Routes>
  <Route path="/results/:evaluationId" element={<Results />} />
</Routes></MemoryRouter>);

test('refresh loads the saved result and preserves a legitimate zero', async () => {
  getEvaluation.mockResolvedValue({ evaluation: { marks: 0, max_marks: 10, percentage: 0, feedback: 'Checked', strengths: [], missing_points: [] } });
  show();
  expect(await screen.findByText('Checked')).toBeInTheDocument();
  expect(getEvaluation).toHaveBeenCalledWith('saved-id');
  expect(screen.getByText('0', { selector: '.marks-value' })).toBeInTheDocument();
});

test('failed result lookup never reports successful completion', async () => {
  getEvaluation.mockRejectedValue({ response: { data: { error: 'Evaluation not found' } } });
  show();
  expect(await screen.findByRole('alert')).toHaveTextContent('Evaluation not found');
  expect(screen.queryByText('Evaluation Complete!')).not.toBeInTheDocument();
});

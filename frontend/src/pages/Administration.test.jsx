import React from 'react';
import { render as renderUI, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
const render = ui => renderUI(<MemoryRouter>{ui}</MemoryRouter>);
import Administration from './Administration';
import api from '../services/api';
jest.mock('../context/AuthContext', () => ({ useAuth: () => ({ user: { role: 'admin', email: 'root@example.com' } }) }));
jest.mock('../services/api', () => ({ __esModule: true, default: { get: jest.fn(), post: jest.fn() } }));
beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockResolvedValue({ data: { courses: [], faculty: [], bootstrap_admin: 'root@example.com' } });
  api.post.mockResolvedValue({ data: {} });
});
test('admin can approve another administrator from the form', async () => {
  render(<Administration />);
  await screen.findByText(/Initial administrator:/);
  fireEvent.change(screen.getByLabelText('Full name *'), { target: { value: 'Second admin' } });
  fireEvent.change(screen.getByLabelText('Google email *'), { target: { value: 'second@example.com' } });
  fireEvent.change(screen.getByLabelText('Account role'), { target: { value: 'admin' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save account' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/access/faculty', { name: 'Second admin', email: 'second@example.com', role: 'admin' }));
  await screen.findByText('Account saved. They can now sign in with Google.');
});
test('missing account details trigger field validation', async () => {
  render(<Administration />);
  await screen.findByText(/Initial administrator:/);
  fireEvent.click(screen.getByRole('button', { name: 'Save account' }));
  expect(screen.getByLabelText('Full name *')).toBeInvalid();
  expect(screen.getByLabelText('Google email *')).toBeInvalid();
  expect(api.post).not.toHaveBeenCalled();
});

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import UserGuide from './UserGuide';
import Navigation from '../components/Navigation';
import { useAuth } from '../context/AuthContext';

jest.mock('../context/AuthContext', () => ({ useAuth: jest.fn() }));

test('administrator can discover both the guide and the standalone single-sheet form', () => {
  useAuth.mockReturnValue({ user: { role: 'admin', email: 'admin@example.com' }, logout: jest.fn() });
  render(<MemoryRouter><Navigation /><UserGuide /></MemoryRouter>);
  expect(screen.getByRole('link', { name: 'User guide' })).toHaveAttribute('href', '/guide');
  fireEvent.click(screen.getByRole('button', { name: /Evaluate/ }));
  expect(screen.getByRole('link', { name: 'Single' })).toHaveAttribute('href', '/evaluate/single');
  expect(screen.getByRole('link', { name: 'Batch' })).toHaveAttribute('href', '/evaluate/batch');
  expect(screen.queryByRole('link', { name: 'Workspace & progress' })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Previous evaluations' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Print / save as PDF' })).toBeInTheDocument();
});

test('assigned users get the guide and workspace single-sheet instructions without admin-only links', () => {
  useAuth.mockReturnValue({ user: { role: 'teacher', email: 'teacher@example.com' }, logout: jest.fn() });
  render(<MemoryRouter><Navigation /><UserGuide /></MemoryRouter>);
  expect(screen.getByRole('link', { name: 'User guide' })).toHaveAttribute('href', '/guide');
  fireEvent.click(screen.getByRole('button', { name: /Evaluate/ }));
  expect(screen.queryByRole('link', { name: 'Single' })).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Batch' })).toHaveAttribute('href', '/evaluate/batch');
  expect(screen.getByText(/select only that student's checkbox/)).toBeInTheDocument();
});

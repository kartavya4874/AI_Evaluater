import { render, screen } from '@testing-library/react';
import App from './App';
jest.mock('./services/api', () => ({ __esModule: true, default: { get: jest.fn() }, getMe: jest.fn() }));
test('requires approved Google sign-in', async () => {
  render(<App />);
  expect(await screen.findByText('Sign in with the Google email approved by your administrator.')).toBeInTheDocument();
});

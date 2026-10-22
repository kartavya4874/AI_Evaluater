import { render, screen } from '@testing-library/react';
import App from './App';
jest.mock('./services/api', () => ({ __esModule: true, default: { get: jest.fn() } }));

jest.mock('./context/AuthContext', () => ({
  AuthProvider: ({ children }) => children,
  useAuth: () => ({ user: { role: 'admin' }, loading: false }),
}));
jest.mock('./pages/ResultsOverview', () => () => <div>Combined review results</div>);
jest.mock('./pages/Evaluate', () => () => <div>Single evaluation form</div>);
jest.mock('./pages/Workspace', () => () => <div>Batch evaluation form</div>);

test.each(['/results', '/batch-results'])('%s opens the combined review view', async path => {
  window.history.replaceState({}, '', path);
  render(<App />);
  expect(await screen.findByText('Combined review results')).toBeInTheDocument();
  expect(window.location.pathname).toBe('/results');
});

test.each(['/', '/batch', '/evaluate', '/evaluate/batch'])('%s opens batch evaluation', async path => {
  window.history.replaceState({}, '', path);
  render(<App />);
  expect(await screen.findByText('Batch evaluation form')).toBeInTheDocument();
  expect(window.location.pathname).toBe('/evaluate/batch');
});

test('single evaluation has its own route', async () => {
  window.history.replaceState({}, '', '/evaluate/single');
  render(<App />);
  expect(await screen.findByText('Single evaluation form')).toBeInTheDocument();
  expect(screen.queryByText('Batch evaluation form')).not.toBeInTheDocument();
});


test('unknown addresses have a recovery page instead of an empty screen', async () => {
  window.history.replaceState({}, '', '/missing-page');
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
});

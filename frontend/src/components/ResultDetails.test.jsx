import React, { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import ResultDetails from './ResultDetails';

function Preview() {
  const [open, setOpen] = useState(false);
  return <><button onClick={() => setOpen(true)}>View details</button>{open && <ResultDetails modal result={{ marks: 76, feedback: 'Full feedback' }} maxMarks={100} onClose={() => setOpen(false)} />}</>;
}

test('clicking inside keeps details open; clicking outside closes and restores focus', () => {
  render(<Preview />);
  const trigger = screen.getByRole('button', { name: 'View details' });
  trigger.focus(); fireEvent.click(trigger);
  expect(document.body.style.overflow).toBe('hidden');
  fireEvent.click(screen.getByText('Full feedback', { selector: 'p' }));
  expect(screen.getByRole('dialog')).toBeInTheDocument();
  fireEvent.click(screen.getByTestId('result-details-backdrop'));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(document.body.style.overflow).not.toBe('hidden');
  expect(trigger).toHaveFocus();
});

test('Escape closes details and Tab keeps keyboard focus in the dialog', () => {
  render(<Preview />);
  fireEvent.click(screen.getByRole('button', { name: 'View details' }));
  const dialog = screen.getByRole('dialog');
  fireEvent.keyDown(dialog, { key: 'Tab', shiftKey: true });
  const close = screen.getByRole('button', { name: 'Close details' });
  expect(close).toHaveFocus();
  fireEvent.keyDown(close, { key: 'Tab' });
  expect(close).toHaveFocus();
  fireEvent.keyDown(close, { key: 'Escape' });
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

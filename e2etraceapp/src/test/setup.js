import '@testing-library/jest-dom';

// jsdom does not implement scrollIntoView — stub it globally so components
// that call element.scrollIntoView() (e.g. SmartGuidancePanel chatEndRef)
// do not throw in the test environment.
if (typeof window !== 'undefined') {
  window.Element.prototype.scrollIntoView = vi.fn();
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
}


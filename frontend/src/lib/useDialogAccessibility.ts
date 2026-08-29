import { useEffect, useRef, type RefObject } from 'react';

const dialogStack: symbol[] = [];
const FOCUSABLE = 'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])';

interface Options {
  closeDisabled?: boolean;
  initialFocusSelector?: string;
  returnFocusSelector?: string;
}

export function useDialogAccessibility<T extends HTMLElement>(
  open: boolean,
  onClose: () => void,
  options: Options = {},
): RefObject<T> {
  const ref = useRef<T>(null);
  const closeRef = useRef(onClose);
  const closeDisabledRef = useRef(Boolean(options.closeDisabled));
  const initialFocusSelectorRef = useRef(options.initialFocusSelector || '[data-autofocus]');
  const returnFocusSelectorRef = useRef(options.returnFocusSelector || '');
  closeRef.current = onClose;
  closeDisabledRef.current = Boolean(options.closeDisabled);
  initialFocusSelectorRef.current = options.initialFocusSelector || '[data-autofocus]';
  returnFocusSelectorRef.current = options.returnFocusSelector || '';

  useEffect(() => {
    if (!open) return;
    const id = Symbol('dialog');
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialogStack.push(id);

    const onKeyDown = (event: KeyboardEvent) => {
      if (dialogStack[dialogStack.length - 1] !== id || !ref.current) return;
      if (event.key === 'Escape' && !closeDisabledRef.current) {
        event.preventDefault();
        event.stopImmediatePropagation();
        closeRef.current();
        return;
      }
      if (event.key !== 'Tab') return;
      const focusable = Array.from(ref.current.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (!focusable.length) {
        event.preventDefault();
        ref.current.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    window.addEventListener('keydown', onKeyDown);
    const focusTimer = window.setTimeout(() => {
      const initial = ref.current?.querySelector<HTMLElement>(initialFocusSelectorRef.current)
        || ref.current?.querySelector<HTMLElement>(FOCUSABLE);
      (initial || ref.current)?.focus();
    }, 30);

    return () => {
      window.clearTimeout(focusTimer);
      window.removeEventListener('keydown', onKeyDown);
      const index = dialogStack.lastIndexOf(id);
      if (index >= 0) dialogStack.splice(index, 1);
      const restoreFocus = () => {
        const previousIsUsable = previouslyFocused?.isConnected
          && previouslyFocused !== document.body
          && !ref.current?.contains(previouslyFocused);
        const fallback = returnFocusSelectorRef.current
          ? document.querySelector<HTMLElement>(returnFocusSelectorRef.current)
          : null;
        (previousIsUsable ? previouslyFocused : fallback)?.focus();
      };
      restoreFocus();
      window.setTimeout(restoreFocus, 0);
    };
  }, [open]);

  return ref;
}

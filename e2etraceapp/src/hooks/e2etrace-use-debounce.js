import { useState, useEffect } from 'react';

/**
 * A custom hook that debounces a value.
 * @param {*} value The value to debounce for E2ETrace.
 * @param {number} delay The debounce delay in milliseconds.
 * @returns The debounced value.
 */
export function e2etraceUseDebounce(value, delay) {
    const [debouncedValue, setDebouncedValue] = useState(value);

    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedValue(value);
        }, delay);

        return () => clearTimeout(handler);
    }, [value, delay]);

    return debouncedValue;
}
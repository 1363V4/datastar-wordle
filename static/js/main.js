function react_to_key(evt, current, squares) {
    if (/^[A-Za-z]$/.test(evt.key)) {
        if (current < 6) {
            squares[current] = evt.key.toUpperCase();
            current++;
        }
        return ['CONTINUE', [current, squares]];
    }
    
    if (evt.key === 'Backspace') {
        if (current > 0) {
            current--;
            squares[current] = '';
        }
        return ['CONTINUE', [current, squares]];
    }
    
    if (evt.key === 'Enter') {
        if (current === 6) {
            return ['OK', [current, squares]];
        }
    }
    
    return ['CONTINUE', [current, squares]];
}

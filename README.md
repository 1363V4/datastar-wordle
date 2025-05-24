# Datastar Wordle with Async Quart & Long-Lived SSE

A **Wordle** game clone built with **Datastar** and **Quart**, demonstrating the power of **long-lived Server-Sent Events (SSE) connections** with async Python. This project showcases how Datastar's persistent SSE streams paired with CQRS event-sourced architecture enables real-time, reactive applications with minimal complexity.

[Quart](https://quart.palletsprojects.com/en/latest/index.html) is an asyncio reimplementation of the popular Flask microframework API.

## Overview

By leveraging **Quart's async architecture** with **Redis pub/sub**, we achieve true real-time reactivity where server-side events can instantly update the client without any user interaction.

## Project Structure

```
datastar-wordle/
├── app.py                # Main Quart application with async SSE
├── templates/
│   └── index.html        # Landing page with SSE connection
├── static/
│   ├── css/
│   │   └── main.css      # Game styling with CSS animations
│   ├── js/
│   │   ├── main.js       # Keyboard handling helper functions
│   │   └── datastar.js   # Datastar framework
│   └── img/              # Game assets and loading animations
├── words.py              # Word list for the game
└── data.json             # TinyDB game state storage
```

## Technology Stack

- **Backend**: Quart with Redis pub/sub for real-time communication
- **Frontend**: Datastar for reactive UI with persistent SSE connections
- **Communication**: Long-lived Server-Sent Events with Redis message broker
- **State Management**: Shared state between server and client via SSE streams
- **Database**: TinyDB for game persistence with Redis for real-time events

## Long-Lived SSE Architecture Benefits

### Traditional vs. Persistent SSE

**Synchronous Flask Pattern**:

```
Client → POST request → Server processes → Single SSE response → Connection closes
```

**Async Quart Pattern**:

```
Client → SSE connection opens → Persistent stream → Real-time updates → Connection persists
```

### Key Advantages of Long-Lived Connections

1. **True Real-Time**: Server can push updates instantly without client requests
2. **Reduced Latency**: No connection overhead for each interaction
3. **Better UX**: Seamless state transitions and live updates
4. **Event-Driven**: React to server-side events, not just user actions

## Datastar Integration & Features

### 1. Persistent SSE Connection

```html
<main id="main" class="gc" data-on-load="@get('/main')" data-indicator-fetching>
  <img src="/static/img/bars-fade.svg" data-show="$fetching" />
</main>
```

**Server-Side Async Stream**:

```python
@app.get('/main')
async def main():
    db_id = session['db_id']
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(str(db_id))

    async def event():
        while True:
            try:
                if await pubsub.get_message():
                    # Real-time data updates
                    data = games.get(doc_id=db_id)
                    html = await main_view(lines, current)

                    # Push state and UI updates
                    yield SSE.merge_signals({'current': 0, 'squares': ['', '', '', '', '', '']})
                    yield SSE.merge_fragments(fragments=[html])

                    # Handle game over scenarios with delays
                    game_over = await is_game_over(lines)
                    if game_over == "WIN":
                        await asyncio.sleep(3)  # Allow animations
                        html = f"<main id='main'>YAY, found the word in {current} tries!</main>"
                        yield SSE.merge_fragments(fragments=[html])

            except asyncio.CancelledError:
                await pubsub.unsubscribe(str(db_id))
                break

    return await make_datastar_response(event())
```

**Why This Matters**:

- **Persistent Connection**: Single connection handles all game interactions
- **Async Processing**: Non-blocking operations for thousands of concurrent games
- **Real-Time State**: Server-driven updates without client polling
- **Redis Integration**: Scalable message broadcasting across processes
- **Graceful Cleanup**: Automatic subscription cleanup on disconnect

### 2. Bidirectional State Sync

```javascript
function react_to_key(evt, current, squares) {
  if (/^[A-Za-z]$/.test(evt.key)) {
    if (current < 6) {
      squares[current] = evt.key.toUpperCase();
      current++;
    }
    return ["CONTINUE", [current, squares]];
  }

  if (evt.key === "Backspace") {
    if (current > 0) {
      current--;
      squares[current] = "";
    }
    return ["CONTINUE", [current, squares]];
  }

  if (evt.key === "Enter") {
    if (current === 6) {
      return ["OK", [current, squares]];
    }
  }

  return ["CONTINUE", [current, squares]];
}
```

```html
<main
  data-on-keydown__window="
    response = react_to_key(evt, $current, $squares);
    rc = response[0];
    $current = response[1][0];
    $squares = [...response[1][1]];
    rc == 'OK' ? @post('/attempt') : null;"
>
  <div
    class="square"
    data-attr-current="$current == 0"
    data-text="$squares[0]"
  ></div>
  <div
    class="square"
    data-attr-current="$current == 1"
    data-text="$squares[1]"
  ></div>
  <!-- ... more squares ... -->
</main>
```

**Server-Side Signal Updates**:

```python
# Reset client state after processing attempt
yield SSE.merge_signals({'current': 0, 'squares': ['', '', '', '', '', '']})

# Update DOM with new game state
yield SSE.merge_fragments(fragments=[html])
```

**Key Features**:

- **Real-Time Signal Sync**: Server can reset/update client signals
- **`data-on-keydown__window`**: Global event binding without focus requirements
- **Conditional Actions**: `rc == 'OK' ? @post('/attempt') : null` for smart requests
- **Spread Operator Support**: `$squares = [...response[1][1]]` for array updates
- **JavaScript Integration**: JavaScript helper functions work with Datastar signals
- **Conditional HTTP Actions**: Only POST when word is complete

### 3. Redis Pub/Sub Integration

**Event Broadcasting**:

```python
@app.post('/attempt')
async def attempt():
    squares = (await request.json).get('squares')
    db_id = session['db_id']

    # Process game logic
    if squares:
        # Update database state
        games.update(fields={'lines': current_lines, 'current': current+1}, doc_ids=[db_id])

        # Broadcast to SSE stream via Redis
        await redis_client.publish(str(db_id), "ping")

    return "", 200
```

**SSE Stream Response**:

```python
async def event():
    while True:
        if await pubsub.get_message():  # Redis message triggers update
            # Fetch fresh data and update client
            data = games.get(doc_id=db_id)
            html = await main_view(lines, current)
            yield SSE.merge_fragments(fragments=[html])
```

**Architecture Benefits**:

- **Decoupled Communication**: POST endpoints just trigger events, SSE handles updates
- **Horizontal Scaling**: Redis enables multi-process/multi-server deployments
- **Event Sourcing**: Clean separation between commands (POST) and queries (SSE)
- **Real-Time Broadcasting**: Instant updates across all connected clients

### 4. Async CSS Animation Coordination

**Server-Controlled Animation Timing**:

```python
async def main_view(lines, current):
    for n in range(NO_LINES):
        if n != current:  # Completed lines get animations
            line = lines.get(str(n), default_line)
            html += f'''
            <div class="line">
                <div style="animation: rotate .2s linear forwards" class="square {line[0][1]}">{line[0][0]}</div>
                <div style="animation: rotate .2s linear forwards .4s" class="square {line[1][1]}">{line[1][0]}</div>
                <div style="animation: rotate .2s linear forwards .8s" class="square {line[2][1]}">{line[2][0]}</div>
                <div style="animation: rotate .2s linear forwards 1.2s" class="square {line[3][1]}">{line[3][0]}</div>
                <div style="animation: rotate .2s linear forwards 1.6s" class="square {line[4][1]}">{line[4][0]}</div>
                <div style="animation: rotate .2s linear forwards 2s" class="square {line[5][1]}">{line[5][0]}</div>
            </div>
            '''
```

**Async Animation Delays**:

```python
game_over = await is_game_over(lines)
if game_over == "WIN":
    await asyncio.sleep(3)  # Wait for letter animations to complete
    html = f"<main id='main'>YAY, found the word!</main>"
    yield SSE.merge_fragments(fragments=[html])
```

**Why This Works**:

- **Server Timing Control**: Async delays coordinate with CSS animations
- **Non-Blocking Waits**: `asyncio.sleep()` doesn't block other connections
- **Staggered Reveals**: Progressive 0.4s delays create satisfying feedback
- **State-Driven Animations**: Server determines when animations should play

### 5. Automatic Session Management

**Seamless Game Initialization**:

```python
@app.before_request
async def before_request():
    if not session.get('db_id'):
        db_id = games.insert({
            'word': choice(words),
            'current': 0,
            'lines': {}
        })
        session['db_id'] = db_id
```

**Fresh Game Reset**:

```python
@app.get('/')
async def index():
    session.clear()  # Force new game
    return await render_template('index.html')
```

**Benefits**:

- **Automatic Setup**: No manual game initialization required
- **Session Isolation**: Each browser session gets independent game state
- **Clean Restart**: Simple page refresh starts new game
- **Database Linking**: Session automatically links to persistent game data

## Real-Time Features Enabled by Long-Lived SSE

### 1. Instant State Synchronization

Unlike the synchronous Flask version that required user actions to trigger updates, this async implementation can:

- **Push server-side changes** to the client instantly
- **Synchronize state** across multiple browser tabs
- **Handle real-time events** like multiplayer features or live updates
- **Maintain persistent connections** for thousands of concurrent users

### 2. Advanced Game Flow Control

```python
async def event():
    # Process game state
    yield SSE.merge_fragments(fragments=[html])

    # Check for game completion
    game_over = await is_game_over(lines)
    match game_over:
        case "WIN":
            await asyncio.sleep(3)  # Allow animations
            yield SSE.merge_fragments(fragments=[win_html])
        case "LOSE":
            await asyncio.sleep(3)  # Allow animations
            yield SSE.merge_fragments(fragments=[lose_html])
```

**Capabilities**:

- **Timed Transitions**: Server controls when UI updates occur
- **Animation Coordination**: Async delays sync with CSS animations
- **Multi-Step Updates**: Single action can trigger multiple UI changes
- **Context-Aware Responses**: Server can make complex decisions about UI flow

## Running the Application

### Prerequisites

- Python 3.9+
- Redis server
- uv package manager

### Setup

1. **Start Redis**:

```bash
redis-server
```

2. **Install dependencies**:

```bash
uv sync
```

3. **Run the application**:

```bash
uv run app.py
```

4. **Play**: Open `http://localhost:5000` in your browser

### Game Rules

- **6-letter words** with **5 attempts**
- Type letters directly (no clicking required)
- **Backspace** to delete letters
- **Enter** to submit when word is complete
- Colors indicate: **Green** (correct position), **Yellow** (wrong position), **Grey** (not in word)

## Architecture Comparison: Sync vs Async

### Synchronous Flask (datastar-wordle-flask)

```python
# Request-response pattern
@app.post('/attempt/<details>')
def attempt(details):
    # Process synchronously
    return SSE.merge_fragments(fragments=[html])  # Single response
```

**Characteristics**:

- ✅ Simple to understand and debug
- ✅ Familiar request-response patterns
- ❌ Connection overhead for each interaction
- ❌ No real-time server-initiated updates
- ❌ Limited to user-triggered actions

### Asynchronous Quart (this project)

```python
# Persistent stream pattern
async def event():
    while True:
        if await pubsub.get_message():  # Real-time trigger
            yield SSE.merge_fragments(fragments=[html])  # Continuous updates
```

**Characteristics**:

- ✅ True real-time capabilities
- ✅ Server-initiated updates
- ✅ Server-side animation timing control

## When to Use Each Pattern

### Use Synchronous SSE When:

- Restricted to ephemeral environments (serverless, lambda, etc.)
- Building traditional web apps with occasional updates
- When simple request-response workflows are sufficient
- Don't need real-time server-initiated features

### Use Long-Lived SSE When:

- Need true real-time features (live updates, collaboration)
- Server-side events should trigger UI changes
- Building highly interactive applications
- Performance and scalability are priorities
- Want to coordinate complex animation sequences

## Key Datastar Patterns Demonstrated

### Long-Lived SSE Streams

```python
async def event():
    while True:
        yield SSE.merge_fragments(fragments=[html])
```

### Signal State Synchronization

```python
yield SSE.merge_signals({'current': 0, 'squares': ['', '', '', '', '', '']})
```

### Window-Level Event Binding

```html
data-on-keydown__window="complex_logic_here"
```

### Redis Event Broadcasting

```python
await redis_client.publish(str(db_id), "ping")
```

### Async Animation Coordination

```python
await asyncio.sleep(3)  # Wait for CSS animations
yield SSE.merge_fragments(fragments=[updated_html])
```

## Why Long-Lived SSE Matters

This project demonstrates that **modern web applications can be real-time and reactive** without the complexity of WebSockets or heavy JavaScript frameworks. By combining:

- **Quart's async capabilities**: Non-blocking, high-performance server
- **Datastar's SSE streams**: Persistent connections with reactive updates
- **Redis pub/sub**: Scalable real-time message broadcasting
- **Simple state management**: Server-driven UI with minimal client logic

We achieve:

- ✅ **True real-time** server-initiated updates
- ✅ **Scalable architecture** for production deployments
- ✅ **Rich animations** with server-controlled timing

**The Result**: A delightful, real-time Wordle experience that showcases the full potential of Datastar's SSE-driven architecture with Quart in Python.

from quart import Quart, session, render_template, request
from datastar_py.sse import ServerSentEventGenerator as SSE
from datastar_py.quart import make_datastar_response

from tinydb import TinyDB
import redis.asyncio as redis

import asyncio
from random import choice

from words import words


# CONFIG

app = Quart(__name__)
app.secret_key = 'a_secret_key'

db = TinyDB("data.json", sort_keys=True, indent=2)
games = db.table('games')

redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

NO_LINES = 5

# UTILS

async def is_game_over(lines):
    if lines:
        last_line = [*lines.values()][-1]
        if all([square[1] == "green" for square in last_line]):
            return "WIN"
        elif lines.get(str(NO_LINES-1)):
            return "LOSE"
    return "NOPE" 

# VIEWS

async def main_view(lines, current):
    html = f'''
    <main 
    id="main" 
    class="gc"
    style="grid-template-rows: repeat({NO_LINES + 1}, 1fr);"
    data-indicator-fetching
    data-on-keydown__window="
    response = react_to_key(evt, $current, $squares);
    rc = response[0];
    $current = response[1][0];
    $squares = [...response[1][1]];
    rc == 'OK' ? @post('/attempt') : null;"
    >
    '''
    for n in range(NO_LINES):
        if n == current:
            html += f'''
            <div class="line">
                <div class="square" data-attr-current="$current == 0" data-text="$squares[0]"></div>
                <div class="square" data-attr-current="$current == 1" data-text="$squares[1]"></div>
                <div class="square" data-attr-current="$current == 2" data-text="$squares[2]"></div>
                <div class="square" data-attr-current="$current == 3" data-text="$squares[3]"></div>
                <div class="square" data-attr-current="$current == 4" data-text="$squares[4]"></div>
                <div class="square" data-attr-current="$current == 5" data-text="$squares[5]"></div>
            </div>
            '''
        else:
            line = lines.get(str(n), [["", ""], ["", ""], ["", ""], ["", ""], ["", ""], ["", ""]])
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
    html += '''
    <img src="/static/img/bars-fade.svg" class="gc" data-show="$fetching">
    </main>
    '''
    return html

# APP

@app.before_request
async def before_request():
    if not session.get('db_id'): 
        db_id = games.insert({
            'word': choice(words),
            'current': 0,
            'lines': {}
        })
        session['db_id'] = db_id

@app.get('/')
async def index():
    session.clear()
    return await render_template('index.html')

@app.get('/main')
async def main():
    db_id = session['db_id']
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(str(db_id))
    async def event():
        while True:
            try:
                if await pubsub.get_message():
                    data = games.get(doc_id=db_id)
                    lines = data.get('lines')
                    current = data.get('current')
                    word = data.get('word')
                    html = await main_view(lines, current)
                    yield SSE.merge_signals({'current': 0, 'squares': ['', '', '', '', '', '']})
                    yield SSE.merge_fragments(fragments=[html])
                    game_over = await is_game_over(lines)
                    match game_over:
                        case "WIN":
                            await asyncio.sleep(3)
                            html = f"<main id='main' class='gc'>YAY, found the word in {current} tries!</main>"
                            yield SSE.merge_fragments(fragments=[html])
                        case "LOSE":
                            await asyncio.sleep(3)
                            html = f"<main id='main' class='gc'>:(, the word was {word}...</main>"
                            yield SSE.merge_fragments(fragments=[html])
                        case "NOPE":
                            pass
                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                await pubsub.unsubscribe(str(db_id))
                break
    return await make_datastar_response(event())

@app.post('/attempt')
async def attempt():
    squares = (await request.json).get('squares')
    db_id = session['db_id']
    data = games.get(doc_id=db_id)
    word = data['word']
    if squares:
        diffs = []
        for good_letter, square in zip(word, squares):
            if good_letter == square:
                diffs += [[good_letter, 'green']]
            elif square in word:
                diffs += [[square, 'yellow']]
            else:
                diffs += [[square, 'grey']]
        current = data['current']
        current_lines = data['lines']
        current_lines[str(current)] = diffs
        games.update(fields={'lines': current_lines, 'current': current+1}, doc_ids=[db_id])
        await redis_client.publish(str(db_id), "ping")
    return "", 200

if __name__ == '__main__':
    app.run(debug=True)

from threading import Lock
try:
    import readline
except ImportError:
    import pyreadline as readline

lock = Lock()


def rlinput(prompt, prefill=''):
    readline.set_startup_hook(lambda: readline.insert_text(prefill))
    try:
        return input(prompt)
    finally:
        readline.set_startup_hook()
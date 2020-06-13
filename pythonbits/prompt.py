# -*- coding: utf-8 -*-


def yesno(question, default):
    while True:
        choices = '[Y/n]' if default else '[y/N]'
        choice = input('%s %s ' % (question, choices))
        if not choice:
            return default
        elif choice.casefold() == 'y':
            return True
        elif choice.casefold() == 'n':
            return False

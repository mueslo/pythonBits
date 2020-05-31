# -*- coding: utf-8 -*-
import os
import re
import copy
import inspect
try:
    import readline
except ImportError:
    import pyreadline as readline


from .logging import log


def rlinput(prompt, prefill=''):
    readline.set_startup_hook(lambda: readline.insert_text(prefill))
    try:
        return input(prompt)
    finally:
        readline.set_startup_hook()


class SubmissionAttributeError(Exception):
    pass


re_frender = re.compile("^_render_(?=[a-z_]*$)")


class RegisteringType(type):
    def __init__(cls, name, bases, attrs):
        cls.registry = copy.deepcopy(getattr(cls, 'registry',
                                             {'mappers': {}, 'types': {}}))

        def add_mapper(f, ff, fft):
            log.debug("{} adding mapper {} for {} ({})",
                      cls.__name__, f, ff, fft)
            if f in cls.registry:
                log.warning("Overwriting {} for class {} with {} "
                            "(previous value: {})", f, name, ff,
                            cls.registry['mappers'][f])
            cls.registry['mappers'][f] = ff
            cls.registry['types'][ff] = fft

        # get form_field mappers from dunder string
        form_field_mappers = getattr(cls, '__form_fields__', {})
        for field, (form_field, form_field_type) in form_field_mappers.items():
            add_mapper(field, form_field, form_field_type)

        for key, val in attrs.items():
            try:
                form_field, form_field_type = getattr(val, 'form_field')
            except AttributeError:
                pass  # most attributes are not a form_field mapper
            else:
                field, n = re.subn(re_frender, '', key)
                assert n == 1  # only then is it a field renderer
                add_mapper(field, form_field, form_field_type)

            # get fields that need finalization
            if getattr(val, 'needs_finalization', False):
                field, n = re.subn(re_frender, '', key)
                assert n == 1  # only then is it a field renderer
                cls._to_finalize = getattr(cls, '_to_finalize', []) + [field]


form_field_types = {'text', 'checkbox', 'file'}  # todo select


def form_field(field, type='text'):
    def decorator(f):
        f.form_field = (field, type)
        return f
    return decorator


def finalize(f):
    f.needs_finalization = True
    return f


class CachedRenderer(object):
    def __init__(self, **kwargs):
        log.debug("Creating cached renderer {}", kwargs)
        self.fields = kwargs
        self.depends_on = {}

    def __getitem__(self, field):
        # todo: better way to track dependencies. explicit @requires decorator?
        try:
            # get first calling field
            caller = next(level[3] for level in inspect.stack()
                          if level[3].startswith('_render_'))
        except StopIteration:
            pass
        else:
            caller, n = re.subn(re_frender, '', caller, count=1)
            if n:  # called by another cached field
                self.depends_on[field] = self.depends_on.setdefault(
                    field, set()) | {caller}
                log.debug('Adding {} dependency {} -> {}',
                          type(self).__name__, caller, field)

        try:
            return self.fields[field]
        except KeyError:
            try:
                field_renderer = getattr(self, '_render_' + field)
            except AttributeError:
                raise SubmissionAttributeError(
                    self.__class__.__name__ + " does not contain or "
                    "has no rules to generate field '" + field + "'")

            log.debug('Rendering field {}[\'{}\']', type(self).__name__, field)
            rv = field_renderer()
            self.fields[field] = rv
            return rv

    def __setitem__(self, key, value):
        self.invalidate_field_cache(key)
        self.fields[key] = value

    def invalidate_field_cache(self, field):
        try:
            dependent_fields = self.depends_on.pop(field)
        except KeyError:
            pass
            self.fields.pop(field, None) and log.debug(
                'del inval leaf {}', field)
        else:
            for f in dependent_fields:
                self.invalidate_field_cache(f)
            self.fields.pop(field, None) and log.debug(
                'del inval node {}', field)


def build_payload(fd_val, form_field, fft):
    # it's either a form field id
    if isinstance(form_field, str):
        if fft == 'text':
            yield 'data', form_field, fd_val
        elif fft == 'checkbox' and fd_val:
            yield 'data', form_field, 'on'
        elif fft == 'file':
            yield 'files', form_field, (os.path.basename(fd_val),
                                        open(fd_val, 'rb'),
                                        'application/octet-stream')

    # or a rule to generate form field ids
    elif callable(form_field):
        for i, val in enumerate(fd_val):
            for pair in build_payload(
                    val, form_field(i, val), fft):
                yield pair  # yield from

    else:
        raise AssertionError(form_field, fd_val)


def toposort(depends_on):
    depends_on = copy.deepcopy(depends_on)
    sorted_funcs = []

    depends = (set(f for v in depends_on.values() for f in v) -
               set(depends_on.keys()))
    for d in depends:
        depends_on[d] = set()

    ready_funcs = set(func for func, deps in depends_on.items() if not deps)
    while ready_funcs:
        executed = ready_funcs.pop()
        depends_on.pop(executed)
        sorted_funcs.append(executed)
        from_selection = [func for func, deps in depends_on.items()
                          if executed in deps]
        for func in from_selection:
            depends_on[func].remove(executed)
            if not depends_on[func]:
                ready_funcs.add(func)

    if depends_on:
        raise Exception("Cyclic dependencies present: {}".format(
            depends_on))
    else:
        return sorted_funcs


class Submission(CachedRenderer, metaclass=RegisteringType):
    def __repr__(self):
        return "\n".join(
            ["Field {k}:\n\t{v}\n".format(k=k, v=v)
             for k, v in list(self.fields.items())])

    @finalize
    def _render_submit(self):
        # todo dict map field names
        # todo truncate long fields in preview

        return self.show_fields(list(self.registry['mappers'].keys()))

    def _finalize_submit(self):
        return self.submit(self['payload'])

    def needs_finalization(self):
        return set(self._to_finalize) & set(self.fields.keys())

    def finalize(self):
        needs_finalization = self.needs_finalization()
        order = toposort(self.depends_on)
        needs_finalization = sorted(needs_finalization,
                                    key=lambda x: order.index(x),
                                    reverse=True)
        for f in needs_finalization:
            self[f] = getattr(self, '_finalize_' + f)()

        setattr(self, 'finalized', None)

    @staticmethod
    def submit(payload):
        raise NotImplementedError

    def show_fields(self, fields):
        def format_val(val):
            if isinstance(val, str) and os.path.exists(val):
                s = 'file://' + str(val)
            elif isinstance(val, list) or isinstance(val, tuple):
                s = "\n".join(format_val(v) for v in val)
            else:
                s = val
                log.debug("No rule for formatting {} {}", type(val), val)
            return str(s)

        consolewidth = 80
        s = ""
        for field in fields:
            val = self[field]
            field_str = field
            if field in self._to_finalize and not hasattr(self, 'finalized'):
                field_str += " (will be finalized)"
            s += ("  " + field_str + "  ").center(consolewidth, "=") + "\n"
            s += format_val(val) + "\n"

        s += "="*consolewidth + "\n"
        return s

    def confirm_finalization(self, fields):
        # todo: disable editing on certain fields, e.g. those dependent on
        #       fields that require finalization

        print(self.show_fields(fields))
        while True:
            print("Reminder: YOU are responsible for following the "
                  "submission rules!")
            choice = input('Finalize these values? This will upload or '
                           'submit all necessary data. [y/n] ')

            if not choice:
                pass
            elif choice.lower() == 'n':
                amend = input("Amend a field? [N/<field name>] ")
                if not amend.lower() or amend.lower() == 'n':
                    return False

                try:
                    val = self[amend]
                except SubmissionAttributeError:
                    print("No field named", amend)
                    print("Choices are:", list(self.fields.keys()))
                else:
                    if not (isinstance(val, str) or
                            isinstance(val, bool) or
                            isinstance(val, int)):
                        print("Can't amend value of type", type(val))
                        continue

                    new_value = rlinput("New (empty to cancel): ", val)

                    if new_value:
                        if isinstance(val, bool):
                            string_true = {'true', 'True', 'y', 'yes'}
                            string_false = {'false', 'False', 'n', 'no'}
                            assert new_value in string_true | string_false
                            new_value = (new_value not in string_false)
                        elif isinstance(val, int):
                            new_value = int(new_value)

                        self[amend] = new_value

                        print(self.show_fields(fields))

            elif choice.lower() == 'y':
                return True

    def _render_payload(self):
        # must be rendered directly from editable fields

        payload = {'files': {}, 'data': {}}
        for fd_name, form_field in self.registry['mappers'].items():
            fd_val = self[fd_name]
            fft = self.registry['types'][form_field]
            # todo: handle input types
            for req_type, ff, val in build_payload(fd_val, form_field, fft):
                payload[req_type][ff] = val

        return payload

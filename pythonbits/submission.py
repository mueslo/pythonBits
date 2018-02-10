# -*- coding: utf-8 -*-

import re
import copy

from .tracker import Tracker


class SubmissionAttributeError(Exception):
    pass


class InvalidSubmission(SubmissionAttributeError):
    pass


class FieldRenderException(Exception):
    pass


class RegisteringType(type):
    def __init__(cls, name, bases, attrs):
        cls.registry = copy.deepcopy(getattr(cls, 'registry', {'mappers': {}, 'types': {}}))

        # get parent form_field mappers, should be covered by above
        #for base in bases:
        #    parent_registry = getattr(base, 'registry', {'mappers': {},
        #                                                 'types': {}})
        #    cls.registry.update(**copy.deepcopy(parent_registry))

        def add_mapper(f, ff, fft):
            print cls.__name__, 'adding mapper', f, 'for', ff, '({})'.format(fft)
            if field in cls.registry:
                print "Warning, overwriting", field, "for class", name, 'with', form_field, 'previous value', cls.registry['mappers'][field]
            cls.registry['mappers'][field] = form_field
            cls.registry['types'][form_field] = form_field_type

        # get form_field mappers from dunder string
        form_field_mappers = getattr(cls, '__form_fields__', {})
        for field, (form_field, form_field_type) in form_field_mappers.items():
            add_mapper(field, form_field, form_field_type)


        for key, val in attrs.iteritems():
            try:
                form_field, form_field_type = getattr(val, 'form_field')
            except AttributeError as e:
                pass  # most attributes are not a form_field mapper
            else:
                field, n = re.subn('^_render_', '', key)
                assert n == 1  # only then is it a field renderer
                add_mapper(field, form_field, form_field_type)

        # get fields that may change
        for key, val in attrs.iteritems():
            if getattr(val, 'needs_finalization', False):
                field, n = re.subn('^_render_', '', key)
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

# todo: better way to track dependencies. explicit @invalidates decorator?
import inspect


class CachedRenderer(object):
    def __init__(self, **kwargs):
        self.fields = kwargs
        self.depends_on = {}

    def __getitem__(self, field):
        caller, n = re.subn('^_render_', '', inspect.stack()[1][3])
        if n:  # called by another cached field
            print 'caller name:', caller, 'tried to get', field, type(self).__name__
            self.depends_on[field] = self.depends_on.setdefault(field, []) + [caller]

        try:
            return self.fields[field]
        except KeyError:
            try:
                field_renderer = getattr(self, '_render_' + field)
            except AttributeError:
                raise SubmissionAttributeError(
                    self.__class__.__name__ + " does not contain or "
                    "has no rules to generate field '" + field + "'")

            try:
                rv = field_renderer()
            except SubmissionAttributeError as e:
                raise FieldRenderException(
                    'Could not render field ' + field + ':\n' + e.message)

            self.fields[field] = rv
            return rv

    def __setitem__(self, key, value):
        raise Exception('not yet implemented')

    def invalidate_field_cache(self, field):
        try:
            dependent_fields = self.depends_on[field]
        except KeyError:
            if self.fields.pop(field, None):
                print 'delete invalidation leaf', field
        else:
            for f in dependent_fields:
                self.invalidate_field_cache(f)
            if self.fields.pop(field, None):
                print 'delete', field

    def get_fields(self, fields):
        # check that all required values are non-zero
        missing_keys = []
        for k in fields:
            try:
                v = self[k]
            except SubmissionAttributeError as e:
                print e
                missing_keys.append(k)
            else:
                if not v:
                    raise InvalidSubmission(
                        "Value of key {key} is {value}".format(key=k, value=v))

        if missing_keys:
            raise InvalidSubmission("Missing field(s) (" +
                                    ", ".join(missing_keys) + ")")

class Submission(CachedRenderer):
    __metaclass__ = RegisteringType

    def __repr__(self):
        return "\n".join(
            ["Field {k}:\n\t{v}\n".format(k=k, v=v)
             for k, v in self.fields.items()])

    def _render_category(self):
        return None

    @finalize
    def _render_submit(self):
        payload = self['payload']

        # todo dict map field names
        # todo truncate mediainfo in preview
        consolewidth = 80
        for name, value in self['payload'].items():
            print ("  " + name +
                        "  ").center(consolewidth, "=")
            print unicode(value)

        while True:
            print ("Reminder: YOU are responsible for following the "
                   "submission rules!")
            choice = raw_input('Submit these values? [y/n] ')

            if not choice:
                pass
            elif choice.lower() == 'n':
                """
                amend = raw_input("Amend a field? [N/<field name>] ")
                if not amend.lower() or amend.lower() == 'n':
                    return "Cancelled by user"

                try:
                    val = self['payload']['data'][amend]
                except KeyError:
                    print "No field named", amend
                    print "Choices are:", self['payload']['data'].keys()
                else:
                    print "Current value:", val
                    new_value = raw_input("New value (empty to cancel): ")

                    if new_value:
                        self['payload']['data'][amend] = new_value
                        del self.fields['payload_preview']
                        print self['payload_preview']
                """
                return False
            elif choice.lower() == 'y':
                return True

    def _finalize_submit(self):
        # submit
        #t = Tracker()
        #url = t.upload(**payload)
        url = 'url'
        print 'would upload now'
        print self['payload']
        return url

    def needs_finalization(self):
        return set(self._to_finalize) & set(self.fields.keys())

    def finalize(self):
        # deletes field caches of fields dependent on those that require
        # finalization

        needs_finalization = self.needs_finalization()

        for f in needs_finalization:
            self.invalidate_field_cache(f)

        for f in needs_finalization:
            self.fields[f] = getattr(self, '_finalize_' + f)()

        # finalize:
        #  upload and invalidate any images _finalize_<image>
        #  submit torrentfile _finalize_<submit>
        #  finalize torrentfile

    def _render_payload(self):
        # must be rendered directly from editable fields
        def pair_fields_and_values(fd_val, form_field):
            # it's either a form field id
            if isinstance(form_field, basestring):
                yield form_field, fd_val

            # or a rule to generate form field ids
            elif callable(form_field):
                    for i, val in enumerate(fd_val):
                        for pair in pair_fields_and_values(
                                val, form_field(i, val)):
                            yield pair  # yield from

            else:
                raise AssertionError(form_field, fd_val)


        payload = {}
        print type(self).__name__
        print self.registry['mappers'].items()
        for fd_name, form_field in self.registry['mappers'].items():
            fd_val = self[fd_name]
            print self.registry['types'][form_field], form_field
            # todo: handle input types
            payload.update(pair_fields_and_values(fd_val, form_field))


        return payload
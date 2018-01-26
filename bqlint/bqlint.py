#!/usr/bin/env python
# -*- coding: utf-8 -*-

from fnmatch import fnmatch
from optparse import OptionParser
import inspect
import os
import re
import sqlparse
import sys

__version__ = '0.5.1dev'

DEFAULT_EXCLUDE = '.svn,CVS,.bzr,.hg,.git'
DEFAULT_IGNORE = 'E24'
MAX_LINE_LENGTH = 79

INDENT_REGEX = re.compile(r'([ \t]*)')
RAISE_COMMA_REGEX = re.compile(r'raise\s+\w+\s*(,)')
SELFTEST_REGEX = re.compile(r'(Okay|[EW]\d{3}):\s(.*)')
ERRORCODE_REGEX = re.compile(r'[EW]\d{3}')
DOCSTRING_REGEX = re.compile(r'u?r?["\']')
WHITESPACE_AROUND_OPERATOR_REGEX = \
    re.compile('([^\w\s]*)\s*(\t|  )\s*([^\w\s]*)')
EXTRANEOUS_WHITESPACE_REGEX = re.compile(r'[[({] | []}),;:]')
WHITESPACE_AROUND_NAMED_PARAMETER_REGEX = \
    re.compile(r'[()]|\s=[^=]|[^=!<>]=\s')

KEYWORDS_STDSQL = {
    "WINDOW": sqlparse.tokens.Keyword
}


WHITESPACE = ' \t'

BINARY_OPERATORS = frozenset([
    '**=', '*=', '+=', '-=', '!=', '<>',
    '%=', '^=', '&=', '|=', '==', '/=', '//=', '<=', '>=', '<<=', '>>=',
    '%', '^', '&', '|', '=', '/', '//', '<', '>', '<<'
])
UNARY_OPERATORS = frozenset(['>>', '**', '*', '+', '-'])
OPERATORS = BINARY_OPERATORS | UNARY_OPERATORS
SKIP_TOKENS = frozenset([])
BENCHMARK_KEYS = ('directories', 'files', 'logical lines', 'physical lines')

options = None
args = None
err_format = "{path}:{line}:{column}:{type} {message}"


def tabs_or_spaces(physical_line, indent_char):
    r"""
    This is a test

    >>> tabs_or_spaces('  \t', ' ')
    (2, 'E101 indentation contains mixed spaces and tabs')
    >>> tabs_or_spaces('   ', ' ')
    """
    indent = INDENT_REGEX.match(physical_line).group(1)
    for offset, char in enumerate(indent):
        if char != indent_char:
            return offset, "E101 indentation contains mixed spaces and tabs"


def tabs_obsolete(physical_line):
    r"""
    For new projects, spaces-only are strongly recommended over tabs.  Most
    editors have features that make this easy to do.

    >>> tabs_obsolete('\tSELECT 1')
    (0, 'W191 indentation contains tabs')
    >>> tabs_obsolete('  SELECT 1')
    """
    indent = INDENT_REGEX.match(physical_line).group(1)
    if indent.count('\t'):
        return indent.index('\t'), "W191 indentation contains tabs"


def trailing_whitespace(physical_line):
    r"""
    JCR: Trailing whitespace is superfluous.
    FBM: Except when it occurs as part of a blank line (i.e. the line is
         nothing but whitespace). According to Python docs[1] a line with only
         whitespace is considered a blank line, and is to be ignored. However,
         matching a blank line to its indentation level avoids mistakenly
         terminating a multi-line statement (e.g. class declaration) when
         pasting code into the standard Python interpreter.

         [1] http://docs.python.org/reference/lexical_analysis.html#blank-lines

    The warning returned varies on whether the line itself is blank, for easier
    filtering for those who want to indent their blank lines.

    >>> trailing_whitespace('SELECT 1   ')
    (8, 'W291 trailing whitespace')
    >>> trailing_whitespace('   ')
    (0, 'W293 blank line contains whitespace')
    >>> trailing_whitespace('SELECT 1')
    >>> trailing_whitespace('')
    """
    physical_line = physical_line.rstrip('\n')    # chr(10), newline
    physical_line = physical_line.rstrip('\r')    # chr(13), carriage return
    physical_line = physical_line.rstrip('\x0c')  # chr(12), form feed, ^L
    stripped = physical_line.rstrip()
    if physical_line != stripped:
        if stripped:
            return len(stripped), "W291 trailing whitespace"
        else:
            return 0, "W293 blank line contains whitespace"


def trailing_blank_lines(physical_line, lines, line_number):
    r"""
    JCR: Trailing blank lines are superfluous.

    >>> trailing_blank_lines('\n', ['SELECT 1','\n'], 2)
    (0, 'W391 blank line at end of file')
    """
    if physical_line.strip() == '' and line_number == len(lines):
        return 0, "W391 blank line at end of file"


def missing_newline(physical_line):
    r"""

    >>> missing_newline('SELECT 1\n')
    >>> missing_newline('SELECT 1')
    (8, 'W292 no newline at end of file')
    """
    if physical_line.rstrip() == physical_line:
        return len(physical_line), "W292 no newline at end of file"


def maximum_line_length(physical_line):
    """
    Limit all lines to a maximum of 79 characters.

    There are still many devices around that are limited to 80 character
    lines; plus, limiting windows to 80 characters makes it possible to have
    several windows side-by-side.  The default wrapping on such devices looks
    ugly.  Therefore, please limit all lines to a maximum of 79 characters.
    For flowing long blocks of text (docstrings or comments), limiting the
    length to 72 characters is recommended.
    >>> maximum_line_length('SELECT' + ' ' * 81 + '1')
    (79, 'E501 line too long (88 characters)')
    """
    line = physical_line.rstrip()
    length = len(line)

    if length > MAX_LINE_LENGTH:
        return MAX_LINE_LENGTH, "E501 line too long (%d characters)" % length


def dont_use_hypen_comment(physical_line):
    """
    >>> dont_use_hypen_comment('-- SP')
    (0, "W000 Don't use `--` comment string, you shoudld use `#` comment style") # noqa
    """
    error_msg = ("W000 Don't use `--` comment string, "
                 + "you shoudld use `#` comment style")
    try:
        offset = physical_line.index('--')
        return (offset, error_msg)
    except ValueError:
        pass


<<<<<<< HEAD:bqlint.py
##############################################################################
# Plugins (check functions) for tokens
##############################################################################

def use_upper_case_keyword(token: sqlparse.sql.Token, offset):
    if token.is_keyword and not token.value.isupper():
        return offset, f"W000 Use upper case for keyword `{token}`"


def use_explicit_alias(token: sqlparse.sql.Token, offset):

    if token.ttype == sqlparse.tokens.Name:
        identifier = token.parent
        while not identifier.get_name():
            identifier = identifier.parent

        if identifier.get_alias() is None \
                and identifier.get_alias() != identifier.get_name():
            return

        if not any(
            token.is_keyword and token.normalized == 'AS'
            for token in identifier.flatten()
        ):
            return offset, f"W000 Alias needs keywords"



##############################################################################
=======
#
>>>>>>> pr-1:bqlint/bqlint.py
# Framework to run all checks
#

def find_checks(argument_name):
    """
    Find all globally visible functions where the first argument name
    starts with argument_name.
    """
    checks = []
    for name, function in list(globals().items()):
        if not inspect.isfunction(function):
            continue

        args = inspect.getfullargspec(function)[0]
        if args and args[0].startswith(argument_name):
            checks.append((name, function, args))

    checks.sort()
    return checks


<<<<<<< HEAD:bqlint.py
class Checker():
=======
def message(args):
    """
    Temporary function to pass pep8 check
    """
    pass


class Checker(object):
    """
    Load a Python source file, tokenize it, check coding style.
    """
>>>>>>> pr-1:bqlint/bqlint.py

    def __init__(self, file_path):
        self.file_path = file_path if file_path else None


    def check_physical(self, line):
        """
        Run all physical checks on a raw input line.
        """
        self.physical_line = line
        self.indent_char = ' '
        for name, check, argument_names in options.physical_checks:
            result = self.run_check(check, argument_names)
            if result is not None:
                offset, text = result
                self.report_error(self.line_number, offset, text, check)

<<<<<<< HEAD:bqlint.py

    def check_token(self, token, offset):
=======
    def build_tokens_line(self):
        """
        Build a logical line from tokens.
        """
        pass
        # self.mapping = []
        # logical = []
        # length = 0
        # previous = None
        # for token in self.tokens:
        #     token_type, text = token[0:2]
        #     if token_type in SKIP_TOKENS:
        #         continue
        #     if token_type == tokenize.STRING:
        #         text = mute_string(text)
        #     if previous:
        #         end_line, end = previous[3]
        #         start_line, start = token[2]
        #         if end_line != start_line:  # different row
        #             prev_text = self.lines[end_line - 1][end - 1]
        #             if prev_text == ',' or (prev_text not in '{[('
        #                                     and text not in '}])'):
        #                 logical.append(' ')
        #                 length += 1
        #         elif end != start:  # different column
        #             fill = self.lines[end_line - 1][end:start]
        #             logical.append(fill)
        #             length += len(fill)
        #     self.mapping.append((length, token))
        #     logical.append(text)
        #     length += len(text)
        #     previous = token
        # self.logical_line = ''.join(logical)
        # assert self.logical_line.lstrip() == self.logical_line
        # assert self.logical_line.rstrip() == self.logical_line

    def check_logical(self):
>>>>>>> pr-1:bqlint/bqlint.py
        """
        Run all physical checks on a raw input line.
        """
<<<<<<< HEAD:bqlint.py
        self.token = token
        self.offset = offset
        for name, check, argument_names in options.token_checks:
=======
        options.counters['logical lines'] += 1
        self.build_tokens_line()
        # first_line = self.lines[self.mapping[0][1][2][0] - 1]
        # indent = first_line[:self.mapping[0][1][2][1]]
        self.previous_indent_level = self.indent_level
        # self.indent_level = expand_indent(indent)
        if options.verbose >= 2:
            print(self.logical_line[:80].rstrip())
        for name, check, argument_names in options.logical_checks:
            if options.verbose >= 4:
                print('   ' + name)
>>>>>>> pr-1:bqlint/bqlint.py
            result = self.run_check(check, argument_names)
            if result is not None:
                offset, text = result
                self.report_error(self.line_number, offset, text, check)


    def run_check(self, check, argument_names):
        """
        Run a check plugin.
        """
<<<<<<< HEAD:bqlint.py
        arguments = []
        for name in argument_names:
            arguments.append(getattr(self, name))
        return check(*arguments)


    def run(self):
        tokens = []
        with open(self.file_path) as fin:
            self.lines = fin.readlines()

        for line_number, line in enumerate(self.lines):
            self.line_number = line_number
            self.check_physical(line)

            offset = 0
            tokens = sqlparse.parse(line)[0].flatten()
            for token in tokens:
                self.check_token(token, offset)
                offset += len(str(token))
=======
        self.expected = expected or ()
        self.line_offset = line_offset
        self.line_number = 0
        self.file_errors = 0
        self.indent_char = None
        self.indent_level = 0
        self.previous_logical = ''
        self.blank_lines = 0
        self.blank_lines_before_comment = 0
        self.tokens = []
        # parens = 0
        for line in self.readline():
            self.check_physical(line)
            # token = sqlparse.split(line)

            # self.tokens.append(token)
            # token_type, text = token, str(token)
            # if token_type == tokenize.OP and text in '([{':
            #     parens += 1
            # if token_type == tokenize.OP and text in '}])':
            #     parens -= 1
            # if token_type == tokenize.NEWLINE and not parens:
            #     self.check_logical()
            #     self.blank_lines = 0
            #     self.blank_lines_before_comment = 0
            #     self.tokens = []
            # if token_type == tokenize.NL and not parens:
            #     if len(self.tokens) <= 1:
            #         # The physical line contains only this token.
            #         self.blank_lines += 1
            #     self.tokens = []
            # if token_type == tokenize.COMMENT:
            #     source_line = token[4]
            #     token_start = token[2][1]
            #     if source_line[:token_start].strip() == '':
            #         self.blank_lines_before_comment = max(self.blank_lines,
            #             self.blank_lines_before_comment)
            #         self.blank_lines = 0
            #     if text.endswith('\n') and not parens:
            # The comment also ends a physical line.  This works around
            # Python < 2.6 behaviour, which does not generate NL after
            # a comment which is on a line by itself.
            #         self.tokens = []
        return self.file_errors
>>>>>>> pr-1:bqlint/bqlint.py

    def report_error(self, line_number, offset, text, check):
        """
        Report an error, according to options.
        """
<<<<<<< HEAD:bqlint.py
        print(err_format.format(
            path=self.file_path, line=line_number, column=offset,
            type=text[0], message=text
        ))

=======
        code = text[:4]
        if ignore_code(code):
            return
        if options.quiet == 1 and not self.file_errors:
            message(self.filename)
        if code in options.counters:
            options.counters[code] += 1
        else:
            options.counters[code] = 1
            options.messages[code] = text[5:]
        if options.quiet or code in self.expected:
            # Don't care about expected errors or warnings
            return
        self.file_errors += 1
        if options.counters[code] == 1 or options.repeat:
            print(err_format.format(
                path=self.filename,
                line=self.line_offset + line_number,
                column=offset + 1,
                type='E',
                message=text
            ))
>>>>>>> pr-1:bqlint/bqlint.py


def input_file(filename):
    """
    Run all checks on a Python source file.
    """
    if options.verbose:
        message('checking ' + filename)
    errors = Checker(filename).run()


def input_dir(dirname, runner=None):
    """
    Check all Python source files in this directory and all subdirectories.
    """
    dirname = dirname.rstrip('/')
    if excluded(dirname):
        return
    if runner is None:
        runner = input_file
    for root, dirs, files in os.walk(dirname):
        if options.verbose:
            message('directory ' + root)
        options.counters['directories'] += 1
        dirs.sort()
        excluded_dirs = []
        for subdir in dirs:
            if excluded(subdir):
                excluded_dirs.append(subdir)
        for subdir in excluded_dirs:
            dirs.remove(subdir)
        files.sort()
        for filename in files:
            if filename_match(filename) and not excluded(filename):
                options.counters['files'] += 1
                runner(os.path.join(root, filename))


def excluded(filename):
    """
    Check if options.exclude contains a pattern that matches filename.
    """
    basename = os.path.basename(filename)
    for pattern in options.exclude:
        if fnmatch(basename, pattern):
            # print basename, 'excluded because it matches', pattern
            return True


def filename_match(filename):
    """
    Check if options.filename contains a pattern that matches filename.
    If options.filename is unspecified, this always returns True.
    """
    if not options.filename:
        return True
    for pattern in options.filename:
        if fnmatch(filename, pattern):
            return True


def ignore_code(code):
    """
    Check if options.ignore contains a prefix of the error code.
    If options.select contains a prefix of the error code, do not ignore it.
    """
    for select in options.select:
        if code.startswith(select):
            return False
    for ignore in options.ignore:
        if code.startswith(ignore):
            return True


def get_count(prefix=''):
    """Return the total count of errors and warnings."""
    keys = list(options.messages.keys())
    count = 0
    for key in keys:
        if key.startswith(prefix):
            count += options.counters[key]
    return count


def process_options(arglist=None):
    """
    Process options passed either via arglist or via command line args.
    """
    global options, args
    parser = OptionParser(version=__version__,
                          usage="%prog [options] input ...")
    parser.add_option('-v', '--verbose', default=0, action='count',
                      help="print status messages, or debug with -vv")
    parser.add_option('-q', '--quiet', default=0, action='count',
                      help="report only file names, or nothing with -qq")
    parser.add_option('-r', '--repeat', action='store_true',
                      help="show all occurrences of the same error")
    parser.add_option('--exclude', metavar='patterns', default=DEFAULT_EXCLUDE,
                      help="exclude files or directories which match these "
                      "comma separated patterns (default: %s)" %
                      DEFAULT_EXCLUDE)
    parser.add_option('--filename', metavar='patterns', default='*.py',
                      help="when parsing directories, only check filenames "
                      "matching these comma separated patterns (default: "
                      "*.py)")
    parser.add_option('--select', metavar='errors', default='',
                      help="select errors and warnings (e.g. E,W6)")
    parser.add_option('--ignore', metavar='errors', default='',
                      help="skip errors and warnings (e.g. E4,W)")
    parser.add_option('--show-source', action='store_true',
                      help="show source code for each error")
    parser.add_option('--show-pep8', action='store_true',
                      help="show text of PEP 8 for each error")
    parser.add_option('--statistics', action='store_true',
                      help="count errors and warnings")
    parser.add_option('--count', action='store_true',
                      help="print total number of errors and warnings "
                      "to standard error and set exit code to 1 if "
                      "total is not null")
    parser.add_option('--benchmark', action='store_true',
                      help="measure processing speed")
    parser.add_option('--testsuite', metavar='dir',
                      help="run regression tests from dir")
    parser.add_option('--doctest', action='store_true',
                      help="run doctest on myself")
    options, args = parser.parse_args(arglist)
    if options.testsuite:
        args.append(options.testsuite)
    if not args and not options.doctest:
        parser.error('input not specified')
    options.prog = os.path.basename(sys.argv[0])
    options.exclude = options.exclude.split(',')
    for index in range(len(options.exclude)):
        options.exclude[index] = options.exclude[index].rstrip('/')
    if options.filename:
        options.filename = options.filename.split(',')
    if options.select:
        options.select = options.select.split(',')
    else:
        options.select = []
    if options.ignore:
        options.ignore = options.ignore.split(',')
    elif options.select:
        # Ignore all checks which are not explicitly selected
        options.ignore = ['']
    elif options.testsuite or options.doctest:
        # For doctest and testsuite, all checks are required
        options.ignore = []
    else:
        # The default choice: ignore controversial checks
        options.ignore = DEFAULT_IGNORE.split(',')
    options.physical_checks = find_checks('physical_line')
    options.token_checks = find_checks('token')
    options.logical_checks = find_checks('logical_line')
    options.counters = dict.fromkeys(BENCHMARK_KEYS, 0)
    options.messages = {}
    return options, args


def readlines(filename):
    return open(filename, encoding='latin-1').readlines()


def _main():
    """
    Parse options and run checks on Python source.
    """
    options, args = process_options()
    if options.doctest:
        import doctest
        doctest.testmod(verbose=options.verbose)
        # selftest()
    runner = input_file

    for path in args:
        if os.path.isdir(path):
            input_dir(path, runner=runner)
        elif not excluded(path):
            options.counters['files'] += 1
            runner(path)

    count = get_count()
    if count:
        if options.count:
            sys.stderr.write(str(count) + '\n')
        sys.exit(1)


if __name__ == '__main__':
    _main()

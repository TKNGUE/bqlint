#!/usr/bin/env python
# -*- coding: utf-8 -*-

__version__ = '0.5.1dev'

from optparse import OptionParser
from fnmatch import fnmatch

import os
import sys
import re
import inspect
import sqlparse


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
    "WINDOW" : sqlparse.tokens.Keyword
}


WHITESPACE = ' \t'

BINARY_OPERATORS = frozenset(['**=', '*=', '+=', '-=', '!=', '<>',
    '%=', '^=', '&=', '|=', '==', '/=', '//=', '<=', '>=', '<<=', '>>=',
    '%',  '^',  '&',  '|',  '=',  '/',  '//',  '<',  '>',  '<<'])
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
    (0, "W000 Don't use `--` comment string, you shoudld use `#` comment style")
    """
    try:
        offset = physical_line.index('--')
        return offset, "W000 Don't use `--` comment string, you shoudld use `#` comment style"
    except ValueError:
        pass


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
# Framework to run all checks
##############################################################################

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


class Checker():

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


    def check_token(self, token, offset):
        """
        Run all physical checks on a raw input line.
        """
        self.token = token
        self.offset = offset
        for name, check, argument_names in options.token_checks:
            result = self.run_check(check, argument_names)
            if result is not None:
                offset, text = result
                self.report_error(self.line_number, offset, text, check)


    def run_check(self, check, argument_names):
        """
        Run a check plugin.
        """
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

    def report_error(self, line_number, offset, text, check):
        """
        Report an error, according to options.
        """
        print(err_format.format(
            path=self.file_path, line=line_number, column=offset,
            type=text[0], message=text
        ))



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
        selftest()
    if options.testsuite:
        runner = run_tests
    else:
        runner = input_file

    for path in args:
        if os.path.isdir(path):
            input_dir(path, runner=runner)
        elif not excluded(path):
            options.counters['files'] += 1
            runner(path)

    if options.statistics:
        print_statistics()
    count = get_count()
    if count:
        if options.count:
            sys.stderr.write(str(count) + '\n')
        sys.exit(1)


if __name__ == '__main__':
    _main()

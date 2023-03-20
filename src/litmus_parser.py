#!/usr/bin/env python3

import os
import lark
from litmus import *


################################################################################
# Litmus test parser
################################################################################


file_path = os.path.dirname(os.path.realpath(__file__))
grammar_path = os.path.join(file_path, "grammar.lark")
with open(grammar_path, "r") as f:
    grammar = f.read()


class ParseException(Exception):
    def __init__(self, text, meta, message):
        text = text[meta.start_pos : meta.end_pos]
        text = " ".join([i.strip() for i in text.split("\n")])
        self.message = f"Line {meta.line}: '{text}': {message}"

    def __str__(self):
        return self.message


@lark.v_args(inline=True, meta=True)
class Transformer(lark.Transformer):
    def __init__(self, text, model):
        self.text = text
        self.instruction_count = 0
        self.model = model

    def _new_id(self):
        c = self.instruction_count
        self.instruction_count += 1
        return f"i{c}"

    def start(self, meta, address_decls, threads, commands):
        return LitmusTest(
            model=self.model,
            addresses=address_decls.children,
            threads=threads.children,
            commands=commands.children,
        )

    def thread(self, meta, tid, *insts):
        return Thread(tid, insts)

    def address_decl(self, meta, space, name, alias_type=None, alias=None):
        return Address(name, space, alias_type, alias)

    def aliases(self, meta, *aliases):
        return aliases

    def _check_sem_scope(self, meta, sem, scope):
        if sem is None:
            sem = "weak"
        if sem in ["volatile", "weak"]:
            if scope:
                raise ParseException(
                    self.text,
                    meta,
                    f"illegal encoding: .{sem} accesses should not have scope",
                )
        if sem == "volatile":
            return "relaxed", "sys"
        elif sem == "weak":
            return "weak", None
        else:
            return sem, scope

    def load(self, meta, op, sem, scope, dst, src, return_value):
        proxy = {
            "ld": "generic",
            "tld": "texture",
            "suld": "surface",
            "ldc": "constant",
        }[op]
        sem, scope = self._check_sem_scope(meta, sem, scope)
        return Load(
            name=self._new_id(),
            op=op,
            sem=sem,
            scope=scope,
            proxy=proxy,
            dst=dst,
            src=src,
            return_value=return_value,
            line=meta.line,
        )

    def store(self, meta, op, sem, scope, dst, value):
        proxy = {
            "st": "generic",
            "sust": "surface",
        }[op]
        sem, scope = self._check_sem_scope(meta, sem, scope)
        return Store(
            name=self._new_id(),
            op=op,
            sem=sem,
            scope=scope,
            proxy=proxy,
            dst=dst,
            value=value,
            line=meta.line,
        )

    def atom(
        self, meta, op, atomic_op, sem, scope, dst, src, value, return_value
    ):
        proxy = {
            "atom": "generic",
            "suatom": "surface",
            "red": "generic",
            "sured": "surface",
        }[op]
        if sem == "volatile":
            raise ParseException(self.text, meta, "illegal modifier .volatile")
        return Atom(
            name=self._new_id(),
            op=op,
            sem=sem,
            scope=scope,
            proxy=proxy,
            atomic_op=atomic_op,
            src=src,
            dst=dst,
            value=value,
            return_value=return_value,
            line=meta.line,
        )

    def red(self, meta, op, atomic_op, sem, scope, src, value):
        if sem == "volatile":
            raise ParseException(self.text, meta, "illegal modifier .volatile")
        return atom(
            name=self._new_id(),
            op=op,
            sem=sem,
            scope=scope,
            atomic_op=atomic_op,
            dst=None,
            src=src,
            value=value,
            return_value=NoValue(),
            line=meta.line,
        )

    def fence(self, meta, op, sem, scope):
        if sem == "volatile":
            raise ParseException(self.text, meta, "illegal modifier .volatile")

        return Fence(
            name=self._new_id(),
            sem=sem,
            scope=scope,
            line=meta.line,
        )

    def proxy_fence(self, meta, op, proxy):
        if proxy == "alias":
            return AliasFence(name=self._new_id(), line=meta.line)
        else:
            return ProxyFence(
                name=self._new_id(), proxy=proxy, line=meta.line
            )

    def alias_fence(self, meta, op):
        return AliasFence(name=self._new_id(), line=meta.line)

    def sem(self, meta, dot=None, arg=None):
        if arg:
            return str(arg)
        else:
            return None

    def scope(self, meta, dot=None, arg=None):
        if arg:
            return str(arg)
        else:
            return None

    def weak(self, meta, *args):
        return None

    def none(self, meta):
        return None

    def return_value(self, meta, *args):
        if args:
            return args[0]
        else:
            return NoValue()

    def atomic_op(self, meta, arg):
        return str(arg)

    def scope_tree(self, meta, d, b=None, t=None):
        if b is not None:
            b = int(b)
        if t is not None:
            t = int(t)
        return ThreadID(int(d), b, t, line=meta.line)

    def thread_scope_tree(self, meta, d, b, t):
        return ThreadID(int(d), int(b), int(t), line=meta.line)

    def reg(self, meta, reg):
        return NamedValue(f"r{reg}")

    def integer(self, meta, n):
        return Integer(int(n))

    def eq(self, meta, left, right):
        return Equal(left, right)

    def neq(self, meta, left, right):
        return Not(Equal(left, right))

    def value_list(self, meta, *values):
        return values

    def and_(self, meta, left, right):
        return And(left, right)

    def or_(self, meta, left, right):
        return Or(left, right)

    def not_(self, meta, expr):
        return Not(expr)

    def condition(self, meta, cmd):
        return cmd

    def num(self, meta, n):
        return int(n)

    def num_value(self, meta, n):
        return Integer(n)

    def no_name(self, meta):
        return ""

    def check(self, meta, expr, name):
        if not name:
            name = f"command{len(self.test.commands)}"
        name = f"check_{name}"
        return Command(name, expr, expected=True, line=meta.line)

    def permit(self, meta, expr, name):
        if not name:
            name = f"command{len(self.test.commands)}"
        return Command(name, expr, expected=True, line=meta.line)

    def assert_(self, meta, expr, name):
        if not name:
            name = f"command{len(self.test.commands)}"
        return Command(name, expr, expected=False, line=meta.line)


_parser = lark.Lark(grammar, propagate_positions=True)


def parse(model, contents):
    return Transformer(contents, model).transform(_parser.parse(contents))


if __name__ == "__main__":
    import sys

    test = parse(sys.stdin.read())
    print(test)

    expanded = test.expand_operations()
    print(expanded)

    alloy = expanded.to_alloy()
    print(alloy)

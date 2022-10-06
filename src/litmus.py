#!/usr/bin/env python3

import alloy_emitter

_s = alloy_emitter._s


################################################################################
# Exception class with line number information
################################################################################


class LitmusException(Exception):
    def __init__(self, line, msg):
        self.line = line
        self.msg = msg

    def __str__(self):
        return f"Line {self.line}: {self.msg}"


################################################################################
# __str__ helper functions
################################################################################


def _a(arg):
    "print the address in brackets if given, or '_' if not"
    if arg is None:
        return "_"
    else:
        return f"[{arg}]"


def _n(name):
    "print `name` with at least 24 characters of spacing`"
    return f"{name: <24}:"


################################################################################
# Litmus test abstract syntax tree
################################################################################


class Address:
    def __init__(self, name, space, alias_type=None, alias=None):
        self.name = name
        self.space = space
        self.alias_type = alias_type
        self.alias = alias

    def __str__(self):
        r = f".{self.space} {self.name}"
        if self.alias_type:
            r += f" {self.alias_type} aliases {self.alias}"
        return r

    def to_alloy(self, test):
        if self.alias_type is None:
            test.alloy_emitter.address(self.name, None)
        elif self.alias_type == "virtually":
            test.alloy_emitter.virtual_synonym(self.name, self.alias)
        elif self.alias_type == "physically":
            test.alloy_emitter.address(self.name, self.alias)
        else:
            raise Exception(f"unknown alias type '{self.alias_type}'")


class ThreadID:
    def __init__(self, d, b, t, line=None):
        self.d = d
        self.b = b
        self.t = t
        self.line = line

    def __str__(self):
        return self.thread()

    def thread(self):
        assert self.t is not None
        return f"{self.block()}_t{self.t}"

    def block(self):
        assert self.b is not None
        return f"{self.device()}_b{self.b}"

    def device(self):
        assert self.d is not None
        return f"d{self.d}"

    def fork(self, name, line):
        return ThreadID(self.d, self.b, self.t, name, line=line)

    def to_alloy(self, test):
        test.alloy_emitter.thread(
            self.device(),
            self.block(),
            self.thread(),
            self.line,
        )


class Thread:
    def __init__(self, tid, insts):
        self.tid = tid
        self.insts = insts

    def __str__(self):
        txt = f"// Thread {self.tid}\n"
        txt += "".join([f"{i};\n" for i in self.insts])
        txt += "\n"
        return txt

    def append(self, inst):
        self.insts.append(inst)

    def __iadd__(self, insts):
        self.insts += insts
        return self

    def to_alloy(self, test):
        self.tid.to_alloy(test)
        for i in self.insts:
            i.to_alloy(test, self.tid)


################################################################################
# Value types
################################################################################


class Value:
    pass


class NoValue(Value):
    def __str__(self):
        return "NoValue"

    def to_alloy(self, test):
        return None


class NamedValue(Value):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

    def to_alloy(self, test):
        return test.alloy_emitter.value(self.name)


class Integer(Value):
    def __init__(self, n):
        self.n = n

    def __str__(self):
        return str(self.n)

    def to_alloy(self, test):
        return test.alloy_emitter.integer(self.n)


class Arithmetic(Value):
    def __init__(self, op, values):
        self.op = op
        self.values = values

    def __str__(self):
        return "(" + f" {self.op} ".join(map(str, self.values)) + ")"

    def to_alloy(self, test):
        return test.alloy_emitter.integer(
            self.op, [i.to_alloy(test) for i in self.values]
        )


################################################################################
# Instructions
################################################################################


class Instruction:
    pass


class Load(Instruction):
    def __init__(
        self, name, op, sem, scope, proxy, dst, src, return_value, line=None
    ):
        self.name = name
        self.op = op
        self.sem = sem
        self.scope = scope
        self.proxy = proxy
        self.dst = dst
        self.src = src
        self.return_value = return_value
        self.line = line

    def __str__(self):
        return (
            f"{_n(self.name)} ld{_s(self.sem)}{_s(self.scope)}{_s(self.proxy)} "
            f"{self.dst}, {_a(self.src)}{_s(self.return_value, ' == ')}"
        )

    def to_alloy(self, test, tid):
        test.alloy_emitter.load(
            self.name,
            self.sem,
            self.scope,
            self.proxy,
            self.dst,
            self.src,
            self.return_value.to_alloy(test),
            self.line,
        )


class Store(Instruction):
    def __init__(
        self, name, op, sem, scope, proxy, dst, value, is_rmw=False, line=None
    ):
        self.name = name
        self.op = op
        self.sem = sem
        self.scope = scope
        self.proxy = proxy
        self.dst = dst
        self.value = value
        self.is_rmw = is_rmw
        self.line = line

    def __str__(self):
        return (
            f"{_n(self.name)} {_s(self.op, '')}{_s(self.sem)}"
            f"{_s(self.scope)}{_s(self.proxy)} "
            f"{_a(self.dst)}, {self.value}"
        )

        return txt

    def to_alloy(self, test, tid):
        test.alloy_emitter.store(
            self.name,
            self.sem,
            self.scope,
            self.proxy,
            self.dst,
            self.value.to_alloy(test),
            False,
            line=self.line,
        )


class Atom(Instruction):
    def __init__(
        self,
        name,
        op,
        atomic_op,
        sem,
        scope,
        proxy,
        dst,
        src,
        value,
        return_value,
        line=None,
    ):
        self.name = name
        self.op = op
        self.atomic_op = atomic_op
        self.sem = sem
        self.scope = scope
        self.proxy = proxy
        self.dst = dst
        self.src = src
        self.value = value
        self.return_value = return_value
        self.line = line

    def __str__(self):
        return (
            f"{_n(self.name)} {_s(self.op, '')}{_s(self.sem)}"
            f"{_s(self.scope)}{_s(self.proxy)} "
            f"{self.dst}, {_a(self.src)}, {_s(self.value)}"
            f"{_s(self.return_value, ' == ')}"
        )

    def to_alloy(self, test, tid):
        test.alloy_emitter.atom(
            self.name,
            self.atomic_op,
            self.sem,
            self.scope,
            self.proxy,
            self.dst,
            self.src,
            self.value.to_alloy(test),
            self.return_value.to_alloy(test),
            line=self.line,
        )


class Fence(Instruction):
    def __init__(self, name, sem, scope, line=None):
        self.name = name
        self.sem = sem
        self.scope = scope
        self.line = line

    def __str__(self):
        return f"{_n(self.name)} fence{_s(self.sem)}{_s(self.scope)}"

    def to_alloy(self, test, tid):
        test.alloy_emitter.fence(
            self.name, self.sem, self.scope, line=self.line
        )


class ProxyFence(Instruction):
    def __init__(self, name, proxy, line=None):
        self.name = name
        self.proxy = proxy
        self.line = line

    def __str__(self):
        return f"{_n(self.name)} fence.proxy{_s(self.proxy)}"

    def to_alloy(self, test, tid):
        test.alloy_emitter.proxy_fence(
            self.name, self.proxy, line=self.line
        )


class AliasFence(Instruction):
    def __init__(self, name, line=None):
        self.name = name
        self.line = line

    def __str__(self):
        return f"{_n(self.name)} fence.alias"

    def to_alloy(self, test, tid):
        test.alloy_emitter.alias_fence(self.name, line=self.line)


################################################################################
# Commands
################################################################################


class Command:
    def __init__(self, name, expr, expected, line=None):
        self.name = name
        self.expr = expr
        self.expected = expected
        self.line = line

    def to_alloy(self, test):
        expr = self.expr.to_alloy(test)
        test.alloy_emitter.command(
            "sanity_" + self.name, expr, True, True, line=self.line
        )
        test.alloy_emitter.command(
            self.name, expr, False, self.expected, line=self.line
        )

    def __str__(self):
        return f"{self.name}: {self.expr} (expect permitted={self.expected})"


class Condition:
    def __init__(self, op, a, b):
        self.op = op
        self.a = a
        self.b = b

    def __str__(self):
        return f"({self.a} {self.op} {self.b})"

    def to_alloy(self, test):
        return f"({self.a.to_alloy()} {self.op} {self.b.to_alloy()})"


class Not(Condition):
    def __init__(self, a):
        self.a = a

    def __str__(self):
        return f"(not {self.a})"

    def to_alloy(self, test):
        return test.alloy_emitter.command_not(self.a.to_alloy(test))


class And(Condition):
    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __str__(self):
        return f"({self.a} and {self.b})"

    def to_alloy(self, test):
        return test.alloy_emitter.command_and(
            self.a.to_alloy(test), self.b.to_alloy(test)
        )


class Or(Condition):
    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __str__(self):
        return f"({self.a} or {self.b})"

    def to_alloy(self, test):
        return test.alloy_emitter.command_or(
            self.a.to_alloy(test), self.b.to_alloy(test)
        )


class Not(Condition):
    def __init__(self, a):
        self.a = a

    def __str__(self):
        return f"not {self.a}"

    def to_alloy(self, test):
        return test.alloy_emitter.command_not(self.a.to_alloy(test))


class Equal(Condition):
    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __str__(self):
        return f"({self.a} == {self.b})"

    def to_alloy(self, test):
        return test.alloy_emitter.command_equal(
            self.a.to_alloy(test), self.b.to_alloy(test)
        )


################################################################################
# Litmus Test
################################################################################


class LitmusTest:
    def __init__(self, model, addresses, threads, commands):
        self.addresses = {a.name: a for a in addresses}
        self.threads = {t.tid: t for t in threads}
        self.commands = {c.name: c for c in commands}

        self.alloy_emitter = alloy_emitter.AlloyEmitter(model)

    def __str__(self):
        s = ""

        s += "Addresses:\n"
        for a in self.addresses.values():
            s += f"{a}\n"
        s += "\n"

        s += "Instructions:\n"
        s += "".join(map(str, self.threads.values()))

        s += "Commands:\n"
        s += "".join(map(str, self.commands.values()))

        return s

    def to_alloy(self):
        # Emit addresses
        for a in self.addresses.values():
            a.to_alloy(self)

        # Emit threads
        for t in self.threads.values():
            t.to_alloy(self)

        # Emit commands
        self.alloy_emitter.command("sanity", "", True, True, None)
        for c in self.commands.values():
            c.to_alloy(self)

        return self.alloy_emitter.text
